"""
Regression tests: batch sub-operations must run with the authenticated
caller's claims, never claims supplied in the request body.

See docs/reviews/2026-07-26-batch-claims-spoofing-review.md for the finding
this guards against: previously, BatchOperationHandler._execute_operation()
read `claims = op_def.get("claims", {})` straight from the client-supplied
batch request body, letting a request grant an arbitrary role (or spoof
`sub`/`tenant_id`) to any sub-operation.
"""

import pytest

from api_foundry_query_engine.dao.batch_operation_handler import (
    BatchOperationHandler,
)
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.app_exception import ApplicationException


class MockConnection:
    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.mark.unit
def test_batch_operation_rejects_client_supplied_claims():
    """A batch request must not be able to set 'claims' on a sub-operation."""
    batch_request = {
        "operations": [
            {
                "entity": "employee",
                "action": "update",
                "store_params": {"salary": 999999},
                "claims": {"roles": ["admin"]},
            }
        ]
    }

    with pytest.raises(ApplicationException) as exc_info:
        BatchOperationHandler(batch_request, MockConnection(), "postgres")

    assert exc_info.value.status_code == 400
    assert "claims" in exc_info.value.message.lower()


@pytest.mark.unit
def test_batch_sub_operations_use_authenticated_caller_claims(monkeypatch):
    """Every sub-operation must run with the claims passed to the handler's
    constructor (the real, token-validated caller identity), not anything
    derived from the batch request body."""
    captured = []

    def fake_execute(self, connector, operation=None):
        captured.append(self.operation.claims)
        return []

    monkeypatch.setattr(OperationDAO, "execute", fake_execute)

    batch_request = {
        "operations": [
            {"entity": "album", "action": "read", "query_params": {}},
            {"entity": "artist", "action": "read", "query_params": {}},
        ]
    }

    handler = BatchOperationHandler(
        batch_request,
        MockConnection(),
        "postgres",
        claims={"roles": ["public"], "sub": "user-123"},
    )
    handler.execute()

    assert len(captured) == 2
    for claims in captured:
        assert claims == {"roles": ["public"], "sub": "user-123"}


@pytest.mark.unit
def test_batch_defaults_to_no_claims_when_none_provided(monkeypatch):
    """Without an explicit claims argument, sub-operations run anonymously
    (empty claims) rather than inheriting anything from the request body."""
    captured = []

    def fake_execute(self, connector, operation=None):
        captured.append(self.operation.claims)
        return []

    monkeypatch.setattr(OperationDAO, "execute", fake_execute)

    batch_request = {
        "operations": [
            {"entity": "album", "action": "read", "query_params": {}},
        ]
    }

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")
    handler.execute()

    assert captured == [{}]

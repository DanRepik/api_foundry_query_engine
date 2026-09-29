"""TransactionalService routing for batch operations.

"batch" is not an entity in the API model, so the service has to find the
database from the batch's sub-operations. It used to look "batch" up like
any other entity and reject every batch with "Unknown operation: batch"
before OperationDAO's batch handling was ever reached.
"""

from types import SimpleNamespace

import pytest

import api_foundry_query_engine.services.transactional_service as service_module
import api_foundry_query_engine.utils.api_model as api_model_module
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService
from api_foundry_query_engine.utils.app_exception import ApplicationException


class _FakeConnection:
    def __init__(self):
        self.committed = False
        self.closed = False

    def engine(self):
        return "postgres"

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.fixture
def service(monkeypatch):
    """A TransactionalService over a two-database stand-in model, with the
    connection factory and OperationDAO replaced so no database is needed."""
    api_model_module.api_model = SimpleNamespace(
        schema_objects={
            "invoice": SimpleNamespace(database="sales"),
            "invoice_line": SimpleNamespace(database="sales"),
            "audit_entry": SimpleNamespace(database="audit"),
        },
        path_operations={"top_albums_read": SimpleNamespace(database="sales")},
    )

    requested = []
    connection = _FakeConnection()

    class FakeFactory:
        def __init__(self, _config):
            pass

        def get_connection(self, database):
            requested.append(database)
            return connection

    class FakeDAO:
        def __init__(self, operation, engine):
            self.operation = operation

        def execute(self, _connection):
            return {"success": True, "results": {}}

    monkeypatch.setattr(service_module, "ConnectionFactory", FakeFactory)
    monkeypatch.setattr(service_module, "OperationDAO", FakeDAO)
    return SimpleNamespace(service=TransactionalService({}), requested=requested, connection=connection)


def _batch(*operations):
    return Operation(
        entity="batch",
        action="create",
        store_params={"operations": list(operations), "options": {"atomic": False}},
    )


@pytest.mark.unit
def test_batch_runs_against_its_operations_database(service):
    result = service.service.execute(
        _batch(
            {"entity": "invoice", "action": "create", "store_params": {}},
            {"entity": "invoice_line", "action": "create", "store_params": {}},
        )
    )

    assert result == [{"success": True, "results": {}}]
    assert service.requested == ["sales"]
    assert service.connection.committed and service.connection.closed


@pytest.mark.unit
def test_batch_database_can_come_from_a_path_operation(service):
    service.service.execute(_batch({"entity": "top_albums", "action": "read"}))

    assert service.requested == ["sales"]


@pytest.mark.unit
def test_unknown_sub_operations_do_not_pick_the_database(service):
    """An unknown entity fails on its own inside the batch; the batch still
    runs against the database its known operations use."""
    service.service.execute(
        _batch(
            {"entity": "no_such_entity", "action": "create"},
            {"entity": "invoice", "action": "create"},
        )
    )

    assert service.requested == ["sales"]


@pytest.mark.unit
def test_batch_across_databases_is_rejected(service):
    with pytest.raises(ApplicationException) as error:
        service.service.execute(
            _batch(
                {"entity": "invoice", "action": "create"},
                {"entity": "audit_entry", "action": "create"},
            )
        )

    assert error.value.status_code == 400
    assert "audit, sales" in error.value.message
    assert service.requested == []


@pytest.mark.unit
@pytest.mark.parametrize("store_params", [{}, {"operations": []}, {"operations": "invoice"}, None])
def test_batch_without_operations_is_rejected(service, store_params):
    operation = Operation(entity="batch", action="create", store_params=store_params)

    with pytest.raises(ApplicationException) as error:
        service.service.execute(operation)

    assert error.value.status_code == 400
    assert service.requested == []


@pytest.mark.unit
def test_batch_of_only_unknown_entities_is_unknown(service):
    with pytest.raises(ApplicationException) as error:
        service.service.execute(_batch({"entity": "no_such_entity", "action": "create"}))

    assert error.value.status_code == 500
    assert "Unknown operation" in error.value.message


@pytest.mark.unit
def test_unknown_entity_is_still_rejected(service):
    with pytest.raises(ApplicationException) as error:
        service.service.execute(Operation(entity="no_such_entity", action="read"))

    assert error.value.status_code == 500
    assert error.value.message == "Unknown operation: no_such_entity"


@pytest.mark.integration
def test_batch_through_the_service(chinook_env):
    """A non-atomic, continue-on-error batch of inserts end to end, the way
    new-america-contract's qr-scan-import Lambda calls it."""
    service = TransactionalService(chinook_env)
    response = service.execute(
        Operation(
            entity="batch",
            action="create",
            store_params={
                "operations": [
                    {"id": "a", "entity": "media_type", "action": "create", "store_params": {"name": "Batch A"}},
                    {"id": "b", "entity": "media_type", "action": "create", "store_params": {"name": "Batch B"}},
                ],
                "options": {"atomic": False, "continueOnError": True},
            },
        )
    )[0]

    assert response["success"] is True
    assert {op_id: result["status"] for op_id, result in response["results"].items()} == {
        "a": "completed",
        "b": "completed",
    }

    for op_id in ("a", "b"):
        media_type_id = response["results"][op_id]["data"]["media_type_id"]
        service.execute(Operation(entity="media_type", action="delete", query_params={"media_type_id": media_type_id}))

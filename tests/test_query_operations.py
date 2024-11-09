import json
import pytest

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService

from test_fixtures import load_model, db_secrets  # noqa F811

log = logger(__name__)


@pytest.mark.integration
class TestQueryOperations:
    def test_select_all(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(entity="media_type", action="read")
        )
        log.debug(f"len: {len(result)}")
        assert len(result) == 5

    def test_select_one(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice", action="read", query_params={"invoice_id": 2}
            )
        )
        log.info(f"result: {json.dumps(result, indent=4)}")
        assert len(result) == 1
        assert result[0]["invoice_id"] == 2

    def test_select_multiple(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "in::5.94,3.96", "billing_country": "USA"},
            )
        )
        log.info(f"count: {len(result)}")
        assert len(result) == 24

    def test_select_invalid(self, load_model, db_secrets):  # noqa F811
        try:
            TransactionalService().execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"otal": 5.94, "billing_country": "USA"},
                )
            )
            assert False, "Invalid parameter did not throw exception"
        except ApplicationException as ae:
            assert ae.status_code == 500
            assert (
                ae.message
                == "Invalid query parameter, property not found. schema object: invoice, property: otal"
            )

    def test_select_gt_le_int(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "gt::5"},
            )
        )
        log.info(f"result: {json.dumps(result, indent=4)}")
        gt_count = len(result)

        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "le::5"},
            )
        )
        log.info(f"le_count: {json.dumps(result, indent=4)}")
        le_count = len(result)

        result = TransactionalService().execute(
            Operation(entity="invoice", action="read")
        )
        total_count = len(result)
        log.info(f"total_count: {total_count}")

        assert total_count == gt_count + le_count

    def test_select_ge_lt_int(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "ge::5"},
            )
        )
        ge_count = len(result)

        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "lt::5"},
            )
        )
        lt_count = len(result)
        log.info(f"lt_count: {lt_count}")

        result = TransactionalService().execute(
            Operation(entity="invoice", action="read")
        )
        total_count = len(result)
        log.info(f"total_count: {total_count}")

        assert total_count == ge_count + lt_count

    def test_select_between_int(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "between::4,6"},
            )
        )
        between_count = len(result)
        log.info(f"between_count: {between_count}")

        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "not-between::4,6"},
            )
        )
        not_between_count = len(result)
        log.info(f"not_between_count: {not_between_count}")

        result = TransactionalService().execute(
            Operation(entity="invoice", action="read")
        )
        total_count = len(result)
        log.info(f"total_count: {total_count}")

        assert total_count == between_count + not_between_count

    def test_select_in_int(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "in::5.94,3.96"},
            )
        )
        in_count = len(result)
        log.info(f"in_count: {in_count}")

        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"total": "not-in::5.94,3.96"},
            )
        )
        not_in_count = len(result)
        log.info(f"not_in_count: {not_in_count}")

        result = TransactionalService().execute(
            Operation(entity="invoice", action="read")
        )
        total_count = len(result)
        log.info(f"total_count: {total_count}")

        assert total_count == in_count + not_in_count

    def test_select_ge_lt_timestamp(self, load_model, db_secrets):  # noqa F811
        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_date": "ge::2025-01-02T00:00:00.000"},
            )
        )
        ge_count = len(result)
        log.info(f"ge_count: {ge_count}")

        result = TransactionalService().execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_date": "lt::2025-01-02T00:00:00.000"},
            )
        )
        lt_count = len(result)
        log.info(f"lt_count: {lt_count}")

        result = TransactionalService().execute(
            Operation(entity="invoice", action="read")
        )
        total_count = len(result)
        log.info(f"total_count: {total_count}")

        assert total_count == ge_count + lt_count

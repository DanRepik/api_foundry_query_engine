import pytest

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService

log = logger(__name__)


def _media_type_row_count(chinook_env) -> int:
    # Other tests in the session insert media types into the shared Chinook
    # database, so the expected count is read from the table itself rather
    # than hard-coded to the seed data's 5 -- the assertion is that the
    # engine returns every row, whatever the table holds.
    import psycopg2

    with psycopg2.connect(chinook_env["chinook_secret"]["dsn"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM media_type")
        return cur.fetchone()[0]

@pytest.mark.integration
class TestMetadataOperations:
    def test_count(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="media_type",
                action="read",
                metadata_params={"count": True},
            )
        )
        log.debug(f"result: {result}")
        assert isinstance(result, list)
        assert result[0]["count"] == _media_type_row_count(chinook_env)

    def test_order(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="customer",
                action="read",
                metadata_params={"sort": "phone"},
            )
        )
        log.debug(f"result: {result[0]}")
        assert isinstance(result, list)
        assert result[0]["first_name"] == "Aaron"
        assert result[0]["last_name"] == "Mitchell"

    def test_order_invalid_1(self, chinook_env):  # noqa F811
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="customer",
                    action="read",
                    metadata_params={"sort": "x-phone"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid order by property, schema object: customer does not have a property: x-phone"  # noqa E501
            )

    def test_order_invalid_2(self, chinook_env):  # noqa F811
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    metadata_params={"sort": "customerx.phone"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid order by property, schema object: invoice does not have a property: customerx"  # noqa E501
            )

    def test_order_invalid_3(self, chinook_env):  # noqa F811
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    metadata_params={"sort": "customer.phonex"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid order by property, schema object: customer does not have a property: phonex"  # noqa E501
            )

    def test_order_asc(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="customer",
                action="read",
                metadata_params={"sort": "phone:asc"},
            )
        )
        log.debug(f"result: {result[0]}")
        assert isinstance(result, list)
        assert result[0]["first_name"] == "Aaron"
        assert result[0]["last_name"] == "Mitchell"

    def test_order_desc(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="customer",
                action="read",
                metadata_params={"sort": "last_name:desc"},
            )
        )
        log.debug(f"result: {result[0]}")
        assert isinstance(result, list)
        assert result[0]["customer_id"] == 37
        assert result[0]["last_name"] == "Zimmermann"

    def test_order_using_object(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                metadata_params={"sort": "customer.phone,invoice_date"},
            )
        )
        log.debug(f"result: {result[0]}")
        assert isinstance(result, list)
        assert result[0]["invoice_id"] == 50
        assert result[0]["billing_address"] == "696 Osborne Street"

    def test_limit(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(entity="invoice", action="read", metadata_params={"limit": 50})
        )
        log.debug(f"result: {len(result)}")
        assert len(result) == 50

    def test_limit_invalid(self, chinook_env):  # noqa F811
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    metadata_params={"limit": "50x"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert ae.message == "Limit is not an valid integer 50x"

    def test_offset(self, chinook_env):  # noqa F811
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                metadata_params={"sort": "invoice_id:asc", "limit": 1, "offset": 50},
            )
        )
        log.debug(f"result: {result[0]}")
        assert len(result) == 1
        assert result[0]["invoice_id"] == 51

    def test_offset_invalid(self, chinook_env):  # noqa F811
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    metadata_params={"offset": "50x"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert ae.message == "Offset is not an valid integer 50x"

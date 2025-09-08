import pytest

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService

from tests.test_schema_objects_fixtures import load_api

log = logger(__name__)


@pytest.mark.integration
class TestAssociationOperations:
    def test_object_property(self, chinook_env):  # noqa F811
        load_api()
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_id": 5},
                metadata_params={"properties": ".* customer:.*"},
            )
        )

        log.debug(f"len: {len(result)}")
        invoice = result[0]
        log.debug(f"invoice: {invoice}")

        assert invoice["customer"]
        assert invoice["customer_id"] == invoice["customer"]["customer_id"]
        assert invoice["customer"]["city"] == "Boston"

    def test_invalid_object_property(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"invoice_id": 5},
                    metadata_params={"properties": ".* custom:.*"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Bad object association: invoice does not have a custom property"
            )

    def test_object_property_criteria(self, chinook_env):  # noqa F811
        load_api()
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"customer.phone": "+420 2 4172 5555"},
            )
        )

        log.debug(f"len: {len(result)}")
        assert len(result) == 7
        invoice = result[3]
        log.debug(f"invoice: {invoice}")

        assert "customer" not in invoice
        assert invoice["customer_id"] == 5
        assert invoice["billing_city"] == "Prague"

    def test_invalid_object_property_criteria_1(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"custom.customer_id": 5},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid selection property invoice does not have a property custom"
            )

    def test_invalid_object_property_criteria_2(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"custom.custom_id": 5},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid selection property invoice does not have a property custom"
            )

    def test_array_property(self, chinook_env):  # noqa F811
        load_api()
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_id": 5},
                metadata_params={"properties": ".* invoice_line_items:.*"},
            )
        )

        log.debug(f"len: {len(result)}")
        invoice = result[0]
        log.debug(f"invoice: {invoice}")
        log.debug(f"line_item: {invoice['invoice_line_items'][0]}")

        assert invoice["invoice_line_items"]
        assert invoice["invoice_id"] == invoice["invoice_line_items"][0]["invoice_id"]
        assert invoice["invoice_line_items"][0]["invoice_id"] == 5
        assert invoice["invoice_line_items"][0]["track_id"] == 99

    def test_array_property_criteria(self, chinook_env):  # noqa F811
        load_api()
        result = TransactionalService(chinook_env).execute(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_line_items.track_id": 298},
            )
        )

        log.debug(f"len: {len(result)}")
        assert len(result) == 2
        invoice = result[0]
        log.debug(f"invoice: {invoice}")

        assert "customer" not in invoice
        assert result[0]["billing_country"] in ["United Kingdom", "Brazil"]
        assert result[1]["billing_country"] in ["United Kingdom", "Brazil"]

    def test_invalid_array_property(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"invoice_id": 5},
                    metadata_params={"properties": ".* line_items:.*"},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Bad object association: invoice does not have a line_items property"
            )

    def test_invalid_array_property_criteria_1(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"line_itms.line_item_id": 5},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid selection property invoice does not have a property line_itms"  # noqa E501
            )

    def test_invalid_array_property_criteria_2(self, chinook_env):  # noqa F811
        load_api()
        try:
            TransactionalService(chinook_env).execute(
                Operation(
                    entity="invoice",
                    action="read",
                    query_params={"line_items.line_item_id": 5},
                )
            )
            assert False, "Missing exception"
        except ApplicationException as ae:
            assert ae.status_code == 400
            assert (
                ae.message
                == "Invalid selection property invoice does not have a property line_items"  # noqa E501
            )

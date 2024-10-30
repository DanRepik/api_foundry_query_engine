import pytest

from datetime import date, datetime, timezone
import os

from api_foundry_query_engine.utils.api_model import APIModel, get_schema_object
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.dao.sql_delete_query_handler import (
    SQLDeleteSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_select_query_handler import (
    SQLSelectSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_subselect_query_handler import (
    SQLSubselectSchemaQueryHandler,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import (
    SchemaObject,
    SchemaObjectProperty,
)
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.logger import logger
from tests.test_schema_objects_fixtures import (
    invoice_with_datetime_version_stamp,
    genre_schema_with_timestamp,
    load_api,
)

log = logger(__name__)


@pytest.mark.unit
class TestSQLHandler:
    def test_field_selection(self):
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(path="invoice", action="read"),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )
        log.info(f"prefix_map: {sql_handler.prefix_map}")
        result_map = sql_handler.selection_result_map()
        log.info(f"result_map: {result_map}")
        assert len(result_map) == 10
        assert result_map.get("i.invoice_id") is not None

    def test_field_selection_with_association(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                metadata_params={"properties": ".* customer:.*"},
            ),
            get_schema_object("invoice"),
            "postgres",
        )

        result_map = sql_handler.selection_result_map()
        log.info(f"result_map: {result_map}")
        assert len(result_map) == 24
        assert result_map.get("i.invoice_id") is not None
        assert result_map.get("c.customer_id") is not None
        log.info(f"select_list: {sql_handler.select_list}")
        assert "i.invoice_id" in sql_handler.select_list
        assert "c.customer_id" in sql_handler.select_list

    def test_search_condition(self):
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"invoice_id": "24", "total": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total " 
            + "FROM invoice AS i " 
            + "WHERE i.invoice_id = %(i_invoice_id)s AND i.total > %(i_total)s"  # noqa E501
        )
        assert sql_handler.placeholders == {"i_invoice_id": 24, "i_total": 5.0}

    @pytest.mark.skip
    def test_search_on_m_property(self):
        try:
            operation_dao = OperationDAO(
                Operation(
                    path="invoice",
                    action="read",
                    query_params={"invoice_id": "24", "line_items.track_id": "gt::5"},
                    metadata_params={"_properties": ".* customer:.*"},
                ),
                "postgres",
            )

            sql_handler = operation_dao.query_handler
            log.info(f"sql_handler: {sql_handler}")

            log.info(f"sql: {sql_handler.sql}")
            assert False

        except ApplicationException as e:
            assert (
                e.message
                == "Queries using properties in arrays is not supported. schema object: invoice, property: line_items.track_id"  # noqa E501
            )

    def test_search_invalid_property(self):
        try:
            operation_dao = OperationDAO(
                Operation(
                    path="invoice",
                    action="read",
                    query_params={"invoice_id": "24", "track_id": "gt::5"},
                ),
                "postgres",
            )

            sql_operation = operation_dao.query_handler
            log.info(f"sql_operation: {sql_operation}")

            log.info(f"sql: {sql_operation.sql}")
            assert False
        except ApplicationException as e:
            assert (
                e.message
                == "Invalid query parameter, property not found. schema object: invoice, property: track_id"  # noqa E501
            )

    def test_search_association_property(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        try:
            operation_dao = OperationDAO(
                Operation(
                    path="invoice",
                    action="read",
                    query_params={
                        "invoice_id": "gt::24",
                        "customer.customer_id": "gt::5",
                    },
                ),
                "postgres",
            )

            sql_operation = operation_dao.query_handler
            log.info(f"sql_handler: {sql_operation}")

            log.info(
                f"sql: {sql_operation.sql}, placeholders: {sql_operation.placeholders}"
            )
            assert (
                sql_operation.sql
                == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total " 
                + "FROM invoice AS i " 
                + "INNER JOIN customer AS c ON i.customer_id = c.customer_id " 
                + "WHERE i.invoice_id > %(i_invoice_id)s AND c.customer_id > %(c_customer_id)s" 
            )
            assert sql_operation.placeholders == {
                "i_invoice_id": 24,
                "c_customer_id": 5,
            }
        except ApplicationException as e:
            assert (
                e.message
                == "Invalid query parameter, property not found. schema object: invoice, property: track_id"  # noqa E501
            )

    def test_search_value_assignment_type_relations(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        schema_object = get_schema_object("invoice")
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"invoice_id": 24, "line_items.price": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        total_property = schema_object.properties["total"]
        (sql, placeholders) = sql_handler.search_value_assignment(total_property, "1234", "i")
        print(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.total = %(i_total)s"
        assert isinstance(placeholders["i_total"], float)

        # test greater than
        (sql, placeholders) = sql_handler.search_value_assignment(
            total_property, "gt::1234", "i"
        )
        print(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.total > %(i_total)s"
        assert isinstance(placeholders["i_total"], float)

        # test between
        (sql, placeholders) = sql_handler.search_value_assignment(
            total_property, "between::1200,1300", "i"
        )
        print(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.total BETWEEN %(i_total_1)s AND %(i_total_2)s"
        assert isinstance(placeholders["i_total_1"], float)
        assert len(placeholders) == 2
        assert placeholders["i_total_1"] == 1200.0
        assert placeholders["i_total_2"] == 1300.0

        # test in
        (sql, placeholders) = sql_handler.search_value_assignment(
            total_property, "in::1200,1250,1300", "i"
        )
        print(f"sql: {sql}, properties: {placeholders}")
        assert (
            sql
            == "i.total IN (%(i_total_0)s, %(i_total_1)s, %(i_total_2)s)"  # noqa E501
        )
        assert isinstance(placeholders["i_total_1"], float)
        assert len(placeholders) == 3
        assert placeholders["i_total_0"] == 1200.0
        assert placeholders["i_total_1"] == 1250.0
        assert placeholders["i_total_2"] == 1300.0

    def test_search_value_assignment_column_rename(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        schema_object = get_schema_object("invoice")
        invoice_date_property = schema_object.properties["invoice_date"]
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"invoice_id": 24, "line_items.price": "gt::5"},
            ),
            schema_object,
            "postgres",
        )

        invoice_date_property.api_type = "date"
        invoice_date_property.column_name = "created_date"
        invoice_date_property.column_type = "date"

        (sql, placeholders) = sql_handler.search_value_assignment(
            invoice_date_property, "gt::2000-12-12", "i"
        )
        log.info(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.created_date > %(i_invoice_date)s"
        assert isinstance(placeholders["i_invoice_date"], date)
        assert placeholders["i_invoice_date"] == date(2000, 12, 12)

    def test_search_value_assignment_datetime(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        schema_object = get_schema_object("invoice")
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"last_updated": date},
            ),
            schema_object,
            "postgres",
        )

        (sql, placeholders) = sql_handler.search_value_assignment(
            schema_object.properties["last_updated"], "gt::2000-12-12T12:34:56Z", "i"  # type: ignore # noqa E501
        )
        log.info(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.last_updated > %(i_last_updated)s"
        assert isinstance(placeholders["i_last_updated"], datetime)
        assert placeholders["i_last_updated"] == datetime(
            2000, 12, 12, 12, 34, 56, tzinfo=timezone.utc
        )

    def test_search_value_assignment_date(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        schema_object = get_schema_object("invoice")
        invoice_date_property = schema_object.properties["invoice_date"]
        invoice_date_property.api_type = "date"
        invoice_date_property.column_type = "date"

        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"last-updated": date},
            ),
            schema_object,
            "postgres",
        )

        (sql, placeholders) = sql_handler.search_value_assignment(
            schema_object.properties["invoice_date"], "gt::2000-12-12", "i"  # type: ignore # noqa E501
        )
        log.info(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.invoice_date > %(i_invoice_date)s"
        assert isinstance(placeholders["i_invoice_date"], date)
        assert placeholders["i_invoice_date"] == date(2000, 12, 12)

    @pytest.mark.skip
    def test_search_value_assignment_bool_to_int(self):
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"invoice_id": 24, "line_items.price": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        property = SchemaObjectProperty(
            operation_id="invoice",
            name="is_active",
            properties={"type": "boolean", "x-af-column-type": "integer"},
        )

        (sql, placeholders) = sql_handler.search_value_assignment(property, "true", "i")
        log.info(f"sql: {sql}, properties: {placeholders}")
        assert sql == "i.is_active = %(i_is_active)s"
        assert isinstance(placeholders["i_last_updated"], date)
        assert placeholders["i_last_updated"] == date(2000, 12, 12)

    def test_select_invalid_column(self):

        try:
            sql_handler = SQLSelectSchemaQueryHandler(
                Operation(
                    path="invoice", action="read", query_params={"not_a_property": "FL"}
                ),
                invoice_with_datetime_version_stamp(),
                "postgres",
            )
            log.info(f"sql: {sql_handler.sql}")
            assert False
        except ApplicationException as e:
            assert e.status_code == 500

    def test_select_single_joined_table(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"billing_state": "FL"},
                metadata_params={"properties": ".* customer:.* invoice_line_items:.*"},
            ),
            get_schema_object("invoice"),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total, c.address, c.city, c.company, c.country, c.customer_id, c.email, c.fax, c.first_name, c.last_name, c.phone, c.postal_code, c.state, c.support_rep_id, c.version_stamp "
            + "FROM invoice AS i " 
            + "INNER JOIN customer AS c ON i.customer_id = c.customer_id " 
            + "WHERE i.billing_state = %(i_billing_state)s"
        )
        assert sql_handler.placeholders == {"i_billing_state": "FL"}

    def test_select_schema_handling_table(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                path="invoice",
                action="read",
                query_params={"billing_state": "FL"},
                metadata_params={"properties": ".* customer:.* invoice_line_items:.*"},
            ),
            get_schema_object("invoice"),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total, c.address, c.city, c.company, c.country, c.customer_id, c.email, c.fax, c.first_name, c.last_name, c.phone, c.postal_code, c.state, c.support_rep_id, c.version_stamp "
            + "FROM invoice AS i " 
            + "INNER JOIN customer AS c ON i.customer_id = c.customer_id WHERE i.billing_state = %(i_billing_state)s"  # noqa E501
        )
        assert sql_handler.placeholders == {"i_billing_state": "FL"}

    def test_select_simple_table(self):
        try:
            sql_handler = SQLSelectSchemaQueryHandler(
                Operation(path="genre", action="read", query_params={"name": "Bill"}),
                genre_schema_with_timestamp(),
                "postgres",
            )
            log.info(
                f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"
            )

            assert (
                sql_handler.sql
                == "SELECT g.genre_id, g.name, g.last_updated FROM genre AS g WHERE g.name = %(g_name)s"
            )
            assert sql_handler.placeholders == {"g_name": "Bill"}
        except ApplicationException as e:
            assert False, e.message

    def test_select_condition_with_count(self):
        try:
            sql_handler = SQLSelectSchemaQueryHandler(
                Operation(
                    path="genre",
                    action="read",
                    query_params={"genre_id": "gt::10"},
                    metadata_params={"count": True},
                ),
                genre_schema_with_timestamp(),
                "postgres",
            )
            log.info(
                f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"
            )

            assert (
                sql_handler.sql
                == "SELECT count(*) FROM genre AS g WHERE g.genre_id > %(g_genre_id)s"
            )
            assert sql_handler.placeholders == {"g_genre_id": 10}
        except ApplicationException as e:
            assert False, e.message

    def test_select_single_table_no_conditions(self):
        try:
            sql_handler = SQLSelectSchemaQueryHandler(
                Operation(path="genre", action="read"),
                genre_schema_with_timestamp(),
                "postgres",
            )
            log.info(
                f"sql-x: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"  # noqa E501
            )

            assert sql_handler.sql == "SELECT g.genre_id, g.name, g.last_updated FROM genre AS g"
            assert sql_handler.placeholders == {}

        except ApplicationException as e:
            assert False, e.message

    def test_delete(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        sql_handler = SQLDeleteSchemaQueryHandler(
            Operation(
                path="playlist_track",
                action="delete",
                query_params={
                    "playlist_id": "2",
                },
                metadata_params={"_properties": "track_id"},
            ),
            get_schema_object("playlist_track"),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "DELETE FROM playlist_track WHERE playlist_id = %(playlist_id)s RETURNING track_id"  # noqa E501
        )
        assert sql_handler.placeholders == {"playlist_id": 2}

    def test_relation_search_condition(self):
        load_api(os.path.join(os.getcwd(), "resources/api_spec.yaml"))
        operation = Operation(
            path="invoice",
            action="read",
            query_params={"billing_state": "FL"},
            metadata_params={"properties": ".* customer:.* invoice_line_items:.*"},
        )
        schema_object = get_schema_object("invoice")
        sql_handler = SQLSelectSchemaQueryHandler(operation, schema_object, "postgres")

        log.info(f"sql_handler: {sql_handler.sql}")
        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, i.billing_state, " 
            + "i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total, " 
            + "c.address, c.city, c.company, c.country, c.customer_id, c.email, c.fax, c.first_name, c.last_name, " 
            + "c.phone, c.postal_code, c.state, c.support_rep_id, c.version_stamp " 
            + "FROM invoice AS i " 
            + "INNER JOIN customer AS c ON i.customer_id = c.customer_id " 
            + "WHERE i.billing_state = %(i_billing_state)s"
        )

        subselect_sql_generator = SQLSubselectSchemaQueryHandler(
            operation,
            schema_object.relations["invoice_line_items"],
            SQLSelectSchemaQueryHandler(operation, schema_object, "postgres"),
        )

        log.info(f"subselect_sql_generator: {subselect_sql_generator.sql}")
        assert (
            subselect_sql_generator.sql
            == "SELECT invoice_id, invoice_line_id, quantity, track_id, unit_price " 
            + "FROM invoice_line " 
            + "WHERE invoice_id IN ( SELECT invoice_id FROM invoice AS i WHERE i.billing_state = %(i_billing_state)s )"
        )

        select_map = subselect_sql_generator.selection_result_map()
        log.info(f"select_map: {select_map}")

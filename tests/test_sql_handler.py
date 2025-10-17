import pytest

from datetime import date, datetime, timezone
import os

from api_foundry_query_engine.utils.api_model import get_schema_object
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
from api_foundry_query_engine.utils.api_model import SchemaObjectProperty
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.logger import logger
import copy
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
            Operation(entity="invoice", action="read"),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )
        log.info(f"prefix_map: {sql_handler.prefix_map}")
        result_map = sql_handler.selection_results
        log.info(f"result_map: {result_map}")
        assert len(result_map) == 10
        assert result_map.get("i.invoice_id") is not None

    def test_field_selection_with_association(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="read",
                metadata_params={"properties": ".* customer:.*"},
            ),
            schema_object,
            "postgres",
        )

        result_map = sql_handler.selection_results
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
                entity="invoice",
                action="read",
                query_params={"invoice_id": "24", "total": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, "
            + "i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total "
            + "FROM invoice AS i "
            + "WHERE i.invoice_id = %(i_invoice_id)s AND i.total > %(i_total)s"  # noqa E501
        )
        assert sql_handler.placeholders == {"i_invoice_id": 24, "i_total": 5.0}

    @pytest.mark.skip
    def test_search_on_m_property(self):
        try:
            operation_dao = OperationDAO(
                Operation(
                    entity="invoice",
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
                    entity="invoice",
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
                    entity="invoice",
                    action="read",
                    query_params={
                        "invoice_id": "gt::24",
                        "customer.customer_id": "gt::5",
                    },
                ),
                "postgres",
            )

            sql_operation = operation_dao.query_handler
            log.info("sql_handler: %s", sql_operation)

            log.info(
                "sql: %s, placeholders: %s",
                sql_operation.sql,
                sql_operation.placeholders,
            )
            assert (
                sql_operation.sql
                == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, "
                + "i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total "
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

    def test_search_value_assignment_type_relations(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="read",
                query_params={"invoice_id": 24, "line_items.price": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        total_property = schema_object.properties["total"]
        (sql, placeholders) = sql_handler.search_value_assignment(
            total_property, "1234", "i"
        )
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

    def test_search_value_assignment_column_rename(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        invoice_date_property = schema_object.properties["invoice_date"]
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
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

    def test_search_value_assignment_datetime(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
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

    def test_search_value_assignment_date(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        invoice_date_property = schema_object.properties["invoice_date"]
        invoice_date_property.api_type = "date"
        invoice_date_property.column_type = "date"

        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
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
                entity="invoice",
                action="read",
                query_params={"invoice_id": 24, "line_items.price": "gt::5"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        property = SchemaObjectProperty(
            data={"type": "boolean", "x-af-column-type": "integer"}
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
                    entity="invoice",
                    action="read",
                    query_params={"not_a_property": "FL"},
                ),
                invoice_with_datetime_version_stamp(),
                "postgres",
            )
            log.info(f"sql: {sql_handler.sql}")
            assert False
        except ApplicationException as e:
            assert e.status_code == 500

    def test_select_single_joined_table(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="read",
                query_params={"billing_state": "FL"},
                metadata_params={"properties": ".* customer:.* invoice_line_items:.*"},
            ),
            schema_object,
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, "
            + "i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total, "
            + "c.address, c.city, c.company, c.country, c.customer_id, c.email, c.fax, c.first_name, "
            + "c.last_name, c.phone, c.postal_code, c.state, c.support_rep_id, c.version_stamp "
            + "FROM invoice AS i "
            + "INNER JOIN customer AS c ON i.customer_id = c.customer_id "
            + "WHERE i.billing_state = %(i_billing_state)s"
        )
        assert sql_handler.placeholders == {"i_billing_state": "FL"}

    def test_select_schema_handling_table(self, chinook_env):
        schema_object = get_schema_object("invoice")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        sql_handler = SQLSelectSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="read",
                query_params={"billing_state": "FL"},
                metadata_params={"properties": ".* customer:.* invoice_line_items:.*"},
            ),
            schema_object,
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert sql_handler.sql == (
            "SELECT i.billing_address, i.billing_city, i.billing_country, i.billing_postal_code, "
            + "i.billing_state, i.customer_id, i.invoice_date, i.invoice_id, i.last_updated, i.total, "
            + "c.address, c.city, c.company, c.country, c.customer_id, c.email, c.fax, c.first_name, "
            + "c.last_name, c.phone, c.postal_code, c.state, c.support_rep_id, c.version_stamp "
            + "FROM invoice AS i "
            + "INNER JOIN customer AS c ON i.customer_id = c.customer_id "
            + "WHERE i.billing_state = %(i_billing_state)s"
        )
        assert sql_handler.placeholders == {"i_billing_state": "FL"}

    def test_select_simple_table(self):
        try:
            sql_handler = SQLSelectSchemaQueryHandler(
                Operation(entity="genre", action="read", query_params={"name": "Bill"}),
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
                    entity="genre",
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
                Operation(entity="genre", action="read"),
                genre_schema_with_timestamp(),
                "postgres",
            )
            log.info(
                f"sql-x: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"  # noqa E501
            )

            assert (
                sql_handler.sql
                == "SELECT g.genre_id, g.name, g.last_updated FROM genre AS g"
            )
            assert sql_handler.placeholders == {}

        except ApplicationException as e:
            assert False, e.message

    def test_delete(self, chinook_env):
        schema_object = get_schema_object("playlist_track")
        assert schema_object is not None
        schema_object = copy.deepcopy(schema_object)
        sql_handler = SQLDeleteSchemaQueryHandler(
            Operation(
                entity="playlist_track",
                action="delete",
                query_params={
                    "playlist_id": "2",
                },
                metadata_params={"_properties": "track_id"},
            ),
            schema_object,
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
            entity="invoice",
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

        select_map = subselect_sql_generator.selection_results
        log.info(f"select_map: {select_map}")


@pytest.mark.unit
class TestTypeConversions:
    """Tests covering conversion between api_types and column_types."""

    def test_convert_to_db_value_string_types(self):
        """Test string type conversions from API to database."""
        # Basic string conversion
        property_data = {
            "api_name": "test_field",
            "column_name": "test_field",
            "api_type": "string",
            "column_type": "string",
        }
        prop = SchemaObjectProperty(property_data)

        # Test normal string
        result = prop.convert_to_db_value("test_value")
        assert result == "test_value"

        # Test None value
        result = prop.convert_to_db_value(None)  # type: ignore
        assert result is None

        # Test empty string
        result = prop.convert_to_db_value("")
        assert result == ""

    def test_convert_to_db_value_numeric_types(self):
        """Test numeric type conversions from API to database."""
        # Integer conversion
        int_property = SchemaObjectProperty(
            {
                "api_name": "test_int",
                "column_name": "test_int",
                "api_type": "integer",
                "column_type": "integer",
            }
        )

        result = int_property.convert_to_db_value("42")
        assert result == 42
        assert isinstance(result, int)

        result = int_property.convert_to_db_value("0")
        assert result == 0

        result = int_property.convert_to_db_value("-123")
        assert result == -123

        # Number/float conversion
        num_property = SchemaObjectProperty(
            {
                "api_name": "test_number",
                "column_name": "test_number",
                "api_type": "number",
                "column_type": "number",
            }
        )

        result = num_property.convert_to_db_value("42.5")
        assert result == 42.5
        assert isinstance(result, float)

        result = num_property.convert_to_db_value("0.0")
        assert result == 0.0

        # Float type specifically
        float_property = SchemaObjectProperty(
            {
                "api_name": "test_float",
                "column_name": "test_float",
                "api_type": "float",
                "column_type": "float",
            }
        )

        result = float_property.convert_to_db_value("3.14159")
        assert result == 3.14159
        assert isinstance(result, float)

    def test_convert_to_db_value_boolean_types(self):
        """Test boolean type conversions from API to database."""
        bool_property = SchemaObjectProperty(
            {
                "api_name": "test_bool",
                "column_name": "test_bool",
                "api_type": "boolean",
                "column_type": "boolean",
            }
        )

        # Test true values
        result = bool_property.convert_to_db_value("true")
        assert result is True

        result = bool_property.convert_to_db_value("True")
        assert result is True

        result = bool_property.convert_to_db_value("TRUE")
        assert result is True

        # Test false values
        result = bool_property.convert_to_db_value("false")
        assert result is False

        result = bool_property.convert_to_db_value("False")
        assert result is False

        result = bool_property.convert_to_db_value("FALSE")
        assert result is False

        result = bool_property.convert_to_db_value("anything_else")
        assert result is False

    def test_convert_to_db_value_boolean_to_integer(self):
        """Test boolean API type mapping to integer column type."""
        bool_to_int_property = SchemaObjectProperty(
            {
                "api_name": "is_active",
                "column_name": "is_active",
                "api_type": "boolean",
                "column_type": "integer",
            }
        )

        # Test true values should convert to 1
        result = bool_to_int_property.convert_to_db_value("true")
        assert result == 1
        assert isinstance(result, int)

        result = bool_to_int_property.convert_to_db_value("True")
        assert result == 1

        # Test false values should convert to 0
        result = bool_to_int_property.convert_to_db_value("false")
        assert result == 0
        assert isinstance(result, int)

        result = bool_to_int_property.convert_to_db_value("anything_else")
        assert result == 0

    def test_convert_to_db_value_uuid_types(self):
        """Test UUID type conversions from API to database."""
        uuid_property = SchemaObjectProperty(
            {
                "api_name": "test_uuid",
                "column_name": "test_uuid",
                "api_type": "uuid",
                "column_type": "uuid",
            }
        )

        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = uuid_property.convert_to_db_value(test_uuid)
        assert result == test_uuid
        assert isinstance(result, str)

    def test_convert_to_db_value_flexible_numeric_mappings(self):
        """Test that numeric types can map to various column types."""
        test_cases = [
            # Number API type can map to various numeric column types
            {
                "api_type": "number",
                "column_type": "float",
                "value": "3.14",
                "expected": 3.14,
            },
            {
                "api_type": "number",
                "column_type": "double",
                "value": "2.718",
                "expected": 2.718,
            },
            {
                "api_type": "number",
                "column_type": "numeric",
                "value": "123.456",
                "expected": 123.456,
            },
            {
                "api_type": "number",
                "column_type": "decimal",
                "value": "99.99",
                "expected": 99.99,
            },
            {
                "api_type": "number",
                "column_type": "real",
                "value": "1.23",
                "expected": 1.23,
            },
            # Integer API type can map to various integer column types
            {
                "api_type": "integer",
                "column_type": "int",
                "value": "42",
                "expected": 42,
            },
            {
                "api_type": "integer",
                "column_type": "bigint",
                "value": "9223372036854775807",
                "expected": 9223372036854775807,
            },
            {
                "api_type": "integer",
                "column_type": "smallint",
                "value": "32767",
                "expected": 32767,
            },
            {
                "api_type": "integer",
                "column_type": "serial",
                "value": "1",
                "expected": 1,
            },
            {
                "api_type": "integer",
                "column_type": "bigserial",
                "value": "123",
                "expected": 123,
            },
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_field",
                "column_name": "test_field",
                "api_type": case["api_type"],
                "column_type": case["column_type"],
            }
            prop = SchemaObjectProperty(property_data)
            result = prop.convert_to_db_value(case["value"])
            assert (
                result == case["expected"]
            ), f"Failed for {case['api_type']} -> {case['column_type']}: expected {case['expected']}, got {result}"

    def test_convert_to_db_value_flexible_datetime_mappings(self):
        """Test that datetime types can map to various column types."""
        test_cases = [
            {"column_type": "datetime", "value": "2023-12-25T10:30:45"},
            {"column_type": "timestamp", "value": "2023-12-25T10:30:45"},
            {"column_type": "timestamptz", "value": "2023-12-25T10:30:45+00:00"},
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_datetime",
                "column_name": "test_datetime",
                "api_type": "date-time",
                "column_type": case["column_type"],
            }
            prop = SchemaObjectProperty(property_data)
            result = prop.convert_to_db_value(case["value"])
            assert isinstance(
                result, datetime
            ), f"Failed for column_type {case['column_type']}: expected datetime, got {type(result)}"

    def test_convert_to_db_value_flexible_string_mappings(self):
        """Test that string types can map to various column types."""
        test_cases = [
            {"column_type": "varchar", "value": "test string"},
            {"column_type": "char", "value": "test"},
            {"column_type": "text", "value": "long text content"},
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_string",
                "column_name": "test_string",
                "api_type": "string",
                "column_type": case["column_type"],
            }
            prop = SchemaObjectProperty(property_data)
            result = prop.convert_to_db_value(case["value"])
            assert (
                result == case["value"]
            ), f"Failed for column_type {case['column_type']}: expected {case['value']}, got {result}"

    def test_convert_to_db_value_date_types(self):
        """Test date and datetime type conversions from API to database."""
        # Date conversion
        date_property = SchemaObjectProperty(
            {
                "api_name": "test_date",
                "column_name": "test_date",
                "api_type": "date",
                "column_type": "date",
            }
        )

        result = date_property.convert_to_db_value("2023-12-25")
        assert result == date(2023, 12, 25)
        assert isinstance(result, date)

        # Test edge case dates
        result = date_property.convert_to_db_value("2000-01-01")
        assert result == date(2000, 1, 1)

        # DateTime conversion
        datetime_property = SchemaObjectProperty(
            {
                "api_name": "test_datetime",
                "column_name": "test_datetime",
                "api_type": "date-time",
                "column_type": "date-time",
            }
        )

        result = datetime_property.convert_to_db_value("2023-12-25T10:30:45")
        assert result == datetime(2023, 12, 25, 10, 30, 45)
        assert isinstance(result, datetime)

        # Test with timezone
        result = datetime_property.convert_to_db_value("2023-12-25T10:30:45+00:00")
        expected = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        assert result == expected

        # Time conversion
        time_property = SchemaObjectProperty(
            {
                "api_name": "test_time",
                "column_name": "test_time",
                "api_type": "time",
                "column_type": "time",
            }
        )

        from datetime import time

        result = time_property.convert_to_db_value("14:30:45")
        assert result == time(14, 30, 45)
        assert isinstance(result, time)

    def test_convert_to_db_value_null_handling(self):
        """Test that None values are handled correctly for all types."""
        test_cases = [
            {"column_type": "string"},
            {"column_type": "integer"},
            {"column_type": "number"},
            {"column_type": "float"},
            {"column_type": "boolean"},
            {"column_type": "date"},
            {"column_type": "date-time"},
            {"column_type": "time"},
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_field",
                "column_name": "test_field",
                **case,
            }
            prop = SchemaObjectProperty(property_data)
            result = prop.convert_to_db_value(None)  # type: ignore
            assert result is None, f"Failed for column_type: {case['column_type']}"

    def test_convert_to_api_value_string_types(self):
        """Test string type conversions from database to API."""
        property_data = {
            "api_name": "test_field",
            "column_name": "test_field",
            "api_type": "string",
            "column_type": "string",
        }
        prop = SchemaObjectProperty(property_data)

        result = prop.convert_to_api_value("test_value")
        assert result == "test_value"

        result = prop.convert_to_api_value(None)
        assert result is None

    def test_convert_to_api_value_numeric_types(self):
        """Test numeric type conversions from database to API."""
        # Integer conversion
        int_property = SchemaObjectProperty(
            {
                "api_name": "test_int",
                "column_name": "test_int",
                "api_type": "integer",
                "column_type": "integer",
            }
        )

        result = int_property.convert_to_api_value(42)
        assert result == 42
        assert isinstance(result, int)

        # Number conversion
        num_property = SchemaObjectProperty(
            {
                "api_name": "test_number",
                "column_name": "test_number",
                "api_type": "number",
                "column_type": "number",
            }
        )

        result = num_property.convert_to_api_value(42.5)
        assert result == 42.5
        assert isinstance(result, float)

        # Float conversion
        float_property = SchemaObjectProperty(
            {
                "api_name": "test_float",
                "column_name": "test_float",
                "api_type": "float",
                "column_type": "float",
            }
        )

        result = float_property.convert_to_api_value(3.14159)
        assert result == 3.14159
        assert isinstance(result, float)

    def test_convert_to_api_value_boolean_types(self):
        """Test boolean type conversions from database to API."""
        bool_property = SchemaObjectProperty(
            {
                "api_name": "test_bool",
                "column_name": "test_bool",
                "api_type": "boolean",
                "column_type": "boolean",
            }
        )

        # Boolean values should be converted to string representation
        result = bool_property.convert_to_api_value(True)
        assert result == "True"
        assert isinstance(result, str)

        result = bool_property.convert_to_api_value(False)
        assert result == "False"
        assert isinstance(result, str)

    def test_convert_to_api_value_boolean_from_integer(self):
        """Test boolean API type handling integer database values."""
        bool_property = SchemaObjectProperty(
            {
                "api_name": "is_active",
                "column_name": "is_active",
                "api_type": "boolean",
                "column_type": "integer",
            }
        )

        # Integer 1 should convert to "true"
        result = bool_property.convert_to_api_value(1)
        assert result == "true"
        assert isinstance(result, str)

        # Integer 0 should convert to "false"
        result = bool_property.convert_to_api_value(0)
        assert result == "false"
        assert isinstance(result, str)

        # Any non-zero integer should convert to "true"
        result = bool_property.convert_to_api_value(42)
        assert result == "true"

        result = bool_property.convert_to_api_value(-1)
        assert result == "true"

    def test_convert_to_api_value_uuid_types(self):
        """Test UUID type conversions from database to API."""
        uuid_property = SchemaObjectProperty(
            {
                "api_name": "test_uuid",
                "column_name": "test_uuid",
                "api_type": "uuid",
                "column_type": "uuid",
            }
        )

        test_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = uuid_property.convert_to_api_value(test_uuid)
        assert result == test_uuid
        assert isinstance(result, str)

    def test_convert_to_api_value_date_types(self):
        """Test date and datetime type conversions from database to API."""
        # Date conversion
        date_property = SchemaObjectProperty(
            {
                "api_name": "test_date",
                "column_name": "test_date",
                "api_type": "date",
                "column_type": "date",
            }
        )

        test_date = date(2023, 12, 25)
        result = date_property.convert_to_api_value(test_date)
        assert result == "2023-12-25"
        assert isinstance(result, str)

        # DateTime conversion
        datetime_property = SchemaObjectProperty(
            {
                "api_name": "test_datetime",
                "column_name": "test_datetime",
                "api_type": "date-time",
                "column_type": "date-time",
            }
        )

        test_datetime = datetime(2023, 12, 25, 10, 30, 45)
        result = datetime_property.convert_to_api_value(test_datetime)
        assert result == "2023-12-25T10:30:45"
        assert isinstance(result, str)

        # DateTime with timezone
        test_datetime_tz = datetime(2023, 12, 25, 10, 30, 45, tzinfo=timezone.utc)
        result = datetime_property.convert_to_api_value(test_datetime_tz)
        assert result == "2023-12-25T10:30:45+00:00"

        # Time conversion
        time_property = SchemaObjectProperty(
            {
                "api_name": "test_time",
                "column_name": "test_time",
                "api_type": "time",
                "column_type": "time",
            }
        )

        from datetime import time

        test_time = time(14, 30, 45)
        result = time_property.convert_to_api_value(test_time)
        assert result == "14:30:45"
        assert isinstance(result, str)

    def test_convert_to_api_value_null_handling(self):
        """Test that None values are handled correctly for all API types."""
        test_cases = [
            {"api_type": "string"},
            {"api_type": "integer"},
            {"api_type": "number"},
            {"api_type": "float"},
            {"api_type": "boolean"},
            {"api_type": "date"},
            {"api_type": "date-time"},
            {"api_type": "time"},
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_field",
                "column_name": "test_field",
                **case,
            }
            prop = SchemaObjectProperty(property_data)
            result = prop.convert_to_api_value(None)  # type: ignore
            assert result is None, f"Failed for api_type: {case['api_type']}"

    def test_convert_to_db_value_missing_column_type(self):
        """Test conversion when column_type is not specified (defaults to string)."""
        property_data = {
            "api_name": "test_field",
            "column_name": "test_field",
            "api_type": "string"
            # column_type is intentionally missing
        }
        prop = SchemaObjectProperty(property_data)

        result = prop.convert_to_db_value("test_value")
        assert result == "test_value"

    def test_convert_to_api_value_missing_api_type(self):
        """Test conversion when api_type is not specified (defaults to string)."""
        property_data = {
            "api_name": "test_field",
            "column_name": "test_field",
            "column_type": "string"
            # api_type is intentionally missing
        }
        prop = SchemaObjectProperty(property_data)

        result = prop.convert_to_api_value("test_value")
        assert result == "test_value"

    def test_round_trip_conversions(self):
        """Test that values can be converted from API to DB and back to API."""
        test_cases = [
            {
                "api_type": "string",
                "column_type": "string",
                "test_value": "hello world",
                "expected_db": "hello world",
                "expected_api": "hello world",
            },
            {
                "api_type": "integer",
                "column_type": "integer",
                "test_value": "42",
                "expected_db": 42,
                "expected_api": 42,
            },
            {
                "api_type": "number",
                "column_type": "number",
                "test_value": "3.14",
                "expected_db": 3.14,
                "expected_api": 3.14,
            },
            {
                "api_type": "boolean",
                "column_type": "boolean",
                "test_value": "true",
                "expected_db": True,
                "expected_api": "True",
            },
            {
                "api_type": "boolean",
                "column_type": "integer",
                "test_value": "true",
                "expected_db": 1,
                "expected_api": "true",
            },
            {
                "api_type": "date",
                "column_type": "date",
                "test_value": "2023-12-25",
                "expected_db": date(2023, 12, 25),
                "expected_api": "2023-12-25",
            },
            {
                "api_type": "uuid",
                "column_type": "uuid",
                "test_value": "550e8400-e29b-41d4-a716-446655440000",
                "expected_db": "550e8400-e29b-41d4-a716-446655440000",
                "expected_api": "550e8400-e29b-41d4-a716-446655440000",
            },
        ]

        for case in test_cases:
            property_data = {
                "api_name": "test_field",
                "column_name": "test_field",
                "api_type": case["api_type"],
                "column_type": case["column_type"],
            }
            prop = SchemaObjectProperty(property_data)

            # Convert API to DB
            db_value = prop.convert_to_db_value(case["test_value"])
            assert db_value == case["expected_db"], (
                f"API->DB conversion failed for {case['api_type']}: "
                f"expected {case['expected_db']}, got {db_value}"
            )

            # Convert DB to API
            api_value = prop.convert_to_api_value(db_value)
            assert api_value == case["expected_api"], (
                f"DB->API conversion failed for {case['api_type']}: "
                f"expected {case['expected_api']}, got {api_value}"
            )

    def test_edge_case_date_formats(self):
        """Test edge cases for date format handling."""
        datetime_property = SchemaObjectProperty(
            {
                "api_name": "test_datetime",
                "column_name": "test_datetime",
                "api_type": "date-time",
                "column_type": "date-time",
            }
        )

        # Test various ISO format variations
        test_cases = [
            "2023-12-25T10:30:45",
            "2023-12-25T10:30:45.123",
            "2023-12-25T10:30:45.123456",
            "2023-12-25T10:30:45+05:30",
            "2023-12-25T10:30:45-08:00",
            "2023-12-25T10:30:45Z",
        ]

        for test_case in test_cases:
            try:
                result = datetime_property.convert_to_db_value(test_case)
                assert isinstance(
                    result, datetime
                ), f"Failed to parse datetime: {test_case}"
            except ValueError as e:
                pytest.fail(
                    f"Failed to parse valid datetime format " f"'{test_case}': {e}"
                )

    def test_api_to_db_type_mismatch_scenarios(self):
        """Test scenarios where API type and column type differ."""
        # API expects string but DB stores as integer
        property_data = {
            "api_name": "test_field",
            "column_name": "test_field",
            "api_type": "string",
            "column_type": "integer",
        }
        prop = SchemaObjectProperty(property_data)

        # The conversion should use column_type for DB conversion
        result = prop.convert_to_db_value("123")
        assert result == 123
        assert isinstance(result, int)

        # And api_type for API conversion
        result = prop.convert_to_api_value(123)
        assert result == "123"  # String conversion due to api_type
        assert isinstance(result, str)

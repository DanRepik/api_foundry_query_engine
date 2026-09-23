import pytest

from api_foundry_query_engine.dao.sql_query_handler import SQLQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.api_model import SchemaObjectProperty


def _handler(engine: str) -> SQLQueryHandler:
    return SQLQueryHandler(Operation(entity="widget", action="read"), engine)


def _property(api_name: str, column_type: str = None, api_type: str = None) -> SchemaObjectProperty:
    return SchemaObjectProperty({"api_name": api_name, "column_type": column_type, "api_type": api_type})


@pytest.mark.unit
class TestDataApiPlaceholders:
    def test_postgres_engine_unaffected(self):
        handler = _handler("postgres")
        prop = _property("id", column_type="uuid")
        assert handler.placeholder(prop) == "%(id)s"

    def test_oracle_engine_unaffected(self):
        handler = _handler("oracle")
        prop = _property("created_at", column_type="date")
        assert handler.placeholder(prop) == "TO_DATE(:created_at, 'YYYY-MM-DD')"

    @pytest.mark.parametrize(
        "column_type,expected_cast",
        [
            ("uuid", "uuid"),
            ("date", "date"),
            ("time", "time"),
            ("timetz", "timetz"),
            ("date-time", "timestamptz"),
            ("datetime", "timestamptz"),
            ("timestamp", "timestamptz"),
            ("timestamptz", "timestamptz"),
        ],
    )
    def test_data_api_casts_typed_columns(self, column_type, expected_cast):
        handler = _handler("postgres:data-api")
        prop = _property("occurred_at", column_type=column_type)
        assert handler.placeholder(prop) == f":occurred_at::{expected_cast}"

    def test_data_api_leaves_plain_string_column_uncast(self):
        handler = _handler("postgres:data-api")
        prop = _property("name", column_type="string")
        assert handler.placeholder(prop) == ":name"

    def test_data_api_leaves_numeric_and_boolean_columns_uncast(self):
        handler = _handler("postgres:data-api")
        assert handler.placeholder(_property("count", column_type="integer")) == ":count"
        assert handler.placeholder(_property("active", column_type="boolean")) == ":active"
        assert handler.placeholder(_property("price", column_type="numeric")) == ":price"

    def test_data_api_casts_embedded_object_to_jsonb_regardless_of_column_type(self):
        handler = _handler("postgres:data-api")
        prop = _property("metadata", column_type="string", api_type="object")
        assert handler.placeholder(prop) == ":metadata::jsonb"

    def test_data_api_casts_embedded_array_to_jsonb(self):
        handler = _handler("postgres:data-api")
        prop = _property("tags", column_type=None, api_type="array")
        assert handler.placeholder(prop) == ":tags::jsonb"

    def test_data_api_custom_param_name_used_over_api_name(self):
        handler = _handler("postgres:data-api")
        prop = _property("id", column_type="uuid")
        assert handler.placeholder(prop, "id_0") == ":id_0::uuid"

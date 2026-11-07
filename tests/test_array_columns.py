"""Postgres array columns: a property with ``type: array`` and an
``x-af-column-type`` such as ``text[]`` is stored in a native array column.

The RDS Data API has no array parameter, so under ``postgres:data-api`` the
value travels as JSON text and the placeholder unpacks it; under psycopg2
the list is adapted to ARRAY[...] and cast to the column type.
"""

import json

import psycopg2
import pytest

from api_foundry_query_engine.connectors.data_api_connection import _encode_parameter
from api_foundry_query_engine.dao.sql_insert_query_handler import SQLInsertSchemaQueryHandler
from api_foundry_query_engine.dao.sql_update_query_handler import SQLUpdateSchemaQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.api_model import SchemaObject, SchemaObjectProperty, array_element_type
from api_foundry_query_engine.utils.app_exception import ApplicationException


def lens_schema():
    return SchemaObject(
        {
            "api_name": "lens",
            "database": "test",
            "primary_key": "lens_id",
            "table_name": "lens",
            "properties": {
                "lens_id": {
                    "api_name": "lens_id",
                    "api_type": "integer",
                    "column_name": "lens_id",
                    "column_type": "integer",
                    "key_type": "auto",
                },
                "name": {"api_name": "name", "api_type": "string", "column_name": "name", "column_type": "string"},
                "flags": {"api_name": "flags", "api_type": "array", "column_name": "flags", "column_type": "text[]"},
                "ranks": {
                    "api_name": "ranks",
                    "api_type": "array",
                    "column_name": "ranks",
                    "column_type": "integer[]",
                },
            },
            "permissions": {"default": {"read": {"admin": ".*"}, "write": {"admin": ".*"}}},
        }
    )


def insert(engine, store):
    return SQLInsertSchemaQueryHandler(
        Operation(entity="lens", action="create", store_params=store, roles=["admin"]), lens_schema(), engine
    )


@pytest.mark.unit
class TestArrayElementType:
    @pytest.mark.parametrize(
        "column_type,element",
        [
            ("text[]", "text"),
            ("integer[]", "integer"),
            ("character varying []", "character varying"),
            (" Double   Precision[] ", "double precision"),
        ],
    )
    def test_array_types(self, column_type, element):
        assert array_element_type(column_type) == element

    @pytest.mark.parametrize("column_type", [None, "text", "jsonb", "text[][]", "text[]; drop table x", "[]", "1x[]"])
    def test_not_array_types(self, column_type):
        assert array_element_type(column_type) is None


@pytest.mark.unit
class TestArrayConversion:
    prop = SchemaObjectProperty({"api_name": "flags", "api_type": "array", "column_type": "text[]"})

    def test_list_passes_through(self):
        assert self.prop.convert_to_db_value(["a", "b"]) == ["a", "b"]
        assert self.prop.convert_to_db_value([]) == []
        assert self.prop.convert_to_db_value(None) is None

    def test_json_text_is_parsed(self):
        assert self.prop.convert_to_db_value('["a", "b"]') == ["a", "b"]

    @pytest.mark.parametrize("value", ["a", '{"a": 1}', [["nested"]], [{"a": 1}], 3])
    def test_rejects_non_arrays(self, value):
        with pytest.raises(ApplicationException) as error:
            self.prop.convert_to_db_value(value)
        assert error.value.status_code == 400

    def test_api_value_is_the_list(self):
        assert self.prop.convert_to_api_value(["a"]) == ["a"]


@pytest.mark.unit
class TestArrayPlaceholders:
    def test_data_api_unpacks_json_text(self):
        handler = insert("postgres:data-api", {"name": "x", "flags": ["a", "b"], "ranks": [1, 2]})
        assert (
            "CASE WHEN :flags::jsonb IS NULL THEN NULL ELSE "
            "CAST(ARRAY(SELECT jsonb_array_elements_text(:flags::jsonb)) AS text[]) END" in handler.sql
        )
        assert "AS integer[]) END" in handler.sql
        assert handler.placeholders["flags"] == ["a", "b"]
        # The Data API connector sends a list as JSON text.
        assert _encode_parameter(handler.placeholders["flags"]) == {"stringValue": '["a", "b"]'}

    def test_psycopg2_casts_the_list(self):
        handler = insert("postgres", {"name": "x", "flags": ["a"]})
        assert "CAST(%(flags)s AS text[])" in handler.sql
        assert handler.placeholders["flags"] == ["a"]

    def test_update(self):
        handler = SQLUpdateSchemaQueryHandler(
            Operation(
                entity="lens",
                action="update",
                query_params={"lens_id": "1"},
                store_params={"flags": []},
                roles=["admin"],
            ),
            lens_schema(),
            "postgres:data-api",
        )
        assert "flags = CASE WHEN :flags::jsonb IS NULL" in handler.sql
        assert handler.placeholders["flags"] == []

    def test_bad_value_is_a_400(self):
        with pytest.raises(ApplicationException) as error:
            insert("postgres:data-api", {"name": "x", "flags": "not an array"}).sql
        assert error.value.status_code == 400


def _as_data_api(sql, values):
    """Run Data API SQL through psycopg2: :name placeholders bound as the
    Data API binds them (lists as JSON text, other values typed)."""
    import re

    params = {}

    def bind(match):
        name = match.group(1)
        value = values[name]
        if isinstance(value, (list, dict)):
            value = json.dumps(value)
        params[name] = value
        return f"CAST(%({name})s AS text)" if isinstance(value, str) else f"%({name})s"

    return re.sub(r"(?<![:\w]):(\w+)", bind, sql), params


@pytest.mark.parametrize("engine", ["postgres:data-api", "postgres"])
def test_round_trip(postgres, engine):  # noqa: F811
    conn = psycopg2.connect(postgres["dsn"])
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DROP TABLE IF EXISTS lens; "
                "CREATE TABLE lens (lens_id serial PRIMARY KEY, name text, flags text[], ranks integer[])"
            )
            for store, expected in (
                ({"name": "a", "flags": ["x", "y z"], "ranks": [3, 1]}, (["x", "y z"], [3, 1])),
                ({"name": "b", "flags": [], "ranks": None}, ([], None)),
            ):
                handler = insert(engine, store)
                if engine == "postgres:data-api":
                    cursor.execute(*_as_data_api(handler.sql, handler.placeholders))
                else:
                    cursor.execute(handler.sql, handler.placeholders)
                cursor.execute("SELECT flags, ranks FROM lens WHERE name = %s", (store["name"],))
                assert cursor.fetchone() == expected
    finally:
        conn.close()

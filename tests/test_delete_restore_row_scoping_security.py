"""
Regression test: DELETE and RESTORE must respect row-level ("where")
permission scoping the same way SELECT and UPDATE already do.

Previously, SQLDeleteSchemaQueryHandler/SQLRestoreSchemaQueryHandler only
checked whether a role had *any* delete/restore grant on the entity
(check_permission()) and never folded a permission model's row-level
`where` clause (e.g. tenant/ownership scoping) into the query. A role with
delete rights on an entity could therefore delete/restore rows outside its
intended scope.
"""

import pytest

from api_foundry_query_engine.dao.sql_delete_query_handler import (
    SQLDeleteSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_restore_query_handler import (
    SQLRestoreSchemaQueryHandler,
)
from api_foundry_query_engine.utils.api_model import SchemaObject
from api_foundry_query_engine.operation import Operation


def _make_schema_object(permissions):
    return SchemaObject(
        {
            "api_name": "document",
            "table_name": "document",
            "primary_key": "document_id",
            "properties": {
                "document_id": {
                    "api_name": "document_id",
                    "api_type": "integer",
                    "column_name": "document_id",
                    "column_type": "integer",
                },
                "tenant_id": {
                    "api_name": "tenant_id",
                    "api_type": "string",
                    "column_name": "tenant_id",
                    "column_type": "string",
                },
            },
            "permissions": permissions,
        }
    )


@pytest.mark.unit
def test_delete_scopes_rows_to_role_where_clause():
    schema_object = _make_schema_object(
        {"default": {"delete": {"manager": {"where": "tenant_id = ${claims.tenant_id}"}}}}
    )
    operation = Operation(
        entity="document",
        action="delete",
        claims={"roles": ["manager"], "tenant_id": "acme"},
    )
    handler = SQLDeleteSchemaQueryHandler(operation, schema_object, "postgres")

    assert "tenant_id = 'acme'" in handler.search_condition


@pytest.mark.unit
def test_delete_without_row_scope_configured_has_no_extra_filter():
    schema_object = _make_schema_object({"default": {"delete": {"manager": True}}})
    operation = Operation(entity="document", action="delete", claims={"roles": ["manager"]})
    handler = SQLDeleteSchemaQueryHandler(operation, schema_object, "postgres")

    assert handler.search_condition == ""


@pytest.mark.unit
def test_restore_scopes_rows_to_role_where_clause():
    schema_object = _make_schema_object(
        {"default": {"restore": {"manager": {"where": "tenant_id = ${claims.tenant_id}"}}}}
    )
    operation = Operation(
        entity="document",
        action="restore",
        claims={"roles": ["manager"], "tenant_id": "acme"},
    )
    handler = SQLRestoreSchemaQueryHandler(operation, schema_object, "postgres")

    assert "tenant_id = 'acme'" in handler.search_condition


@pytest.mark.unit
def test_restore_falls_back_to_write_row_scope():
    """Restore's own permission check falls back restore->write; the
    row-level where-scope should follow the same fallback."""
    schema_object = _make_schema_object(
        {"default": {"write": {"manager": {"where": "tenant_id = ${claims.tenant_id}"}}}}
    )
    operation = Operation(
        entity="document",
        action="restore",
        claims={"roles": ["manager"], "tenant_id": "acme"},
    )
    handler = SQLRestoreSchemaQueryHandler(operation, schema_object, "postgres")

    assert "tenant_id = 'acme'" in handler.search_condition

"""Tests for property value injection from claims and other sources."""
import pytest
from datetime import datetime
from unittest.mock import patch
import uuid

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.sql_insert_query_handler import (
    SQLInsertSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_update_query_handler import (
    SQLUpdateSchemaQueryHandler,
)
from api_foundry_query_engine.utils.api_model import SchemaObject
from api_foundry_query_engine.utils.app_exception import ApplicationException


@pytest.mark.unit
class TestValueExtraction:
    """Test extraction of injected values from various sources."""

    def test_extract_claim_value(self):
        """Test extracting value from JWT claims."""
        operation = Operation(
            entity="test",
            action="create",
            claims={"sub": "user123", "tenant": "acme"},
        )
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        # Test claim extraction
        assert handler.extract_injected_value("claim:sub") == "user123"
        assert handler.extract_injected_value("claim:tenant") == "acme"
        assert handler.extract_injected_value("claim:missing") is None

    def test_extract_timestamp(self):
        """Test extracting current timestamp."""
        operation = Operation(entity="test", action="create")
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        timestamp = handler.extract_injected_value("timestamp")
        assert timestamp is not None
        # Verify it's a valid ISO format timestamp
        datetime.fromisoformat(timestamp)

    def test_extract_date(self):
        """Test extracting current date."""
        operation = Operation(entity="test", action="create")
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        date_str = handler.extract_injected_value("date")
        assert date_str is not None
        # Verify it's a valid date format
        datetime.strptime(date_str, "%Y-%m-%d")

    def test_extract_uuid(self):
        """Test generating a UUID."""
        operation = Operation(entity="test", action="create")
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        uuid_str = handler.extract_injected_value("uuid")
        assert uuid_str is not None
        # Verify it's a valid UUID
        uuid.UUID(uuid_str)

    @patch.dict("os.environ", {"TEST_VAR": "test_value"})
    def test_extract_env_variable(self):
        """Test extracting value from environment variable."""
        operation = Operation(entity="test", action="create")
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        assert handler.extract_injected_value("env:TEST_VAR") == "test_value"
        assert handler.extract_injected_value("env:MISSING") is None

    def test_invalid_source(self):
        """Test that invalid source raises exception."""
        operation = Operation(entity="test", action="create")
        schema_object = SchemaObject(
            {
                "api_name": "test",
                "database": "test_db",
                "table_name": "test_table",
                "primary_key": "id",
                "properties": {
                    "id": {
                        "api_name": "id",
                        "column_name": "id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    }
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        with pytest.raises(ApplicationException) as exc_info:
            handler.extract_injected_value("invalid:source")

        assert exc_info.value.status_code == 400
        assert "Unknown inject value source" in exc_info.value.message


@pytest.mark.unit
class TestInsertInjection:
    """Test value injection during INSERT operations."""

    def test_inject_created_by_on_insert(self):
        """Test that created_by is injected from claims on INSERT."""
        operation = Operation(
            entity="album",
            action="create",
            store_params={"title": "Test Album"},
            claims={"sub": "user123"},
        )

        schema_object = SchemaObject(
            {
                "api_name": "album",
                "database": "chinook",
                "table_name": "album",
                "primary_key": "album_id",
                "properties": {
                    "album_id": {
                        "api_name": "album_id",
                        "column_name": "album_id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    },
                    "title": {
                        "api_name": "title",
                        "column_name": "title",
                        "api_type": "string",
                        "column_type": "string",
                    },
                    "created_by": {
                        "api_name": "created_by",
                        "column_name": "created_by",
                        "api_type": "string",
                        "column_type": "string",
                        "inject_value": "claim:sub",
                        "inject_on": ["create"],
                    },
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        sql = handler.sql
        placeholders = handler.placeholders

        # Verify created_by is in the SQL
        assert "created_by" in sql
        # Verify the injected value is in placeholders
        assert "__inject_created_by" in placeholders
        assert placeholders["__inject_created_by"] == "user123"

    def test_user_cannot_override_injected_property(self):
        """Test that user cannot manually set an injected property."""
        operation = Operation(
            entity="album",
            action="create",
            store_params={"title": "Test Album", "created_by": "hacker"},
            claims={"sub": "user123"},
        )

        schema_object = SchemaObject(
            {
                "api_name": "album",
                "database": "chinook",
                "table_name": "album",
                "primary_key": "album_id",
                "properties": {
                    "album_id": {
                        "api_name": "album_id",
                        "column_name": "album_id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    },
                    "title": {
                        "api_name": "title",
                        "column_name": "title",
                        "api_type": "string",
                        "column_type": "string",
                    },
                    "created_by": {
                        "api_name": "created_by",
                        "column_name": "created_by",
                        "api_type": "string",
                        "column_type": "string",
                        "inject_value": "claim:sub",
                        "inject_on": ["create"],
                    },
                },
            }
        )

        handler = SQLInsertSchemaQueryHandler(operation, schema_object, "postgres")

        with pytest.raises(ApplicationException) as exc_info:
            _ = handler.sql

        assert exc_info.value.status_code == 403
        assert "auto-injected" in exc_info.value.message


@pytest.mark.unit
class TestUpdateInjection:
    """Test value injection during UPDATE operations."""

    def test_inject_updated_by_on_update(self):
        """Test that updated_by is injected from claims on UPDATE."""
        operation = Operation(
            entity="album",
            action="update",
            query_params={"album_id": "1"},
            store_params={"title": "Updated Album"},
            claims={"sub": "user456"},
        )

        schema_object = SchemaObject(
            {
                "api_name": "album",
                "database": "chinook",
                "table_name": "album",
                "primary_key": "album_id",
                "properties": {
                    "album_id": {
                        "api_name": "album_id",
                        "column_name": "album_id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    },
                    "title": {
                        "api_name": "title",
                        "column_name": "title",
                        "api_type": "string",
                        "column_type": "string",
                    },
                    "updated_by": {
                        "api_name": "updated_by",
                        "column_name": "updated_by",
                        "api_type": "string",
                        "column_type": "string",
                        "inject_value": "claim:sub",
                        "inject_on": ["update"],
                    },
                },
            }
        )

        handler = SQLUpdateSchemaQueryHandler(operation, schema_object, "postgres")

        sql = handler.sql
        placeholders = handler.placeholders

        # Verify updated_by is in the SQL
        assert "updated_by" in sql
        # Verify the injected value is in placeholders
        assert "__inject_updated_by" in placeholders
        assert placeholders["__inject_updated_by"] == "user456"

    def test_created_by_not_injected_on_update(self):
        """Test that create-only fields are not injected on UPDATE."""
        operation = Operation(
            entity="album",
            action="update",
            query_params={"album_id": "1"},
            store_params={"title": "Updated Album"},
            claims={"sub": "user456"},
        )

        schema_object = SchemaObject(
            {
                "api_name": "album",
                "database": "chinook",
                "table_name": "album",
                "primary_key": "album_id",
                "properties": {
                    "album_id": {
                        "api_name": "album_id",
                        "column_name": "album_id",
                        "api_type": "integer",
                        "column_type": "integer",
                        "key_type": "auto",
                    },
                    "title": {
                        "api_name": "title",
                        "column_name": "title",
                        "api_type": "string",
                        "column_type": "string",
                    },
                    "created_by": {
                        "api_name": "created_by",
                        "column_name": "created_by",
                        "api_type": "string",
                        "column_type": "string",
                        "inject_value": "claim:sub",
                        "inject_on": ["create"],  # Only on create
                    },
                },
            }
        )

        handler = SQLUpdateSchemaQueryHandler(operation, schema_object, "postgres")

        _ = handler.sql
        placeholders = handler.placeholders

        # Verify created_by is NOT in the UPDATE statement
        assert "__inject_created_by" not in placeholders


def comment_schema():
    return SchemaObject(
        {
            "api_name": "comments",
            "database": "policy_corpus",
            "primary_key": "comment_id",
            "table_name": "comments",
            "properties": {
                "comment_id": {
                    "api_name": "comment_id",
                    "api_type": "string",
                    "column_name": "comment_id",
                    "column_type": "uuid",
                    "key_type": "auto",
                },
                "node_id": {
                    "api_name": "node_id",
                    "api_type": "string",
                    "column_name": "node_id",
                    "column_type": "uuid",
                },
                "user_id": {
                    "api_name": "user_id",
                    "api_type": "string",
                    "column_name": "user_id",
                    "column_type": "text",
                    "inject_value": "claim:sub",
                    "inject_on": ["create"],
                },
                "updated_by": {
                    "api_name": "updated_by",
                    "api_type": "string",
                    "column_name": "updated_by",
                    "column_type": "text",
                    "inject_value": "claim:sub",
                    "inject_on": ["update"],
                },
                "body": {
                    "api_name": "body",
                    "api_type": "string",
                    "column_name": "body",
                    "column_type": "text",
                },
            },
            "permissions": {
                "public": {
                    "write": "^(node_id|body)$",
                    "read": ".*",
                }
            },
        }
    )


def test_insert_injects_claim_backed_fields():
    sql_handler = SQLInsertSchemaQueryHandler(
        Operation(
            entity="comments",
            action="create",
            store_params={"node_id": "node-1", "body": "hello"},
            roles=["public"],
            claims={"sub": "public-user-id-005"},
        ),
        comment_schema(),
        "postgres",
    )

    assert (
        sql_handler.sql == "INSERT INTO comments ( node_id, body, user_id ) "
        "VALUES ( %(node_id)s, %(body)s, %(user_id)s) "
        "RETURNING comment_id, node_id, user_id, updated_by, body"
    )
    assert sql_handler.placeholders == {
        "node_id": "node-1",
        "body": "hello",
        "user_id": "public-user-id-005",
    }


def test_insert_rejects_manual_override_of_injected_fields():
    try:
        handler = SQLInsertSchemaQueryHandler(
            Operation(
                entity="comments",
                action="create",
                store_params={
                    "node_id": "node-1",
                    "body": "hello",
                    "user_id": "attacker",
                },
                roles=["public"],
                claims={"sub": "public-user-id-005"},
            ),
            comment_schema(),
            "postgres",
        )
        handler.sql
        assert False, "Expected injected property override to be rejected"
    except ApplicationException as error:
        assert error.message == "Property 'user_id' is auto-injected and cannot be set manually"


def test_update_injects_update_only_fields():
    sql_handler = SQLUpdateSchemaQueryHandler(
        Operation(
            entity="comments",
            action="update",
            query_params={"comment_id": "comment-1"},
            store_params={"body": "updated"},
            roles=["public"],
            claims={"sub": "public-user-id-005"},
        ),
        comment_schema(),
        "postgres",
    )

    assert "updated_by = %(updated_by)s" in sql_handler.sql
    assert sql_handler.placeholders["updated_by"] == "public-user-id-005"

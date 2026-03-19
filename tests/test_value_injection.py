from api_foundry_query_engine.dao.sql_insert_query_handler import (
    SQLInsertSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_update_query_handler import (
    SQLUpdateSchemaQueryHandler,
)
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject


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
        sql_handler.sql
        == "INSERT INTO comments ( node_id, body, user_id ) VALUES ( %(node_id)s, %(body)s, %(user_id)s) RETURNING comment_id, node_id, user_id, updated_by, body"
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
        assert (
            error.message
            == "Property 'user_id' is auto-injected and cannot be set manually"
        )


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

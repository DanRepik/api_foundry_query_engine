import json
import yaml
from api_foundry_query_engine.lambda_handler import QueryEngine


def test_read_album_as_sales_associate_limits_columns(chinook_env):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "GET",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-1",
                    "scope": "read:album",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "GET",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    assert len(rows) >= 1
    row = rows[0]
    # sales_associate may only read album_id and title
    assert set(row.keys()).issubset({"album_id", "title"})
    assert "album_id" in row and "title" in row
    assert "artist_id" not in row


def test_read_album_as_sales_manager_all_columns(chinook_env):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "GET",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "read:album",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "GET",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    assert len(rows) >= 1
    row = rows[0]
    # sales_manager has read: .*
    assert {"album_id", "artist_id", "title"}.issubset(set(row.keys()))


def test_read_album_as_sales_manager_out_of_scope(chinook_env):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "GET",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "read:invoice_line",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "GET",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 401
    body = json.loads(resp["body"]) or {}
    # Ensure clear insufficient scope message
    assert "insufficient_scope" in body.get("message", "")


def test_delete_album_forbidden_for_associate(chinook_env):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "DELETE",
        "resource": "/album",
        "queryStringParameters": {"album_id": "5"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "delete:album",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "DELETE",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert "Subject is not allowed to delete album" in body.get("message", "")


def test_delete_invoice_line_allowed(chinook_env):  # noqa F811
    event = {
        "path": "/invoice_line",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "DELETE",
        "resource": "/invoice_line",
        "queryStringParameters": {"invoice_line_id": "1"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "delete:invoice_line",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "DELETE",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert {
            "invoice_line_id",
            "invoice_id",
            "track_id",
            "unit_price",
        }.issubset(set(row.keys()))


def test_create_album_as_sales_manager_allowed(chinook_env):  # noqa F811
    payload = {"artist_id": 1, "title": "Authorization Test Album"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "POST",
        "resource": "/album",
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "write:album",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "POST",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    assert rows
    row = rows[0]
    assert {"album_id", "title"}.issubset(set(row.keys()))
    assert row.get("title") == "Authorization Test Album"


def test_create_album_as_sales_associate_forbidden(chinook_env):  # noqa F811
    payload = {"artist_id": 1, "title": "Associate Should Fail"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "POST",
        "resource": "/album",
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "write:album",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "POST",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert "Subject is not allowed to create with property: artist_id" in body.get(
        "message", ""
    )


def test_update_album_as_sales_manager_allowed(chinook_env):  # noqa F811
    payload = {"title": "Authorization Updated Title"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "PUT",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "write:album",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "PUT",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert {"album_id", "artist_id", "title"}.issubset(set(row.keys()))
        assert row.get("title") == "Authorization Updated Title"


def test_update_album_as_sales_associate_forbidden(chinook_env):  # noqa F811
    payload = {"title": "Associate Update Should Fail"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "PUT",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "write:album",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "PUT",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert (
        "Subject does not have permission to update properties: ['title']"
        in body.get("message", "")
    )


def test_read_album_with_action_wildcard_scope(chinook_env):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "GET",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "user-1",
                    "scope": "read:*",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "GET",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert isinstance(rows, list)
    row = rows[0]
    assert set(row.keys()).issubset({"album_id", "title"})


def test_delete_album_with_global_wildcard_scope_but_role_denied(
    chinook_env,
):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "DELETE",
        "resource": "/album",
        "queryStringParameters": {"album_id": "999999"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "*:*",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "DELETE",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert "Subject is not allowed to delete album" in body.get("message", "")


def test_delete_album_with_action_wildcard_scope_allowed_role(
    chinook_env,
):  # noqa F811
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "DELETE",
        "resource": "/album",
        "queryStringParameters": {"album_id": "999999"},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "delete:*",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "DELETE",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"]) or {}
    assert "No records were modified" in body.get("message", "")


def test_create_album_with_global_wildcard_scope_role_denied(
    chinook_env,
):  # noqa F811
    payload = {"artist_id": 1, "title": "Wildcard Associate"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "POST",
        "resource": "/album",
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "*",
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "POST",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert "Subject is not allowed to create with property: artist_id" in body.get(
        "message", ""
    )


def test_update_album_with_action_wildcard_scope_allowed_role(
    chinook_env,
):  # noqa F811
    payload = {"title": "Wildcard Manager Update"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "PUT",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "write:*",
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "PUT",
            "stage": "dev",
        },
    }

    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200


def test_custom_path_permissions_associate_filtered(chinook_env):  # noqa F811
    # Create a simple custom path operation over album with path-level permissions
    config = yaml.safe_load(chinook_env["API_SPEC"])  # type: ignore
    config.setdefault("path_operations", {})
    config["path_operations"]["perm_test_read"] = {
        "action": "read",
        "database": "chinook",
        "entity": "perm_test",
        "inputs": {},
        "outputs": {
            "album_id": {
                "api_name": "album_id",
                "api_type": "integer",
                "column_name": "album_id",
                "column_type": "integer",
                "type": "integer",
            },
            "title": {
                "api_name": "title",
                "api_type": "string",
                "column_name": "title",
                "column_type": "string",
                "type": "string",
            },
        },
        "sql": "SELECT album_id, title FROM album ORDER BY album_id LIMIT 2",
        "security": {
            "sales_associate": {"read": "album_id"},
            "sales_manager": {"read": ".*"},
        },
    }

    modified_env = dict(chinook_env)
    modified_env["API_SPEC"] = yaml.safe_dump(config)

    from api_foundry_query_engine.utils.api_model import set_api_model
    from api_foundry_query_engine.utils import api_model as api_model_module

    try:
        api_model_module.api_model = None
        set_api_model(modified_env)

        event = {
            "path": "/perm_test",
            "headers": {"Host": "localhost", "User-Agent": "pytest"},
            "httpMethod": "GET",
            "resource": "/perm_test",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "assoc-1",
                        "scope": "read:perm_test",
                        "roles": ["sales_associate"],
                    }
                },
                "httpMethod": "GET",
                "stage": "dev",
            },
        }

        engine = QueryEngine(config=modified_env)
        resp = engine.handler(event)
        assert resp["statusCode"] == 200
        rows = json.loads(resp["body"]) or []
        assert isinstance(rows, list)
        assert rows, "Expected rows from custom path operation"
        # Associates should only see album_id per injected security
        assert set(rows[0].keys()).issubset({"album_id"})
    finally:
        api_model_module.api_model = None
        set_api_model(chinook_env)


def test_custom_path_permissions_manager_all_outputs(chinook_env):  # noqa F811
    # Same custom path operation but validate manager can see all outputs
    config = yaml.safe_load(chinook_env["API_SPEC"])  # type: ignore
    config.setdefault("path_operations", {})
    config["path_operations"]["perm_test_read"] = {
        "action": "read",
        "database": "chinook",
        "entity": "perm_test",
        "inputs": {},
        "outputs": {
            "album_id": {
                "api_name": "album_id",
                "api_type": "integer",
                "column_name": "album_id",
                "column_type": "integer",
                "type": "integer",
            },
            "title": {
                "api_name": "title",
                "api_type": "string",
                "column_name": "title",
                "column_type": "string",
                "type": "string",
            },
        },
        "sql": "SELECT album_id, title FROM album ORDER BY album_id LIMIT 2",
        "security": {
            "sales_associate": {"read": "album_id"},
            "sales_manager": {"read": ".*"},
        },
    }

    modified_env = dict(chinook_env)
    modified_env["API_SPEC"] = yaml.safe_dump(config)

    from api_foundry_query_engine.utils.api_model import set_api_model
    from api_foundry_query_engine.utils import api_model as api_model_module

    try:
        api_model_module.api_model = None
        set_api_model(modified_env)

        event = {
            "path": "/perm_test",
            "headers": {"Host": "localhost", "User-Agent": "pytest"},
            "httpMethod": "GET",
            "resource": "/perm_test",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "manager-1",
                        "scope": "read:perm_test",
                        "roles": ["sales_manager"],
                    }
                },
                "httpMethod": "GET",
                "stage": "dev",
            },
        }

        engine = QueryEngine(config=modified_env)
        resp = engine.handler(event)
        assert resp["statusCode"] == 200
        rows = json.loads(resp["body"]) or []
        assert isinstance(rows, list)
        assert rows, "Expected rows from custom path operation"
        # Managers should see both outputs
        assert {"album_id", "title"}.issubset(set(rows[0].keys()))
    finally:
        api_model_module.api_model = None
        set_api_model(chinook_env)


def test_create_album_with_permissions_claim_and_scope_allowed(
    chinook_env,
):  # noqa F811
    payload = {"artist_id": 1, "title": "Perms+Scope Album"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "POST",
        "resource": "/album",
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "scope": "write:album",
                    "permissions": ["write:album"],
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "POST",
            "stage": "dev",
        },
    }
    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert rows and rows[0].get("title") == "Perms+Scope Album"


def test_create_album_with_permissions_claim_only_no_scope_currently_allowed(
    chinook_env,
):  # noqa F811
    # Note: Current behavior doesn't enforce scope if 'scope' claim is omitted.
    payload = {"artist_id": 1, "title": "Perms Only Album"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "POST",
        "resource": "/album",
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "manager-1",
                    "permissions": ["write:album"],
                    "roles": ["sales_manager"],
                }
            },
            "httpMethod": "POST",
            "stage": "dev",
        },
    }
    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    # Document current behavior: allowed when scope is missing but permissions present
    assert resp["statusCode"] == 200
    rows = json.loads(resp["body"]) or []
    assert rows and rows[0].get("title") == "Perms Only Album"


def test_update_album_with_permissions_claim_associate_still_denied(
    chinook_env,
):  # noqa F811
    payload = {"title": "Assoc Perms Should Not Override"}
    event = {
        "path": "/album",
        "headers": {"Host": "localhost", "User-Agent": "pytest"},
        "httpMethod": "PUT",
        "resource": "/album",
        "queryStringParameters": {"album_id": "1"},
        "body": json.dumps(payload),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "sub": "assoc-1",
                    "scope": "write:album",
                    "permissions": ["write:album"],
                    "roles": ["sales_associate"],
                }
            },
            "httpMethod": "PUT",
            "stage": "dev",
        },
    }
    engine = QueryEngine(config=chinook_env)
    resp = engine.handler(event)
    assert resp["statusCode"] == 402
    body = json.loads(resp["body"]) or {}
    assert (
        "Subject does not have permission to update properties: ['title']"
        in body.get("message", "")
    )

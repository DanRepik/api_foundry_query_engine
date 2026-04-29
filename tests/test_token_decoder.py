import pytest

from api_foundry_query_engine.utils import api_model as api_model_module
from api_foundry_query_engine.utils import token_decoder as token_decoder_module


def _set_api_spec(monkeypatch):
    api_model_module.api_model = None
    monkeypatch.setenv(
        "API_SPEC",
        """
path_operations:
  public_read:
    entity: public
    action: read
    sql: SELECT 1
    database: test
    inputs: {}
    outputs: {}
    security:
      default:
        read:
          public: ".*"
  private_read:
    entity: private
    action: read
    sql: SELECT 1
    database: test
    inputs: {}
    outputs: {}
    security:
      default:
        read:
          staffer: ".*"
schema_objects: {}
""".strip(),
    )


@pytest.mark.unit
def test_token_decoder_uses_anonymous_role_when_claims_checks_are_skipped(monkeypatch):
    _set_api_spec(monkeypatch)
    monkeypatch.setenv("ANONYMOUS_ROLE", "public")
    monkeypatch.setenv("SKIP_CLAIMS_CHECK", "true")
    monkeypatch.setenv("TOKEN_VALIDATOR_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:auth")

    def fail_validator(_lambda_arn):
        raise AssertionError("lambda validator should not be constructed for public routes")

    monkeypatch.setattr(token_decoder_module, "LambdaTokenValidator", fail_validator)

    seen = {}

    @token_decoder_module.token_decoder()
    def handler(event, context):
        seen["event"] = event
        return {"statusCode": 200}

    event = {
        "resource": "/public",
        "httpMethod": "GET",
        "headers": {"Authorization": "Bearer token-from-browser"},
    }

    result = handler(event, None)

    assert result == {"statusCode": 200}
    assert seen["event"]["requestContext"]["authorizer"] == {"roles": ["public"]}


@pytest.mark.unit
def test_token_decoder_preserves_existing_gateway_authorizer(monkeypatch):
    _set_api_spec(monkeypatch)
    monkeypatch.setenv("ANONYMOUS_ROLE", "public")
    monkeypatch.setenv("SKIP_CLAIMS_CHECK", "true")

    @token_decoder_module.token_decoder()
    def handler(event, context):
        return event["requestContext"]["authorizer"]

    event = {
        "requestContext": {
            "authorizer": {
                "roles": ["staffer"],
                "claims": {"sub": "user-1"},
            }
        }
    }

    result = handler(event, None)

    assert result == {
        "roles": ["staffer"],
        "claims": {"sub": "user-1"},
    }


@pytest.mark.unit
def test_token_decoder_does_not_bypass_validation_for_non_public_routes(monkeypatch):
    _set_api_spec(monkeypatch)
    monkeypatch.setenv("ANONYMOUS_ROLE", "public")
    monkeypatch.setenv("SKIP_CLAIMS_CHECK", "true")
    monkeypatch.setenv("TOKEN_VALIDATOR_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:auth")

    calls = []

    class DummyValidator:
        def __init__(self, lambda_arn):
            calls.append(("init", lambda_arn))

        def validate(self, token, method_arn="arn:aws:execute-api:*:*:*"):
            calls.append(("validate", token, method_arn))
            return {"roles": ["staffer"], "sub": "user-1"}

    monkeypatch.setattr(token_decoder_module, "LambdaTokenValidator", DummyValidator)

    @token_decoder_module.token_decoder()
    def handler(event, context):
        return event["requestContext"]["authorizer"]

    result = handler(
        {
            "resource": "/private",
            "httpMethod": "GET",
            "headers": {"Authorization": "Bearer token-from-browser"},
        },
        None,
    )

    assert result == {"roles": ["staffer"], "sub": "user-1"}
    assert calls == [
        ("init", "arn:aws:lambda:us-east-1:123:function:auth"),
        ("validate", "token-from-browser", "arn:aws:execute-api:*:*:*"),
    ]


@pytest.mark.unit
def test_token_decoder_rejects_non_public_routes_without_valid_auth(monkeypatch):
    _set_api_spec(monkeypatch)
    monkeypatch.setenv("ANONYMOUS_ROLE", "public")
    monkeypatch.delenv("TOKEN_VALIDATOR_LAMBDA_ARN", raising=False)
    monkeypatch.delenv("JWKS_HOST", raising=False)
    monkeypatch.delenv("JWT_ISSUER", raising=False)
    monkeypatch.delenv("JWT_ALLOWED_AUDIENCES", raising=False)

    @token_decoder_module.token_decoder()
    def handler(event, context):
        raise AssertionError("handler should not run for unauthorized private route")

    result = handler(
        {
            "resource": "/private",
            "httpMethod": "GET",
            "headers": {},
        },
        None,
    )

    assert result["statusCode"] == 401

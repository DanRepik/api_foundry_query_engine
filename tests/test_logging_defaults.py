import importlib
import json
import logging

import pytest

from api_foundry_query_engine.utils import logger as logger_module
from api_foundry_query_engine.utils import token_decoder as token_decoder_module

SDK_LOGGERS = logger_module.AWS_SDK_LOGGERS


@pytest.fixture
def restore_logging():
    """Reloading utils.logger reconfigures the root logger; put the levels
    back so later tests see what they saw before."""
    root = logging.getLogger()
    saved = (root.level, {name: logging.getLogger(name).level for name in SDK_LOGGERS})
    yield
    root.setLevel(saved[0])
    for name, level in saved[1].items():
        logging.getLogger(name).setLevel(level)


def _reload_logger_module():
    return importlib.reload(logger_module)


@pytest.mark.unit
def test_root_logger_defaults_to_info(monkeypatch, restore_logging):
    monkeypatch.delenv("LOGGING_LEVEL", raising=False)
    _reload_logger_module()

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


@pytest.mark.unit
def test_aws_sdk_loggers_stay_at_warning_even_when_logging_level_is_debug(monkeypatch, restore_logging):
    """At DEBUG botocore logs signed request headers (x-amz-security-token)
    and request bodies (rds-data SQL parameters); turning on engine debug
    logging must not turn those on."""
    monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")
    monkeypatch.delenv("AWS_SDK_LOGGING_LEVEL", raising=False)
    module = _reload_logger_module()
    module.logger(__name__)

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG
    for name in SDK_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING, name
    assert not logging.getLogger("botocore.endpoint").isEnabledFor(logging.DEBUG)


@pytest.mark.unit
def test_aws_sdk_logging_can_be_enabled_explicitly(monkeypatch, restore_logging):
    monkeypatch.setenv("AWS_SDK_LOGGING_LEVEL", "DEBUG")
    _reload_logger_module()

    assert logging.getLogger("botocore").getEffectiveLevel() == logging.DEBUG


@pytest.mark.unit
def test_redacted_event_masks_credential_headers_case_insensitively():
    event = {
        "headers": {"Authorization": "Bearer secret-jwt", "Cookie": "session=abc", "Accept": "application/json"},
        "multiValueHeaders": {"authorization": ["Bearer secret-jwt"], "X-Api-Key": ["key-123"]},
        "path": "/albums",
    }

    redacted = token_decoder_module._redacted_event(event)

    assert redacted["headers"] == {"Authorization": "[REDACTED]", "Cookie": "[REDACTED]", "Accept": "application/json"}
    assert redacted["multiValueHeaders"] == {"authorization": "[REDACTED]", "X-Api-Key": "[REDACTED]"}
    assert redacted["path"] == "/albums"
    # The handler still gets the real event.
    assert event["headers"]["Authorization"] == "Bearer secret-jwt"


@pytest.mark.unit
def test_token_decoder_debug_event_dump_never_contains_the_bearer_token(monkeypatch, caplog):
    monkeypatch.setenv("ANONYMOUS_ROLE", "public")
    monkeypatch.setenv("SKIP_CLAIMS_CHECK", "true")

    @token_decoder_module.token_decoder()
    def handler(event, context):
        return "ok"

    event = {
        "headers": {"Authorization": "Bearer secret-jwt"},
        "requestContext": {"authorizer": {"roles": ["staffer"], "claims": {"sub": "user-1"}}},
    }
    with caplog.at_level(logging.DEBUG, logger=token_decoder_module.log.name):
        assert handler(event, None) == "ok"

    dumps = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Event structure")]
    assert dumps, "expected the DEBUG event dump to run"
    assert all("secret-jwt" not in message for message in dumps)
    assert json.loads(dumps[0].split(": ", 1)[1])["headers"]["Authorization"] == "[REDACTED]"

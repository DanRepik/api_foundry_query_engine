import json

import pytest

from api_foundry_query_engine import lambda_handler
from api_foundry_query_engine.lambda_handler import QueryEngine


class _Adapter:
    def __init__(self, response):
        self.response = response

    def process_event(self, event):
        return self.response


def _engine(response, config):
    engine = QueryEngine.__new__(QueryEngine)
    engine.adapter = _Adapter(response)
    engine.max_response_bytes = int(config.get("MAX_RESPONSE_BYTES") or lambda_handler.DEFAULT_MAX_RESPONSE_BYTES)
    return engine


@pytest.mark.unit
class TestResponseSizeLimit:
    """Lambda rejects synchronous responses over 6 MB, which API Gateway then
    surfaces as an opaque 502. The handler must refuse with an explanatory
    502 of its own instead. (Shipped in 0.8.82; carried onto main.)"""

    def test_response_within_limit_is_returned(self):
        result = _engine([{"a": 1}], {"MAX_RESPONSE_BYTES": "1000"}).handler({})
        assert result["statusCode"] == 200
        assert json.loads(result["body"]) == [{"a": 1}]

    def test_response_over_limit_is_refused_with_a_clear_502(self):
        result = _engine([{"a": "x" * 2000}], {"MAX_RESPONSE_BYTES": "1000"}).handler({})
        assert result["statusCode"] == 502
        assert "narrow the request with filters" in json.loads(result["body"])["message"]

    def test_default_limit_leaves_room_for_lambdas_6mb_cap(self):
        assert lambda_handler.DEFAULT_MAX_RESPONSE_BYTES < 6 * 1024 * 1024

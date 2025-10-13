import pytest

from api_foundry_query_engine.services.service import Service
from api_foundry_query_engine.adapters.gateway_adapter import GatewayAdapter
from api_foundry_query_engine.operation import Operation


def proto_event(
    method: str = "GET",
    resource: str = "/accounts",
    path: str = "/accounts",
) -> dict[str, object]:
    return {
        "resource": resource,
        "path": path,
        "httpMethod": method,
        "requestContext": {
            "resourcePath": resource,
            "httpMethod": method,
            "path": path,
        },
        "headers": {
            "accept": "application/json",
        },
        "queryStringParameters": None,
        "pathParameters": None,
        "body": None,
        "isBase64Encoded": False,
    }


class MockService(Service):
    def execute(self, operation: Operation):
        # Simulating service execution and returning dummy result
        assert operation.query_params.get("account_id", 0) == 123
        assert operation.action == "read"
        return [{"account_id": 123}]


@pytest.mark.unit
class TestGatewayAdapter:
    def test_gateway_adapter_path_params(self):
        mock_service = MockService()
        mock_adapter = GatewayAdapter(service=mock_service)

        # Calling the process_event method
        event = proto_event("GET", "/accounts/{account_id}", "/accounts/123")
        event["pathParameters"] = {"account_id": 123}

        result = mock_adapter.process_event(event=event)

        # Asserting the result
        assert result == [{"account_id": 123}]

    def test_gateway_adapter_query_params(self):
        mock_service = MockService()
        mock_adapter = GatewayAdapter(service=mock_service)

        # Calling the process_event method
        event = proto_event("GET", "/accounts", "/accounts?account_id=123")
        event["queryStringParameters"] = {"account_id": 123}

        result = mock_adapter.process_event(event)

        # Asserting the result
        assert result == [{"account_id": 123}]

    @pytest.mark.skip
    def test_gateway_adapter_camel_case(self):
        mock_service = MockService()
        mock_adapter = GatewayAdapter(service=mock_service)

        # Calling the process_event method
        event = proto_event("GET", "/accounts", "/accounts?accountId=123&_case=camel")
        event["queryStringParameters"] = {"accountId": 123}

        result = mock_adapter.process_event(event)

        # Asserting the result
        assert result == [{"accountId": 123}]

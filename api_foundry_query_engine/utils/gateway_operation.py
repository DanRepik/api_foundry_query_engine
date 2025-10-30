"""
Gateway Operation Decorator for Lambda Functions

This decorator handles the marshalling and unmarshalling of API Gateway events
into Operation objects, similar to what GatewayAdapter does but as a decorator.
It extracts the operation details and adds them to the event for downstream processing.
"""

import functools
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException

log = logging.getLogger(__name__)


def gateway_operation(validate_scopes: bool = True, auto_marshal_response: bool = True):
    """
    Decorator to handle API Gateway event marshalling and unmarshalling.

    This decorator:
    1. Unmarshals API Gateway events into Operation objects
    2. Adds the Operation to the event for downstream processing
    3. Validates OAuth scopes based on the operation
    4. Marshals response data back to API Gateway format

    Args:
        validate_scopes: Whether to validate OAuth scopes (default: True)
        auto_marshal_response: Whether to automatically format response (default: True)

    Returns:
        Decorated function that processes API Gateway events

    Example:
        @token_decoder()
        @claims_check()
        @gateway_operation()
        def handler(event, context):
            # event now contains 'operation' key with Operation object
            operation = event['operation']
            return {"data": [{"id": 1, "name": "Test"}]}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                log.debug("Gateway operation decorator starting")

                # Unmarshal API Gateway event into Operation
                operation = _unmarshal_gateway_event(event, validate_scopes)

                # Add operation to event for downstream processing
                event["operation"] = operation

                log.debug(
                    "Created operation: entity=%s, action=%s",
                    operation.entity,
                    operation.action,
                )

                # Execute the original function
                result = func(event, context)

                # Auto-marshal response if requested
                if auto_marshal_response and isinstance(result, (list, dict)):
                    return _marshal_response(result)
                else:
                    return result

            except ApplicationException:
                raise
            except Exception as e:
                log.error("Gateway operation error: %s", str(e))
                raise ApplicationException(
                    status_code=500,
                    message="Internal server error during operation processing",
                )

        return wrapper

    return decorator


def _unmarshal_gateway_event(event: Dict[str, Any], validate_scopes: bool) -> Operation:
    """
    Unmarshal API Gateway event into Operation object.

    This replicates the logic from GatewayAdapter.unmarshal() method.
    """
    # Extract entity from resource path
    resource = event.get("resource")
    if resource is not None and "/" in resource:
        parts = resource.split("/")
        entity = parts[1] if len(parts) > 1 else None
    else:
        entity = None

    # Map HTTP method to action
    method = str(event.get("httpMethod", "")).upper()
    actions_map = {
        "GET": "read",
        "POST": "create",
        "PUT": "update",
        "DELETE": "delete",
    }
    action = actions_map.get(method, "read")

    # Collect parameters from path and query string
    event_params = {}

    path_parameters = _convert_parameters(event.get("pathParameters"))
    if path_parameters is not None:
        event_params.update(path_parameters)

    query_string_parameters = _convert_parameters(event.get("queryStringParameters"))
    if query_string_parameters is not None:
        event_params.update(query_string_parameters)

    query_params, metadata_params = _split_params(event_params)

    # Extract store params from request body
    store_params = {}
    body = event.get("body")
    if body is not None and len(body) > 0:
        store_params = json.loads(body)

    # Extract claims from authorizer context
    authorizer_info = event.get("requestContext", {}).get("authorizer", {})
    claims = authorizer_info.get("claims", {})
    scope_str = claims.get("scope", "")

    # Validate OAuth scopes if requested
    if validate_scopes and entity and scope_str:
        _validate_oauth_scopes(method, entity, scope_str)

    return Operation(
        entity=entity,
        action=action,
        store_params=store_params,
        query_params=query_params,
        metadata_params=metadata_params,
        claims=claims,
    )


def _decode_json_array(raw_value: Any) -> List[Any]:
    """Decode JSON-encoded arrays from OAuth context."""
    if isinstance(raw_value, str):
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return []
    else:
        return raw_value if isinstance(raw_value, list) else []


def _validate_oauth_scopes(method: str, entity: str, scope_str: str) -> None:
    """
    Validate OAuth scopes based on the operation.

    Enforces scope pattern: read|write|delete:<entity>
    """
    required_action = {
        "GET": "read",
        "POST": "write",
        "PUT": "write",
        "PATCH": "write",
        "DELETE": "delete",
    }.get(method, "read")

    required_scope = f"{required_action}:{entity}"
    token_scopes = set(str(scope_str).split())

    def _has_scope(required: str) -> bool:
        return (
            required in token_scopes
            or f"{required_action}:*" in token_scopes
            or "*" in token_scopes
            or "*:*" in token_scopes
        )

    if not _has_scope(required_scope):
        raise ApplicationException(
            401, f"insufficient_scope: required_scope={required_scope}"
        )


def _convert_parameters(
    parameters: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Convert parameters to appropriate types.

    Tries to convert strings to int, then float, falls back to string.
    """
    if parameters is None:
        return None

    result = {}
    for parameter, value in parameters.items():
        try:
            result[parameter] = int(value)
        except ValueError:
            try:
                result[parameter] = float(value)
            except ValueError:
                result[parameter] = value
    return result


def _split_params(parameters: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Split parameters into query_params and metadata_params.

    Metadata parameters start with '__'.
    """
    query_params = {}
    metadata_params = {}

    for key, value in parameters.items():
        if key.startswith("__"):
            metadata_params[key] = value
        else:
            query_params[key] = value

    return query_params, metadata_params


def _marshal_response(result: Any) -> Dict[str, Any]:
    """
    Marshal response data into API Gateway format.

    Args:
        result: The response data (list or dict)

    Returns:
        API Gateway compatible response
    """
    try:
        return {
            "isBase64Encoded": False,
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result) if result is not None else json.dumps([]),
        }
    except (TypeError, ValueError) as e:
        log.error("Failed to marshal response: %s", e)
        raise ApplicationException(
            status_code=500, message="Failed to serialize response data"
        )


# Convenience decorators for specific use cases
def gateway_read_operation(validate_scopes: bool = True):
    """Convenience decorator for read operations."""
    return gateway_operation(
        validate_scopes=validate_scopes, auto_marshal_response=True
    )


def gateway_write_operation(validate_scopes: bool = True):
    """Convenience decorator for write operations."""
    return gateway_operation(
        validate_scopes=validate_scopes, auto_marshal_response=True
    )


def gateway_operation_no_validation():
    """Decorator that skips scope validation."""
    return gateway_operation(validate_scopes=False, auto_marshal_response=True)


def gateway_operation_raw_response():
    """Decorator that doesn't auto-marshal the response."""
    return gateway_operation(validate_scopes=True, auto_marshal_response=False)

"""
Example of using the gateway_operation decorator with the Query Engine.

This shows how to integrate the gateway operation marshalling/unmarshalling
as a decorator instead of using the GatewayAdapter directly.
"""

import json
import logging
import os
from typing import Any, Dict

from api_foundry_query_engine.utils.api_model import set_api_model
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.token_decoder import token_decoder
from api_foundry_query_engine.utils.claims_check import requires_authentication
from api_foundry_query_engine.utils.gateway_operation import (
    gateway_operation,
    gateway_read_operation,
    gateway_write_operation,
    gateway_operation_no_validation,
)
from api_foundry_query_engine.services.transactional_service import TransactionalService
from api_foundry_query_engine.connectors.connection_factory import ConnectionFactory

log = logging.getLogger(__name__)


# Option 1: Full decorator stack for standard Query Engine operation
@token_decoder()
@requires_authentication()
@gateway_operation()
def handler(event, context):
    """
    Standard Query Engine handler with full decorator stack.

    Decorator flow:
    1. @token_decoder() - Validates JWT and extracts claims
    2. @requires_authentication() - Ensures valid authentication
    3. @gateway_operation() - Unmarshals event into Operation, validates scopes
    4. Handler processes the operation and returns data
    5. @gateway_operation() - Marshals response back to API Gateway format
    """
    # The operation is now available in the event
    operation = event["operation"]

    log.info(f"Processing {operation.action} operation on {operation.entity}")

    # Process the operation using the Query Engine services
    return _process_operation(operation)


# Option 2: Using convenience decorators for specific operation types
@token_decoder()
@requires_authentication()
@gateway_read_operation()
def read_handler(event, context):
    """Handler optimized for read operations."""
    operation = event["operation"]
    return _process_operation(operation)


@token_decoder()
@requires_authentication()
@gateway_write_operation()
def write_handler(event, context):
    """Handler optimized for write operations."""
    operation = event["operation"]
    return _process_operation(operation)


# Option 3: Skip scope validation for internal/admin operations
@token_decoder()
@requires_authentication()
@gateway_operation_no_validation()
def admin_handler(event, context):
    """Handler that skips OAuth scope validation."""
    operation = event["operation"]
    return _process_operation(operation)


# Option 4: Custom response handling
@token_decoder()
@requires_authentication()
@gateway_operation(validate_scopes=True, auto_marshal_response=False)
def custom_response_handler(event, context):
    """
    Handler with custom response marshalling.

    This handler manually controls the response format instead of
    using the automatic marshalling.
    """
    operation = event["operation"]

    try:
        result = _process_operation(operation)

        # Custom response format
        return {
            "isBase64Encoded": False,
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "X-Operation": f"{operation.action}:{operation.entity}",
                "X-User": operation.subject or "anonymous",
            },
            "body": json.dumps(
                {
                    "data": result,
                    "meta": {
                        "operation": operation.action,
                        "entity": operation.entity,
                        "user": operation.subject,
                    },
                }
            ),
        }

    except ApplicationException as e:
        return {
            "isBase64Encoded": False,
            "statusCode": e.status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


# Option 5: Processing operation data directly
@token_decoder()
@requires_authentication()
@gateway_operation()
def direct_processing_handler(event, context):
    """
    Handler that processes operation data directly without services.

    This shows how to access all the operation details that were
    extracted from the API Gateway event.
    """
    operation = event["operation"]

    # Access all operation details
    log.info(f"Entity: {operation.entity}")
    log.info(f"Action: {operation.action}")
    log.info(f"Query params: {operation.query_params}")
    log.info(f"Store params: {operation.store_params}")
    log.info(f"Metadata params: {operation.metadata_params}")
    log.info(f"User roles: {operation.roles}")
    log.info(f"User subject: {operation.subject}")

    # Process based on action type
    if operation.action == "read":
        return _handle_read_operation(operation)
    elif operation.action in ["create", "update"]:
        return _handle_write_operation(operation)
    elif operation.action == "delete":
        return _handle_delete_operation(operation)
    else:
        raise ApplicationException(400, f"Unknown action: {operation.action}")


def _process_operation(operation) -> Any:
    """
    Process an operation using the Query Engine services.

    This replicates what the original QueryEngine.handler() method does.
    """
    # Get database connection
    config = os.environ
    connection_factory = ConnectionFactory(config)

    # Use TransactionalService to process the operation
    service = TransactionalService(operation, connection_factory)
    return service.execute()


def _handle_read_operation(operation) -> Dict[str, Any]:
    """Handle read operations."""
    # Example: Get data based on query parameters
    entity_id = operation.query_params.get("id")

    if entity_id:
        return {"id": entity_id, "entity": operation.entity, "action": "read"}
    else:
        return [
            {"id": 1, "entity": operation.entity},
            {"id": 2, "entity": operation.entity},
        ]


def _handle_write_operation(operation) -> Dict[str, Any]:
    """Handle create/update operations."""
    # Example: Process store parameters (request body)
    data = operation.store_params

    return {
        "action": operation.action,
        "entity": operation.entity,
        "data": data,
        "user": operation.subject,
    }


def _handle_delete_operation(operation) -> Dict[str, Any]:
    """Handle delete operations."""
    entity_id = operation.query_params.get("id")

    if not entity_id:
        raise ApplicationException(400, "ID required for delete operation")

    return {
        "action": "delete",
        "entity": operation.entity,
        "id": entity_id,
        "deleted": True,
    }


# Initialize API model (same as original lambda_handler.py)
def _initialize_engine():
    """Initialize the Query Engine configuration."""
    if not hasattr(_initialize_engine, "initialized"):
        log.info("Loading engine config from environment variables")
        config = os.environ
        set_api_model(config)
        _initialize_engine.initialized = True


# Ensure initialization on module load
_initialize_engine()


# Export the standard handler
__all__ = ["handler"]

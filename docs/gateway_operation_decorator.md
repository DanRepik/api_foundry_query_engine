# Gateway Operation Decorator

The `gateway_operation` decorator provides a clean way to handle API Gateway event marshalling and unmarshalling in AWS Lambda functions, replacing the need to manually use the `GatewayAdapter` class.

## Overview

This decorator automatically:
- Extracts API Gateway events into `Operation` objects
- Validates OAuth scopes (optional)
- Handles request/response marshalling
- Manages error responses
- Converts field names between camelCase and snake_case

## Basic Usage

```python
from api_foundry_query_engine.utils.token_decoder import token_decoder
from api_foundry_query_engine.utils.claims_check import claims_check
from api_foundry_query_engine.utils.gateway_operation import gateway_operation

@token_decoder()
@claims_check()  # Auto-validates path-based scopes by default
@gateway_operation()
def lambda_handler(event, context):
    # The operation is automatically added to the event
    operation = event['operation']

    # Process the operation
    result = process_operation(operation)

    # Return data - automatic response marshalling
    return result
```

## Decorator Stack Order

The decorators should be applied in this order (from bottom to top):

1. `@gateway_operation()` - Request/response handling (outermost)
2. `@claims_check()` - Path-based scope validation and authorization
3. `@token_decoder()` - JWT token validation (innermost)

## Available Decorators

### 1. `@gateway_operation()`

Full-featured decorator with all options:

```python
@gateway_operation(
    validate_scopes=True,           # Enable OAuth scope validation
    auto_marshal_response=True      # Automatic response formatting
)
def handler(event, context):
    operation = event['operation']
    return {"data": "response"}
```

### 2. `@gateway_read_operation()`

Optimized for read operations (GET requests):

```python
@gateway_read_operation()
def read_handler(event, context):
    operation = event['operation']
    # Scope validation expects 'read:entity' or higher
    return get_data(operation)
```

### 3. `@gateway_write_operation()`

Optimized for write operations (POST/PUT requests):

```python
@gateway_write_operation()
def write_handler(event, context):
    operation = event['operation']
    # Scope validation expects 'write:entity' or higher
    return save_data(operation)
```

### 4. `@gateway_operation_no_validation()`

Skips OAuth scope validation:

```python
@gateway_operation_no_validation()
def admin_handler(event, context):
    operation = event['operation']
    # No scope validation - for internal/admin endpoints
    return admin_operation(operation)
```

## Operation Object

The decorator creates an `Operation` object with these properties:

```python
operation = event['operation']

# Entity and action
operation.entity          # e.g., "album"
operation.action          # e.g., "read", "create", "update", "delete"

# Parameters
operation.query_params    # Query string and path parameters
operation.store_params    # Request body data
operation.metadata_params # Special params like __sort, __limit

# User context
operation.subject         # JWT 'sub' claim (user ID)
operation.roles          # List of user roles
operation.claims         # Full JWT claims dictionary
```

## OAuth Scope Validation

When `validate_scopes=True`, the decorator checks that the user's OAuth scope matches the required permission level:

### Scope Hierarchy
- `read:entity` - Can perform read operations
- `write:entity` - Can perform read and write operations
- `delete:entity` - Can perform read, write, and delete operations
- `admin:entity` - Can perform any operation
- `*:*` - Global admin access

### Examples
```python
# User has scope "read:albums"
GET /albums     ✅ Allowed (read operation)
POST /albums    ❌ Forbidden (needs write:albums)
DELETE /albums  ❌ Forbidden (needs delete:albums)

# User has scope "write:albums"
GET /albums     ✅ Allowed (write includes read)
POST /albums    ✅ Allowed (write operation)
DELETE /albums  ❌ Forbidden (needs delete:albums)

# User has scope "*:*"
Any operation   ✅ Allowed (global admin)
```

## Response Handling

### Automatic Marshalling (Default)

The decorator automatically formats responses:

```python
@gateway_operation()
def handler(event, context):
    # Return any data
    return {"albums": [...]}

# Becomes:
{
    "isBase64Encoded": false,
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": "{\"albums\": [...]}"
}
```

### Manual Response Control

Disable auto-marshalling for custom responses:

```python
@gateway_operation(auto_marshal_response=False)
def handler(event, context):
    return {
        "isBase64Encoded": false,
        "statusCode": 201,
        "headers": {"X-Custom": "header"},
        "body": json.dumps({"custom": "response"})
    }
```

## Error Handling

Exceptions are automatically converted to proper HTTP responses:

```python
@gateway_operation()
def handler(event, context):
    if invalid_request:
        raise ApplicationException(400, "Invalid request data")

    # Becomes:
    {
        "statusCode": 400,
        "headers": {"Content-Type": "application/json"},
        "body": "{\"error\": \"Invalid request data\"}"
    }
```

## Integration with Query Engine

The decorator integrates seamlessly with the existing Query Engine services:

```python
from api_foundry_query_engine.services.transactional_service import TransactionalService
from api_foundry_query_engine.connectors.connection_factory import ConnectionFactory

@token_decoder()
@requires_authentication()
@gateway_operation()
def query_engine_handler(event, context):
    operation = event['operation']

    # Use existing Query Engine services
    config = os.environ
    connection_factory = ConnectionFactory(config)
    service = TransactionalService(operation, connection_factory)

    return service.execute()
```

## Migration from GatewayAdapter

### Before (Using GatewayAdapter)
```python
def lambda_handler(event, context):
    adapter = GatewayAdapter(config)
    operation = adapter.unmarshal(event)

    result = process_operation(operation)

    return adapter.marshal(result)
```

### After (Using Decorator)
```python
@token_decoder()
@requires_authentication()
@gateway_operation()
def lambda_handler(event, context):
    operation = event['operation']
    result = process_operation(operation)
    return result
```

## Testing

Test the decorated handlers by mocking API Gateway events:

```python
def test_handler():
    event = {
        "httpMethod": "GET",
        "path": "/albums",
        "queryStringParameters": {"limit": "10"},
        "requestContext": {
            "authorizer": {
                "sub": "user123",
                "scope": "read:albums",
                "roles": ["user"]
            }
        }
    }

    result = handler(event, {})
    assert result["statusCode"] == 200
```

## Configuration

The decorator uses the same configuration as the existing Query Engine:

- `JWKS_HOST` - JWT validation endpoint
- `JWT_ISSUER` - Expected JWT issuer
- `JWT_ALLOWED_AUDIENCES` - Allowed JWT audiences

## Best Practices

1. **Always use the full decorator stack** for user-facing endpoints
2. **Use convenience decorators** (`gateway_read_operation`, etc.) for cleaner code
3. **Skip scope validation** only for internal/admin endpoints
4. **Return simple data structures** - let the decorator handle response formatting
5. **Use ApplicationException** for user-facing errors
6. **Test with realistic API Gateway events** to ensure proper operation extraction

# Claims Check Decorator

The `claims_check` decorator provides JWT scope and permission validation for AWS Lambda functions. It works in conjunction with the `@token_decoder()` decorator to ensure that authenticated users have the required permissions for the requested operation.

**By default**, the decorator automatically validates that user scopes or permissions match the request path and HTTP method (e.g., GET /employee requires `read:employee` scope OR `employee.read` permission).

## Features

- **Automatic Path Validation**: By default validates scopes/permissions match request path (GET /employee needs `read:employee` scope OR `employee.read` permission)
- **Dual Authorization**: Accepts either OAuth scopes OR fine-grained permissions to satisfy requirements
- **Custom Requirements**: Specify exact scopes and permissions required beyond path validation
- **Entity Extraction**: Extract entity names from request paths automatically
- **Convenience Decorators**: Pre-built decorators for common operations (read, write, delete)
- **Flexible Configuration**: Multiple ways to configure permission requirements

## Basic Usage

### 1. Default Path Validation (Recommended)

```python
from api_foundry_query_engine.utils.token_decoder import token_decoder
from api_foundry_query_engine.utils.claims_check import claims_check

@token_decoder()
@claims_check()  # Default: validate_path_scope=True
def handler(event, context):
    # Automatically validates request path against user permissions:
    # - GET /employee requires read:employee scope OR employee.read permission
    # - POST /employee requires write:employee scope OR employee.write permission
    # - DELETE /employee requires delete:employee scope OR employee.delete permission
    return {"statusCode": 200, "body": "Success"}
```

### 2. Skip Path Validation

```python
@token_decoder()
@claims_check(validate_path_scope=False)
def handler(event, context):
    # Only validates authentication exists - no path-based scope checking
    # SQL-level permissions will still be enforced by query engine
    return {"statusCode": 200, "body": "Success"}
```

### 3. Additional Scope Requirements

```python
@token_decoder()
@claims_check(
    required_scopes=["read:*", "write:album"],
    required_permissions=["album.read", "album.modify"]
)
def handler(event, context):
    # Path validation PLUS additional requirements:
    # - Path validation (e.g., GET /album needs read:album OR album.read)
    # - Either "read:*" OR "write:album" scope
    # - Both "album.read" AND "album.modify" permissions
    return {"statusCode": 200, "body": "Success"}
```

### 4. Convenience Decorators

```python
from api_foundry_query_engine.utils.claims_check import (
    requires_read_scope,
    requires_write_scope,
    requires_delete_scope
)

@token_decoder()
@requires_read_scope("album")
def read_albums(event, context):
    # Requires "read:album" or "read:*" scope
    return {"statusCode": 200, "body": "Albums"}

@token_decoder()
@requires_write_scope()
def write_entity(event, context):
    # Requires minimum write-level scope for any entity
    return {"statusCode": 200, "body": "Updated"}

@token_decoder()
@requires_delete_scope()
def delete_any(event, context):
    # Requires "delete:*" scope for any delete operation
    return {"statusCode": 200, "body": "Deleted"}
```

## Configuration Options

### Decorator Parameters

- **`validate_path_scope`**: Auto-validate scope matches request path/method (default: `True`)
- **`required_scopes`**: List of additional required OAuth scopes (e.g., `["read:*", "write:album"]`)
- **`required_permissions`**: List of additional required permissions (e.g., `["album.read", "album.write"]`)
- **`operation_type`**: Override operation type detection (`"read"`, `"write"`, `"delete"`)
- **`entity_name`**: Override entity name detection
- **`min_scope_level`**: Minimum scope level required (`"read"`, `"write"`, `"delete"`, `"admin"`)

### Scope Formats

The decorator supports various scope formats:

- **Wildcard scopes**: `read:*`, `write:*`, `delete:*` - Allow operation on any entity
- **Entity-specific scopes**: `read:album`, `write:customer` - Allow operation on specific entity
- **Admin scopes**: `admin:*` - Full administrative access

### Permission Formats

Permissions can use wildcards and patterns:

- **Direct permissions**: `album.read`, `customer.write`
- **Wildcard permissions**: `album.*`, `*.read`
- **Admin permissions**: `system.admin`, `data.modify`

## JWT Claims Structure

The decorator expects JWT claims to be available in `event.requestContext.authorizer` (set by `@token_decoder()`):

```json
{
  "sub": "user123",
  "scope": "read:* write:album delete:customer",
  "permissions": ["album.read", "album.write", "customer.*"],
  "roles": ["user", "editor"]
}
```

## Dual Authorization System

The decorator uses a flexible dual authorization approach - users can satisfy access requirements with **either scopes OR permissions**:

### Scope-Based Authorization
Traditional OAuth 2.0 scopes in format `operation:entity`:
- `read:employee` - Read access to employee data
- `write:*` - Write access to any entity
- `*:*` or `*` - Global access

### Permission-Based Authorization
Fine-grained permissions in format `entity.operation`:
- `employee.read` - Read employee data
- `customer.*` - All operations on customer data
- `system.admin` - Administrative permissions

### Access Resolution
For a `GET /employee` request, access is granted if user has:
- **Scope**: `read:employee`, `read:*`, `*:*`, or `*`
- **OR Permission**: `employee.read` or `employee.*`

This allows mixing OAuth scopes with application-specific permissions in the same system.

## Path and Operation Detection

### Operation Type Detection

HTTP methods are mapped to operation types:

- `GET` → `read`
- `POST`, `PUT`, `PATCH` → `write`
- `DELETE` → `delete`

### Entity Extraction

Entities are extracted from request paths:

- `/chinook-api/album` → `album`
- `/api/v1/customer/123` → `customer` (ignores path parameters)
- `/album/{id}` → `album`

## Error Handling

The decorator raises `ApplicationException` with appropriate HTTP status codes:

- **401 Unauthorized**: No JWT claims found
- **403 Forbidden**: Insufficient scopes or permissions
- **500 Internal Server Error**: Unexpected validation errors

## Advanced Examples

### Conditional Claims Checking

```python
@token_decoder()
def conditional_handler(event, context):
    http_method = event.get("httpMethod", "GET").upper()

    if http_method == "GET":
        @requires_read_scope(extract_from_path=True)
        def read_op(evt, ctx):
            return process_read(evt)
        return read_op(event, context)

    elif http_method in ["POST", "PUT"]:
        @claims_check(
            required_scopes=["write:*"],
            required_permissions=["data.modify"]
        )
        def write_op(evt, ctx):
            return process_write(evt)
        return write_op(event, context)
```

### Role-Based Access Control

```python
@token_decoder()
@claims_check(
    required_scopes=["admin:*"],
    required_permissions=["system.admin", "data.delete"]
)
def admin_only_handler(event, context):
    # Only users with admin scope AND admin permissions can access
    return {"statusCode": 200, "body": "Admin operation complete"}
```

### Multiple Entity Types

```python
@token_decoder()
@claims_check(
    required_scopes=["read:album", "read:artist", "read:track"],
    operation_type="read"
)
def music_catalog_handler(event, context):
    # User needs access to read albums, artists, OR tracks
    return {"statusCode": 200, "body": "Music catalog"}
```

## Integration with API Foundry

The claims_check decorator integrates seamlessly with API Foundry's permission system:

1. **JWT Token Validation**: `@token_decoder()` validates and decodes JWT tokens
2. **Claims Extraction**: `@claims_check()` extracts scopes and permissions from validated claims
3. **Permission Enforcement**: Validates user permissions against operation requirements
4. **Request Processing**: If validation passes, the original Lambda handler executes

This provides a complete authentication and authorization pipeline for API Foundry REST APIs.

## Testing

Use the provided test utilities to validate claims checking:

```python
from api_foundry_query_engine.utils.claims_check import _scope_matches, _permission_matches

# Test scope matching
assert _scope_matches(["read:*"], "read:album", "read", "album")
assert _scope_matches(["write:album"], "write:album", "write", "album")

# Test permission matching
assert _permission_matches(["album.*"], "album.read")
assert _permission_matches(["system.admin"], "system.admin")
```

See `tests/test_claims_check.py` for comprehensive test examples.

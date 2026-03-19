# API Foundry Query Engine

The **API Foundry Query Engine** is a serverless runtime engine that powers API Foundry's REST APIs. It runs as an AWS Lambda function behind API Gateway, transforming HTTP requests into secure, optimized database operations based on OpenAPI specifications with custom `x-af-*` extensions.

## Key Features

- **Specification-Driven**: Auto-generates CRUD operations from OpenAPI schemas with `x-af-database` extensions
- **Batch Operations**: Multi-operation workflows with dependency resolution and cross-reference substitution
- **Advanced Security**: Multi-level authorization with JWT validation, RBAC, and SQL-level permission enforcement
- **Sophisticated RBAC**: Field-level and row-level permissions with claim templating for multi-tenant scenarios
- **SQL Generation**: Dynamic, optimized SQL creation with parameterized queries and permission filtering
- **Multi-Database Support**: PostgreSQL, MySQL, and Oracle compatibility
- **Association Handling**: Automatic loading of related objects via `x-af-parent-property` and `x-af-child-property`

## Table of Contents

- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [Operation Model](#operation-model)
  - [Authentication & Authorization](#authentication--authorization)
  - [Permission System](#permission-system)
- [Advanced Features](#advanced-features)
  - [Batch Operations](#batch-operations)
  - [Association Loading](#association-loading)
  - [Metadata Parameters](#metadata-parameters)
- [API Specification Integration](#api-specification-integration)
- [Development & Testing](#development--testing)
- [Configuration Reference](#configuration-reference)
- [Examples & Patterns](#examples--patterns)
- [Troubleshooting](#troubleshooting)
- [Performance & Best Practices](#performance--best-practices)

## Architecture

```
HTTP Request → JWT Decoder → Gateway Adapter → Services → DAO → SQL Handlers → Database
     ↓              ↓              ↓            ↓       ↓         ↓
API Gateway    Token Claims    Operation     Business  Query    Optimized
   Event      Authentication   Object        Logic    Routing   SQL + Params
```

### Key Components

- **lambda_handler.py**: Entry point with optional JWT validation
- **operation.py**: Core data model representing all operations
- **adapters/gateway_adapter.py**: Transforms API Gateway events to Operations
- **services/**: Business logic and transaction management
- **dao/operation_dao.py**: Routes operations to appropriate SQL handlers
- **dao/batch_operation_handler.py**: Orchestrates multi-operation workflows
- **dao/dependency_resolver.py**: Determines execution order for batch operations
- **dao/reference_resolver.py**: Substitutes cross-operation references
- **dao/sql_*_handler.py**: Generate database-specific SQL

## Quick Start

### Installation

```bash
pip install api-foundry-query-engine
```

### Basic Lambda Handler

```python
from api_foundry_query_engine.utils.token_decoder import token_decoder
from api_foundry_query_engine.utils.api_model import set_api_model
import yaml

# Load API specification
with open("/var/task/api_spec.yaml") as f:
    api_spec = yaml.safe_load(f)
    set_api_model(api_spec)

# Optional: Use token_decoder only if no upstream JWT validation
@token_decoder()  # Uses JWKS_HOST, JWT_ISSUER, JWT_ALLOWED_AUDIENCES env vars
def lambda_handler(event, context):
    from api_foundry_query_engine.services import Service
    service = Service()
    return service.process(event)
```

### Environment Configuration

```bash
# Database (Required)
export DB_SECRET_NAME="arn:aws:secretsmanager:us-east-1:123:secret:db-credentials"

# JWT (Optional - only if using token_decoder)
export JWKS_HOST="oauth.company.com"
export JWT_ISSUER="https://oauth.company.com/"
export JWT_ALLOWED_AUDIENCES="api.company.com"

# Application
export LOG_LEVEL="INFO"
```

## Core Concepts

### Operation Model

Operations are the central data structure representing all database interactions:

```python
from api_foundry_query_engine.operation import Operation

operation = Operation(
    entity="album",           # Target schema object
    action="read",           # read, create, update, delete, custom
    query_params={           # Selection criteria
        "artist_id": "1",
        "title": "like::Dark*"
    },
    store_params={},         # Data to store (create/update only)
    metadata_params={        # Processing instructions
        "__sort": "title:asc",
        "__limit": "10"
    },
    claims={                 # JWT claims for authorization
        "sub": "user123",
        "roles": ["user"]
    }
)
```

#### Parameter Types

**Query Parameters** - Used for record selection and filtering:
**Query Parameters** - Used for record selection and filtering:

| Operator | SQL | Example |
|----------|-----|---------|
| `eq::value` | `= value` | `id=eq::123` |
| `ne::value` | `<> value` | `status=ne::inactive` |
| `lt::value` | `< value` | `price=lt::50` |
| `le::value` | `<= value` | `price=le::100` |
| `gt::value` | `> value` | `price=gt::100` |
| `ge::value` | `>= value` | `price=ge::50` |
| `in::val1,val2` | `IN (val1,val2)` | `genre=in::Rock,Pop` |
| `not-in::val1,val2` | `NOT IN (val1,val2)` | `status=not-in::draft,deleted` |
| `between::val1,val2` | `BETWEEN val1 AND val2` | `price=between::10,50` |
| `like::pattern` | `LIKE pattern` | `title=like::Dark*` |

**Store Parameters** - Data to create or update (POST/PUT only):

```python
# POST /album
operation = Operation(
    entity="album",
    action="create",
    store_params={
        "title": "New Album",
        "artist_id": 42,
        "release_date": "2023-10-15"
    }
)
```

**Metadata Parameters** - Processing instructions:

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `__sort` | ORDER BY clause | `title:asc,created_date:desc` |
| `__limit` | LIMIT clause | `10` |
| `__offset` | OFFSET clause | `20` |
| `__properties` | Column selection | `title,artist_id` |
| `__include` | Association loading | `artist,tracks` |

### Authentication & Authorization

#### JWT Token Decoder (Optional)

The token decoder is **optional** - use only when there's no upstream JWT validation.

**When to Use:**
- Direct Lambda invocation without API Gateway JWT authorizer
- Development/testing environments
- Custom authentication flows

**When to Skip:**
- API Gateway JWT Authorizer handles validation upstream
- Lambda Authorizer provides pre-validated claims
- Public endpoints requiring no authentication

```python
# With token decoder
@token_decoder()
def lambda_handler(event, context):
    return service.process(event)

# Without token decoder (API Gateway handles JWT)
def lambda_handler(event, context):
    # Claims already in event['requestContext']['authorizer']
    return service.process(event)
```

#### OAuth Provider Configuration

**Auth0:**
```bash
export JWKS_HOST="your-domain.auth0.com"
export JWT_ISSUER="https://your-domain.auth0.com/"
export JWT_ALLOWED_AUDIENCES="your-api-identifier"
```

**AWS Cognito:**
```bash
export JWKS_HOST="cognito-idp.us-east-1.amazonaws.com"
export JWT_ISSUER="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXX"
export JWT_ALLOWED_AUDIENCES="your-cognito-app-client-id"
```

### Permission System

The Query Engine implements sophisticated RBAC with field-level and row-level security.

#### Permission Structure

```yaml
x-af-permissions:
  <provider>:          # Token validator name (typically "default")
    <action>:          # read, write, delete
      <role>:          # User role from token claims
        <rule>         # Permission rule (string or object)
```

#### Concise Format (Field-Level Only)

For simple field-level permissions without row filtering:

```yaml
x-af-permissions:
  default:
    read:
      sales_associate: "album_id|title|artist_id"  # Regex pattern
      sales_manager: ".*"                          # All fields
    write:
      sales_associate: "title"
      sales_manager: ".*"
    delete:
      sales_manager: true
```

#### Verbose Format (Row-Level Security)

For advanced permissions with WHERE clause filtering:

```yaml
x-af-permissions:
  default:
    read:
      user:
        properties: "^(id|email|name)$"
        where: "user_id = ${claims.sub}"           # Claim templating
      admin:
        properties: ".*"
    write:
      user:
        properties: "^(email|name)$"
        where: "user_id = ${claims.sub}"
    delete:
      admin:
        allow: true
```

#### Claim Templating

WHERE clauses support dynamic JWT claim substitution:

```yaml
# Multi-tenant isolation
where: "tenant_id = ${claims.tenant_id}"

# Department-based access
where: "department = ${claims.department}"

# User-owned records only
where: "owner_id = ${claims.sub}"
```

#### Multi-Level Security

1. **JWT Token Validation**: Signature, expiration, issuer, audience
2. **Role-Based Access Control**: Field and row-level permissions
3. **SQL-Level Enforcement**: WHERE clauses applied to generated queries

## Advanced Features

### Batch Operations

Batch operations enable complex multi-operation workflows with automatic dependency resolution, cross-reference substitution, and transaction management.

#### Overview

A batch operation allows submitting multiple CRUD operations in a single request. The Query Engine:
1. **Analyzes dependencies** between operations using topological sort
2. **Executes in order** respecting dependencies
3. **Substitutes references** from completed operations into pending ones
4. **Manages transactions** - all operations succeed or all fail
5. **Returns results** for all operations

#### Use Cases

- **Bulk inserts with dependencies**: Create parent and child records in one request
- **Complex workflows**: Multi-step data transformations
- **Transactional updates**: Ensure related records are updated atomically
- **Performance optimization**: Reduce network round-trips

#### Batch Request Format

```json
{
  "operations": [
    {
      "id": "create_artist",
      "entity": "artist",
      "action": "create",
      "store_params": {
        "name": "New Artist"
      }
    },
    {
      "id": "create_album",
      "entity": "album",
      "action": "create",
      "store_params": {
        "title": "New Album",
        "artist_id": "$ref:create_artist.artist_id"
      }
    }
  ]
}
```

#### Optional Operation IDs

Operation IDs are **optional** - they're only required when an operation is referenced by another operation:

```json
{
  "operations": [
    {
      "entity": "album",
      "action": "create",
      "store_params": {"title": "Album 1", "artist_id": 1}
    },
    {
      "entity": "album",
      "action": "create",
      "store_params": {"title": "Album 2", "artist_id": 1}
    }
  ]
}
```

Operations without IDs are auto-assigned as `op_0`, `op_1`, etc.

#### Dependency Resolution

The batch handler automatically:
- Detects `$ref:` placeholders in operation parameters
- Builds a dependency graph
- Uses Kahn's algorithm for topological sorting
- Detects circular dependencies and rejects invalid batches

#### Reference Substitution

Reference syntax: `$ref:operation_id.property.path`

```json
{
  "operations": [
    {
      "id": "op1",
      "entity": "customer",
      "action": "create",
      "store_params": {"name": "John Doe", "email": "john@example.com"}
    },
    {
      "entity": "invoice",
      "action": "create",
      "store_params": {
        "customer_id": "$ref:op1.customer_id",
        "total": "$ref:op1.customer_id"  // Can reuse same reference
      }
    }
  ]
}
```

**Nested property access:**
```json
"customer_email": "$ref:op1.customer.email"
"first_track_id": "$ref:op2.tracks[0].track_id"
```

#### Complete Example: Album with Tracks

```json
POST /batch

{
  "operations": [
    {
      "id": "new_artist",
      "entity": "artist",
      "action": "create",
      "store_params": {
        "name": "The Beatles"
      }
    },
    {
      "id": "new_album",
      "entity": "album",
      "action": "create",
      "store_params": {
        "title": "Abbey Road",
        "artist_id": "$ref:new_artist.artist_id"
      }
    },
    {
      "entity": "track",
      "action": "create",
      "store_params": {
        "name": "Come Together",
        "album_id": "$ref:new_album.album_id",
        "composer": "Lennon-McCartney"
      }
    },
    {
      "entity": "track",
      "action": "create",
      "store_params": {
        "name": "Something",
        "album_id": "$ref:new_album.album_id",
        "composer": "Harrison"
      }
    }
  ]
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "new_artist",
      "status": "success",
      "data": {"artist_id": 42, "name": "The Beatles"}
    },
    {
      "id": "new_album",
      "status": "success",
      "data": {"album_id": 100, "title": "Abbey Road", "artist_id": 42}
    },
    {
      "id": "op_2",
      "status": "success",
      "data": {"track_id": 500, "name": "Come Together", "album_id": 100}
    },
    {
      "id": "op_3",
      "status": "success",
      "data": {"track_id": 501, "name": "Something", "album_id": 100}
    }
  ]
}
```

#### Error Handling

If any operation fails, the entire batch is rolled back:

```json
{
  "error": "Batch operation failed",
  "failed_operation": "new_album",
  "message": "Foreign key constraint violation",
  "results": []
}
```

#### Enabling Batch Operations

Batch operations are enabled in the API Foundry deployment:

```python
from api_foundry import APIFoundry

api_foundry = APIFoundry(
    "my-api",
    api_spec="./api_spec.yaml",
    batch_path="/batch",  # Enables batch endpoint at POST /batch
    secrets=json.dumps({"db": "secret_arn"})
)
```

### Association Loading

The Query Engine can automatically load related objects via 1:1 and 1:many relationships.

#### Parent Properties (1:1)

Loaded via INNER JOIN:

```yaml
invoice:
  type: object
  properties:
    customer_id:
      type: integer
    customer:
      $ref: '#/components/schemas/customer'
      x-af-parent-property: customer_id  # Join key
```

Request:
```
GET /invoice/123?__include=customer
```

Response includes nested customer object.

#### Child Properties (1:many)

Loaded via subselect:

```yaml
customer:
  type: object
  properties:
    invoices:
      type: array
      x-af-child-property: customer_id  # Foreign key in invoice table
      items:
        $ref: '#/components/schemas/invoice'
```

Request:
```
GET /customer/5?__include=invoices
```

Response includes array of invoice objects.

### Metadata Parameters

Customize query behavior and response format:

#### `__properties` - Field Selection

Restrict returned fields using regex patterns:

```
GET /invoice?__properties=invoice_id total customer:.*
```

Returns only `invoice_id`, `total`, and all customer fields.

#### `__sort` - Ordering

Order results by one or more fields:

```
GET /album?__sort=title:asc,release_date:desc
```

Sort by nested properties:
```
GET /invoice?__sort=customer.name:asc
```

#### `__limit` and `__offset` - Pagination

```
GET /album?__limit=20&__offset=40
```

Returns albums 41-60.

#### `__count` - Count Only

```
GET /album?artist_id=5&__count=true
```

Returns: `{"count": 12}`

#### `__include` - Load Associations

```
GET /invoice/123?__include=customer,invoice_line_items
```

Loads invoice with nested customer object and line items array.

## API Specification Integration

### Key Extensions

| Extension | Scope | Purpose | Example |
|-----------|-------|---------|---------|
| `x-af-database` | Schema | Database connection name | `chinook` |
| `x-af-primary-key` | Property | Primary key strategy | `auto`, `manual`, `uuid`, `sequence` |
| `x-af-concurrency-control` | Property | Optimistic locking | `version`, `timestamp` |
| `x-af-permissions` | Schema | Role-based access control | See [Permission System](#permission-system) |
| `x-af-parent-property` | Property | 1:1 relationship join key | `customer_id` |
| `x-af-child-property` | Property | 1:many relationship foreign key | `invoice_id` |

### Schema Example

```yaml
components:
  schemas:
    album:
      type: object
      x-af-database: chinook
      x-af-permissions:
        default:
          read:
            user: "id|title|artist_id"
            admin: ".*"
          write:
            admin: ".*"
          delete:
            admin: true
      properties:
        album_id:
          type: integer
          x-af-primary-key: auto
        title:
          type: string
        artist_id:
          type: integer
        artist:
          $ref: '#/components/schemas/artist'
          x-af-parent-property: artist_id
        tracks:
          type: array
          x-af-child-property: album_id
          items:
            $ref: '#/components/schemas/track'
        updated_at:
          type: string
          format: date-time
          x-af-concurrency-control: version
```

### Custom SQL Operations

Define path operations with custom SQL:

```yaml
paths:
  /reports/top-albums:
    get:
      x-af-database: chinook
      x-af-sql: |
        SELECT a.album_id, a.title, COUNT(il.invoice_line_id) as sold
        FROM album a
        JOIN track t ON a.album_id = t.album_id
        JOIN invoice_line il ON t.track_id = il.track_id
        WHERE il.invoice_date BETWEEN :start AND :end
        GROUP BY a.album_id
        ORDER BY sold DESC
        LIMIT :limit
      parameters:
        - name: start
          in: query
          required: true
          schema:
            type: string
            format: date-time
        - name: end
          in: query
          required: true
          schema:
            type: string
            format: date-time
        - name: limit
          in: query
          schema:
            type: integer
            default: 10
      responses:
        '200':
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  properties:
                    album_id: {type: integer}
                    title: {type: string}
                    sold: {type: integer}
```

## Development & Testing

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/DanRepik/api_foundry_query_engine.git
cd api_foundry_query_engine

# Install dependencies
pip install -e ".[dev]"

# Install test dependencies
pip install pytest pytest-cov fixture-foundry
```

### Running Tests

```bash
# Unit tests only (no database required)
pytest -m unit

# Integration tests (requires Docker for PostgreSQL)
pytest -m integration

# All tests
pytest

# With coverage
pytest --cov=api_foundry_query_engine --cov-report=html
```

### Test Infrastructure

The project uses **fixture_foundry** to automatically provision PostgreSQL containers for integration tests:

```python
# tests/conftest.py
import pytest
from fixture_foundry import PostgresContainer

@pytest.fixture(scope="session")
def chinook_db():
    """Provides a PostgreSQL container with Chinook test data"""
    with PostgresContainer() as postgres:
        # Load test data
        postgres.exec_sql_file("tests/Chinook_Postgres.sql")
        yield postgres
```

### Key Test Fixtures

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `chinook_db` | session | PostgreSQL config dict (dsn, username, password, database, host_port) |
| `chinook_env` | session | Full environment with API spec, secrets, and ConnectionFactory config |
| `chinook_api` | session | API model YAML text from `tests/chinook_api.yaml` |

> **Note**: Integration tests should use `ConnectionFactory(chinook_env)` to get database connections.
> Direct `PostgresConnection(chinook_db)` usage is deprecated - see `test_batch_operations.py` for proper pattern.

### Test Organization

```
tests/
├── conftest.py                          # Shared fixtures (chinook_env, chinook_db, chinook_api)
├── chinook_api.yaml                     # Test API specification
├── Chinook_Postgres.sql                 # Test database DDL/data
├── test_gateway_adapter.py              # Unit tests for adapters
├── test_permissions.py                  # Permission SQL generation tests
├── test_authorization_enforcement.py    # End-to-end permission tests
├── test_association_operations.py       # 1:1 and 1:many loading tests
├── test_batch_operations.py             # Batch workflow integration tests (uses ConnectionFactory)
├── test_dependency_resolver.py          # Topological sort tests
├── test_reference_resolver.py           # Reference substitution tests
└── test_sql_handler.py                  # SQL generation unit/integration tests
```

### Test Fixture Patterns

**Integration tests** should use `ConnectionFactory` with the `chinook_env` fixture:

```python
@pytest.mark.integration
def test_batch_operations(chinook_env):
    """Proper integration test pattern"""
    factory = ConnectionFactory(chinook_env)
    connection = factory.get_connection("chinook")
    try:
        handler = BatchOperationHandler(batch_request, connection, "postgres")
        result = handler.execute()
        # assertions...
    finally:
        connection.close()
```

**Unit tests** should use mocked/fixture data and mark with `@pytest.mark.unit`:

```python
@pytest.mark.unit
def test_sql_generation():
    """Unit test - no database required"""
    schema = load_test_schema()
    handler = SQLSelectSchemaQueryHandler(operation, schema, "postgres")
    sql, params = handler.generate_sql()
    assert "SELECT" in sql
```

### Permission Testing Pattern

Always test both concise and verbose permission formats:

```python
def test_field_level_permissions():
    """Test concise format with regex patterns"""
    operation = Operation(
        entity="album",
        action="read",
        claims={"roles": ["user"]}
    )
    sql, params = handler.generate_sql(operation)
    assert "album_id" in sql
    assert "title" in sql
    assert "internal_notes" not in sql  # Restricted by permissions

def test_row_level_permissions():
    """Test verbose format with WHERE clause"""
    operation = Operation(
        entity="account",
        action="read",
        claims={"sub": "user123", "roles": ["user"]}
    )
    sql, params = handler.generate_sql(operation)
    assert "WHERE id = ?" in sql
    assert params[0] == "user123"
```

## Configuration Reference

### Environment Variables

#### Database Configuration (Required)

```bash
export DB_SECRET_NAME="arn:aws:secretsmanager:region:account:secret:name"
export DB_ENGINE="postgresql"        # Optional: postgresql, mysql, oracle
export DB_SCHEMA="public"            # Optional: database schema name
```

#### JWT Configuration (Optional)

Only required if using `@token_decoder()`:

```bash
export JWKS_HOST="oauth.company.com"
export JWT_ISSUER="https://oauth.company.com/"
export JWT_ALLOWED_AUDIENCES="api.company.com,mobile.company.com"
export JWT_ALGORITHMS="RS256,ES256"   # Optional: comma-separated
export REQUIRE_AUTHENTICATION="true"  # Optional: default true
```

#### Application Settings

```bash
export LOG_LEVEL="INFO"              # DEBUG, INFO, WARN, ERROR
export ENABLE_CORS="true"            # Enable CORS headers
export DEFAULT_PAGE_SIZE="50"        # Default __limit value
```

### Database Secrets Format

AWS Secrets Manager secret should contain:

```json
{
  "engine": "postgres",
  "host": "db.example.com",
  "port": 5432,
  "database": "chinook",
  "username": "app_user",
  "password": "secure_password"
}
```

## Examples & Patterns

### CRUD Operations

**Create:**
```python
Operation(
    entity="album",
    action="create",
    store_params={
        "title": "New Album",
        "artist_id": 42
    }
)
```

**Read with filtering:**
```python
Operation(
    entity="album",
    action="read",
    query_params={"artist_id": "1", "title": "like::Dark*"},
    metadata_params={"__sort": "title:asc", "__limit": "10"}
)
```

**Update with concurrency control:**
```python
Operation(
    entity="album",
    action="update",
    query_params={"album_id": "123"},
    store_params={"title": "Updated Title", "updated_at": "2024-01-15T10:00:00Z"}
)
```

**Delete:**
```python
Operation(
    entity="album",
    action="delete",
    query_params={"album_id": "123"}
)
```

### Batch Operations

**Bulk insert with auto-IDs:**
```json
POST /batch
{
  "operations": [
    {"entity": "album", "action": "create", "store_params": {"title": "Album 1", "artist_id": 1}},
    {"entity": "album", "action": "create", "store_params": {"title": "Album 2", "artist_id": 1}},
    {"entity": "album", "action": "create", "store_params": {"title": "Album 3", "artist_id": 1}}
  ]
}
```

**Complex workflow with references:**
```json
{
  "operations": [
    {
      "id": "new_customer",
      "entity": "customer",
      "action": "create",
      "store_params": {"name": "ACME Corp", "email": "contact@acme.com"}
    },
    {
      "id": "new_invoice",
      "entity": "invoice",
      "action": "create",
      "store_params": {
        "customer_id": "$ref:new_customer.customer_id",
        "total": 0
      }
    },
    {
      "entity": "invoice_line",
      "action": "create",
      "store_params": {
        "invoice_id": "$ref:new_invoice.invoice_id",
        "track_id": 10,
        "quantity": 1,
        "unit_price": 0.99
      }
    },
    {
      "entity": "invoice",
      "action": "update",
      "query_params": {"invoice_id": "$ref:new_invoice.invoice_id"},
      "store_params": {"total": 0.99}
    }
  ]
}
```

### Security Patterns

**Multi-tenant isolation:**
```yaml
x-af-permissions:
  default:
    read:
      user:
        properties: ".*"
        where: "tenant_id = ${claims.tenant_id}"
```

**Department-based access:**
```yaml
x-af-permissions:
  default:
    read:
      manager:
        properties: ".*"
        where: "department = ${claims.department}"
      employee:
        properties: "^(id|name|email)$"
        where: "id = ${claims.sub}"
```

**Self-only with admin override:**
```yaml
x-af-permissions:
  default:
    read:
      user:
        properties: "^(id|email|name)$"
        where: "id = ${claims.sub}"
      admin:
        properties: ".*"
        # No where clause - admin sees all
    write:
      user:
        properties: "^(email|name)$"
        where: "id = ${claims.sub}"
      admin:
        properties: ".*"
```

## Troubleshooting

### Common Errors

#### Permission Denied (402)
#### Permission Denied (402)

**Problem:** "After applying permissions there are no properties returned in response"

**Cause:** The effective `read` rule excludes all properties, or required properties weren't matched by the regex.

**Solution:**
```yaml
# Widen the properties regex
x-af-permissions:
  default:
    read:
      user: ".*"  # Allow all fields
      # Or be more specific
      user: "^(id|name|email|created_at)$"
```

Or use `__properties` metadata parameter to request specific fields:
```
GET /album?__properties=id title
```

#### JWT Validation Failed

**Check configuration:**
```bash
export LOG_LEVEL="DEBUG"
```

**Common issues:**
- Wrong `JWKS_HOST` or `JWT_ISSUER`
- Token expired or invalid signature
- Audience mismatch between token and `JWT_ALLOWED_AUDIENCES`
- Token not in `Authorization: Bearer <token>` header format

#### Empty Results with Row-Level Security

**Problem:** Query returns no rows even though data exists

**Cause:** Claim types don't match database types

```yaml
# claims.sub = "user-123" (string)
# But database owner_id is integer
where: "owner_id = ${claims.sub}"
```

**Solution:** Use appropriate claim or add type handling:
```yaml
# Use numeric claim
where: "owner_id = ${claims.user_id}"

# Or use string comparison
where: "owner_id::text = ${claims.sub}"
```

#### Batch Operation Circular Dependency

**Problem:** "Circular dependency detected in batch operations"

**Cause:** Operations reference each other in a cycle:

```json
{
  "operations": [
    {"id": "op1", "store_params": {"ref": "$ref:op2.id"}},
    {"id": "op2", "store_params": {"ref": "$ref:op1.id"}}
  ]
}
```

**Solution:** Restructure operations to remove circular references. Dependencies must form a directed acyclic graph (DAG).

#### Reference Resolution Error

**Problem:** "Cannot resolve reference $ref:op1.missing_field"

**Cause:** Referenced property doesn't exist in the operation result

**Solution:**
1. Verify the referenced operation returns the expected property
2. Check the property path is correct (use dot notation for nested: `$ref:op1.customer.email`)
3. Ensure referenced operation completed successfully before this operation runs

#### Duplicate Operation ID

**Problem:** "Duplicate operation ID in batch"

**Cause:** Multiple operations have the same `id`:

```json
{
  "operations": [
    {"id": "op1", ...},
    {"id": "op1", ...}  // Duplicate!
  ]
}
```

**Solution:** Ensure each operation that needs an ID has a unique identifier, or omit IDs to use auto-generation.

### Debug Logging

Enable detailed logging to trace execution:

```bash
export LOG_LEVEL="DEBUG"
```

**Debug output includes:**
- Permission patterns matched for each role
- Generated SQL with parameter placeholders
- JWT token validation steps and claim extraction
- Claims populated in event context
- Batch operation execution order
- Reference substitution details
- SQL execution timing

**Example debug log:**
```
DEBUG: Permission pattern for role 'user': ^(id|email|name)$
DEBUG: Generated SQL: SELECT id, email, name FROM account WHERE id = ?
DEBUG: Parameters: ['user123']
DEBUG: Batch execution order: ['create_artist', 'create_album', 'op_2', 'op_3']
DEBUG: Resolved reference $ref:create_artist.artist_id -> 42
```

### Best Practices

1. **Use API Gateway JWT authorizers** when possible instead of token decoder
   - Offloads validation to API Gateway
   - Better performance and caching
   - Centralized token management

2. **Apply principle of least privilege** in permission definitions
   - Start with minimal permissions and expand as needed
   - Use row-level security for multi-tenant applications
   - Test permissions with different user roles

3. **Use row-level security** for multi-tenant applications
   ```yaml
   where: "tenant_id = ${claims.tenant_id}"
   ```

4. **Monitor database connections** to avoid exhausting connection pools
   - Lambda containers reuse connections
   - Set appropriate connection pool limits
   - Monitor CloudWatch metrics

5. **Cache frequently accessed reference data** in Lambda memory
   - API specifications are cached automatically
   - Consider caching lookup tables or configuration

6. **Use parameterized queries** to prevent SQL injection
   - Never concatenate user input into SQL strings
   - All handlers use parameterized queries automatically

7. **Test permissions thoroughly** with different user roles and scenarios
   - Create integration tests for each permission configuration
   - Test both field-level and row-level restrictions
   - Verify claim templating with realistic token payloads

8. **Size batch operations appropriately**
   - Keep batches under 25 operations for optimal performance
   - Break very large imports into multiple batch requests
   - Consider transaction timeout limits (typically 5-30 seconds)

9. **Use optional IDs for simple batches**
   - Omit IDs when operations don't reference each other
   - Cleaner JSON and less boilerplate
   - Auto-generated IDs still available in response

10. **Structure batch dependencies carefully**
    - Ensure references form a DAG (no cycles)
    - Group related operations together
    - Use meaningful operation IDs for debugging

## Performance & Best Practices

### Performance Optimization

**Connection Pooling:**
- Database connections are reused within Lambda container lifetime
- Warm containers significantly reduce latency
- Monitor connection pool exhaustion via CloudWatch

**Schema Caching:**
- API specifications loaded once per Lambda container
- Subsequent requests use cached schema
- Cold start includes schema loading time (~100-500ms)

**SQL Optimization:**
- Parameterized queries enable database query plan caching
- Permission filtering integrated into WHERE clauses (single query)
- Association loading uses JOINs (1:1) or efficient subqueries (1:many)
- Column selection reduces network transfer

**Batch Operations:**
- Single transaction reduces round-trips
- Topological sort executes in optimal order
- Reference resolution happens in-memory (no extra queries)
- Bulk operations faster than individual API calls

### Lambda Configuration Recommendations

```yaml
Runtime: python3.11
Memory: 512 MB  # Increase for large API specs or complex queries
Timeout: 30s    # Increase for batch operations or complex SQL
Environment:
  LOG_LEVEL: INFO
  DB_SECRET_NAME: ...
```

### Monitoring

**Key CloudWatch Metrics:**
- Lambda duration (latency)
- Lambda errors (application failures)
- Lambda throttles (concurrency limits)
- Database connection count
- SQL query duration

**Custom Metrics to Track:**
- Permission denial rate by role
- Batch operation size distribution
- Average operations per batch
- Reference resolution failures

## Architecture Deep Dive

### Request Pipeline Flow

```
1. API Gateway → Lambda Handler
   ↓ @token_decoder() validates JWT (optional)

2. Gateway Adapter
   ↓ Unmarshals event → Operation object
   ↓ Extracts claims from authorizer context

3. Service Layer
   ↓ Business logic validation
   ↓ Transaction management

4. DAO (Operation DAO)
   ↓ Routes to appropriate handler
   ↓ Batch operations → BatchOperationHandler
   ↓ CRUD operations → SQL*QueryHandler

5. SQL Handler
   ↓ Applies permissions (field + row-level)
   ↓ Generates parameterized SQL
   ↓ Executes against database

6. Response Adapter
   ↓ Formats result as JSON
   ↓ Returns to API Gateway
```

### Deferred Import Pattern

**Why BatchOperationHandler uses deferred import:**

In `operation_dao.py`, the batch handler is imported **inside** the `execute()` method rather than at module level:

```python
# operation_dao.py
def execute(self, connector, operation=None):
    if op.entity == "batch" and op.action == "create":
        from api_foundry_query_engine.dao.batch_operation_handler import (
            BatchOperationHandler,
        )
        # Use handler...
```

**Reason:** Prevents circular dependency:
```
operation_dao.py → batch_operation_handler.py → operation_dao.py
```

`BatchOperationHandler` needs `OperationDAO` to execute individual operations within a batch. If `OperationDAO` also imports `BatchOperationHandler` at the top level, Python would encounter a circular import.

**Benefits of deferred import:**
1. **Defensive programming** - Avoids fragile circular dependencies
2. **Clear intent** - Makes the circular relationship explicit
3. **Performance** - Only loads batch handler when needed (not for CRUD operations)
4. **Best practice** - Standard Python pattern for circular dependencies

**Alternative solutions considered:**
- ❌ Top-level import: Works in Python but fragile
- ❌ Dependency injection: More complex, unnecessary
- ❌ Separate module: More files, batch is logically part of DAO
- ✅ **Deferred import: Safe, clear, standard**

### SQL Handler Interface

All SQL handlers implement this interface:

```python
class SQLQueryHandler:
    def generate_sql(self, operation: Operation) -> tuple[str, list]:
        """
        Generate SQL query and parameters.

        Returns:
            tuple: (sql_string, parameters_list)
        """
        pass

    def get_permission_patterns(self, operation: Operation, action: str):
        """Get permission regex patterns for role/action"""
        pass
```

**Handler Selection Logic:**

```python
# In operation_dao.py
if operation.entity == "batch":
    handler = BatchOperationHandler()
elif operation.action == "read":
    handler = SQLSelectQueryHandler()
elif operation.action == "create":
    handler = SQLInsertQueryHandler()
elif operation.action == "update":
    handler = SQLUpdateQueryHandler()
elif operation.action == "delete":
    handler = SQLDeleteQueryHandler()
elif operation.action == "custom":
    handler = SQLCustomQueryHandler()
```

## API Reference

### Operation Class

```python
@dataclass
class Operation:
    entity: str              # Schema object name or "batch"
    action: str              # read, create, update, delete, custom
    query_params: dict       # Selection criteria
    store_params: dict       # Data to store
    metadata_params: dict    # Processing instructions
    claims: dict            # JWT claims
    custom_sql: str         # Optional custom SQL
    database: str           # Database connection name
```

### Common Exceptions

```python
ApplicationException(status_code, message)
# Base exception for user-facing errors

PermissionDenied(message)
# Raised when permission check fails (status 402)

ValidationError(message)
# Raised for invalid input data (status 400)

NotFound(message)
# Raised when resource not found (status 404)

ConcurrencyError(message)
# Raised when optimistic locking fails (status 409)

BatchOperationError(message, failed_operation, details)
# Raised when batch operation fails (status 400)
```

### Key Utility Functions

```python
# utils/api_model.py
def set_api_model(spec: dict) -> None:
    """Set the active API specification"""

def get_schema_object(name: str) -> dict:
    """Get schema object definition by name"""

# utils/logger.py
def get_logger(name: str) -> logging.Logger:
    """Get configured logger for module"""

# connectors/connection_factory.py
def create_connector(database: str) -> DatabaseConnector:
    """Create database connector from secrets"""
```

## Migration & Upgrade Guide

### Upgrading to Batch Operations

**Before (multiple API calls):**
```python
# Client code
artist = post("/artist", {"name": "The Beatles"})
album = post("/album", {"title": "Abbey Road", "artist_id": artist["artist_id"]})
track = post("/track", {"name": "Come Together", "album_id": album["album_id"]})
```

**After (single batch call):**
```python
batch = post("/batch", {
    "operations": [
        {"id": "a", "entity": "artist", "action": "create",
         "store_params": {"name": "The Beatles"}},
        {"id": "b", "entity": "album", "action": "create",
         "store_params": {"title": "Abbey Road", "artist_id": "$ref:a.artist_id"}},
        {"entity": "track", "action": "create",
         "store_params": {"name": "Come Together", "album_id": "$ref:b.album_id"}}
    ]
})
```

**Benefits:**
- ✅ Single network round-trip
- ✅ Atomic transaction (all or nothing)
- ✅ Automatic dependency ordering
- ✅ Simpler error handling

### Migrating Permission Format

**Legacy format (still supported):**
```yaml
x-af-permissions:
  sales_reader:
    read: "^(id|name)$"
  sales_manager:
    create: ".*"
    update: ".*"
    delete: true
```

**New provider-first format (recommended):**
```yaml
x-af-permissions:
  default:
    read:
      sales_reader: "^(id|name)$"
    write:  # create and update normalized to write
      sales_manager: ".*"
    delete:
      sales_manager: true
```

**With row-level security (verbose format):**
```yaml
x-af-permissions:
  default:
    read:
      sales_reader:
        properties: "^(id|name)$"
        where: "region = ${claims.region}"
    write:
      sales_manager:
        properties: ".*"
        where: "region = ${claims.region}"
```

### Breaking Changes

**Version 2.0:**
- Permission action names: `create` and `update` normalized to `write`
- Batch operations require explicit enabling via `batch_path` parameter
- Token decoder now pass-through when `jwks_url` not configured

**Version 1.5:**
- Association loading changed from `__expand` to `__include`
- Metadata parameter prefix changed from `-` to `__`

## Contributing & Resources

### Development Setup

```bash
# Clone and install
git clone https://github.com/DanRepik/api_foundry_query_engine.git
cd api_foundry_query_engine
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Format code
black . && isort .
```

### Code Style Guidelines

- **Python**: Follow PEP 8, use Black formatter
- **Line length**: 88 characters (Black default)
- **Imports**: Organized with isort
- **Type hints**: Use where it improves clarity
- **Docstrings**: Google style for public APIs

### Running CI Locally

```bash
# Type checking
mypy api_foundry_query_engine

# Linting
flake8 api_foundry_query_engine

# Security scanning
bandit -r api_foundry_query_engine

# All checks
pre-commit run --all-files
```

### Related Projects

- **[API Foundry](https://github.com/DanRepik/api_foundry)**: Main IaC framework for deploying APIs
- **[fixture_foundry](https://github.com/DanRepik/fixture_foundry)**: Docker-based test fixtures for databases
- **[cloud_foundry](https://github.com/DanRepik/cloud_foundry)**: Companion project for cloud-native deployment

### Documentation

- **[Batch Operations Guide](./docs/batch_operations.md)**: Complete batch operations reference
- **[Claims Check Decorator](./docs/claims_check_decorator.md)**: Authorization decorator details
- **[Gateway Operation Decorator](./docs/gateway_operation_decorator.md)**: Event transformation details

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Support

- **Issues**: [GitHub Issues](https://github.com/DanRepik/api_foundry_query_engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DanRepik/api_foundry_query_engine/discussions)
- **Email**: [support@apifoundry.io](mailto:support@apifoundry.io)

---

**API Foundry Query Engine** - Building secure, scalable database APIs with zero boilerplate.

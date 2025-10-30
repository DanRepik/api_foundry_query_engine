# API Foundry Query Engine

The **API Foundry Query Engine** is a serverless runtime engine that powers API Foundry's REST APIs. It runs as an AWS Lambda function behind API Gateway, transforming HTTP requests into secure, optimized database operations based on OpenAPI specifications with custom `x-af-*` extensions.

## Key Features

- **Specification-Driven**: Auto-generates CRUD operations from OpenAPI schemas with `x-af-database` extensions
- **Advanced Security**: Multi-level authorization with JWT validation, RBAC, and SQL-level permission enforcement
- **Sophisticated RBAC**: Field-level and row-level permissions with claim templating for multi-tenant scenarios
- **SQL Generation**: Dynamic, optimized SQL creation with parameterized queries and permission filtering
- **Multi-Database Support**: PostgreSQL, MySQL, and Oracle compatibility
- **Association Handling**: Automatic loading of related objects via `x-af-parent-property` and `x-af-child-property`

## Architecture

```
HTTP Request → JWT Decoder → Gateway Adapter → Services → DAO → SQL Handlers → Database
     ↓              ↓              ↓            ↓       ↓         ↓
API Gateway    Token Claims    Operation     Business  Query    Optimized
   Event      Authentication   Object        Logic    Routing   SQL + Params
```

## Quick Start

```python
from api_foundry_query_engine.utils.token_decoder import token_decoder

@token_decoder(require_authentication=False)  # Optional - use when no upstream JWT validation
def lambda_handler(event, context):
    return query_engine.process(event)
```

## Installation & Setup

### Prerequisites

- Python >= 3.9
- AWS Lambda environment (for deployment)
- Compatible database (PostgreSQL, MySQL, or Oracle)

### Installation

```bash
pip install api-foundry-query-engine
```

### Basic Configuration

```python
# Environment variables
export DB_SECRET_NAME="arn:aws:secretsmanager:us-east-1:123:secret:db-credentials"
export JWKS_HOST="oauth.company.com"  # Optional - only if using JWT decoder
export JWT_ISSUER="https://oauth.company.com/"
export JWT_ALLOWED_AUDIENCES="api.company.com"
```

## API Specification Handling

The Query Engine is driven by OpenAPI specifications enhanced with custom `x-af-*` extensions.

### Specification Loading

**Primary Method - Deployment Package:**
```python
# Specification embedded in Lambda deployment package
api_model = APIModel(yaml.safe_load(open("/var/task/api_spec.yaml")))
```

**Alternative - Environment Variable:**
```bash
export API_SPEC='{"openapi": "3.1.0", "components": {"schemas": {...}}}'
```

### Key Extensions

| Extension | Purpose | Example |
|-----------|---------|---------|
| `x-af-database` | Database connection name (schema-level) | `chinook` |
| `x-af-primary-key` | Primary key strategy (property-level) | `auto`, `manual`, `uuid` |
| `x-af-concurrency-control` | Optimistic locking field (property-level) | `version`, `timestamp` |
| `x-af-permissions` | Role-based access control (schema-level) | See permissions section |

### Schema Object Structure

```yaml
components:
  schemas:
    album:
      type: object
      x-af-database: chinook              # Schema-level: database connection
      x-af-permissions:                   # Schema-level: access control
        default:
          read:
            user: "id|title|artist_id"
            admin: ".*"
      properties:
        album_id:
          type: integer
          x-af-primary-key: auto          # Property-level: primary key strategy
        title:
          type: string
        artist_id:
          type: integer
        updated_at:
          type: string
          format: date-time
          x-af-concurrency-control: version  # Property-level: optimistic locking
```

### Relationship Definitions

Parent-child relationships are defined within the OpenAPI specification as properties with special `x-af-*` attributes:

```yaml
# OpenAPI schema definitions with relationship properties
components:
  schemas:
    customer:
      type: object
      x-af-database: chinook
      properties:
        customer_id:
          type: integer
          x-af-primary-key: auto
        invoices:                        # Child relationship property
          description: A list of the customers invoices
          type: array
          x-af-child-property: customer_id
          items:
            $ref: '#/components/schemas/invoice'

    invoice:
      type: object
      x-af-database: chinook
      properties:
        invoice_id:
          type: integer
          x-af-primary-key: auto
        customer_id:
          type: integer
        customer:                        # Parent relationship property
          description: The customer for this invoice
          x-af-parent-property: customer_id
          $ref: '#/components/schemas/customer'
```

## Authentication & Authorization

### JWT Token Decoder (Optional)

The token decoder is **optional** - use only when there's no upstream JWT validation. If no `jwks_url` is configured (either directly or via `JWKS_HOST` environment variable), the decoder does nothing and processing continues normally.

#### When to Use Token Decoder:
- Direct Lambda invocation without API Gateway JWT authorizer
- Development/testing environments
- Custom authentication flows

#### When to Skip:
- API Gateway JWT Authorizer handles validation upstream
- Lambda Authorizer provides pre-validated claims
- Public endpoints requiring no authentication
- No `jwks_url` configured (decoder becomes pass-through)

```python
# With token decoder - explicit configuration
@token_decoder(
    jwks_url="https://oauth.company.com/.well-known/jwks.json",
    audience="api.company.com",
    issuer="https://oauth.company.com/"
)
def handler(event, context):
    return query_engine.process(event)

# With token decoder - environment variable configuration
@token_decoder()  # Uses JWKS_HOST, JWT_ISSUER, JWT_ALLOWED_AUDIENCES env vars
def handler_with_env_config(event, context):
    return query_engine.process(event)

# Without token decoder (API Gateway handles JWT)
def handler(event, context):
    # Claims already in event['requestContext']['authorizer']
    return query_engine.process(event)
```

### Permission System

The Query Engine implements sophisticated RBAC with field-level and row-level security.

#### Permission Formats

**Concise Format (Field-Level Only):**
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

**Verbose Format (Row-Level Security):**
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
```

#### Claim Templating

WHERE clauses support dynamic JWT claim substitution:

```yaml
# Multi-tenant isolation
where: "tenant_id = ${claims.tenant_id}"

# Department-based access
where: "department = ${claims.department}"

# Complex conditions
where: "(owner_id = ${claims.sub}) OR (${claims.roles[0]} = 'admin')"
```

#### Multi-Level Security

1. **JWT Token Validation**: Signature, expiration, issuer, audience
2. **Scope/Permission Checking**: OAuth scopes and fine-grained permissions
3. **SQL-Level Enforcement**: Field filtering and row-level WHERE clauses

## Operation Model & SQL Generation

### Operation Structure

Operations contain these key components:
- **Entity**: Target schema object (e.g., "album")
- **Action**: CRUD action ("read", "create", "update", "delete")
- **Query Parameters**: Selection/filtering criteria
- **Store Parameters**: Data to store/update
- **Metadata Parameters**: Processing instructions (__sort, __limit, etc.)
- **Claims**: JWT claims and user context

### Parameter Types

#### Query Parameters
```python
# GET /album?artist_id=1&title=like::Dark*&__sort=title:asc
operation = Operation(
    entity="album",
    action="read",
    query_params={"artist_id": "1", "title": "like::Dark*"},
    metadata_params={"__sort": "title:asc", "__limit": "10"}
)
```

#### Query Operators
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
| `not-between::val1,val2` | `NOT BETWEEN val1 AND val2` | `price=not-between::10,50` |

**Note**: NULL values are handled automatically by the system. When a field is null in the database, equality comparisons will return appropriate results without requiring special null operators.

#### Store Parameters
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

#### Metadata Parameters
| Parameter | Purpose | Example |
|-----------|---------|---------|
| `__sort` | ORDER BY clause | `title:asc,created_date:desc` |
| `__limit` | LIMIT clause | `10` |
| `__offset` | OFFSET clause | `20` |
| `__properties` | Column selection | `title,artist_id` |
| `__include` | Association loading | `artist,tracks` |

### SQL Generation Process

1. **Handler Selection**: Routes to appropriate SQL handler based on action/entity
2. **Permission Filtering**: Applies field-level and row-level security
3. **Query Building**: Generates parameterized SQL with proper JOINs
4. **Parameter Binding**: Safely substitutes parameters to prevent SQL injection

## Configuration Reference

### Environment Variables

#### Database Configuration
```bash
# Required
export DB_SECRET_NAME="arn:aws:secretsmanager:region:account:secret:name"

# Optional
export DB_ENGINE="postgresql"        # postgresql, mysql, oracle
export DB_SCHEMA="public"           # Database schema name
```

#### JWT Configuration (Optional - only if using token decoder)
```bash
# Required for JWT validation
export JWKS_HOST="oauth.company.com"
export JWT_ISSUER="https://oauth.company.com/"
export JWT_ALLOWED_AUDIENCES="api.company.com,mobile.company.com"

# Optional
export REQUIRE_AUTHENTICATION="true"  # Set to false for development
export JWT_ALGORITHMS="RS256,ES256"   # Comma-separated
```

#### Application Settings
```bash
export LOG_LEVEL="INFO"              # DEBUG, INFO, WARN, ERROR
export ENABLE_CORS="true"            # Enable CORS headers
export DEFAULT_PAGE_SIZE="50"        # Default limit for queries
```

### OAuth Provider Examples

#### Auth0
```bash
export JWKS_HOST="your-domain.auth0.com"
export JWT_ISSUER="https://your-domain.auth0.com/"
export JWT_ALLOWED_AUDIENCES="your-api-identifier"
```

#### AWS Cognito
```bash
export JWKS_HOST="cognito-idp.us-east-1.amazonaws.com"
export JWT_ISSUER="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_XXXXXXXXX"
export JWT_ALLOWED_AUDIENCES="your-cognito-app-client-id"
```

#### Custom OAuth Server
```bash
export JWKS_HOST="oauth.company.com"
export JWT_ISSUER="https://oauth.company.com/"
export JWT_ALLOWED_AUDIENCES="api.company.com"
```

### Performance Considerations

- **Connection Pooling**: Reuses database connections within Lambda containers
- **Schema Caching**: API specifications cached in Lambda memory
- **Parameterized Queries**: Prevents SQL injection and enables query plan caching
- **Column Selection**: Only selects authorized fields to reduce network traffic

## Examples & Troubleshooting

### CRUD Operations

```python
# Create
Operation(entity="album", action="create", store_params={
    "title": "New Album", "artist_id": 42
})

# Read (with filtering and sorting)
Operation(entity="album", action="read",
    query_params={"artist_id": "1"},
    metadata_params={"__sort": "title:asc", "__limit": "10"})

# Update
Operation(entity="album", action="update",
    query_params={"album_id": "123"},
    store_params={"title": "Updated Title"})

# Delete
Operation(entity="album", action="delete",
    query_params={"album_id": "123"})
```

### Common Errors & Solutions

#### Permission Denied
```yaml
# Problem: User role has no read permissions
x-af-permissions:
  default:
    write:
      user: ".*"    # Can write but not read

# Solution: Add read permissions
x-af-permissions:
  default:
    read:
      user: "id|name|email"
    write:
      user: ".*"
```

#### JWT Validation Failed
```bash
# Check configuration
export LOG_LEVEL="DEBUG"

# Common issues:
# - Wrong JWKS_HOST or JWT_ISSUER
# - Token expired or invalid signature
# - Audience mismatch
```

#### Empty Results with Row-Level Security
```yaml
# Problem: Claim types don't match database types
where: "owner_id = ${claims.sub}"  # claims.sub = "user-123" (string)
# But database owner_id is integer

# Solution: Use appropriate claim or cast
where: "owner_id = ${claims.user_id}"  # Use numeric claim
```

### Debug Logging

```bash
export LOG_LEVEL="DEBUG"

# Produces logs showing:
# - Permission patterns matched
# - Generated SQL with parameters
# - JWT token validation steps
# - Claims populated in event context
```

### Best Practices

1. **Use API Gateway JWT authorizers** when possible instead of token decoder
2. **Apply principle of least privilege** in permission definitions
3. **Use row-level security** for multi-tenant applications
4. **Monitor database connections** to avoid exhausting connection pools
5. **Cache frequently accessed reference data** in Lambda memory
6. **Use parameterized queries** to prevent SQL injection
7. **Test permissions thoroughly** with different user roles and scenarios

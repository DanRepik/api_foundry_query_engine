# AI Coding Agent Instructions for API Foundry Query Engine

The Query Engine is the AWS Lambda runtime that powers API Foundry's REST APIs. It transforms API Gateway events into structured Operations, enforces role-based permissions, and executes optimized SQL against relational databases.

## Core Architecture & Data Flow

**Request Pipeline**: API Gateway Event → JWT Decoder → Gateway Adapter → Services → DAO → SQL Handlers → Database

### Key Components
- **Entry Point**: `lambda_handler.py` - Uses `@token_decoder()` decorator for JWT validation
- **Operation Model**: `operation.py` - Central data structure with entity, action, query/store params, roles, and claims
- **Adapters**: Transform data between layers
  - `GatewayAdapter`: API Gateway events ↔ Operations (extracts roles from JWT claims)
  - `CaseChangeAdapter`: Field name normalization (snake_case ↔ camelCase)
- **Services**: Business logic pipeline (`Service`, `TransactionalService`)
- **DAO Layer**: `OperationDAO` routes to specialized SQL handlers by action type
- **SQL Handlers**: Generate database-specific SQL and parameters
  - `sql_select_query_handler.py`: SELECT with permissions filtering, joins, associations
  - `sql_insert_query_handler.py`: INSERT with validation and concurrency control
  - `sql_update_query_handler.py`: UPDATE with optimistic locking via version fields
  - `sql_delete_query_handler.py`: DELETE with permission checks
  - `sql_custom_query_handler.py`: Custom SQL execution for complex operations

### JWT Integration Pattern
- Lambda handler uses `@token_decoder()` (with parentheses) to validate JWTs from `Authorization: Bearer` headers
- JWT claims accessible via `event['requestContext']['authorizer']` following API Gateway TOKEN authorizer pattern
- Claims include: `sub` (subject), `roles` (array), `scope`, `permissions`, custom tenant claims
- Configuration via environment variables: `JWKS_HOST`, `JWT_ISSUER`, `JWT_ALLOWED_AUDIENCES`

## Permissions System (Sophisticated RBAC)

**Structure**: `x-af-permissions` → provider → action → role → rule

### Two Permission Formats

**Concise Format** (field-level only):
```yaml
x-af-permissions:
  default:
    read:
      sales_associate: "album_id|title"  # Regex for allowed columns
      sales_manager: ".*"                # All columns
    write:
      sales_associate: "title"           # Limited write access
    delete:
      sales_manager: true                # Boolean permission
```

**Verbose Format** (with row-level security):
```yaml
x-af-permissions:
  default:
    read:
      user:
        properties: "^(id|email|name)$"
        where: "user_id = ${claims.sub}"  # JWT claim templating
      admin:
        properties: ".*"
    delete:
      admin: {allow: true}
```

### Claim Templating
- `${claims.sub}`: JWT subject (user ID)
- `${claims.tenant}`: Multi-tenant isolation
- `${claims.department}`: Department-based filtering
- Template substitution happens in SQL WHERE clauses for row-level security

## Development Workflow

### Essential Commands
```bash
# Unit tests (no database)
pytest -q -m unit

# Integration tests (real PostgreSQL via fixture_foundry)
pytest -q -m integration

# All tests
pytest -q

# Coverage report
pytest --cov=api_foundry_query_engine --cov-report=html

# Code formatting
black . && isort .
```

### Test Infrastructure
- **Database Tests**: Use `fixture_foundry` to auto-provision PostgreSQL containers
- **Test Data**: Chinook sample database loaded via `tests/Chinook_Postgres.sql`
- **Fixtures**: `chinook_db` (database), `chinook_api` (API model) in `tests/conftest.py`
- **Test Markers**: `@pytest.mark.unit` (no DB), `@pytest.mark.integration` (with DB)

### Permission Test Patterns (Critical for Security)
- `tests/test_permissions.py`: SQL generation for different role/permission combinations
- `tests/test_authorization_enforcement.py`: End-to-end permission enforcement
- Always test both concise (`"column|pattern"`) and verbose (`{properties: "regex", where: "condition"}`) formats
- Verify claim templating with different JWT payloads

## Code Patterns & Conventions

### Operation Construction
```python
operation = Operation(
    entity="album",
    action="read",  # read, create, update, delete
    query_params={"artist_id": "1"},
    metadata_params={"__sort": "title:asc", "__limit": "10"},
    claims={"sub": "user123", "roles": ["sales_associate"]}
)
```

### SQL Handler Extension
- Inherit from `SQLQueryHandler` base class
- Implement `generate_sql()` returning `(sql_string, parameters_list)`
- Use parameterized queries to prevent SQL injection
- Access permissions via `self.get_permission_patterns(operation, action)`

### Error Handling
- Raise `ApplicationException` for user-facing validation errors (400-level)
- Use structured logging via `utils/logger.py`
- Database errors bubble up as 500-level responses

### API Model Integration
- `utils/api_model.py` provides active schema via `set_api_model()` and `get_schema_object()`
- Schema objects define table mapping, primary keys, relationships, and permissions
- Load from YAML files in tests: `tests/chinook_api.yaml`

## Critical Files to Understand
- `lambda_handler.py`: Entry point with JWT decorator usage pattern
- `operation.py`: Core data model with all possible operation parameters
- `adapters/gateway_adapter.py`: API Gateway event parsing and JWT claims extraction
- `dao/operation_dao.py`: Handler selection logic based on action and entity type
- `dao/sql_select_query_handler.py`: Complex SELECT generation with permission filtering
- `tests/test_permissions.py`: Comprehensive permission scenarios and expected SQL output

## Common Debugging Scenarios
- **JWT Issues**: Check `@token_decoder()` has parentheses, verify environment variables
- **Permission Denials**: Examine role claims in JWT, check permission regex patterns
- **SQL Generation**: Look at handler tests for expected SQL patterns given specific operations
- **Database Integration**: Use `chinook_db` fixture for real database testing

## Build & Deployment Context
- **Build System**: Hatchling (modern Python packaging)
- **Dependencies**: boto3 (AWS), pyyaml (config), pyhumps (case conversion)
- **Package Structure**: Designed for AWS Lambda deployment with minimal cold start overhead
- **Environment**: Expects AWS Secrets Manager for database credentials, S3 for API specs

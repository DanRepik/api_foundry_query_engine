# API Foundry Query Engine

The **API Foundry Query Engine** is the serverless runtime component that powers API Foundry's REST APIs. It runs as an AWS Lambda function and transforms HTTP requests from API Gateway into structured database operations, enforcing permissions and schema validation along the way.

## Overview

The Query Engine serves as the bridge between REST API requests and relational database operations. It parses incoming API Gateway events, applies security rules, generates optimized SQL queries, and returns properly formatted JSON responses.

### Key Features

- **Request Processing**: Transforms API Gateway events into structured `Operation` objects
- **Security Enforcement**: Role-based access control (RBAC) with field-level and row-level permissions
- **SQL Generation**: Dynamic SQL creation for CRUD operations and custom queries
- **Schema Validation**: Type checking and constraint enforcement based on OpenAPI specifications
- **Multi-Database Support**: PostgreSQL, MySQL, and Oracle compatibility
- **Optimistic Concurrency**: Built-in support for version-based record locking
- **Association Handling**: Automatic loading of related objects and collections

## Architecture

```
API Gateway Event → Adapters → Services → DAO → SQL Handlers → Database
                       ↓           ↓        ↓
                   Security    Validation  Query
                   Context     Pipeline    Generation
```

### Core Components

#### Entry Point
- **`lambda_handler.py`**: AWS Lambda entry point and QueryEngine class

#### Data Model
- **`operation.py`**: Central `Operation` class representing parsed requests

#### Adapters
- **`GatewayAdapter`**: Parses API Gateway events and builds `Operation` objects
- **`CaseChangeAdapter`**: Normalizes field naming conventions
- **`SecurityAdapter`**: Reserved for security-oriented transformations

#### Services
- **`Service`**: Main processing pipeline that orchestrates adapters and handlers
- **`TransactionalService`**: Wraps operations in database transactions when needed

#### Data Access Layer (DAO)
- **`OperationDAO`**: Routes operations to appropriate SQL handlers
- **SQL Handlers**: Generate database-specific SQL and parameters
  - `sql_select_query_handler.py`: SELECT operations with filtering and joins
  - `sql_insert_query_handler.py`: INSERT operations with validation
  - `sql_update_query_handler.py`: UPDATE operations with concurrency control
  - `sql_delete_query_handler.py`: DELETE operations with permission checks
  - `sql_custom_query_handler.py`: Custom SQL execution

#### Utilities
- **`api_model.py`**: Active schema and relationship definitions
- **`logger.py`**: Structured logging utilities
- **`app_exception.py`**: Custom exception handling

## Installation

### Prerequisites

- Python >= 3.9
- AWS Lambda environment (for deployment)
- Compatible database (PostgreSQL, MySQL, or Oracle)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/DanRepik/api-foundry-query-engine.git
cd api-foundry-query-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Usage

### Basic Lambda Handler

```python
from api_foundry_query_engine.lambda_handler import QueryEngine

# Configuration from environment variables
config = {
    "db_secret_name": "my-database-secret",
    "api_model": "path/to/openapi-spec.yaml"
}

# Create query engine instance
engine = QueryEngine(config)

# AWS Lambda handler function
def lambda_handler(event, context):
    return engine.handler(event)
```

### Direct Operation Processing

```python
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.service import Service
from api_foundry_query_engine.dao.operation_dao import OperationDAO

# Create operation
operation = Operation(
    entity="album",
    action="read",
    query_params={"artist_id": "1"},
    roles={"sales_associate": ["read"]}
)

# Process operation
service = Service(OperationDAO())
result = service.execute(operation)
```

## Permissions System

The Query Engine implements a sophisticated Role-Based Access Control (RBAC) system supporting both simple field-level permissions and advanced row-level security.

### Permission Structure

```yaml
x-af-permissions:
  <provider>:          # Token validator (typically "default")
    <action>:          # read, write, delete
      <role>:          # User role from JWT claims
        <rule>         # Permission rule
```

### Concise Format

For simple field-level permissions without row filtering:

```yaml
x-af-permissions:
  default:
    read:
      sales_associate: "album_id|title|artist_id"
      sales_manager: ".*"
    write:
      sales_associate: "title"
      sales_manager: ".*"
    delete:
      sales_manager: true
```

### Verbose Format with Row-Level Security

For advanced permissions with WHERE clause filtering:

```yaml
x-af-permissions:
  default:
    read:
      user:
        properties: "^(id|email|name)$"
        where: "user_id = ${claims.sub}"
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

### Claim Templating

WHERE clauses support JWT claim substitution:

- `${claims.sub}`: Subject (user ID)
- `${claims.tenant_id}`: Multi-tenant isolation
- `${claims.department}`: Department-based filtering

## Development

### Running Tests

```bash
# Unit tests only (no database required)
pytest -q -m unit

# Integration tests (requires PostgreSQL)
pytest -q -m integration

# All tests
pytest -q

# With coverage
pytest --cov=api_foundry_query_engine --cov-report=html
```

### Test Database Setup

Integration tests use the Chinook sample database. The `fixture_foundry` package automatically provisions a PostgreSQL container and loads test data.

```python
# Example test
@pytest.mark.integration
def test_album_selection(chinook_db):
    # Test uses real database with Chinook data
    pass
```

### Code Style

```bash
# Format code
black api_foundry_query_engine tests

# Sort imports
isort api_foundry_query_engine tests

# Pre-commit hooks
pre-commit install
```

## Configuration

### Environment Variables

- **`DB_SECRET_NAME`**: AWS Secrets Manager secret containing database credentials
- **`API_MODEL_S3_BUCKET`**: S3 bucket containing OpenAPI specification
- **`API_MODEL_S3_KEY`**: S3 key for OpenAPI specification file
- **`LOG_LEVEL`**: Logging level (DEBUG, INFO, WARNING, ERROR)

### Database Secret Format

```json
{
  "engine": "postgres",
  "host": "localhost",
  "port": 5432,
  "database": "mydb",
  "username": "user",
  "password": "password"
}
```

## API Reference

### Operation Class

The central data structure representing a parsed request:

```python
class Operation:
    entity: str              # Target schema object (e.g., "album")
    action: str              # CRUD action ("create", "read", "update", "delete")
    query_params: dict       # Selection criteria
    store_params: dict       # Data to store/update
    metadata_params: dict    # Processing instructions (__properties, __sort, etc.)
    roles: dict             # User roles and permissions
```

### SQL Handler Interface

All SQL handlers implement a common interface:

```python
class SqlQueryHandler:
    def generate_sql(self, operation: Operation) -> tuple[str, list]:
        """Generate SQL query and parameters"""
        pass

    def execute(self, operation: Operation) -> list[dict]:
        """Execute operation and return results"""
        pass
```

## Examples

### Basic CRUD Operations

```python
# Create album
operation = Operation(
    entity="album",
    action="create",
    store_params={"title": "New Album", "artist_id": 1}
)

# Read albums by artist
operation = Operation(
    entity="album",
    action="read",
    query_params={"artist_id": 1}
)

# Update album with concurrency control
operation = Operation(
    entity="album",
    action="update",
    query_params={"album_id": 1, "version": "2023-10-17T10:00:00Z"},
    store_params={"title": "Updated Title"}
)

# Delete album
operation = Operation(
    entity="album",
    action="delete",
    query_params={"album_id": 1}
)
```

### Advanced Queries

```python
# Select with filtering and sorting
operation = Operation(
    entity="invoice",
    action="read",
    query_params={
        "total": "gt::10.00",  # Greater than $10
        "billing_country": "USA"
    },
    metadata_params={
        "__sort": "invoice_date:desc",
        "__limit": "50",
        "__properties": "invoice_id total billing_.*"
    }
)

# Association loading
operation = Operation(
    entity="invoice",
    action="read",
    query_params={"customer_id": 1},
    metadata_params={
        "__properties": ".* customer:.* invoice_line_items:.*"
    }
)
```

## Error Handling

The Query Engine provides detailed error responses:

```python
try:
    result = service.execute(operation)
except ApplicationException as e:
    # User-facing validation errors
    return {
        "statusCode": 400,
        "body": {"error": str(e)}
    }
except Exception as e:
    # System errors
    return {
        "statusCode": 500,
        "body": {"error": "Internal server error"}
    }
```

Common error scenarios:

- **400 Bad Request**: Invalid query parameters, malformed data
- **401 Unauthorized**: Missing or invalid JWT token
- **403 Forbidden**: Insufficient permissions for operation
- **404 Not Found**: Entity or record not found
- **409 Conflict**: Concurrency control violation
- **422 Unprocessable Entity**: Schema validation failure

## Performance Considerations

### Query Optimization

- **Column Selection**: Only fetch columns allowed by permissions
- **Index Usage**: Generate SQL that leverages database indexes
- **Join Optimization**: Efficient joins for association loading
- **Parameterized Queries**: Prevent SQL injection and enable query plan caching

### Connection Management

- **Connection Pooling**: Reuse database connections across requests
- **Lazy Loading**: Connect to database only when needed
- **Connection Limits**: Respect database connection limits in Lambda

### Caching

- **Schema Caching**: Cache parsed OpenAPI specifications
- **Connection Caching**: Reuse connection objects within Lambda container

## Deployment

### AWS Lambda Package

The Query Engine is designed for serverless deployment:

```bash
# Build deployment package
python -m build

# Upload to AWS Lambda
aws lambda create-function \
  --function-name api-foundry-query-engine \
  --runtime python3.9 \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://dist/api_foundry_query_engine-*.whl
```

### Integration with API Foundry

The Query Engine is typically deployed as part of a complete API Foundry stack:

```python
from api_foundry import APIFoundry

api = APIFoundry(
    "my-api",
    api_spec="./openapi.yaml",
    secrets={"chinook": "arn:aws:secretsmanager:..."}
)
```

## Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run the test suite: `pytest`
5. Commit changes: `git commit -am 'Add new feature'`
6. Push to branch: `git push origin feature/new-feature`
7. Submit a pull request

### Coding Guidelines

- **Test Coverage**: Maintain >90% test coverage
- **Type Hints**: Use type annotations for all public APIs
- **Documentation**: Update docstrings and README for new features
- **Error Handling**: Provide clear error messages for validation failures
- **Performance**: Profile and optimize database queries

### Testing Guidelines

- **Unit Tests**: Mock external dependencies (database, AWS services)
- **Integration Tests**: Use real database with test data
- **Permission Tests**: Verify security rules work correctly
- **Performance Tests**: Validate query execution times

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Related Projects

- **[API Foundry](https://github.com/DanRepik/api-foundry)**: Main project for deploying APIs
- **[Fixture Foundry](https://github.com/DanRepik/fixture-foundry)**: Test infrastructure and database fixtures

## Support

- **Documentation**: [API Foundry Documentation](https://github.com/DanRepik/api-foundry)
- **Issues**: [GitHub Issues](https://github.com/DanRepik/api-foundry-query-engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DanRepik/api-foundry-query-engine/discussions)

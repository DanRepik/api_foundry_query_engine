# Batch Operations - Complete Implementation Guide

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Integration Steps](#integration-steps)
4. [Testing Strategy](#testing-strategy)
5. [Deployment Checklist](#deployment-checklist)
6. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Design

```
┌─────────────────┐
│  API Gateway    │
│   POST /batch   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Lambda Handler                              │
│  @token_decoder() @gateway_operation()                   │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│         TransactionalService                             │
│  - Get database connection                               │
│  - Call OperationDAO.execute()                           │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│           OperationDAO                                   │
│  if entity == "batch":                                   │
│    → BatchOperationHandler                               │
│  else:                                                   │
│    → Standard SQL Handlers                               │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│      BatchOperationHandler                               │
│  ┌──────────────────┐  ┌────────────────────┐           │
│  │ Dependency       │  │ Reference          │           │
│  │ Resolver         │  │ Resolver           │           │
│  └──────────────────┘  └────────────────────┘           │
│                                                           │
│  For each operation in execution order:                  │
│    1. Resolve references                                 │
│    2. Create Operation object                            │
│    3. Execute via OperationDAO                           │
│    4. Store results                                      │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Request → Validate → Resolve Dependencies → Execute Loop → Respond
                                               │
                     ┌─────────────────────────┘
                     │
              ┌──────▼──────┐
              │ For each op │
              └──────┬──────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
  ┌─────▼────┐ ┌────▼─────┐ ┌───▼────┐
  │ Resolve  │ │ Execute  │ │ Store  │
  │  Refs    │ │   DAO    │ │ Result │
  └──────────┘ └──────────┘ └────────┘
```

---

## Component Details

### 1. DependencyResolver

**File**: `api_foundry_query_engine/utils/dependency_resolver.py`

**Responsibilities**:
- Validate operation IDs are unique
- Validate dependencies reference valid operations
- Determine execution order via topological sort
- Detect circular dependencies
- Provide helper queries (independent ops, dependents)

**Algorithm**: Kahn's topological sort
- O(V + E) time complexity
- V = number of operations
- E = number of dependencies

**Error Cases**:
- Duplicate operation IDs → 400 error
- Unknown dependency → 400 error
- Circular dependency → 400 error with cycle path

### 2. ReferenceResolver

**File**: `api_foundry_query_engine/utils/reference_resolver.py`

**Responsibilities**:
- Parse `$ref:op_id.property.path` syntax
- Navigate nested objects and arrays
- Preserve original data types
- Handle string interpolation
- Validate references are resolvable

**Supported Patterns**:
```python
# Full replacement (preserves type)
"$ref:op1.customer_id" → 42 (int)

# Nested navigation
"$ref:op1.address.street" → "123 Main St"

# Array indexing
"$ref:op1.items.0.id" → first item's ID

# String interpolation
"prefix_$ref:op1.id_suffix" → "prefix_42_suffix"

# Multiple refs
"$ref:op1.first $ref:op2.last" → "John Doe"
```

**Error Cases**:
- Referenced operation not found → 400 error
- Referenced operation failed → 400 error
- Property path not found → 400 error with available properties

### 3. BatchOperationHandler

**File**: `api_foundry_query_engine/dao/batch_operation_handler.py`

**Responsibilities**:
- Validate batch request structure
- Coordinate dependency resolution
- Coordinate reference resolution
- Execute operations in order
- Manage transaction lifecycle
- Handle errors and skipping
- Build response structure

**Execution Flow**:
```python
def execute(self):
    # 1. Get execution order
    execution_order = self.resolver.get_execution_order()

    # 2. For each operation
    for op_id in execution_order:
        # 2a. Check if should skip (dependency failed)
        if self._should_skip_operation(op_id):
            mark_as_skipped()
            continue

        # 2b. Resolve references
        resolver = ReferenceResolver(self.results)
        query_params = resolver.resolve_parameters(op.query_params)
        store_params = resolver.resolve_parameters(op.store_params)

        # 2c. Execute operation
        operation = Operation(entity, action, query_params, store_params, ...)
        dao = OperationDAO(operation, engine)
        result = dao.execute(connection)

        # 2d. Store result
        self.results[op_id] = {"status": "completed", "data": result}

    # 3. Commit or rollback
    if atomic and no_failures:
        connection.commit()
    elif atomic and had_failures:
        connection.rollback()

    # 4. Build response
    return {"success": all_succeeded, "results": self.results}
```

---

## Integration Steps

### Step 1: Add Batch Routing to OperationDAO

**File**: `api_foundry_query_engine/dao/operation_dao.py`

**Location**: In `execute()` method, before existing handler selection

```python
def execute(self, connector, operation=None) -> Union[list[dict], dict]:
    """Execute the database operation."""

    op = operation if operation is not None else self.operation

    # NEW: Check if this is a batch operation
    if op.entity == "batch" and op.action == "create":
        from api_foundry_query_engine.dao.batch_operation_handler import (
            BatchOperationHandler,
        )

        # Extract batch request from store_params
        batch_request = op.store_params

        # Execute batch
        handler = BatchOperationHandler(batch_request, connector, self.engine)
        return handler.execute()

    # EXISTING: Continue with standard handler selection
    cursor = connector.cursor()
    result = self.__fetch_record_set(self.query_handler, cursor)
    # ... rest of existing code
```

### Step 2: Create Batch Entity in API Model

**File**: Create new schema or add to existing spec

**Option A**: Add to chinook_api.yaml (for testing)

```yaml
schema_objects:
  batch:
    api_name: batch
    database: chinook  # Any database, doesn't matter
    table_name: batch  # Virtual entity, no actual table
    properties: {}
    primary_key: null
    relations: {}
    permissions: {}
```

**Option B**: Handle dynamically in OperationDAO (recommended)

No schema object needed - just detect entity name and route appropriately.

### Step 3: Update GatewayAdapter

**File**: `api_foundry_query_engine/adapters/gateway_adapter.py`

**Location**: In `unmarshal()` method

```python
def unmarshal(self, event: Dict[str, Any]) -> Operation:
    # ... existing code to extract entity, action, params ...

    # NEW: Handle batch requests
    if entity == "batch" and method == "POST":
        # Batch request body contains the batch definition
        body = event.get("body")
        if body:
            batch_request = json.loads(body)
            return Operation(
                entity="batch",
                action="create",
                store_params=batch_request,  # Entire batch in store_params
                claims=claims,
            )

    # EXISTING: Continue with standard unmarshalling
    # ...
```

### Step 4: Add OpenAPI Specification

**File**: Add to your API spec (or create batch_api.yaml)

```yaml
paths:
  /batch:
    post:
      summary: Execute batch operations
      description: |
        Execute multiple database operations in a single request with
        dependency resolution and transaction management.
      tags:
        - Batch Operations
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BatchRequest'
            examples:
              createInvoiceWithLines:
                summary: Create invoice with line items
                value:
                  operations:
                    - id: create_invoice
                      entity: invoice
                      action: create
                      store_params:
                        customer_id: 5
                        total: 2.97
                    - id: create_line_1
                      entity: invoice_line
                      action: create
                      store_params:
                        invoice_id: $ref:create_invoice.invoice_id
                        track_id: 1
                        unit_price: 0.99
                      depends_on: [create_invoice]
      responses:
        '200':
          description: Batch execution completed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BatchResponse'
        '400':
          description: Invalid batch request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

components:
  schemas:
    BatchRequest:
      type: object
      required: [operations]
      properties:
        operations:
          type: array
          minItems: 1
          maxItems: 100
          items:
            $ref: '#/components/schemas/BatchOperation'
        options:
          type: object
          properties:
            atomic:
              type: boolean
              default: true
              description: All-or-nothing transaction
            continueOnError:
              type: boolean
              default: false
              description: Continue executing after errors

    BatchOperation:
      type: object
      required: [entity, action]
      properties:
        id:
          type: string
          description: |
            Unique operation identifier. Optional unless this operation
            is referenced by other operations via depends_on or $ref.
            If not provided, an ID will be auto-generated as 'op_N'.
          pattern: '^[a-zA-Z0-9_]+$'
        entity:
          type: string
          description: Target entity name
        action:
          type: string
          enum: [create, read, update, delete]
        store_params:
          type: object
          description: Data to create/update
        query_params:
          type: object
          description: Selection criteria
        metadata_params:
          type: object
          description: Metadata like __limit, __sort
        depends_on:
          type: array
          items:
            type: string
          description: IDs of operations that must complete first
        claims:
          type: object
          description: Optional JWT claims override

    BatchResponse:
      type: object
      properties:
        success:
          type: boolean
        results:
          type: object
          additionalProperties:
            $ref: '#/components/schemas/OperationResult'
        failedOperations:
          type: array
          items:
            type: string

    OperationResult:
      type: object
      properties:
        status:
          type: string
          enum: [completed, failed, skipped]
        data:
          type: array
          description: Result records (if completed)
        error:
          type: string
          description: Error message (if failed)
        statusCode:
          type: integer
          description: HTTP status code (if failed)
        reason:
          type: string
          description: Skip reason (if skipped)
```

### Step 5: Deploy to API Gateway

**File**: `api_foundry/iac/gateway_spec.py`

Add batch path to API Gateway configuration (if using automated deployment).

Alternatively, manually add the `/batch` POST endpoint in AWS console.

---

## Testing Strategy

### Unit Testing

**Run unit tests**:
```bash
cd api_foundry_query_engine
pytest -m unit tests/test_dependency_resolver.py -v
pytest -m unit tests/test_reference_resolver.py -v
```

**Coverage**: Both test files achieve >95% code coverage

### Integration Testing

**Prerequisites**:
```bash
# Ensure PostgreSQL is running
docker ps | grep postgres

# Ensure chinook database is loaded
psql -h localhost -U postgres -d chinook -c "\dt"
```

**Run integration tests**:
```bash
# Run all batch operation integration tests
pytest -m integration tests/test_batch_operations.py -v

# Run specific test
pytest tests/test_batch_operations.py::TestBatchOperations::test_create_invoice_with_line_items -v
```

**Test infrastructure**:
- Uses `fixture_foundry` to auto-provision PostgreSQL in Docker
- `chinook_env` fixture provides full environment with ConnectionFactory
- Tests use proper `ConnectionFactory` pattern for database connections
- All batch tests marked with `@pytest.mark.integration`

**Test scenarios covered**:
1. ✅ Create invoice with line items (full workflow)
2. ✅ Mixed read/write operations
3. ✅ Atomic rollback on error
4. ✅ Continue on error (partial success)
5. ✅ Dependency skipping
6. ✅ Circular dependency detection
7. ✅ Reference substitution (`$ref:op_id.field`)
8. ✅ Update operations with references

### Manual Testing

**Step 1**: Start API locally
```bash
# In api_foundry workspace
source dev_helpers.sh
up
```

**Step 2**: Get JWT token
```bash
# Get test token (adjust for your auth setup)
export TOKEN="your_jwt_token_here"
```

**Step 3**: Test batch endpoint
```bash
curl -X POST http://localhost:4566/restapis/{api_id}/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {
        "id": "create_customer",
        "entity": "customer",
        "action": "create",
        "store_params": {
          "first_name": "Test",
          "last_name": "User",
          "email": "test@example.com"
        }
      }
    ]
  }'
```

### Load Testing

**Test batch limits**:
```python
# Generate 100 operation batch
operations = [
    {
        "id": f"op_{i}",
        "entity": "media_type",
        "action": "create",
        "store_params": {"name": f"Type {i}"}
    }
    for i in range(100)
]

# Should succeed
requests.post(url, json={"operations": operations})

# Test 101 operations (should fail)
operations.append({"id": "op_101", "entity": "media_type", "action": "create"})
response = requests.post(url, json={"operations": operations})
assert response.status_code == 400
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] Documentation reviewed
- [ ] OpenAPI spec validated
- [ ] Code reviewed by team
- [ ] Performance tested with realistic batch sizes

### Deployment Steps

1. **Deploy Query Engine Lambda**
   ```bash
   cd api_foundry
   # Build and deploy lambda with new code
   ```

2. **Update API Gateway**
   - Add `/batch` POST endpoint
   - Configure integration with Lambda
   - Set request/response models
   - Configure CORS if needed

3. **Test in Staging**
   ```bash
   # Run integration tests against staging
   export TEST_API_URL=https://staging-api.example.com
   pytest -m integration
   ```

4. **Monitor Deployment**
   - Check CloudWatch logs for errors
   - Monitor Lambda duration/errors
   - Test batch endpoint manually

### Post-Deployment

- [ ] Smoke test in production
- [ ] Monitor error rates
- [ ] Check batch execution duration
- [ ] Verify transaction rollback works
- [ ] Update client SDKs/documentation

---

## Troubleshooting

### Common Issues

#### 1. Circular Dependency Error

**Symptom**:
```json
{
  "status": 400,
  "message": "Circular dependency detected: op_a -> op_b -> op_a"
}
```

**Solution**:
- Review `depends_on` arrays
- Draw dependency graph on paper
- Remove circular references
- Consider splitting into multiple batches

#### 2. Reference Not Found

**Symptom**:
```json
{
  "status": 400,
  "message": "Cannot resolve reference '$ref:op1.customer_id': property not found"
}
```

**Solutions**:
- Check operation ID is correct
- Verify property name exists in result
- Check operation completed successfully
- Review available properties in error message

#### 3. Batch Timeout

**Symptom**: Lambda timeout (30s default)

**Solutions**:
- Reduce batch size
- Remove unnecessary read operations
- Optimize SQL queries
- Increase Lambda timeout (if appropriate)
- Consider async processing for large batches

#### 4. Transaction Rollback Not Working

**Symptom**: Partial data committed despite error

**Solutions**:
- Verify `atomic: true` in options
- Check connection.commit() not called elsewhere
- Ensure database supports transactions
- Check isolation level settings

#### 5. Permission Denied on Nested Operation

**Symptom**: Operation 3 fails with 403 error

**Solutions**:
- Each operation checked independently
- Verify JWT has required scopes for ALL operations
- Check entity-level permissions
- Review row-level security WHERE clauses

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check logs for:
- Execution order determination
- Reference resolution details
- Individual operation execution
- Transaction commit/rollback

### Performance Profiling

```python
import time

class BatchOperationHandler:
    def execute(self):
        start = time.time()

        # ... execution logic ...

        duration = time.time() - start
        log.info(f"Batch completed in {duration:.2f}s")

        # Log per-operation timing
        for op_id, result in self.results.items():
            log.info(f"{op_id}: {result.get('duration', 0):.3f}s")
```

---

## Best Practices

### 1. Batch Size

- **Optimal**: 10-20 operations
- **Maximum**: 100 operations
- **Rationale**: Balance between network overhead and execution time

### 2. Dependency Design

- Keep dependency chains shallow (3-4 levels max)
- Use parallel operations where possible
- Avoid long linear chains

### 3. Error Handling

- Use `atomic: true` for critical workflows
- Use `continueOnError: true` for best-effort scenarios
- Always check `failedOperations` in response

### 4. Naming Conventions

```python
# Good operation IDs
"create_customer"
"update_invoice_total"
"delete_old_records"

# Bad operation IDs
"op1"
"temp"
"x"
```

### 5. Reference Usage

```python
# Prefer simple references
"customer_id": "$ref:create_customer.customer_id"

# Avoid complex string interpolation when possible
"description": "$ref:op1.text $ref:op2.text $ref:op3.text"  # Hard to debug
```

---

## Conclusion

This implementation guide provides everything needed to deploy and operate the Batch Operations feature. The modular design, comprehensive testing, and detailed documentation ensure a robust and maintainable solution.

For questions or issues, refer to:
- `docs/batch_operations.md` - API documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical overview
- Test files - Usage examples

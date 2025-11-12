# Batch Operations API

## Overview

The Batch Operations API allows you to execute multiple database operations in a single request with automatic dependency resolution, reference substitution, and transaction management. This is useful for complex workflows that involve creating or updating multiple related entities.

## Endpoint

```
POST /batch
```

## Request Structure

```json
{
  "operations": [
    {
      "id": "unique_operation_id",  // Optional - auto-generated if omitted
      "entity": "entity_name",      // Required
      "action": "create|read|update|delete",  // Required
      "store_params": { /* data to create/update */ },
      "query_params": { /* selection criteria */ },
      "metadata_params": { /* metadata like __limit, __sort */ },
      "depends_on": ["other_operation_id"],
      "claims": { /* optional JWT claims override */ }
    }
  ],
  "options": {
    "atomic": true,           // All-or-nothing transaction (default: true)
    "continueOnError": false  // Continue executing after errors (default: false)
  }
}
```

### Operation Properties

| Property | Required | Description |
|----------|----------|-------------|
| `id` | No* | Unique identifier for this operation. Auto-generated as `op_N` if not provided. *Required only if referenced by other operations via `depends_on` or `$ref`. |
| `entity` | Yes | Target entity name (e.g., "customer", "invoice") |
| `action` | Yes | CRUD action: `create`, `read`, `update`, or `delete` |
| `store_params` | No | Data to create/update (for create/update actions) |
| `query_params` | No | Selection criteria (for read/update/delete actions) |
| `metadata_params` | No | Metadata like `__limit`, `__sort`, `__properties` |
| `depends_on` | No | Array of operation IDs that must complete first |
| `claims` | No | Optional JWT claims override for this operation |

## Key Features

### 1. Dependency Resolution

Operations can depend on other operations using the `depends_on` array:

```json
{
  "operations": [
    {
      "id": "create_customer",
      "entity": "customer",
      "action": "create",
      "store_params": { "name": "John Doe", "email": "john@example.com" }
    },
    {
      "id": "create_invoice",
      "entity": "invoice",
      "action": "create",
      "store_params": {
        "customer_id": "$ref:create_customer.customer_id",
        "total": 100.00
      },
      "depends_on": ["create_customer"]
    }
  ]
}
```

The batch handler will:
- Automatically determine execution order using topological sort
- Detect circular dependencies and return 400 error
- Skip dependent operations if their dependencies fail

### 2. Reference Substitution

Use `$ref:operation_id.property_path` syntax to reference values from previous operations:

**Simple reference:**
```json
"customer_id": "$ref:create_customer.customer_id"
```

**Nested property:**
```json
"address": "$ref:read_customer.billing_address.street"
```

**Array indexing:**
```json
"first_item_id": "$ref:read_items.items.0.id"
```

**String interpolation:**
```json
"description": "Invoice for customer $ref:create_customer.customer_id"
```

### 3. Transaction Control

#### Atomic Mode (default)
All operations succeed or all rollback:

```json
{
  "options": { "atomic": true }
}
```

- If any operation fails, entire batch is rolled back
- Database is left in original state
- Use for critical workflows where partial completion is unacceptable

#### Non-Atomic Mode
Each operation commits independently:

```json
{
  "options": { "atomic": false }
}
```

- Successful operations are committed even if others fail
- Use with `continueOnError: true` for best-effort scenarios
- Response indicates which operations succeeded/failed

#### Continue on Error

```json
{
  "options": { "continueOnError": true }
}
```

- Batch continues executing after errors
- Failed operations marked as `"status": "failed"`
- Dependent operations skipped if parent fails
- Final response includes `failedOperations` array

## Response Structure

### Success Response

```json
{
  "success": true,
  "results": {
    "create_customer": {
      "status": "completed",
      "data": [{ "customer_id": 42, "name": "John Doe" }]
    },
    "create_invoice": {
      "status": "completed",
      "data": [{ "invoice_id": 100, "customer_id": 42, "total": 100.00 }]
    }
  }
}
```

### Partial Failure Response

```json
{
  "success": false,
  "failedOperations": ["create_invalid"],
  "results": {
    "create_customer": {
      "status": "completed",
      "data": [{ "customer_id": 42 }]
    },
    "create_invalid": {
      "status": "failed",
      "error": "Foreign key constraint violation",
      "statusCode": 400
    },
    "dependent_operation": {
      "status": "skipped",
      "reason": "Dependency failed"
    }
  }
}
```

## Use Cases

### 1. Create Invoice with Line Items

```json
## Use Cases

### 1. Create Parent and Children
Create an invoice with multiple line items in one request:

```json
{
  "operations": [
    {
      "id": "create_invoice",
      "entity": "invoice",
      "action": "create",
      "store_params": {
        "customer_id": 5,
        "invoice_date": "2024-01-01",
        "total": 2.97
      }
    },
    {
      "id": "create_line_1",
      "entity": "invoice_line",
      "action": "create",
      "store_params": {
        "invoice_id": "$ref:create_invoice.invoice_id",
        "track_id": 1,
        "unit_price": 0.99,
        "quantity": 1
      },
      "depends_on": ["create_invoice"]
    },
    {
      "id": "create_line_2",
      "entity": "invoice_line",
      "action": "create",
      "store_params": {
        "invoice_id": "$ref:create_invoice.invoice_id",
        "track_id": 2,
        "unit_price": 0.99,
        "quantity": 2
      },
      "depends_on": ["create_invoice"]
    }
  ],
  "options": { "atomic": true }
}
```

### 2. Bulk Insert (No IDs Needed)
Insert multiple independent records without dependencies:

```json
{
  "operations": [
    {
      "entity": "album",
      "action": "create",
      "store_params": { "title": "Album 1", "artist_id": 1 }
    },
    {
      "entity": "album",
      "action": "create",
      "store_params": { "title": "Album 2", "artist_id": 2 }
    },
    {
      "entity": "album",
      "action": "create",
      "store_params": { "title": "Album 3", "artist_id": 3 }
    }
  ],
  "options": { "atomic": false }
}
```

**Note**: Since these operations don't reference each other, the `id` field is omitted. IDs are auto-generated as `op_0`, `op_1`, `op_2`.

### 3. Mixed Read and Write
```

### 2. Update with Cascading Changes

```json
{
  "operations": [
    {
      "id": "update_customer",
      "entity": "customer",
      "action": "update",
      "query_params": { "customer_id": 5 },
      "store_params": {
        "address": "456 Oak Ave",
        "city": "New York"
      }
    },
    {
      "id": "sync_invoices",
      "entity": "invoice",
      "action": "update",
      "query_params": { "customer_id": 5 },
      "store_params": {
        "billing_address": "$ref:update_customer.address",
        "billing_city": "$ref:update_customer.city"
      },
      "depends_on": ["update_customer"]
    }
  ]
}
```

### 3. Conditional Workflow

```json
{
  "operations": [
    {
      "id": "check_inventory",
      "entity": "inventory",
      "action": "read",
      "query_params": { "product_id": 100 }
    },
    {
      "id": "create_order",
      "entity": "order",
      "action": "create",
      "store_params": {
        "product_id": 100,
        "quantity": "$ref:check_inventory.available_quantity"
      },
      "depends_on": ["check_inventory"]
    }
  ]
}
```

## Limitations and Best Practices

### Limitations

1. **Maximum Batch Size**: 100 operations per request
2. **No Nested Batches**: Cannot include batch operations within batch operations
3. **Linear Dependencies Only**: Complex conditional logic not supported
4. **Same Database**: All operations must target the same database
5. **Synchronous**: Batch executes synchronously (use async for long-running batches)

### Best Practices

1. **Keep Batches Small**: Aim for 10-20 operations for optimal performance
2. **Use Atomic Mode for Critical Workflows**: Ensure data consistency
3. **Explicit Dependencies**: Always specify `depends_on` even if obvious
4. **Descriptive Operation IDs**: Use clear naming like `create_customer` not `op1`
5. **Error Handling**: Check `failedOperations` in response for partial failures
6. **Test Rollback**: Verify atomic rollback behavior in development

## Error Handling

### Common Errors

**Circular Dependency (400)**
```json
{
  "status": 400,
  "message": "Circular dependency detected: op_a -> op_b -> op_a"
}
```

**Unknown Reference (400)**
```json
{
  "status": 400,
  "message": "Reference to unknown operation 'missing_op' in operation 'create_invoice'"
}
```

**Missing Required Field (400)**
```json
{
  "status": 400,
  "message": "Operation 'op1' missing required field 'entity'"
}
```

**Batch Size Exceeded (400)**
```json
{
  "status": 400,
  "message": "Batch size exceeds maximum (100). Requested: 150"
}
```

### Debugging Tips

1. **Check Execution Order**: Review dependency resolution in logs
2. **Validate References**: Ensure referenced properties exist in results
3. **Test Incrementally**: Start with 2 operations, add complexity gradually
4. **Review Logs**: Operation execution logged with detailed context
5. **Use Non-Atomic for Testing**: See which operations succeed/fail independently

## Security

### Permission Checking

Each operation is validated independently:
- Uses standard entity-level permissions
- Row-level security (RLS) applied per operation
- JWT claims from request context used for all operations
- Can override claims per-operation if needed (advanced use case)

### Authentication

Batch endpoint requires same authentication as individual operations:
- JWT token required in `Authorization` header
- Scopes validated per operation
- Failed permission check stops batch execution (if atomic)

## Performance Considerations

### Optimization Tips

1. **Minimize Round-Trips**: Batch reduces network latency vs. N separate requests
2. **Transaction Overhead**: Atomic mode has commit/rollback cost
3. **Dependency Chains**: Long chains may increase execution time
4. **Parallel Execution**: Independent operations (no dependencies) execute sequentially (future: parallel execution possible)

### When NOT to Use Batch

- Single operation (use standard CRUD endpoints)
- Bulk inserts of identical entities (use bulk import tools)
- Operations across multiple databases (use separate requests)
- Long-running workflows (use async/job queue instead)

## Examples

See `tests/test_batch_operations.py` for comprehensive examples including:
- Creating invoices with line items
- Mixed read/write operations
- Error handling and rollback
- Dependency resolution
- Reference substitution patterns

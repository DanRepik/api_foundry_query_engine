# Operation ID Made Optional in Batch Operations

## Summary

The `id` field in batch operations is now **optional**. It's only required when an operation needs to be referenced by other operations via `depends_on` or `$ref` syntax.

## Changes Made

### 1. OpenAPI Schema (`api_foundry/iac/gateway_spec.py`)

**Before:**
```yaml
BatchOperation:
  type: object
  required: [id, entity, action]  # id was required
  properties:
    id:
      type: string
      description: Unique operation identifier
```

**After:**
```yaml
BatchOperation:
  type: object
  required: [entity, action]  # id removed from required
  properties:
    id:
      type: string
      description: |
        Unique operation identifier. Required only if this operation
        is referenced by other operations via depends_on or $ref.
        If not provided, an ID will be auto-generated as 'op_N'.
```

### 2. Runtime Validation (`api_foundry_query_engine/dao/batch_operation_handler.py`)

**Changes:**
- Removed requirement for `id` field
- Auto-generates IDs as `op_0`, `op_1`, `op_2`, etc. when not provided
- Detects duplicate IDs and raises error
- Handles empty string IDs by replacing with auto-generated ones

**Code:**
```python
# Auto-generate IDs for operations that don't have them
seen_ids = set()
for i, op in enumerate(self.operations):
    # Auto-generate ID if not provided
    if "id" not in op or not op["id"]:
        op["id"] = f"op_{i}"

    # Check for duplicate IDs
    if op["id"] in seen_ids:
        raise ApplicationException(
            400,
            f"Duplicate operation ID '{op['id']}' found",
        )
    seen_ids.add(op["id"])
```

## Use Cases

### Simple Batch Insert (No IDs Needed)

When operations don't reference each other, you can omit the `id` field entirely:

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
  ]
}
```

**What happens:**
- Operations auto-assigned IDs: `op_0`, `op_1`, `op_2`
- All operations execute independently
- No manual ID management needed

### With Dependencies (IDs Required)

When operations reference each other, you must provide explicit IDs:

```json
{
  "operations": [
    {
      "id": "create_invoice",  // Required - referenced below
      "entity": "invoice",
      "action": "create",
      "store_params": { "customer_id": 5, "total": 2.97 }
    },
    {
      "id": "create_line",     // Optional, but recommended
      "entity": "invoice_line",
      "action": "create",
      "store_params": {
        "invoice_id": "$ref:create_invoice.invoice_id",  // References above
        "track_id": 1,
        "unit_price": 0.99
      },
      "depends_on": ["create_invoice"]
    }
  ]
}
```

### Mixed: Some with IDs, Some Without

```json
{
  "operations": [
    {
      "id": "read_customer",  // Explicit ID - will be referenced
      "entity": "customer",
      "action": "read",
      "query_params": { "customer_id": 5 }
    },
    {
      // No ID - not referenced (auto-generated as op_1)
      "entity": "album",
      "action": "create",
      "store_params": { "title": "New Album" }
    },
    {
      "id": "create_invoice",  // Explicit ID - will be referenced
      "entity": "invoice",
      "action": "create",
      "store_params": {
        "customer_id": "$ref:read_customer.customer_id",
        "total": 10.00
      },
      "depends_on": ["read_customer"]
    }
  ]
}
```

## Benefits

### 1. Simpler Bulk Operations
For simple batch inserts/updates without dependencies, you no longer need to invent unique IDs:

**Before (verbose):**
```json
{
  "operations": [
    { "id": "insert_1", "entity": "album", "action": "create", "store_params": {...} },
    { "id": "insert_2", "entity": "album", "action": "create", "store_params": {...} },
    { "id": "insert_3", "entity": "album", "action": "create", "store_params": {...} }
  ]
}
```

**After (concise):**
```json
{
  "operations": [
    { "entity": "album", "action": "create", "store_params": {...} },
    { "entity": "album", "action": "create", "store_params": {...} },
    { "entity": "album", "action": "create", "store_params": {...} }
  ]
}
```

### 2. Reduced Cognitive Load
- Don't need to think about IDs unless using dependencies/references
- Auto-generated IDs follow predictable pattern (`op_0`, `op_1`, etc.)
- Less boilerplate in requests

### 3. Backward Compatible
- Existing requests with explicit IDs continue to work
- No breaking changes to API
- Duplicate ID detection prevents accidental collisions

### 4. Clear Intent
- **ID present** = "This operation will be referenced"
- **ID absent** = "This is a standalone operation"

## Testing

All tests pass with the new behavior:

```bash
# OpenAPI schema generation
python test_batch_standalone.py
# ✓ BatchOperation has id (optional), entity, action (required)

# Runtime validation and auto-generation
python test_batch_id_standalone.py
# ✓ Auto-generated IDs: op_0, op_1
# ✓ Explicit IDs preserved: create_album, read_artist
# ✓ Mixed IDs: my_op, op_1, another_op
# ✓ Duplicate ID detected
# ✓ Empty ID replaced with: op_0
# ✓ Three operations without IDs work fine
```

## Documentation Updates

- ✅ `IMPLEMENTATION_GUIDE.md` - Updated BatchOperation schema
- ✅ `batch_operations.md` - Added operation properties table and bulk insert example
- ✅ `test_batch_standalone.py` - Updated test assertions
- ✅ `test_batch_id_optional.py` - New comprehensive test suite

## Files Modified

1. `api_foundry/iac/gateway_spec.py` - OpenAPI schema (3 lines)
2. `api_foundry_query_engine/dao/batch_operation_handler.py` - Auto-ID generation (15 lines)
3. `api_foundry_query_engine/IMPLEMENTATION_GUIDE.md` - Documentation
4. `api_foundry_query_engine/docs/batch_operations.md` - Documentation + examples
5. `tests/test_batch_id_optional.py` - New test suite (178 lines)
6. `test_batch_standalone.py` - Updated assertions

## Migration Guide

### For Existing Code
No changes needed! Existing batch requests with explicit IDs continue to work exactly as before.

### For New Code
**Recommendation:**
- **Use IDs** when operations have dependencies or are referenced via `$ref`
- **Omit IDs** for simple bulk inserts/updates without cross-references

**Example patterns:**
```javascript
// Good: No IDs for independent operations
fetch('/batch', {
  body: JSON.stringify({
    operations: albums.map(album => ({
      entity: 'album',
      action: 'create',
      store_params: album
    }))
  })
})

// Good: IDs for dependent operations
fetch('/batch', {
  body: JSON.stringify({
    operations: [
      { id: 'inv', entity: 'invoice', action: 'create', ... },
      {
        entity: 'invoice_line',
        action: 'create',
        store_params: { invoice_id: '$ref:inv.invoice_id', ... },
        depends_on: ['inv']
      }
    ]
  })
})
```

## Summary

Making the `id` field optional significantly improves the developer experience for simple batch operations while maintaining full power for complex workflows with dependencies. The change is backward compatible, well-tested, and properly documented.

**Key Takeaway:** Only provide `id` when you need it. The system handles the rest automatically.

# Testing Infrastructure Updates

## Summary of Changes

This document summarizes recent updates to the testing infrastructure and documentation.

## Test Suite Fixes (Nov 23, 2025)

### 1. Fixed Test Markers in `test_sql_handler.py`
- **Issue**: 8 tests marked as `@pytest.mark.unit` required database fixtures
- **Fix**: Moved class-level marker to individual methods, added `@pytest.mark.integration` to tests needing `chinook_env`
- **Result**: Unit tests now run without database (91 passing)

### 2. Fixed JWT Token Decoder for Testing
- **File**: `api_foundry_query_engine/utils/token_decoder.py`
- **Issue**: Import-time ValueError when JWKS_HOST not configured
- **Fix**: Allow decorator application without JWKS config for testing
- **Result**: Tests can import modules without full JWT infrastructure

### 3. Fixed API Model Global Singleton
- **File**: `tests/test_schema_objects_fixtures.py`
- **Issue**: `load_api()` created APIModel but didn't set global variable
- **Fix**: Properly set `api_model_module.api_model` global
- **Result**: Schema objects properly loaded in tests

### 4. Fixed PostgresConnection DSN Support
- **File**: `api_foundry_query_engine/connectors/postgres_connection.py`
- **Issue**: `KeyError: 'host'` when using fixture_foundry's DSN-based config
- **Fix**: Check for `dsn` first, fallback to individual host/port parameters
- **Result**: Works with both fixture_foundry (DSN) and production (individual params)

### 5. Fixed Batch Operation Tests
- **File**: `tests/test_batch_operations_old.py`
- **Issue**: Tests passed dict directly to BatchOperationHandler instead of connection object
- **Fix**: Wrap `chinook_db` in `PostgresConnection` before passing to handler
- **Status**: **DEPRECATED** - this file should be removed

## Test Patterns & Best Practices

### ✅ Correct Pattern (Integration Tests)

Use `ConnectionFactory` with `chinook_env`:

```python
@pytest.mark.integration
def test_batch_operations(chinook_env):
    factory = ConnectionFactory(chinook_env)
    connection = factory.get_connection("chinook")
    try:
        handler = BatchOperationHandler(batch_request, connection, "postgres")
        result = handler.execute()
        # assertions...
    finally:
        connection.close()
```

### ❌ Deprecated Pattern

Direct `PostgresConnection` instantiation:

```python
# DON'T DO THIS - deprecated pattern
def test_old_way(chinook_db):
    connection = PostgresConnection(chinook_db)  # Avoid this
    handler = BatchOperationHandler(batch_request, connection, "postgres")
```

### Unit Test Pattern

```python
@pytest.mark.unit
def test_sql_generation():
    """No database required"""
    schema = load_test_schema()
    handler = SQLSelectSchemaQueryHandler(operation, schema, "postgres")
    sql, params = handler.generate_sql()
    assert "SELECT" in sql
```

## Test Fixtures

| Fixture | Type | Purpose | Usage |
|---------|------|---------|-------|
| `chinook_db` | dict | Raw PostgreSQL config from fixture_foundry | Low-level, avoid in new tests |
| `chinook_env` | dict | Full environment with ConnectionFactory config | **Preferred for integration tests** |
| `chinook_api` | str | API model YAML text | Schema loading |

## Files to Remove

### `tests/test_batch_operations_old.py` - DEPRECATED
- Replaced by: `tests/test_batch_operations.py`
- Reason: Uses deprecated direct PostgresConnection pattern
- Action: Safe to delete (marked with deprecation notice)

## Documentation Updated

### Updated Files:
1. `.github/copilot-instructions.md` - Test infrastructure and connection patterns
2. `README.md` - Test fixtures table and integration test patterns
3. `docs/IMPLEMENTATION_GUIDE.md` - Test scenarios and infrastructure
4. `docs/IMPLEMENTATION_SUMMARY.md` - Test counts and patterns
5. `api_foundry_query_engine/connectors/postgres_connection.py` - DSN support docstring

### Key Documentation Changes:
- Added ConnectionFactory as preferred pattern
- Documented DSN vs individual parameter configs
- Added deprecation notices for old patterns
- Updated test counts (7 tests in new file vs 8 in old)
- Added fixture usage guidelines

## Migration Guide

If you have tests using the old pattern:

**Before:**
```python
def test_something(chinook_env, chinook_db):
    connection = PostgresConnection(chinook_db)
    handler = SomeHandler(connection)
```

**After:**
```python
def test_something(chinook_env):
    factory = ConnectionFactory(chinook_env)
    connection = factory.get_connection("chinook")
    try:
        handler = SomeHandler(connection)
        # test code
    finally:
        connection.close()
```

## Test Execution

```bash
# Unit tests only (fast, no database)
pytest -q -m unit

# Integration tests only (requires fixture_foundry)
pytest -q -m integration

# All tests
pytest -q

# Specific test file
pytest tests/test_batch_operations.py -v

# With coverage
pytest --cov=api_foundry_query_engine --cov-report=html
```

## Results

- ✅ 91 unit tests passing
- ✅ 9 soft delete tests passing
- ✅ 7 batch operation integration tests (in new file)
- ✅ All tests properly marked as unit/integration
- ✅ ConnectionFactory pattern standardized
- ✅ PostgresConnection supports both DSN and individual configs

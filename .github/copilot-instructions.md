# AI Coding Agent Instructions for API Foundry Query Engine

The Query Engine is the Lambda-side runtime used by API Foundry. It transforms an API Gateway event into a structured Operation, enforces schema/permissions, and executes SQL against an RDBMS.

## Core Architecture
- Entry point: `api_foundry_query_engine/lambda_handler.py`
- Operation model: `api_foundry_query_engine/operation.py`
- Adapters:
  - `GatewayAdapter` parses API Gateway events and builds an `Operation` (roles/claims from authorizer).
  - `CaseChangeAdapter` normalizes field names.
  - `SecurityAdapter` reserved for security-oriented transformations.
- Services:
  - `Service` pipeline orchestrates adapters and a DAO handler.
  - `TransactionalService` wraps execution in database transactions when needed.
- DAO/SQL Handlers:
  - `OperationDAO` selects a concrete SQL handler based on action.
  - `sql_select_query_handler.py`, `sql_insert_query_handler.py`, `sql_update_query_handler.py`, `sql_custom_query_handler.py` generate SQL and params.
- Utilities:
  - `utils/api_model.py` provides the active model (schema objects and relations).
  - `utils/logger.py` and `utils/app_exception.py` for diagnostics and errors.

## Permissions Model (current tests)
- Simple role → action → fields rules are used in tests:
  - Example (from tests):
    - `sales_associate` read: `album_id|title`, write: `year_released`
    - `sales_manager` read/write all (`.*`), delete: `true`
- The `GatewayAdapter` passes roles via JWT claims: `claims.roles` and `claims.subject`.
- Select handlers reduce returned columns based on the union of allowed fields from roles; insert/update validate writable fields; delete requires an allowed role.

## Development
- Python >= 3.9
- Build system: Hatchling
- Dev env extras in pyproject: `dev` group (pytest, pytest-cov, black, isort, fixture_foundry)

### Quickstart
- Run unit tests:
  - `pytest -q -m unit`
- Run all tests:
  - `pytest -q`

### Database-backed tests
- Uses `fixture_foundry` to provision PostgreSQL and load the Chinook schema:
  - See `tests/conftest.py` for `chinook_db` fixture and `Chinook_Postgres.sql`.

## Test Hints
- See `tests/test_permissions.py` for expected SQL given roles.
- See `tests/test_sql_insert_handler.py`/`test_sql_update_handler.py` for write behavior.
- `tests/chinook_api.yaml` initializes the active model via `set_api_model`.

## Coding Guidelines
- Keep SQL handler public APIs stable; update tests if SQL text changes intentionally.
- Validate and sanitize inputs early in adapters/services; leave SQL handlers to focus on SQL generation.
- Prefer small, targeted patches. Keep unrelated reformatting out of diffs.
- Raise `ApplicationException` for user-facing validation errors.

## Typical Data Flow
1. API Gateway event → `GatewayAdapter.unmarshal()` → `Operation`
2. Services chain applies validation/security
3. DAO selects SQL handler and generates SQL + params
4. Handler executes against Postgres (in tests this is simulated or real via fixtures)
5. `GatewayAdapter.marshal()` shapes the response

## Useful Modules to Inspect
- `adapters/gateway_adapter.py` — event parsing and claims/roles extraction
- `dao/operation_dao.py` — routing to SQL handlers
- `dao/sql_select_query_handler.py` — column filtering by role, WHERE building
- `services/security_service.py` — simple field-level permission checks

## PR Review Checklist
- Build and tests pass locally: `pytest -q`
- New logic covered by unit tests; add integration tests if DB dependent
- No secrets or credentials committed
- Clear error messages for permission failures

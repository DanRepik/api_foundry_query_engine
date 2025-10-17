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

## Permissions Model (current implementation)
- **Structure**: provider → action → role → rule hierarchy with `x-af-permissions`
- **Formats**:
  - Concise: `read: "album_id|title"` (direct property regex string)
  - Verbose: `read: {properties: "regex", where: "condition"}` (object with optional WHERE clause)
- **Actions**: `read`, `write` (normalized from create/update), `delete`
- **Row-Level Security**: WHERE clauses with claim templating `${claims.sub}`
- **Example roles**:
  - `sales_associate` read: `"album_id|title"`, write: `{properties: "title", where: "artist_id = ${claims.tenant}"}`
  - `sales_manager` read/write all (`".*"`), delete: `{allow: true}`
- The `GatewayAdapter` passes roles via JWT claims: `claims.roles` and `claims.subject`.
- Select handlers reduce returned columns based on union of allowed properties from roles; insert/update validate writable properties; delete requires allowed role.
- Backward compatibility maintained for legacy role-first format

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
- See `tests/test_permissions.py` for expected SQL given roles and permission formats.
- See `tests/test_sql_insert_handler.py`/`test_sql_update_handler.py` for write behavior.
- `tests/chinook_api.yaml` initializes the active model via `set_api_model` and demonstrates both concise and verbose permission formats.
- Permission tests cover both concise format (`"album_id|title"`) and verbose format (`{properties: "regex", where: "condition"}`).

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
- `dao/sql_select_query_handler.py` — column filtering by role, WHERE building, hybrid security support
- `dao/sql_query_handler.py` — base handler with permission pattern extraction for both formats
- `services/security_service.py` — field-level permission checks

## PR Review Checklist
- Build and tests pass locally: `pytest -q`
- New logic covered by unit tests; add integration tests if DB dependent
- No secrets or credentials committed
- Clear error messages for permission failures

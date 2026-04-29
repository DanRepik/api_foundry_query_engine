# Security Review: token_decoder anonymous fallback

## Scope
- `api_foundry_query_engine/utils/token_decoder.py`
- `api_foundry_query_engine/connectors/postgres_connection.py`
- Regression tests for anonymous routing and custom SQL row mapping

## Finding
- Severity: High
- Status: Fixed
- Issue: The anonymous-role fallback in `token_decoder()` was applied at the shared Lambda entrypoint level instead of the route-permission level. With `ANONYMOUS_ROLE` set, requests on non-public routes could be downgraded into anonymous execution whenever inline validation was skipped, missing, or failed.
- Evidence:
  - `api_foundry_query_engine/lambda_handler.py` wraps the single query-engine handler with `@token_decoder()` and `@claims_check(...)`.
  - `api_foundry_query_engine/utils/token_decoder.py` previously assigned `requestContext.authorizer = {"roles": [ANONYMOUS_ROLE]}` before route inspection and also fell back to anonymous after failed validation.
  - Route permissions are modeled in API config via `PathOperation.permissions` / `SchemaObject.permissions` and enforced later in SQL handlers.

## Mitigation
- Anonymous fallback is now allowed only when the matched route explicitly grants the configured anonymous role in the API permission model.
- Private routes continue through real token validation and return `401` if no valid identity is established.

## Verification
- `python3 -m pytest tests/test_token_decoder.py -q`
- `python3 -m pytest tests/test_claims_check.py -q`
- `python3 -m pytest tests/test_postgres_connection.py tests/test_custom_sql.py -q`

## Verdict
- `approve_with_conditions`
- Condition: the remaining dirty worktree changes in this repo should be reviewed and committed intentionally. The token decoder change set itself is suitable for release after that normal hygiene step.

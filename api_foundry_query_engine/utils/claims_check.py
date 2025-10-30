"""
Claims Check Decorator for Lambda Functions

This decorator validates JWT scopes and permissions after token decoding.
It works in conjunction with the @token_decoder() decorator to ensure
that the authenticated user has the required permissions for the requested
operation.
"""

import functools
import logging
import os
import re
from typing import Optional, Dict, Any, Callable
from api_foundry_query_engine.utils.app_exception import ApplicationException

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def claims_check(
    require_authentication: Optional[bool] = None,
    validate_scope_format: bool = True,
    validate_path_scope: bool = True,
    min_scope_level: Optional[str] = None,
    required_scopes: Optional[list] = None,
    required_permissions: Optional[list] = None,
    operation_type: Optional[str] = None,
    entity_name: Optional[str] = None,
):
    """
    Decorator for API Foundry Query Engine authentication validation.

    This decorator validates that the user has valid authentication for the
    Query Engine. The Query Engine acts as a SQL translation engine that
    handles all operations, so granular permissions are enforced at the
    SQL level by the existing permissions system.

    Args:
        require_authentication: Require valid JWT token claims (default: True)
        validate_scope_format: Validate that scopes follow expected format
        validate_path_scope: Auto-validate scope matches request path/method
                           (default: True). E.g. GET /employee needs
                           read:employee scope
        min_scope_level: Minimum scope level required
                        ('read', 'write', 'delete')
                        If None, any valid scope is accepted
        required_scopes: List of specific scopes required (optional)
        required_permissions: List of specific permissions required (optional)
        operation_type: Override operation type detection (optional)
        entity_name: Override entity name detection (optional)

    Returns:
        Decorated function that validates authentication before executing

    Raises:
        ApplicationException: If authentication validation fails

    Example:
        @token_decoder()
        @claims_check()  # Auto-validate scope matches path
        def handler(event, context):
            # GET /employee needs read:employee scope OR employee.read perm
            # Additional SQL-level permissions enforced by query engine
            return query_engine.process(event)

        @claims_check(validate_path_scope=False)  # Skip path validation
        def handler_no_scope_check(event, context):
            # Only SQL-level permissions will be enforced
            return query_engine.process(event)

        @claims_check(min_scope_level="write")  # Path + minimum write level
        def admin_handler(event, context):
            return query_engine.process(event)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
            try:
                log.debug("Claims check decorator starting")

                config_require_authentication = require_authentication or os.getenv(
                    "REQUIRE_AUTHENTICATION", ""
                ).lower() in ("true", "1", "yes")
                log.debug(
                    "config_require_authentication: %s", config_require_authentication
                )

                # Extract claims from the event (set by token_decoder)
                claims = _extract_claims(event)
                if not claims:
                    if config_require_authentication:
                        raise ApplicationException(
                            status_code=401, message="No authentication claims found"
                        )
                else:
                    log.debug("Found claims: %s", list(claims.keys()))

                    # Validate scope format if requested
                    if validate_scope_format:
                        _validate_scope_format(claims)

                    # Check minimum scope level if specified
                    if min_scope_level:
                        _validate_min_scope_level(claims, min_scope_level)

                    # Auto-validate path-based scope if enabled
                    if validate_path_scope:
                        _validate_path_scope(claims, event, operation_type, entity_name)

                    # Check specific scopes if required
                    if required_scopes:
                        _validate_required_scopes(
                            claims, required_scopes, event, operation_type, entity_name
                        )

                    # Check specific permissions if required
                    if required_permissions:
                        _validate_required_permissions(claims, required_permissions)

                log.debug("Authentication validation passed")

                # Execute the original function
                return func(event, context)

            except ApplicationException:
                raise
            except Exception as e:
                log.error("Claims check error: %s", str(e))
                raise ApplicationException(
                    status_code=500,
                    message="Internal server error during claims validation",
                )

        return wrapper

    return decorator


def _extract_claims(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract JWT claims from the event context.

    Checks multiple locations where claims might be stored:
    - requestContext.authorizer (API Gateway TOKEN authorizer)
    - requestContext.authorizer.claims (nested claims)
    - requestContext.authorizer.iam (IAM authorizer context)
    - requestContext.authorizer.lambda (Lambda authorizer context)
    """
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer")

        if authorizer is None:
            log.debug("No authorizer found in requestContext")
            return None

        # Check direct authorizer context (most common for TOKEN authorizer)
        claim_keys = ["sub", "scope", "permissions", "roles"]
        if isinstance(authorizer, dict) and any(
            key in authorizer for key in claim_keys
        ):
            log.debug("Found claims in requestContext.authorizer")
            return authorizer

        # Check nested claims object
        claims = authorizer.get("claims")
        if claims and isinstance(claims, dict):
            log.debug("Found claims in requestContext.authorizer.claims")
            return claims

        # Check IAM authorizer context
        iam_context = authorizer.get("iam")
        if iam_context and isinstance(iam_context, dict):
            log.debug("Found claims in requestContext.authorizer.iam")
            return iam_context

        # Check Lambda authorizer context
        lambda_context = authorizer.get("lambda")
        if lambda_context and isinstance(lambda_context, dict):
            log.debug("Found claims in requestContext.authorizer.lambda")
            return lambda_context

        # If authorizer exists but no recognized claims format, return it
        # This handles empty authorizers or custom claim structures
        log.debug("Authorizer exists but no standard claims structure found")
        return authorizer

    except Exception as e:
        log.warning("Failed to extract claims: %s", str(e))
        return None


# Operation types and resources are handled by the SQL Query Engine


def _validate_scope_format(claims: Dict[str, Any]) -> None:
    """Validate that scopes follow expected format."""
    scopes = claims.get("scope", "")
    if isinstance(scopes, str):
        scopes = scopes.split()
    elif not isinstance(scopes, list):
        scopes = []

    # Allow empty scopes if permissions exist
    permissions = claims.get("permissions", [])
    if not scopes and not permissions:
        raise ApplicationException(
            status_code=403, message="No scopes or permissions found in token"
        )

    # Validate scope format: should be operation:resource or operation:*
    for scope in scopes:
        if not re.match(r"^[a-zA-Z]+:[a-zA-Z*_-]+$", scope):
            log.warning("Invalid scope format: %s", scope)
            # Don't fail on invalid format, just log warning
            # The SQL layer will handle actual permission enforcement


def _validate_min_scope_level(claims: Dict[str, Any], min_level: str) -> None:
    """Validate that user has at least the minimum scope level."""
    scopes = claims.get("scope", "")
    if isinstance(scopes, str):
        scopes = scopes.split()
    elif not isinstance(scopes, list):
        scopes = []

    # Define scope hierarchy
    scope_hierarchy = {"read": 1, "write": 2, "delete": 3, "admin": 4}

    min_level_value = scope_hierarchy.get(min_level, 0)
    user_max_level = 0

    for scope in scopes:
        if ":" in scope:
            operation = scope.split(":")[0].lower()
            scope_value = scope_hierarchy.get(operation, 0)
            user_max_level = max(user_max_level, scope_value)

    if user_max_level < min_level_value:
        raise ApplicationException(
            status_code=403, message=f"Insufficient scope level. Required: {min_level}"
        )


def _validate_path_scope(
    claims: Dict[str, Any],
    event: Dict[str, Any],
    operation_type: Optional[str],
    entity_name: Optional[str],
) -> None:
    """Validate that user has scope matching the request path and method."""
    user_scopes = claims.get("scope", "")
    if isinstance(user_scopes, str):
        user_scopes = user_scopes.split()
    elif not isinstance(user_scopes, list):
        user_scopes = []

    # Get user permissions as well
    user_permissions = claims.get("permissions", [])
    if isinstance(user_permissions, str):
        try:
            import json

            user_permissions = json.loads(user_permissions)
        except (json.JSONDecodeError, ValueError):
            user_permissions = []
    elif not isinstance(user_permissions, list):
        user_permissions = []

    # Skip path scope validation if user has no scopes or permissions
    if not user_scopes and not user_permissions:
        log.debug("No scopes or permissions found, skipping path validation")
        return

    # Determine operation and entity from request
    operation = operation_type or _extract_operation_type(event)
    entity = entity_name or _extract_entity_from_path(event)

    if not entity:
        # Can't validate without entity - skip validation
        log.debug("No entity found in path, skipping path scope validation")
        return

    # Construct required scope for this request
    required_scope = f"{operation}:{entity}"

    # Check if user has the required scope OR equivalent permission
    has_scope = _scope_matches(user_scopes, required_scope, operation, entity)
    required_permission = f"{entity}.{operation}"
    has_permission = _permission_matches(user_permissions, required_permission)

    if not has_scope and not has_permission:
        raise ApplicationException(
            status_code=403,
            message=f"Access denied. Required scope: {required_scope} "
            f"or permission: {required_permission}",
        )

    log.debug("Path scope validation passed for %s", required_scope)


def _validate_required_scopes(
    claims: Dict[str, Any],
    required_scopes: list,
    event: Dict[str, Any],
    operation_type: Optional[str],
    entity_name: Optional[str],
) -> None:
    """Validate that user has required scopes."""
    user_scopes = claims.get("scope", "")
    if isinstance(user_scopes, str):
        user_scopes = user_scopes.split()
    elif not isinstance(user_scopes, list):
        user_scopes = []

    # Determine operation and entity
    operation = operation_type or _extract_operation_type(event)
    entity = entity_name or _extract_entity_from_path(event)

    # Check each required scope
    for required_scope in required_scopes:
        if not _scope_matches(user_scopes, required_scope, operation, entity):
            raise ApplicationException(
                status_code=403, message=f"Required scope not found: {required_scope}"
            )


def _validate_required_permissions(
    claims: Dict[str, Any], required_permissions: list
) -> None:
    """Validate that user has required permissions."""
    user_permissions = claims.get("permissions", [])
    if isinstance(user_permissions, str):
        # Handle JSON string format
        try:
            import json

            user_permissions = json.loads(user_permissions)
        except (json.JSONDecodeError, ValueError):
            user_permissions = []
    elif not isinstance(user_permissions, list):
        user_permissions = []

    # Check each required permission
    for required_permission in required_permissions:
        if not _permission_matches(user_permissions, required_permission):
            raise ApplicationException(
                status_code=403,
                message=f"Required permission not found: {required_permission}",
            )


# The Query Engine handles granular permissions at the SQL level
# This decorator only validates basic authentication and scope levels


# Convenience decorators for Query Engine access levels
def requires_authentication():
    """Require valid authentication but allow any scopes."""
    return claims_check(require_authentication=True)


def requires_read_access():
    """Require at least read-level access."""
    return claims_check(min_scope_level="read")


def requires_write_access():
    """Require at least write-level access."""
    return claims_check(min_scope_level="write")


def requires_delete_access():
    """Require at least delete-level access."""
    return claims_check(min_scope_level="delete")


def requires_admin_access():
    """Require admin-level access."""
    return claims_check(min_scope_level="admin")


# Additional utility functions for testing and convenience
def requires_read_scope(entity: Optional[str] = None, extract_from_path: bool = False):
    """Convenience decorator for read operations."""
    # Parameters kept for compatibility but not used in simple implementation
    _ = entity, extract_from_path  # Silence unused warnings
    return claims_check(min_scope_level="read")


def requires_write_scope(entity: Optional[str] = None, extract_from_path: bool = False):
    """Convenience decorator for write operations."""
    # Parameters kept for compatibility but not used in simple implementation
    _ = entity, extract_from_path  # Silence unused warnings
    return claims_check(min_scope_level="write")


def _extract_operation_type(event: Dict[str, Any]) -> str:
    """Extract operation type from HTTP method."""
    method = event.get("httpMethod", "GET").upper()
    if method == "GET":
        return "read"
    elif method in ["POST", "PUT", "PATCH"]:
        return "write"
    elif method == "DELETE":
        return "delete"
    else:
        return "read"  # default


def _extract_entity_from_path(event: Dict[str, Any]) -> Optional[str]:
    """Extract entity name from request path."""
    path = event.get("path") or event.get("resource", "")
    if not path:
        return None

    # Remove leading slash and split by slash
    path_parts = path.lstrip("/").split("/")

    # Skip API prefixes and return the last non-parameter part
    # For paths like "/chinook-api/album" or "/api/v1/customer/123"
    for part in reversed(path_parts):
        if part and not part.startswith("{") and not part.isdigit():
            return part

    # If no suitable part found, return the last non-parameter part
    for part in reversed(path_parts):
        if part and not part.startswith("{"):
            return part

    return None


def _scope_matches(
    user_scopes: list, required_scope: str, operation: str, entity: str
) -> bool:
    """Check if user scopes match the required scope."""
    _ = entity  # Silence unused warning
    # Check for exact match
    if required_scope in user_scopes:
        return True

    # Check for wildcard matches
    wildcard_patterns = [
        f"{operation}:*",  # operation wildcard
        "*:*",  # global wildcard
        "*",  # simple wildcard
    ]

    for pattern in wildcard_patterns:
        if pattern in user_scopes:
            return True

    return False


def _permission_matches(user_permissions: list, required_permission: str) -> bool:
    """Check if user permissions match the required permission."""
    # Direct match
    if required_permission in user_permissions:
        return True

    # Wildcard match (e.g., "customer.*" matches "customer.read")
    for perm in user_permissions:
        if perm.endswith(".*"):
            prefix = perm[:-2]  # Remove ".*"
            if required_permission.startswith(prefix + "."):
                return True

    return False

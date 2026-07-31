import json
from typing import Any, Dict, List, Optional

from api_foundry_query_engine.utils.logger import logger

logger = logger(__name__)


class Operation:
    """
    Represents an action to be performed on an entity.

    The `Operation` class encapsulates the details required
    to execute an operation on a given entity, including
    query parameters for selecting records, parameters for
    storing or updating values, metadata for operational
    instructions, and roles defining the contexts in which
    the operation can be performed.

    Attributes:
        entity (str): The name of the resource or object being
            targeted (e.g., "User", "Order").
        action (str): The type of action being performed
            (e.g., "create", "read", "update", "delete").
        query_params (dict): Parameters used to filter or select
            the records affected by the operation.
        store_params (dict): Parameters that define the values to
            be stored or updated for the selected records.
        metadata_params (dict): Additional instructions for the
            operation, such as sorting or pagination.
        roles (dict): Defines the roles under which the operation
            is allowed to be performed.
    """

    def __init__(
        self,
        *,
        entity: str,
        action: str,
        query_params: Optional[Dict[str, Any]] = None,
        store_params: Optional[Dict[str, Any]] = None,
        metadata_params: Optional[Dict[str, Any]] = None,
        claims: Optional[Dict[str, Any]] = None,
        roles: Optional[List[str]] = None,
    ):
        """
        Initializes the Operation instance.

        Args:
            entity (str): The name of the entity to perform the operation on.
            action (str): The action to perform on the entity.
            query_params (dict, optional): Parameters for selecting
                affected records (default: {}).
            store_params (dict, optional): Parameters defining new or
                updated values (default: {}).
            metadata_params (dict, optional): Metadata for the
                operation, such as sorting or pagination (default: {}).
            roles (dict, optional): Defines the roles allowed to
                perform the operation (default: {}).
        """
        # The target entity for the operation (e.g., "User", "Order").
        self.entity = entity

        # The type of action to perform (e.g., "create",
        # "read", "update", "delete").
        self.action = action

        # Query parameters to filter or identify the affected records.
        self.query_params = query_params or {}

        # Parameters defining the values to be stored or updated
        # for the operation.
        self.store_params = store_params or {}

        # Metadata for operational instructions like sorting,
        # limiting, or offsetting results.
        self.metadata_params = metadata_params or {}

        # Roles defining the context in which the operation is allowed.
        self.claims = claims or {}
        if roles is not None and "roles" not in self.claims:
            self.claims["roles"] = roles

        # Log the operation for debugging and audit purposes
        logger.info(
            "Operation created: entity=%s, action=%s, "
            "query_params=%s, store_params=%s, "
            "metadata_params=%s, claims=%s",
            self.entity,
            self.action,
            self.query_params,
            self.store_params,
            self.metadata_params,
            self.claims,
        )

    @property
    def roles(self) -> List[str]:
        """Get the roles from claims.

        Falls back to a singular `role` claim plus `groups` when the
        plural `roles` key itself isn't present -- some authorizers (e.g.
        a custom Lambda TOKEN authorizer following AWS's own convention
        of a `role` string and a `groups` list) never populate `roles`,
        which previously made every such caller look role-less even with
        a perfectly valid, correctly-scoped token. `groups` may arrive as
        a real list or, when it passed through an API Gateway authorizer
        context (whose values must be strings), a JSON-encoded string.
        """
        if not self.claims:
            return []
        roles = self.claims.get("roles")
        if roles:
            return list(roles) if isinstance(roles, list) else [str(roles)]

        fallback: List[str] = []
        role = self.claims.get("role")
        if role:
            fallback.append(str(role))

        groups_raw = self.claims.get("groups")
        groups: List[str] = []
        if isinstance(groups_raw, str) and groups_raw.strip():
            try:
                parsed = json.loads(groups_raw)
                groups = [str(item) for item in parsed] if isinstance(parsed, list) else [groups_raw]
            except (TypeError, ValueError):
                groups = [groups_raw]
        elif isinstance(groups_raw, list):
            groups = [str(item) for item in groups_raw]

        for group in groups:
            if group not in fallback:
                fallback.append(group)
        return fallback

    def subject(self) -> Optional[str]:
        """Get the subject from claims."""
        return self.claims.get("sub") if self.claims else None

    def groups(self) -> List[str]:
        """Get the groups from claims."""
        return self.claims.get("groups", []) if self.claims else []

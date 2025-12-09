from api_foundry_query_engine.dao.sql_query_handler import (
    SQLSchemaQueryHandler,
)
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class SQLRestoreSchemaQueryHandler(SQLSchemaQueryHandler):
    """Handler for restoring soft-deleted records."""

    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, schema_object, engine)

    def check_permission(self) -> bool:
        """Check if user has permission to restore records."""
        # if permissions are not defined then no restrictions are applied
        if not self.schema_object.permissions:
            return True

        # Use the proper provider-action-role structure
        provider_permissions = self.schema_object.permissions.get("default", {})

        # Check for explicit restore permissions first
        restore_permissions = provider_permissions.get("restore", {})
        write_permissions = provider_permissions.get("write", {})

        for role in self.operation.roles:
            # Try restore permissions first
            role_permissions = restore_permissions.get(role)
            log.info("role: %s, restore_permissions: %s", role, role_permissions)

            # If not found, fall back to write permissions
            if role_permissions is None:
                role_permissions = write_permissions.get(role)
                log.info("Fallback to write permissions: %s", role_permissions)

            # If still not found, check wildcard "*"
            if role_permissions is None:
                role_permissions = restore_permissions.get(
                    "*"
                ) or write_permissions.get("*")
                log.info("Fallback to wildcard role '*': %s", role_permissions)
                if role_permissions is None:
                    continue

            # Handle both boolean and object permission formats
            if isinstance(role_permissions, bool):
                allowed = role_permissions
            else:
                # For complex permission objects, existence means allowed
                allowed = True

            if allowed:
                return True

        return False

    def _get_restore_update_values(self) -> str:
        """Generate SET clause for restore operation."""
        self.store_placeholders = {}
        columns = []

        # Process soft delete properties
        soft_delete_props = self.schema_object.get_soft_delete_properties()

        for _, prop in soft_delete_props.items():
            strategy = prop.get_soft_delete_strategy()
            config = prop.get_soft_delete_config()
            column_name = prop.column_name

            if strategy == "null_check":
                columns.append(f"{column_name} = NULL")
            elif strategy == "boolean_flag":
                active_value = config.get("active_value", True)
                columns.append(f"{column_name} = {str(active_value).lower()}")
            elif strategy == "exclude_values":
                restore_value = config.get("restore_value")
                if restore_value:
                    if isinstance(restore_value, str):
                        columns.append(f"{column_name} = '{restore_value}'")
                    else:
                        columns.append(f"{column_name} = {restore_value}")

        # Process audit fields for restore action
        audit_props = self.schema_object.get_soft_delete_audit_properties()
        claims = self.operation.claims or {}

        for _, prop in audit_props.items():
            config = prop.get_soft_delete_config()
            action = config.get("action", "")

            if action == "restore" and "sub" in claims:
                placeholder_key = f"audit_{prop.api_name}"
                columns.append(f"{prop.column_name} = %({placeholder_key})s")
                self.store_placeholders[placeholder_key] = claims["sub"]
            elif action == "restore_timestamp":
                columns.append(f"{prop.column_name} = CURRENT_TIMESTAMP")

        return " SET " + ", ".join(columns) if columns else ""

    @property
    def search_condition(self) -> str:
        """Override to include soft-deleted records in restore search."""
        self.search_placeholders = {}
        conditions = []

        # Don't apply soft delete filtering for restore operations
        # We want to find the soft-deleted records to restore them

        for name, value in self.operation.query_params.items():
            if "." in name:
                raise ApplicationException(
                    400, "Selection on relations is not supported"
                )
            prop = self.schema_object.properties.get(name)
            if not prop:
                raise ApplicationException(
                    500, f"Search condition column not found {name}"
                )

            assignment, holders = self.search_value_assignment(prop, value)
            conditions.append(assignment)
            self.search_placeholders.update(holders)

        # Add condition to only restore soft-deleted records
        soft_delete_conditions = self._get_soft_delete_restore_conditions()
        if soft_delete_conditions:
            conditions.append(f"({soft_delete_conditions})")

        return f" WHERE {' AND '.join(conditions)}" if conditions else ""

    def _get_soft_delete_restore_conditions(self) -> str:
        """Generate conditions to identify soft-deleted records for restore."""
        conditions = []

        soft_delete_props = self.schema_object.get_soft_delete_properties()

        for _, prop in soft_delete_props.items():
            strategy = prop.get_soft_delete_strategy()
            config = prop.get_soft_delete_config()
            column_name = prop.column_name

            if strategy == "null_check":
                conditions.append(f"{column_name} IS NOT NULL")
            elif strategy == "boolean_flag":
                active_value = config.get("active_value", True)
                inactive_value = not active_value
                value_str = str(inactive_value).lower()
                conditions.append(f"{column_name} = {value_str}")
            elif strategy == "exclude_values":
                excluded_values = config.get("values", [])
                if excluded_values:
                    # For restore, we want records that ARE in the excluded values
                    formatted_values = ", ".join(
                        f"'{val}'" if isinstance(val, str) else str(val)
                        for val in excluded_values
                    )
                    conditions.append(f"{column_name} IN ({formatted_values})")

        # For multiple soft delete fields, use AND logic
        # A record is considered soft-deleted if ALL soft delete conditions are true
        return " AND ".join(conditions) if conditions else ""

    @property
    def sql(self) -> str:
        if not self.check_permission():
            raise ApplicationException(
                403,
                f"Subject is not allowed to restore " f"{self.schema_object.api_name}",
            )

        if not self.schema_object.has_soft_delete_support():
            raise ApplicationException(
                400,
                f"Schema object {self.schema_object.api_name} does not support "
                + "soft delete operations",
            )

        update_clause = self._get_restore_update_values()
        if not update_clause:
            raise ApplicationException(
                400, f"No restore fields available for {self.schema_object.api_name}"
            )

        return (
            f"UPDATE {self.table_expression}{update_clause}"
            + f"{self.search_condition} RETURNING {self.select_list}"
        )

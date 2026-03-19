from api_foundry_query_engine.dao.sql_query_handler import SQLSchemaQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class SQLDeleteSchemaQueryHandler(SQLSchemaQueryHandler):
    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, schema_object, engine)

    def check_permission(self) -> bool:
        """
        Checks the user's permissions for the specified permission type.

        Args:
            permission_type (str): The type of permission to check ("read" or "write").
            properties (List[str], optional): Specific properties to check. If None,
                all schema properties are checked.

        Returns:
            List[str]: A list of properties the user is permitted to access.
        """
        # if permissions are not defined then no restrictions are applied
        if not self.schema_object.permissions:
            return True

        # Use the proper provider-action-role structure
        provider_permissions = self.schema_object.permissions.get("default", {})
        delete_permissions = provider_permissions.get("delete", {})

        for role in self.operation.roles:
            role_permissions = delete_permissions.get(role)
            log.info("role: %s, role_permissions: %s", role, role_permissions)

            # If no permissions found for role, check wildcard "*"
            if role_permissions is None:
                role_permissions = delete_permissions.get("*")
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

    def _has_soft_delete_fields(self) -> bool:
        """Check if schema object supports soft delete."""
        return self.schema_object.has_soft_delete_support()

    def _get_soft_delete_update_values(self) -> str:
        """Generate SET clause for soft delete operation."""
        self.store_placeholders = {}
        columns = []

        # Process soft delete properties
        soft_delete_props = self.schema_object.get_soft_delete_properties()

        for _, prop in soft_delete_props.items():
            strategy = prop.get_soft_delete_strategy()
            config = prop.get_soft_delete_config()
            column_name = prop.column_name

            if strategy == "null_check":
                # Set timestamp fields to CURRENT_TIMESTAMP
                if prop.api_type in ["date-time", "datetime"]:
                    columns.append(f"{column_name} = CURRENT_TIMESTAMP")
                else:
                    columns.append(f"{column_name} = 'deleted'")
            elif strategy == "boolean_flag":
                inactive_value = not config.get("active_value", True)
                value_str = str(inactive_value).lower()
                columns.append(f"{column_name} = {value_str}")
            elif strategy == "exclude_values":
                delete_value = config.get("delete_value")
                if delete_value:
                    if isinstance(delete_value, str):
                        columns.append(f"{column_name} = '{delete_value}'")
                    else:
                        columns.append(f"{column_name} = {delete_value}")

        # Process audit fields
        audit_props = self.schema_object.get_soft_delete_audit_properties()
        claims = self.operation.claims or {}

        for _, prop in audit_props.items():
            config = prop.get_soft_delete_config()
            action = config.get("action", "")

            if action == "delete" and "sub" in claims:
                placeholder_key = f"audit_{prop.api_name}"
                columns.append(f"{prop.column_name} = %({placeholder_key})s")
                self.store_placeholders[placeholder_key] = claims["sub"]

        return " SET " + ", ".join(columns) if columns else ""

    @property
    def sql(self) -> str:
        if not self.check_permission():
            raise ApplicationException(
                403, f"Subject is not allowed to delete {self.schema_object.api_name}"
            )

        concurrency_property = self.schema_object.concurrency_property
        if concurrency_property:
            if not self.operation.query_params.get(concurrency_property.api_name):
                raise ApplicationException(
                    400,
                    "Missing required concurrency management property.  "
                    + f"schema_object: {self.schema_object.api_name}, "
                    + f"property: {concurrency_property.api_name}",
                )
            if self.operation.store_params.get(concurrency_property.api_name):
                raise ApplicationException(
                    400,
                    "For updating concurrency managed schema objects the current "
                    + "version may not be supplied as a storage parameter.  "
                    + f"schema_object: {self.schema_object.api_name}, "
                    + f"property: {concurrency_property.api_name}",
                )

        # Use soft delete if supported, otherwise hard delete
        if self._has_soft_delete_fields():
            update_clause = self._get_soft_delete_update_values()
            return (
                f"UPDATE {self.table_expression}{update_clause}"
                + f"{self.search_condition} RETURNING {self.select_list}"
            )
        else:
            # Fall back to hard delete for tables without soft delete support
            return (
                f"DELETE FROM {self.table_expression}{self.search_condition} "
                + f"RETURNING {self.select_list}"
            )

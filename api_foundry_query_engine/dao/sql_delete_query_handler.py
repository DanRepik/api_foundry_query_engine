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

    @property
    def sql(self) -> str:
        if not self.check_permission():
            raise ApplicationException(
                402, f"Subject is not allowed to delete {self.schema_object.api_name}"
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

        return (
            f"DELETE FROM {self.table_expression}{self.search_condition} "
            + f"RETURNING {self.select_list}"
        )

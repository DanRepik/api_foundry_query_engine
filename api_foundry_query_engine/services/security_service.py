from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.service import ServiceAdapter

log = logger(__name__)


class SecurityService(ServiceAdapter):
    def execute(self, operation: Operation) -> list[dict]:
        """
        Execute the operation after validating security instructions.

        Parameters:
        - operation (Operation): The operation to execute.

        Returns:
        - list[dict]: The result of the operation, filtered based on security rules.
        """
        log.debug(f"Executing operation: {operation}")

        # Resolve the schema or path operation to retrieve the `security` attribute
        schema_or_path = self.schema_or_path_resolver(
            operation.entity, operation.action
        )
        if not schema_or_path or "security" not in schema_or_path:
            raise ValueError(
                f"No security instructions found for entity {operation.entity}"
            )

        security_rules = schema_or_path["security"]

        # Validate query and store parameters
        self._validate_query_params(operation.query_params, security_rules)
        self._validate_store_params(operation.store_params, security_rules)

        # Execute the next service
        result = self.next_service.execute(operation)

        # Filter the result based on security rules
        filtered_result = self._filter_result(result, security_rules)
        return filtered_result

    def _validate_query_params(self, query_params: dict, security_rules: dict):
        """
        Validate query parameters against read permissions.

        Parameters:
        - query_params (dict): Query parameters to validate.
        - security_rules (dict): Security rules for validation.

        Raises:
        - PermissionError: If a query parameter violates read permissions.
        """
        read_permissions = security_rules.get("read", [])
        invalid_params = [
            key
            for key in query_params
            if key not in read_permissions and read_permissions != ["*"]
        ]
        if invalid_params:
            raise PermissionError(f"Query parameters not permitted: {invalid_params}")

    def _validate_store_params(self, store_params: dict, security_rules: dict):
        """
        Validate store parameters against write permissions.

        Parameters:
        - store_params (dict): Store parameters to validate.
        - security_rules (dict): Security rules for validation.

        Raises:
        - PermissionError: If a store parameter violates write permissions.
        """
        write_permissions = security_rules.get("write", [])
        invalid_params = [
            key
            for key in store_params
            if key not in write_permissions and write_permissions != ["*"]
        ]
        if invalid_params:
            raise PermissionError(f"Store parameters not permitted: {invalid_params}")

    def _filter_result(self, result: list[dict], security_rules: dict) -> list[dict]:
        """
        Filter the result based on read permissions.

        Parameters:
        - result (list[dict]): The original result set.
        - security_rules (dict): Security rules for filtering.

        Returns:
        - list[dict]: The filtered result set.
        """
        read_permissions = security_rules.get("read", [])
        if read_permissions == ["*"]:
            return result  # No filtering needed

        filtered_result = []
        for record in result:
            filtered_record = {
                key: value for key, value in record.items() if key in read_permissions
            }
            filtered_result.append(filtered_record)

        return filtered_result

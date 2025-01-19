from typing import Optional

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.service import Service
from api_foundry_query_engine.adapters.adapter import Adapter
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class SecurityAdapter(Adapter):
    def __init__(self, service: Optional[Service] = None, permissions: dict = None):
        """
        Initialize SecurityAdapter with a service and permissions.

        Parameters:
        - service (Service): The service used to process operations.
        - permissions (dict): A dictionary containing the user's permissions,
                              structured as:
                              {
                                  "read": ["field1", "field2", ...],
                                  "write": ["field3", "field4", ...]
                              }
        """
        super().__init__(service)
        self.permissions = permissions or {"read": [], "write": []}

    def unmarshal(self, event) -> Operation:
        """
        Unmarshal the event into an Operation object after validating query and store params.

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - Operation: The validated operation.
        """
        entity = event.get("entity")
        action = event.get("action")
        query_params = event.get("query_params", {})
        store_params = event.get("store_params", {})

        # Validate read permissions for query_params
        invalid_query_params = [
            key for key in query_params if key not in self.permissions["read"]
        ]
        if invalid_query_params:
            raise PermissionError(
                f"Query parameters not permitted: {invalid_query_params}"
            )

        # Validate write permissions for store_params
        invalid_store_params = [
            key for key in store_params if key not in self.permissions["write"]
        ]
        if invalid_store_params:
            raise PermissionError(
                f"Store parameters not permitted: {invalid_store_params}"
            )

        return Operation(
            entity=entity,
            action=action,
            query_params=query_params,
            store_params=store_params,
        )

    def marshal(self, result: list[dict]):
        """
        Filter the result based on read permissions before returning.

        Parameters:
        - result (list[dict]): The data set to return in the response.

        Returns:
        - list[dict]: Filtered response with only permitted fields.
        """
        filtered_result = []
        for record in result:
            filtered_record = {
                key: value
                for key, value in record.items()
                if key in self.permissions["read"]
            }
            filtered_result.append(filtered_record)

        return filtered_result

    def process_event(self, event):
        """
        Process Lambda event using a domain function.

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - any: Result of the domain function.
        """
        try:
            operation = self.unmarshal(event)
            result = self.service.execute(operation)
            log.debug(f"adapter result: {result}")
            return self.marshal(result)
        except PermissionError as e:
            log.error(f"Permission error: {e}")
            return {"error": str(e), "status": "permission_denied"}

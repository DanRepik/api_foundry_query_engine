import json
from typing import Any, Dict, List, Optional, Tuple

from api_foundry_query_engine.adapters.adapter import Adapter
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException

actions_map = {
    "GET": "read",
    "POST": "create",
    "PUT": "update",
    "DELETE": "delete",
}


class GatewayAdapter(Adapter):
    def marshal(self, result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Marshal the result into a event response

        Parameters:
        - result (list): the data set to return in the response

        Returns:
        - the event response
        """
        return super().marshal(result)

    def unmarshal(self, event: Dict[str, Any]) -> Operation:
        """
        Get parameters from the Lambda event.

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - tuple: Tuple containing data, query and metadata parameters.
        """
        resource = event.get("resource")
        if resource is not None and "/" in resource:
            parts = resource.split("/")
            entity = parts[1] if len(parts) > 1 else None
        else:
            entity = None

        method = str(event.get("httpMethod", "")).upper()
        action = actions_map.get(method, "read")

        event_params = {}

        path_parameters = self._convert_parameters(event.get("pathParameters"))
        if path_parameters is not None:
            event_params.update(path_parameters)

        queryStringParameters = self._convert_parameters(
            event.get("queryStringParameters")
        )
        if queryStringParameters is not None:
            event_params.update(queryStringParameters)

        query_params, metadata_params = self.split_params(event_params)

        store_params = {}
        body = event.get("body")
        if body is not None and len(body) > 0:
            store_params = json.loads(body)

        authorizer_info = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer_info.get("claims", {})
        roles = claims.get("roles", [])
        groups = claims.get("groups", [])
        subject = claims.get("sub")
        permissions = claims.get("permissions", [])
        scope_str = claims.get("scope")

        # Enforce OAuth scopes (simulating API Gateway authorizer behavior)
        # Required scope pattern: read|write|delete:<entity>
        if entity and scope_str:
            required_action = {
                "GET": "read",
                "POST": "write",
                "PUT": "write",
                "PATCH": "write",
                "DELETE": "delete",
            }.get(method, "read")
            required_scope = f"{required_action}:{entity}"
            token_scopes = set(str(scope_str).split())

            def _has_scope(required: str) -> bool:
                return (
                    required in token_scopes
                    or f"{required_action}:*" in token_scopes
                    or "*" in token_scopes
                    or "*:*" in token_scopes
                )

            if not _has_scope(required_scope):
                raise ApplicationException(
                    401,
                    ("insufficient_scope: required_scope=" + required_scope),
                )

        return Operation(
            entity=entity,
            action=action,
            store_params=store_params,
            query_params=query_params,
            metadata_params=metadata_params,
            roles=roles,
            groups=groups,
            subject=subject,
            permissions=permissions,
            claims=claims,
        )

    def _convert_parameters(
        self, parameters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Convert parameters to appropriate types.

        Parameters:
        - parameters (dict): Dictionary of parameters.

        Returns:
        - dict: Dictionary with parameters converted to appropriate types.
        """
        if parameters is None:
            return None

        result = {}
        for parameter, value in parameters.items():
            try:
                result[parameter] = int(value)
            except ValueError:
                try:
                    result[parameter] = float(value)
                except ValueError:
                    result[parameter] = value
        return result

    def split_params(
        self, parameters: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Split a dictionary into two dictionaries based on keys.

        Parameters:
        - dictionary (dict): Input dictionary.

        Returns:
        - tuple: A tuple containing two dictionaries.
                The first dictionary contains metadata_params,
                and the second dictionary query_params.
        """
        query_params = {}
        metadata_params = {}

        for key, value in parameters.items():
            if key.startswith("__"):
                metadata_params[key] = value
            else:
                query_params[key] = value

        return query_params, metadata_params

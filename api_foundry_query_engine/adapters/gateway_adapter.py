import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from api_foundry_query_engine.adapters.adapter import Adapter
from api_foundry_query_engine.operation import Operation

log = logging.getLogger(__name__)

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
        if resource:
            parts = [p for p in resource.split("/") if p]  # Remove empty strings
            # Skip common API prefixes like "api", "v1", "v2", etc.
            api_prefixes = {"api", "v1", "v2", "v3"}
            literal_parts = [p for p in parts if p not in api_prefixes and not p.startswith("{")]
            entity = "_".join(literal_parts) if literal_parts else None
        else:
            entity = None

        method = str(event.get("httpMethod", "")).upper()
        action = actions_map.get(method, "read")

        # Extract JWT claims early for batch operations
        claims = event.get("requestContext", {}).get("authorizer", {})

        # Handle different authorizer types
        if isinstance(claims, dict):
            # Parse JSON-stringified fields (roles, permissions)
            # from token validator
            for key in ["roles", "permissions"]:
                if key in claims and isinstance(claims[key], str):
                    try:
                        claims[key] = json.loads(claims[key])
                    except (json.JSONDecodeError, ValueError):
                        pass  # Keep as string if not valid JSON

            # TOKEN authorizer puts claims directly in authorizer object
            if "sub" in claims or "iss" in claims or "roles" in claims:
                # Already have JWT claims at top level
                pass
            elif "claims" in claims:
                # Some configurations nest claims
                claims = claims["claims"]
            elif "iam" in claims:
                # IAM authorizer fallback
                claims = claims["iam"]
            elif "lambda" in claims:
                # Lambda authorizer fallback
                claims = claims["lambda"]
            else:
                # Empty or unknown format - keep what we have
                pass
        else:
            # Non-dict authorizer context
            claims = {}

        # Handle batch requests
        if entity == "batch" and method == "POST":
            body = event.get("body")
            if body:
                batch_request = json.loads(body)
                return Operation(
                    entity="batch",
                    action="create",
                    store_params=batch_request,
                    claims=claims,
                )

        event_params = {}

        raw_path = event.get("path") or ""
        path_parameters = event.get("pathParameters") or {}
        if "proxy" in path_parameters and not raw_path:
            raw_path = f"/{path_parameters['proxy']}"
        extracted_path_params = self._extract_path_params(resource, raw_path)
        for key, value in extracted_path_params.items():
            if key not in path_parameters or path_parameters.get(key) in (None, "", "None"):
                path_parameters[key] = value

        path_parameters = self._convert_parameters(path_parameters)
        if path_parameters is not None:
            event_params.update(path_parameters)

        query_string_parameters = self._convert_parameters(event.get("queryStringParameters"))
        if query_string_parameters is not None:
            event_params.update(query_string_parameters)
        query_params, metadata_params = self.split_params(event_params)
        log.info("Unmarshalled query parameters: %s", query_params)
        log.info("Unmarshalled metadata parameters: %s", metadata_params)

        store_params = {}
        body = event.get("body")
        if body is not None and len(body) > 0:
            store_params = json.loads(body)

        return Operation(
            entity=entity,
            action=action,
            store_params=store_params,
            query_params=query_params,
            metadata_params=metadata_params,
            claims=claims,
        )

    def _convert_parameters(self, parameters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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

    def _extract_path_params(self, resource: Optional[str], path: str) -> Dict[str, str]:
        if not resource or not path:
            return {}

        resource_parts = [p for p in resource.split("/") if p]
        path_parts = [p for p in path.split("/") if p]
        params: Dict[str, str] = {}

        for template, actual in zip(resource_parts, path_parts):
            if template.startswith("{") and template.endswith("}"):
                key = template[1:-1]
                if key:
                    params[key] = actual

        return params

    def split_params(self, parameters: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
                metadata_params[key[2:]] = value
            else:
                query_params[key] = value

        log.info("split_params input: %s", parameters)
        log.info("query_params: %s", query_params)
        log.info("metadata_params: %s", metadata_params)

        return query_params, metadata_params

import json

from api_foundry_query_engine.adapters.adapter import Adapter
from api_foundry_query_engine.operation import Operation

actions_map = {
    "GET": "read",
    "POST": "create",
    "PUT": "update",
    "DELETE": "delete",
}


class GatewayAdapter(Adapter):
    def marshal(self, result: list[dict]):
        """
        Marshal the result into a event response

        Parameters:
        - result (list): the data set to return in the response

        Returns:
        - the event response
        """
        return super().marshal(result)

    def unmarshal(self, event):
        """
        Get parameters from the Lambda event.

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - tuple: Tuple containing data, query and metadata parameters.
        """
        entity = event.get("resource").split("/")[1]
        action = actions_map.get(event.get("httpMethod").upper(), "read")

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

        roles = []
        authorizer_info = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer_info.get("claims", {})
        roles = claims.get("roles", [])
        subject = claims.get("subject")

        return Operation(
            entity=entity,
            action=action,
            store_params=store_params,
            query_params=query_params,
            metadata_params=metadata_params,
            roles=roles,
            subject=subject,
        )

    def _convert_parameters(self, parameters):
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

    def split_params(self, parameters: dict):
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

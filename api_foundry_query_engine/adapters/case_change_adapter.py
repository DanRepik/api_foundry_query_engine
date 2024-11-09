from humps import camelize, decamelize

from api_foundry_query_engine.adapters.adapter import Adapter
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation

log = logger(__name__)


class CaseChangeAdapter(Adapter):
    """
    Handles changing case from snake to camel and back
    """

    def unmarshal(self, event) -> Operation:
        """
        Unmarshal the event in a tuple for processing

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - tuple: Tuple containing entity operation, store_params, query_params and metadata params.
        """
        operation = super().unmarshal(event)

        # determine case
        self.camel_case = (
            operation.metadata_params.get("_case", "snake") == "camel"
            or self.__check_camel_case(operation.store_params)
            or self.__check_camel_case(operation.query_params)
        )
        log.info(f"camel_case: {self.camel_case}")

        if self.camel_case:
            return Operation(
                path=operation.entity,
                action=operation.action,
                store_params=decamelize(operation.store_params),
                query_params=decamelize(operation.query_params),
                metadata_params=operation.metadata_params,
            )

        return operation

    def marshal(self, result: list[dict]):
        """
        Marshal the result into a event response

        Parameters:
        - result (list): the data set to return in the response

        Returns:
        - the event response
        """
        super().marshal(result)

        if not self.camel_case:
            return result

        converted_result = []
        for item in result:
            converted_result.append(camelize(item))

        # convert back to camel case if needed
        return converted_result

    def __check_camel_case(self, params: dict) -> bool:
        if params is not None:
            # check the keys for an upper case character
            for param in params:
                if (
                    param != param.lower()
                    and param != param.upper()
                    and "_" not in param
                ):
                    return True

        return False

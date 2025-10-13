import abc
from typing import Mapping, Optional

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.transactional_service import TransactionalService
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.services.service import Service

log = logger(__name__)


class Adapter(metaclass=abc.ABCMeta):
    service: Service
    config: Mapping[str, str]

    @classmethod
    def __subclasshook__(cls, __subclass: type) -> bool:
        return (
            hasattr(__subclass, "marshal")
            and callable(__subclass.marshal)
            and hasattr(__subclass, "umarshal")
            and callable(__subclass.unmarshal)
        )

    def __init__(
        self, config: Mapping[str, str] = {}, service: Optional[Service] = None
    ) -> None:
        self.config = config
        self.service = (
            service if service is not None else TransactionalService(config=self.config)
        )

    def unmarshal(self, event) -> Operation:
        """
        Unmarshal the event in a tuple for processing

        Parameters:
        - event (dict): Lambda event object.

        Returns:
        - Operation containing the entity, action, and parameters
        """
        raise NotImplementedError

    def marshal(self, result: list[dict]):
        """
        Marshal the result into a event response

        Parameters:
        - result (list): the data set to return in the response

        Returns:
        - the event response
        """
        return result

    def process_event(self, event):
        """
        Process Lambda event using a domain function.

        Parameters:
        - service_function (callable): The service function to be executed.
        - event (dict): Lambda event object.

        Returns:
        - any: Result of the domain function.
        """
        operation = self.unmarshal(event)

        result = self.service.execute(operation)
        log.debug(f"adapter result: {result}")

        return self.marshal(result)

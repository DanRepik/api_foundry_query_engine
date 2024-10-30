import abc
from typing import Union

from api_foundry_query_engine.connectors.connection import Connection
from api_foundry_query_engine.operation import Operation


class DAO(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, __subclass: type) -> bool:
        return hasattr(__subclass, "execute") and callable(__subclass.execute)

    def execute(
        self, connector: Connection, operation: Operation
    ) -> Union[list[dict], dict]:
        raise NotImplementedError


class DAOAdapter(DAO):
    def execute(
        self, connector: Connection, operation: Operation
    ) -> Union[list[dict], dict]:
        return super().execute(connector, operation)

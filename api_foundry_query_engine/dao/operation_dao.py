from typing import Union

from api_foundry_query_engine.dao.sql_custom_query_handler import SQLCustomQueryHandler
from api_foundry_query_engine.dao.sql_delete_query_handler import (
    SQLDeleteSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_insert_query_handler import (
    SQLInsertSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_select_query_handler import (
    SQLSelectSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_subselect_query_handler import (
    SQLSubselectSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_update_query_handler import (
    SQLUpdateSchemaQueryHandler,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.dao.dao import DAO
from api_foundry_query_engine.connectors.connection import Cursor
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.api_model import (
    get_schema_object,
    get_path_operation,
)
from api_foundry_query_engine.dao.sql_query_handler import SQLQueryHandler


class OperationDAO(DAO):
    """
    A class to handle database operations based on the provided
    Operation object.

    Attributes:
        operation (Operation): The operation to perform.
    """

    def __init__(self, operation: Operation, engine: str) -> None:
        """
        Initialize the OperationDAO with the provided Operation object.

        Args:
            operation (Operation): The operation to perform.
        """
        super().__init__()
        self.operation = operation
        self.engine = engine

    @property
    def query_handler(self) -> SQLQueryHandler:
        if not hasattr(self, "_query_handler"):
            path_operation = get_path_operation(
                self.operation.entity, self.operation.action
            )
            if path_operation:
                self._query_handler = SQLCustomQueryHandler(
                    self.operation, path_operation, self.engine
                )
                return self._query_handler

            schema_object = get_schema_object(self.operation.entity)
            if self.operation.action == "read":
                self._query_handler = SQLSelectSchemaQueryHandler(
                    self.operation, schema_object, self.engine
                )
            elif self.operation.action == "create":
                self._query_handler = SQLInsertSchemaQueryHandler(
                    self.operation, schema_object, self.engine
                )
            elif self.operation.action == "update":
                self._query_handler = SQLUpdateSchemaQueryHandler(
                    self.operation, schema_object, self.engine
                )
            elif self.operation.action == "delete":
                self._query_handler = SQLDeleteSchemaQueryHandler(
                    self.operation, schema_object, self.engine
                )
            else:
                raise ApplicationException(
                    400, f"Invalid operation action: {self.operation.action}"
                )
        return self._query_handler

    def execute(self, cursor: Cursor) -> Union[list[dict], dict]:
        """
        Execute the database operation based on the provided cursor.

        Args:
            cursor (Cursor): The database cursor.

        Returns:
            list[dict]: A list of dictionaries containing the results
            of the operation.
        """

        result = self.__fetch_record_set(self.query_handler, cursor)

        if self.operation.action == "read":
            if self.operation.metadata_params.get("count", False):
                return result[0]
            self.__fetch_many(result, cursor)
        elif self.operation.action in ["update", "delete"] and len(result) == 0:
            raise ApplicationException(400, "No records were modified")

        return result

    def __fetch_many(self, parent_set: list[dict], cursor: Cursor):
        if "properties" not in self.operation.metadata_params:
            return

        schema_object = get_schema_object(self.operation.entity)
        for name, relation in schema_object.relations.items():
            if relation.type == "object":
                continue

            child_set = self.__fetch_record_set(
                SQLSubselectSchemaQueryHandler(
                    self.operation, relation, self.query_handler  # type: ignore
                ),
                cursor,
            )
            if len(child_set) == 0:
                continue

            for parent in parent_set:
                parent[name] = []

            parents = {}
            for parent in parent_set:
                parents[parent[relation.parent_property]] = parent

            for child in child_set:
                parent_id = child[relation.child_property]
                parent = parents.get(parent_id)
                if parent:
                    parent[name].append(child)

    def __fetch_record_set(
        self, query_handler: SQLQueryHandler, cursor: Cursor
    ) -> list[dict]:
        sql = query_handler.sql
        if not sql:
            return []

        record_set = cursor.execute(
            sql, query_handler.placeholders, query_handler.selection_results
        )
        result = []
        for record in record_set:
            object = query_handler.marshal_record(record)
            result.append(object)

        return result

import traceback
from typing import Mapping, Optional

from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.service import ServiceAdapter
from api_foundry_query_engine.connectors.connection_factory import ConnectionFactory
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.api_model import (
    get_path_operation,
    get_schema_object,
)

log = logger(__name__)


class TransactionalService(ServiceAdapter):
    def __init__(self, config: Mapping[str, str]):
        super().__init__()
        self.config = config
        self.connection_factory = ConnectionFactory(config)

    def execute(self, operation: Operation) -> list[dict]:
        if operation.entity == "batch" and operation.action == "create":
            database = self._batch_database(operation)
        else:
            database = self._database(operation.entity, operation.action)
            if database is None:
                raise ApplicationException(500, f"Unknown operation: {operation.entity}")

        # Pass config to connection_factory if needed (future extension)
        connection = self.connection_factory.get_connection(database)

        try:
            result = OperationDAO(operation, connection.engine()).execute(connection)
            if operation.action != "read":
                connection.commit()
            if isinstance(result, dict):
                return [result]
            return result
        except Exception as error:
            log.error("transaction exception: %s", error)
            log.error("traceback: %s", traceback.format_exc())
            raise error
        finally:
            connection.close()

    @staticmethod
    def _database(entity, action) -> Optional[str]:
        path_operation = get_path_operation(entity, action)
        if path_operation:
            return path_operation.database
        schema_object = get_schema_object(entity)
        if schema_object:
            return schema_object.database
        return None

    def _batch_database(self, operation: Operation) -> str:
        """The database a batch runs against.

        "batch" is not an entity in the API model, so the database comes
        from the sub-operations. They share one connection, so they must all
        resolve to the same database. A sub-operation naming an unknown
        entity doesn't pick the database; it fails on its own inside the
        batch, where continueOnError decides what happens next.
        """
        operations = (operation.store_params or {}).get("operations")
        if not isinstance(operations, list) or not operations:
            raise ApplicationException(400, "Batch request must contain at least one operation")

        databases = {self._database(op.get("entity"), op.get("action")) for op in operations if isinstance(op, dict)}
        databases.discard(None)
        if not databases:
            raise ApplicationException(500, "Unknown operation: no batch operation names a known entity")
        if len(databases) > 1:
            raise ApplicationException(
                400,
                "Batch operations must all use the same database; got " + ", ".join(sorted(databases)),
            )
        return databases.pop()

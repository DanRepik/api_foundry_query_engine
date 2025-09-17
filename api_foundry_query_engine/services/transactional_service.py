import traceback
from typing import Mapping

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
        path_operation = get_path_operation(operation.entity, operation.action)
        if path_operation:
            database = path_operation.database
        else:
            schema_object = get_schema_object(operation.entity)
            if schema_object:
                database = schema_object.database
            else:
                raise ApplicationException(
                    500, f"Unknown operation: {operation.entity}"
                )

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
            log.error(f"transaction exception: {error}")
            log.error(f"traceback: {traceback.format_exc()}")
            raise error
        finally:
            connection.close()

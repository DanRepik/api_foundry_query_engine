import traceback

from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.services.service import ServiceAdapter
from api_foundry_query_engine.connectors.connection_factory import connection_factory
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.api_model import (
    get_path_operation,
    get_schema_object,
)

log = logger(__name__)


class TransactionalService(ServiceAdapter):
    def execute(self, operation: Operation):
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

        connection = connection_factory.get_connection(database)

        try:
            result = None
            cursor = connection.cursor()
            try:
                result = OperationDAO(operation, connection.engine()).execute(cursor)
            finally:
                cursor.close()
            if operation.action != "read":
                connection.commit()
            return result
        except Exception as error:
            log.error(f"transaction exception: {error}")
            log.error(f"traceback: {traceback.format_exc()}")
            raise error
        finally:
            connection.close()

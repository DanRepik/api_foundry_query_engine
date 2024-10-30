from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.connectors.connection import Connector

log = logger(__name__)


class OracleConnnector(Connector):
    def __init__(self, db_secret_name: str) -> None:
        super().__init__(db_secret_name)

    def close(self):
        pass

    def execute(self, cursor, sql: str, parameters: dict):
        from oracledb import Error, IntegrityError, ProgrammingError

        log.debug(f"sql: {sql}, parameters: {parameters}")
        try:
            cursor.execute(sql, parameters)
        except IntegrityError as err:
            (error,) = err.args
            raise ApplicationException(409, error.message)
        except ProgrammingError as err:
            (error,) = err.args
            raise ApplicationException(400, error.message)
        except Error as err:
            (error,) = err.args
            raise ApplicationException(500, error.message)

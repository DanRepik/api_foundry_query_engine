from api_foundry_query_engine.connectors.connection import Connection, Cursor
from api_foundry_query_engine.utils.logger import logger

# Initialize the logger
log = logger(__name__)


class PostgresCursor(Cursor):
    def __init__(self, cursor):
        self.__cursor = cursor

    def execute(self, sql: str, params: dict, selection_results: dict) -> list[dict]:
        """
        Execute SQL statements on the PostgreSQL database.

        Parameters:
        - cursor: The database cursor.
        - sql (str): The SQL statement to execute.
        - params (dict): Parameters to be used in the SQL statement.
        - selection_results (dict): Mapping of result columns.

        Returns:
        - list[dict]: List of result records as dictionaries.

        Raises:
        - AppException: Custom exception for handling database-related errors.
        """
        from psycopg2 import Error, IntegrityError, ProgrammingError

        log.info("sql: %s", sql)

        try:
            # Execute the SQL statement with parameters
            self.__cursor.execute(sql, params)
            result = []
            for record in self.__cursor:
                # Convert record tuple to dictionary using selection_results
                result.append(
                    {col: value for col, value in zip(selection_results, record)}
                )

            return result
        except IntegrityError as err:
            # Handle integrity constraint violation (e.g., duplicate key)
            from api_foundry_query_engine.utils.app_exception import (
                ApplicationException,
            )

            raise ApplicationException(409, err.pgerror)
        except ProgrammingError as err:
            # Handle programming errors (e.g., syntax error in SQL)
            from api_foundry_query_engine.utils.app_exception import (
                ApplicationException,
            )

            raise ApplicationException(400, err.pgerror)
        except Error as err:
            # Handle other database errors
            from api_foundry_query_engine.utils.app_exception import (
                ApplicationException,
            )

            raise ApplicationException(500, err.pgerror)

    def close(self):
        self.__cursor.close()


class PostgresConnection(Connection):
    """
    PostgreSQL database connection wrapper.

    Supports two configuration formats:
    1. DSN-based (preferred for testing with fixture_foundry):
       {"dsn": "postgresql://user:pass@host:port/dbname"}

    2. Individual parameters (for production AWS Secrets Manager):
       {"host": "...", "port": 5432, "database": "...", "username": "...", "password": "..."}

    The get_connection() method prioritizes DSN if present, otherwise builds connection
    from individual parameters.
    """

    def __init__(self, db_config: dict) -> None:
        super().__init__(db_config)
        self.__connection = self.get_connection()

    def cursor(self) -> Cursor:
        return PostgresCursor(self.__connection.cursor())

    def close(self):
        self.__connection.close()

    def commit(self):
        self.__connection.commit()

    def rollback(self):
        self.__connection.rollback()

    def get_connection(self):
        """
        Get a connection to the PostgreSQL database.

        Parameters:
        - schema (str, optional): The database schema to set for the
            connection.

        Returns:
        - connection: A connection to the PostgreSQL database.
        """
        from psycopg2 import connect

        # If DSN is provided, use it directly (simplifies fixture_foundry integration)
        if "dsn" in self.db_config:
            log.info("Connecting using DSN: %s", self.db_config["dsn"])
            return connect(self.db_config["dsn"])

        # Otherwise, build connection from individual parameters
        dbname = self.db_config["database"]
        user = self.db_config["username"]
        password = self.db_config["password"]
        host = self.db_config.get("host", "localhost")
        port = self.db_config.get("port", 5432)
        additional_config = self.db_config.get("configuration", {})

        # Merge additional configuration parameters with the main connection parameters
        connection_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port,
        }

        connection_params.update(additional_config)

        log.info(
            f"connection_params: dbname: {dbname}, user: {user}, host: {host}, port: {port}"
        )

        # Create a connection to the PostgreSQL database
        return connect(**connection_params)

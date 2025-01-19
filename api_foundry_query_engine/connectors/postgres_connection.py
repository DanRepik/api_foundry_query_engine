from api_foundry_query_engine.connectors.connection import Connection, Cursor
from api_foundry_query_engine.utils.logger import logger

# Initialize the logger
log = logger(__name__)


class PostgresCursor(Cursor):
    def __init__(self, cursor):
        self.__cursor = cursor

    def execute(self, sql: str, parameters: dict, result_columns: list[str]) -> list:
        """
        Execute SQL statements on the PostgreSQL database.

        Parameters:
        - cursor: The database cursor.
        - sql (str): The SQL statement to execute.
        - parameters (dict): Parameters to be used in the SQL statement.

        Returns:
        - None

        Raises:
        - AppException: Custom exception for handling database-related errors.
        """
        from psycopg2 import Error, IntegrityError, ProgrammingError

        log.info(f"sql: {sql}")

        try:
            # Execute the SQL statement with parameters
            self.__cursor.execute(sql, parameters)
            result = []
            for record in self.__cursor:
                # Convert record tuple to dictionary using result_columns
                result.append(
                    {col: value for col, value in zip(result_columns, record)}
                )

            return result
        except IntegrityError as err:
            # Handle integrity constraint violation (e.g., duplicate key)
            raise Exception(409, err.pgerror)
        except ProgrammingError as err:
            # Handle programming errors (e.g., syntax error in SQL)
            raise Exception(400, err.pgerror)
        except Error as err:
            # Handle other database errors
            raise Exception(500, err.pgerror)

    def close(self):
        self.__cursor.close()


class PostgresConnection(Connection):
    def __init__(self, db_config: dict) -> None:
        super().__init__(db_config)
        self.__connection = self.get_connection()

    def cursor(self) -> Cursor:
        return PostgresCursor(self.__connection.cursor())

    def close(self):
        self.__connection.close()

    def commit(self):
        self.__connection.commit()

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

        dbname = self.db_config["dbname"]
        user = self.db_config["username"]
        password = self.db_config["password"]
        host = self.db_config["host"]
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

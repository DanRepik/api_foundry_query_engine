from api_foundry_query_engine.connectors.connection import Connection, Cursor
from api_foundry_query_engine.utils.logger import logger
import boto3
import time

# Initialize the logger
log = logger(__name__)


class AthenaCursor(Cursor):
    def __init__(self, athena_client, db_config):
        self.athena_client = athena_client
        self.db_config = db_config

    def execute(self, sql: str, parameters: dict, result_columns: list[str]) -> list:
        """
        Execute a SQL statement on the Athena database.

        Parameters:
        - sql (str): The SQL query to execute.
        - parameters (dict): Parameters for the query (currently unused; substitute manually in the query).
        - result_columns (list[str]): Column names for the results.

        Returns:
        - list[dict]: Query results as a list of dictionaries.
        """
        # Substitute parameters into the query manually (Athena doesn't support placeholders)
        for key, value in parameters.items():
            placeholder = f":{key}"
            if isinstance(value, str):
                value = f"'{value}'"  # Wrap strings in quotes
            sql = sql.replace(placeholder, str(value))

        log.info(f"Executing query: {sql}")

        # Start the query execution
        response = self.athena_client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": self.db_config["database"]},
            ResultConfiguration={"OutputLocation": self.db_config["output_location"]},
        )
        query_execution_id = response["QueryExecutionId"]
        log.info(f"Query execution started: {query_execution_id}")

        # Wait for the query to complete
        while True:
            status_response = self.athena_client.get_query_execution(
                QueryExecutionId=query_execution_id
            )
            status = status_response["QueryExecution"]["Status"]["State"]

            if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                break
            time.sleep(2)

        if status == "FAILED":
            raise Exception(
                f"Query failed: {status_response['QueryExecution']['Status']['StateChangeReason']}"
            )
        elif status == "CANCELLED":
            raise Exception("Query was cancelled.")

        # Fetch results
        results_response = self.athena_client.get_query_results(
            QueryExecutionId=query_execution_id
        )
        rows = results_response["ResultSet"]["Rows"]

        # Convert rows to dictionaries
        result = []
        for row in rows[1:]:  # Skip the first row (header row)
            record = {
                col: value.get("VarCharValue", None)
                for col, value in zip(result_columns, row["Data"])
            }
            result.append(record)

        return result

    def close(self):
        log.info("Closing Athena cursor (no persistent connection to close).")


class AthenaConnection(Connection):
    def __init__(self, db_config: dict) -> None:
        """
        Initialize the AthenaConnection with the given configuration.

        Parameters:
        - db_config (dict): A dictionary containing Athena connection configuration.
          Required keys:
            - 'region': AWS region of the Athena service.
            - 'output_location': S3 bucket location for query results.
            - 'database': Athena database name.
        """
        super().__init__(db_config)
        self.athena_client = self.get_athena_client()

    def engine(self) -> str:
        return "athena"

    def cursor(self) -> Cursor:
        return AthenaCursor(self.athena_client, self.db_config)

    def commit(self):
        # Athena queries are read-only; no commit operation is required
        log.info("Athena does not support transactions. Commit is a no-op.")

    def close(self):
        # Athena uses a stateless API, so there's nothing to close
        log.info("Closing Athena connection (no persistent connection to close).")

    def get_athena_client(self):
        """
        Get a Boto3 client for Athena.
        """
        region = self.db_config.get("region")
        if not region:
            raise ValueError("Athena configuration must include 'region'.")
        return boto3.client("athena", region_name=region)

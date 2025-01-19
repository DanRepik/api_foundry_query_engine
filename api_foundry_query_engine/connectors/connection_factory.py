import boto3
import json
import os

from api_foundry_query_engine.connectors.connection import Connection
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class ConnectionFactory:
    db_config_map: dict[str, dict]

    def __init__(self):
        self.db_config_map = dict()

    def get_connection(self, database: str) -> Connection:
        """
        Factory function to create a database connector based on the
        specified engine and schema.

        Args:
        - engine (str): The database engine type
                ('postgres', 'oracle', or 'mysql').
        - schema (str): The schema for the database.

        Returns:
        - Connector: An instance of the appropriate Connector subclass.
        """

        # Get the secret name based on the engine and database from the secrets map
        log.info(f"database: {database}")
        db_config = self.db_config_map.get(database)
        if not db_config:
            secret_name = json.loads(os.environ.get("SECRETS", "{}")).get(database)
            log.debug(f"secret_name: {secret_name}")

            if secret_name:
                db_config = self.__get_secret(secret_name)
            else:
                raise ValueError(f"Secret not found for database: {database}")

        engine = db_config.get("engine")
        if not engine:
            raise ApplicationException(
                500, "Database 'engine' is not defined in the secret."
            )

        if engine == "postgres":
            from .postgres_connection import PostgresConnection

            return PostgresConnection(db_config)

        # Add support for other engines here if needed in the future

        raise ValueError(f"Unsupported database engine: {engine}")

    def __get_secret(self, db_secret_name: str):
        """
        Get the secret from AWS Secrets Manager.

        Parameters:
        - db_secret_name (str): The name of the AWS Secrets Manager secret.

        Returns:
        - dict: The database configuration obtained from the secret.
        """
        endpoint_url = os.environ.get("AWS_ENDPOINT_URL")  # LocalStack endpoint
        sts_client = boto3.client("sts", endpoint_url=endpoint_url)

        secret_account_id = os.environ.get("SECRET_ACCOUNT_ID", None)
        log.debug(f"secret_account_id: {secret_account_id}")

        if secret_account_id:
            # If a secret account ID is provided, assume a role in that account
            secret_role = os.environ.get("ROLE_NAME", None)
            assume_role_response = sts_client.assume_role(
                RoleArn=f"arn:aws:iam::{secret_account_id}:role/{secret_role}",
                RoleSessionName="AssumeRoleSession",
            )

            credentials = assume_role_response["Credentials"]

            secretsmanager = boto3.client(
                "secretsmanager",
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                endpoint_url=endpoint_url,
            )
        else:
            # If no secret account ID is provided, use the default account
            log.info(f"endpoint_url: {endpoint_url}")
            secretsmanager = boto3.client(
                "secretsmanager",
                #                endpoint_url=endpoint_url,
            )

        # Get the secret value from AWS Secrets Manager
        log.info(f"db_secret_name: {db_secret_name}")
        db_secret = secretsmanager.get_secret_value(SecretId=db_secret_name)
        log.debug(f"loading secret name: {db_secret}")

        # Return the parsed JSON secret string
        return json.loads(db_secret.get("SecretString"))


connection_factory = ConnectionFactory()

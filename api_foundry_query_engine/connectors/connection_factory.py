from typing import Callable, Mapping, Tuple, Type
import boto3
import json

from api_foundry_query_engine.connectors.connection import Connection, parse_engine
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


def _load_postgres_connection() -> Type[Connection]:
    from api_foundry_query_engine.connectors.postgres_connection import PostgresConnection

    return PostgresConnection


def _load_data_api_connection() -> Type[Connection]:
    from api_foundry_query_engine.connectors.data_api_connection import DataApiConnection

    return DataApiConnection


# (dialect, driver) -> a loader returning the Connection subclass to
# instantiate. A function rather than the class itself so each connector's
# module (and its own dependencies, e.g. psycopg2) is only imported once a
# config value actually selects it. Add new dialect/driver combinations
# here rather than growing an if/elif chain.
CONNECTOR_REGISTRY: dict[Tuple[str, str], Callable[[], Type[Connection]]] = {
    ("postgres", "psycopg2"): _load_postgres_connection,
    ("postgres", "data-api"): _load_data_api_connection,
}


class ConnectionFactory:
    db_config_map: dict[str, dict]
    config: Mapping[str, str]

    def __init__(self, config: Mapping[str, str] = {}):
        self.db_config_map = dict()
        self.config = config

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
        log.info("database: %s", database)
        db_config = self.db_config_map.get(database)
        if not db_config:
            # A <DATABASE>_DATA_API_CLUSTER_ARN config value selects the
            # RDS Data API connector and, like the DSN branch below, skips
            # Secrets Manager entirely -- the Data API looks up the
            # credentials server-side from secret_arn, so this Lambda
            # never needs secretsmanager:GetSecretValue or a password in
            # its own environment at all (not even to work around VPC
            # egress, since a Data API Lambda isn't VPC-attached).
            data_api_cluster_arn = self.config.get(f"{database.upper()}_DATA_API_CLUSTER_ARN")
            if data_api_cluster_arn:
                db_config = {
                    "engine": "postgres:data-api",
                    "resource_arn": data_api_cluster_arn,
                    "secret_arn": self.config.get(f"{database.upper()}_DATA_API_SECRET_ARN"),
                    "database": self.config.get(f"{database.upper()}_DATA_API_DATABASE"),
                }
                schema = self.config.get(f"{database.upper()}_DATA_API_SCHEMA")
                if schema:
                    db_config["schema"] = schema
                endpoint_url = self.config.get("AWS_ENDPOINT_URL")  # LocalStack endpoint
                if endpoint_url:
                    db_config["endpoint_url"] = endpoint_url
            else:
                # A <DATABASE>_DSN config value (e.g. CONTRACT_DB_DSN) skips
                # Secrets Manager entirely. This matters for a Lambda that's
                # VPC-attached for private database access but has no route
                # to the Secrets Manager API (no NAT gateway, no interface
                # endpoint) -- the SECRETS/get_secret_value path would just
                # hang. PostgresConnection already accepts a raw "dsn" key.
                dsn = self.config.get(f"{database.upper()}_DSN")
                if dsn:
                    db_config = {"engine": self.config.get(f"{database.upper()}_ENGINE", "postgres"), "dsn": dsn}
                else:
                    # Use config dict for secrets
                    secrets_map = self.config.get("SECRETS", {})
                    if isinstance(secrets_map, str):
                        secrets_map = json.loads(secrets_map)
                    secret_name = secrets_map.get(database)
                    log.debug("secret_name: %s", secret_name)

                    if secret_name:
                        db_config = self.__get_secret(secret_name)
                    else:
                        raise ValueError(f"Secret not found for database: {database}")

        engine = db_config.get("engine")
        if not engine:
            raise ApplicationException(500, "Database 'engine' is not defined in the secret.")

        dialect, driver = parse_engine(engine)
        loader = CONNECTOR_REGISTRY.get((dialect, driver))
        if loader is None:
            raise ValueError(
                f"Unsupported database engine: {engine!r} (dialect={dialect!r}, driver={driver!r}). "
                f"Registered: {sorted(CONNECTOR_REGISTRY.keys())}"
            )
        return loader()(db_config)

    def __get_secret(self, db_secret_name: str):
        """
        Get the secret from AWS Secrets Manager.

        Parameters:
        - db_secret_name (str): The name of the AWS Secrets Manager secret.

        Returns:
        - dict: The database configuration obtained from the secret.
        """
        if self.config.get(db_secret_name):
            return self.config.get(db_secret_name)

        endpoint_url = self.config.get("AWS_ENDPOINT_URL")  # LocalStack endpoint
        sts_client = boto3.client("sts", endpoint_url=endpoint_url)

        secret_account_id = self.config.get("SECRET_ACCOUNT_ID", None)
        log.debug("secret_account_id: %s", secret_account_id)

        if secret_account_id:
            # If a secret account ID is provided, assume a role in that account
            secret_role = self.config.get("ROLE_NAME", None)
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
            log.info("endpoint_url: %s", endpoint_url)
            secretsmanager = boto3.client(
                "secretsmanager",
                endpoint_url=endpoint_url,
            )

        # Get the secret value from AWS Secrets Manager
        log.info("db_secret_name: %s", db_secret_name)
        db_secret = secretsmanager.get_secret_value(SecretId=db_secret_name)
        log.debug("loading secret name: %s", db_secret)

        # Return the parsed JSON secret string
        return json.loads(db_secret.get("SecretString"))

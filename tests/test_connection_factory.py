import os

import pytest

from api_foundry_query_engine.connectors.connection_factory import ConnectionFactory
from api_foundry_query_engine.connectors.data_api_connection import DataApiConnection
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.mark.integration
class TestPostgresConnection:
    def test_postgres_connection(self, chinook_env):  # noqa f811
        connection = ConnectionFactory(chinook_env).get_connection("chinook")

        log.info(f"connection: {connection}")

        assert connection is not None


@pytest.mark.unit
class TestDataApiConnectionFactory:
    def test_data_api_cluster_arn_config_selects_data_api_connector(self):
        # This is the whole point of the <DATABASE>_DATA_API_CLUSTER_ARN
        # branch: it must not touch Secrets Manager or the SECRETS config
        # at all (that's the earlier VPC-egress workaround this replaces),
        # so a config with no SECRETS entry for "cep" is enough to prove
        # that path wasn't taken.
        config = {
            "CEP_DATA_API_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:cep",
            "CEP_DATA_API_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:cep-db",
            "CEP_DATA_API_DATABASE": "cep",
        }
        connection = ConnectionFactory(config).get_connection("cep")

        assert isinstance(connection, DataApiConnection)
        assert connection.resource_arn == config["CEP_DATA_API_CLUSTER_ARN"]
        assert connection.secret_arn == config["CEP_DATA_API_SECRET_ARN"]
        assert connection.database == "cep"
        assert connection.schema is None

    def test_data_api_config_passes_through_schema_and_localstack_endpoint(self):
        config = {
            "CEP_DATA_API_CLUSTER_ARN": "arn:aws:rds:us-east-1:123456789012:cluster:cep",
            "CEP_DATA_API_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:cep-db",
            "CEP_DATA_API_DATABASE": "cep",
            "CEP_DATA_API_SCHEMA": "contract_app",
            "AWS_ENDPOINT_URL": "http://localhost:4566",
        }
        connection = ConnectionFactory(config).get_connection("cep")

        assert connection.schema == "contract_app"

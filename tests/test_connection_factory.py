import pytest

from api_foundry_query_engine.connectors.connection_factory import ConnectionFactory
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


@pytest.mark.integration
class TestPostgresConnection:
    def test_postgres_connection(self, chinook_env):  # noqa f811
        connection = ConnectionFactory(chinook_env).get_connection("chinook")

        log.info(f"connection: {connection}")

        assert connection is not None

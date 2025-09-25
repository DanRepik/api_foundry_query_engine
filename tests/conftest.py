import json
import pytest
import psycopg2

from pathlib import Path

from api_foundry_query_engine.utils.api_model import set_api_model

from .infrastructure_fixtures import deploy  # noqa F401
from .infrastructure_fixtures import exec_sql_file
from .infrastructure_fixtures import postgres  # noqa F401
from .infrastructure_fixtures import localstack  # noqa F401
from .infrastructure_fixtures import test_network  # noqa F401


@pytest.fixture(scope="session")
def chinook_db(postgres):  # noqa: F811
    # Locate DDL files (project root is one parent up from this test file: backend/tests/ -> farm_market/)
    project_root = Path(__file__).resolve().parents[1]
    chinook_sql = project_root / "tests" / "Chinook_Postgres.sql"

    assert chinook_sql.exists(), f"Missing {chinook_sql}"

    # Connect and load schemas
    conn = psycopg2.connect(postgres["dsn"])
    try:
        conn.autocommit = True  # allow full scripts to run without transaction issues
        exec_sql_file(conn, chinook_sql)

        yield postgres

    finally:
        conn.close()


@pytest.fixture(scope="session")
def chinook_api():
    # Load API specification from YAML file
    api_spec_path = Path(__file__).resolve().parents[1] / "tests" / "chinook_api.yaml"
    assert api_spec_path.exists(), f"Missing {api_spec_path}"
    yield api_spec_path.read_text()


@pytest.fixture(scope="session")
def chinook_env(chinook_db, chinook_api):
    secrets = {"chinook": "chinook_secret"}

    env = {
        "API_SPEC": chinook_api,
        "SECRETS": json.dumps(secrets),
        "chinook_secret": {
            "engine": "postgres",
            "host": "localhost",
            "port": chinook_db["host_port"],
            "username": chinook_db["username"],
            "password": chinook_db["password"],
            "database": chinook_db["database"],
            "dsn": chinook_db["dsn"],
        },
    }

    set_api_model(env)

    yield env

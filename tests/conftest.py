import json
import pytest
import psycopg2
from typing import Iterable

from pathlib import Path

import yaml

from api_foundry_query_engine.utils import api_model as api_model_module
from api_foundry_query_engine.utils.api_model import APIModel, set_api_model

from fixture_foundry import deploy
from fixture_foundry import deploy  # noqa F401
from fixture_foundry import exec_sql_file
from fixture_foundry import postgres  # noqa F401
from fixture_foundry import localstack  # noqa F401
from fixture_foundry import container_network  # noqa F401


DOCKER_DEPENDENT_FIXTURES = {
    "container_network",
    "localstack",
    "postgres",
    "chinook_db",
    "chinook_env",
}


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        try:
            client.ping()
        finally:
            client.close()
        return True
    except Exception:
        return False


def _uses_any_fixture(fixtures: Iterable[str], names: set[str]) -> bool:
    return bool(set(fixtures).intersection(names))


def pytest_collection_modifyitems(config, items):
    if _docker_available():
        return

    skip_docker = pytest.mark.skip(reason="Skipping Docker-dependent test: Docker daemon is not accessible.")
    for item in items:
        if _uses_any_fixture(getattr(item, "fixturenames", []), DOCKER_DEPENDENT_FIXTURES):
            item.add_marker(skip_docker)


@pytest.fixture(scope="session")
def chinook_db(postgres):  # noqa: F811
    # Locate DDL files (project root is one parent up from this test file
    project_root = Path(__file__).resolve().parents[1]
    chinook_sql = project_root / "tests" / "Chinook_Postgres.sql"

    assert chinook_sql.exists(), f"Missing {chinook_sql}"

    # Connect and load schemas
    conn = psycopg2.connect(postgres["dsn"])
    try:
        # allow full scripts to run without transaction issues
        conn.autocommit = True
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


@pytest.fixture(scope="session")
def chinook_api_model(chinook_api):
    return APIModel(yaml.safe_load(chinook_api))


@pytest.fixture(autouse=True)
def _isolate_api_model(request):
    """Keep the module-level api_model singleton from leaking between tests.

    Several tests install their own model (or a stand-in object) directly on
    api_model_module.api_model, and set_api_model() -- which chinook_env
    calls only once per session -- is a no-op while any model is set. Without
    this, a Chinook test ran against whichever model the previous test left
    behind, so its permissions, schema objects and path operations depended
    on test order. Every test now starts from the model it expects and leaves
    the singleton as it found it.
    """
    saved = api_model_module.api_model
    if "chinook_env" in request.fixturenames:
        api_model_module.api_model = request.getfixturevalue("chinook_api_model")
    yield
    api_model_module.api_model = saved


import json
import yaml
import pytest
import psycopg2

from pathlib import Path

import pulumi_aws as aws
import pulumi.automation as auto

from api_foundry_query_engine.utils.api_model import set_api_model

from .postgres_fixtures import _exec_sql_file, postgres_container, postgres_container_no_teardown
from .localstack_fixture import localstack
from .automation_helpers import deploy_stack, deploy_stack_no_teardown

@pytest.fixture(scope="session")
def chinook_db(postgres_container):
    # Locate DDL files (project root is one parent up from this test file: backend/tests/ -> farm_market/)
    project_root = Path(__file__).resolve().parents[1]
    chinook_sql = project_root / "tests" / "Chinook_Postgres.sql"

    assert chinook_sql.exists(), f"Missing {chinook_sql}"

    # Connect and load schemas
    conn = psycopg2.connect(postgres_container["dsn"])
    try:
        conn.autocommit = True  # allow full scripts to run without transaction issues
        _exec_sql_file(conn, chinook_sql)

        yield postgres_container

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

    secrets = {
        "chinook": "chinook_secret"
    }

    env = {
        "API_SPEC": chinook_api,
        "SECRETS": json.dumps(secrets),
        "chinook_secret": {
            "engine": "postgres",
            "host": chinook_db["host"],
            "port": chinook_db["port"],
            "username": chinook_db["user"],
            "password": chinook_db["password"],
            "database": chinook_db["database"],
            "dsn": chinook_db["dsn"],
        }
    }

    set_api_model(env)

    yield env

@pytest.fixture
def chinook_api_model(chinook_env):
    set_api_model(chinook_env)
    yield chinook_env


@pytest.fixture(scope="session")
def market_stack(localstack, chinook_model):
    def pulumi_program():
        # Extract connection info from chinook_model
        conn_info = {
            "engine": "postgresql",
            "host": chinook_model["host"],
            "port": chinook_model["port"],
            "user": chinook_model["user"],
            "password": chinook_model["password"],
            "database": chinook_model["database"],
            "dsn": chinook_model["dsn"],
        }

        secret = aws.secretsmanager.Secret("test-secret", name="test/secret")
        secret_value = aws.secretsmanager.SecretVersion(
            "test-secret-value",
            secret_id=secret.id,
            secret_string=json.dumps(conn_info),
        )

    stack_name = "test"
    project_name = "query-engineå"
    aws_config = {
        "aws:region": auto.ConfigValue(localstack["region"]),
        "aws:accessKey": auto.ConfigValue("test"),
        "aws:secretKey": auto.ConfigValue("test"),
        # Point AWS services used by the provider to LocalStack and relax validations
        "aws:endpoints": auto.ConfigValue(json.dumps([{
            "secretsmanager": localstack["endpoint_url"],
            "sts": localstack["endpoint_url"],
        }])),
        "aws:skipCredentialsValidation": auto.ConfigValue("true"),
        "aws:skipRegionValidation": auto.ConfigValue("true"),
        "aws:skipRequestingAccountId": auto.ConfigValue("true"),
        "aws:skipMetadataApiCheck": auto.ConfigValue("true"),
        # In case HTTP endpoints are used without TLS
        "aws:insecure": auto.ConfigValue("true"),
        # Useful if S3 is ever used in tests with LocalStack
        "aws:s3UsePathStyle": auto.ConfigValue("true"),
    }
    
    stack = auto.create_or_select_stack(stack_name=stack_name, project_name=project_name, program=pulumi_program)
    try:
        # Clean any prior state-backed resources so LocalStack restarts don't leave stale ARNs
        try:
            stack.destroy(on_output=print)
        except Exception:
            pass
        stack.set_all_config(aws_config)
        # Refresh to detect drift/missing resources in a new LocalStack instance
        try:
            stack.refresh(on_output=print)
        except Exception:
            # Proceed even if refresh fails; up will reconcile
            pass
        stack.up(on_output=print)

        outputs = stack.outputs()
        yield outputs

    finally:
        stack.destroy()
        stack.workspace.remove_stack(stack_name)

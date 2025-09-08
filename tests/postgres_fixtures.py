import time
from typing import Generator
from pathlib import Path

import docker
import psycopg2
import pytest

def _exec_sql_file(conn, sql_path: Path):
    sql_text = sql_path.read_text(encoding="utf-8")
    # Execute entire script (supports DO $$ ... $$ blocks and multiple statements)
    with conn.cursor() as cur:
        cur.execute(sql_text)

@pytest.fixture(scope="session")
def postgres_container() -> Generator[dict, None, None]:
    """
    Starts a PostgreSQL container and yields connection info.
    Uses a random host port mapped to 5432.
    """
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        assert False, f"Docker not available: {e}"

    user = "test_user"
    password = "test_password"
    database = "chinook"
    image = "postgis/postgis:16-3.4"

    container = client.containers.run(
        image,
        name=f"query-engine-test-{int(time.time())}",
        environment={
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": database,
        },
        ports={"5432/tcp": 0},  # random host port
        detach=True,
    )

    try:
        # Resolve mapped port
        host = "127.0.0.1"
        host_port = None
        deadline = time.time() + 60
        while time.time() < deadline:
            container.reload()
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            mapping = ports.get("5432/tcp")
            if mapping and mapping[0].get("HostPort"):
                host_port = int(mapping[0]["HostPort"])
                break
            time.sleep(0.25)

        if not host_port:
            raise RuntimeError("Failed to map Postgres port")

        # Wait for readiness
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                conn = psycopg2.connect(
                    dbname=database, user=user, password=password, host=host, port=host_port
                )
                conn.close()
                break
            except Exception:
                time.sleep(0.5)

        yield {
            "host": host,
            "port": host_port,
            "user": user,
            "password": password,
            "database": database,
            "dsn": f"postgresql://{user}:{password}@{host}:{host_port}/{database}",
        }
    finally:
        try:
            container.stop(timeout=5)
        except Exception:
            pass
        try:
            container.remove(v=True, force=True)
        except Exception:
            pass

@pytest.fixture(scope="session")
def postgres_container_no_teardown() -> Generator[dict, None, None]:
    """
    Starts a PostgreSQL container and yields connection info.
    Uses a random host port mapped to 5432.
    """
    try:
        client = docker.from_env()
        client.ping()
    except Exception as e:
        assert False, f"Docker not available: {e}"

    user = "test"
    password = "test"
    database = "testdb"
    image = "postgis/postgis:16-3.4"

    container = client.containers.run(
        image,
        name=f"pg-freemium-test-{int(time.time())}",
        environment={
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": database,
        },
        ports={"5432/tcp": None},  # random host port
        detach=True,
    )

    # Resolve mapped port
    host = "127.0.0.1"
    host_port = None
    deadline = time.time() + 60
    while time.time() < deadline:
        container.reload()
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
        mapping = ports.get("5432/tcp")
        if mapping and mapping[0].get("HostPort"):
            host_port = int(mapping[0]["HostPort"])
            break
        time.sleep(0.25)

    if not host_port:
        raise RuntimeError("Failed to map Postgres port")

    # Wait for readiness
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(
                dbname=database, user=user, password=password, host=host, port=host_port
            )
            conn.close()
            break
        except Exception:
            time.sleep(0.5)

    yield {
        "host": host,
        "port": host_port,
        "user": user,
        "password": password,
        "database": database,
        "dsn": f"postgresql://{user}:{password}@{host}:{host_port}/{database}",
    }

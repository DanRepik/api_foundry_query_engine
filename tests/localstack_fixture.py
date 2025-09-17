"""
Pytest fixture to run LocalStack in a Docker container for integration tests.

Usage in tests:

    def test_something(localstack):
        endpoint = localstack["endpoint_url"]
        # e.g., boto3.client("secretsmanager", endpoint_url=endpoint, region_name=localstack["region"]) ...

CLI options:
    --localstack-image     Docker image (default: localstack/localstack:latest)
    --localstack-services  Comma list of services (default: secretsmanager)

Environment:
    Set AWS_REGION and AWS_DEFAULT_REGION for convenience (default: us-east-1).
"""
from __future__ import annotations

import os
import time
from typing import Dict, Generator, Optional

import pytest

try:
    import docker  # type: ignore
    from docker.errors import DockerException  # type: ignore
except Exception:  # pragma: no cover - handled in fixture with skip
    docker = None  # type: ignore
    DockerException = Exception  # type: ignore

import requests


os.environ["PULUMI_BACKEND_URL"] = "file://~"
DEFAULT_REGION = os.environ.get(
    "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
)


def _wait_for_localstack(endpoint: str, timeout: int = 90) -> None:
    """Wait until LocalStack health endpoint reports ready or timeout expires."""
    url_candidates = [
        f"{endpoint}/_localstack/health",  # modern health endpoint
        f"{endpoint}/health",  # legacy fallback
    ]

    start = time.time()
    last_err: Optional[str] = None
    while time.time() - start < timeout:
        for url in url_candidates:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception:
                        data = {}
                    # Heuristics: consider healthy if initialized true or services reported
                    if isinstance(data, dict):
                        if data.get("initialized") is True:
                            return
                        if "services" in data:
                            # services dict often present when up
                            return
                    else:
                        return
            except Exception as e:  # noqa: PERF203 - simple polling loop
                last_err = str(e)
                time.sleep(0.5)
                continue
        time.sleep(0.5)
    raise RuntimeError(
        f"Timed out waiting for LocalStack at {endpoint} (last_err={last_err})"
    )


@pytest.fixture(scope="session")
def localstack(request: pytest.FixtureRequest) -> Generator[Dict[str, str], None, None]:
    """
    Session-scoped fixture that runs a LocalStack container.

    Yields a dict with:
      - endpoint_url: Edge endpoint URL (e.g., http://127.0.0.1:4566)
      - region: AWS region configured
      - container_id: Docker container id
      - services: comma list of services configured
    """
    teardown: bool = request.config.getoption("--teardown").lower() == "true"
    port: int = int(request.config.getoption("--localstack-port"))
    image: str = request.config.getoption("--localstack-image")
    services: str = request.config.getoption("--localstack-services")
    timeout: int = int(request.config.getoption("--localstack-timeout"))

    if docker is None:
        assert False, "Docker SDK not available: skipping LocalStack-dependent tests"

    try:
        client = docker.from_env()
    except DockerException:
        assert False, "Docker daemon not available: skipping LocalStack-dependent tests"

    # Pull image to ensure availability
    try:
        client.images.pull(image)
    except Exception:
        # If pull fails, we may already have it locally — proceed
        pass

    # Publish edge port on a random host port to avoid collisions
    ports = {"4566/tcp": None if port == 0 else port}
    env = {
        "SERVICES": services,
        "LS_LOG": "warn",
        "AWS_DEFAULT_REGION": DEFAULT_REGION,
        # Speed-ups for CI; optional
        "DISABLE_CORS_CHECKS": "1",
    }

    container = client.containers.run(
        image,
        detach=True,
        environment=env,
        ports=ports,
        name=None,  # let Docker assign a random name
        tty=False,
        auto_remove=True,
    )

    if port == 0:
        # Resolve host port assigned for edge, with retries to avoid race condition
        host_port = None
        max_attempts = 10
        for attempt in range(max_attempts):
            container.reload()
            try:
                port_info = container.attrs["NetworkSettings"]["Ports"]["4566/tcp"]
                if port_info and port_info[0] and port_info[0].get("HostPort"):
                    host_port = int(port_info[0]["HostPort"])  # type: ignore[arg-type]
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if host_port is None:
            # Clean up if mapping not available
            try:
                container.stop(timeout=5)
            finally:
                raise RuntimeError(
                    "Failed to determine LocalStack edge port after retries"
                )
    else:
        host_port = port

    endpoint = f"http://127.0.0.1:{host_port}"

    # Set common AWS envs for child code that relies on defaults
    os.environ.setdefault("AWS_REGION", DEFAULT_REGION)
    os.environ.setdefault("AWS_DEFAULT_REGION", DEFAULT_REGION)
    os.environ.setdefault(
        "AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID", "test")
    )
    os.environ.setdefault(
        "AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
    )

    # Wait for the health endpoint to be ready
    _wait_for_localstack(endpoint, timeout=timeout)

    try:
        yield {
            "endpoint_url": endpoint,
            "region": DEFAULT_REGION,
            "container_id": str(container.id),
            "services": services,
        }
    finally:
        if teardown:
            # Stop container if still running
            try:
                container.stop(timeout=5)
            except Exception:
                pass

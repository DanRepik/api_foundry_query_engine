import os
import json

import pytest

from api_foundry_query_engine.lambda_handler import QueryEngine
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


@pytest.fixture(scope="session")
def chinook_handler(chinook_env):
    query_engine = QueryEngine(config=chinook_env)
    yield query_engine


def test_handler_insufficient_scope(chinook_env):  # noqa F811
    log.info(f"cwd {os.path.join(os.getcwd(), 'resources/api_spec.yaml')}")

    os.environ["API_SPEC"] = os.path.join(os.getcwd(), "resources/api_spec.yaml")

    import api_foundry_query_engine.lambda_handler as lambda_handler

    event = {
        "path": "/album",
        "headers": {
            "Host": "localhost",
            "User-Agent": "python-requests/2.25.1",
            "accept-encoding": "gzip, deflate",
            "accept": "*/*",
            "Connection": "keep-alive",
        },
        "body": "",
        "isBase64Encoded": False,
        "httpMethod": "GET",
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {},
        "resource": "/artist",
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "authorizer": {
                "claims": {
                    "sub": "user-123",
                    "scope": "read:album",
                    "roles": ["sales_manager", "sales_associate"],
                }
            },
            "resourcePath": "/artist",
            "domainPrefix": "localhost",
            "domainName": "localhost",
            "resourceId": "resource-id",
            "requestId": "request-id",
            "identity": {
                "accountId": "000000000000",
                "sourceIp": "127.0.0.1",
                "userAgent": "python-requests/2.25.1",
            },
            "httpMethod": "GET",
            "protocol": "HTTP/1.1",
            "requestTime": "10/Oct/2020:19:23:19 +0000",
            "requestTimeEpoch": 1602358999000,
            "path": "/dev/album",
            "stage": "dev",
        },
        "stageVariables": {},
    }

    print(f"current dir: {os.getcwd()}")

    #    ModelFactory.load_yaml(api_spec_path="resources/chinook_api.yaml")
    # Ensure the handler uses SECRETS from chinook_env while reading API_SPEC from os.environ
    merged_env = dict(os.environ)
    merged_env["SECRETS"] = chinook_env["SECRETS"]
    merged_env["chinook_secret"] = chinook_env["chinook_secret"]
    lambda_handler.handler.engine_config = merged_env
    response = lambda_handler.handler(event, None)
    print(f"response {response}")
    assert response["statusCode"] == 401
    assert "insufficient_scope: required_scope=read:artist" in response["body"]


def test_handler_sufficient_scope(chinook_env):  # noqa F811
    log.info(f"cwd {os.path.join(os.getcwd(), 'resources/api_spec.yaml')}")

    os.environ["API_SPEC"] = os.path.join(os.getcwd(), "resources/api_spec.yaml")

    import api_foundry_query_engine.lambda_handler as lambda_handler

    event = {
        "path": "/artist",
        "headers": {
            "Host": "localhost",
            "User-Agent": "python-requests/2.25.1",
            "accept-encoding": "gzip, deflate",
            "accept": "*/*",
            "Connection": "keep-alive",
        },
        "body": "",
        "isBase64Encoded": False,
        "httpMethod": "GET",
        "queryStringParameters": None,
        "multiValueQueryStringParameters": None,
        "pathParameters": {},
        "resource": "/artist",
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "authorizer": {
                "claims": {
                    "sub": "user-123",
                    "scope": "read:artist",
                    "roles": ["sales_manager", "sales_associate"],
                }
            },
            "resourcePath": "/artist",
            "domainPrefix": "localhost",
            "domainName": "localhost",
            "resourceId": "resource-id",
            "requestId": "request-id",
            "identity": {
                "accountId": "000000000000",
                "sourceIp": "127.0.0.1",
                "userAgent": "python-requests/2.25.1",
            },
            "httpMethod": "GET",
            "protocol": "HTTP/1.1",
            "requestTime": "10/Oct/2020:19:23:19 +0000",
            "requestTimeEpoch": 1602358999000,
            "path": "/dev/artist",
            "stage": "dev",
        },
        "stageVariables": {},
    }

    print(f"current dir: {os.getcwd()}")

    #    ModelFactory.load_yaml(api_spec_path="resources/chinook_api.yaml")
    # Ensure the handler uses SECRETS from chinook_env while reading API_SPEC from os.environ
    merged_env = dict(os.environ)
    merged_env["SECRETS"] = chinook_env["SECRETS"]
    merged_env["chinook_secret"] = chinook_env["chinook_secret"]
    lambda_handler.handler.engine_config = merged_env
    response = lambda_handler.handler(event, None)
    assert response["statusCode"] == 200
    artist = json.loads(response["body"])
    assert len(artist) == 275


def test_handler_with_groups(chinook_handler):  # noqa F811
    response = chinook_handler.handler(
        {
            "path": "/album",
            "headers": {
                "Host": "localhost",
                "User-Agent": "python-requests/2.25.1",
            },
            "httpMethod": "GET",
            "resource": "/album",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "user-123",
                        "scope": "read:album write:album",
                        "roles": ["sales_manager", "sales_associate"],
                    }
                },
                "httpMethod": "GET",
                "stage": "dev",
            },
        }
    )
    assert response["statusCode"] == 200
    albums = json.loads(response["body"])
    assert isinstance(albums, list)

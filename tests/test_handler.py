
import os
import json

from api_foundry_query_engine.utils.api_model import APIModel
from api_foundry_query_engine.utils.logger import logger

from tests.test_fixtures import db_secrets  # noqa F401

log = logger(__name__)

def test_handler(db_secrets):  # noqa F811
    log.info(f"cwd {os.path.join(os.getcwd(), 'resources/api_spec.yaml')}")

    os.environ["API_SPEC"] = os.path.join(os.getcwd(), "resources/api_spec.yaml")
    
    from api_foundry_query_engine.lambda_handler import handler

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
        "resource": "/album",
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "resourcePath": "/album",
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
            "authorizer": {},
            "path": "/dev/album",
            "stage": "dev",
        },
        "stageVariables": {},
    }

    print(f"current dir: {os.getcwd()}")
#    ModelFactory.load_yaml(api_spec_path="resources/chinook_api.yaml")
    response = handler(event, None)
    assert response["statusCode"] == 200
    albums = json.loads(response["body"])
    assert len(albums) == 350

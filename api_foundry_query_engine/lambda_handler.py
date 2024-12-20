import json
import logging
import os

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.adapters.gateway_adapter import GatewayAdapter
from api_foundry_query_engine.utils.api_model import load_api

log = logging.getLogger(__name__)


load_api(os.environ.get("API_SPEC", "/var/task/api_spec.yaml"))
adapter = GatewayAdapter()


def handler(event, _):
    log.debug(f"event: {event}")
    try:
        response = adapter.process_event(event)

        # Ensure the response conforms to API Gateway requirements
        return {
            "isBase64Encoded": False,
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response),
        }
    except ApplicationException as e:
        log.error(f"exception: {e}", exc_info=True)
        return {
            "isBase64Encoded": False,
            "statusCode": e.status_code,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": f"exception: {e}"}),
        }
    except Exception as e:
        log.error(f"exception: {e}", exc_info=True)
        return {
            "isBase64Encoded": False,
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": f"exception: {e}"}),
        }

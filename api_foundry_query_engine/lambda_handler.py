import json
import logging
import os
from typing import Mapping, Any

from api_foundry_query_engine.utils.api_model import set_api_model
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.adapters.gateway_adapter import GatewayAdapter
from api_foundry_query_engine.utils.token_decoder import token_decoder
from api_foundry_query_engine.utils.claims_check import claims_check

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)


class QueryEngine:
    def __init__(self, config: Mapping[str, str]):
        self.adapter = GatewayAdapter(config)

    def handler(self, event) -> dict[str, Any]:
        log.debug("event: %s", event)
        try:
            response = self.adapter.process_event(event)

            # Ensure the response conforms to API Gateway requirements
            return {
                "isBase64Encoded": False,
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(response),
            }
        except ApplicationException as e:
            log.error("exception: %s", e, exc_info=True)
            return {
                "isBase64Encoded": False,
                "statusCode": e.status_code,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": "exception: %s" % e}),
            }
        except RuntimeError as e:
            log.error("runtime error: %s", e, exc_info=True)
            return {
                "isBase64Encoded": False,
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"message": f"runtime error: {e}"}),
            }


@token_decoder()
@claims_check()
def handler(event, _):
    if not hasattr(handler, "engine_config"):
        log.info("Loading engine config from environment variables")
        handler.engine_config = os.environ
        log.info("engine_config: %s", handler.engine_config)

    if not hasattr(handler, "query_engine"):
        set_api_model(handler.engine_config)
        log.info("Creating QueryEngine instance")
        handler.query_engine = QueryEngine(handler.engine_config)

    return handler.query_engine.handler(event)

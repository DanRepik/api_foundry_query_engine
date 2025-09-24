import json
import logging
import os
from typing import Optional, Mapping

from api_foundry_query_engine.utils.api_model import set_api_model
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.adapters.gateway_adapter import GatewayAdapter

log = logging.getLogger(__name__)


class QueryEngine:
    def __init__(self, config: Mapping[str, str]):
        self.adapter = GatewayAdapter(config)

    def handler(self, event):
        log.debug(f"event: {event}")
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


engine_config: Optional[Mapping[str, str]] = None
query_engine: Optional[QueryEngine] = None


def handler(event, _):
    global engine_config, query_engine
    log.info(f"engine_config: {engine_config}")
    if engine_config is None:
        log.info("Loading engine config from environment variables")
        engine_config = os.environ
        log.info(f"engine_config: {engine_config}")

    if query_engine is None:
        set_api_model(engine_config)
        log.info("Creating QueryEngine instance")
        query_engine = QueryEngine(engine_config)

    return query_engine.handler(event)

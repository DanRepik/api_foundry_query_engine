import json
import logging
import os
from typing import Optional, Mapping

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.adapters.gateway_adapter import GatewayAdapter

log = logging.getLogger(__name__)

engine_config: Optional[Mapping[str, str]] = None
adapter: Optional[GatewayAdapter] = None


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


def handler(event, _):
    global engine_config, adapter
    if engine_config is None:
        engine_config = os.environ

    query_engine = QueryEngine(engine_config)
    return query_engine.handler(event)

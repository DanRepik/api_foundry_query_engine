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


# Lambda rejects synchronous responses over 6 MB (6,291,556 bytes including
# its own envelope); API Gateway then surfaces that as an opaque
# "502 Internal server error". The margin leaves room for the statusCode/
# headers wrapper so a body under the limit can't still be refused.
DEFAULT_MAX_RESPONSE_BYTES = 6 * 1024 * 1024 - 4096


class QueryEngine:
    def __init__(self, config: Mapping[str, str]):
        self.adapter = GatewayAdapter(config)
        self.max_response_bytes = int(
            config.get("MAX_RESPONSE_BYTES") or DEFAULT_MAX_RESPONSE_BYTES
        )

    def handler(self, event) -> dict[str, Any]:
        log.debug("event: %s", event)
        try:
            response = self.adapter.process_event(event)
            body = json.dumps(response)

            # json.dumps escapes to ASCII by default, so len(body) is bytes.
            if len(body) > self.max_response_bytes:
                log.error(
                    "response of %d bytes exceeds limit of %d bytes",
                    len(body),
                    self.max_response_bytes,
                )
                return {
                    "isBase64Encoded": False,
                    "statusCode": 502,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(
                        {
                            "message": (
                                f"response of {len(body)} bytes exceeds the "
                                f"maximum of {self.max_response_bytes} bytes; "
                                "narrow the request with filters"
                            )
                        }
                    ),
                }

            # Ensure the response conforms to API Gateway requirements
            return {
                "isBase64Encoded": False,
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": body,
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
@claims_check(validate_path_scope=False, validate_scope_format=False)
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

import hashlib
import json

from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.operation import Operation

log = logger(__name__)


class Service:
    def __init__(self, config: dict = {}):
        self.config = config

    def execute(self, operation: Operation) -> list[dict]:
        raise NotImplementedError


class ServiceAdapter(Service):
    def __init__(self, config: dict = {}):
        super().__init__(config)

    def execute(self, operation: Operation) -> list[dict]:
        return super().execute(operation)


class MutationPublisher(ServiceAdapter):
    def __init__(self, config: dict = {}):
        super().__init__(config)

    def execute(self, operation):
        result = super().execute(operation)
        self.publish_notification(operation)
        return result

    def publish_notification(self, operation):
        topic_arn = self.config.get("BROADCAST_TOPIC", None)
        log.debug(f"Topic ARN: {topic_arn}")

        if topic_arn is not None:
            log.debug("Sending message")
            message = {
                "entity": operation.api_name,
                "action": operation.action,
                "store_params": operation.store_params,
                "query_params": operation.query_params,
            }

            message_str = json.dumps({"default": json.dumps(message)})
            log.debug(f"message_str: {message_str}")
            hash_object = hashlib.sha256(message_str.encode("utf-8"))
            hex_dig = hash_object.hexdigest()

            msg_id = self.__client("sns").publish(
                TopicArn=topic_arn,
                MessageStructure="json",
                MessageDeduplicationId=hex_dig,
                MessageGroupId=operation.api_name,
                Message=message_str,
            )
            log.info(f"publish msg id {msg_id}")

    def __client(self, client_type):
        import boto3

        region = self.config.get("AWS_REGION", "us-east-1")
        session = boto3.Session()
        if session:
            return session.client(client_type, region_name=region)
        return boto3.client(client_type, region_name=region)

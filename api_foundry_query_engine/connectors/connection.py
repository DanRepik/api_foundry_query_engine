from api_foundry_query_engine.utils.logger import logger

# Initialize the logger
log = logger(__name__)

db_config_map = dict()


class Cursor:
    def execute(self, sql: str, params: dict, selection_results: dict) -> list[dict]:
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class Connection:
    def __init__(self, db_config: dict) -> None:
        super().__init__()
        self.db_config = db_config

    def engine(self) -> str:
        return self.db_config["engine"]

    def cursor(self) -> Cursor:
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

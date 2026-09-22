from collections import defaultdict, deque
from typing import List, Optional

from api_foundry_query_engine.utils.logger import logger

# Initialize the logger
log = logger(__name__)

db_config_map = dict()


def map_columns_to_selection_keys(column_names: List[str], selection_results: dict) -> List[Optional[str]]:
    """Match a result set's bare column names, in cursor order, to
    selection_results' keys (which may be table-alias-qualified, e.g.
    "m.media_type_id" -- cursor/column metadata never returns qualified
    names).

    Returns one entry per column: selection_results' own key for that
    column, or None if it isn't selected. A join can select the same bare
    column from multiple tables (e.g. both "i.customer_id" and
    "c.customer_id"), so this consumes one queued key per bare name per
    occurrence -- in selection_results' insertion order, which matches the
    SELECT list's column order -- rather than a plain name lookup, which
    would collapse duplicates and silently drop a column's value.
    """
    queues: dict[str, deque] = defaultdict(deque)
    for key in selection_results:
        queues[key.rsplit(".", 1)[-1]].append(key)

    return [queues[name].popleft() if queues.get(name) else None for name in column_names]


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

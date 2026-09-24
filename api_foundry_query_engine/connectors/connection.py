import os
from collections import defaultdict, deque
from typing import List, Optional, Tuple

from api_foundry_query_engine.utils.logger import logger

# Initialize the logger
log = logger(__name__)

db_config_map = dict()

# The driver a bare "engine" value (no ":driver" suffix) resolves to for
# each dialect, when nothing else overrides it. This only names a driver --
# it doesn't guarantee one is actually registered in ConnectionFactory's
# CONNECTOR_REGISTRY yet (oracle/mysql have neither a real connector nor
# tests exercising one, only dialect-specific SQL generation in
# SQLQueryHandler.placeholder/concurrency_generator). Using ConnectionFactory
# with such a dialect fails there instead, with a clear "unsupported
# engine" error rather than a "no default driver" one.
DEFAULT_DRIVERS = {
    "postgres": "psycopg2",
    "oracle": "cx_oracle",
    "mysql": "mysqlclient",
}


def parse_engine(engine: str) -> Tuple[str, str]:
    """Split an `engine` config value into (dialect, driver).

    `engine` was originally meant to select a SQL dialect ("postgres",
    "oracle", "mysql") for dialect-specific SQL generation (see
    SQLQueryHandler.placeholder/concurrency_generator). Once a second
    connector (the RDS Data API) existed for the same dialect, driver
    selection got bolted onto the same string as a distinct value
    ("postgres-data-api") instead of an orthogonal axis -- indistinguishable
    from a dialect at a glance, and unable to express e.g. an Oracle Data
    API-style driver without inventing another one-off name.

    The explicit form is "{dialect}:{driver}", e.g. "postgres:data-api".
    A bare dialect ("postgres") resolves its driver from the
    "{DIALECT}_DEFAULT_DRIVER" environment variable if set, else
    DEFAULT_DRIVERS -- so existing config/tests that only ever named a
    dialect keep working, and a deployment can switch its default driver
    (e.g. postgres -> data-api) without touching every config value that
    names the dialect alone.
    """
    if ":" in engine:
        dialect, driver = engine.split(":", 1)
        return dialect, driver

    dialect = engine
    driver = os.environ.get(f"{dialect.upper()}_DEFAULT_DRIVER") or DEFAULT_DRIVERS.get(dialect)
    if not driver:
        raise ValueError(
            f"No default driver configured for dialect {dialect!r} -- set "
            f"{dialect.upper()}_DEFAULT_DRIVER or add it to DEFAULT_DRIVERS, "
            f"or specify one explicitly as \"{dialect}:<driver>\"."
        )
    return dialect, driver


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

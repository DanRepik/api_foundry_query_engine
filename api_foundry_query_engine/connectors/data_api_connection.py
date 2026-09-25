import json
import re
import time
from datetime import date, datetime, time as time_type, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3
from botocore.config import Config as BotoConfig

from api_foundry_query_engine.connectors.connection import (
    Connection,
    Cursor,
    map_columns_to_selection_keys,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

# The Data API's own statement timeout is 45s (AWS docs); a boto3
# read_timeout below that would surface as a generic SDK timeout instead
# of the service's own, more useful error, so stay comfortably above it.
READ_TIMEOUT_SECONDS = 65

# A paused Aurora Serverless v2 cluster resumes in well under this budget
# (AWS docs put it at ~15s), but the caller (API Gateway) has a hard 29s
# cap end to end, so don't retry for longer than that leaves room for.
RESUME_RETRY_BUDGET_SECONDS = 20
RESUME_RETRY_INTERVAL_SECONDS = 2

_WRITE_KEYWORDS = ("INSERT", "UPDATE", "DELETE")


def _is_write_statement(sql: str) -> bool:
    stripped = sql.strip()
    if not stripped:
        return False
    return stripped.split(None, 1)[0].upper() in _WRITE_KEYWORDS


def _encode_parameter(value: Any) -> dict:
    """Encode a Python value into an RDS Data API parameter `value` field.

    Values arriving here have already been through
    SchemaObjectProperty.convert_to_db_value (or json.dumps, for embedded
    objects/arrays), so this only needs to get each Python type onto the
    wire faithfully -- columns a plain string can't be implicitly coerced
    into (uuid, jsonb, timestamptz, ...) are handled by an explicit SQL
    cast on the placeholder instead (see SQLQueryHandler.placeholder).
    """
    if value is None:
        return {"isNull": True}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"longValue": value}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, Decimal):
        return {"stringValue": str(value)}
    if isinstance(value, datetime):
        return {"stringValue": value.strftime("%Y-%m-%d %H:%M:%S.%f")}
    if isinstance(value, date):
        return {"stringValue": value.isoformat()}
    if isinstance(value, time_type):
        return {"stringValue": value.strftime("%H:%M:%S.%f")}
    if isinstance(value, (dict, list)):
        # Not expected on this path today (object/array properties are
        # already JSON-text by the time they reach here), but dumping to
        # JSON is the only non-lossy fallback if one ever does.
        return {"stringValue": json.dumps(value)}
    return {"stringValue": str(value)}


def _build_parameters(params: dict) -> list:
    return [{"name": name, "value": _encode_parameter(value)} for name, value in (params or {}).items()]


def _parse_data_api_timestamp(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ApplicationException(500, f"Unrecognized Data API timestamp value: {value!r}")


def _parse_data_api_time(value: str) -> time_type:
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ApplicationException(500, f"Unrecognized Data API time value: {value!r}")


def _decode_array(array_value: dict) -> list:
    for key in ("stringValues", "longValues", "doubleValues", "booleanValues"):
        values = array_value.get(key)
        if values is not None:
            return list(values)
    nested = array_value.get("arrayValues")
    if nested is not None:
        return [_decode_array(v) for v in nested]
    return []


def _rehydrate_string(value: str, type_name: Optional[str]) -> Any:
    """Turn a Data API stringValue back into the Python type psycopg2
    would have produced for the same column, so marshal_record and
    SchemaObjectProperty.convert_to_api_value behave identically
    regardless of which connector ran the query. Without this, e.g. a
    jsonb column would come back as an escaped string instead of a dict,
    and a timestamptz would lose its offset.
    """
    if type_name in ("json", "jsonb"):
        return json.loads(value)
    if type_name == "timestamptz":
        return _parse_data_api_timestamp(value).replace(tzinfo=timezone.utc)
    if type_name == "timestamp":
        return _parse_data_api_timestamp(value)
    if type_name == "date":
        return date.fromisoformat(value)
    if type_name in ("time", "timetz"):
        return _parse_data_api_time(value)
    return value


def _decode_field(field: dict, type_name: Optional[str]) -> Any:
    if field.get("isNull"):
        return None
    if "booleanValue" in field:
        return field["booleanValue"]
    if "longValue" in field:
        return field["longValue"]
    if "doubleValue" in field:
        return field["doubleValue"]
    if "blobValue" in field:
        return field["blobValue"]
    if "arrayValue" in field:
        return _decode_array(field["arrayValue"])
    value = field.get("stringValue")
    if value is None:
        return None
    return _rehydrate_string(value, type_name)


def _sqlstate_class(message: str) -> str:
    match = re.search(r"SQLState:\s*([0-9A-Za-z]+)", message or "")
    return match.group(1)[:2] if match else ""


def _map_database_error(message: str) -> ApplicationException:
    # Mirrors PostgresCursor's IntegrityError/ProgrammingError/Error
    # mapping, driven off the SQLState class Postgres appends to the
    # DatabaseErrorException message instead of a driver-specific type.
    sqlstate_class = _sqlstate_class(message)
    if sqlstate_class == "23":
        return ApplicationException(409, message)
    if sqlstate_class == "42":
        return ApplicationException(400, message)
    return ApplicationException(500, message)


class DataApiCursor(Cursor):
    def __init__(self, connection: "DataApiConnection"):
        self.__connection = connection

    def execute(self, sql: str, params: dict, selection_results: dict) -> list[dict]:
        log.info("sql: %s", sql)

        transaction_id = self.__connection.begin_if_needed(sql)
        response = self.__connection.execute_statement(sql, _build_parameters(params), transaction_id)

        records = response.get("records")
        if not records:
            return []

        column_metadata = response.get("columnMetadata") or []
        columns = [(meta.get("name"), meta.get("typeName")) for meta in column_metadata]
        # column_metadata's "name" is always bare, even when
        # selection_results' keys are table-alias-qualified (e.g.
        # "m.media_type_id") -- see postgres_connection.py's PostgresCursor
        # for the same mapping against psycopg2's cursor.description.
        position_keys = map_columns_to_selection_keys([name for name, _ in columns], selection_results)

        result = []
        for record in records:
            row = {}
            for key, (_, type_name), field in zip(position_keys, columns, record):
                if key is not None:
                    row[key] = _decode_field(field, type_name)
            result.append(row)
        return result

    def close(self):
        # Each execute() is a single stateless HTTPS call; there is no
        # per-cursor resource to release. The connection, not the cursor,
        # owns the transaction lifecycle -- see DataApiConnection.close().
        pass


class DataApiConnection(Connection):
    """RDS Data API connection.

    Lets the query engine reach a private, PubliclyAccessible=False Aurora
    cluster from a Lambda that is *not* VPC-attached: every call is a
    plain HTTPS request to the `rds-data` API, authenticated by IAM, with
    the database credentials looked up server-side from the secret named
    by `secret_arn`. Unlike the VPC-attached DSN-in-env-var workaround
    this replaces, the password never reaches the Lambda's environment or
    memory. The Data API reads the secret with the caller's own IAM
    permissions, so the role needs `secretsmanager:GetSecretValue` on
    `secret_arn` as well as the `rds-data` actions (ExecuteStatement,
    BeginTransaction, CommitTransaction, RollbackTransaction) on the
    cluster.

    db_config keys: `resource_arn` (the cluster ARN), `secret_arn`,
    `database`, and optionally `schema` and `endpoint_url` (LocalStack).
    """

    def __init__(self, db_config: dict) -> None:
        super().__init__(db_config)
        self.resource_arn = db_config["resource_arn"]
        self.secret_arn = db_config["secret_arn"]
        self.database = db_config["database"]
        self.schema = db_config.get("schema")
        self.transaction_id: Optional[str] = None
        self.client = boto3.client(
            "rds-data",
            endpoint_url=db_config.get("endpoint_url"),
            config=BotoConfig(read_timeout=READ_TIMEOUT_SECONDS, retries={"max_attempts": 1}),
        )

    def cursor(self) -> Cursor:
        return DataApiCursor(self)

    def begin_if_needed(self, sql: str) -> Optional[str]:
        """Begin a transaction on the first write seen on this connection,
        and reuse it for every statement (read or write) after that, so a
        read that depends on an earlier write in the same request or
        batch sees it. A pure read sequence never begins one, avoiding
        the extra begin/commit round trips for the common read-only path.
        """
        if self.transaction_id is not None:
            return self.transaction_id
        if not _is_write_statement(sql):
            return None

        kwargs = {"resourceArn": self.resource_arn, "secretArn": self.secret_arn, "database": self.database}
        if self.schema:
            kwargs["schema"] = self.schema
        response = self.client.begin_transaction(**kwargs)
        self.transaction_id = response["transactionId"]
        return self.transaction_id

    def execute_statement(self, sql: str, parameters: list, transaction_id: Optional[str]) -> dict:
        kwargs = {
            "resourceArn": self.resource_arn,
            "secretArn": self.secret_arn,
            "database": self.database,
            "sql": sql,
            "parameters": parameters,
            "includeResultMetadata": True,
        }
        if self.schema:
            kwargs["schema"] = self.schema
        if transaction_id:
            kwargs["transactionId"] = transaction_id

        deadline = time.monotonic() + RESUME_RETRY_BUDGET_SECONDS
        while True:
            try:
                return self.client.execute_statement(**kwargs)
            except self.client.exceptions.DatabaseResumingException:
                if time.monotonic() >= deadline:
                    raise ApplicationException(
                        503,
                        "Database is resuming from auto-pause; retry the request shortly.",
                    )
                log.info("database resuming, retrying in %ss", RESUME_RETRY_INTERVAL_SECONDS)
                time.sleep(RESUME_RETRY_INTERVAL_SECONDS)
            except self.client.exceptions.UnsupportedResultException as err:
                raise ApplicationException(
                    400,
                    "Result exceeds the RDS Data API's response size limit; " "narrow the query or add pagination.",
                ) from err
            except self.client.exceptions.DatabaseErrorException as err:
                raise _map_database_error(_error_message(err)) from err
            except self.client.exceptions.BadRequestException as err:
                raise ApplicationException(400, _error_message(err)) from err
            except self.client.exceptions.TransactionNotFoundException as err:
                # The transaction's idle timeout elapsed server-side; the
                # connection can't keep using it.
                self.transaction_id = None
                raise ApplicationException(500, "Database transaction expired before the request completed.") from err
            except self.client.exceptions.StatementTimeoutException as err:
                raise ApplicationException(504, _error_message(err)) from err

    def commit(self):
        if self.transaction_id is None:
            return
        self.client.commit_transaction(
            resourceArn=self.resource_arn, secretArn=self.secret_arn, transactionId=self.transaction_id
        )
        self.transaction_id = None

    def rollback(self):
        if self.transaction_id is None:
            return
        self.client.rollback_transaction(
            resourceArn=self.resource_arn, secretArn=self.secret_arn, transactionId=self.transaction_id
        )
        self.transaction_id = None

    def close(self):
        # Mirrors psycopg2: closing a connection with an open, uncommitted
        # transaction implicitly rolls it back, rather than leaving a Data
        # API transaction dangling until its own idle timeout.
        if self.transaction_id is not None:
            try:
                self.rollback()
            except Exception:
                log.error("failed to roll back open Data API transaction on close")


def _error_message(err) -> str:
    return err.response.get("Error", {}).get("Message", str(err))

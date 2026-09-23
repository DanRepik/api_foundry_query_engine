import os
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from botocore.stub import Stubber

from api_foundry_query_engine.connectors.data_api_connection import (
    DataApiConnection,
    _build_parameters,
    _decode_field,
    _is_write_statement,
    _map_database_error,
    _rehydrate_string,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException

# boto3 needs a region to construct a client even when every call is
# stubbed; production Lambdas get one from the runtime's AWS_REGION.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

RESOURCE_ARN = "arn:aws:rds:us-east-1:123456789012:cluster:test-cluster"
SECRET_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret"
DATABASE = "cep"


def _connection() -> DataApiConnection:
    return DataApiConnection(
        {
            "engine": "postgres:data-api",
            "resource_arn": RESOURCE_ARN,
            "secret_arn": SECRET_ARN,
            "database": DATABASE,
        }
    )


def _column(name, type_name):
    return {"name": name, "typeName": type_name}


@pytest.mark.unit
class TestParameterEncoding:
    def test_encodes_scalar_types(self):
        params = _build_parameters(
            {
                "n": None,
                "flag": True,
                "count": 5,
                "price": 1.5,
                "name": "hello",
            }
        )
        by_name = {p["name"]: p["value"] for p in params}
        assert by_name["n"] == {"isNull": True}
        assert by_name["flag"] == {"booleanValue": True}
        assert by_name["count"] == {"longValue": 5}
        assert by_name["price"] == {"doubleValue": 1.5}
        assert by_name["name"] == {"stringValue": "hello"}

    def test_encodes_decimal_as_string(self):
        params = _build_parameters({"amount": Decimal("12.50")})
        assert params[0]["value"] == {"stringValue": "12.50"}

    def test_encodes_datetime_in_data_api_format(self):
        value = datetime(2026, 9, 20, 11, 56, 6, 364935)
        params = _build_parameters({"occurred_at": value})
        assert params[0]["value"] == {"stringValue": "2026-09-20 11:56:06.364935"}

    def test_encodes_date_and_time(self):
        params = _build_parameters({"d": date(2026, 9, 20), "t": time(11, 56, 6, 364935)})
        by_name = {p["name"]: p["value"] for p in params}
        assert by_name["d"] == {"stringValue": "2026-09-20"}
        assert by_name["t"] == {"stringValue": "11:56:06.364935"}

    def test_json_text_stays_a_plain_string(self):
        # Insert/update handlers already json.dumps() object/array values
        # before they reach the connector -- confirm that string passes
        # through untouched rather than being re-encoded.
        params = _build_parameters({"metadata": '{"kind": "artifact"}'})
        assert params[0]["value"] == {"stringValue": '{"kind": "artifact"}'}


@pytest.mark.unit
class TestResultRehydration:
    def test_jsonb_column_parsed_to_native_object(self):
        assert _rehydrate_string('{"kind": "artifact"}', "jsonb") == {"kind": "artifact"}

    def test_timestamptz_column_becomes_aware_utc_datetime(self):
        result = _rehydrate_string("2026-09-20 11:56:06.364935", "timestamptz")
        assert result == datetime(2026, 9, 20, 11, 56, 6, 364935, tzinfo=timezone.utc)

    def test_timestamp_column_stays_naive(self):
        result = _rehydrate_string("2026-09-20 11:56:06", "timestamp")
        assert result == datetime(2026, 9, 20, 11, 56, 6)

    def test_date_column(self):
        assert _rehydrate_string("2026-09-20", "date") == date(2026, 9, 20)

    def test_time_column(self):
        assert _rehydrate_string("11:56:06.364935", "time") == time(11, 56, 6, 364935)

    def test_uuid_and_plain_string_columns_pass_through(self):
        assert _rehydrate_string("11111111-2222-3333-4444-555555555555", "uuid") == (
            "11111111-2222-3333-4444-555555555555"
        )
        assert _rehydrate_string("hello", "varchar") == "hello"

    def test_decode_field_prefers_native_types_over_string_rehydration(self):
        assert _decode_field({"isNull": True}, "jsonb") is None
        assert _decode_field({"booleanValue": True}, "boolean") is True
        assert _decode_field({"longValue": 5}, "int4") == 5
        assert _decode_field({"doubleValue": 1.5}, "float8") == 1.5


@pytest.mark.unit
class TestStatementSniffing:
    @pytest.mark.parametrize(
        "sql,expected",
        [
            ("SELECT id FROM widget", False),
            ("  select id from widget", False),
            ("INSERT INTO widget (id) VALUES (:id)", True),
            ("UPDATE widget SET name = :name", True),
            ("DELETE FROM widget WHERE id = :id", True),
            ("", False),
        ],
    )
    def test_is_write_statement(self, sql, expected):
        assert _is_write_statement(sql) is expected


@pytest.mark.unit
class TestDatabaseErrorMapping:
    def test_integrity_violation_maps_to_409(self):
        err = _map_database_error("duplicate key value violates unique constraint SQLState: 23505")
        assert isinstance(err, ApplicationException)
        assert err.status_code == 409

    def test_syntax_error_maps_to_400(self):
        err = _map_database_error('syntax error at or near "FORM" SQLState: 42601')
        assert err.status_code == 400

    def test_unrecognized_sqlstate_maps_to_500(self):
        err = _map_database_error("something went wrong SQLState: 58000")
        assert err.status_code == 500

    def test_missing_sqlstate_maps_to_500(self):
        err = _map_database_error("no sqlstate here")
        assert err.status_code == 500


@pytest.mark.unit
class TestDataApiCursorExecute:
    def test_read_only_statement_runs_without_transaction(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        stubber.add_response(
            "execute_statement",
            {
                "records": [[{"stringValue": "widget-1"}, {"longValue": 5}]],
                "columnMetadata": [_column("id", "varchar"), _column("count", "int4")],
            },
            {
                "resourceArn": RESOURCE_ARN,
                "secretArn": SECRET_ARN,
                "database": DATABASE,
                "sql": "SELECT id, count FROM widget",
                "parameters": [],
                "includeResultMetadata": True,
            },
        )
        with stubber:
            cursor = connection.cursor()
            result = cursor.execute("SELECT id, count FROM widget", {}, {"id": object(), "count": object()})

        assert result == [{"id": "widget-1", "count": 5}]
        assert connection.transaction_id is None

    def test_write_statement_begins_and_reuses_transaction(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        stubber.add_response("begin_transaction", {"transactionId": "txn-1"})
        stubber.add_response(
            "execute_statement",
            {"records": [[{"longValue": 1}]], "columnMetadata": [_column("id", "int4")]},
            {
                "resourceArn": RESOURCE_ARN,
                "secretArn": SECRET_ARN,
                "database": DATABASE,
                "sql": "INSERT INTO widget (id) VALUES (:id) RETURNING id",
                "parameters": [{"name": "id", "value": {"longValue": 1}}],
                "includeResultMetadata": True,
                "transactionId": "txn-1",
            },
        )
        # A read issued afterward on the same connection (e.g. relation
        # fetch in a batch) must reuse the same transaction rather than
        # running autocommitted, so it can see the write above.
        stubber.add_response(
            "execute_statement",
            {"records": [], "columnMetadata": []},
            {
                "resourceArn": RESOURCE_ARN,
                "secretArn": SECRET_ARN,
                "database": DATABASE,
                "sql": "SELECT id FROM widget",
                "parameters": [],
                "includeResultMetadata": True,
                "transactionId": "txn-1",
            },
        )
        stubber.add_response(
            "commit_transaction",
            {"transactionStatus": "Transaction Committed"},
            {"resourceArn": RESOURCE_ARN, "secretArn": SECRET_ARN, "transactionId": "txn-1"},
        )

        with stubber:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO widget (id) VALUES (:id) RETURNING id", {"id": 1}, {"id": object()})
            assert connection.transaction_id == "txn-1"
            cursor.execute("SELECT id FROM widget", {}, {"id": object()})
            connection.commit()

        assert connection.transaction_id is None
        stubber.assert_no_pending_responses()

    def test_close_rolls_back_an_uncommitted_transaction(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        stubber.add_response("begin_transaction", {"transactionId": "txn-2"})
        stubber.add_response(
            "execute_statement",
            {"records": [], "columnMetadata": []},
            {
                "resourceArn": RESOURCE_ARN,
                "secretArn": SECRET_ARN,
                "database": DATABASE,
                "sql": "DELETE FROM widget WHERE id = :id",
                "parameters": [{"name": "id", "value": {"longValue": 1}}],
                "includeResultMetadata": True,
                "transactionId": "txn-2",
            },
        )
        stubber.add_response(
            "rollback_transaction",
            {"transactionStatus": "Rollback Complete"},
            {"resourceArn": RESOURCE_ARN, "secretArn": SECRET_ARN, "transactionId": "txn-2"},
        )

        with stubber:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM widget WHERE id = :id", {"id": 1}, {})
            connection.close()

        assert connection.transaction_id is None
        stubber.assert_no_pending_responses()

    def test_no_transaction_means_close_is_a_no_op(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        with stubber:
            connection.close()
        stubber.assert_no_pending_responses()

    def test_database_error_is_raised_as_application_exception(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        stubber.add_client_error(
            "execute_statement",
            service_error_code="DatabaseErrorException",
            service_message="duplicate key value SQLState: 23505",
        )

        with stubber:
            cursor = connection.cursor()
            with pytest.raises(ApplicationException) as excinfo:
                cursor.execute("SELECT 1", {}, {})

        assert excinfo.value.status_code == 409

    def test_unsupported_result_is_raised_as_400(self):
        connection = _connection()
        stubber = Stubber(connection.client)
        stubber.add_client_error(
            "execute_statement",
            service_error_code="UnsupportedResultException",
            service_message="The result exceeds the size limit 1 MB",
        )

        with stubber:
            cursor = connection.cursor()
            with pytest.raises(ApplicationException) as excinfo:
                cursor.execute("SELECT * FROM widget", {}, {})

        assert excinfo.value.status_code == 400

    def test_database_resuming_retries_then_succeeds(self, monkeypatch):
        connection = _connection()
        monkeypatch.setattr("api_foundry_query_engine.connectors.data_api_connection.time.sleep", lambda _: None)
        stubber = Stubber(connection.client)
        stubber.add_client_error(
            "execute_statement",
            service_error_code="DatabaseResumingException",
            service_message="Database resuming",
        )
        stubber.add_response(
            "execute_statement",
            {"records": [], "columnMetadata": []},
            {
                "resourceArn": RESOURCE_ARN,
                "secretArn": SECRET_ARN,
                "database": DATABASE,
                "sql": "SELECT 1",
                "parameters": [],
                "includeResultMetadata": True,
            },
        )

        with stubber:
            cursor = connection.cursor()
            result = cursor.execute("SELECT 1", {}, {})

        assert result == []
        stubber.assert_no_pending_responses()

    def test_database_resuming_past_budget_raises_503(self, monkeypatch):
        connection = _connection()
        monkeypatch.setattr("api_foundry_query_engine.connectors.data_api_connection.time.sleep", lambda _: None)
        # Force the retry loop's deadline check to report as already
        # expired on the very first poll, so the test doesn't depend on
        # wall-clock time or actually retry.
        clock = iter([0, 999])
        monkeypatch.setattr(
            "api_foundry_query_engine.connectors.data_api_connection.time.monotonic",
            lambda: next(clock),
        )
        stubber = Stubber(connection.client)
        stubber.add_client_error(
            "execute_statement",
            service_error_code="DatabaseResumingException",
            service_message="Database resuming",
        )

        with stubber:
            cursor = connection.cursor()
            with pytest.raises(ApplicationException) as excinfo:
                cursor.execute("SELECT 1", {}, {})

        assert excinfo.value.status_code == 503

    def test_transaction_not_found_clears_transaction_state(self):
        connection = _connection()
        connection.transaction_id = "stale-txn"
        stubber = Stubber(connection.client)
        stubber.add_client_error(
            "execute_statement",
            service_error_code="TransactionNotFoundException",
            service_message="Transaction not found",
        )

        with stubber:
            cursor = connection.cursor()
            with pytest.raises(ApplicationException) as excinfo:
                cursor.execute("SELECT 1", {}, {})

        assert excinfo.value.status_code == 500
        assert connection.transaction_id is None

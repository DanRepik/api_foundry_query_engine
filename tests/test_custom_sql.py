import pytest

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.sql_custom_query_handler import SQLCustomQueryHandler
from api_foundry_query_engine.utils.api_model import get_path_operation
from api_foundry_query_engine.utils.logger import logger
from tests.test_schema_objects_fixtures import load_api

log = logger(__name__)


@pytest.mark.unit
class TestSQLGenerator:
    def test_custom_sql_with_default_value(self):
        load_api()
        sql_operation = SQLCustomQueryHandler(
            Operation(
                entity="top_selling_albums",
                action="read",
                query_params={
                    "start": "2022-01-01T00:00:00",
                    "end": "2022-01-07T00:00:00",
                    "limit": 10,
                },
            ),
            get_path_operation("top_selling_albums", "read"),
            "postgres",
        )

        log.info(
            f"sql: {sql_operation.sql}, placeholders: {sql_operation.placeholders}"
        )
        log.info(f"placeholders: {sql_operation.placeholders}")
        log.info(f"start: {sql_operation.placeholders['start']}")
        log.info(f"selection_results: {sql_operation.selection_results}")
        log.info(f"outputs: {sql_operation.path_operation.outputs}")

        assert (
            sql_operation.sql
            == "SELECT a.album_id as album_id, a.title AS album_title, "
            + "COUNT(il.invoice_line_id) AS total_sold "
            + "FROM invoice_line il "
            + "JOIN invoice i ON il.invoice_id = i.invoice_id "
            + "JOIN track t ON il.track_id = t.track_id "
            + "JOIN album a ON t.album_id = a.album_id "
            + "WHERE i.invoice_date >= %(start)s "
            + "AND i.invoice_date <= %(end)s "
            + "GROUP BY a.album_id ORDER BY total_sold DESC LIMIT %(limit)s"
        )
        assert sql_operation.placeholders == {
            "start": "2022-01-01T00:00:00",
            "end": "2022-01-07T00:00:00",
            "limit": "10",
        }

    def test_custom_sql(self):
        load_api()
        sql_operation = SQLCustomQueryHandler(
            Operation(
                entity="top_selling_albums",
                action="read",
                query_params={
                    "start": "2022-01-01T00:00:00",
                    "end": "2022-01-07T00:00:00",
                },
            ),
            get_path_operation("top_selling_albums", "read"),
            "postgres",
        )

        log.info(
            f"sql: {sql_operation.sql}, placeholders: {sql_operation.placeholders}"
        )
        log.info(f"placeholders: {sql_operation.placeholders}")
        log.info(f"start: {sql_operation.placeholders['start']}")
        log.info(f"selection_results: {sql_operation.selection_results}")
        log.info(f"outputs: {sql_operation.path_operation.outputs}")

        assert (
            sql_operation.sql
            == "SELECT a.album_id as album_id, a.title AS album_title, "
            + "COUNT(il.invoice_line_id) AS total_sold "
            + "FROM invoice_line il "
            + "JOIN invoice i ON il.invoice_id = i.invoice_id "
            + "JOIN track t ON il.track_id = t.track_id "
            + "JOIN album a ON t.album_id = a.album_id "
            + "WHERE i.invoice_date >= %(start)s "
            + "AND i.invoice_date <= %(end)s "
            + "GROUP BY a.album_id ORDER BY total_sold DESC LIMIT %(limit)s"
        )
        assert sql_operation.placeholders == {
            "start": "2022-01-01T00:00:00",
            "end": "2022-01-07T00:00:00",
            "limit": "10",
        }

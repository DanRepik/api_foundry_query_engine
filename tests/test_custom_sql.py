import pytest

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.sql_custom_query_handler import SQLCustomQueryHandler
from api_foundry_query_engine.utils.api_model import PathOperation, ModelFactory
from api_foundry_query_engine.utils.logger import logger
from test_fixtures import load_model  # noqa F401

log = logger(__name__)


@pytest.mark.unit
class TestSQLGenerator:
    def test_custom_sql(self, load_model):  # noqa F811
        sql_operation = SQLCustomQueryHandler(
            Operation(
                path="/top_selling_albums",
                action="read",
                query_params={
                    "start": "2022-01-01T00:00:00",
                    "end": "2022-01-07T00:00:00",
                },
            ),
            PathOperation(
                path="/top_selling_albums",
                method="get",
                path_operation={
                    "summary": "Get top-selling albums",
                    "description": "Returns the top 10 selling albums within a specified datetime range.",
                    "x-af-database": "chinook",
                    "x-af-sql": """
                        SELECT
                            a.album_id as album_id,
                            a.title AS album_title,
                            COUNT(il.invoice_line_id) AS total_sold
                        FROM
                            invoice_line il
                        JOIN
                            track t ON il.track_id = t.track_id
                        JOIN
                            album a ON t.album_id = a.album_id
                        WHERE
                            i.invoice_date >= :start
                            AND i.invoice_date <= :end
                        GROUP BY
                            a.title
                        ORDER BY
                            total_sold DESC
                        LIMIT :limit
                      """,
                    "parameters": [
                        {
                            "in": "query",
                            "name": "start",
                            "schema": {"type": "string", "format": "date-time"},
                            "required": True,
                            "description": "Start datetime for the sales period.",
                        },
                        {
                            "in": "query",
                            "name": "end",
                            "schema": {"type": "string", "format": "date-time"},
                            "required": True,
                            "description": "End datetime for the sales period.",
                        },
                        {
                            "in": "query",
                            "name": "limit",
                            "schema": {"type": "integer"},
                            "default": 10,
                            "description": "The number of albums to return.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "A list of top-selling albums",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "album_id": {
                                                    "type": "integer",
                                                    "description": "The id of the album",
                                                },
                                                "album_title": {
                                                    "type": "string",
                                                    "description": "The title of the album",
                                                },
                                                "total_sold": {
                                                    "type": "integer",
                                                    "description": "The number of albums sold",
                                                },
                                            },
                                        },
                                    }
                                }
                            },
                        }
                    },
                },
                spec=ModelFactory.spec,
            ),
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
            + "COUNT(il.invoice_line_id) AS total_sold FROM invoice_line il "
            + "JOIN track t ON il.track_id = t.track_id "
            + "JOIN album a ON t.album_id = a.album_id "
            + "WHERE i.invoice_date >= %(start)s "
            + "AND i.invoice_date <= %(end)s "
            + "GROUP BY a.title ORDER BY total_sold DESC LIMIT %(limit)s"
        )
        assert sql_operation.placeholders == {
            "start": "2022-01-01T00:00:00",
            "end": "2022-01-07T00:00:00",
            "limit": "10",
        }

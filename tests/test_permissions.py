from yaml import safe_load

from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.api_model import APIModel, get_schema_object
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


def test_some_restrictions():

    model_factory = APIModel(
        safe_load(
            """
schema_objects:
    album:
        api_name: album
        database: chinook
        permissions:
            sales_associate:
                read: album_id|title
            sales_manager:
                delete: true
                read: .*
                write: .*
        primary_key: album_id
        properties:
            album_id:
                api_name: album_id
                api_type: integer
                column_name: album_id
                column_type: integer
                key_type: auto
                required: false
            artist_id:
                api_name: artist_id
                api_type: integer
                column_name: artist_id
                column_type: integer
                required: false
            title:
                api_name: title
                api_type: string
                column_name: title
                column_type: string
                max_length: 160
                required: false
        table_name: album
"""
        )
    )
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    try:
        operation_dao = OperationDAO(
            Operation(
                entity="album",
                action="read",
                query_params={"album_id": "24"},
                roles=["sales_associate"],
            ),
            "postgres",
        )

        sql_handler = operation_dao.query_handler
        log.info(f"sql_handler: {sql_handler}")

        log.info(f"sql: {sql_handler.sql}")
        assert sql_handler.sql == "SELECT a.album_id, a.title FROM album AS a WHERE a.album_id = %(a_album_id)s"
        return

    except ApplicationException as e:
        assert (
            e.message
            == "Queries using properties in arrays is not supported. schema object: invoice, property: line_items.track_id"  # noqa E501
        )

    assert False

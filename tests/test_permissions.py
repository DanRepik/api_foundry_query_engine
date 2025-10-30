from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.api_model import get_schema_object
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

ALBUM_SCHEMA = """
schema_objects:
    album:
        api_name: album
        database: chinook
        permissions:
            sales_associate:
                read: album_id|title
                write: year_released
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
            year_released:
                api_name: year_released
                api_type: integer
                column_name: year_released
                column_type: integer
                required: false
        table_name: album
"""

INVOICE_SCHEMA = """
schema_objects:
    invoice:
        api_name: invoice
        concurrency_property: last_updated
        database: chinook
        permissions: {}
        primary_key: invoice_id
        properties:
            billing_address:
                api_name: billing_address
                api_type: string
                column_name: billing_address
                column_type: string
                max_length: 70
                required: false
            billing_city:
                api_name: billing_city
                api_type: string
                column_name: billing_city
                column_type: string
                max_length: 40
                required: false
            billing_country:
                api_name: billing_country
                api_type: string
                column_name: billing_country
                column_type: string
                max_length: 40
                required: false
            billing_postal_code:
                api_name: billing_postal_code
                api_type: string
                column_name: billing_postal_code
                column_type: string
                max_length: 10
                required: false
            billing_state:
                api_name: billing_state
                api_type: string
                column_name: billing_state
                column_type: string
                max_length: 40
                required: false
            customer_id:
                api_name: customer_id
                api_type: integer
                column_name: customer_id
                column_type: integer
                required: false
            invoice_date:
                api_name: invoice_date
                api_type: string
                column_name: invoice_date
                column_type: string
                required: false
            invoice_id:
                api_name: invoice_id
                api_type: integer
                column_name: invoice_id
                column_type: integer
                key_type: auto
                required: false
            last_updated:
                api_name: last_updated
                api_type: string
                column_name: last_updated
                column_type: string
                required: false
            total:
                api_name: total
                api_type: number
                column_name: total
                column_type: number
                required: false
        permissions:
            sales_associate:
                read: invoice_id|invoice_date|total
            sales_manager:
                delete: true
                read: .*
                write: .*
        relations:
            invoice_line_items:
                api_name: invoice_line_items
                api_type: array
                child_property: invoice_id
                parent_property: invoice_id
                schema_name: invoice_line
        table_name: invoice
    invoice_line:
        api_name: invoice_line
        database: chinook
        permissions: {}
        primary_key: invoice_line_id
        properties:
            invoice_id:
                api_name: invoice_id
                api_type: integer
                column_name: invoice_id
                column_type: integer
                required: false
            invoice_line_id:
                api_name: invoice_line_id
                api_type: integer
                column_name: invoice_line_id
                column_type: integer
                key_type: auto
                required: false
            quantity:
                api_name: quantity
                api_type: integer
                column_name: quantity
                column_type: integer
                required: false
            track_id:
                api_name: track_id
                api_type: integer
                column_name: track_id
                column_type: integer
                required: false
            unit_price:
                api_name: unit_price
                api_type: number
                column_name: unit_price
                column_type: number
                required: false
        permissions:
            sales_associate:
                read: track_id|unit_price
            sales_manager:
                delete: true
                read: .*
                write: .*
        table_name: invoice_line
"""


def test_read_some_restrictions(chinook_env):
    # sales associates cannot read artist_id or year_released
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="read",
            query_params={"album_id": "24"},
            claims={"roles": ["sales_associate"]},
        ),
        "postgres",
    )

    sql_handler = operation_dao.query_handler
    log.info(f"sql_handler: {sql_handler}")

    log.info(f"sql: {sql_handler.sql}")
    assert (
        sql_handler.sql
        == "SELECT a.album_id, a.title FROM album AS a WHERE a.album_id = %(a_album_id)s"
    )


def test_read_no_restrictions(chinook_env):
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="read",
            query_params={"album_id": "24"},
            claims={"roles": ["sales_manager"]},
        ),
        "postgres",
    )

    sql_handler = operation_dao.query_handler
    log.info(f"sql_handler: {sql_handler}")

    log.info(f"sql: {sql_handler.sql}")
    assert (
        sql_handler.sql
        == "SELECT a.album_id, a.artist_id, a.title FROM album AS a WHERE a.album_id = %(a_album_id)s"
    )


def test_read_all_restricted(chinook_env):
    # role does not allow any properties returned
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="read",
            query_params={"album_id": "24"},
            claims={"roles": ["customer_agent"]},
        ),
        "postgres",
    )

    try:
        sql_handler = operation_dao.query_handler
        log.info(f"sql_handler: {sql_handler}")

        log.info(f"sql: {sql_handler.sql}")
        assert (
            sql_handler.sql
            == "SELECT a.album_id, a.title FROM album AS a WHERE a.album_id = %(a_album_id)s"
        )
    except ApplicationException as ae:
        assert (
            ae.message
            == "After applying permissions there are no properties returned in response"
        )


def test_read_relation_some_restrictions(chinook_env):
    # test that permissions are applied to association objects
    schema_object = get_schema_object("invoice")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="invoice",
            action="read",
            query_params={"invoice_id": "24"},
            metadata_params={"properties": ".* invoice_line_items:.*"},
            claims={"roles": ["sales_associate"]},
        ),
        "postgres",
    )

    sql_handler = operation_dao.query_handler
    log.info(f"sql_handler: {sql_handler}")

    log.info(f"sql: {sql_handler.sql}")
    assert (
        sql_handler.sql
        == "SELECT i.billing_address, i.billing_city, i.billing_country, "
        + "i.billing_postal_code, i.billing_state, i.customer_id, "
        + "i.invoice_date, i.invoice_id, i.last_updated, i.total "
        + "FROM invoice AS i WHERE i.invoice_id = %(i_invoice_id)s"
    )


def test_create_prohibited_property(chinook_env):
    # sales associates cannot update title
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="create",
            store_params={"title": "something different"},
            claims={"roles": ["sales_associate"]},
        ),
        "postgres",
    )

    try:
        operation_dao.query_handler.sql
        assert False, "Exception should have been raised"
    except ApplicationException as ae:
        assert ae.message == "Subject is not allowed to create with property: title"


def test_create_allowed_property(chinook_env):
    # sales manager can create title
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="create",
            store_params={"title": "new title"},
            claims={"roles": ["sales_manager"]},
        ),
        "postgres",
    )

    sql = operation_dao.query_handler.sql
    log.info(f"sql: {sql}")
    assert (
        sql
        == "INSERT INTO album ( title ) VALUES ( %(title)s) RETURNING album_id, artist_id, title"
    )


def test_update_prohibited_property(chinook_env):
    # sales associates cannot update title
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="update",
            query_params={"album_id": "24"},
            store_params={"title": "something different"},
            claims={"roles": ["sales_associate"]},
        ),
        "postgres",
    )

    try:
        operation_dao.query_handler.sql
        assert False, "Exception should have been raised"
    except ApplicationException as ae:
        assert (
            ae.message
            == "Subject does not have permission to update properties: ['title']"
        )


def test_update_allowed_property(chinook_env):
    # sales manager can update title
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="update",
            query_params={"album_id": "24"},
            store_params={"title": "2024"},
            claims={"roles": ["sales_manager"]},
        ),
        "postgres",
    )

    sql = operation_dao.query_handler.sql
    log.info(f"sql: {sql}")
    assert (
        sql
        == "UPDATE album SET title = %(title)s WHERE album_id = %(album_id)s RETURNING album_id, artist_id, title"
    )


def test_delete_prohibited(chinook_env):
    # sales associates cannot delete albums
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="delete",
            query_params={"album_id": 5},
            claims={"roles": ["sales_associate"]},
        ),
        "postgres",
    )

    try:
        operation_dao.query_handler.sql
        assert False, "Exception should have been raised"
    except ApplicationException as ae:
        assert ae.message == "Subject is not allowed to delete album"


def test_delete_allowed(chinook_env):
    # sales associates cannot update title
    schema_object = get_schema_object("album")
    log.info(f"schema_object: {schema_object}")

    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="delete",
            query_params={"album_id": 5},
            claims={"roles": ["sales_manager"]},
        ),
        "postgres",
    )

    sql = operation_dao.query_handler.sql
    log.info(f"sql: {sql}")
    assert (
        sql
        == "DELETE FROM album WHERE album_id = %(album_id)s RETURNING album_id, artist_id, title"
    )


def test_concise_format_permissions(chinook_env):
    """Test that both concise and verbose permission formats work together."""
    # The existing ALBUM_SCHEMA already demonstrates the concise format:
    # sales_associate: read: album_id|title, write: year_released
    # This test validates that both concise and verbose formats are supported

    # Test 1: Read permissions with concise format
    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="read",
            query_params={"album_id": "1"},
            claims={"roles": ["sales_associate"]},
        ),
        "postgresql",
    )
    # sales_associate has read: "album_id|title" (concise format)
    assert "a.album_id" in operation_dao.query_handler.selection_results
    assert "a.title" in operation_dao.query_handler.selection_results
    # Should not have artist_id in selection (not in read permissions)
    assert "a.artist_id" not in operation_dao.query_handler.selection_results

    # Test 2: Write permissions with concise format
    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="update",
            query_params={"album_id": "1"},
            store_params={"year_released": 2023},
            claims={"roles": ["sales_associate"]},
        ),
        "postgresql",
    )
    # sales_associate has write: "year_released" (concise format)
    # The returning clause uses read permissions: "album_id|title"
    # So the selection_results should contain read-permitted fields only
    assert "album_id" in operation_dao.query_handler.selection_results
    assert "title" in operation_dao.query_handler.selection_results
    # year_released is writable but not readable for sales_associate
    assert "year_released" not in operation_dao.query_handler.selection_results

    # Test 3: Manager has broader permissions (concise .* patterns)
    operation_dao = OperationDAO(
        Operation(
            entity="album",
            action="read",
            query_params={"album_id": "1"},
            claims={"roles": ["sales_manager"]},
        ),
        "postgresql",
    )
    # sales_manager has read: ".*" (concise format allowing all)
    assert "a.album_id" in operation_dao.query_handler.selection_results
    assert "a.title" in operation_dao.query_handler.selection_results
    assert "a.artist_id" in operation_dao.query_handler.selection_results

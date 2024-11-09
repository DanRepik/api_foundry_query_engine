import pytest

from datetime import datetime

from api_foundry_query_engine.dao.sql_insert_query_handler import (
    SQLInsertSchemaQueryHandler,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.logger import logger
from tests.test_schema_objects_fixtures import (
    invoice_with_datetime_version_stamp,
    invoice_without_version_stamp,
    invoice_with_uuid_version_stamp,
    genre_schema_with_timestamp,
    genre_schema_with_serial_number,
    genre_schema_required_key,
    genre_schema_seqnence_key,
)

log = logger(__name__)


@pytest.mark.unit
class TestInsertSQLHandler:
    def test_insert_uuid(self):
        sql_handler = SQLInsertSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="create",
                store_params={
                    "customer_id": "2",
                    "invoice_date": "2024-03-17",
                    "billing_address": "Theodor-Heuss-Straße 34",
                    "billing_city": "Stuttgart",
                    "billing_country": "Germany",
                    "billing_postal_code": "70174",
                    "total": "1.63",
                },
            ),
            invoice_with_uuid_version_stamp(),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "INSERT INTO invoice ( customer_id, invoice_date, billing_address, "
            + "billing_city, billing_country, billing_postal_code, total, version_stamp ) "
            + "VALUES ( %(customer_id)s, %(invoice_date)s, %(billing_address)s, "
            + "%(billing_city)s, %(billing_country)s, %(billing_postal_code)s, %(total)s, "
            + "gen_random_uuid()) "
            + "RETURNING billing_address, billing_city, billing_country, "
            + "billing_postal_code, billing_state, customer_id, invoice_date, "
            + "invoice_id, version_stamp, total"
        )

        assert sql_handler.placeholders == {
            "customer_id": 2,
            "invoice_date": datetime(2024, 3, 17, 0, 0),
            "billing_address": "Theodor-Heuss-Straße 34",
            "billing_city": "Stuttgart",
            "billing_country": "Germany",
            "billing_postal_code": "70174",
            "total": 1.63,
        }

    def test_insert_no_cc(self):  # noqa F811
        sql_handler = SQLInsertSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="create",
                store_params={
                    "customer_id": "2",
                    "invoice_date": "2024-03-17",
                    "billing_address": "Theodor-Heuss-Straße 34",
                    "billing_city": "Stuttgart",
                    "billing_country": "Germany",
                    "billing_postal_code": "70174",
                    "total": "1.63",
                },
            ),
            invoice_without_version_stamp(),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "INSERT INTO invoice ( customer_id, invoice_date, billing_address, "
            + "billing_city, billing_country, billing_postal_code, total ) "
            + "VALUES ( %(customer_id)s, %(invoice_date)s, %(billing_address)s, "
            + "%(billing_city)s, %(billing_country)s, %(billing_postal_code)s, "
            + "%(total)s) "
            + "RETURNING billing_address, billing_city, billing_country, "
            + "billing_postal_code, billing_state, customer_id, invoice_date, "
            + "invoice_id, total"
        )

        assert sql_handler.placeholders == {
            "customer_id": 2,
            "invoice_date": datetime(2024, 3, 17, 0, 0),
            "billing_address": "Theodor-Heuss-Straße 34",
            "billing_city": "Stuttgart",
            "billing_country": "Germany",
            "billing_postal_code": "70174",
            "total": 1.63,
        }

    def test_insert_property_selection(self):
        sql_handler = SQLInsertSchemaQueryHandler(
            Operation(
                entity="invoice",
                action="create",
                store_params={
                    "customer_id": "2",
                    "invoice_date": "2024-03-17",
                    "billing_address": "Theodor-Heuss-Straße 34",
                    "billing_city": "Stuttgart",
                    "billing_country": "Germany",
                    "billing_postal_code": "70174",
                    "total": "1.63",
                },
                metadata_params={"_properties": "customer_id invoice_date"},
            ),
            invoice_with_datetime_version_stamp(),
            "postgres",
        )

        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "INSERT INTO invoice ( customer_id, invoice_date, billing_address, "
            + "billing_city, billing_country, billing_postal_code, total, last_updated ) "
            + "VALUES ( %(customer_id)s, %(invoice_date)s, %(billing_address)s, "
            + "%(billing_city)s, %(billing_country)s, %(billing_postal_code)s, %(total)s, "
            + "CURRENT_TIMESTAMP) RETURNING customer_id, invoice_date"
        )

        assert sql_handler.placeholders == {
            "customer_id": 2,
            "invoice_date": datetime(2024, 3, 17, 0, 0),
            "billing_address": "Theodor-Heuss-Straße 34",
            "billing_city": "Stuttgart",
            "billing_country": "Germany",
            "billing_postal_code": "70174",
            "total": 1.63,
        }

    def test_insert_bad_key(self):
        try:
            SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={"genre_id": 34, "description": "Bad genre"},
                ),
                genre_schema_with_timestamp(),
                "postgres",
            )
            assert False, "Attempt to set primary key during insert did not fail"
        except ApplicationException as e:
            assert (
                e.message
                == "Primary key values cannot be inserted when key type is auto. schema_object: genre"
            )

    def test_insert_missing_required_key(self):
        try:
            SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={"description": "Bad genre"},
                ),
                genre_schema_required_key(),
                "postgres",
            )
            assert False, "Attempt to insert without a required key did not fail"
        except ApplicationException:
            pass

    def test_insert_auto_key(self):
        try:
            SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={"genre_id": 34, "name": "Good genre"},
                ),
                genre_schema_with_timestamp(),
                "postgres",
            )
            assert False, "Attempt to set primary key during insert did not fail"
        except ApplicationException:
            pass

    def test_insert_sequence(self):
        sql_handler = SQLInsertSchemaQueryHandler(
            Operation(
                entity="genre",
                action="create",
                store_params={"name": "Good genre"},
            ),
            genre_schema_seqnence_key(),
            "postgres",
        )
        log.info(f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}")

        assert (
            sql_handler.sql
            == "INSERT INTO genre ( name, genre_id ) "
            + "VALUES ( %(name)s, nextval('test-sequence')) "
            + "RETURNING genre_id, name"
        )
        assert sql_handler.placeholders == {"name": "Good genre"}

    def test_insert_timestamp(self):
        try:
            sql_handler = SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={"name": "New genre"},
                ),
                genre_schema_with_timestamp(),
                "postgres",
            )
            log.info(
                f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"
            )
            assert (
                sql_handler.sql
                == "INSERT INTO genre ( name, last_updated ) "
                + "VALUES ( %(name)s, CURRENT_TIMESTAMP) "
                + "RETURNING genre_id, name, last_updated"
            )

            "RETURNING genre_id, name, last_updated"

            assert sql_handler.placeholders == {"name": "New genre"}
        except ApplicationException:
            assert False

    def test_insert_cc_with_param(self):
        try:
            SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={
                        "name": "New genre",
                        "last_updated": "test uuid",
                    },
                ),
                genre_schema_with_timestamp(),
                "postgres",
            )
            assert False, "Attempt to set primary key during insert did not fail"
        except ApplicationException as e:
            assert (
                e.message
                == "Versioned properties can not be supplied a store parameters. "
                + "schema_object: genre, property: last_updated"
            )

    def test_insert_serial(self):
        try:
            sql_handler = SQLInsertSchemaQueryHandler(
                Operation(
                    entity="genre",
                    action="create",
                    store_params={"name": "New genre"},
                ),
                genre_schema_with_serial_number(),
                "postgres",
            )
            log.info(
                f"sql: {sql_handler.sql}, placeholders: {sql_handler.placeholders}"
            )
            assert (
                sql_handler.sql
                == "INSERT INTO genre ( name, version ) VALUES ( %(name)s, 1) "
                + "RETURNING genre_id, name, version"
            )
            assert sql_handler.placeholders == {"name": "New genre"}
        except ApplicationException:
            assert False

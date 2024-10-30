import os
import yaml
from typing import Optional

from api_foundry_query_engine.utils.api_model import APIModel, SchemaObject

def load_api(filename: Optional[str] = None):
    if not filename:
        filename = os.path.join(os.getcwd(), "resources/api_spec.yaml")
    with open(filename, "r") as file:
        APIModel(yaml.safe_load(file))


def invoice_with_datetime_version_stamp():
    return SchemaObject(
        {
            "api_name": "invoice",
            "concurrency_property": "last_updated",
            "database": "chinook",
            "primary_key": "invoice_id",
            "table_name": "invoice",
            "properties": {
                "billing_address": {
                    "api_name": "billing_address",
                    "api_type": "string",
                    "column_name": "billing_address",
                    "column_type": "string",
                    "max_length": 70,
                    "required": False,
                },
                "billing_city": {
                    "api_name": "billing_city",
                    "api_type": "string",
                    "column_name": "billing_city",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_country": {
                    "api_name": "billing_country",
                    "api_type": "string",
                    "column_name": "billing_country",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_postal_code": {
                    "api_name": "billing_postal_code",
                    "api_type": "string",
                    "column_name": "billing_postal_code",
                    "column_type": "string",
                    "max_length": 10,
                    "required": False,
                },
                "billing_state": {
                    "api_name": "billing_state",
                    "api_type": "string",
                    "column_name": "billing_state",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "customer_id": {
                    "api_name": "customer_id",
                    "api_type": "integer",
                    "column_name": "customer_id",
                    "column_type": "integer",
                    "required": False,
                },
                "invoice_date": {
                    "api_name": "invoice_date",
                    "api_type": "date-time",
                    "column_name": "invoice_date",
                    "column_type": "date-time",
                    "required": False,
                },
                "invoice_id": {
                    "api_name": "invoice_id",
                    "api_type": "integer",
                    "column_name": "invoice_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "last_updated": {
                    "api_name": "last_updated",
                    "api_type": "date-time",
                    "column_name": "last_updated",
                    "column_type": "date-time",
                    "required": False,
                },
                "total": {
                    "api_name": "total",
                    "api_type": "number",
                    "column_name": "total",
                    "column_type": "number",
                    "required": False,
                },
            },
        },
    )


def invoice_with_uuid_version_stamp():
    return SchemaObject(
        {
            "api_name": "invoice",
            "concurrency_property": "version_stamp",
            "database": "chinook",
            "primary_key": "invoice_id",
            "table_name": "invoice",
            "properties": {
                "billing_address": {
                    "api_name": "billing_address",
                    "api_type": "string",
                    "column_name": "billing_address",
                    "column_type": "string",
                    "max_length": 70,
                    "required": False,
                },
                "billing_city": {
                    "api_name": "billing_city",
                    "api_type": "string",
                    "column_name": "billing_city",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_country": {
                    "api_name": "billing_country",
                    "api_type": "string",
                    "column_name": "billing_country",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_postal_code": {
                    "api_name": "billing_postal_code",
                    "api_type": "string",
                    "column_name": "billing_postal_code",
                    "column_type": "string",
                    "max_length": 10,
                    "required": False,
                },
                "billing_state": {
                    "api_name": "billing_state",
                    "api_type": "string",
                    "column_name": "billing_state",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "customer_id": {
                    "api_name": "customer_id",
                    "api_type": "integer",
                    "column_name": "customer_id",
                    "column_type": "integer",
                    "required": False,
                },
                "invoice_date": {
                    "api_name": "invoice_date",
                    "api_type": "date-time",
                    "column_name": "invoice_date",
                    "column_type": "date-time",
                    "required": False,
                },
                "invoice_id": {
                    "api_name": "invoice_id",
                    "api_type": "integer",
                    "column_name": "invoice_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "version_stamp": {
                    "api_name": "version_stamp",
                    "api_type": "string",
                    "column_name": "version_stamp",
                    "column_type": "string",
                    "required": "false",
                },
                "total": {
                    "api_name": "total",
                    "api_type": "number",
                    "column_name": "total",
                    "column_type": "number",
                    "required": False,
                },
            },
        }
    )


def invoice_with_integer_version_stamp():
    return SchemaObject(
        {
            "api_name": "invoice",
            "concurrency_property": "version_stamp",
            "database": "chinook",
            "primary_key": "invoice_id",
            "table_name": "invoice",
            "properties": {
                "billing_address": {
                    "api_name": "billing_address",
                    "api_type": "string",
                    "column_name": "billing_address",
                    "column_type": "string",
                    "max_length": 70,
                    "required": False,
                },
                "billing_city": {
                    "api_name": "billing_city",
                    "api_type": "string",
                    "column_name": "billing_city",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_country": {
                    "api_name": "billing_country",
                    "api_type": "string",
                    "column_name": "billing_country",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_postal_code": {
                    "api_name": "billing_postal_code",
                    "api_type": "string",
                    "column_name": "billing_postal_code",
                    "column_type": "string",
                    "max_length": 10,
                    "required": False,
                },
                "billing_state": {
                    "api_name": "billing_state",
                    "api_type": "string",
                    "column_name": "billing_state",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "customer_id": {
                    "api_name": "customer_id",
                    "api_type": "integer",
                    "column_name": "customer_id",
                    "column_type": "integer",
                    "required": False,
                },
                "invoice_date": {
                    "api_name": "invoice_date",
                    "api_type": "date-time",
                    "column_name": "invoice_date",
                    "column_type": "date-time",
                    "required": False,
                },
                "invoice_id": {
                    "api_name": "invoice_id",
                    "api_type": "integer",
                    "column_name": "invoice_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "version_stamp": {
                    "api_name": "version_stamp",
                    "api_type": "string",
                    "column_name": "version_stamp",
                    "column_type": "integer",
                    "required": "false",
                },
                "total": {
                    "api_name": "total",
                    "api_type": "number",
                    "column_name": "total",
                    "column_type": "number",
                    "required": False,
                },
            },
        }
    )


def invoice_without_version_stamp():
    return SchemaObject(
        {
            "api_name": "invoice",
            "database": "chinook",
            "primary_key": "invoice_id",
            "table_name": "invoice",
            "properties": {
                "billing_address": {
                    "api_name": "billing_address",
                    "api_type": "string",
                    "column_name": "billing_address",
                    "column_type": "string",
                    "max_length": 70,
                    "required": False,
                },
                "billing_city": {
                    "api_name": "billing_city",
                    "api_type": "string",
                    "column_name": "billing_city",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_country": {
                    "api_name": "billing_country",
                    "api_type": "string",
                    "column_name": "billing_country",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "billing_postal_code": {
                    "api_name": "billing_postal_code",
                    "api_type": "string",
                    "column_name": "billing_postal_code",
                    "column_type": "string",
                    "max_length": 10,
                    "required": False,
                },
                "billing_state": {
                    "api_name": "billing_state",
                    "api_type": "string",
                    "column_name": "billing_state",
                    "column_type": "string",
                    "max_length": 40,
                    "required": False,
                },
                "customer_id": {
                    "api_name": "customer_id",
                    "api_type": "integer",
                    "column_name": "customer_id",
                    "column_type": "integer",
                    "required": False,
                },
                "invoice_date": {
                    "api_name": "invoice_date",
                    "api_type": "date-time",
                    "column_name": "invoice_date",
                    "column_type": "date-time",
                    "required": False,
                },
                "invoice_id": {
                    "api_name": "invoice_id",
                    "api_type": "integer",
                    "column_name": "invoice_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "total": {
                    "api_name": "total",
                    "api_type": "number",
                    "column_name": "total",
                    "column_type": "number",
                    "required": False,
                },
            },
        }
    )


def genre_schema_with_timestamp():
    return SchemaObject(
        {
            "api_name": "genre",
            "database": "chinook",
            "primary_key": "genre_id",
            "concurrency_property": "last_updated",
            "table_name": "genre",
            "properties": {
                "genre_id": {
                    "api_name": "genre_id",
                    "api_type": "integer",
                    "column_name": "genre_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "name": {
                    "api_name": "name",
                    "api_type": "string",
                    "column_name": "name",
                    "column_type": "string",
                    "max_length": 120,
                    "required": False,
                },
                "last_updated": {
                    "api_name": "last_updated",
                    "api_type": "date-time",
                    "column_name": "last_updated",
                    "column_type": "date-time",
                    "required": True,
                },
            },
            "relations": {
                "track_items": {
                    "api_name": "track_items",
                    "child_property": "genre_id",
                    "parent_property": "genre_id",
                    "schema_name": "track",
                    "type": "array",
                }
            },
        }
    )

def genre_schema_with_serial_number():
    return SchemaObject(
        {
            "api_name": "genre",
            "database": "chinook",
            "primary_key": "genre_id",
            "concurrency_property": "version",
            "table_name": "genre",
            "properties": {
                "genre_id": {
                    "api_name": "genre_id",
                    "api_type": "integer",
                    "column_name": "genre_id",
                    "column_type": "integer",
                    "key_type": "auto",
                    "required": False,
                },
                "name": {
                    "api_name": "name",
                    "api_type": "string",
                    "column_name": "name",
                    "column_type": "string",
                    "max_length": 120,
                    "required": False,
                },
                "version": {
                    "api_name": "version",
                    "api_type": "integer",
                    "column_name": "version",
                    "column_type": "integer",
                    "required": True,
                },
            },
            "relations": {
                "track_items": {
                    "api_name": "track_items",
                    "child_property": "genre_id",
                    "parent_property": "genre_id",
                    "schema_name": "track",
                    "type": "array",
                }
            },
        }
    )

def genre_schema_required_key():
    return SchemaObject(
        {
            "api_name": "genre",
            "database": "chinook",
            "primary_key": "genre_id",
            "table_name": "genre",
            "properties": {
                "genre_id": {
                    "api_name": "genre_id",
                    "api_type": "integer",
                    "column_name": "genre_id",
                    "column_type": "integer",
                    "key_type": "required",
                    "required": False,
                },
                "name": {
                    "api_name": "name",
                    "api_type": "string",
                    "column_name": "name",
                    "column_type": "string",
                    "max_length": 120,
                    "required": False,
                },
                "version": {
                    "api_name": "version",
                    "api_type": "integer",
                    "column_name": "version",
                    "column_type": "integer",
                    "required": False,
                },
            },
            "relations": {
                "track_items": {
                    "api_name": "track_items",
                    "child_property": "genre_id",
                    "parent_property": "genre_id",
                    "schema_name": "track",
                    "type": "array",
                }
            },
        }
    )


def genre_schema_seqnence_key():
    return SchemaObject(
        {
            "api_name": "genre",
            "database": "chinook",
            "primary_key": "genre_id",
            "table_name": "genre",
            "properties": {
                "genre_id": {
                    "api_name": "genre_id",
                    "api_type": "integer",
                    "column_name": "genre_id",
                    "column_type": "integer",
                    "key_type": "sequence",
                    "sequence_name": "test-sequence",
                    "required": False,
                },
                "name": {
                    "api_name": "name",
                    "api_type": "string",
                    "column_name": "name",
                    "column_type": "string",
                    "max_length": 120,
                    "required": False,
                },
            },
            "relations": {
                "track_items": {
                    "api_name": "track_items",
                    "child_property": "genre_id",
                    "parent_property": "genre_id",
                    "schema_name": "track",
                    "type": "array",
                }
            },
        }
    )


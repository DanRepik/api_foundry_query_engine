import pytest
from api_foundry_query_engine.utils.logger import logger
from api_foundry_query_engine.utils.api_model import (
    ModelFactory,
    SchemaObject,
    SchemaObjectProperty,
)

log = logger(__name__)


@pytest.mark.unit
def test_set_spec():
    # Mock the file content of api_spec.yaml
    ModelFactory.set_spec(
        {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "x-af-database": "database",
                        "properties": {
                            "id": {"type": "integer", "x-af-primary-key": "auto"},
                            "name": {"type": "string"},
                        },
                    }
                }
            },
        }
    )

    assert "TestSchema" in ModelFactory.schema_objects
    schema_object = ModelFactory.get_schema_object("TestSchema")
    assert isinstance(schema_object, SchemaObject)
    assert schema_object.api_name == "TestSchema"


@pytest.mark.unit
def test_schema_object_initialization():
    log.info("starting test")
    ModelFactory.set_spec(
        {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "x-af-database": "testdb",
                        "properties": {
                            "id": {"type": "integer", "x-af-primary-key": "auto"},
                            "name": {"type": "string"},
                        },
                    }
                }
            },
        }
    )

    schema_object = ModelFactory.get_schema_object("TestSchema")
    assert schema_object.api_name == "TestSchema"
    assert schema_object.database == "testdb"
    assert schema_object.primary_key
    assert schema_object.primary_key.name == "id"
    assert schema_object.primary_key.key_type == "auto"


#    assert schema_object.primary_key.name == "id"


def test_schema_object_property_conversion():
    ModelFactory.set_spec(
        {
            "openapi": "3.0.0",
            "components": {
                "schemas": {
                    "TestSchema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer", "x-af-primary-key": "auto"},
                            "name": {"type": "string"},
                        },
                    }
                }
            },
        }
    )

    properties = {
        "type": "string",
        "x-af-column-name": "name",
        "x-af-column-type": "string",
        "x-af-primary-key": False,
    }
    property_object = SchemaObjectProperty(
        "test_entity", "name", properties, spec=ModelFactory.spec
    )
    db_value = property_object.convert_to_db_value("test_value")
    assert db_value == "test_value"
    api_value = property_object.convert_to_api_value("test_value")
    assert api_value == "test_value"

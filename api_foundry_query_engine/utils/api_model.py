import yaml

from datetime import datetime
from typing import Any, Dict, Optional

from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class SchemaObjectProperty:
    """Represents a property of a schema object."""

    def __init__(self, data: Dict[str, Any]):
        self.api_name = data.get("api_name")
        self.column_name = data.get("column_name")
        self.type = data.get("type")
        self.api_type = data.get("api_type")
        self.column_type = data.get("column_type")
        self.required = data.get("required", False)
        self.min_length = data.get("min_length")
        self.max_length = data.get("max_length")
        self.pattern = data.get("pattern")
        self.default = data.get("default")
        self.key_type = data.get("key_type")
        self.sequence_name = data.get("sequence_name")
        self.concurrency_control = data.get("concurrency_control")

    def __repr__(self):
        return f"SchemaObjectProperty(api_name={self.api_name}, column_name={self.column_name}, type={self.type})"

    def convert_to_db_value(self, value: str) -> Optional[Any]:
        if value is None:
            return None
        conversion_mapping = {
            "string": lambda x: x,
            "number": float,
            "float": float,
            "integer": int,
            "boolean": lambda x: x.lower() == "true",
            "date": lambda x: datetime.strptime(x, "%Y-%m-%d").date() if x else None,
            "date-time": lambda x: datetime.fromisoformat(x) if x else None,
            "time": lambda x: datetime.strptime(x, "%H:%M:%S").time() if x else None,
        }
        conversion_func = conversion_mapping.get(self.column_type, lambda x: x)
        return conversion_func(value)

    def convert_to_api_value(self, value) -> Optional[Any]:
        if value is None:
            return None
        conversion_mapping = {
            "string": lambda x: x,
            "number": float,
            "float": float,
            "integer": int,
            "boolean": str,
            "date": lambda x: x.date().isoformat() if x else None,
            "date-time": lambda x: x.isoformat() if x else None,
            "time": lambda x: x.time().isoformat() if x else None,
        }
        conversion_func = conversion_mapping.get(self.api_type, lambda x: x)
        return conversion_func(value)


class SchemaObjectAssociation:
    """Represents an association (relationship) between schema objects."""

    def __init__(self, parent_schema: str, data: Dict[str, Any]):
        self.parent_schema = parent_schema
        self.schema_name = data.get("schema_name")
        self.api_name = data.get("api_name")
        self.type = data.get("type")
        self._child_property = data.get("child_property")
        self._parent_property = data.get("parent_property")

    @property
    def child_property(self) -> str:
        return (
            self._child_property
            if self._child_property
            else get_schema_object(self.schema_name).primary_key.column_name
        )

    @property
    def parent_property(self) -> str:
        return (
            self._parent_property
            if self._parent_property
            else get_schema_object(self.parent_schema).primary_key.column_name
        )

    def __repr__(self):
        return (
            f"SchemaObjectAssociation(name={self.api_name}, "
            + f"child_property={self._child_property}, "
            + f"parent_property={self.parent_property})"
        )

    @property
    def child_schema_object(self) -> "SchemaObject":
        return get_schema_object(self.schema_name)


class SchemaObject:
    """Represents a schema object in the API configuration."""

    def __init__(self, data: Dict[str, Any]):
        self.api_name = data.get("api_name")
        self.database = data.get("database")
        self.table_name = data.get("table_name")
        self.properties = {
            name: SchemaObjectProperty(prop_data)
            for name, prop_data in data.get("properties", {}).items()
        }
        self.relations = {
            name: SchemaObjectAssociation(self.api_name, assoc_data)
            for name, assoc_data in data.get("relations", {}).items()
        }
        self.concurrency_property = (
            self.properties[data.get("concurrency_property")]
            if data.get("concurrency_property")
            else None
        )
        self._primary_key = data.get("primary_key")
        self.permissions = data.get("permissions")

    def __repr__(self):
        return f"SchemaObject(table_name={self.table_name}, primary_key={self.primary_key})"

    @property
    def primary_key(self):
        return self.properties.get(self._primary_key)


class PathOperation:
    """Represents a path operation in the API configuration."""

    def __init__(self, data: Dict[str, Any]):
        self.entity = data["entity"]
        self.action = data["action"]
        self.sql = data["sql"]
        self.database = data["database"]
        self.inputs = {
            name: SchemaObjectProperty(input_data)
            for name, input_data in data.get("inputs", {}).items()
        }
        self.outputs = {
            name: SchemaObjectProperty(output_data)
            for name, output_data in data.get("outputs", {}).items()
        }
        self.permissions = data.get("security")

    def __repr__(self):
        return f"PathOperation(entity={self.entity}, method={self.method})"


schema_objects = None
path_operations = None


def get_schema_object(name: str) -> Optional[SchemaObject]:
    """Returns a schema object by name."""
    global schema_objects
    return schema_objects.get(name)


def get_path_operation(path: str, method: str) -> Optional[PathOperation]:
    """Returns a path operation by name."""
    log.info(f"path: {path}, method: {method}")
    global path_operations
    return path_operations.get(f"{path}_{method}")


class APIModel:
    """Class to load and expose the API configuration as objects."""

    def __init__(self, config: Dict[str, Any]):
        print("building api_model")
        global schema_objects
        schema_objects = {
            name: SchemaObject(schema_data)
            for name, schema_data in config.get("schema_objects", {}).items()
        }
        global path_operations
        path_operations = {
            name: PathOperation(path_data)
            for name, path_data in config.get("path_operations", {}).items()
        }

    def __repr__(self):
        return (
            f"APIModel(schema_objects={list(self.schema_objects.keys())}, "
            + f"path_operations={list(self.path_operations.keys())})"
        )


def load_api(filename: str):
    with open(filename, "r") as file:
        APIModel(yaml.safe_load(file))

import os
import yaml

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

api_model = None


def get_schema_object(name: str) -> Optional["SchemaObject"]:
    global api_model
    if api_model is None:
        return None
    return api_model.schema_objects.get(name)


def get_path_operation(path: str, method: str) -> Optional["PathOperation"]:
    global api_model
    if api_model is None:
        return None
    return api_model.path_operations.get(f"{path}_{method}")


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
        self.inject_value = data.get("inject_value")
        self.inject_on = data.get("inject_on", [])
        self.soft_delete = data.get("x-af-soft-delete") or data.get("soft_delete")

    def __repr__(self):
        return f"SchemaObjectProperty(api_name={self.api_name}, column_name={self.column_name}, type={self.type})"

    def convert_to_db_value(self, value) -> Optional[Any]:
        if value is None:
            return None

        column_type = self.column_type if self.column_type is not None else "string"

        # Handle string types
        if column_type in ["string", "varchar", "char", "text", "uuid"]:
            return value

        # Handle numeric types - float/double/numeric variations
        elif column_type in ["number", "float", "double", "numeric", "decimal", "real"]:
            return float(value)

        # Handle boolean types - can map to boolean or integer columns
        elif column_type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() == "true"
        elif (
            column_type in ["int", "integer", "smallint", "bigint"]
            and hasattr(self, "api_type")
            and self.api_type == "boolean"
        ):
            # Boolean API type mapping to integer column type
            if isinstance(value, bool):
                return 1 if value else 0
            return 1 if str(value).lower() == "true" else 0

        # Handle integer types (after boolean check to avoid conflicts)
        elif column_type in [
            "integer",
            "int",
            "bigint",
            "smallint",
            "serial",
            "bigserial",
        ]:
            return int(value)

        # Handle date types
        elif column_type == "date":
            return datetime.strptime(value, "%Y-%m-%d").date() if value else None

        # Handle datetime types - various column type names
        elif column_type in ["date-time", "datetime", "timestamp", "timestamptz"]:
            return datetime.fromisoformat(value) if value else None

        # Handle time types
        elif column_type in ["time", "timetz"]:
            return datetime.strptime(value, "%H:%M:%S").time() if value else None

        # Default to string conversion for unknown types
        else:
            return value

    def is_soft_delete_field(self) -> bool:
        """Check if this property is configured for soft delete."""
        return self.soft_delete is not None

    def get_soft_delete_strategy(self) -> str:
        """Get the soft delete strategy for this property."""
        if not self.soft_delete:
            return "none"
        return self.soft_delete.get("strategy", "none")

    def get_soft_delete_config(self) -> Dict[str, Any]:
        """Get the complete soft delete configuration."""
        return self.soft_delete or {}

    def convert_to_api_value(self, value) -> Optional[Any]:
        if value is None:
            return None

        api_type = self.api_type if self.api_type is not None else "string"

        # Handle string types (including UUID which is represented as string in API)
        if api_type in ["string", "uuid"]:
            return str(value) if value is not None else None

        # Handle integer type
        elif api_type == "integer":
            return int(value) if value is not None else None

        # Handle number and float types
        elif api_type in ["number", "float"]:
            return float(value) if value is not None else None

        # Handle boolean type - convert any value to string representation
        elif api_type == "boolean":
            if isinstance(value, bool):
                return str(value)
            elif isinstance(value, int):
                # Handle boolean stored as integer (0/1)
                return "true" if value != 0 else "false"
            elif isinstance(value, str):
                return value.lower() in ["true", "1", "yes", "on"]
            else:
                return str(bool(value))

        # Handle date type
        elif api_type == "date":
            if hasattr(value, "date"):
                # If it's a datetime, extract the date part
                return value.date().isoformat()
            elif hasattr(value, "isoformat"):
                # If it's already a date
                return value.isoformat()
            else:
                return str(value)

        # Handle datetime type
        elif api_type == "date-time":
            if hasattr(value, "isoformat"):
                return value.isoformat()
            else:
                return str(value)

        # Handle time type
        elif api_type == "time":
            if hasattr(value, "time"):
                # If it's a datetime, extract the time part
                return value.time().isoformat()
            elif hasattr(value, "isoformat"):
                # If it's already a time
                return value.isoformat()
            else:
                return str(value)

        # Default to string conversion for unknown types
        else:
            return str(value) if value is not None else None


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
        if self._child_property:
            return self._child_property
        if not self.schema_name:
            raise ValueError("schema_name is None in SchemaObjectAssociation")
        child_schema = get_schema_object(self.schema_name)
        if not child_schema:
            raise ValueError(f"SchemaObject '{self.schema_name}' not found")
        if not child_schema.primary_key:
            raise ValueError(f"Primary key not defined for schema '{self.schema_name}'")
        column_name = getattr(child_schema.primary_key, "column_name", None)
        if column_name is None:
            raise ValueError(
                f"Primary key property does not have 'column_name' for schema '{self.schema_name}'"
            )
        return column_name

    @property
    def parent_property(self) -> str:
        if self._parent_property:
            return self._parent_property
        parent_schema_obj = get_schema_object(self.parent_schema)
        if not parent_schema_obj:
            raise ValueError(f"SchemaObject '{self.parent_schema}' not found")
        if not parent_schema_obj.primary_key:
            raise ValueError(
                f"Primary key not defined for schema '{self.parent_schema}'"
            )
        column_name = getattr(parent_schema_obj.primary_key, "column_name", None)
        if column_name is None:
            raise ValueError(
                f"Primary key property does not have 'column_name' for schema '{self.parent_schema}'"
            )
        return column_name

    def __repr__(self):
        return (
            f"SchemaObjectAssociation(name={self.api_name}, "
            + f"child_property={self._child_property}, "
            + f"parent_property={self.parent_property})"
        )

    @property
    def child_schema_object(self) -> "SchemaObject":
        if self.schema_name is None:
            raise ValueError("schema_name is None in SchemaObjectAssociation")
        schema_obj = get_schema_object(self.schema_name)
        if schema_obj is None:
            raise ValueError(f"SchemaObject '{self.schema_name}' not found")
        return schema_obj


class SchemaObject:
    """Represents a schema object in the API configuration."""

    def __init__(self, data: Dict[str, Any]):
        self.api_name: str = str(data.get("api_name"))
        self.database: str = str(data.get("database"))
        self.schema: Optional[str] = data.get("schema")
        self.table_name: str = str(data.get("table_name"))
        self.qualified_name: str = (
            f"{self.schema}.{self.table_name}" if self.schema else self.table_name
        )
        self.properties: Dict[str, SchemaObjectProperty] = {
            name: SchemaObjectProperty(prop_data)
            for name, prop_data in data.get("properties", {}).items()
        }
        self.relations = {
            name: SchemaObjectAssociation(
                self.api_name if self.api_name is not None else "", assoc_data
            )
            for name, assoc_data in data.get("relations", {}).items()
        }
        self.concurrency_property = (
            self.properties[str(data.get("concurrency_property"))]
            if data.get("concurrency_property")
            else None
        )
        self._primary_key: str = str(data.get("primary_key"))
        self.permissions = data.get("permissions")

    def __repr__(self):
        return f"SchemaObject(table_name={self.table_name}, primary_key={self.primary_key})"

    @property
    def primary_key(self):
        return self.properties.get(self._primary_key)

    def has_soft_delete_support(self) -> bool:
        """Check if this schema object supports soft delete operations."""
        return len(self.get_soft_delete_properties()) > 0

    def get_soft_delete_properties(self) -> Dict[str, SchemaObjectProperty]:
        """Get all properties configured for soft delete filtering."""
        return {
            name: prop
            for name, prop in self.properties.items()
            if prop.is_soft_delete_field()
            and prop.get_soft_delete_strategy()
            in ["null_check", "boolean_flag", "exclude_values"]
        }

    def get_soft_delete_audit_properties(
        self,
    ) -> Dict[str, SchemaObjectProperty]:
        """Get properties used for soft delete audit trails."""
        return {
            name: prop
            for name, prop in self.properties.items()
            if prop.is_soft_delete_field()
            and prop.get_soft_delete_strategy() == "audit_field"
        }

    def get_soft_delete_strategies(self) -> List[str]:
        """Get list of all soft delete strategies used in this schema."""
        strategies = set()
        for prop in self.properties.values():
            if prop.is_soft_delete_field():
                strategies.add(prop.get_soft_delete_strategy())
        return list(strategies)


class PathOperation:
    """Represents a path operation in the API configuration."""

    def __init__(self, data: Dict[str, Any]):
        self.entity: str = data["entity"]
        self.action: str = data["action"]
        self.sql: str = data["sql"]
        self.database: str = data["database"]
        self.inputs: Dict[str, SchemaObjectProperty] = {
            name: SchemaObjectProperty(input_data)
            for name, input_data in data.get("inputs", {}).items()
        }
        self.outputs: Dict[str, SchemaObjectProperty] = {
            name: SchemaObjectProperty(output_data)
            for name, output_data in data.get("outputs", {}).items()
        }
        self.permissions = data.get("security")

    def __repr__(self):
        return f"PathOperation(entity={self.entity}, action={self.action})"


class APIModel:
    """Class to load and expose the API configuration as objects."""

    def __init__(self, config: Dict[str, Any]):
        log.info("building api_model")
        self.schema_objects = {
            name: SchemaObject(schema_data)
            for name, schema_data in config.get("schema_objects", {}).items()
        }
        self.path_operations = {
            name: PathOperation(path_data)
            for name, path_data in config.get("path_operations", {}).items()
        }

    def get_path_operation(self, path: str, method: str) -> Optional[PathOperation]:
        """Returns a path operation by name."""
        if self.path_operations is None:
            return None
        return self.path_operations.get(f"{path}_{method}")

    def __repr__(self):
        return (
            f"APIModel(schema_objects={list(self.schema_objects.keys())}, "
            + f"path_operations={list(self.path_operations.keys())})"
        )


def set_api_model(engine_config: Mapping[str, str]):
    global api_model
    if api_model is None:
        if engine_config.get("API_SPEC"):
            api_model = APIModel(yaml.safe_load(engine_config["API_SPEC"]))
        else:
            log.info("Loading API model from file")
            with open(
                os.environ.get("API_SPEC", "/var/task/api_spec.yaml"), "r"
            ) as file:
                api_model = APIModel(yaml.safe_load(file))
        log.info("Loaded API model: %s", api_model)

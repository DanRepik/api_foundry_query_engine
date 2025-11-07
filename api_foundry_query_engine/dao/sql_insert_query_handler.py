from typing import Optional
from api_foundry_query_engine.dao.sql_query_handler import SQLSchemaQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject, SchemaObjectProperty
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class SQLInsertSchemaQueryHandler(SQLSchemaQueryHandler):
    key_property: Optional[SchemaObjectProperty]

    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, schema_object, engine)
        self.key_property = schema_object.primary_key
        if self.key_property:
            if self.key_property.key_type == "auto":
                if operation.store_params.get(self.key_property.column_name):
                    raise ApplicationException(
                        400,
                        "Primary key values cannot be inserted when key type"
                        + f" is auto. schema_object: {schema_object.api_name}",
                    )
            elif self.key_property.key_type == "required":
                if not operation.store_params.get(self.key_property.column_name):
                    raise ApplicationException(
                        400,
                        "Primary key values must be provided when key type is"
                        + f" required. schema_object: {schema_object.api_name}",
                    )
        self.concurrency_property = schema_object.concurrency_property
        if self.concurrency_property and operation.store_params.get(
            self.concurrency_property.api_name
        ):
            raise ApplicationException(
                400,
                "Versioned properties can not be supplied a store parameters. "
                + f"schema_object: {schema_object.api_name}, "
                + f"property: {self.concurrency_property.api_name}",
            )

    @property
    def sql(self) -> str:
        self.concurrency_property = self.schema_object.concurrency_property
        if not self.concurrency_property:
            return (
                f"INSERT INTO {self.table_expression}{self.insert_values} "
                + f"RETURNING {self.select_list}"
            )

        if self.operation.store_params.get(self.concurrency_property.api_name):
            raise ApplicationException(
                400,
                "When inserting schema objects with a version property "
                + "the a version must not be supplied as a storage parameter."
                + f"  schema_object: {self.schema_object.api_name}, "
                + f"property: {self.concurrency_property.api_name}",
            )
        return (
            f"INSERT INTO {self.table_expression}{self.insert_values}"
            + f" RETURNING {self.select_list}"
        )

    @property
    def insert_values(self) -> str:
        self.store_placeholders = {}
        placeholders = []
        columns = []

        allowed_property_names = self.check_permissions(
            "write", self.schema_object.permissions, self.schema_object.properties
        )
        allowed_properties = {
            k: v
            for k, v in self.schema_object.properties.items()
            if k in allowed_property_names
        }
        log.info("allowed properties: %s", allowed_properties)

        import json

        # First, validate that user is not trying to set injected properties
        for property_name, property in self.schema_object.properties.items():
            if property.inject_value and property_name in self.operation.store_params:
                raise ApplicationException(
                    403,
                    f"Property '{property_name}' is auto-injected and "
                    + "cannot be set manually",
                )

        for name, value in self.operation.store_params.items():
            parts = name.split(".")

            if len(parts) > 1:
                raise ApplicationException(
                    400,
                    "Properties can not be set on associated objects " + name,
                )

            property = allowed_properties.get(parts[0], None)
            if property is None:
                if parts[0] not in self.schema_object.properties:
                    raise ApplicationException(400, f"Invalid property: {name}")
                else:
                    raise ApplicationException(
                        402,
                        f"Subject is not allowed to create with property: {parts[0]}",
                    )

            columns.append(property.column_name)
            if property.api_name is None:
                raise ApplicationException(
                    400, f"Property '{name}' does not have a valid api_name."
                )
            placeholders.append(self.placeholder(property, property.api_name))
            # Serialize embedded objects to JSON
            if property.api_type == "object":
                self.store_placeholders[property.api_name] = json.dumps(value)
            else:
                self.store_placeholders[
                    property.api_name
                ] = property.convert_to_db_value(value)

        # Inject values from claims/timestamps/etc for properties with
        # x-af-inject-value on CREATE
        for property_name, property in self.schema_object.properties.items():
            if property.inject_value and "create" in property.inject_on:
                injected_value = self.extract_injected_value(property.inject_value)
                if injected_value is not None:
                    placeholder_key = f"__inject_{property_name}"
                    columns.append(property.column_name)
                    placeholders.append(self.placeholder(property, placeholder_key))
                    self.store_placeholders[
                        placeholder_key
                    ] = property.convert_to_db_value(injected_value)
                elif property.required:
                    raise ApplicationException(
                        400,
                        f"Required injected property '{property_name}' "
                        + f"could not be populated from '{property.inject_value}'",
                    )

        if self.key_property:
            if self.key_property.key_type == "sequence":
                columns.append(self.key_property.column_name)
                placeholders.append(f"nextval('{self.key_property.sequence_name}')")

        if self.concurrency_property:
            columns.append(self.concurrency_property.column_name)
            if self.concurrency_property.column_type == "integer":
                placeholders.append("1")
            else:
                placeholders.append(
                    self.concurrency_generator(self.concurrency_property)
                )

        return f" ( {', '.join(columns)} ) VALUES ( {', '.join(placeholders)})"

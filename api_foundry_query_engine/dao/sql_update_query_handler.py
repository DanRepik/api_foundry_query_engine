from api_foundry_query_engine.dao.sql_query_handler import SQLSchemaQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject


class SQLUpdateSchemaQueryHandler(SQLSchemaQueryHandler):
    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, schema_object, engine)

    @property
    def sql(self) -> str:
        concurrency_property = self.schema_object.concurrency_property
        if not concurrency_property:
            return (
                f"UPDATE {self.table_expression}{self.update_values}"
                + f"{self.search_condition} RETURNING {self.select_list}"
            )

        if not self.operation.query_params.get(concurrency_property.api_name):
            raise ApplicationException(
                400,
                "Missing required concurrency management property.  "
                + f"schema_object: {self.schema_object.api_name}, "
                + f"property: {concurrency_property.api_name}",
            )
        if self.operation.store_params.get(concurrency_property.api_name):
            raise ApplicationException(
                400,
                "For updating concurrency managed schema objects the current version "
                + " may not be supplied as a storage parameter.  "
                + f"schema_object: {self.schema_object.api_name}, "
                + f"property: {concurrency_property.api_name}",
            )

        return f"UPDATE {self.table_expression}{self.update_values}, {concurrency_property.column_name} = {self.concurrency_generator(concurrency_property)} {self.search_condition} RETURNING {self.select_list}"  # noqa E501

    @property
    def update_values(self) -> str:
        self.store_placeholders = {}
        columns = []

        for name, value in self.operation.store_params.items():
            try:
                property = self.schema_object.properties[name]
            except KeyError:
                raise ApplicationException(
                    400, f"Search condition column not found {name}"
                )

            placeholder = property.api_name
            column_name = property.column_name

            columns.append(f"{column_name} = {self.placeholder(property, placeholder)}")
            self.store_placeholders[placeholder] = property.convert_to_db_value(value)

        return f" SET {', '.join(columns)}"
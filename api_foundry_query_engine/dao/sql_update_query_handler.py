import re
from typing import Match
from api_foundry_query_engine.dao.sql_query_handler import SQLSchemaQueryHandler
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.api_model import SchemaObject


class SQLUpdateSchemaQueryHandler(SQLSchemaQueryHandler):
    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, schema_object, engine)

    def _template_where(self, expr: str) -> str:
        """Template substitution for WHERE clause expressions with claim values."""
        if not expr:
            return expr

        def _quote(val: object) -> str:
            if val is None:
                return "NULL"
            if isinstance(val, (int, float)):
                return str(val)
            s = str(val).replace("'", "''")
            return f"'{s}'"

        def _replace(m: Match[str]) -> str:
            key = m.group(1)
            claims = self.operation.claims or {}
            return _quote(claims.get(key))

        return re.sub(r"\$\{claims\.([A-Za-z0-9_]+)\}", _replace, expr)

    def _row_where_clause(self) -> str:
        """
        Generate row-level WHERE clause based on write permissions.
        Only applies to UPDATE operations, not CREATE.
        """
        perms = getattr(self.schema_object, "permissions", None) or {}
        # provider-first default
        if "default" in perms:
            provider = perms.get("default", {}) or {}
            write_map = provider.get("write", {}) or {}
            role_permissions = perms.get("default", {})
        else:
            # legacy role-first -> synthesize write map
            write_map = {}
            role_permissions = perms
            for role, role_perms in perms.items():
                if isinstance(role_perms, dict):
                    write_map[role] = role_perms.get("write")

        filters = []
        for role in self.operation.roles or []:
            # Check for role-level WHERE clause (hybrid approach)
            role_where = None
            if isinstance(role_permissions.get(role), dict):
                role_where = role_permissions[role].get("where")

            # Check for operation-level WHERE clause
            operation_where = None
            rule = write_map.get(role)
            if isinstance(rule, dict):
                operation_where = rule.get("where")

            # Operation-level takes precedence, fallback to role-level
            where_clause = operation_where if operation_where else role_where

            if isinstance(where_clause, str) and where_clause.strip():
                filters.append(self._template_where(where_clause))

        if not filters:
            return ""
        return "(" + ") OR (".join(filters) + ")"

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
        allowed_property_names = self.check_permissions(
            "write", self.schema_object.permissions, self.schema_object.properties
        )
        allowed_properties = {
            k: v
            for k, v in self.schema_object.properties.items()
            if k in allowed_property_names
        }
        self.store_placeholders = {}
        columns = []
        invalid_columns = []

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
            property = allowed_properties.get(name, None)
            if property is None:
                invalid_columns.append(name)
                continue

            placeholder = (
                str(property.api_name) if property.api_name is not None else name
            )
            column_name = property.column_name

            columns.append(f"{column_name} = {self.placeholder(property, placeholder)}")
            # Serialize embedded objects to JSON
            if property.api_type == "object":
                self.store_placeholders[placeholder] = json.dumps(value)
            else:
                self.store_placeholders[placeholder] = property.convert_to_db_value(
                    value
                )

        # Inject values from claims/timestamps/etc for properties with
        # x-af-inject-value on UPDATE
        for property_name, property in self.schema_object.properties.items():
            if property.inject_value and "update" in property.inject_on:
                injected_value = self.extract_injected_value(property.inject_value)
                if injected_value is not None:
                    placeholder_key = f"__inject_{property_name}"
                    column_name = property.column_name
                    columns.append(
                        f"{column_name} = {self.placeholder(property, placeholder_key)}"
                    )
                    self.store_placeholders[
                        placeholder_key
                    ] = property.convert_to_db_value(injected_value)
                elif property.required:
                    raise ApplicationException(
                        400,
                        f"Required injected property '{property_name}' "
                        + f"could not be populated from '{property.inject_value}'",
                    )

        if invalid_columns:
            raise ApplicationException(
                403,
                f"Subject does not have permission to update properties: "
                f"{invalid_columns}",
            )
        return f" SET {', '.join(columns)}"

    @property
    def search_condition(self) -> str:
        """
        Override to add permission-based WHERE clause for UPDATE operations.
        """
        # Get the base search condition from parent class
        base_condition = super().search_condition

        # Get row-level permission filters
        row_filter = self._row_where_clause()

        # If we have both, combine them
        if base_condition and row_filter:
            # base_condition already has " WHERE ", so add AND
            return f"{base_condition} AND ({row_filter})"
        elif row_filter:
            # Only row filter, add WHERE prefix
            return f" WHERE ({row_filter})"
        else:
            # Only base condition or neither
            return base_condition

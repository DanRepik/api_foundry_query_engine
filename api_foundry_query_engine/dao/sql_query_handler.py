import re
from typing import Optional, List, Dict
from datetime import datetime, date

from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.api_model import SchemaObject, SchemaObjectProperty
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)

SQL_RESERVED_WORDS = {
    "select",
    "from",
    "where",
    "insert",
    "update",
    "delete",
    "join",
    "on",
    "order",
    "group",
    "having",
    "union",
    "distinct",
    "into",
    "as",
    "and",
    "or",
    "not",
    "in",
    "is",
    "null",
    "like",
    "between",
    "by",
    "case",
    "when",
    "then",
    "else",
    "end",
    "exists",
    "all",
    "any",
    "some",
    "limit",
    "offset",
    "fetch",
    "for",
    "create",
    "alter",
    "drop",
    "table",
    "index",
    "view",
    "trigger",
    "procedure",
    "function",
    "database",
    "schema",
    "grant",
    "revoke",
    "primary",
    "key",
    "foreign",
    "references",
    "check",
    "unique",
    "default",
    "with",
    "values",
    "set",
    "transaction",
    "commit",
    "rollback",
    "savepoint",
    "lock",
    "tablespace",
    "sequence",
    "if",
    "else",
    "elsif",
    "loop",
    "begin",
    "declare",
    "end",
    "open",
    "fetch",
    "close",
    "cursor",
    "next",
}

RELATIONAL_TYPES = {
    "lt": "<",
    "le": "<=",
    "eq": "=",
    "ge": ">=",
    "gt": ">",
    "in": "in",
    "not-in": "not-in",
    "between": "between",
    "not-between": "not-between",
}


class SQLQueryHandler:
    operation: Operation
    engine: str

    def __init__(
        self, operation: Operation, engine: str
    ):  # , schema_object: SchemaObject):
        self.operation = operation
        self.engine = engine
        self.__select_list_columns = None

    @property
    def sql(self) -> str:
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def placeholders(self) -> Dict[str, SchemaObjectProperty]:
        raise NotImplementedError("Subclasses must implement this method")

    @property
    def select_list_columns(self) -> List[str]:
        if not self.__select_list_columns:
            # Filter columns based on read permissions
            self.__select_list_columns = list(self.selection_results.keys())
        return self.__select_list_columns

    def marshal_record(self, record: dict) -> dict:
        """
        Converts a database record to an API-compatible dictionary,
        removing properties the user is not allowed to read.

        Args:
            record (dict): A dictionary representing a single database record.

        Returns:
            dict: A dictionary with only the properties the user is allowed to see.
        """
        result = {}
        for name, value in record.items():
            if name in self.selection_results:  # Check if the property is allowed
                property = self.selection_results[name]
                result[property.api_name] = property.convert_to_api_value(value)
        return result

    def placeholder(self, property: SchemaObjectProperty, param: str = "") -> str:
        if len(param) == 0:
            param = property.api_name

        if self.engine == "oracle":
            if property.column_type == "date":
                return f"TO_DATE(:{param}, 'YYYY-MM-DD')"
            elif property.column_type == "datetime":
                return f"TO_TIMESTAMP(:{param}, 'YYYY-MM-DD\"T\"HH24:MI:SS.FF')"
            elif property.column_type == "time":
                return f"TO_TIME(:{param}, 'HH24:MI:SS.FF')"
            return f":{param}"
        return f"%({param})s"

    def check_permissions(
        self,
        permission_type: str,
        permissions: Optional[dict],
        properties: Optional[List[str]],
    ) -> Dict[str, SchemaObjectProperty]:
        """
        Checks the user's permissions for the specified permission type.

        Args:
            permission_type (str): The type of permission to check ("read" or "write").
            properties (List[str], optional): Specific properties to check. If None,
                all schema properties are checked.

        Returns:
            List[str]: A list of properties the user is permitted to access.
        """
        # if permissions are not defined then no restrictions are applied
        log.info(
            f"checking permissions permission_type: {permission_type}, permissions: {permissions}"
        )
        if not permissions:
            return properties

        allowed_properties = {}

        for role in self.operation.roles:
            role_permissions = permissions.get(role, {})
            log.info(f"role: {role}, role_permissions: {role_permissions}")
            if len(role_permissions) == 0:
                continue
            for prop_name, property in properties.items():
                log.info(f"prop_name: {prop_name}, property: {property}")
                if permission_type == "read" and re.match(
                    role_permissions.get("read", ""), prop_name
                ):
                    allowed_properties[prop_name] = property
                if permission_type == "write" and re.match(
                    role_permissions.get("write", ""), prop_name
                ):
                    allowed_properties[prop_name] = property

        log.info(f"allowed_properties: {allowed_properties}")
        return allowed_properties

    @property
    def selection_results(self) -> Dict:
        raise NotImplementedError()

    def generate_sql_condition(
        self, property: SchemaObjectProperty, value, prefix: Optional[str] = None
    ) -> str:
        operand = "="
        if isinstance(value, str):
            parts = value.split("::", 1)
            operand = RELATIONAL_TYPES.get(parts[0], "=") if len(parts) > 1 else "="
            value_str = parts[-1]
        elif isinstance(value, (datetime, date)):
            value_str = value.isoformat()
        else:
            value_str = str(value)

        column = f"{prefix}.{property.column_name}" if prefix else property.column_name
        placeholder_name = (
            f"{prefix}_{property.api_name}" if prefix else property.api_name
        )

        if operand in ["between", "not-between"]:
            value_set = value_str.split(",")
            sql = f"{column} {'NOT ' if operand == 'not-between' else ''}BETWEEN {self.placeholder(property, f'{placeholder_name}_1')} AND {self.placeholder(property, f'{prefix}_{property.api_name}_2')}"  # noqa E501
        elif operand in ["in", "not-in"]:
            value_set = value_str.split(",")
            assignments = [
                self.placeholder(property, f"{placeholder_name}_{index}")
                for index, _ in enumerate(value_set)
            ]
            sql = f"{column} {'NOT ' if operand == 'not-in' else ''}IN ({', '.join(assignments)})"  # noqa E501
        else:
            sql = f"{column} {operand} {self.placeholder(property, placeholder_name)}"
        return sql

    def generate_placeholders(
        self, property: SchemaObjectProperty, value, prefix: Optional[str] = None
    ) -> dict:
        operand = "="

        if isinstance(value, str):
            parts = value.split("::", 1)
            operand = RELATIONAL_TYPES.get(parts[0], "=") if len(parts) > 1 else "="
            value_str = parts[-1]
        elif isinstance(value, (datetime, date)):
            value_str = value.isoformat()
        else:
            value_str = str(value)

        placeholder_name = (
            f"{prefix}_{property.api_name}" if prefix else property.api_name
        )
        placeholders = {}

        if operand in ["between", "not-between"]:
            value_set = value_str.split(",")
            placeholders = {
                f"{placeholder_name}_1": property.convert_to_db_value(value_set[0]),
                f"{placeholder_name}_2": property.convert_to_db_value(value_set[1]),
            }
        elif operand in ["in", "not-in"]:
            value_set = value_str.split(",")
            for index, item in enumerate(value_set):
                item_name = f"{placeholder_name}_{index}"
                placeholders[item_name] = property.convert_to_db_value(item)
        else:
            placeholders = {placeholder_name: property.convert_to_db_value(value_str)}

        return placeholders

    def search_value_assignment(
        self, property: SchemaObjectProperty, value, prefix: Optional[str] = None
    ) -> tuple[str, dict]:
        sql_condition = self.generate_sql_condition(property, value, prefix)
        placeholders = self.generate_placeholders(property, value, prefix)
        return sql_condition, placeholders


class SQLSchemaQueryHandler(SQLQueryHandler):
    schema_object: SchemaObject

    def __init__(
        self, operation: Operation, schema_object: SchemaObject, engine: str
    ) -> None:
        super().__init__(operation, engine)
        self.schema_object = schema_object
        self.single_table = self.__single_table()
        self.__select_list = None
        self.__selection_result_map = None
        self.search_placeholders = dict()
        self.store_placeholders = dict()
        self.active_prefixes = set()

    @property
    def sql(self) -> str:
        raise NotImplementedError("Subclasses should implement this method")

    @property
    def placeholders(self) -> dict:
        return {**self.search_placeholders, **self.store_placeholders}

    @property
    def prefix_map(self) -> Dict[str, str]:
        if not hasattr(self, "_prefix_map"):
            self._prefix_map = {}
            for entity in [
                self.schema_object.api_name,
                *self.schema_object.relations.keys(),
            ]:
                entity_lower = entity.lower()
                for i in range(1, len(entity_lower) + 1):
                    substring = entity_lower[:i]
                    if (
                        substring not in self._prefix_map.values()
                        and substring not in SQL_RESERVED_WORDS
                    ):
                        self._prefix_map[entity] = substring
                        break
        return self._prefix_map

    def __single_table(self) -> bool:
        if len(self.prefix_map) == 1 or self.operation.action == "create":
            return True
        if ":" in self.operation.metadata_params.get("properties", ""):
            return False
        for param in self.operation.query_params.keys():
            if "." in param:
                return False
        return True

    @property
    def select_list(self) -> str:
        if not self.__select_list:
            self.__select_list = ", ".join(self.select_list_columns)
        return self.__select_list

    @property
    def table_expression(self) -> str:
        return self.schema_object.table_name

    @property
    def selection_results(self) -> Dict:
        """
        Filters the schema properties to include only those the user is allowed to read.

        Returns:
            dict: A dictionary of allowed schema properties.
        """
        log.info("selection_result")
        if not hasattr(self, "__selection_results"):
            log.info(f"prefix_map: {self.prefix_map}")
            filters = self.operation.metadata_params.get("_properties", ".*").split()
            allowed_properties = self.check_permissions(
                "read", self.schema_object.permissions, self.schema_object.properties
            )
            self.__selection_results = self.filter_and_prefix_keys(
                filters, allowed_properties
            )
        return self.__selection_results

    @property
    def search_condition(self) -> str:
        self.search_placeholders = {}
        conditions = []
        for name, value in self.operation.query_params.items():
            if "." in name:
                raise ApplicationException(
                    400, "Selection on relations is not supported"
                )
            property = self.schema_object.properties.get(name)
            if not property:
                raise ApplicationException(
                    500, f"Search condition column not found {name}"
                )
            if (
                self.operation.action != "read"
                and isinstance(value, str)
                and re.match(
                    r"^(lt|le|eq|ne|gt|ge|in|not-in|between|not-between)::(.+)$", value
                )
                and self.schema_object.concurrency_property
            ):
                raise ApplicationException(
                    400,
                    "Concurrency settings prohibit multi-record updates "
                    + self.schema_object.api_name
                    + ", property: "
                    + property.api_name,
                )

            assignment, holders = self.search_value_assignment(property, value)
            conditions.append(assignment)
            self.search_placeholders.update(holders)
        return f" WHERE {' AND '.join(conditions)}" if conditions else ""

    def filter_and_prefix_keys(
        self, regex_list: List[str], properties: dict, prefix: Optional[str] = None
    ) -> dict:
        """
        Accepts a prefix string, list of regular expressions, and a dictionary.
        Returns a new dictionary containing items whose keys match any of the
        regular expressions, with the prefix string prepended to the key
        values of the dictionary.

        Parameters:
        - prefix (str): The prefix string to prepend to the key values.
        - regex_list (list of str): The list of regular expression patterns
                to match keys.
        - properties (dict): The input properties.

        Returns:
        - dict: A new dictionary containing filtered items with modified key values.
        """
        filtered_dict = {}
        compiled_regexes = [re.compile(regex) for regex in regex_list]
        for key, value in properties.items():
            for pattern in compiled_regexes:
                if pattern.match(key):
                    filtered_dict[f"{prefix}.{key}" if prefix else key] = value
                    self.active_prefixes.add(prefix)
                    break
        return filtered_dict

    def concurrency_generator(self, property: SchemaObjectProperty) -> str:
        if property.api_type == "date-time":
            return "CURRENT_TIMESTAMP"
        elif property.api_type == "integer":
            return f"{property.column_name} + 1"
        elif property.api_type in ["string", "uuid"]:
            if self.engine == "oracle":
                return "SYS_GUID()"
            if self.engine == "mysql":
                return "UUID()"
            return "gen_random_uuid()"
        raise ApplicationException(
            500,
            (
                "Concurrency control property is unrecognized type"
                + f"name: {property.api_name}, type: {property.api_type}"
            ),
        )

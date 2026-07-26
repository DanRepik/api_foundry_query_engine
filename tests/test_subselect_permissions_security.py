"""
Regression test: nested/associated (one-to-many) reads must enforce the
same field-level read permissions as top-level reads.

See docs/reviews/2026-07-26-batch-claims-spoofing-review.md for context:
SQLSubselectSchemaQueryHandler.selection_results previously built its column
list straight from schema_object.properties with no call to
check_permissions(), so a property restricted at the top level (e.g. a
role-gated 'salary' field) leaked through when fetched as a nested
association (e.g. GET /department?_properties=employees:.*).
"""

import pytest

from api_foundry_query_engine.utils import api_model as api_model_module
from api_foundry_query_engine.utils.api_model import APIModel
from api_foundry_query_engine.dao.sql_subselect_query_handler import (
    SQLSubselectSchemaQueryHandler,
)
from api_foundry_query_engine.operation import Operation


class DummyParentGenerator:
    engine = "postgres"


API_CONFIG = {
    "schema_objects": {
        "department": {
            "api_name": "department",
            "table_name": "department",
            "primary_key": "department_id",
            "properties": {
                "department_id": {
                    "api_name": "department_id",
                    "api_type": "integer",
                    "column_name": "department_id",
                    "column_type": "integer",
                },
            },
            "relations": {
                "employees": {
                    "schema_name": "employee",
                    "api_name": "employees",
                    "type": "array",
                    "parent_property": "department_id",
                    "child_property": "department_id",
                },
            },
        },
        "employee": {
            "api_name": "employee",
            "table_name": "employee",
            "primary_key": "employee_id",
            "properties": {
                "employee_id": {
                    "api_name": "employee_id",
                    "api_type": "integer",
                    "column_name": "employee_id",
                    "column_type": "integer",
                },
                "name": {
                    "api_name": "name",
                    "api_type": "string",
                    "column_name": "name",
                    "column_type": "string",
                },
                "salary": {
                    "api_name": "salary",
                    "api_type": "number",
                    "column_name": "salary",
                    "column_type": "numeric",
                },
            },
            "permissions": {
                "default": {
                    "read": {
                        "public": "employee_id|name",
                        "hr": ".*",
                    }
                }
            },
        },
    }
}


@pytest.fixture
def department_employees_relation(monkeypatch):
    monkeypatch.setattr(api_model_module, "api_model", APIModel(API_CONFIG))
    department = api_model_module.get_schema_object("department")
    return department.relations["employees"]


@pytest.mark.unit
def test_subselect_hides_restricted_property_for_unprivileged_role(
    department_employees_relation,
):
    operation = Operation(
        entity="department",
        action="read",
        metadata_params={"properties": "employees:.*"},
        claims={"roles": ["public"]},
    )
    handler = SQLSubselectSchemaQueryHandler(operation, department_employees_relation, DummyParentGenerator())

    columns = set(handler.selection_results.keys())

    assert "salary" not in columns
    assert "name" in columns
    assert "employee_id" in columns


@pytest.mark.unit
def test_subselect_allows_restricted_property_for_privileged_role(
    department_employees_relation,
):
    operation = Operation(
        entity="department",
        action="read",
        metadata_params={"properties": "employees:.*"},
        claims={"roles": ["hr"]},
    )
    handler = SQLSubselectSchemaQueryHandler(operation, department_employees_relation, DummyParentGenerator())

    columns = set(handler.selection_results.keys())

    assert {"employee_id", "name", "salary"}.issubset(columns)

"""
Unit tests for ReferenceResolver
"""

import pytest
from api_foundry_query_engine.utils.reference_resolver import ReferenceResolver
from api_foundry_query_engine.utils.app_exception import ApplicationException


@pytest.mark.unit
class TestReferenceResolver:
    def test_resolve_simple_reference(self):
        """Test resolving a simple scalar reference"""
        results = {
            "create_customer": {
                "status": "completed",
                "data": {"customer_id": 42, "name": "John Doe"},
            }
        }

        resolver = ReferenceResolver(results)
        params = {"customer_id": "$ref:create_customer.customer_id"}

        resolved = resolver.resolve_parameters(params)
        assert resolved["customer_id"] == 42

    def test_resolve_nested_reference(self):
        """Test resolving reference to nested property"""
        results = {
            "create_invoice": {
                "status": "completed",
                "data": {
                    "invoice_id": 100,
                    "customer": {"customer_id": 42, "name": "John"},
                },
            }
        }

        resolver = ReferenceResolver(results)
        params = {"id": "$ref:create_invoice.customer.customer_id"}

        resolved = resolver.resolve_parameters(params)
        assert resolved["id"] == 42

    def test_resolve_multiple_references(self):
        """Test resolving multiple references in different parameters"""
        results = {
            "op1": {"status": "completed", "data": {"value_a": 10}},
            "op2": {"status": "completed", "data": {"value_b": 20}},
        }

        resolver = ReferenceResolver(results)
        params = {
            "field1": "$ref:op1.value_a",
            "field2": "$ref:op2.value_b",
            "field3": "static_value",
        }

        resolved = resolver.resolve_parameters(params)
        assert resolved["field1"] == 10
        assert resolved["field2"] == 20
        assert resolved["field3"] == "static_value"

    def test_resolve_reference_in_string(self):
        """Test partial string replacement with reference"""
        results = {
            "op1": {"status": "completed", "data": {"id": 42}},
        }

        resolver = ReferenceResolver(results)
        params = {"message": "Customer ID is: $ref:op1.id"}

        resolved = resolver.resolve_parameters(params)
        assert resolved["message"] == "Customer ID is: 42"

    def test_resolve_nested_dict(self):
        """Test resolving references in nested dictionaries"""
        results = {
            "op1": {"status": "completed", "data": {"customer_id": 42}},
        }

        resolver = ReferenceResolver(results)
        params = {
            "invoice": {
                "customer_id": "$ref:op1.customer_id",
                "total": 100.50,
            }
        }

        resolved = resolver.resolve_parameters(params)
        assert resolved["invoice"]["customer_id"] == 42
        assert resolved["invoice"]["total"] == 100.50

    def test_resolve_array_values(self):
        """Test resolving references in arrays"""
        results = {
            "op1": {"status": "completed", "data": {"id": 42}},
        }

        resolver = ReferenceResolver(results)
        params = {"items": ["$ref:op1.id", 99, "$ref:op1.id"]}

        resolved = resolver.resolve_parameters(params)
        assert resolved["items"] == [42, 99, 42]

    def test_unknown_operation_reference(self):
        """Test error when referencing unknown operation"""
        results = {
            "op1": {"status": "completed", "data": {"id": 42}},
        }

        resolver = ReferenceResolver(results)
        params = {"field": "$ref:unknown_op.id"}

        with pytest.raises(ApplicationException) as exc_info:
            resolver.resolve_parameters(params)

        assert exc_info.value.status_code == 400
        assert "unknown operation" in exc_info.value.message.lower()

    def test_reference_to_failed_operation(self):
        """Test error when referencing a failed operation"""
        results = {
            "op1": {
                "status": "failed",
                "error": "Something went wrong",
            },
        }

        resolver = ReferenceResolver(results)
        params = {"field": "$ref:op1.id"}

        with pytest.raises(ApplicationException) as exc_info:
            resolver.resolve_parameters(params)

        assert exc_info.value.status_code == 400
        assert "failed" in exc_info.value.message.lower()

    def test_missing_property_in_result(self):
        """Test error when referenced property doesn't exist"""
        results = {
            "op1": {
                "status": "completed",
                "data": {"customer_id": 42},
            },
        }

        resolver = ReferenceResolver(results)
        params = {"field": "$ref:op1.missing_field"}

        with pytest.raises(ApplicationException) as exc_info:
            resolver.resolve_parameters(params)

        assert exc_info.value.status_code == 400
        assert "property not found" in exc_info.value.message.lower()

    def test_validate_references(self):
        """Test extracting all referenced operation IDs"""
        resolver = ReferenceResolver({})
        params = {
            "field1": "$ref:op1.value",
            "field2": "$ref:op2.value",
            "nested": {"field3": "$ref:op3.value"},
            "array": ["$ref:op1.value", "$ref:op4.value"],
        }

        refs = resolver.validate_references(params)
        assert set(refs) == {"op1", "op2", "op3", "op4"}

    def test_preserve_type_on_full_replacement(self):
        """Test that full reference replacement preserves original type"""
        results = {
            "op1": {
                "status": "completed",
                "data": {
                    "int_value": 42,
                    "float_value": 3.14,
                    "bool_value": True,
                },
            },
        }

        resolver = ReferenceResolver(results)
        params = {
            "int_field": "$ref:op1.int_value",
            "float_field": "$ref:op1.float_value",
            "bool_field": "$ref:op1.bool_value",
        }

        resolved = resolver.resolve_parameters(params)
        assert resolved["int_field"] == 42
        assert isinstance(resolved["int_field"], int)
        assert resolved["float_field"] == 3.14
        assert isinstance(resolved["float_field"], float)
        assert resolved["bool_field"] is True
        assert isinstance(resolved["bool_field"], bool)

    def test_array_index_reference(self):
        """Test referencing array elements by index"""
        results = {
            "op1": {
                "status": "completed",
                "data": {
                    "items": [
                        {"id": 1, "name": "First"},
                        {"id": 2, "name": "Second"},
                    ]
                },
            },
        }

        resolver = ReferenceResolver(results)
        params = {
            "first_id": "$ref:op1.items.0.id",
            "second_name": "$ref:op1.items.1.name",
        }

        resolved = resolver.resolve_parameters(params)
        assert resolved["first_id"] == 1
        assert resolved["second_name"] == "Second"

    def test_multiple_refs_in_single_string(self):
        """Test multiple references in a single string value"""
        results = {
            "op1": {"status": "completed", "data": {"first": "John"}},
            "op2": {"status": "completed", "data": {"last": "Doe"}},
        }

        resolver = ReferenceResolver(results)
        params = {"full_name": "$ref:op1.first $ref:op2.last"}

        resolved = resolver.resolve_parameters(params)
        assert resolved["full_name"] == "John Doe"

    def test_empty_parameters(self):
        """Test handling of empty/None parameters"""
        resolver = ReferenceResolver({})

        assert resolver.resolve_parameters({}) == {}
        assert resolver.resolve_parameters(None) is None

    def test_no_references(self):
        """Test that parameters without references pass through unchanged"""
        resolver = ReferenceResolver({})
        params = {
            "field1": "static_value",
            "field2": 42,
            "field3": {"nested": "value"},
            "field4": [1, 2, 3],
        }

        resolved = resolver.resolve_parameters(params)
        assert resolved == params

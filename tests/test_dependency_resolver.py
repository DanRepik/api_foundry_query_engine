"""
Unit tests for DependencyResolver
"""

import pytest
from api_foundry_query_engine.utils.dependency_resolver import DependencyResolver
from api_foundry_query_engine.utils.app_exception import ApplicationException


@pytest.mark.unit
class TestDependencyResolver:
    def test_simple_linear_dependencies(self):
        """Test linear dependency chain: A → B → C"""
        operations = [
            {"id": "op_c", "depends_on": ["op_b"]},
            {"id": "op_a", "depends_on": []},
            {"id": "op_b", "depends_on": ["op_a"]},
        ]

        resolver = DependencyResolver(operations)
        order = resolver.get_execution_order()

        assert order == ["op_a", "op_b", "op_c"]

    def test_parallel_operations(self):
        """Test operations with no dependencies (can run in parallel)"""
        operations = [
            {"id": "op_a"},
            {"id": "op_b"},
            {"id": "op_c"},
        ]

        resolver = DependencyResolver(operations)
        order = resolver.get_execution_order()

        # All should be in result (order doesn't matter)
        assert set(order) == {"op_a", "op_b", "op_c"}

    def test_diamond_dependencies(self):
        """Test diamond pattern: A → B,C → D"""
        operations = [
            {"id": "op_d", "depends_on": ["op_b", "op_c"]},
            {"id": "op_a"},
            {"id": "op_b", "depends_on": ["op_a"]},
            {"id": "op_c", "depends_on": ["op_a"]},
        ]

        resolver = DependencyResolver(operations)
        order = resolver.get_execution_order()

        # op_a must be first, op_d must be last
        assert order[0] == "op_a"
        assert order[3] == "op_d"
        # op_b and op_c can be in any order
        assert set(order[1:3]) == {"op_b", "op_c"}

    def test_circular_dependency_direct(self):
        """Test detection of direct circular dependency: A → B → A"""
        operations = [
            {"id": "op_a", "depends_on": ["op_b"]},
            {"id": "op_b", "depends_on": ["op_a"]},
        ]

        with pytest.raises(ApplicationException) as exc_info:
            resolver = DependencyResolver(operations)
            resolver.get_execution_order()

        assert exc_info.value.status_code == 400
        assert "Circular dependency" in exc_info.value.message

    def test_circular_dependency_indirect(self):
        """Test detection of indirect circular dependency: A → B → C → A"""
        operations = [
            {"id": "op_a", "depends_on": ["op_c"]},
            {"id": "op_b", "depends_on": ["op_a"]},
            {"id": "op_c", "depends_on": ["op_b"]},
        ]

        with pytest.raises(ApplicationException) as exc_info:
            resolver = DependencyResolver(operations)
            resolver.get_execution_order()

        assert exc_info.value.status_code == 400
        assert "Circular dependency" in exc_info.value.message

    def test_unknown_dependency(self):
        """Test error when operation depends on unknown operation"""
        operations = [
            {"id": "op_a", "depends_on": ["op_unknown"]},
        ]

        with pytest.raises(ApplicationException) as exc_info:
            DependencyResolver(operations)

        assert exc_info.value.status_code == 400
        assert "unknown operation" in exc_info.value.message

    def test_duplicate_operation_ids(self):
        """Test error when operations have duplicate IDs"""
        operations = [
            {"id": "op_a"},
            {"id": "op_b"},
            {"id": "op_a"},  # Duplicate
        ]

        with pytest.raises(ApplicationException) as exc_info:
            DependencyResolver(operations)

        assert exc_info.value.status_code == 400
        assert "Duplicate operation IDs" in exc_info.value.message

    def test_get_independent_operations(self):
        """Test finding operations with no dependencies"""
        operations = [
            {"id": "op_a"},
            {"id": "op_b", "depends_on": ["op_a"]},
            {"id": "op_c"},
            {"id": "op_d", "depends_on": ["op_b"]},
        ]

        resolver = DependencyResolver(operations)
        independent = resolver.get_independent_operations()

        assert independent == {"op_a", "op_c"}

    def test_get_dependents(self):
        """Test finding operations that depend on a given operation"""
        operations = [
            {"id": "op_a"},
            {"id": "op_b", "depends_on": ["op_a"]},
            {"id": "op_c", "depends_on": ["op_a"]},
            {"id": "op_d", "depends_on": ["op_b"]},
        ]

        resolver = DependencyResolver(operations)

        # op_a has two direct dependents
        assert set(resolver.get_dependents("op_a")) == {"op_b", "op_c"}

        # op_b has one dependent
        assert resolver.get_dependents("op_b") == ["op_d"]

        # op_d has no dependents
        assert resolver.get_dependents("op_d") == []

    def test_complex_dependency_graph(self):
        """Test complex multi-level dependency graph"""
        operations = [
            {"id": "create_customer"},
            {"id": "create_invoice", "depends_on": ["create_customer"]},
            {"id": "create_line_1", "depends_on": ["create_invoice"]},
            {"id": "create_line_2", "depends_on": ["create_invoice"]},
            {"id": "create_line_3", "depends_on": ["create_invoice"]},
            {
                "id": "update_total",
                "depends_on": [
                    "create_line_1",
                    "create_line_2",
                    "create_line_3",
                ],
            },
        ]

        resolver = DependencyResolver(operations)
        order = resolver.get_execution_order()

        # Verify execution order constraints
        assert order.index("create_customer") < order.index("create_invoice")
        assert order.index("create_invoice") < order.index("create_line_1")
        assert order.index("create_invoice") < order.index("create_line_2")
        assert order.index("create_invoice") < order.index("create_line_3")
        assert order.index("update_total") == len(order) - 1  # Must be last

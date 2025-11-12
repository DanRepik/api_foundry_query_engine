"""
Dependency Resolver for Batch Operations

Performs topological sorting of operations based on their dependency relationships.
Detects circular dependencies and provides clear error messages.
"""

from typing import List, Dict, Set
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class DependencyResolver:
    """Resolves operation dependencies and determines execution order."""

    def __init__(self, operations: List[Dict]):
        """
        Initialize the dependency resolver.

        Args:
            operations: List of operation dictionaries with 'id' and optional 'depends_on'
        """
        self.operations = operations
        self.op_map = {op["id"]: op for op in operations}
        self._validate_operations()

    def _validate_operations(self):
        """Validate that operations have unique IDs and valid dependencies."""
        # Check for unique IDs
        ids = [op["id"] for op in self.operations]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ApplicationException(
                400, f"Duplicate operation IDs found: {set(duplicates)}"
            )

        # Check that all dependencies reference valid operation IDs
        for op in self.operations:
            depends_on = op.get("depends_on", [])
            for dep_id in depends_on:
                if dep_id not in self.op_map:
                    raise ApplicationException(
                        400,
                        f"Operation '{op['id']}' depends on unknown operation '{dep_id}'",
                    )

    def get_execution_order(self) -> List[str]:
        """
        Determine execution order using topological sort (Kahn's algorithm).

        Returns:
            List of operation IDs in execution order

        Raises:
            ApplicationException: If circular dependencies detected
        """
        # Build adjacency list and in-degree map
        # graph maps: operation_id -> list of operations it depends on
        graph = {op["id"]: op.get("depends_on", []) for op in self.operations}
        in_degree = {op_id: 0 for op_id in graph}

        # Calculate in-degrees - how many dependencies each operation has
        for op_id, dependencies in graph.items():
            in_degree[op_id] = len(dependencies)

        # Find all nodes with no dependencies (in-degree = 0)
        queue = [op_id for op_id, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Remove node from queue
            node = queue.pop(0)
            result.append(node)

            # For each operation that depends on this node, reduce in-degree
            for op_id, dependencies in graph.items():
                if node in dependencies:
                    in_degree[op_id] -= 1
                    if in_degree[op_id] == 0:
                        queue.append(op_id)

        # If result doesn't contain all nodes, there's a cycle
        if len(result) != len(graph):
            cycle = self._find_cycle(graph)
            raise ApplicationException(
                400, f"Circular dependency detected: {' -> '.join(cycle)}"
            )

        log.info(f"Execution order determined: {result}")
        return result

    def _find_cycle(self, graph: Dict[str, List[str]]) -> List[str]:
        """
        Find and return a cycle in the dependency graph for error reporting.

        Args:
            graph: Adjacency list representation of dependencies

        Returns:
            List of operation IDs forming a cycle
        """
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> List[str]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Check all dependencies
            for dependency in graph.get(node, []):
                if dependency not in visited:
                    cycle = dfs(dependency, path[:])
                    if cycle:
                        return cycle
                elif dependency in rec_stack:
                    # Found cycle - return the cycle path
                    cycle_start = path.index(dependency)
                    return path[cycle_start:] + [dependency]

            rec_stack.remove(node)
            return []

        for node in graph:
            if node not in visited:
                cycle = dfs(node, [])
                if cycle:
                    return cycle

        return []

    def get_independent_operations(self) -> Set[str]:
        """
        Get operations that have no dependencies (can execute immediately).

        Returns:
            Set of operation IDs with no dependencies
        """
        return {op["id"] for op in self.operations if not op.get("depends_on", [])}

    def get_dependents(self, op_id: str) -> List[str]:
        """
        Get all operations that depend on the given operation.

        Args:
            op_id: Operation ID to check

        Returns:
            List of operation IDs that depend on op_id
        """
        dependents = []
        for op in self.operations:
            if op_id in op.get("depends_on", []):
                dependents.append(op["id"])
        return dependents

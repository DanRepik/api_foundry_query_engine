"""
Reference Resolver for Batch Operations

Resolves $ref: placeholders in operation parameters with values from
previously executed operations.
"""

import re
from typing import Dict, Any, List
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class ReferenceResolver:
    """Resolves $ref: references to values from completed operations."""

    REF_PATTERN = re.compile(r"\$ref:([a-zA-Z0-9_]+)\.([a-zA-Z0-9_.]+)")

    def __init__(self, results: Dict[str, Dict[str, Any]]):
        """
        Initialize the reference resolver.

        Args:
            results: Dictionary mapping operation IDs to their results
        """
        self.results = results

    def resolve_parameters(
        self, params: Dict[str, Any], operation_id: str = None
    ) -> Dict[str, Any]:
        """
        Resolve all $ref: references in parameters.

        Args:
            params: Parameter dictionary potentially containing references
            operation_id: ID of the operation being resolved (for logging)

        Returns:
            Parameters with all references replaced with actual values

        Raises:
            ApplicationException: If reference cannot be resolved
        """
        if not params:
            return params

        resolved = {}
        for key, value in params.items():
            resolved[key] = self._resolve_value(value, key, operation_id)

        return resolved

    def _resolve_value(
        self, value: Any, param_name: str = None, operation_id: str = None
    ) -> Any:
        """
        Recursively resolve a parameter value.

        Args:
            value: The value to resolve
            param_name: Name of the parameter (for error messages)
            operation_id: ID of the operation (for error messages)

        Returns:
            Resolved value
        """
        if isinstance(value, str):
            return self._resolve_string_value(value, param_name, operation_id)
        elif isinstance(value, dict):
            return {
                k: self._resolve_value(v, f"{param_name}.{k}", operation_id)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [
                self._resolve_value(item, f"{param_name}[{i}]", operation_id)
                for i, item in enumerate(value)
            ]
        else:
            return value

    def _resolve_string_value(
        self, value: str, param_name: str = None, operation_id: str = None
    ) -> Any:
        """
        Resolve a string value that may contain $ref: references.

        Supports:
        - Full replacement: "$ref:op1.customer_id" → 42
        - Partial replacement: "prefix_$ref:op1.id_suffix" → "prefix_42_suffix"

        Args:
            value: String value to resolve
            param_name: Name of the parameter (for error messages)
            operation_id: ID of the operation (for error messages)

        Returns:
            Resolved value (may not be string if full replacement)
        """
        if not isinstance(value, str) or "$ref:" not in value:
            return value

        matches = list(self.REF_PATTERN.finditer(value))

        # If entire string is a single reference, return the actual type
        if len(matches) == 1 and matches[0].group(0) == value:
            return self._extract_reference(
                matches[0].group(1), matches[0].group(2), param_name, operation_id
            )

        # Otherwise, perform string substitution
        result = value
        for match in matches:
            ref_op_id = match.group(1)
            ref_path = match.group(2)
            ref_value = self._extract_reference(
                ref_op_id, ref_path, param_name, operation_id
            )
            result = result.replace(match.group(0), str(ref_value))

        return result

    def _extract_reference(
        self,
        ref_op_id: str,
        ref_path: str,
        param_name: str = None,
        operation_id: str = None,
    ) -> Any:
        """
        Extract a value from results using operation ID and property path.

        Args:
            ref_op_id: Referenced operation ID
            ref_path: Dot-notation path to property (e.g., "customer_id")
            param_name: Name of the parameter (for error messages)
            operation_id: ID of the operation (for error messages)

        Returns:
            The referenced value

        Raises:
            ApplicationException: If reference cannot be resolved
        """
        # Check if referenced operation exists
        if ref_op_id not in self.results:
            context = f" in operation '{operation_id}'" if operation_id else ""
            raise ApplicationException(
                400,
                f"Reference to unknown operation '{ref_op_id}'{context}. "
                f"Ensure operation is defined and appears before this one.",
            )

        # Check if operation completed successfully
        op_result = self.results[ref_op_id]
        if op_result.get("status") != "completed":
            context = f" in operation '{operation_id}'" if operation_id else ""
            raise ApplicationException(
                400,
                f"Cannot reference operation '{ref_op_id}'{context}: "
                f"operation {op_result.get('status', 'failed')}",
            )

        # Navigate to the referenced property
        data = op_result.get("data", {})
        path_parts = ref_path.split(".")

        try:
            value = data
            for part in path_parts:
                if isinstance(value, dict):
                    value = value[part]
                elif isinstance(value, list):
                    # Support array indexing: items.0.id
                    value = value[int(part)]
                else:
                    raise KeyError(part)
            return value

        except (KeyError, IndexError, ValueError) as e:
            context = f" in operation '{operation_id}'" if operation_id else ""
            param_context = f" for parameter '{param_name}'" if param_name else ""
            # Show available properties if data is a dict, otherwise show data type
            available = (
                f"Available properties: {list(data.keys())}"
                if isinstance(data, dict)
                else f"Data is {type(data).__name__}, not a dict"
            )
            raise ApplicationException(
                400,
                f"Cannot resolve reference '$ref:{ref_op_id}.{ref_path}'"
                f"{context}{param_context}: property not found in result. "
                f"{available}",
            ) from e

    def validate_references(self, params: Dict[str, Any]) -> List[str]:
        """
        Validate that all references in parameters can be resolved.

        Args:
            params: Parameters to validate

        Returns:
            List of referenced operation IDs
        """
        refs = []

        def find_refs(value: Any):
            if isinstance(value, str) and "$ref:" in value:
                for match in self.REF_PATTERN.finditer(value):
                    refs.append(match.group(1))
            elif isinstance(value, dict):
                for v in value.values():
                    find_refs(v)
            elif isinstance(value, list):
                for item in value:
                    find_refs(item)

        find_refs(params)
        return list(set(refs))

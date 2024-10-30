from typing import Any, List, Dict, Optional, Union


class SpecificationHandler:
    def __init__(self, spec: Dict):
        self.spec = spec

    def resolve_reference(self, reference: str) -> Optional[Any]:
        """
        Resolve a $ref reference in an OpenAPI specification.

        Args:
            reference (str): The $ref string to resolve.

        Returns:
            Optional[Any]: The resolved reference or None if not found.
        """
        if not reference.startswith("#/"):
            return None

        parts = reference[2:].split("/")
        return self.traverse_spec(self.spec, parts)

    def traverse_spec(
        self, spec: Dict[str, Any], keys: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Traverse an OpenAPI specification object using a list of strings as keys.

        Args:
            spec (Dict[str, Any]): The OpenAPI specification object.
            keys (List[str]): A list of strings representing the keys to traverse.

        Returns:
            Optional[Any]: The value found at the specified path or None if any key
                is not found.
        """
        current_element = spec
        for key in keys:
            while isinstance(current_element, dict) and "$ref" in current_element:
                resolved_reference = self.resolve_reference(current_element["$ref"])
                if resolved_reference:
                    current_element = {**current_element, **resolved_reference}
                    current_element.pop("$ref")
                if current_element is None:
                    return None

            if not isinstance(current_element, dict) or key not in current_element:
                return None
            current_element = current_element[key]

        return current_element

    def get(
        self,
        spec: Dict[str, Any],
        key: Union[List[str], str],
        default: Optional[Any] = None,
    ) -> Optional[Any]:
        current_element = spec

        if isinstance(key, list):
            return self.traverse_spec(spec, key) or default

        if isinstance(current_element, dict):
            if key in current_element:
                return current_element[key]

            if "$ref" in current_element:
                resolved_reference = self.resolve_reference(current_element["$ref"])
                if resolved_reference:
                    return self.get(resolved_reference, key, default)

        return default

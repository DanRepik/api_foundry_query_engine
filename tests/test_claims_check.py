"""
Test cases and examples for the claims_check decorator.
"""

import pytest
from api_foundry_query_engine.utils.claims_check import (
    claims_check,
    requires_read_scope,
    requires_write_scope,
    _extract_claims,
    _extract_operation_type,
    _extract_entity_from_path,
    _scope_matches,
    _permission_matches,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException


class TestClaimsCheck:
    """Test cases for the claims_check decorator."""

    def test_extract_claims_success(self):
        """Test successful claims extraction."""
        event = {
            "requestContext": {
                "authorizer": {
                    "sub": "user123",
                    "scope": "read:* write:album",
                    "permissions": ["album.read", "album.write"],
                    "roles": ["user"],
                }
            }
        }
        claims = _extract_claims(event)
        assert claims is not None
        assert claims["sub"] == "user123"
        assert "scope" in claims

    def test_extract_claims_missing(self):
        """Test claims extraction when no claims exist."""
        event = {"requestContext": {}}
        claims = _extract_claims(event)
        assert claims is None

    def test_extract_operation_type(self):
        """Test operation type extraction from HTTP method."""
        assert _extract_operation_type({"httpMethod": "GET"}) == "read"
        assert _extract_operation_type({"httpMethod": "POST"}) == "write"
        assert _extract_operation_type({"httpMethod": "PUT"}) == "write"
        assert _extract_operation_type({"httpMethod": "DELETE"}) == "delete"
        assert _extract_operation_type({}) == "read"  # default

    def test_extract_entity_from_path(self):
        """Test entity extraction from request path."""
        event1 = {"path": "/chinook-api/album"}
        assert _extract_entity_from_path(event1) == "album"

        event2 = {"resource": "/album/{id}"}
        assert _extract_entity_from_path(event2) == "album"

        event3 = {"path": "/api/v1/customer/123"}
        assert _extract_entity_from_path(event3) == "customer"

    def test_scope_matches_wildcard(self):
        """Test scope matching with wildcards."""
        user_scopes = ["read:*", "write:album"]

        # Wildcard should match any read operation
        assert _scope_matches(user_scopes, "read:customer", "read", "customer")
        assert _scope_matches(user_scopes, "read:album", "read", "album")

        # Specific scope should match exactly
        assert _scope_matches(user_scopes, "write:album", "write", "album")

        # Should not match different operations
        assert not _scope_matches(user_scopes, "delete:album", "delete", "album")

    def test_permission_matches(self):
        """Test permission matching."""
        user_permissions = ["album.read", "customer.*", "invoice.write"]

        # Direct match
        assert _permission_matches(user_permissions, "album.read")

        # Wildcard match
        assert _permission_matches(user_permissions, "customer.read")
        assert _permission_matches(user_permissions, "customer.write")

        # No match
        assert not _permission_matches(user_permissions, "album.delete")

    def test_decorator_with_valid_scopes(self):
        """Test decorator with valid scopes."""

        @claims_check(required_scopes=["read:*"])
        def test_handler(event, context):
            return {"statusCode": 200}

        event = {
            "httpMethod": "GET",
            "path": "/album",
            "requestContext": {
                "authorizer": {"scope": "read:* write:album", "permissions": []}
            },
        }

        result = test_handler(event, None)
        assert result["statusCode"] == 200

    def test_decorator_with_insufficient_scopes(self):
        """Test decorator with insufficient scopes."""

        @claims_check(required_scopes=["write:*"])
        def test_handler(event, context):
            return {"statusCode": 200}

        event = {
            "httpMethod": "POST",
            "path": "/album",
            "requestContext": {
                "authorizer": {
                    "scope": "read:*",  # Only read, but write required
                    "permissions": [],
                }
            },
        }

        with pytest.raises(ApplicationException) as exc_info:
            test_handler(event, None)

        assert exc_info.value.status_code == 403

    def test_decorator_with_valid_permissions(self):
        """Test decorator with valid permissions."""

        @claims_check(required_permissions=["album.read"])
        def test_handler(event, context):
            return {"statusCode": 200}

        event = {
            "httpMethod": "GET",
            "path": "/album",
            "requestContext": {
                "authorizer": {
                    "scope": "",
                    "permissions": ["album.read", "album.write"],
                }
            },
        }

        result = test_handler(event, None)
        assert result["statusCode"] == 200

    def test_convenience_decorators(self):
        """Test convenience decorators."""

        @requires_read_scope("album")
        def read_handler(event, context):
            return {"statusCode": 200}

        @requires_write_scope()
        def write_handler(event, context):
            return {"statusCode": 200}

        event_read = {
            "httpMethod": "GET",
            "path": "/album",
            "requestContext": {
                "authorizer": {"scope": "read:album", "permissions": []}
            },
        }

        event_write = {
            "httpMethod": "POST",
            "path": "/customer",
            "requestContext": {"authorizer": {"scope": "write:*", "permissions": []}},
        }

        # Should succeed
        result1 = read_handler(event_read, None)
        assert result1["statusCode"] == 200

        result2 = write_handler(event_write, None)
        assert result2["statusCode"] == 200

    def test_no_claims_error(self):
        """Test error when no claims are present."""

        @claims_check(required_scopes=["read:*"])
        def test_handler(event, context):
            return {"statusCode": 200}

        event = {"httpMethod": "GET", "path": "/album"}

        with pytest.raises(ApplicationException) as exc_info:
            test_handler(event, None)

        assert exc_info.value.status_code == 401


def example_lambda_handler():
    """
    Example of how to use the claims_check decorator in a Lambda function.
    """
    from api_foundry_query_engine.utils.token_decoder import token_decoder

    # Example 1: Check for specific scopes
    @token_decoder()
    @claims_check(required_scopes=["read:*"], operation_type="read")
    def read_albums_handler(event, context):
        # Your business logic here
        return {"statusCode": 200, "body": "Albums retrieved successfully"}

    # Example 2: Check for entity-specific permissions
    @token_decoder()
    @claims_check(
        required_scopes=["write:album"],
        required_permissions=["album.create"],
        operation_type="write",
        entity_name="album",
    )
    def create_album_handler(event, context):
        # Your business logic here
        return {"statusCode": 201, "body": "Album created successfully"}

    # Example 3: Use convenience decorators
    @token_decoder()
    @requires_read_scope("customer")
    def read_customers_handler(event, context):
        # Your business logic here
        return {"statusCode": 200, "body": "Customers retrieved successfully"}

    # Example 4: Auto-extract entity from path
    @token_decoder()
    @requires_write_scope(extract_from_path=True)
    def update_entity_handler(event, context):
        # Entity will be auto-extracted from path like /api/album/123
        return {"statusCode": 200, "body": "Entity updated successfully"}

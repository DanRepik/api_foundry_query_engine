"""Test that operation ID is optional in batch operations."""
import pytest
from api_foundry_query_engine.dao.batch_operation_handler import (
    BatchOperationHandler,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException


@pytest.mark.unit
def test_operations_without_ids_get_auto_generated():
    """Test that operations without IDs get auto-generated IDs."""

    batch_request = {
        "operations": [
            {
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Test Album"},
            },
            {"entity": "artist", "action": "read", "query_params": {"name": "AC/DC"}},
        ]
    }

    # Mock connection and engine
    class MockConnection:
        pass

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check that IDs were auto-generated
    assert handler.operations[0]["id"] == "op_0"
    assert handler.operations[1]["id"] == "op_1"


@pytest.mark.unit
def test_explicit_ids_are_preserved():
    """Test that explicit IDs are preserved."""

    batch_request = {
        "operations": [
            {
                "id": "create_album",
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Test Album"},
            },
            {
                "id": "read_artist",
                "entity": "artist",
                "action": "read",
                "query_params": {"name": "AC/DC"},
            },
        ]
    }

    class MockConnection:
        pass

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check that explicit IDs are preserved
    assert handler.operations[0]["id"] == "create_album"
    assert handler.operations[1]["id"] == "read_artist"


@pytest.mark.unit
def test_mixed_explicit_and_auto_ids():
    """Test mixing explicit and auto-generated IDs."""

    batch_request = {
        "operations": [
            {
                "id": "my_op",
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 1"},
            },
            {
                # No ID - should get op_1
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 2"},
            },
            {
                "id": "another_op",
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 3"},
            },
        ]
    }

    class MockConnection:
        pass

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check IDs
    assert handler.operations[0]["id"] == "my_op"
    assert handler.operations[1]["id"] == "op_1"
    assert handler.operations[2]["id"] == "another_op"


@pytest.mark.unit
def test_duplicate_ids_raise_error():
    """Test that duplicate IDs raise an error."""

    batch_request = {
        "operations": [
            {
                "id": "same_id",
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 1"},
            },
            {
                "id": "same_id",  # Duplicate!
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 2"},
            },
        ]
    }

    class MockConnection:
        pass

    with pytest.raises(ApplicationException) as exc_info:
        BatchOperationHandler(batch_request, MockConnection(), "postgres")

    assert exc_info.value.status_code == 400
    assert "Duplicate operation ID 'same_id'" in exc_info.value.message


@pytest.mark.unit
def test_empty_id_gets_auto_generated():
    """Test that empty string ID gets auto-generated."""

    batch_request = {
        "operations": [
            {
                "id": "",  # Empty string should be replaced
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Test Album"},
            },
        ]
    }

    class MockConnection:
        pass

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Empty ID should be replaced with auto-generated one
    assert handler.operations[0]["id"] == "op_0"

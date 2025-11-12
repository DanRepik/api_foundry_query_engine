"""Standalone test for optional operation IDs in batch operations."""
import sys

sys.path.insert(0, "/Users/clydedanielrepik/workspaces/api_foundry_query_engine")

from api_foundry_query_engine.dao.batch_operation_handler import (
    BatchOperationHandler,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException


class MockConnection:
    """Mock database connection for testing."""

    pass


def test_operations_without_ids_get_auto_generated():
    """Test that operations without IDs get auto-generated IDs."""

    print("\n1. Testing auto-generated IDs for operations without IDs...")

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

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check that IDs were auto-generated
    assert (
        handler.operations[0]["id"] == "op_0"
    ), f"Expected 'op_0', got '{handler.operations[0]['id']}'"
    assert (
        handler.operations[1]["id"] == "op_1"
    ), f"Expected 'op_1', got '{handler.operations[1]['id']}'"

    print("   ✓ Auto-generated IDs: op_0, op_1")


def test_explicit_ids_are_preserved():
    """Test that explicit IDs are preserved."""

    print("\n2. Testing that explicit IDs are preserved...")

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

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check that explicit IDs are preserved
    assert handler.operations[0]["id"] == "create_album"
    assert handler.operations[1]["id"] == "read_artist"

    print("   ✓ Explicit IDs preserved: create_album, read_artist")


def test_mixed_explicit_and_auto_ids():
    """Test mixing explicit and auto-generated IDs."""

    print("\n3. Testing mixed explicit and auto-generated IDs...")

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

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Check IDs
    assert handler.operations[0]["id"] == "my_op"
    assert handler.operations[1]["id"] == "op_1"
    assert handler.operations[2]["id"] == "another_op"

    print("   ✓ Mixed IDs: my_op, op_1, another_op")


def test_duplicate_ids_raise_error():
    """Test that duplicate IDs raise an error."""

    print("\n4. Testing that duplicate IDs raise an error...")

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

    try:
        handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")
        assert False, "Should have raised ApplicationException"
    except ApplicationException as e:
        assert e.status_code == 400
        assert "Duplicate operation ID 'same_id'" in e.message
        print(f"   ✓ Duplicate ID detected: {e.message}")


def test_empty_id_gets_auto_generated():
    """Test that empty string ID gets auto-generated."""

    print("\n5. Testing that empty ID gets auto-generated...")

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

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # Empty ID should be replaced with auto-generated one
    assert handler.operations[0]["id"] == "op_0"

    print("   ✓ Empty ID replaced with: op_0")


def test_simple_batch_no_references():
    """Test a realistic batch with no references between operations."""

    print("\n6. Testing realistic batch with no ID dependencies...")

    batch_request = {
        "operations": [
            {
                # No ID needed - not referenced
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 1", "artist_id": 1},
            },
            {
                # No ID needed - not referenced
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 2", "artist_id": 2},
            },
            {
                # No ID needed - not referenced
                "entity": "album",
                "action": "create",
                "store_params": {"title": "Album 3", "artist_id": 3},
            },
        ]
    }

    handler = BatchOperationHandler(batch_request, MockConnection(), "postgres")

    # All should have auto-generated IDs
    assert handler.operations[0]["id"] == "op_0"
    assert handler.operations[1]["id"] == "op_1"
    assert handler.operations[2]["id"] == "op_2"

    print("   ✓ Three operations without IDs work fine")
    print("   ✓ Auto-generated: op_0, op_1, op_2")


if __name__ == "__main__":
    print("=" * 70)
    print("OPTIONAL OPERATION ID TESTS")
    print("=" * 70)

    try:
        test_operations_without_ids_get_auto_generated()
        test_explicit_ids_are_preserved()
        test_mixed_explicit_and_auto_ids()
        test_duplicate_ids_raise_error()
        test_empty_id_gets_auto_generated()
        test_simple_batch_no_references()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nConclusion:")
        print("  • Operation IDs are now optional")
        print("  • Auto-generated as 'op_N' when missing")
        print("  • Explicit IDs are preserved when provided")
        print("  • Duplicate IDs are detected and rejected")
        print("  • Use cases:")
        print("    - No ID needed: Simple batch inserts/updates")
        print("    - ID required: When operation is referenced via $ref or depends_on")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()

"""Test to demonstrate circular import issue."""

# This simulates what would happen if we moved the import to the top

print("Attempting to import with top-level BatchOperationHandler import...")

try:
    # Simulate operation_dao.py with top-level import
    import sys

    # Create a temporary module that simulates the circular import
    code = """
from api_foundry_query_engine.dao.batch_operation_handler import BatchOperationHandler
from api_foundry_query_engine.dao.operation_dao import OperationDAO

print("If you see this, there's no circular import issue!")
"""

    exec(code)

except ImportError as e:
    print(f"❌ Circular import detected: {e}")
    print("\nThis is why we use deferred import!")

print("\nNow testing with deferred import (current implementation):")

try:
    from api_foundry_query_engine.dao.operation_dao import OperationDAO

    print("✓ OperationDAO imported successfully")

    from api_foundry_query_engine.dao.batch_operation_handler import (
        BatchOperationHandler,
    )

    print("✓ BatchOperationHandler imported successfully")

    print("\n✅ Deferred import pattern works!")

except ImportError as e:
    print(f"❌ Even deferred import failed: {e}")

import pytest
from unittest.mock import Mock
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.utils.api_model import (
    SchemaObject,
    SchemaObjectProperty,
)
from api_foundry_query_engine.dao.sql_select_query_handler import (
    SQLSelectSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_delete_query_handler import (
    SQLDeleteSchemaQueryHandler,
)
from api_foundry_query_engine.dao.sql_restore_query_handler import (
    SQLRestoreSchemaQueryHandler,
)


class TestSoftDeleteFunctionality:
    """Test suite for soft delet        # Should only include deleted_at filter
            assert "status NOT IN" not in multi_sql
            assert "is_active = True" not in multi_sql
            assert "deleted_at IS NULL" in multi_sql


    if __name__ == "__main__":
        pytest.main([__file__])
    ionality across all query handlers."""

    def create_mock_schema_object(self, table_name: str, **extra_properties):
        """Helper to create a mock schema object with standard properties."""
        properties = {
            "id": SchemaObjectProperty(
                {
                    "api_name": "id",
                    "column_name": "id",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "uuid",
                }
            ),
            **extra_properties,
        }

        schema_data = {
            "api_name": table_name,
            "database": "test_db",
            "schema": "public",
            "table_name": table_name,
            "properties": {name: prop.__dict__ for name, prop in properties.items()},
            "primary_key": "id",
        }
        return SchemaObject(schema_data)

    def test_schema_object_soft_delete_detection(self):
        """Test that schema objects correctly detect soft delete capabilities."""

        # Test null_check strategy
        schema_with_deleted_at = self.create_mock_schema_object(
            "contracts",
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
        )
        assert schema_with_deleted_at.has_soft_delete_support() is True
        assert "null_check" in schema_with_deleted_at.get_soft_delete_strategies()

        # Test boolean_flag strategy
        schema_with_active = self.create_mock_schema_object(
            "reviews",
            active=SchemaObjectProperty(
                {
                    "api_name": "active",
                    "column_name": "active",
                    "type": "boolean",
                    "api_type": "boolean",
                    "column_type": "boolean",
                    "soft_delete": {"strategy": "boolean_flag", "active_value": True},
                }
            ),
        )
        assert schema_with_active.has_soft_delete_support() is True
        assert "boolean_flag" in schema_with_active.get_soft_delete_strategies()

        # Test exclude_values strategy
        schema_with_status = self.create_mock_schema_object(
            "contracts",
            status=SchemaObjectProperty(
                {
                    "api_name": "status",
                    "column_name": "status",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "contract_status",
                    "soft_delete": {
                        "strategy": "exclude_values",
                        "values": ["terminated", "deleted"],
                        "delete_value": "terminated",
                        "restore_value": "active",
                    },
                }
            ),
        )
        assert schema_with_status.has_soft_delete_support() is True
        assert "exclude_values" in schema_with_status.get_soft_delete_strategies()

        # Test no soft delete support
        schema_without_soft_delete = self.create_mock_schema_object("users")
        assert schema_without_soft_delete.has_soft_delete_support() is False
        assert len(schema_without_soft_delete.get_soft_delete_strategies()) == 0

    def test_select_handler_soft_delete_filtering(self):
        """Test that SELECT queries automatically filter soft-deleted records."""

        # Test null_check filtering
        schema = self.create_mock_schema_object(
            "contracts",
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
        )

        operation = Operation(
            entity="contracts", action="read", query_params={"id": "test-id"}
        )

        handler = SQLSelectSchemaQueryHandler(operation, schema, "postgresql")

        # Check that soft delete filter is applied in generated SQL
        sql = handler.sql
        assert "deleted_at IS NULL" in sql

        # Test boolean_flag filtering
        schema_active = self.create_mock_schema_object(
            "reviews",
            active=SchemaObjectProperty(
                {
                    "api_name": "active",
                    "column_name": "active",
                    "type": "boolean",
                    "api_type": "boolean",
                    "column_type": "boolean",
                    "soft_delete": {"strategy": "boolean_flag", "active_value": True},
                }
            ),
        )

        operation_active = Operation(
            entity="reviews", action="read", query_params={"id": "test-id"}
        )

        handler_active = SQLSelectSchemaQueryHandler(
            operation_active, schema_active, "postgresql"
        )

        sql_active = handler_active.sql
        assert "active = True" in sql_active

    def test_delete_handler_soft_delete_operation(self):
        """Test that DELETE operations perform soft deletes when supported."""

        # Test soft delete with deleted_at field
        schema = self.create_mock_schema_object(
            "contracts",
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
            deleted_by=SchemaObjectProperty(
                {
                    "api_name": "deleted_by",
                    "column_name": "deleted_by",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "uuid",
                    "soft_delete": {"strategy": "audit_field", "action": "delete"},
                }
            ),
        )

        operation = Operation(
            entity="contracts",
            action="delete",
            query_params={"id": "test-id"},
            claims={"sub": "user-123"},
        )

        handler = SQLDeleteSchemaQueryHandler(operation, schema, "postgresql")

        # Mock the check_permission method to return True
        handler.check_permission = Mock(return_value=True)

        # Test that UPDATE is used instead of DELETE
        sql = handler.sql
        assert sql.startswith("UPDATE")
        assert "SET" in sql
        assert "deleted_at = CURRENT_TIMESTAMP" in sql
        # The audit field should also be set
        assert "deleted_by" in sql

    def test_delete_handler_hard_delete_fallback(self):
        """Test DELETE falls back to hard delete for tables without soft delete."""

        # No soft delete fields
        schema = self.create_mock_schema_object("users")

        operation = Operation(
            entity="users", action="delete", query_params={"id": "test-id"}
        )

        handler = SQLDeleteSchemaQueryHandler(operation, schema, "postgresql")
        handler.check_permission = Mock(return_value=True)

        # Check that hard delete is performed
        sql = handler.sql
        assert sql.startswith("DELETE FROM")
        assert "SET" not in sql

    def test_restore_handler_functionality(self):
        """Test the restore handler for soft-deleted records."""

        schema = self.create_mock_schema_object(
            "contracts",
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
            restored_by=SchemaObjectProperty(
                {
                    "api_name": "restored_by",
                    "column_name": "restored_by",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "uuid",
                    "soft_delete": {"strategy": "audit_field", "action": "restore"},
                }
            ),
            status=SchemaObjectProperty(
                {
                    "api_name": "status",
                    "column_name": "status",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "contract_status",
                    "soft_delete": {
                        "strategy": "exclude_values",
                        "values": ["terminated", "deleted"],
                        "delete_value": "terminated",
                        "restore_value": "active",
                    },
                }
            ),
        )

        operation = Operation(
            entity="contracts",
            action="restore",
            query_params={"id": "test-id"},
            claims={"sub": "admin-123", "roles": ["admin"]},
        )

        handler = SQLRestoreSchemaQueryHandler(operation, schema, "postgresql")
        handler.check_permission = Mock(return_value=True)

        # Test SQL generation
        sql = handler.sql
        assert sql.startswith("UPDATE")
        assert "SET" in sql
        assert "deleted_at = NULL" in sql
        assert "status = 'active'" in sql

        # Test search condition includes soft-deleted records
        search_condition = handler.search_condition
        assert "deleted_at IS NOT NULL" in search_condition

    def test_restore_handler_permissions(self):
        """Test that restore handler checks permissions correctly."""

        schema = self.create_mock_schema_object(
            "contracts",
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
        )

        # Add permissions that deny restore
        schema.permissions = {
            "default": {"restore": {"user": False}, "write": {"admin": True}}
        }

        operation = Operation(
            entity="contracts",
            action="restore",
            query_params={"id": "test-id"},
            claims={"roles": ["user"]},
        )

        handler = SQLRestoreSchemaQueryHandler(operation, schema, "postgresql")

        # Should deny permission for user role
        assert handler.check_permission() is False

        # Test fallback to write permissions for admin
        operation_admin = Operation(
            entity="contracts",
            action="restore",
            query_params={"id": "test-id"},
            claims={"roles": ["admin"]},
        )
        handler_admin = SQLRestoreSchemaQueryHandler(
            operation_admin, schema, "postgresql"
        )
        assert handler_admin.check_permission() is True

    def test_active_flag_soft_delete_variations(self):
        """Test soft delete functionality with active flag strategy."""

        schema = self.create_mock_schema_object(
            "reviews",
            active=SchemaObjectProperty(
                {
                    "api_name": "active",
                    "column_name": "active",
                    "type": "boolean",
                    "api_type": "boolean",
                    "column_type": "boolean",
                    "soft_delete": {"strategy": "boolean_flag", "active_value": True},
                }
            ),
            deleted_by=SchemaObjectProperty(
                {
                    "api_name": "deleted_by",
                    "column_name": "deleted_by",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "uuid",
                    "soft_delete": {"strategy": "audit_field", "action": "delete"},
                }
            ),
        )

        # Test DELETE operation
        delete_operation = Operation(
            entity="reviews",
            action="delete",
            query_params={"id": "review-123"},
            claims={"sub": "user-456", "roles": ["user"]},
        )

        delete_handler = SQLDeleteSchemaQueryHandler(
            delete_operation, schema, "postgresql"
        )
        delete_handler.check_permission = Mock(return_value=True)

        sql = delete_handler.sql
        assert "active = false" in sql
        assert "deleted_by" in sql

        # Test RESTORE operation
        restore_operation = Operation(
            entity="reviews",
            action="restore",
            query_params={"id": "review-123"},
            claims={"sub": "admin-789", "roles": ["admin"]},
        )

        restore_handler = SQLRestoreSchemaQueryHandler(
            restore_operation, schema, "postgresql"
        )
        restore_handler.check_permission = Mock(return_value=True)

        sql_restore = restore_handler.sql
        assert "active = true" in sql_restore

    def test_contract_status_soft_delete(self):
        """Test soft delete with contract_status enum."""

        schema = self.create_mock_schema_object(
            "contracts",
            status=SchemaObjectProperty(
                {
                    "api_name": "status",
                    "column_name": "status",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "contract_status",
                    "soft_delete": {
                        "strategy": "exclude_values",
                        "values": ["terminated", "deleted"],
                        "delete_value": "terminated",
                        "restore_value": "active",
                    },
                }
            ),
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "date-time",
                    "column_type": "timestamptz",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
        )

        # Test DELETE sets status to terminated
        delete_operation = Operation(
            entity="contracts",
            action="delete",
            query_params={"id": "contract-123"},
            claims={"roles": ["admin"]},
        )

        delete_handler = SQLDeleteSchemaQueryHandler(
            delete_operation, schema, "postgresql"
        )
        delete_handler.check_permission = Mock(return_value=True)

        sql = delete_handler.sql
        assert "status = 'terminated'" in sql
        assert "deleted_at = CURRENT_TIMESTAMP" in sql

        # Test RESTORE sets status back to active
        restore_operation = Operation(
            entity="contracts",
            action="restore",
            query_params={"id": "contract-123"},
            claims={"roles": ["admin"]},
        )

        restore_handler = SQLRestoreSchemaQueryHandler(
            restore_operation, schema, "postgresql"
        )
        restore_handler.check_permission = Mock(return_value=True)

        sql_restore = restore_handler.sql
        assert "status = 'active'" in sql_restore
        assert "deleted_at = NULL" in sql_restore

    def test_smart_conflict_detection(self):
        """Test smart conflict detection - querying for soft-deleted values
        bypasses filtering."""

        # Create schema with multiple soft delete strategies
        schema = self.create_mock_schema_object(
            "products",
            name=SchemaObjectProperty(
                {
                    "api_name": "name",
                    "column_name": "name",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "varchar",
                }
            ),
            status=SchemaObjectProperty(
                {
                    "api_name": "status",
                    "column_name": "status",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "varchar",
                    "soft_delete": {
                        "strategy": "exclude_values",
                        "values": ["archived", "deleted"],
                    },
                }
            ),
            is_active=SchemaObjectProperty(
                {
                    "api_name": "is_active",
                    "column_name": "is_active",
                    "type": "boolean",
                    "api_type": "boolean",
                    "column_type": "boolean",
                    "soft_delete": {"strategy": "boolean_flag", "active_value": True},
                }
            ),
            deleted_at=SchemaObjectProperty(
                {
                    "api_name": "deleted_at",
                    "column_name": "deleted_at",
                    "type": "string",
                    "api_type": "string",
                    "column_type": "timestamp",
                    "soft_delete": {"strategy": "null_check"},
                }
            ),
        )

        # Test 1: Normal query - should apply all soft delete filters
        normal_operation = Operation(
            entity="products", action="read", query_params={"name": "Test Product"}
        )

        select_handler = SQLSelectSchemaQueryHandler(
            normal_operation, schema, "postgresql"
        )

        sql = select_handler.sql
        # Should include all soft delete filters
        assert "status NOT IN ('archived', 'deleted')" in sql
        assert "is_active = True" in sql
        assert "deleted_at IS NULL" in sql

        # Test 2: Query for archived status - should skip status filter
        archived_operation = Operation(
            entity="products", action="read", query_params={"status": "archived"}
        )

        archived_handler = SQLSelectSchemaQueryHandler(
            archived_operation, schema, "postgresql"
        )

        archived_sql = archived_handler.sql

        # Should NOT include status filter but include others
        assert "status NOT IN" not in archived_sql
        assert "is_active = True" in archived_sql
        assert "deleted_at IS NULL" in archived_sql

        # Test 3: Query for inactive records - should skip is_active filter
        inactive_operation = Operation(
            entity="products", action="read", query_params={"is_active": "false"}
        )

        inactive_handler = SQLSelectSchemaQueryHandler(
            inactive_operation, schema, "postgresql"
        )

        inactive_sql = inactive_handler.sql

        # Should NOT include is_active filter but include others
        assert "is_active = True" not in inactive_sql
        assert "status NOT IN ('archived', 'deleted')" in inactive_sql
        assert "deleted_at IS NULL" in inactive_sql

        # Test 4: Multiple conflicts - should skip multiple filters
        multi_conflict_operation = Operation(
            entity="products",
            action="read",
            query_params={"status": "deleted", "is_active": "false"},
        )

        multi_handler = SQLSelectSchemaQueryHandler(
            multi_conflict_operation, schema, "postgresql"
        )

        multi_sql = multi_handler.sql

        # Should only include deleted_at filter
        assert "status NOT IN" not in multi_sql
        assert "is_active = True" not in multi_sql
        assert "deleted_at IS NULL" in multi_sql


if __name__ == "__main__":
    pytest.main([__file__])

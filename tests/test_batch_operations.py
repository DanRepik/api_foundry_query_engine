"""
Integration tests for Batch Operations
"""

import pytest
from api_foundry_query_engine.dao.batch_operation_handler import (
    BatchOperationHandler,
)
from api_foundry_query_engine.connectors.connection_factory import (
    ConnectionFactory,
)
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


@pytest.mark.integration
class TestBatchOperations:
    def test_create_invoice_with_line_items(self, chinook_env):
        """Test creating invoice with multiple line items in batch"""
        batch_request = {
            "operations": [
                {
                    "entity": "invoice",
                    "action": "create",
                    "store_params": {
                        "customer_id": 1,
                        "invoice_date": "2024-11-11T10:00:00",
                        "billing_address": "123 Main St",
                        "billing_city": "TestCity",
                        "billing_country": "USA",
                        "total": 2.97,
                    },
                },
                {
                    "entity": "invoice_line",
                    "action": "create",
                    "store_params": {
                        "invoice_id": "$ref:op_0.invoice_id",
                        "track_id": 1,
                        "unit_price": 0.99,
                        "quantity": 1,
                    },
                },
                {
                    "entity": "invoice_line",
                    "action": "create",
                    "store_params": {
                        "invoice_id": "$ref:op_0.invoice_id",
                        "track_id": 2,
                        "unit_price": 0.99,
                        "quantity": 2,
                    },
                },
            ],
            "options": {"atomic": True},
        }

        # Create connection from environment
        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            log.info("Batch result success: %s", result["success"])

            assert result["success"] is True
            assert len(result["results"]) == 3
            assert result["results"]["op_0"]["status"] == "completed"
            assert result["results"]["op_1"]["status"] == "completed"
            assert result["results"]["op_2"]["status"] == "completed"

            # Verify invoice was created (single-item results are unwrapped)
            invoice_id = result["results"]["op_0"]["data"]["invoice_id"]
            assert invoice_id is not None

            # Verify line items reference correct invoice
            line_1 = result["results"]["op_1"]["data"]["invoice_id"]
            line_2 = result["results"]["op_2"]["data"]["invoice_id"]
            assert line_1 == invoice_id
            assert line_2 == invoice_id
        finally:
            connection.close()

    def test_batch_with_read_operations(self, chinook_env):
        """Test batch with mixed read and write operations"""
        batch_request = {
            "operations": [
                {
                    "id": "read_customer",
                    "entity": "customer",
                    "action": "read",
                    "query_params": {"customer_id": 1},
                },
                {
                    "id": "create_invoice",
                    "entity": "invoice",
                    "action": "create",
                    "store_params": {
                        "customer_id": "$ref:read_customer.customer_id",
                        "invoice_date": "2024-11-11T10:00:00",
                        "billing_address": "456 Oak Ave",
                        "billing_city": "TestCity",
                        "billing_country": "USA",
                        "total": 5.00,
                    },
                    "depends_on": ["read_customer"],
                },
            ],
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            assert result["success"] is True
            assert result["results"]["read_customer"]["status"] == "completed"
            assert result["results"]["create_invoice"]["status"] == "completed"

            # Verify customer_id was correctly referenced
            cust_id = result["results"]["read_customer"]["data"]["customer_id"]
            inv_cust_id = result["results"]["create_invoice"]["data"]["customer_id"]
            assert inv_cust_id == cust_id
        finally:
            connection.close()

    def test_batch_rollback_on_error(self, chinook_env):
        """Test that batch rolls back all changes on error (atomic mode)"""
        batch_request = {
            "operations": [
                {
                    "id": "create_media_type",
                    "entity": "media_type",
                    "action": "create",
                    "store_params": {"name": "Test Media Type"},
                },
                {
                    "id": "create_invalid",
                    "entity": "invoice",
                    "action": "create",
                    "store_params": {
                        "customer_id": 99999,  # Invalid customer ID
                        "invoice_date": "2024-11-11T10:00:00",
                        "total": 5.00,
                    },
                    "depends_on": ["create_media_type"],
                },
            ],
            "options": {"atomic": True, "continueOnError": False},
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")

            with pytest.raises(ApplicationException):
                handler.execute()
        finally:
            connection.close()

    def test_batch_continue_on_error(self, chinook_env):
        """Test batch continues executing after error when configured"""
        batch_request = {
            "operations": [
                {
                    "id": "create_valid",
                    "entity": "media_type",
                    "action": "create",
                    "store_params": {"name": "Valid Media Type"},
                },
                {
                    "id": "create_invalid",
                    "entity": "invoice",
                    "action": "create",
                    "store_params": {
                        "customer_id": 99999,  # Invalid
                        "total": 5.00,
                    },
                },
                {
                    "id": "create_another",
                    "entity": "media_type",
                    "action": "create",
                    "store_params": {"name": "Another Media Type"},
                },
            ],
            "options": {"atomic": False, "continueOnError": True},
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            log.info("Continue on error result success: %s", result["success"])

            assert result["success"] is False  # Had failures
            assert result["results"]["create_valid"]["status"] == "completed"
            assert result["results"]["create_invalid"]["status"] == "failed"
            assert result["results"]["create_another"]["status"] == "completed"
        finally:
            connection.close()

    def test_batch_dependency_skipping(self, chinook_env):
        """Test that dependent operations are skipped when parent fails"""
        batch_request = {
            "operations": [
                {
                    "id": "failing_op",
                    "entity": "invoice",
                    "action": "create",
                    "store_params": {
                        "customer_id": 99999,  # Invalid
                        "total": 5.00,
                    },
                },
                {
                    "id": "dependent_op",
                    "entity": "invoice_line",
                    "action": "create",
                    "store_params": {
                        "invoice_id": "$ref:failing_op.invoice_id",
                        "track_id": 1,
                        "unit_price": 0.99,
                        "quantity": 1,
                    },
                    "depends_on": ["failing_op"],
                },
            ],
            "options": {"continueOnError": True},
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            assert result["results"]["failing_op"]["status"] == "failed"
            assert result["results"]["dependent_op"]["status"] == "skipped"
            assert result["results"]["dependent_op"]["reason"] == "Dependency failed"
        finally:
            connection.close()

    def test_batch_circular_dependency(self, chinook_env):
        """Test that circular dependencies are detected"""
        batch_request = {
            "operations": [
                {
                    "id": "op_a",
                    "entity": "media_type",
                    "action": "create",
                    "depends_on": ["op_b"],
                },
                {
                    "id": "op_b",
                    "entity": "media_type",
                    "action": "create",
                    "depends_on": ["op_a"],
                },
            ],
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            with pytest.raises(ApplicationException) as exc_info:
                BatchOperationHandler(batch_request, connection, "postgres")

            assert "Circular dependency detected" in str(exc_info.value.message)
        finally:
            connection.close()

    def test_batch_update_with_reference(self, chinook_env):
        """Test batch update using reference from previous operation"""
        batch_request = {
            "operations": [
                {
                    "id": "create_media",
                    "entity": "media_type",
                    "action": "create",
                    "store_params": {"name": "Original Name"},
                },
                {
                    "id": "update_media",
                    "entity": "media_type",
                    "action": "update",
                    "query_params": {
                        "media_type_id": "$ref:create_media.media_type_id"
                    },
                    "store_params": {"name": "Updated Name"},
                    "depends_on": ["create_media"],
                },
            ],
        }

        factory = ConnectionFactory(chinook_env)
        connection = factory.get_connection("chinook")

        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            assert result["success"] is True
            assert result["results"]["create_media"]["status"] == "completed"
            assert result["results"]["update_media"]["status"] == "completed"

            # Verify the name was updated
            updated_name = result["results"]["update_media"]["data"]["name"]
            assert updated_name == "Updated Name"
        finally:
            connection.close()

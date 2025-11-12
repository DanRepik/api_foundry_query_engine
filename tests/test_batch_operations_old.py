"""
Integration tests for Batch Operations
"""

import pytest
import json
from api_foundry_query_engine.dao.batch_operation_handler import (
    BatchOperationHandler,
)
from api_foundry_query_engine.connectors.postgres_connection import PostgresConnection
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


@pytest.mark.integration
class TestBatchOperations:
    def test_create_invoice_with_line_items(self, chinook_env, chinook_db):
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

        # Create connection from chinook_db config
        connection = PostgresConnection(chinook_db)
        try:
            handler = BatchOperationHandler(batch_request, connection, "postgres")
            result = handler.execute()

            log.debug(f"Batch result: {json.dumps(result, indent=2)}")

            assert result["success"] is True
            assert len(result["results"]) == 3
            assert result["results"]["op_0"]["status"] == "completed"
            assert result["results"]["op_1"]["status"] == "completed"
            assert result["results"]["op_2"]["status"] == "completed"

            # Verify invoice was created
            invoice_id = result["results"]["op_0"]["data"][0]["invoice_id"]
            assert invoice_id is not None

            # Verify line items reference correct invoice
            line_1_invoice = result["results"]["op_1"]["data"][0]["invoice_id"]
            line_2_invoice = result["results"]["op_2"]["data"][0]["invoice_id"]
            assert line_1_invoice == invoice_id
            assert line_2_invoice == invoice_id
        finally:
            connection.close()
        invoice_id = result["results"][0]["data"][0]["invoice_id"]
        assert invoice_id is not None

        # Verify line items reference correct invoice
        line_1_invoice = result["results"][1]["data"][0]["invoice_id"]
        line_2_invoice = result["results"][2]["data"][0]["invoice_id"]
        assert line_1_invoice == invoice_id
        assert line_2_invoice == invoice_id
        """Test creating invoice with multiple line items in batch"""
        batch_request = {
            "operations": [
                {
                    "id": "create_invoice",
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
                    "id": "create_line_1",
                    "entity": "invoice_line",
                    "action": "create",
                    "store_params": {
                        "invoice_id": "$ref:create_invoice.invoice_id",
                        "track_id": 1,
                        "unit_price": 0.99,
                        "quantity": 1,
                    },
                    "depends_on": ["create_invoice"],
                },
                {
                    "id": "create_line_2",
                    "entity": "invoice_line",
                    "action": "create",
                    "store_params": {
                        "invoice_id": "$ref:create_invoice.invoice_id",
                        "track_id": 2,
                        "unit_price": 0.99,
                        "quantity": 2,
                    },
                    "depends_on": ["create_invoice"],
                },
            ],
            "options": {"atomic": True},
        }

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")
        result = handler.execute()

        log.debug(f"Batch result: {json.dumps(result, indent=2)}")

        assert result["success"] is True
        assert len(result["results"]) == 3
        assert result["results"]["create_invoice"]["status"] == "completed"
        assert result["results"]["create_line_1"]["status"] == "completed"
        assert result["results"]["create_line_2"]["status"] == "completed"

        # Verify invoice was created
        invoice_id = result["results"]["create_invoice"]["data"][0]["invoice_id"]
        assert invoice_id is not None

        # Verify line items reference correct invoice
        line_1_invoice = result["results"]["create_line_1"]["data"][0]["invoice_id"]
        line_2_invoice = result["results"]["create_line_2"]["data"][0]["invoice_id"]
        assert line_1_invoice == invoice_id
        assert line_2_invoice == invoice_id

    def test_batch_with_read_operations(self, chinook_env, chinook_db):
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

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")
        result = handler.execute()

        assert result["success"] is True
        assert result["results"]["read_customer"]["status"] == "completed"
        assert result["results"]["create_invoice"]["status"] == "completed"

        # Verify customer_id was correctly referenced
        customer_id = result["results"]["read_customer"]["data"][0]["customer_id"]
        invoice_customer_id = result["results"]["create_invoice"]["data"][0][
            "customer_id"
        ]
        assert invoice_customer_id == customer_id

    def test_batch_rollback_on_error(self, chinook_env, chinook_db):
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

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")

        with pytest.raises(ApplicationException):
            handler.execute()

        # Verify nothing was committed (transaction rolled back)
        # The media_type should not exist
        cursor = chinook_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM media_type WHERE name = 'Test Media Type'")
        count = cursor.fetchone()[0]
        assert count == 0

    def test_batch_continue_on_error(self, chinook_env, chinook_db):
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

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")
        result = handler.execute()

        log.debug(f"Continue on error result: {json.dumps(result, indent=2)}")

        assert result["success"] is False  # Had failures
        assert "failedOperations" in result
        assert "create_invalid" in result["failedOperations"]
        assert result["results"]["create_valid"]["status"] == "completed"
        assert result["results"]["create_invalid"]["status"] == "failed"
        assert result["results"]["create_another"]["status"] == "completed"

    def test_batch_dependency_skipping(self, chinook_env, chinook_db):
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

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")
        result = handler.execute()

        assert result["results"]["failing_op"]["status"] == "failed"
        assert result["results"]["dependent_op"]["status"] == "skipped"
        assert result["results"]["dependent_op"]["reason"] == "Dependency failed"

    def test_batch_circular_dependency(self, chinook_env, chinook_db):
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

        with pytest.raises(ApplicationException) as exc_info:
            BatchOperationHandler(batch_request, chinook_db, "postgres")

        assert exc_info.value.status_code == 400
        assert "Circular dependency" in exc_info.value.message

    def test_batch_exceeds_size_limit(self, chinook_env, chinook_db):
        """Test that batch size limit is enforced"""
        operations = [
            {
                "id": f"op_{i}",
                "entity": "media_type",
                "action": "create",
                "store_params": {"name": f"Type {i}"},
            }
            for i in range(101)  # Exceeds limit of 100
        ]

        batch_request = {"operations": operations}

        with pytest.raises(ApplicationException) as exc_info:
            BatchOperationHandler(batch_request, chinook_db, "postgres")

        assert exc_info.value.status_code == 400
        assert "exceeds maximum" in exc_info.value.message

    def test_batch_update_with_reference(self, chinook_env, chinook_db):
        """Test batch update using reference from previous operation"""
        # First create a record
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

        handler = BatchOperationHandler(batch_request, chinook_db, "postgres")
        result = handler.execute()

        assert result["success"] is True
        assert result["results"]["create_media"]["data"][0]["name"] == ("Original Name")
        assert result["results"]["update_media"]["data"][0]["name"] == ("Updated Name")

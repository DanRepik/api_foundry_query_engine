"""
Batch Operation Handler

Orchestrates execution of multiple operations with dependency resolution,
reference substitution, and transaction management.
"""

from typing import Dict, Any, List, Optional
from api_foundry_query_engine.operation import Operation
from api_foundry_query_engine.dao.operation_dao import OperationDAO
from api_foundry_query_engine.utils.dependency_resolver import DependencyResolver
from api_foundry_query_engine.utils.reference_resolver import ReferenceResolver
from api_foundry_query_engine.utils.app_exception import ApplicationException
from api_foundry_query_engine.utils.logger import logger

log = logger(__name__)


class BatchOperationHandler:
    """Handles execution of batch operations with dependencies."""

    def __init__(self, batch_request: Dict[str, Any], connection, engine: str):
        """
        Initialize the batch operation handler.

        Args:
            batch_request: Batch request with 'operations' and 'options'
            connection: Database connection for executing operations
            engine: Database engine type (postgres, mysql, etc.)
        """
        self.operations = batch_request.get("operations", [])
        self.options = batch_request.get("options", {})
        self.connection = connection
        self.engine = engine
        self.results: Dict[str, Dict[str, Any]] = {}
        self.failed_operations: List[str] = []

        # Validate batch request
        self._validate_batch_request()

        # Resolve execution order
        self.resolver = DependencyResolver(self.operations)
        self.execution_order = self.resolver.get_execution_order()

    def _validate_batch_request(self):
        """Validate the batch request structure."""
        if not self.operations:
            raise ApplicationException(
                400, "Batch request must contain at least one operation"
            )

        if len(self.operations) > 100:
            raise ApplicationException(
                400,
                f"Batch size exceeds maximum (100). "
                f"Requested: {len(self.operations)}",
            )

        # Auto-generate IDs for operations that don't have them
        seen_ids = set()
        for i, op in enumerate(self.operations):
            # Auto-generate ID if not provided
            if "id" not in op or not op["id"]:
                op["id"] = f"op_{i}"

            # Check for duplicate IDs
            if op["id"] in seen_ids:
                raise ApplicationException(
                    400,
                    f"Duplicate operation ID '{op['id']}' found",
                )
            seen_ids.add(op["id"])

            # Validate required fields
            if "entity" not in op:
                raise ApplicationException(
                    400,
                    f"Operation '{op['id']}' missing required field 'entity'",
                )
            if "action" not in op:
                raise ApplicationException(
                    400,
                    f"Operation '{op['id']}' missing required field 'action'",
                )
            if op["action"] not in ["create", "read", "update", "delete"]:
                raise ApplicationException(
                    400,
                    f"Operation '{op['id']}' has invalid action " f"'{op['action']}'",
                )

    def execute(self) -> Dict[str, Any]:
        """
        Execute all operations in dependency order.

        Returns:
            Dictionary with 'success', 'results', and optionally 'errors'

        Raises:
            ApplicationException: On validation or execution errors
        """
        atomic = self.options.get("atomic", True)
        continue_on_error = self.options.get("continueOnError", False)

        log.info(
            "Executing batch with %d operations (atomic=%s, continue=%s)",
            len(self.operations),
            atomic,
            continue_on_error,
        )

        try:
            for op_id in self.execution_order:
                # Check if we should skip this operation
                if self._should_skip_operation(op_id):
                    self.results[op_id] = {
                        "status": "skipped",
                        "reason": "Dependency failed",
                    }
                    continue

                # Execute the operation
                try:
                    result = self._execute_operation(op_id)
                    # Unwrap single-item lists for easier reference access
                    # e.g., $ref:op_0.invoice_id instead of $ref:op_0.0.invoice_id
                    if isinstance(result, list) and len(result) == 1:
                        result = result[0]
                    self.results[op_id] = {"status": "completed", "data": result}
                    log.info("Operation '%s' completed successfully", op_id)

                except ApplicationException as e:
                    log.error("Operation '%s' failed: %s", op_id, e.message)
                    self.results[op_id] = {
                        "status": "failed",
                        "error": e.message,
                        "statusCode": e.status_code,
                    }
                    self.failed_operations.append(op_id)

                    # Rollback the failed transaction
                    # In non-atomic mode, this allows next operation to proceed
                    if not atomic:
                        self.connection.rollback()
                        log.info("Failed operation rolled back (non-atomic mode)")

                    # Stop on error if not continuing
                    if not continue_on_error:
                        if atomic:
                            self.connection.rollback()
                            log.info("Transaction rolled back")
                        raise ApplicationException(
                            400,
                            f"Batch failed at operation '{op_id}': {e.message}",
                        ) from e

                # Commit each operation if not atomic and it succeeded
                if not atomic and op_id not in self.failed_operations:
                    self.connection.commit()
                    log.info("Operation '%s' committed (non-atomic mode)", op_id)

            # Commit transaction if atomic and all succeeded
            if atomic and not self.failed_operations:
                self.connection.commit()
                log.info("Batch transaction committed successfully")
            elif atomic and self.failed_operations and continue_on_error:
                self.connection.rollback()
                log.info("Batch had failures, transaction rolled back")

            # Build response
            success = len(self.failed_operations) == 0
            response = {"success": success, "results": self.results}

            if self.failed_operations:
                response["failedOperations"] = self.failed_operations

            return response

        except Exception as e:
            # Rollback on any unexpected error
            if atomic:
                self.connection.rollback()
                log.error("Batch failed, transaction rolled back")
            raise e

    def _should_skip_operation(self, op_id: str) -> bool:
        """
        Determine if operation should be skipped due to failed dependencies.

        Args:
            op_id: Operation ID to check

        Returns:
            True if operation should be skipped
        """
        op = next(o for o in self.operations if o["id"] == op_id)
        depends_on = op.get("depends_on", [])

        for dep_id in depends_on:
            if dep_id in self.failed_operations:
                log.info(
                    "Skipping operation '%s' due to failed dependency '%s'",
                    op_id,
                    dep_id,
                )
                return True
            if dep_id not in self.results:
                log.warning(
                    "Operation '%s' depends on '%s' which hasn't executed yet",
                    op_id,
                    dep_id,
                )
                return True
            if self.results[dep_id].get("status") != "completed":
                log.info(
                    "Skipping operation '%s' due to incomplete dependency '%s'",
                    op_id,
                    dep_id,
                )
                return True

        return False

    def _execute_operation(self, op_id: str) -> Any:
        """
        Execute a single operation.

        Args:
            op_id: Operation ID to execute

        Returns:
            Operation result data

        Raises:
            ApplicationException: On execution error
        """
        # Get operation definition
        op_def = next(o for o in self.operations if o["id"] == op_id)

        # Resolve references in parameters
        ref_resolver = ReferenceResolver(self.results)
        query_params = ref_resolver.resolve_parameters(
            op_def.get("query_params", {}), op_id
        )
        store_params = ref_resolver.resolve_parameters(
            op_def.get("store_params", {}), op_id
        )
        metadata_params = ref_resolver.resolve_parameters(
            op_def.get("metadata_params", {}), op_id
        )

        # Get claims from operation or use empty dict
        claims = op_def.get("claims", {})

        # Create Operation object
        operation = Operation(
            entity=op_def["entity"],
            action=op_def["action"],
            query_params=query_params,
            store_params=store_params,
            metadata_params=metadata_params,
            claims=claims,
        )

        log.debug(
            "Executing operation '%s': %s %s",
            op_id,
            operation.action,
            operation.entity,
        )

        # Execute through OperationDAO
        dao = OperationDAO(operation, self.engine)
        result = dao.execute(self.connection)

        return result

    def get_operation_summary(self) -> Dict[str, int]:
        """
        Get summary statistics of batch execution.

        Returns:
            Dictionary with counts of completed, failed, skipped operations
        """
        summary = {"total": len(self.operations), "completed": 0, "failed": 0}

        for op_result in self.results.values():
            status = op_result.get("status")
            if status == "completed":
                summary["completed"] += 1
            elif status == "failed":
                summary["failed"] += 1
            elif status == "skipped":
                summary["skipped"] = summary.get("skipped", 0) + 1

        return summary

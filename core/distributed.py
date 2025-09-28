"""
Distributed processing module for preventing duplicate record processing.

This module provides the DistributedProcessor class that handles atomic record
claiming and status management for distributed Prefect flows. It uses database-level
locking to ensure each record is processed exactly once, even when multiple
container instances are running concurrently.
"""

import socket
import uuid
from typing import Any, Optional

from core.config import ConfigManager
from core.database import DatabaseManager, _create_retry_decorator


class DistributedProcessor:
    """
    Distributed processor for atomic record claiming and status management.

    Handles the core distributed processing logic, working with DatabaseManager
    to provide atomic record claiming and status management. Prevents duplicate
    processing when multiple containers are running the same flow.

    Key Features:
    - Atomic record claiming using FOR UPDATE SKIP LOCKED
    - Unique instance ID generation for container isolation
    - Individual record failure handling without affecting batch processing
    - Integration with DatabaseManager's logging and error handling
    """

    def __init__(
        self,
        rpa_db_manager: DatabaseManager,
        source_db_manager: Optional[DatabaseManager] = None,
        config_manager: Optional[ConfigManager] = None
    ):
        """
        Initialize DistributedProcessor with DatabaseManager instances and configuration.

        Args:
            rpa_db_manager: DatabaseManager instance for PostgreSQL (queue and results)
            source_db_manager: Optional DatabaseManager for source data (SQL Server)
            config_manager: Optional ConfigManager for distributed processing configuration

        Raises:
            ValueError: If rpa_db_manager is None or invalid
            TypeError: If managers are not DatabaseManager instances
            RuntimeError: If configuration validation fails
        """
        if rpa_db_manager is None:
            raise ValueError("rpa_db_manager cannot be None")

        if not isinstance(rpa_db_manager, DatabaseManager):
            raise TypeError("rpa_db_manager must be a DatabaseManager instance")

        if source_db_manager is not None and not isinstance(source_db_manager, DatabaseManager):
            raise TypeError("source_db_manager must be a DatabaseManager instance or None")

        self.rpa_db = rpa_db_manager
        self.source_db = source_db_manager

        # Initialize configuration manager
        self.config_manager = config_manager or ConfigManager()

        # Load and validate distributed processing configuration
        try:
            self.config = self.config_manager.get_distributed_config()
        except (ValueError, RuntimeError) as e:
            raise RuntimeError(f"Failed to load distributed processing configuration: {e}") from e

        # Use DatabaseManager's logger for consistency
        self.logger = self.rpa_db.logger

        # Generate unique instance ID for this container/process
        self.instance_id = self._generate_instance_id()

        self.logger.info(
            f"DistributedProcessor initialized with instance_id: {self.instance_id}, "
            f"config: {self.config}"
        )

    def _generate_instance_id(self) -> str:
        """
        Generate unique instance ID using hostname and UUID.

        Creates a unique identifier for this container/process instance to prevent
        hostname collisions and enable tracking of which instance processed which records.

        Returns:
            Unique instance identifier string in format: hostname-uuid_prefix

        Example:
            "rpa-worker-1-abc123de"
        """
        try:
            # Get hostname (container name in Kubernetes/Docker environments)
            hostname = socket.gethostname()

            # Generate UUID and take first 8 characters for brevity
            uuid_prefix = str(uuid.uuid4()).replace('-', '')[:8]

            # Combine hostname and UUID prefix
            instance_id = f"{hostname}-{uuid_prefix}"

            self.logger.debug(f"Generated instance_id: {instance_id}")

            return instance_id

        except Exception as e:
            # Fallback to UUID-only if hostname fails
            fallback_id = f"unknown-{str(uuid.uuid4()).replace('-', '')[:8]}"
            self.logger.warning(
                f"Failed to get hostname for instance ID generation: {e}. "
                f"Using fallback: {fallback_id}"
            )
            return fallback_id

    @property
    def database_name(self) -> str:
        """Get the database name from the rpa_db manager."""
        return self.rpa_db.database_name

    def claim_records_batch(self, flow_name: str, batch_size: int) -> list[dict[str, Any]]:
        """
        Claim a batch of pending records atomically for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions when multiple
        containers attempt to claim records simultaneously. Records are claimed
        in FIFO order (oldest first) and atomically updated to 'processing' status.

        Args:
            flow_name: Name of the flow to claim records for
            batch_size: Maximum number of records to claim

        Returns:
            List of claimed records with id, payload, retry_count, and created_at fields.
            Returns empty list if no records are available.

        Raises:
            ValueError: If flow_name is empty or batch_size is invalid
            RuntimeError: If database operation fails

        Example:
            records = processor.claim_records_batch("survey_processor", 10)
            for record in records:
                # Process record['payload']
                processor.mark_record_completed(record['id'], result)
        """
        # Validate input parameters
        if not flow_name or not isinstance(flow_name, str):
            raise ValueError("flow_name must be a non-empty string")

        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        self.logger.info(
            f"Claiming batch of {batch_size} records for flow '{flow_name}' "
            f"with instance_id '{self.instance_id}'"
        )

        try:
            # SQL query to atomically claim records using FOR UPDATE SKIP LOCKED
            claim_query = """
                UPDATE processing_queue
                SET status = 'processing',
                    flow_instance_id = :instance_id,
                    claimed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT id FROM processing_queue
                    WHERE flow_name = :flow_name AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, payload, retry_count, created_at;
            """

            # Execute the claim query with parameters
            query_params = {
                'flow_name': flow_name,
                'batch_size': batch_size,
                'instance_id': self.instance_id
            }

            results = self.rpa_db.execute_query(claim_query, query_params)

            # Handle empty result set gracefully
            if not results:
                self.logger.debug(
                    f"No pending records found for flow '{flow_name}' "
                    f"(batch_size: {batch_size})"
                )
                return []

            # Convert results to list of dictionaries
            claimed_records = []
            for row in results:
                record = {
                    'id': row[0],
                    'payload': row[1],  # JSONB field
                    'retry_count': row[2],
                    'created_at': row[3]
                }
                claimed_records.append(record)

            self.logger.info(
                f"Successfully claimed {len(claimed_records)} records for flow '{flow_name}' "
                f"with instance_id '{self.instance_id}'"
            )

            return claimed_records

        except Exception as e:
            error_msg = (
                f"Failed to claim records for flow '{flow_name}' "
                f"(batch_size: {batch_size}, instance_id: '{self.instance_id}'): {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def mark_record_completed(self, record_id: int, result: dict[str, Any]) -> None:
        """
        Mark a record as completed and store the processing result.

        Updates the record status to 'completed', stores the result in the payload field,
        and sets the completed_at timestamp. This method should be called after
        successful processing of a claimed record.

        Args:
            record_id: ID of the record to mark as completed
            result: Processing result to store in the payload field

        Raises:
            ValueError: If record_id is invalid or result is not a dictionary
            RuntimeError: If database operation fails or record not found

        Example:
            result = {"satisfaction_score": 8.5, "processed_items": 3}
            processor.mark_record_completed(record_id, result)
        """
        # Validate input parameters
        if not isinstance(record_id, int) or record_id <= 0:
            raise ValueError("record_id must be a positive integer")

        if not isinstance(result, dict):
            raise ValueError("result must be a dictionary")

        self.logger.info(
            f"Marking record {record_id} as completed with instance_id '{self.instance_id}'"
        )

        try:
            # SQL query to update record status to completed
            update_query = """
                UPDATE processing_queue
                SET status = 'completed',
                    payload = :result,
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :record_id
                  AND status = 'processing'
                  AND flow_instance_id = :instance_id;
            """

            # Execute the update query
            query_params = {
                'record_id': record_id,
                'result': result,
                'instance_id': self.instance_id
            }

            rows_affected = self.rpa_db.execute_query(
                update_query, query_params, return_count=True
                )

            # Check if record was found and updated
            if rows_affected == 0:
                error_msg = (
                    f"Record {record_id} not found or not in processing state "
                    f"for instance_id '{self.instance_id}'"
                )
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            self.logger.info(
                f"Successfully marked record {record_id} as completed "
                f"with instance_id '{self.instance_id}'"
            )

        except Exception as e:
            if isinstance(e, RuntimeError):
                # Re-raise RuntimeError as-is (record not found case)
                raise

            error_msg = (
                f"Failed to mark record {record_id} as completed "
                f"for instance_id '{self.instance_id}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def mark_record_failed(self, record_id: int, error_message: str) -> None:
        """
        Mark a record as failed and increment retry count.

        Updates the record status to 'failed', stores the error message,
        increments the retry count, and sets the updated_at timestamp.
        This method should be called when processing of a claimed record fails.

        Args:
            record_id: ID of the record to mark as failed
            error_message: Error message describing the failure

        Raises:
            ValueError: If record_id is invalid or error_message is empty
            RuntimeError: If database operation fails or record not found

        Example:
            processor.mark_record_failed(record_id, "Invalid survey data format")
        """
        # Validate input parameters
        if not isinstance(record_id, int) or record_id <= 0:
            raise ValueError("record_id must be a positive integer")

        if not isinstance(error_message, str) or not error_message.strip():
            raise ValueError("error_message must be a non-empty string")

        self.logger.info(
            f"Marking record {record_id} as failed with instance_id '{self.instance_id}'"
        )

        try:
            # SQL query to update record status to failed and increment retry count
            update_query = """
                UPDATE processing_queue
                SET status = 'failed',
                    error_message = :error_message,
                    retry_count = retry_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :record_id
                  AND status = 'processing'
                  AND flow_instance_id = :instance_id;
            """

            # Execute the update query
            query_params = {
                'record_id': record_id,
                'error_message': error_message.strip(),
                'instance_id': self.instance_id
            }

            rows_affected = self.rpa_db.execute_query(
                update_query, query_params, return_count=True
                )

            # Check if record was found and updated
            if rows_affected == 0:
                error_msg = (
                    f"Record {record_id} not found or not in processing state "
                    f"for instance_id '{self.instance_id}'"
                )
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            self.logger.info(
                f"Successfully marked record {record_id} as failed "
                f"with instance_id '{self.instance_id}'"
            )

        except Exception as e:
            if isinstance(e, RuntimeError):
                # Re-raise RuntimeError as-is (record not found case)
                raise

            error_msg = (
                f"Failed to mark record {record_id} as failed "
                f"for instance_id '{self.instance_id}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def add_records_to_queue(
        self,
        flow_name: str,
        records: list[dict[str, Any]]
    ) -> int:
        """
        Add new records to the processing queue with pending status.

        Supports batch insertion for efficient bulk record addition. All records
        are added with 'pending' status and can be claimed by any processor instance.
        Validates required fields (flow_name, payload) before insertion.

        Args:
            flow_name: Name of the flow that will process these records
            records: List of record dictionaries, each containing 'payload' field

        Returns:
            Number of records successfully added to the queue

        Raises:
            ValueError: If flow_name is empty, records is empty, or validation fails
            RuntimeError: If database operation fails

        Example:
            records = [
                {"payload": {"survey_id": 1001, "customer_id": "CUST001"}},
                {"payload": {"survey_id": 1002, "customer_id": "CUST002"}}
            ]
            count = processor.add_records_to_queue("survey_processor", records)
        """
        # Validate input parameters
        if not flow_name or not isinstance(flow_name, str):
            raise ValueError("flow_name must be a non-empty string")

        if not isinstance(records, list) or len(records) == 0:
            raise ValueError("records must be a non-empty list")

        # Validate each record
        for i, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"Record at index {i} must be a dictionary")

            if 'payload' not in record:
                raise ValueError(f"Record at index {i} missing required 'payload' field")

            if not isinstance(record['payload'], dict):
                raise ValueError(f"Record at index {i} 'payload' must be a dictionary")

        self.logger.info(
            f"Adding {len(records)} records to queue for flow '{flow_name}'"
        )

        try:
            # Use batch insertion for efficiency
            if len(records) == 1:
                # Single record insertion
                insert_query = """
                    INSERT INTO processing_queue (flow_name, payload, status, created_at, updated_at)
                    VALUES (:flow_name, :payload, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """  # noqa: E501
                query_params = {
                    'flow_name': flow_name,
                    'payload': records[0]['payload']
                }
                self.rpa_db.execute_query(insert_query, query_params)
                inserted_count = 1

            else:
                # Batch insertion using VALUES clause
                values_placeholders = []
                query_params = {'flow_name': flow_name}

                for i, record in enumerate(records):
                    values_placeholders.append(
                        f"(:flow_name, :payload_{i}, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                    query_params[f'payload_{i}'] = record['payload']

                insert_query = f"""
                    INSERT INTO processing_queue (flow_name, payload, status, created_at, updated_at)
                    VALUES {', '.join(values_placeholders)}
                """

                self.rpa_db.execute_query(insert_query, query_params)
                inserted_count = len(records)

            self.logger.info(
                f"Successfully added {inserted_count} records to queue for flow '{flow_name}'"
            )

            return inserted_count

        except Exception as e:
            error_msg = (
                f"Failed to add {len(records)} records to queue for flow '{flow_name}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def get_queue_status(self, flow_name: Optional[str] = None) -> dict[str, Any]:
        """
        Get queue status with counts by status and optionally by flow_name.

        Returns comprehensive queue statistics including record counts by status.
        Can be filtered by flow_name or return system-wide statistics.

        Args:
            flow_name: Optional flow name to filter results. If None, returns all flows.

        Returns:
            Dictionary containing queue status information with the following structure:
            {
                "total_records": int,
                "pending_records": int,
                "processing_records": int,
                "completed_records": int,
                "failed_records": int,
                "flow_name": str or None,
                "by_flow": {flow_name: {status: count}} (if flow_name is None)
            }

        Raises:
            RuntimeError: If database operation fails

        Example:
            # Get status for specific flow
            status = processor.get_queue_status("survey_processor")

            # Get system-wide status
            status = processor.get_queue_status()
        """
        # Validate input parameters
        if flow_name is not None and (not isinstance(flow_name, str) or not flow_name.strip()):
            raise ValueError("flow_name must be a non-empty string or None")

        self.logger.debug(
            f"Getting queue status for flow: {flow_name or 'all flows'}"
        )

        try:
            if flow_name:
                # Get status for specific flow
                status_query = """
                    SELECT status, COUNT(*) as count
                    FROM processing_queue
                    WHERE flow_name = :flow_name
                    GROUP BY status
                """
                query_params = {'flow_name': flow_name}

            else:
                # Get system-wide status
                status_query = """
                    SELECT status, COUNT(*) as count
                    FROM processing_queue
                    GROUP BY status
                """
                query_params = {}

            results = self.rpa_db.execute_query(status_query, query_params)

            # Initialize status counts
            status_counts = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }

            # Process query results
            for row in results:
                status = row[0]
                count = row[1]
                if status in status_counts:
                    status_counts[status] = count

            # Calculate total
            total_records = sum(status_counts.values())

            # Build response
            queue_status = {
                'total_records': total_records,
                'pending_records': status_counts['pending'],
                'processing_records': status_counts['processing'],
                'completed_records': status_counts['completed'],
                'failed_records': status_counts['failed'],
                'flow_name': flow_name
            }

            # If no specific flow requested, add breakdown by flow
            if flow_name is None:
                by_flow_query = """
                    SELECT flow_name, status, COUNT(*) as count
                    FROM processing_queue
                    GROUP BY flow_name, status
                    ORDER BY flow_name, status
                """
                by_flow_results = self.rpa_db.execute_query(by_flow_query, {})

                by_flow = {}
                for row in by_flow_results:
                    flow = row[0]
                    status = row[1]
                    count = row[2]

                    if flow not in by_flow:
                        by_flow[flow] = {
                            'pending': 0,
                            'processing': 0,
                            'completed': 0,
                            'failed': 0,
                            'total': 0
                        }

                    by_flow[flow][status] = count
                    by_flow[flow]['total'] += count

                queue_status['by_flow'] = by_flow

            self.logger.debug(
                f"Queue status retrieved: {total_records} total records "
                f"({status_counts['pending']} pending, {status_counts['processing']} processing, "
                f"{status_counts['completed']} completed, {status_counts['failed']} failed)"
            )

            return queue_status

        except Exception as e:
            error_msg = f"Failed to get queue status for flow '{flow_name}': {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def cleanup_orphaned_records(self, timeout_hours: int = 1) -> int:
        """
        Reset stuck processing records after timeout to pending status.

        Identifies records that have been in 'processing' status for longer than
        the specified timeout and resets them to 'pending' status so they can be
        claimed again. This handles cases where containers crash or fail without
        properly updating record status.

        Args:
            timeout_hours: Number of hours after which processing records are
                         considered orphaned (default: 1 hour)

        Returns:
            Number of orphaned records that were reset to pending status

        Raises:
            ValueError: If timeout_hours is not a positive integer
            RuntimeError: If database operation fails

        Example:
            # Clean up records stuck for more than 2 hours
            cleaned_count = processor.cleanup_orphaned_records(timeout_hours=2)
        """
        # Validate input parameters
        if not isinstance(timeout_hours, int) or timeout_hours <= 0:
            raise ValueError("timeout_hours must be a positive integer")

        self.logger.info(
            f"Starting cleanup of orphaned records with timeout: {timeout_hours} hours"
        )

        try:
            # SQL query to reset orphaned records
            cleanup_query = f"""
                UPDATE processing_queue
                SET status = 'pending',
                    flow_instance_id = NULL,
                    claimed_at = NULL,
                    retry_count = retry_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                  AND claimed_at < CURRENT_TIMESTAMP - INTERVAL '{timeout_hours} hours'
            """

            # Execute the cleanup query
            rows_affected = self.rpa_db.execute_query(cleanup_query, {}, return_count=True)

            if rows_affected > 0:
                self.logger.warning(
                    f"Cleaned up {rows_affected} orphaned records that were stuck "
                    f"in processing status for more than {timeout_hours} hours"
                )
            else:
                self.logger.debug(
                    f"No orphaned records found with timeout: {timeout_hours} hours"
                )

            return rows_affected

        except Exception as e:
            error_msg = (
                f"Failed to cleanup orphaned records with timeout {timeout_hours} hours: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def reset_failed_records(self, flow_name: str, max_retries: int = 3) -> int:
        """
        Reset failed records to pending status for retry within retry limits.

        Identifies failed records for a specific flow that have not exceeded the
        maximum retry limit and resets them to 'pending' status so they can be
        processed again. Records that have exceeded the retry limit are left
        in 'failed' status for manual review.

        Args:
            flow_name: Name of the flow to reset failed records for
            max_retries: Maximum number of retries allowed before giving up (default: 3)

        Returns:
            Number of failed records that were reset to pending status

        Raises:
            ValueError: If flow_name is empty or max_retries is not a positive integer
            RuntimeError: If database operation fails

        Example:
            # Reset failed survey processing records (up to 5 retries)
            reset_count = processor.reset_failed_records("survey_processor", max_retries=5)
        """
        # Validate input parameters
        if not flow_name or not isinstance(flow_name, str):
            raise ValueError("flow_name must be a non-empty string")

        if not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError("max_retries must be a positive integer")

        self.logger.info(
            f"Resetting failed records for flow '{flow_name}' "
            f"with max_retries: {max_retries}"
        )

        try:
            # First, get count of records that will be reset vs. those that won't
            count_query = """
                SELECT
                    COUNT(*) FILTER (WHERE retry_count < :max_retries) as resettable,
                    COUNT(*) FILTER (WHERE retry_count >= :max_retries) as exceeded_limit,
                    COUNT(*) as total
                FROM processing_queue
                WHERE flow_name = :flow_name AND status = 'failed'
            """

            count_params = {
                'flow_name': flow_name,
                'max_retries': max_retries
            }

            count_results = self.rpa_db.execute_query(count_query, count_params)

            if count_results:
                resettable = count_results[0][0] or 0
                exceeded_limit = count_results[0][1] or 0
                total_failed = count_results[0][2] or 0

                self.logger.info(
                    f"Found {total_failed} failed records for flow '{flow_name}': "
                    f"{resettable} can be reset, {exceeded_limit} exceeded retry limit"
                )
            else:
                resettable = 0

            # Reset eligible failed records to pending
            if resettable > 0:
                reset_query = """
                    UPDATE processing_queue
                    SET status = 'pending',
                        flow_instance_id = NULL,
                        claimed_at = NULL,
                        error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE flow_name = :flow_name
                      AND status = 'failed'
                      AND retry_count < :max_retries
                """

                reset_params = {
                    'flow_name': flow_name,
                    'max_retries': max_retries
                }

                rows_affected = self.rpa_db.execute_query(reset_query, reset_params, return_count=True)

                self.logger.info(
                    f"Successfully reset {rows_affected} failed records to pending "
                    f"for flow '{flow_name}' (max_retries: {max_retries})"
                )

                return rows_affected
            else:
                self.logger.debug(
                    f"No failed records eligible for reset found for flow '{flow_name}' "
                    f"(max_retries: {max_retries})"
                )
                return 0

        except Exception as e:
            error_msg = (
                f"Failed to reset failed records for flow '{flow_name}' "
                f"(max_retries: {max_retries}): {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive health check of the distributed processing system.

        Validates both rpa_db and source_db DatabaseManager instances using their
        existing health_check methods, retrieves queue status metrics, and includes
        instance information. Provides a complete view of system health for monitoring.

        Returns:
            Dictionary containing comprehensive health status with the following structure:
            {
                "status": "healthy|degraded|unhealthy",
                "databases": {
                    "rpa_db": {
                        "status": "healthy|degraded|unhealthy",
                        "connection": bool,
                        "response_time_ms": float,
                        "error": str (if unhealthy)
                    },
                    "source_db": {  # Only if source_db is configured
                        "status": "healthy|degraded|unhealthy",
                        "connection": bool,
                        "response_time_ms": float,
                        "error": str (if unhealthy)
                    }
                },
                "queue_status": {
                    "pending_records": int,
                    "processing_records": int,
                    "completed_records": int,
                    "failed_records": int,
                    "total_records": int
                },
                "instance_info": {
                    "instance_id": str,
                    "hostname": str,
                    "rpa_db_name": str,
                    "source_db_name": str or None
                },
                "timestamp": str (ISO format),
                "error": str (if overall status is unhealthy)
            }

        Raises:
            RuntimeError: If critical health check operations fail

        Example:
            health = processor.health_check()
            if health["status"] == "unhealthy":
                logger.error(f"System unhealthy: {health.get('error', 'Unknown error')}")
        """
        from datetime import datetime, timezone

        self.logger.debug("Starting distributed processing system health check")

        try:
            # Initialize health status structure
            health_status = {
                "status": "healthy",
                "databases": {},
                "queue_status": {},
                "instance_info": {
                    "instance_id": self.instance_id,
                    "hostname": socket.gethostname(),
                    "rpa_db_name": self.rpa_db.database_name,
                    "source_db_name": self.source_db.database_name if self.source_db else None
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Check rpa_db health (required database)
            try:
                self.logger.debug("Checking rpa_db health")
                rpa_db_health = self.rpa_db.health_check()
                health_status["databases"]["rpa_db"] = rpa_db_health

                # If rpa_db is unhealthy, entire system is unhealthy
                if rpa_db_health.get("status") == "unhealthy":
                    health_status["status"] = "unhealthy"
                    health_status["error"] = f"RPA database unhealthy: {rpa_db_health.get('error', 'Unknown error')}"
                elif rpa_db_health.get("status") == "degraded":
                    health_status["status"] = "degraded"

            except Exception as e:
                self.logger.error(f"Failed to check rpa_db health: {e}")
                health_status["databases"]["rpa_db"] = {
                    "status": "unhealthy",
                    "connection": False,
                    "error": str(e)
                }
                health_status["status"] = "unhealthy"
                health_status["error"] = f"RPA database health check failed: {e}"

            # Check source_db health (optional database)
            if self.source_db:
                try:
                    self.logger.debug("Checking source_db health")
                    source_db_health = self.source_db.health_check()
                    health_status["databases"]["source_db"] = source_db_health

                    # Source DB issues cause degraded status, not unhealthy
                    if source_db_health.get("status") == "unhealthy":
                        if health_status["status"] == "healthy":
                            health_status["status"] = "degraded"
                    elif source_db_health.get("status") == "degraded":
                        if health_status["status"] == "healthy":
                            health_status["status"] = "degraded"

                except Exception as e:
                    self.logger.warning(f"Failed to check source_db health: {e}")
                    health_status["databases"]["source_db"] = {
                        "status": "unhealthy",
                        "connection": False,
                        "error": str(e)
                    }
                    # Source DB failure only causes degraded status
                    if health_status["status"] == "healthy":
                        health_status["status"] = "degraded"

            # Get queue status metrics (only if rpa_db is healthy enough)
            if health_status["databases"]["rpa_db"].get("connection", False):
                try:
                    self.logger.debug("Retrieving queue status metrics")
                    queue_status = self.get_queue_status()
                    health_status["queue_status"] = {
                        "pending_records": queue_status["pending_records"],
                        "processing_records": queue_status["processing_records"],
                        "completed_records": queue_status["completed_records"],
                        "failed_records": queue_status["failed_records"],
                        "total_records": queue_status["total_records"]
                    }

                except Exception as e:
                    self.logger.warning(f"Failed to retrieve queue status: {e}")
                    health_status["queue_status"] = {
                        "pending_records": -1,
                        "processing_records": -1,
                        "completed_records": -1,
                        "failed_records": -1,
                        "total_records": -1,
                        "error": str(e)
                    }
                    # Queue status failure causes degraded status if not already unhealthy
                    if health_status["status"] == "healthy":
                        health_status["status"] = "degraded"
            else:
                # Cannot get queue status without database connection
                health_status["queue_status"] = {
                    "pending_records": -1,
                    "processing_records": -1,
                    "completed_records": -1,
                    "failed_records": -1,
                    "total_records": -1,
                    "error": "Database connection unavailable"
                }

            # Log health check result
            status = health_status["status"]
            if status == "healthy":
                self.logger.info(f"Health check completed: {status}")
            elif status == "degraded":
                self.logger.warning(f"Health check completed: {status}")
            else:
                self.logger.error(f"Health check completed: {status} - {health_status.get('error', 'Unknown error')}")

            return health_status

        except Exception as e:
            # Critical failure in health check itself
            error_msg = f"Critical failure during health check: {e}"
            self.logger.error(error_msg)

            # Return minimal unhealthy status
            return {
                "status": "unhealthy",
                "error": error_msg,
                "instance_info": {
                    "instance_id": self.instance_id,
                    "hostname": "unknown",
                    "rpa_db_name": getattr(self.rpa_db, 'database_name', 'unknown'),
                    "source_db_name": getattr(self.source_db, 'database_name', None) if self.source_db else None
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def process_survey_logic(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Process survey data using multi-database pattern.

        Demonstrates the multi-database processing pattern by reading source data
        from SurveyHub (SQL Server) and writing results to rpa_db (PostgreSQL).
        This function implements requirements 3.2, 3.3, and 3.4 for multi-database
        integration.

        Args:
            payload: Dictionary containing survey processing parameters.
                    Must include 'survey_id' field.

        Returns:
            Dictionary containing processed survey results with the following structure:
            {
                "survey_id": str,
                "customer_id": str,
                "satisfaction_score": float,
                "processed_at": datetime,
                "processing_duration_ms": int,
                "source": str
            }

        Raises:
            ValueError: If payload is invalid or survey_id not found
            RuntimeError: If database operations fail
            TypeError: If source_db_manager is not configured

        Example:
            payload = {"survey_id": "SURV-001", "customer_id": "CUST-001"}
            result = processor.process_survey_logic(payload)
        """
        # Validate input parameters
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dictionary")

        if 'survey_id' not in payload:
            raise ValueError("payload must contain 'survey_id' field")

        survey_id = payload['survey_id']
        if not isinstance(survey_id, str) or not survey_id.strip():
            raise ValueError("survey_id must be a non-empty string")

        # Check if source database is configured
        if self.source_db is None:
            raise TypeError("source_db_manager is required for multi-database processing")

        self.logger.info(f"Processing survey {survey_id} using multi-database pattern")

        try:
            import time
            from datetime import datetime, timezone

            start_time = time.time()

            # Step 1: Read source data from SurveyHub (SQL Server)
            # Requirement 3.2: Use DatabaseManager("SurveyHub") for SQL Server queries
            survey_data = self._retrieve_source_survey_data(survey_id)

            # Step 2: Process the data (business logic)
            processed_result = self._transform_survey_data(survey_data, payload)

            # Step 3: Write results to PostgreSQL
            # Requirement 3.4: Use appropriate DatabaseManager instance for target database
            self._store_survey_results(processed_result)

            # Calculate processing duration
            end_time = time.time()
            processing_duration_ms = int((end_time - start_time) * 1000)

            # Add metadata to result
            processed_result.update({
                "processed_at": datetime.now(timezone.utc),
                "processing_duration_ms": processing_duration_ms,
                "source": "multi_database_processor"
            })

            self.logger.info(
                f"Successfully processed survey {survey_id} in {processing_duration_ms}ms"
            )

            return processed_result

        except Exception as e:
            error_msg = f"Failed to process survey {survey_id}: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _retrieve_source_survey_data(self, survey_id: str) -> dict[str, Any]:
        """
        Retrieve source survey data from SurveyHub database.

        Implements requirement 3.2: Use DatabaseManager("SurveyHub") for SQL Server queries.

        Args:
            survey_id: Survey identifier to retrieve

        Returns:
            Dictionary containing survey data from source database

        Raises:
            ValueError: If survey not found
            RuntimeError: If database query fails
        """
        try:
            # Query source database for survey data
            # Note: In a real implementation, this would query actual SurveyHub tables
            # For this implementation, we'll simulate the source data structure
            source_query = """
                SELECT survey_id, customer_id, response_data, submitted_at, survey_type
                FROM survey_responses
                WHERE survey_id = :survey_id
            """

            query_params = {"survey_id": survey_id}

            self.logger.debug(f"Querying source database for survey {survey_id}")

            # Execute query using source DatabaseManager
            results = self.source_db.execute_query(source_query, query_params)

            if not results:
                raise ValueError(f"Survey {survey_id} not found in source database")

            # Convert result to dictionary
            survey_row = results[0]
            survey_data = {
                "survey_id": survey_row[0],
                "customer_id": survey_row[1],
                "response_data": survey_row[2],  # Assuming JSON/JSONB field
                "submitted_at": survey_row[3],
                "survey_type": survey_row[4]
            }

            self.logger.debug(f"Retrieved survey data for {survey_id}: {survey_data}")

            return survey_data

        except ValueError:
            # Re-raise ValueError as-is (survey not found)
            raise
        except Exception as e:
            error_msg = f"Failed to retrieve survey data for {survey_id}: {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _transform_survey_data(
        self,
        survey_data: dict[str, Any],
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Transform survey data with business logic processing.

        Implements business logic for survey data transformation including
        satisfaction score calculation and data validation.

        Args:
            survey_data: Raw survey data from source database
            payload: Original processing payload with additional parameters

        Returns:
            Dictionary containing transformed survey results

        Raises:
            ValueError: If survey data is invalid or missing required fields
        """
        try:
            # Extract survey information
            survey_id = survey_data["survey_id"]
            customer_id = survey_data["customer_id"]
            response_data = survey_data.get("response_data", {})
            survey_type = survey_data.get("survey_type", "unknown")

            self.logger.debug(f"Transforming survey data for {survey_id}")

            # Business logic: Calculate satisfaction score
            satisfaction_score = self._calculate_satisfaction_score(response_data, survey_type)

            # Business logic: Determine processing status
            processing_status = "completed" if satisfaction_score is not None else "failed"

            # Create processed result
            processed_result = {
                "survey_id": survey_id,
                "customer_id": customer_id,
                "satisfaction_score": satisfaction_score,
                "survey_type": survey_type,
                "processing_status": processing_status,
                "flow_run_id": payload.get("flow_run_id", f"distributed-{self.instance_id}")
            }

            # Add customer name if available in payload or derive from customer_id
            if "customer_name" in payload:
                processed_result["customer_name"] = payload["customer_name"]
            else:
                # Simple derivation for demo purposes
                processed_result["customer_name"] = f"Customer {customer_id}"

            self.logger.debug(
                f"Transformed survey {survey_id}: score={satisfaction_score}, "
                f"status={processing_status}"
            )

            return processed_result

        except Exception as e:
            error_msg = f"Failed to transform survey data for {survey_data.get('survey_id', 'unknown')}: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _calculate_satisfaction_score(
        self,
        response_data: dict[str, Any],
        survey_type: str
    ) -> Optional[float]:
        """
        Calculate satisfaction score based on survey responses.

        Implements business logic for satisfaction score calculation based on
        survey type and response data structure.

        Args:
            response_data: Survey response data (JSON structure)
            survey_type: Type of survey (affects scoring algorithm)

        Returns:
            Calculated satisfaction score (0.0-10.0) or None if calculation fails
        """
        try:
            if not isinstance(response_data, dict):
                self.logger.warning("Invalid response_data format, using default score")
                return 5.0  # Default neutral score

            # Different scoring logic based on survey type
            if survey_type == "Customer Satisfaction":
                # Look for overall satisfaction rating
                overall_rating = response_data.get("overall_satisfaction")
                if overall_rating is not None:
                    return float(overall_rating)

                # Fallback: average of all numeric ratings
                ratings = []
                for _key, value in response_data.items():
                    if isinstance(value, (int, float)) and 0 <= value <= 10:
                        ratings.append(float(value))

                return sum(ratings) / len(ratings) if ratings else 5.0

            elif survey_type == "Product Feedback":
                # Product feedback scoring
                product_rating = response_data.get("product_rating", 5.0)
                recommendation_score = response_data.get("recommendation_likelihood", 5.0)

                # Weighted average: 70% product rating, 30% recommendation
                return (float(product_rating) * 0.7) + (float(recommendation_score) * 0.3)

            elif survey_type == "Market Research":
                # Market research scoring (simpler approach)
                interest_level = response_data.get("interest_level", 5.0)
                return float(interest_level)

            else:
                # Unknown survey type - use simple average
                numeric_values = []
                for value in response_data.values():
                    if isinstance(value, (int, float)) and 0 <= value <= 10:
                        numeric_values.append(float(value))

                return sum(numeric_values) / len(numeric_values) if numeric_values else 5.0

        except Exception as e:
            self.logger.warning(f"Failed to calculate satisfaction score: {e}")
            return None

    def _store_survey_results(self, processed_result: dict[str, Any]) -> None:
        """
        Store processed survey results in rpa_db (PostgreSQL).

        Implements requirement 3.3: Use DatabaseManager("rpa_db") for PostgreSQL operations.

        Args:
            processed_result: Processed survey data to store

        Raises:
            RuntimeError: If database insert operation fails
        """
        try:
            # Requirement 3.3: Use DatabaseManager("rpa_db") for PostgreSQL operations
            insert_query = """
                INSERT INTO processed_surveys
                (survey_id, customer_id, customer_name, survey_type, processing_status,
                 processed_at, processing_duration_ms, flow_run_id)
                VALUES (:survey_id, :customer_id, :customer_name, :survey_type,
                        :processing_status, :processed_at, :processing_duration_ms, :flow_run_id)
            """

            # Prepare parameters for insertion
            insert_params = {
                "survey_id": processed_result["survey_id"],
                "customer_id": processed_result["customer_id"],
                "customer_name": processed_result["customer_name"],
                "survey_type": processed_result["survey_type"],
                "processing_status": processed_result["processing_status"],
                "processed_at": processed_result.get("processed_at"),
                "processing_duration_ms": processed_result.get("processing_duration_ms"),
                "flow_run_id": processed_result["flow_run_id"]
            }

            self.logger.debug(
                f"Storing survey results for {processed_result['survey_id']} in rpa_db"
            )

            # Execute insert using rpa_db DatabaseManager
            self.rpa_db.execute_query(insert_query, insert_params)

            self.logger.info(
                f"Successfully stored survey results for {processed_result['survey_id']} "
                f"with status {processed_result['processing_status']}"
            )

        except Exception as e:
            error_msg = (
                f"Failed to store survey results for {processed_result.get('survey_id', 'unknown')}: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    # Retry-enabled versions of critical operations

    def claim_records_batch_with_retry(
        self,
        flow_name: str,
        batch_size: int,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0
    ) -> list[dict[str, Any]]:
        """
        Claim a batch of pending records atomically with automatic retry for transient failures.

        This method wraps claim_records_batch with configurable retry logic that
        automatically retries on transient database errors such as connection
        timeouts, network issues, or temporary database unavailability.

        Args:
            flow_name: Name of the flow to claim records for
            batch_size: Maximum number of records to claim
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            List of claimed records with id, payload, retry_count, and created_at fields.
            Returns empty list if no records are available.

        Raises:
            ValueError: If flow_name is empty or batch_size is invalid
            RuntimeError: If database operation fails after all retry attempts

        Example:
            records = processor.claim_records_batch_with_retry("survey_processor", 10)
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait
        )

        @retry_decorator
        def _claim_with_retry():
            self.logger.debug(
                f"Claiming records with retry for flow '{flow_name}' "
                f"(batch_size: {batch_size}, max_attempts: {max_attempts})"
            )
            return self.claim_records_batch(flow_name, batch_size)

        try:
            return _claim_with_retry()
        except Exception as e:
            error_msg = (
                f"Record claiming with retry failed for flow '{flow_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def mark_record_completed_with_retry(
        self,
        record_id: int,
        result: dict[str, Any],
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0
    ) -> None:
        """
        Mark a record as completed with automatic retry for transient failures.

        This method wraps mark_record_completed with configurable retry logic that
        automatically retries on transient database errors. Ensures that record
        completion status is reliably updated even in the presence of temporary
        database connectivity issues.

        Args:
            record_id: ID of the record to mark as completed
            result: Processing result to store in the payload field
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Raises:
            ValueError: If record_id is invalid or result is not a dictionary
            RuntimeError: If database operation fails after all retry attempts

        Example:
            result = {"satisfaction_score": 8.5, "processed_items": 3}
            processor.mark_record_completed_with_retry(record_id, result)
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait
        )

        @retry_decorator
        def _mark_completed_with_retry():
            self.logger.debug(
                f"Marking record {record_id} as completed with retry "
                f"(max_attempts: {max_attempts})"
            )
            return self.mark_record_completed(record_id, result)

        try:
            return _mark_completed_with_retry()
        except Exception as e:
            error_msg = (
                f"Mark record completed with retry failed for record {record_id} "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def mark_record_failed_with_retry(
        self,
        record_id: int,
        error_message: str,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0
    ) -> None:
        """
        Mark a record as failed with automatic retry for transient failures.

        This method wraps mark_record_failed with configurable retry logic that
        automatically retries on transient database errors. Ensures that record
        failure status is reliably updated even in the presence of temporary
        database connectivity issues.

        Args:
            record_id: ID of the record to mark as failed
            error_message: Error message describing the failure
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Raises:
            ValueError: If record_id is invalid or error_message is empty
            RuntimeError: If database operation fails after all retry attempts

        Example:
            processor.mark_record_failed_with_retry(record_id, "Invalid survey data format")
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait
        )

        @retry_decorator
        def _mark_failed_with_retry():
            self.logger.debug(
                f"Marking record {record_id} as failed with retry "
                f"(max_attempts: {max_attempts})"
            )
            return self.mark_record_failed(record_id, error_message)

        try:
            return _mark_failed_with_retry()
        except Exception as e:
            error_msg = (
                f"Mark record failed with retry failed for record {record_id} "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def cleanup_orphaned_records_with_retry(
        self,
        timeout_hours: int = 1,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0
    ) -> int:
        """
        Reset stuck processing records with automatic retry for transient failures.

        This method wraps cleanup_orphaned_records with configurable retry logic that
        automatically retries on transient database errors. Ensures that cleanup
        operations are reliably executed even in the presence of temporary
        database connectivity issues.

        Args:
            timeout_hours: Number of hours after which processing records are
                         considered orphaned (default: 1 hour)
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            Number of orphaned records that were reset to pending status

        Raises:
            ValueError: If timeout_hours is not a positive integer
            RuntimeError: If database operation fails after all retry attempts

        Example:
            cleaned_count = processor.cleanup_orphaned_records_with_retry(timeout_hours=2)
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait
        )

        @retry_decorator
        def _cleanup_with_retry():
            self.logger.debug(
                f"Cleaning up orphaned records with retry "
                f"(timeout_hours: {timeout_hours}, max_attempts: {max_attempts})"
            )
            return self.cleanup_orphaned_records(timeout_hours)

        try:
            return _cleanup_with_retry()
        except Exception as e:
            error_msg = (
                f"Cleanup orphaned records with retry failed "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def reset_failed_records_with_retry(
        self,
        flow_name: str,
        max_retries: int = 3,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0
    ) -> int:
        """
        Reset failed records to pending status with automatic retry for transient failures.

        This method wraps reset_failed_records with configurable retry logic that
        automatically retries on transient database errors. Ensures that failed
        record reset operations are reliably executed even in the presence of
        temporary database connectivity issues.

        Args:
            flow_name: Name of the flow to reset failed records for
            max_retries: Maximum number of retries allowed before giving up (default: 3)
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            Number of failed records that were reset to pending status

        Raises:
            ValueError: If flow_name is empty or max_retries is not a positive integer
            RuntimeError: If database operation fails after all retry attempts

        Example:
            reset_count = processor.reset_failed_records_with_retry("survey_processor", max_retries=5)
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait
        )

        @retry_decorator
        def _reset_failed_with_retry():
            self.logger.debug(
                f"Resetting failed records with retry for flow '{flow_name}' "
                f"(max_retries: {max_retries}, max_attempts: {max_attempts})"
            )
            return self.reset_failed_records(flow_name, max_retries)

        try:
            return _reset_failed_with_retry()
        except Exception as e:
            error_msg = (
                f"Reset failed records with retry failed for flow '{flow_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def __repr__(self) -> str:
        """String representation of DistributedProcessor."""
        source_db_name = self.source_db.database_name if self.source_db else "None"
        return (
            f"DistributedProcessor(rpa_db='{self.rpa_db.database_name}', "
            f"source_db='{source_db_name}', instance_id='{self.instance_id}')"
        )

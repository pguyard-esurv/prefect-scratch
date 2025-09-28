# Implementation Plan

- [x] 1. Create database migrations for processing queue

  - Create V006\_\_Create_processing_queue.sql migration file in core/migrations/rpa_db/
  - Define processing_queue table with id, flow_name, payload (JSONB), status, flow_instance_id, timestamps, and retry_count columns
  - Add status check constraint for pending/processing/completed/failed values
  - Create update trigger for updated_at timestamp column
  - Write unit tests to verify migration file syntax and table structure
  - _Requirements: 1.1, 1.3, 10.1, 10.2_

- [x] 2. Create performance indexes for processing queue

  - Create V007\_\_Add_processing_indexes.sql migration file in core/migrations/rpa_db/
  - Add composite index on (status, created_at) for efficient pending record queries
  - Add composite index on (flow_name, status) for flow-specific queries
  - Add partial indexes for pending and processing status records
  - Add index on flow_instance_id for cleanup operations
  - Test index performance with sample data and query patterns
  - _Requirements: 1.4, 8.3, 8.4_

- [x] 3. Implement core DistributedProcessor class

  - Create core/distributed.py file with DistributedProcessor class
  - Implement \_\_init\_\_ method accepting DatabaseManager instances for rpa_db and optional source_db
  - Add logger initialization using DatabaseManager's logger for consistency
  - Implement unique instance ID generation using hostname and UUID
  - Write unit tests for class initialization and instance ID generation
  - _Requirements: 2.5, 3.1, 3.4, 7.1, 9.1_

- [x] 4. Implement atomic record claiming functionality

  - Create claim_records_batch method using FOR UPDATE SKIP LOCKED SQL pattern
  - Implement atomic status update from pending to processing with instance ID assignment
  - Add FIFO ordering by created_at timestamp for fair processing
  - Handle empty result sets gracefully when no records are available
  - Write unit tests with mocked DatabaseManager to verify claiming logic and SQL queries
  - _Requirements: 1.1, 1.2, 2.1, 2.5_

- [x] 5. Implement record status management methods

  - Create mark_record_completed method to update status and store results in payload
  - Create mark_record_failed method to update status, error message, and increment retry count
  - Add proper error handling and logging for status update operations
  - Ensure all status updates include updated_at timestamp
  - Write unit tests for both success and failure scenarios with mocked database operations
  - _Requirements: 2.3, 2.4, 4.1, 4.2_

- [x] 6. Implement queue management utilities

  - Create add_records_to_queue method for adding new records with pending status
  - Implement get_queue_status method returning counts by status and flow_name
  - Add batch insertion support for efficient bulk record addition
  - Include validation for required fields (flow_name, payload)
  - Write unit tests for queue management operations and validation logic
  - _Requirements: 1.3, 6.2, 9.2_

- [x] 7. Implement cleanup and maintenance operations

  - Create cleanup_orphaned_records method to reset stuck processing records after timeout
  - Implement reset_failed_records method to retry failed records within retry limits
  - Add configurable timeout parameter (default 1 hour) for orphaned record detection
  - Include logging of cleanup operations and affected record counts
  - Write unit tests for cleanup scenarios with various timeout and retry conditions
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 8. Implement health monitoring integration

  - Create health_check method that validates both rpa_db and source_db DatabaseManager instances
  - Integrate with DatabaseManager's existing health_check methods for database connectivity
  - Add queue status metrics (pending, processing, failed record counts) to health response
  - Include instance information (instance_id, hostname) in health status
  - Write unit tests for health check scenarios including healthy, degraded, and unhealthy states
  - _Requirements: 6.1, 6.4, 6.5, 8.5_

- [x] 9. Create distributed flow template

  - Create core/flow_template.py with standardized distributed processing flow pattern
  - Implement module-level DatabaseManager and DistributedProcessor instances for performance
  - Add mandatory database health check before processing begins with fail-fast behavior
  - Create distributed_processing_flow function with record claiming, mapping, and summary generation
  - Write process_record_with_status task with individual record error handling
  - Write unit tests for flow template with mocked processor and database operations
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2_

- [x] 10. Implement multi-database processing pattern

  - Create process_survey_logic function demonstrating read from SurveyHub, write to rpa_db pattern
  - Implement source data retrieval using source DatabaseManager instance
  - Add business logic processing with proper error handling for missing data
  - Implement result storage using rpa_db DatabaseManager instance
  - Write integration tests with test databases to verify multi-database operations
  - _Requirements: 3.2, 3.3, 3.4, 5.5_

- [x] 11. Add retry logic and resilience features

  - Integrate tenacity retry decorators for transient database failures
  - Implement retry-enabled versions of critical operations (claim_records_batch, status updates)
  - Add exponential backoff configuration for connection retries
  - Ensure retry logic doesn't conflict with database-level retry counting
  - Write unit tests for retry behavior with simulated transient and permanent failures
  - _Requirements: 4.3, 9.1, 9.2_

- [x] 12. Create example distributed flow implementation

  - Create flows/examples/distributed_survey_processing.py with complete working example
  - Implement sample record preparation function for adding surveys to processing queue
  - Add example business logic for survey data transformation and scoring
  - Include proper error handling, logging, and summary generation
  - Create integration test that runs the complete flow with test data
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 13. Update existing flows to support distributed processing

  - Update flows/rpa1/workflow.py to optionally use distributed processing pattern
  - Update flows/rpa2/workflow.py to optionally use distributed processing pattern
  - Update flows/rpa3/workflow.py to optionally use distributed processing pattern
  - Add configuration flags to enable/disable distributed processing per flow
  - Maintain backward compatibility with existing non-distributed execution
  - _Requirements: 5.1, 5.2, 11.1, 11.2_

- [x] 14. Implement configuration and environment support

  - Add distributed processing configuration variables to ConfigManager pattern
  - Support environment-specific batch sizes, timeout values, and retry limits
  - Create configuration validation for required database connections
  - Add configuration examples for development, staging, and production environments
  - Write unit tests for configuration loading and validation with various environment scenarios
  - _Requirements: 11.1, 11.2, 11.4, 11.5_

- [x] 15. Create comprehensive test suite

  - Write unit tests for DistributedProcessor class with mocked DatabaseManager instances
  - Create integration tests for multi-container scenarios using test databases
  - Implement concurrent processing tests to verify no duplicate record processing
  - Add performance tests for batch processing and connection pool utilization
  - Create chaos tests for container failures and database connectivity issues
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 8.3, 8.4_

- [x] 16. Add monitoring and operational utilities

  - Create database health check task that can be used across multiple flows
  - Implement queue monitoring utilities for operational visibility into processing status
  - Add diagnostic utilities for troubleshooting processing issues and orphaned records
  - Create performance monitoring task for tracking processing rates and error rates
  - Write operational runbook with troubleshooting guides and maintenance procedures
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 17. Create documentation and examples

  - Write comprehensive README for distributed processing system setup and usage
  - Create migration guide for converting existing flows to distributed processing
  - Add troubleshooting guide for common issues and performance optimization
  - Create operational runbook for production deployment and maintenance
  - Write API documentation for DistributedProcessor class and flow template usage
  - _Requirements: 11.3, 11.4, 11.5_

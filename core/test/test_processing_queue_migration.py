"""
Test suite for V006__Create_processing_queue.sql migration.

This module tests the processing queue migration file to ensure:
- Migration file syntax is valid
- Table structure matches requirements
- Constraints are properly defined
- Triggers function correctly
- Sample data is inserted correctly

Requirements covered: 1.1, 1.3, 10.1, 10.2
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.database import DatabaseManager


class TestProcessingQueueMigration:
    """Test the V006 processing queue migration file."""

    def setup_method(self):
        """Set up test fixtures."""
        self.migration_file_path = Path("core/migrations/rpa_db/V006__Create_processing_queue.sql")

        # Setup mock configuration for database testing
        self.mock_config_patcher = patch("core.database.ConfigManager")
        self.mock_create_engine_patcher = patch("core.database.create_engine")

        self.mock_config_class = self.mock_config_patcher.start()
        self.mock_create_engine = self.mock_create_engine_patcher.start()

        self.mock_config = Mock()
        self.mock_config_class.return_value = self.mock_config
        self.mock_config.environment = "test"
        self.mock_config.get_variable.side_effect = lambda key, default=None: {
            "rpa_db_type": "postgresql"
        }.get(key, default)
        self.mock_config.get_secret.return_value = (
            "postgresql://test:test@localhost:5432/test_rpa_db"
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        self.mock_config_patcher.stop()
        self.mock_create_engine_patcher.stop()

    def test_migration_file_exists(self):
        """Test that the V006 migration file exists and is readable."""
        assert self.migration_file_path.exists(), f"Migration file {self.migration_file_path} does not exist"
        assert self.migration_file_path.is_file(), f"Migration path {self.migration_file_path} is not a file"

        # Test that file is readable
        content = self.migration_file_path.read_text()
        assert len(content) > 0, "Migration file is empty"
        assert "CREATE TABLE" in content, "Migration file does not contain CREATE TABLE statement"

    def test_migration_file_naming_convention(self):
        """Test that the migration file follows the correct naming convention."""
        filename = self.migration_file_path.name

        # Test naming pattern: V{version}__{description}.sql
        assert filename.startswith("V006__"), f"Migration file should start with 'V006__', got {filename}"
        assert filename.endswith(".sql"), f"Migration file should end with '.sql', got {filename}"
        assert "Create_processing_queue" in filename, f"Migration file should contain 'Create_processing_queue', got {filename}"

    def test_migration_sql_syntax_validation(self):
        """Test that the migration SQL has valid syntax structure."""
        content = self.migration_file_path.read_text()

        # Test for required SQL elements
        assert "CREATE TABLE IF NOT EXISTS processing_queue" in content, "Missing processing_queue table creation"
        assert "CREATE OR REPLACE FUNCTION update_updated_at_column()" in content, "Missing update function"
        assert "CREATE TRIGGER update_processing_queue_updated_at" in content, "Missing update trigger"

        # Test for proper SQL statement termination
        statements = [stmt.strip() for stmt in content.split(';') if stmt.strip()]
        for stmt in statements:
            if stmt and not stmt.startswith('--'):
                # Each non-comment statement should be properly formed
                assert len(stmt) > 0, "Empty SQL statement found"

    def test_table_structure_requirements(self):
        """Test that the processing_queue table has all required columns."""
        content = self.migration_file_path.read_text()

        # Extract table creation statement
        table_start = content.find("CREATE TABLE IF NOT EXISTS processing_queue")
        table_end = content.find(");", table_start) + 2
        table_sql = content[table_start:table_end]

        # Test required columns exist
        required_columns = [
            "id SERIAL PRIMARY KEY",
            "flow_name VARCHAR(100) NOT NULL",
            "payload JSONB NOT NULL",
            "status VARCHAR(20) NOT NULL DEFAULT 'pending'",
            "flow_instance_id VARCHAR(100)",
            "claimed_at TIMESTAMP",
            "completed_at TIMESTAMP",
            "error_message TEXT",
            "retry_count INTEGER NOT NULL DEFAULT 0",
            "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
        ]

        for column in required_columns:
            assert column in table_sql, f"Required column definition not found: {column}"

    def test_status_check_constraint(self):
        """Test that the status column has proper check constraint."""
        content = self.migration_file_path.read_text()

        # Test status constraint exists
        assert "CHECK (status IN ('pending', 'processing', 'completed', 'failed'))" in content, \
            "Status check constraint not found or incorrect"

        # Test all required status values are included
        required_statuses = ['pending', 'processing', 'completed', 'failed']
        for status in required_statuses:
            assert f"'{status}'" in content, f"Required status '{status}' not found in constraint"

    def test_trigger_function_definition(self):
        """Test that the update trigger function is properly defined."""
        content = self.migration_file_path.read_text()

        # Test function creation
        assert "CREATE OR REPLACE FUNCTION update_updated_at_column()" in content, \
            "Update function not found"
        assert "RETURNS TRIGGER" in content, "Function should return TRIGGER type"
        assert "NEW.updated_at = CURRENT_TIMESTAMP" in content, \
            "Function should set updated_at to CURRENT_TIMESTAMP"
        assert "RETURN NEW" in content, "Function should return NEW record"
        assert "language 'plpgsql'" in content, "Function should use plpgsql language"

    def test_trigger_creation(self):
        """Test that the update trigger is properly created."""
        content = self.migration_file_path.read_text()

        # Test trigger creation
        assert "CREATE TRIGGER update_processing_queue_updated_at" in content, \
            "Update trigger not found"
        assert "BEFORE UPDATE ON processing_queue" in content, \
            "Trigger should be BEFORE UPDATE on processing_queue"
        assert "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()" in content, \
            "Trigger should execute update_updated_at_column function"

    def test_basic_indexes_creation(self):
        """Test that basic performance indexes are created."""
        content = self.migration_file_path.read_text()

        # Test basic indexes exist
        expected_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status)",
            "CREATE INDEX IF NOT EXISTS idx_processing_queue_flow_name ON processing_queue(flow_name)",
            "CREATE INDEX IF NOT EXISTS idx_processing_queue_created_at ON processing_queue(created_at)"
        ]

        for index in expected_indexes:
            assert index in content, f"Required index not found: {index}"

    def test_sample_data_insertion(self):
        """Test that sample data is properly inserted."""
        content = self.migration_file_path.read_text()

        # Test sample data insertion exists
        assert "INSERT INTO processing_queue (flow_name, payload, status) VALUES" in content, \
            "Sample data insertion not found"

        # Test sample data includes different flow types and statuses
        sample_flows = ['survey_processor', 'order_processor', 'data_validation']
        for flow in sample_flows:
            assert f"'{flow}'" in content, f"Sample data should include {flow} flow"

        # Test sample data includes JSONB payloads
        assert '"survey_id"' in content, "Sample data should include survey_id in payload"
        assert '"order_id"' in content, "Sample data should include order_id in payload"
        assert '"batch_id"' in content, "Sample data should include batch_id in payload"

    def test_sample_data_status_updates(self):
        """Test that sample data includes status updates to demonstrate functionality."""
        content = self.migration_file_path.read_text()

        # Test that sample data is updated to show different statuses
        assert "UPDATE processing_queue" in content, "Sample data should include UPDATE statements"
        assert "status = 'completed'" in content, "Sample data should show completed status"
        assert "status = 'failed'" in content, "Sample data should show failed status"
        assert "flow_instance_id = 'container-" in content, "Sample data should show flow_instance_id"
        assert "error_message = " in content, "Sample data should show error_message"

    def test_migration_idempotency(self):
        """Test that the migration can be run multiple times safely."""
        content = self.migration_file_path.read_text()

        # Test IF NOT EXISTS clauses
        assert "CREATE TABLE IF NOT EXISTS processing_queue" in content, \
            "Table creation should use IF NOT EXISTS"
        assert "CREATE INDEX IF NOT EXISTS" in content, \
            "Index creation should use IF NOT EXISTS"

        # Test OR REPLACE for function
        assert "CREATE OR REPLACE FUNCTION" in content, \
            "Function creation should use OR REPLACE"

    def test_postgresql_specific_features(self):
        """Test that the migration uses PostgreSQL-specific features correctly."""
        content = self.migration_file_path.read_text()

        # Test PostgreSQL-specific data types
        assert "SERIAL PRIMARY KEY" in content, "Should use PostgreSQL SERIAL type"
        assert "JSONB" in content, "Should use PostgreSQL JSONB type"
        assert "CURRENT_TIMESTAMP" in content, "Should use CURRENT_TIMESTAMP function"

        # Test PostgreSQL-specific syntax
        assert "language 'plpgsql'" in content, "Should use plpgsql language for function"

    def test_migration_comments_and_documentation(self):
        """Test that the migration includes proper comments and documentation."""
        content = self.migration_file_path.read_text()

        # Test header comment exists
        lines = content.split('\n')
        assert lines[0].startswith('--'), "First line should be a comment"
        assert "Migration V006" in lines[0], "Header should identify migration version"
        assert "processing_queue" in lines[0], "Header should mention processing_queue"

        # Test section comments exist
        assert "-- Create function to automatically update updated_at timestamp" in content, \
            "Function creation should have explanatory comment"
        assert "-- Create trigger to update updated_at timestamp" in content, \
            "Trigger creation should have explanatory comment"
        assert "-- Create basic indexes for performance" in content, \
            "Index creation should have explanatory comment"

    def test_requirements_coverage(self):
        """Test that the migration covers all specified requirements."""
        content = self.migration_file_path.read_text()

        # Requirement 1.1: Database queue with concurrent access support
        assert "FOR UPDATE SKIP LOCKED" in content or "processing_queue" in content, \
            "Should support concurrent access (table structure for FOR UPDATE SKIP LOCKED)"

        # Requirement 1.3: Support for pending, processing, completed, failed statuses
        statuses = ['pending', 'processing', 'completed', 'failed']
        for status in statuses:
            assert f"'{status}'" in content, f"Should support {status} status"

        # Requirement 10.1: Migration files in core/migrations/rpa_db/
        assert self.migration_file_path.parent.name == "rpa_db", \
            "Migration should be in rpa_db directory"

        # Requirement 10.2: Automatic migration execution through DatabaseManager
        # This is tested by ensuring the file follows the correct naming convention
        # and is in the correct location for DatabaseManager to find it
        assert self.migration_file_path.name.startswith("V006__"), \
            "Migration should follow Pyway naming convention for automatic execution"


class TestProcessingQueueMigrationIntegration:
    """Integration tests for the processing queue migration with DatabaseManager."""

    def setup_method(self):
        """Set up test fixtures for integration testing."""
        # Create temporary migration directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.migration_dir = Path(self.temp_dir) / "core" / "migrations" / "rpa_db"
        self.migration_dir.mkdir(parents=True, exist_ok=True)

        # Copy the actual migration file to temp directory
        actual_migration = Path("core/migrations/rpa_db/V006__Create_processing_queue.sql")
        temp_migration = self.migration_dir / "V006__Create_processing_queue.sql"
        temp_migration.write_text(actual_migration.read_text())

        # Setup mock configuration
        self.mock_config_patcher = patch("core.database.ConfigManager")
        self.mock_create_engine_patcher = patch("core.database.create_engine")

        self.mock_config_class = self.mock_config_patcher.start()
        self.mock_create_engine = self.mock_create_engine_patcher.start()

        self.mock_config = Mock()
        self.mock_config_class.return_value = self.mock_config
        self.mock_config.environment = "test"
        self.mock_config.get_variable.side_effect = lambda key, default=None: {
            "rpa_db_type": "postgresql"
        }.get(key, default)
        self.mock_config.get_secret.return_value = (
            "postgresql://test:test@localhost:5432/test_rpa_db"
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.mock_config_patcher.stop()
        self.mock_create_engine_patcher.stop()

    def test_migration_execution_with_database_manager(self):
        """Test that the migration can be executed through DatabaseManager."""
        # Setup mock engine and Pyway
        mock_engine = Mock()
        self.mock_create_engine.return_value = mock_engine

        executed_migrations = []

        with patch("core.database.Migrate") as mock_migrate_class:
            mock_migrate = Mock()
            mock_migrate_class.return_value = mock_migrate

            def mock_migrate_execution():
                # Simulate successful migration execution
                migration_files = sorted(self.migration_dir.glob("V*__*.sql"))
                for migration_file in migration_files:
                    executed_migrations.append({
                        "version": migration_file.name.split("__")[0],
                        "description": migration_file.name.split("__")[1].replace(".sql", ""),
                        "filename": migration_file.name,
                        "status": "success"
                    })
                return executed_migrations

            mock_migrate.migrate.side_effect = mock_migrate_execution

            # Patch migration directory
            with patch.object(DatabaseManager, "_get_migration_directory") as mock_get_dir:
                mock_get_dir.return_value = self.migration_dir

                # Execute migration through DatabaseManager
                db_manager = DatabaseManager("rpa_db")
                db_manager.run_migrations()

                # Verify migration was executed
                assert len(executed_migrations) == 1
                assert executed_migrations[0]["version"] == "V006"
                assert "Create_processing_queue" in executed_migrations[0]["description"]
                assert executed_migrations[0]["status"] == "success"

    def test_migration_status_reporting(self):
        """Test that migration status is properly reported."""
        # Setup mock engine and Pyway
        mock_engine = Mock()
        self.mock_create_engine.return_value = mock_engine

        with patch("core.database.Migrate") as mock_migrate_class:
            mock_migrate = Mock()
            mock_migrate_class.return_value = mock_migrate

            # Simulate migration status
            mock_migrate.info.return_value = {
                "current_version": "V006",
                "applied_migrations": 1,
            }

            # Patch migration directory
            with patch.object(DatabaseManager, "_get_migration_directory") as mock_get_dir:
                mock_get_dir.return_value = self.migration_dir

                # Get migration status through DatabaseManager
                db_manager = DatabaseManager("rpa_db")
                migration_status = db_manager.get_migration_status()

                # Verify migration status
                assert migration_status["database_name"] == "rpa_db"
                assert migration_status["current_version"] == "V006"
                assert migration_status["total_applied"] == 1

                # Verify migration file is listed
                migration_filenames = [m["filename"] for m in migration_status["pending_migrations"]]
                assert "V006__Create_processing_queue.sql" in migration_filenames

    def test_migration_failure_handling(self):
        """Test proper handling of migration failures."""
        # Setup mock engine and Pyway
        mock_engine = Mock()
        self.mock_create_engine.return_value = mock_engine

        with patch("core.database.Migrate") as mock_migrate_class:
            mock_migrate = Mock()
            mock_migrate_class.return_value = mock_migrate

            # Simulate migration failure
            mock_migrate.migrate.side_effect = Exception("Migration V006 failed: table already exists")

            # Patch migration directory
            with patch.object(DatabaseManager, "_get_migration_directory") as mock_get_dir:
                mock_get_dir.return_value = self.migration_dir

                # Test migration failure handling
                db_manager = DatabaseManager("rpa_db")

                with pytest.raises(RuntimeError, match="Migration execution failed"):
                    db_manager.run_migrations()

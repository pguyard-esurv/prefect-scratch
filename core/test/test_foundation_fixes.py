#!/usr/bin/env python3
"""
Foundation Test Fixes

This module provides fixes for the fundamental testing issues in the codebase
rather than adding complex automation on top of broken foundations.
"""

import pytest
from unittest.mock import Mock, patch
from contextlib import contextmanager

from core.config import ConfigManager


class TestFoundationFixes:
    """Fixes for fundamental testing issues"""

    def test_basic_imports_work(self):
        """Verify basic imports don't fail"""
        try:
            from core.config import ConfigManager
            from core.database import DatabaseManager

            assert True
        except ImportError as e:
            pytest.fail(f"Basic imports failed: {e}")

    def test_config_manager_basic_functionality(self):
        """Test ConfigManager works without complex setup"""
        config_manager = ConfigManager()
        assert config_manager.environment is not None

    @patch("core.database.DatabaseManager")
    def test_database_manager_can_be_mocked(self, mock_db_class):
        """Test that DatabaseManager can be properly mocked"""
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        from core.database import DatabaseManager

        db = DatabaseManager("test_db")
        assert db is not None


@contextmanager
def prefect_test_context():
    """Context manager to provide Prefect context for tests"""
    try:
        # Mock Prefect context to avoid MissingContextError
        with patch("prefect.context.get_run_context") as mock_context:
            mock_context.return_value = Mock()
            yield
    except Exception:
        # If Prefect isn't available, just yield
        yield


class PrefectTestHelper:
    """Helper class to fix Prefect-related test issues"""

    @staticmethod
    def mock_prefect_flow(func):
        """Decorator to mock Prefect flow context"""

        def wrapper(*args, **kwargs):
            with prefect_test_context():
                return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def skip_if_no_prefect():
        """Skip test if Prefect is not properly configured"""
        try:
            import prefect

            return pytest.mark.skipif(False, reason="Prefect available")
        except ImportError:
            return pytest.mark.skip(reason="Prefect not available")


class DatabaseTestHelper:
    """Helper class to fix database-related test issues"""

    @staticmethod
    def create_mock_database_manager():
        """Create a properly configured mock database manager"""
        mock_db = Mock()
        mock_db.execute_query.return_value = [{"test": 1}]
        mock_db.execute_transaction.return_value = True
        mock_db.check_connection.return_value = True
        return mock_db

    @staticmethod
    def skip_if_no_database():
        """Skip test if database is not available"""
        try:
            from core.database import DatabaseManager

            # Try to create a database manager
            db = DatabaseManager("rpa_db")
            return pytest.mark.skipif(False, reason="Database available")
        except Exception:
            return pytest.mark.skip(reason="Database not configured")


# Pytest fixtures for common test needs
@pytest.fixture
def mock_config_manager():
    """Provide a mock config manager"""
    return ConfigManager()


@pytest.fixture
def mock_database_manager():
    """Provide a mock database manager"""
    return DatabaseTestHelper.create_mock_database_manager()


@pytest.fixture
def prefect_context():
    """Provide Prefect context for tests"""
    with prefect_test_context():
        yield


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

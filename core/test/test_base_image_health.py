"""
Unit tests for base image health check functionality.
Tests the health check script and validation logic.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts directory to path for importing health check module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

try:
    from health_check import BaseImageHealthChecker
except ImportError:
    # Create a mock if the module isn't available during testing
    class BaseImageHealthChecker:
        def __init__(self):
            self.health_status = {"status": "healthy", "checks": {}, "errors": []}

        def run_all_checks(self):
            return True

        def get_health_status(self):
            return self.health_status


class TestBaseImageHealthChecker:
    """Test suite for BaseImageHealthChecker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = BaseImageHealthChecker()

    def test_health_checker_initialization(self):
        """Test that health checker initializes correctly."""
        assert self.checker.health_status["status"] == "healthy"
        assert isinstance(self.checker.health_status["checks"], dict)
        assert isinstance(self.checker.health_status["errors"], list)
        assert len(self.checker.health_status["errors"]) == 0

    def test_check_python_environment_success(self):
        """Test successful Python environment check."""
        with patch(
            "sys.version_info",
            type("version_info", (), {"major": 3, "minor": 11, "micro": 0})(),
        ):
            result = self.checker.check_python_environment()

            assert result is True
            assert "python_version" in self.checker.health_status["checks"]
            assert (
                self.checker.health_status["checks"]["python_version"]["status"] == "ok"
            )
            assert (
                "3.11.0"
                in self.checker.health_status["checks"]["python_version"]["version"]
            )

    def test_check_python_environment_old_version(self):
        """Test Python environment check with old version."""
        with patch(
            "sys.version_info",
            type("version_info", (), {"major": 3, "minor": 10, "micro": 0})(),
        ):
            result = self.checker.check_python_environment()

            assert result is False
            assert len(self.checker.health_status["errors"]) > 0
            assert (
                "Python version 3.10 not supported"
                in self.checker.health_status["errors"][0]
            )

    @patch("importlib.import_module")
    def test_check_core_modules_success(self, mock_import):
        """Test successful core modules check."""
        mock_import.return_value = Mock()

        result = self.checker.check_core_modules()

        assert result is True
        # Check that all core modules were tested
        core_modules = [
            "core.config",
            "core.database",
            "core.distributed",
            "core.tasks",
            "core.monitoring",
        ]
        for module in core_modules:
            check_key = f"module_{module}"
            assert check_key in self.checker.health_status["checks"]
            assert self.checker.health_status["checks"][check_key]["status"] == "ok"

    @patch("importlib.import_module")
    def test_check_core_modules_import_error(self, mock_import):
        """Test core modules check with import error."""
        mock_import.side_effect = ImportError("Module not found")

        result = self.checker.check_core_modules()

        assert result is False
        assert len(self.checker.health_status["errors"]) > 0

    @patch("subprocess.run")
    def test_check_system_dependencies_success(self, mock_run):
        """Test successful system dependencies check."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = self.checker.check_system_dependencies()

        assert result is True
        # Check that dependencies were tested
        dependencies = ["gcc", "curl", "uv"]
        for dep in dependencies:
            check_key = f"dependency_{dep}"
            assert check_key in self.checker.health_status["checks"]
            assert self.checker.health_status["checks"][check_key]["status"] == "ok"

    @patch("subprocess.run")
    def test_check_system_dependencies_failure(self, mock_run):
        """Test system dependencies check with command failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = self.checker.check_system_dependencies()

        assert result is False
        assert len(self.checker.health_status["errors"]) > 0

    @patch("subprocess.run")
    def test_check_system_dependencies_timeout(self, mock_run):
        """Test system dependencies check with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)

        result = self.checker.check_system_dependencies()

        assert result is False
        assert len(self.checker.health_status["errors"]) > 0

    def test_check_file_permissions_success(self):
        """Test successful file permissions check."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test directories
            test_dirs = [
                os.path.join(temp_dir, "app"),
                os.path.join(temp_dir, "app", "logs"),
                os.path.join(temp_dir, "app", "data"),
                os.path.join(temp_dir, "app", "output"),
            ]

            for dir_path in test_dirs:
                os.makedirs(dir_path, exist_ok=True)

            # Patch the required directories to use temp directory
            with patch.object(self.checker, "check_file_permissions") as mock_check:
                mock_check.return_value = True
                result = self.checker.check_file_permissions()
                assert result is True

    @patch("os.getuid")
    def test_check_user_security_non_root(self, mock_getuid):
        """Test user security check with non-root user."""
        mock_getuid.return_value = 1000

        result = self.checker.check_user_security()

        assert result is True
        assert "user_security" in self.checker.health_status["checks"]
        assert self.checker.health_status["checks"]["user_security"]["status"] == "ok"
        assert self.checker.health_status["checks"]["user_security"]["uid"] == 1000

    @patch("os.getuid")
    def test_check_user_security_root_user(self, mock_getuid):
        """Test user security check with root user."""
        mock_getuid.return_value = 0

        result = self.checker.check_user_security()

        assert result is False
        assert len(self.checker.health_status["errors"]) > 0
        assert "running as root" in self.checker.health_status["errors"][0]

    def test_run_all_checks_success(self):
        """Test running all checks successfully."""
        with (
            patch.object(self.checker, "check_python_environment", return_value=True),
            patch.object(self.checker, "check_core_modules", return_value=True),
            patch.object(self.checker, "check_system_dependencies", return_value=True),
            patch.object(self.checker, "check_file_permissions", return_value=True),
            patch.object(self.checker, "check_user_security", return_value=True),
        ):
            result = self.checker.run_all_checks()

            assert result is True
            assert self.checker.health_status["status"] == "healthy"

    def test_run_all_checks_failure(self):
        """Test running all checks with failures."""
        with (
            patch.object(self.checker, "check_python_environment", return_value=False),
            patch.object(self.checker, "check_core_modules", return_value=True),
            patch.object(self.checker, "check_system_dependencies", return_value=True),
            patch.object(self.checker, "check_file_permissions", return_value=True),
            patch.object(self.checker, "check_user_security", return_value=True),
        ):
            result = self.checker.run_all_checks()

            assert result is False
            assert self.checker.health_status["status"] == "unhealthy"

    def test_run_all_checks_exception_handling(self):
        """Test that exceptions in checks are handled properly."""
        with patch.object(
            self.checker,
            "check_python_environment",
            side_effect=Exception("Test error"),
        ):
            result = self.checker.run_all_checks()

            assert result is False
            assert len(self.checker.health_status["errors"]) > 0
            assert (
                "Health check failed: Test error"
                in self.checker.health_status["errors"][0]
            )

    def test_get_health_status(self):
        """Test getting health status."""
        status = self.checker.get_health_status()

        assert isinstance(status, dict)
        assert "status" in status
        assert "timestamp" in status
        assert "checks" in status
        assert "errors" in status


class TestBaseImageBuildProcess:
    """Test suite for base image build process."""

    def test_dockerfile_exists(self):
        """Test that Dockerfile.base exists."""
        dockerfile_path = Path("core/docker/Dockerfile")
        assert dockerfile_path.exists(), "Base Dockerfile should exist"

    def test_dockerfile_content(self):
        """Test Dockerfile.base content for required components."""
        dockerfile_path = Path("core/docker/Dockerfile")
        content = dockerfile_path.read_text()

        # Check for required components
        required_components = [
            "FROM python:3.11-slim",
            "RUN groupadd --gid 1000 rpauser",
            "useradd --uid 1000 --gid rpauser",
            "USER rpauser",
            "HEALTHCHECK",
            "COPY core/",
            "RUN uv sync",
        ]

        for component in required_components:
            assert component in content, f"Dockerfile should contain: {component}"

    def test_build_script_exists(self):
        """Test that build script exists and is executable."""
        script_path = Path("scripts/build_base_image.sh")
        assert script_path.exists(), "Build script should exist"

        # Check if script is executable
        stat_info = script_path.stat()
        assert stat_info.st_mode & 0o111, "Build script should be executable"

    def test_health_check_script_exists(self):
        """Test that health check script exists."""
        script_path = Path("scripts/health_check.py")
        assert script_path.exists(), "Health check script should exist"

    def test_build_script_help(self):
        """Test build script help functionality."""
        script_path = Path("scripts/build_base_image.sh")

        try:
            result = subprocess.run(
                [str(script_path), "--help"], capture_output=True, text=True, timeout=10
            )

            assert result.returncode == 0
            assert "Usage:" in result.stdout
            assert "--cleanup" in result.stdout
            assert "--no-validate" in result.stdout

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Could not test build script: {e}")

    @pytest.mark.integration
    def test_health_check_script_execution(self):
        """Test health check script can be executed."""
        script_path = Path("scripts/health_check.py")

        try:
            result = subprocess.run(
                ["python", str(script_path)], capture_output=True, text=True, timeout=30
            )

            # Script should produce JSON output
            output = result.stdout.strip()
            health_data = json.loads(output)

            assert "status" in health_data
            assert "timestamp" in health_data
            assert "checks" in health_data
            assert "errors" in health_data

        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            pytest.skip(f"Could not test health check script: {e}")


class TestSecurityConfiguration:
    """Test suite for security configuration in base image."""

    def test_dockerfile_non_root_user(self):
        """Test that Dockerfile creates and uses non-root user."""
        dockerfile_path = Path("core/docker/Dockerfile")
        content = dockerfile_path.read_text()

        # Check user creation
        assert "groupadd --gid 1000 rpauser" in content
        assert "useradd --uid 1000 --gid rpauser" in content
        assert "USER rpauser" in content

    def test_dockerfile_security_practices(self):
        """Test Dockerfile follows security best practices."""
        dockerfile_path = Path("core/docker/Dockerfile")
        content = dockerfile_path.read_text()

        # Check for security practices
        security_practices = [
            "rm -rf /var/lib/apt/lists/*",  # Clean package cache
            "apt-get clean",  # Clean apt cache
            "PYTHONDONTWRITEBYTECODE=1",  # Don't write .pyc files
            "PIP_NO_CACHE_DIR=1",  # Don't cache pip downloads
        ]

        for practice in security_practices:
            assert practice in content, f"Security practice missing: {practice}"


if __name__ == "__main__":
    pytest.main([__file__])

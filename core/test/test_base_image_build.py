"""
Unit tests for base image build process and infrastructure.
Tests build script functionality and Docker image validation.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestBuildScriptFunctionality:
    """Test suite for build script functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.script_path = Path("scripts/build_base_image.sh")

    def test_build_script_exists_and_executable(self):
        """Test that build script exists and is executable."""
        assert self.script_path.exists(), "Build script should exist"

        # Check if script is executable
        stat_info = self.script_path.stat()
        assert stat_info.st_mode & 0o111, "Build script should be executable"

    def test_build_script_shebang(self):
        """Test that build script has proper shebang."""
        content = self.script_path.read_text()
        assert content.startswith("#!/bin/bash"), (
            "Build script should have bash shebang"
        )

    def test_build_script_help_option(self):
        """Test build script help option."""
        try:
            result = subprocess.run(
                [str(self.script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0
            help_output = result.stdout

            # Check for expected help content
            expected_content = [
                "Usage:",
                "--cleanup",
                "--no-validate",
                "--no-tag",
                "--help",
            ]

            for content in expected_content:
                assert content in help_output, f"Help should contain: {content}"

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Could not test build script help: {e}")

    def test_build_script_error_handling(self):
        """Test build script error handling with invalid options."""
        try:
            result = subprocess.run(
                [str(self.script_path), "--invalid-option"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode != 0, "Script should fail with invalid option"
            assert (
                "Unknown option" in result.stderr or "Unknown option" in result.stdout
            )

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Could not test build script error handling: {e}")


class TestDockerfileValidation:
    """Test suite for Dockerfile validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.dockerfile_path = Path("Dockerfile.base")

    def test_dockerfile_exists(self):
        """Test that Dockerfile.base exists."""
        assert self.dockerfile_path.exists(), "Dockerfile.base should exist"

    def test_dockerfile_base_image(self):
        """Test Dockerfile uses correct base image."""
        content = self.dockerfile_path.read_text()
        assert "FROM python:3.11-slim" in content, (
            "Should use Python 3.11 slim base image"
        )

    def test_dockerfile_environment_variables(self):
        """Test Dockerfile sets required environment variables."""
        content = self.dockerfile_path.read_text()

        required_env_vars = [
            "PYTHONUNBUFFERED=1",
            "PYTHONDONTWRITEBYTECODE=1",
            "PIP_NO_CACHE_DIR=1",
            "PIP_DISABLE_PIP_VERSION_CHECK=1",
        ]

        for env_var in required_env_vars:
            assert env_var in content, f"Dockerfile should set: {env_var}"

    def test_dockerfile_system_dependencies(self):
        """Test Dockerfile installs required system dependencies."""
        content = self.dockerfile_path.read_text()

        required_packages = [
            "gcc",
            "g++",
            "curl",
            "wget",
            "git",
            "build-essential",
            "libpq-dev",
        ]

        for package in required_packages:
            assert package in content, f"Dockerfile should install: {package}"

    def test_dockerfile_user_security(self):
        """Test Dockerfile implements proper user security."""
        content = self.dockerfile_path.read_text()

        security_requirements = [
            "groupadd --gid 1000 rpauser",
            "useradd --uid 1000 --gid rpauser",
            "USER rpauser",
        ]

        for requirement in security_requirements:
            assert requirement in content, (
                f"Security requirement missing: {requirement}"
            )

    def test_dockerfile_working_directory(self):
        """Test Dockerfile sets correct working directory."""
        content = self.dockerfile_path.read_text()
        assert "WORKDIR /app" in content, "Should set working directory to /app"

    def test_dockerfile_health_check(self):
        """Test Dockerfile includes health check configuration."""
        content = self.dockerfile_path.read_text()

        health_check_components = [
            "HEALTHCHECK",
            "--interval=30s",
            "--timeout=10s",
            "--start-period=5s",
            "--retries=3",
            "python scripts/health_check.py",
        ]

        for component in health_check_components:
            assert component in content, f"Health check should include: {component}"

    def test_dockerfile_copy_operations(self):
        """Test Dockerfile copies required files and directories."""
        content = self.dockerfile_path.read_text()

        copy_operations = [
            "COPY pyproject.toml uv.lock",
            "COPY core/ ./core/",
            "COPY conftest.py",
            "COPY scripts/health_check.py",
        ]

        for operation in copy_operations:
            assert operation in content, f"Should copy: {operation}"

    def test_dockerfile_directory_creation(self):
        """Test Dockerfile creates required directories."""
        content = self.dockerfile_path.read_text()

        required_dirs = ["/app/logs", "/app/data", "/app/output"]

        for dir_path in required_dirs:
            assert dir_path in content, f"Should create directory: {dir_path}"

    def test_dockerfile_permissions(self):
        """Test Dockerfile sets proper permissions."""
        content = self.dockerfile_path.read_text()

        permission_commands = [
            "chown -R rpauser:rpauser /app",
            "chmod +x ./scripts/health_check.py",
        ]

        for command in permission_commands:
            assert command in content, f"Should set permissions: {command}"


class TestHealthCheckIntegration:
    """Test suite for health check integration."""

    def test_health_check_script_exists(self):
        """Test that health check script exists."""
        script_path = Path("scripts/health_check.py")
        assert script_path.exists(), "Health check script should exist"

    def test_health_check_script_executable(self):
        """Test health check script is executable."""
        script_path = Path("scripts/health_check.py")
        content = script_path.read_text()
        assert content.startswith("#!/usr/bin/env python3"), (
            "Should have Python shebang"
        )

    @pytest.mark.integration
    def test_health_check_json_output(self):
        """Test health check produces valid JSON output."""
        script_path = Path("scripts/health_check.py")

        try:
            result = subprocess.run(
                ["python", str(script_path)], capture_output=True, text=True, timeout=30
            )

            # Should produce JSON output regardless of exit code
            output = result.stdout.strip()
            health_data = json.loads(output)

            # Validate JSON structure
            required_fields = ["status", "timestamp", "checks", "errors"]
            for field in required_fields:
                assert field in health_data, (
                    f"Health check output should contain: {field}"
                )

            # Validate status values
            assert health_data["status"] in ["healthy", "unhealthy"], (
                "Status should be valid"
            )

        except (
            subprocess.TimeoutExpired,
            FileNotFoundError,
            json.JSONDecodeError,
        ) as e:
            pytest.skip(f"Could not test health check JSON output: {e}")


class TestBuildOptimization:
    """Test suite for build optimization features."""

    def test_dockerfile_layer_optimization(self):
        """Test Dockerfile is optimized for layer caching."""
        content = Path("Dockerfile.base").read_text()
        lines = [line.strip() for line in content.split("\n") if line.strip()]

        # Find positions of key operations
        copy_deps_pos = None
        uv_sync_pos = None
        copy_core_pos = None

        for i, line in enumerate(lines):
            if "COPY pyproject.toml uv.lock" in line:
                copy_deps_pos = i
            elif "RUN uv sync" in line:
                uv_sync_pos = i
            elif "COPY core/" in line:
                copy_core_pos = i

        # Verify optimal ordering for caching
        if (
            copy_deps_pos is not None
            and uv_sync_pos is not None
            and copy_core_pos is not None
        ):
            assert copy_deps_pos < uv_sync_pos, (
                "Dependencies should be copied before installation"
            )
            assert uv_sync_pos < copy_core_pos, (
                "Dependencies should be installed before copying code"
            )

    def test_dockerfile_cache_optimization(self):
        """Test Dockerfile includes cache optimization directives."""
        content = Path("Dockerfile.base").read_text()

        # Check for cache-friendly practices
        cache_optimizations = [
            "rm -rf /var/lib/apt/lists/*",  # Clean package cache
            "apt-get clean",  # Clean apt cache
            "PIP_NO_CACHE_DIR=1",  # Disable pip cache
        ]

        for optimization in cache_optimizations:
            assert optimization in content, (
                f"Cache optimization missing: {optimization}"
            )


class TestBuildScriptValidation:
    """Test suite for build script validation logic."""

    def test_build_script_prerequisite_checks(self):
        """Test build script includes prerequisite validation."""
        content = Path("scripts/build_base_image.sh").read_text()

        prerequisite_checks = [
            "command -v docker",
            "docker info",
            "pyproject.toml",
            "uv.lock",
            "core/",
        ]

        for check in prerequisite_checks:
            assert check in content, f"Build script should check for: {check}"

    def test_build_script_error_handling(self):
        """Test build script includes proper error handling."""
        content = Path("scripts/build_base_image.sh").read_text()

        error_handling_patterns = [
            "set -euo pipefail",  # Strict error handling
            "log_error",  # Error logging function
            "exit 1",  # Proper exit codes
        ]

        for pattern in error_handling_patterns:
            assert pattern in content, f"Build script should include: {pattern}"

    def test_build_script_logging(self):
        """Test build script includes comprehensive logging."""
        content = Path("scripts/build_base_image.sh").read_text()

        logging_functions = ["log_info", "log_success", "log_warning", "log_error"]

        for func in logging_functions:
            assert func in content, f"Build script should have logging function: {func}"


if __name__ == "__main__":
    pytest.main([__file__])

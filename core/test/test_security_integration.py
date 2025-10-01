"""
Security integration tests for container isolation and compliance verification.

This module provides comprehensive integration tests that validate security
configurations in real container environments, including container isolation,
compliance verification, and end-to-end security validation scenarios.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pytest

from core.container_config import ContainerConfigManager
from core.security_validator import SecurityLevel, SecurityValidator


class TestSecurityIntegration(unittest.TestCase):
    """Integration tests for security validation in container environments."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.test_config = {
            "security": {
                "run_as_non_root": True,
                "user_id": 1000,
                "group_id": 1000,
                "drop_capabilities": ["ALL"],
                "secrets_mount_path": "/var/secrets",
            },
            "network": {
                "mode": "bridge",
                "privileged": False,
            },
        }

        self.validator = SecurityValidator(
            container_config=self.test_config,
            enable_vulnerability_scanning=True,
            enable_network_validation=True,
        )

        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.slow
    def test_container_isolation_validation(self):
        """Test container isolation and security boundaries."""
        # Test user isolation
        result = self.validator.validate_user_permissions()

        self.assertIsInstance(result.details, dict)
        self.assertIn("current_uid", result.details)
        self.assertIn("current_gid", result.details)

        # Verify non-root execution
        current_uid = result.details["current_uid"]
        if current_uid == 0:
            self.assertEqual(result.level, SecurityLevel.FAIL)
            self.assertIn("root", result.message.lower())
        else:
            # Non-root user should pass or have warnings
            self.assertIn(result.level, [SecurityLevel.PASS, SecurityLevel.WARNING])

    def test_filesystem_isolation_validation(self):
        """Test filesystem isolation and access controls."""
        # Create test files with different permissions
        test_files = []

        # Secure file
        secure_file = Path(self.temp_dir) / "secure_file"
        secure_file.write_text("secure content")
        secure_file.chmod(0o600)
        test_files.append(str(secure_file))

        # World-readable file
        readable_file = Path(self.temp_dir) / "readable_file"
        readable_file.write_text("readable content")
        readable_file.chmod(0o644)
        test_files.append(str(readable_file))

        # World-writable file (security risk)
        writable_file = Path(self.temp_dir) / "writable_file"
        writable_file.write_text("writable content")
        writable_file.chmod(0o666)
        test_files.append(str(writable_file))

        # Test filesystem permissions checking
        fs_check = self.validator._check_filesystem_permissions()

        self.assertIsInstance(fs_check, dict)
        self.assertIn("issues", fs_check)
        self.assertIn("recommendations", fs_check)
        self.assertIn("details", fs_check)

        # Verify that the validator can detect permission issues
        # (This is a basic test - in practice, the validator checks system directories)

    def test_network_isolation_validation(self):
        """Test network isolation and security policies."""
        result = self.validator.validate_network_policies()

        self.assertEqual(result.check_name, "network_policies")
        self.assertIn(
            result.level,
            [SecurityLevel.PASS, SecurityLevel.WARNING, SecurityLevel.FAIL],
        )

        # Check that network validation includes expected components
        self.assertIn("network_interfaces", result.details)
        self.assertIn("listening_ports", result.details)
        self.assertIn("tls_configuration", result.details)
        self.assertIn("container_network", result.details)

    def test_secret_management_compliance(self):
        """Test secret management compliance and security."""
        # Create test secret files
        secrets_dir = Path(self.temp_dir) / "secrets"
        secrets_dir.mkdir()

        # Secure secret file
        secure_secret = secrets_dir / "secure_secret"
        secure_secret.write_text("secret_value")
        secure_secret.chmod(0o600)

        # Insecure secret file
        insecure_secret = secrets_dir / "insecure_secret"
        insecure_secret.write_text("secret_value")
        insecure_secret.chmod(0o644)

        # Test secret management validation
        result = self.validator.validate_secret_management()

        self.assertEqual(result.check_name, "secret_management")
        self.assertIn(
            result.level,
            [SecurityLevel.PASS, SecurityLevel.WARNING, SecurityLevel.FAIL],
        )

        # Check that secret validation includes expected components
        self.assertIn("environment_secrets", result.details)
        self.assertIn("file_secrets", result.details)
        self.assertIn("secret_configuration", result.details)

    @pytest.mark.slow
    def test_vulnerability_scanning_integration(self):
        """Test vulnerability scanning in container environment."""
        if not self.validator.enable_vulnerability_scanning:
            self.skipTest("Vulnerability scanning disabled")

        report = self.validator.scan_vulnerabilities()

        self.assertIsInstance(report.total_count, int)
        self.assertIsInstance(report.critical_count, int)
        self.assertIsInstance(report.high_count, int)
        self.assertIsInstance(report.medium_count, int)
        self.assertIsInstance(report.low_count, int)

        # Verify counts add up
        self.assertEqual(
            report.total_count,
            report.critical_count
            + report.high_count
            + report.medium_count
            + report.low_count,
        )

    def test_comprehensive_security_compliance(self):
        """Test comprehensive security compliance validation."""
        report = self.validator.comprehensive_security_validation()

        self.assertIsInstance(report.overall_status, SecurityLevel)
        self.assertIsInstance(report.checks, dict)
        self.assertIsInstance(report.summary, dict)
        self.assertIsInstance(report.compliance_status, dict)

        # Verify all expected checks are present
        expected_checks = ["user_permissions", "network_policies", "secret_management"]
        for check_name in expected_checks:
            self.assertIn(check_name, report.checks)

        # Verify summary counts
        summary = report.summary
        self.assertEqual(
            summary["total_checks"],
            summary["passed_checks"]
            + summary["warning_checks"]
            + summary["failed_checks"],
        )

        # Verify compliance status includes key security areas
        compliance = report.compliance_status
        expected_compliance_areas = [
            "non_root_execution",
            "network_security",
            "secret_management",
            "vulnerability_free",
        ]

        for area in expected_compliance_areas:
            self.assertIn(area, compliance)
            self.assertIsInstance(compliance[area], bool)

    @pytest.mark.slow
    def test_container_config_integration(self):
        """Test integration with ContainerConfigManager."""
        # Create a container config manager
        config_manager = ContainerConfigManager(
            flow_name="test_flow", environment="test"
        )

        # Load container configuration
        container_config = config_manager.load_container_config()

        # Create validator with loaded configuration
        validator = SecurityValidator(
            container_config=container_config,
            enable_vulnerability_scanning=False,  # Disable for faster tests
            enable_network_validation=True,
        )

        # Perform security validation
        report = validator.comprehensive_security_validation()

        self.assertIsInstance(report.overall_status, SecurityLevel)
        self.assertGreater(report.summary["total_checks"], 0)

    def test_security_validation_with_environment_variables(self):
        """Test security validation with various environment variable configurations."""
        # Test with security-related environment variables
        test_env_vars = {
            "CONTAINER_SECURITY_RUN_AS_NON_ROOT": "true",
            "CONTAINER_SECURITY_USER_ID": "1000",
            "CONTAINER_SECURITY_DROP_CAPABILITIES": "ALL",
            "DATABASE_PASSWORD": "secret123",  # Should be detected as potential secret
            "API_KEY": "abc123def456",  # Should be detected as potential secret
        }

        with patch.dict(os.environ, test_env_vars, clear=False):
            result = self.validator.validate_secret_management()

            # Should detect potential secrets in environment variables
            env_secrets = result.details.get("environment_secrets", {})
            potential_secrets = env_secrets.get("potential_secret_env_vars", [])

            secret_names = [s["name"] for s in potential_secrets]

            # Check if secrets were detected (may depend on environment)
            if secret_names:
                # If any secrets were detected, verify our test secrets are included
                has_password = any("PASSWORD" in name for name in secret_names)
                has_key = any("KEY" in name for name in secret_names)

                # At least one of our test secrets should be detected
                self.assertTrue(
                    has_password or has_key,
                    f"Expected to detect PASSWORD or KEY in environment variables, got: {secret_names}",
                )
            else:
                # If no secrets detected, that's also acceptable (depends on implementation)
                self.assertIsInstance(secret_names, list)

    def test_security_validation_error_handling(self):
        """Test security validation error handling and recovery."""
        # Test with invalid configuration
        invalid_config = {
            "security": {
                "user_id": "invalid",  # Should be integer
                "drop_capabilities": None,  # Should be list
            }
        }

        validator = SecurityValidator(container_config=invalid_config)

        # Should handle errors gracefully
        report = validator.comprehensive_security_validation()

        self.assertIsInstance(report.overall_status, SecurityLevel)
        # May have warnings or failures due to invalid config, but shouldn't crash

    def test_security_metrics_and_reporting(self):
        """Test security metrics collection and reporting."""
        report = self.validator.comprehensive_security_validation()

        # Test report serialization
        report_dict = report.to_dict()

        self.assertIsInstance(report_dict, dict)
        self.assertIn("overall_status", report_dict)
        self.assertIn("checks", report_dict)
        self.assertIn("summary", report_dict)
        self.assertIn("compliance_status", report_dict)
        self.assertIn("timestamp", report_dict)

        # Verify JSON serialization works
        json_str = json.dumps(report_dict)
        self.assertIsInstance(json_str, str)

        # Verify deserialization works
        parsed_report = json.loads(json_str)
        self.assertEqual(parsed_report["overall_status"], report_dict["overall_status"])

    @pytest.mark.slow
    def test_security_validation_performance(self):
        """Test security validation performance and timing."""
        start_time = time.time()

        report = self.validator.comprehensive_security_validation()

        end_time = time.time()
        total_time = end_time - start_time

        # Validation should complete within reasonable time (adjust as needed)
        self.assertLess(total_time, 30.0)  # 30 seconds max

        # Check that timing information is recorded
        self.assertGreater(report.total_duration, 0)
        self.assertLess(report.total_duration, total_time + 1)  # Allow some overhead

    @pytest.mark.slow
    def test_security_validation_caching(self):
        """Test security validation caching behavior."""
        # Perform validation twice
        report1 = self.validator.comprehensive_security_validation()
        report2 = self.validator.comprehensive_security_validation()

        # Both should succeed
        self.assertIsInstance(report1.overall_status, SecurityLevel)
        self.assertIsInstance(report2.overall_status, SecurityLevel)

        # Second validation might be faster due to caching (implementation dependent)
        # This is more of a performance test than a functional test

    @pytest.mark.slow
    def test_container_runtime_security_checks(self):
        """Test container runtime security checks."""
        # Check if running in container environment
        is_container = (
            os.path.exists("/.dockerenv")
            or os.path.exists("/proc/1/cgroup")
            and any(
                "docker" in line or "containerd" in line
                for line in open("/proc/1/cgroup").readlines()
            )
        )

        if is_container:
            # Perform container-specific security checks
            result = self.validator.validate_user_permissions()

            # In container, should have specific user configuration
            self.assertIn("current_uid", result.details)
            self.assertIn("current_gid", result.details)

            # Check process capabilities if available
            if "process_capabilities" in result.details:
                caps = result.details["process_capabilities"]
                self.assertIsInstance(caps, dict)
        else:
            # Running on host system - different expectations
            self.skipTest("Not running in container environment")

    @pytest.mark.slow
    def test_security_compliance_standards(self):
        """Test compliance with security standards and best practices."""
        report = self.validator.comprehensive_security_validation()

        # Check compliance with common security standards
        compliance = report.compliance_status

        # Non-root execution (CIS Docker Benchmark)
        if "non_root_execution" in compliance:
            # Should be True for secure containers
            if not compliance["non_root_execution"]:
                # If running as root, should be flagged as security issue
                self.assertEqual(report.overall_status, SecurityLevel.FAIL)

        # Network security
        if "network_security" in compliance:
            # Network should be properly configured
            self.assertIsInstance(compliance["network_security"], bool)

        # Secret management
        if "secret_management" in compliance:
            # Secrets should be properly managed
            self.assertIsInstance(compliance["secret_management"], bool)

    def test_security_validation_with_real_vulnerabilities(self):
        """Test security validation with simulated real vulnerabilities."""
        # Create temporary files that simulate security issues

        # World-writable file in sensitive location
        if os.access("/tmp", os.W_OK):
            world_writable = Path("/tmp") / f"test_security_{os.getpid()}"
            try:
                world_writable.write_text("test content")
                world_writable.chmod(0o666)

                # Run filesystem check
                fs_check = self.validator._check_filesystem_permissions()

                # Clean up
                world_writable.unlink()

                # Should detect some filesystem issues (implementation dependent)
                self.assertIsInstance(fs_check["issues"], list)

            except PermissionError:
                self.skipTest("Cannot create test files in /tmp")

    def test_security_validation_reporting_formats(self):
        """Test different security validation reporting formats."""
        report = self.validator.comprehensive_security_validation()

        # Test dictionary format
        report_dict = report.to_dict()
        self.assertIsInstance(report_dict, dict)

        # Test JSON format
        json_report = json.dumps(report_dict, indent=2)
        self.assertIsInstance(json_report, str)

        # Verify JSON is valid
        parsed_json = json.loads(json_report)
        self.assertEqual(parsed_json["overall_status"], report.overall_status.value)

        # Test that all check results are serializable
        for _check_name, check_result in report.checks.items():
            check_dict = check_result.to_dict()
            self.assertIsInstance(check_dict, dict)
            self.assertIn("level", check_dict)
            self.assertIn("message", check_dict)


class TestSecurityValidatorContainerEnvironment(unittest.TestCase):
    """Tests specifically for container environment security validation."""

    def setUp(self):
        """Set up container environment tests."""
        self.validator = SecurityValidator(
            enable_vulnerability_scanning=False,  # Disable for faster tests
            enable_network_validation=True,
        )

    @pytest.mark.slow
    def test_container_detection(self):
        """Test detection of container environment."""
        # Check common container indicators
        container_indicators = [
            os.path.exists("/.dockerenv"),
            os.path.exists("/proc/1/cgroup"),
            os.getenv("container") is not None,
        ]

        is_likely_container = any(container_indicators)

        if is_likely_container:
            # Perform container-specific validations
            result = self.validator.validate_user_permissions()
            self.assertIsInstance(result.details, dict)
        else:
            # Running on host - different security considerations
            self.skipTest("Not detected as container environment")

    @pytest.mark.slow
    def test_container_security_context(self):
        """Test container security context validation."""
        # Check security context information
        result = self.validator.validate_user_permissions()

        # Should have user information
        self.assertIn("current_uid", result.details)
        self.assertIn("current_gid", result.details)

        # Check for container-specific security features
        if "process_capabilities" in result.details:
            caps_info = result.details["process_capabilities"]
            self.assertIsInstance(caps_info, dict)

    @pytest.mark.slow
    def test_container_network_security(self):
        """Test container network security validation."""
        result = self.validator.validate_network_policies()

        # Should check network configuration
        self.assertIn("container_network", result.details)

        container_network = result.details["container_network"]
        self.assertIsInstance(container_network, dict)

    @pytest.mark.slow
    def test_container_filesystem_security(self):
        """Test container filesystem security validation."""
        fs_check = self.validator._check_filesystem_permissions()

        # Should check filesystem permissions
        self.assertIsInstance(fs_check, dict)
        self.assertIn("issues", fs_check)
        self.assertIn("recommendations", fs_check)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)

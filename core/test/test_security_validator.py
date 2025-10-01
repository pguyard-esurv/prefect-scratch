"""
Tests for security validation and compliance system.

This module provides comprehensive tests for the SecurityValidator class including
container security configuration validation, user permission validation, network
policy validation, secret management validation, and vulnerability scanning.
"""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.security_validator import (
    SecurityLevel,
    SecurityResult,
    SecurityValidationReport,
    SecurityValidator,
    VulnerabilityReport,
)


class TestSecurityValidator(unittest.TestCase):
    """Test cases for SecurityValidator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.container_config = {
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
            container_config=self.container_config,
            enable_vulnerability_scanning=True,
            enable_network_validation=True,
        )

    def test_security_validator_initialization(self):
        """Test SecurityValidator initialization."""
        validator = SecurityValidator()
        self.assertIsNotNone(validator)
        self.assertEqual(validator.container_config, {})
        self.assertTrue(validator.enable_vulnerability_scanning)
        self.assertTrue(validator.enable_network_validation)

        # Test with custom configuration
        validator = SecurityValidator(
            container_config=self.container_config,
            enable_vulnerability_scanning=False,
            enable_network_validation=False,
        )
        self.assertEqual(validator.container_config, self.container_config)
        self.assertFalse(validator.enable_vulnerability_scanning)
        self.assertFalse(validator.enable_network_validation)

    @patch("os.getuid")
    @patch("os.getgid")
    @patch("pwd.getpwuid")
    def test_validate_user_permissions_non_root(
        self, mock_getpwuid, mock_getgid, mock_getuid
    ):
        """Test user permissions validation for non-root user."""
        # Mock non-root user
        mock_getuid.return_value = 1000
        mock_getgid.return_value = 1000
        mock_getpwuid.return_value = Mock(
            pw_name="testuser", pw_dir="/home/testuser", pw_shell="/bin/bash"
        )

        with patch.object(
            self.validator, "_check_filesystem_permissions"
        ) as mock_fs_check:
            mock_fs_check.return_value = {
                "issues": [],
                "recommendations": [],
                "details": {},
            }

            with patch.object(
                self.validator, "_check_process_capabilities"
            ) as mock_caps_check:
                mock_caps_check.return_value = {
                    "issues": [],
                    "recommendations": [],
                    "details": {},
                }

                result = self.validator.validate_user_permissions()

        self.assertIsInstance(result, SecurityResult)
        self.assertEqual(result.check_name, "user_permissions")
        self.assertEqual(result.level, SecurityLevel.PASS)
        self.assertIn("validation passed", result.message.lower())
        self.assertEqual(result.details["current_uid"], 1000)
        self.assertEqual(result.details["current_gid"], 1000)

    @patch("os.getuid")
    @patch("os.getgid")
    def test_validate_user_permissions_root_user(self, mock_getgid, mock_getuid):
        """Test user permissions validation for root user."""
        # Mock root user
        mock_getuid.return_value = 0
        mock_getgid.return_value = 0

        with patch.object(
            self.validator, "_check_filesystem_permissions"
        ) as mock_fs_check:
            mock_fs_check.return_value = {
                "issues": [],
                "recommendations": [],
                "details": {},
            }

            with patch.object(
                self.validator, "_check_process_capabilities"
            ) as mock_caps_check:
                mock_caps_check.return_value = {
                    "issues": [],
                    "recommendations": [],
                    "details": {},
                }

                result = self.validator.validate_user_permissions()

        self.assertEqual(result.level, SecurityLevel.FAIL)
        self.assertIn("root", result.message.lower())
        self.assertTrue(
            any("root" in issue.lower() for issue in result.details["issues"])
        )

    @patch("os.getuid")
    @patch("os.getgid")
    def test_validate_user_permissions_system_user(self, mock_getgid, mock_getuid):
        """Test user permissions validation for system user."""
        # Mock system user (UID < 1000)
        mock_getuid.return_value = 500
        mock_getgid.return_value = 500

        with patch.object(
            self.validator, "_check_filesystem_permissions"
        ) as mock_fs_check:
            mock_fs_check.return_value = {
                "issues": [],
                "recommendations": [],
                "details": {},
            }

            with patch.object(
                self.validator, "_check_process_capabilities"
            ) as mock_caps_check:
                mock_caps_check.return_value = {
                    "issues": [],
                    "recommendations": [],
                    "details": {},
                }

                result = self.validator.validate_user_permissions()

        self.assertEqual(result.level, SecurityLevel.WARNING)
        self.assertTrue(
            any("system user" in issue.lower() for issue in result.details["issues"])
        )

    def test_check_filesystem_permissions(self):
        """Test filesystem permissions checking."""
        with patch("os.path.exists") as mock_exists:
            with patch("os.access") as mock_access:
                with patch("os.path.expanduser") as mock_expanduser:
                    with patch("os.stat") as mock_stat:
                        # Mock filesystem state
                        mock_exists.return_value = True
                        mock_access.return_value = (
                            False  # No write access to sensitive dirs
                        )
                        mock_expanduser.return_value = "/home/testuser"

                        # Mock home directory with secure permissions
                        mock_stat_result = Mock()
                        mock_stat_result.st_mode = 0o40755  # drwxr-xr-x
                        mock_stat.return_value = mock_stat_result

                        with patch.object(
                            self.validator, "_find_setuid_files"
                        ) as mock_setuid:
                            mock_setuid.return_value = []

                            result = self.validator._check_filesystem_permissions()

        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIn("recommendations", result)
        self.assertIn("details", result)

    def test_check_process_capabilities(self):
        """Test process capabilities checking."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True

            with patch(
                "builtins.open",
                unittest.mock.mock_open(read_data="CapEff:\t0000000000000000\n"),
            ):
                result = self.validator._check_process_capabilities()

        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIn("recommendations", result)
        self.assertIn("details", result)

    def test_validate_network_policies_enabled(self):
        """Test network policy validation when enabled."""
        with patch.object(
            self.validator, "_check_network_interfaces"
        ) as mock_net_check:
            mock_net_check.return_value = {
                "issues": [],
                "recommendations": [],
                "details": {},
            }

            with patch.object(
                self.validator, "_check_listening_ports"
            ) as mock_ports_check:
                mock_ports_check.return_value = {
                    "issues": [],
                    "recommendations": [],
                    "details": {},
                }

                with patch.object(
                    self.validator, "_check_tls_configuration"
                ) as mock_tls_check:
                    mock_tls_check.return_value = {
                        "issues": [],
                        "recommendations": [],
                        "details": {},
                    }

                    with patch.object(
                        self.validator, "_check_container_network_config"
                    ) as mock_container_check:
                        mock_container_check.return_value = {
                            "issues": [],
                            "recommendations": [],
                            "details": {},
                        }

                        result = self.validator.validate_network_policies()

        self.assertEqual(result.check_name, "network_policies")
        self.assertEqual(result.level, SecurityLevel.PASS)

    def test_validate_network_policies_disabled(self):
        """Test network policy validation when disabled."""
        validator = SecurityValidator(enable_network_validation=False)
        result = validator.validate_network_policies()

        self.assertEqual(result.level, SecurityLevel.PASS)
        self.assertIn("disabled", result.message.lower())
        self.assertFalse(result.details["enabled"])

    @patch("subprocess.run")
    def test_check_listening_ports(self, mock_subprocess):
        """Test listening ports checking."""
        # Mock ss command output
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="State    Recv-Q   Send-Q     Local Address:Port\nLISTEN   0        128        0.0.0.0:22\nLISTEN   0        128        127.0.0.1:5432\n",
        )

        result = self.validator._check_listening_ports()

        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIn("recommendations", result)
        self.assertIn("details", result)
        self.assertIn("listening_ports", result["details"])

    def test_check_tls_configuration(self):
        """Test TLS configuration checking."""
        with patch.dict(os.environ, {"CONTAINER_SECURITY_TLS_ENABLED": "true"}):
            with patch("os.path.exists") as mock_exists:
                with patch("os.listdir") as mock_listdir:
                    mock_exists.return_value = True
                    mock_listdir.return_value = ["cert.pem", "key.pem"]

                    with patch("subprocess.run") as mock_subprocess:
                        # Mock successful certificate validation
                        mock_subprocess.return_value = Mock(returncode=0)

                        result = self.validator._check_tls_configuration()

        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIn("recommendations", result)
        self.assertIn("details", result)

    def test_validate_secret_management(self):
        """Test secret management validation."""
        with patch.object(
            self.validator, "_check_environment_secrets"
        ) as mock_env_check:
            mock_env_check.return_value = {
                "issues": [],
                "recommendations": [],
                "details": {},
            }

            with patch.object(self.validator, "_check_file_secrets") as mock_file_check:
                mock_file_check.return_value = {
                    "issues": [],
                    "recommendations": [],
                    "details": {},
                }

                with patch.object(
                    self.validator, "_check_secret_configuration"
                ) as mock_config_check:
                    mock_config_check.return_value = {
                        "issues": [],
                        "recommendations": [],
                        "details": {},
                    }

                    result = self.validator.validate_secret_management()

        self.assertEqual(result.check_name, "secret_management")
        self.assertEqual(result.level, SecurityLevel.PASS)

    def test_check_environment_secrets(self):
        """Test environment variable secret checking."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_PASSWORD": "secret123",
                "API_KEY": "abc123",
                "NORMAL_VAR": "value",
            },
        ):
            result = self.validator._check_environment_secrets()

        self.assertIsInstance(result, dict)
        self.assertIn("issues", result)
        self.assertIn("recommendations", result)
        self.assertIn("details", result)

        # Should detect potential secrets
        potential_secrets = result["details"]["potential_secret_env_vars"]
        secret_names = [s["name"] for s in potential_secrets]
        self.assertIn("DATABASE_PASSWORD", secret_names)
        self.assertIn("API_KEY", secret_names)
        self.assertNotIn("NORMAL_VAR", secret_names)

    def test_check_file_secrets(self):
        """Test file-based secret checking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test secret files
            secret_dir = Path(temp_dir) / "secrets"
            secret_dir.mkdir()

            # Secure file
            secure_file = secret_dir / "secure_secret"
            secure_file.write_text("secret_content")
            secure_file.chmod(0o600)

            # Insecure file
            insecure_file = secret_dir / "insecure_secret"
            insecure_file.write_text("secret_content")
            insecure_file.chmod(0o644)

            # Mock secret paths to include our temp directory
            with patch.object(self.validator, "_check_file_secrets") as mock_method:
                mock_method.return_value = {
                    "issues": [
                        f"Insecure secret file permissions: [{insecure_file} (mode: 644)]"
                    ],
                    "recommendations": [
                        "Set restrictive permissions (600 or 640) on secret files"
                    ],
                    "details": {
                        "secret_files": [
                            {"path": str(secure_file), "mode": "600", "size": 14},
                            {"path": str(insecure_file), "mode": "644", "size": 14},
                        ],
                        "insecure_files": [f"{insecure_file} (mode: 644)"],
                    },
                }

                result = self.validator._check_file_secrets()

        self.assertIn("issues", result)
        self.assertTrue(len(result["issues"]) > 0)
        self.assertIn("insecure_files", result["details"])

    def test_scan_vulnerabilities_enabled(self):
        """Test vulnerability scanning when enabled."""
        with patch.object(
            self.validator, "_scan_package_vulnerabilities"
        ) as mock_pkg_scan:
            mock_pkg_scan.return_value = [
                {
                    "id": "PKG-OPENSSL-001",
                    "title": "Vulnerable openssl package",
                    "severity": "high",
                    "component": "openssl",
                }
            ]

            with patch.object(
                self.validator, "_scan_configuration_vulnerabilities"
            ) as mock_config_scan:
                mock_config_scan.return_value = [
                    {
                        "id": "CFG-PERM-001",
                        "title": "World-writable sensitive file",
                        "severity": "medium",
                        "component": "filesystem",
                    }
                ]

                result = self.validator.scan_vulnerabilities()

        self.assertIsInstance(result, VulnerabilityReport)
        self.assertEqual(result.scan_type, "comprehensive")
        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.high_count, 1)
        self.assertEqual(result.medium_count, 1)

    def test_scan_vulnerabilities_disabled(self):
        """Test vulnerability scanning when disabled."""
        validator = SecurityValidator(enable_vulnerability_scanning=False)
        result = validator.scan_vulnerabilities()

        self.assertEqual(result.scan_type, "disabled")
        self.assertEqual(result.total_count, 0)

    @patch("subprocess.run")
    def test_scan_package_vulnerabilities(self, mock_subprocess):
        """Test package vulnerability scanning."""
        # Mock dpkg output
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="ii  openssl  1.0.1  OpenSSL library\nii  bash  4.3  Bash shell\n",
        )

        result = self.validator._scan_package_vulnerabilities()

        self.assertIsInstance(result, list)
        # Should detect vulnerable packages based on mock data
        if result:
            vuln = result[0]
            self.assertIn("id", vuln)
            self.assertIn("title", vuln)
            self.assertIn("severity", vuln)

    def test_scan_configuration_vulnerabilities(self):
        """Test configuration vulnerability scanning."""
        with patch("os.path.exists") as mock_exists:
            with patch(
                "builtins.open",
                unittest.mock.mock_open(
                    read_data="testuser::1000:1000::/home/testuser:/bin/bash\n"
                ),
            ):
                mock_exists.return_value = True

                result = self.validator._scan_configuration_vulnerabilities()

        self.assertIsInstance(result, list)
        # Should detect empty password
        if result:
            vuln = result[0]
            self.assertEqual(vuln["id"], "CFG-PASSWD-001")
            self.assertEqual(vuln["severity"], "critical")

    def test_comprehensive_security_validation(self):
        """Test comprehensive security validation."""
        with patch.object(self.validator, "validate_user_permissions") as mock_user:
            mock_user.return_value = SecurityResult(
                check_name="user_permissions",
                level=SecurityLevel.PASS,
                message="User permissions validation passed",
                details={},
                recommendations=[],
                timestamp=datetime.now(),
                check_duration=0.1,
            )

            with patch.object(
                self.validator, "validate_network_policies"
            ) as mock_network:
                mock_network.return_value = SecurityResult(
                    check_name="network_policies",
                    level=SecurityLevel.WARNING,
                    message="Network security warnings found",
                    details={},
                    recommendations=["Configure network policies"],
                    timestamp=datetime.now(),
                    check_duration=0.1,
                )

                with patch.object(
                    self.validator, "validate_secret_management"
                ) as mock_secrets:
                    mock_secrets.return_value = SecurityResult(
                        check_name="secret_management",
                        level=SecurityLevel.PASS,
                        message="Secret management validation passed",
                        details={},
                        recommendations=[],
                        timestamp=datetime.now(),
                        check_duration=0.1,
                    )

                    with patch.object(
                        self.validator, "scan_vulnerabilities"
                    ) as mock_vuln:
                        mock_vuln.return_value = VulnerabilityReport(
                            scan_type="comprehensive",
                            vulnerabilities=[],
                            total_count=0,
                            critical_count=0,
                            high_count=0,
                            medium_count=0,
                            low_count=0,
                            scan_duration=0.1,
                            timestamp=datetime.now(),
                        )

                        result = self.validator.comprehensive_security_validation()

        self.assertIsInstance(result, SecurityValidationReport)
        self.assertEqual(
            result.overall_status, SecurityLevel.WARNING
        )  # Due to network warning
        self.assertEqual(result.summary["total_checks"], 3)
        self.assertEqual(result.summary["passed_checks"], 2)
        self.assertEqual(result.summary["warning_checks"], 1)
        self.assertEqual(result.summary["failed_checks"], 0)

    def test_security_result_serialization(self):
        """Test SecurityResult serialization to dictionary."""
        result = SecurityResult(
            check_name="test_check",
            level=SecurityLevel.PASS,
            message="Test passed",
            details={"key": "value"},
            recommendations=["Test recommendation"],
            timestamp=datetime.now(),
            check_duration=0.1,
        )

        result_dict = result.to_dict()

        self.assertIsInstance(result_dict, dict)
        self.assertEqual(result_dict["check_name"], "test_check")
        self.assertEqual(result_dict["level"], "pass")
        self.assertEqual(result_dict["message"], "Test passed")
        self.assertIn("timestamp", result_dict)

    def test_vulnerability_report_serialization(self):
        """Test VulnerabilityReport serialization to dictionary."""
        report = VulnerabilityReport(
            scan_type="test",
            vulnerabilities=[{"id": "TEST-001", "severity": "low"}],
            total_count=1,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=1,
            scan_duration=0.1,
            timestamp=datetime.now(),
        )

        report_dict = report.to_dict()

        self.assertIsInstance(report_dict, dict)
        self.assertEqual(report_dict["scan_type"], "test")
        self.assertEqual(report_dict["total_count"], 1)
        self.assertIn("timestamp", report_dict)

    def test_security_validation_report_serialization(self):
        """Test SecurityValidationReport serialization to dictionary."""
        checks = {
            "test_check": SecurityResult(
                check_name="test_check",
                level=SecurityLevel.PASS,
                message="Test passed",
                details={},
                recommendations=[],
                timestamp=datetime.now(),
                check_duration=0.1,
            )
        }

        report = SecurityValidationReport(
            overall_status=SecurityLevel.PASS,
            checks=checks,
            vulnerability_reports=[],
            summary={
                "total_checks": 1,
                "passed_checks": 1,
                "warning_checks": 0,
                "failed_checks": 0,
            },
            recommendations=[],
            compliance_status={"test_compliance": True},
            timestamp=datetime.now(),
            total_duration=0.1,
        )

        report_dict = report.to_dict()

        self.assertIsInstance(report_dict, dict)
        self.assertEqual(report_dict["overall_status"], "pass")
        self.assertIn("checks", report_dict)
        self.assertIn("timestamp", report_dict)

    def test_error_handling_in_validation(self):
        """Test error handling in security validation methods."""
        # Test user permissions validation error handling
        with patch("os.getuid", side_effect=Exception("Test error")):
            result = self.validator.validate_user_permissions()
            self.assertEqual(result.level, SecurityLevel.FAIL)
            self.assertIn("failed", result.message.lower())

        # Test network policies validation error handling
        with patch.object(
            self.validator,
            "_check_network_interfaces",
            side_effect=Exception("Test error"),
        ):
            result = self.validator.validate_network_policies()
            self.assertEqual(result.level, SecurityLevel.FAIL)

        # Test secret management validation error handling
        with patch.object(
            self.validator,
            "_check_environment_secrets",
            side_effect=Exception("Test error"),
        ):
            result = self.validator.validate_secret_management()
            self.assertEqual(result.level, SecurityLevel.FAIL)


class TestSecurityValidatorIntegration(unittest.TestCase):
    """Integration tests for SecurityValidator."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.validator = SecurityValidator(
            enable_vulnerability_scanning=False,  # Disable for faster tests
            enable_network_validation=True,
        )

    @pytest.mark.slow


    def test_real_user_permissions_check(self):
        """Test real user permissions checking (non-mocked)."""
        result = self.validator.validate_user_permissions()

        self.assertIsInstance(result, SecurityResult)
        self.assertEqual(result.check_name, "user_permissions")
        self.assertIn(
            result.level,
            [SecurityLevel.PASS, SecurityLevel.WARNING, SecurityLevel.FAIL],
        )
        self.assertIsInstance(result.details, dict)
        self.assertIn("current_uid", result.details)
        self.assertIn("current_gid", result.details)

    def test_real_secret_management_check(self):
        """Test real secret management checking (non-mocked)."""
        result = self.validator.validate_secret_management()

        self.assertIsInstance(result, SecurityResult)
        self.assertEqual(result.check_name, "secret_management")
        self.assertIn(
            result.level,
            [SecurityLevel.PASS, SecurityLevel.WARNING, SecurityLevel.FAIL],
        )

    def test_comprehensive_validation_integration(self):
        """Test comprehensive security validation integration."""
        result = self.validator.comprehensive_security_validation()

        self.assertIsInstance(result, SecurityValidationReport)
        self.assertIn(
            result.overall_status,
            [SecurityLevel.PASS, SecurityLevel.WARNING, SecurityLevel.FAIL],
        )
        self.assertGreater(result.summary["total_checks"], 0)
        self.assertIsInstance(result.compliance_status, dict)


if __name__ == "__main__":
    unittest.main()

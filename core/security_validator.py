"""
Security validation and compliance system for container environments.

This module provides comprehensive security validation including container security
configuration validation, user permission validation, non-root execution verification,
network policy validation, secure communication verification, secret management
validation, and vulnerability scanning capabilities.
"""

import logging
import os
import pwd
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class SecurityLevel(Enum):
    """Security validation levels."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass
class SecurityResult:
    """Security validation result."""

    check_name: str
    level: SecurityLevel
    message: str
    details: dict[str, Any]
    recommendations: list[str]
    timestamp: datetime
    check_duration: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["level"] = self.level.value
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        return result


@dataclass
class VulnerabilityReport:
    """Vulnerability scanning report."""

    scan_type: str
    vulnerabilities: list[dict[str, Any]]
    total_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    scan_duration: float
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        return result


@dataclass
class SecurityValidationReport:
    """Comprehensive security validation report."""

    overall_status: SecurityLevel
    checks: dict[str, SecurityResult]
    vulnerability_reports: list[VulnerabilityReport]
    summary: dict[str, int]
    recommendations: list[str]
    compliance_status: dict[str, bool]
    timestamp: datetime
    total_duration: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["overall_status"] = self.overall_status.value
        result["checks"] = {k: v.to_dict() for k, v in self.checks.items()}
        result["vulnerability_reports"] = [
            vr.to_dict() for vr in self.vulnerability_reports
        ]
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        return result


class SecurityValidator:
    """
    Comprehensive security validation system for container environments.

    Provides security validation capabilities including:
    - Container security configuration validation
    - User permission validation and non-root execution verification
    - Network policy validation and secure communication verification
    - Secret management validation
    - Vulnerability scanning
    - Security compliance checking
    """

    def __init__(
        self,
        container_config: Optional[dict[str, Any]] = None,
        enable_vulnerability_scanning: bool = True,
        enable_network_validation: bool = True,
        log_level: str = "INFO",
    ):
        """
        Initialize security validator.

        Args:
            container_config: Container configuration dictionary
            enable_vulnerability_scanning: Enable vulnerability scanning
            enable_network_validation: Enable network policy validation
            log_level: Logging level
        """
        self.container_config = container_config or {}
        self.enable_vulnerability_scanning = enable_vulnerability_scanning
        self.enable_network_validation = enable_network_validation

        # Initialize logger
        self.logger = logging.getLogger("SecurityValidator")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(getattr(logging, log_level.upper()))

        # Security check cache
        self._check_cache = {}
        self._cache_ttl = 300  # 5 minutes

    def validate_user_permissions(self) -> SecurityResult:
        """
        Validate user permissions and non-root execution.

        Checks:
        - Current user is not root (UID != 0)
        - User has appropriate permissions for required operations
        - File system permissions are properly configured
        - Process capabilities are appropriately dropped

        Returns:
            SecurityResult with user permission validation details
        """
        start_time = time.time()
        check_name = "user_permissions"

        try:
            details = {}
            recommendations = []
            issues = []

            # Check current user
            current_uid = os.getuid()
            current_gid = os.getgid()

            details["current_uid"] = current_uid
            details["current_gid"] = current_gid

            # Validate non-root execution
            if current_uid == 0:
                issues.append("Container is running as root user (UID 0)")
                recommendations.append(
                    "Configure container to run as non-root user (UID >= 1000)"
                )
            elif current_uid < 1000:
                issues.append(
                    f"Container is running with system user UID {current_uid}"
                )
                recommendations.append(
                    "Use UID >= 1000 to avoid conflicts with system users"
                )

            if current_gid == 0:
                issues.append("Container is running with root group (GID 0)")
                recommendations.append(
                    "Configure container to run with non-root group (GID >= 1000)"
                )

            # Get user information
            try:
                user_info = pwd.getpwuid(current_uid)
                details["username"] = user_info.pw_name
                details["home_directory"] = user_info.pw_dir
                details["shell"] = user_info.pw_shell
            except KeyError:
                details["username"] = "unknown"
                issues.append(f"User with UID {current_uid} not found in passwd")

            # Check file system permissions
            fs_check = self._check_filesystem_permissions()
            details["filesystem_permissions"] = fs_check
            if fs_check.get("issues"):
                issues.extend(fs_check["issues"])
                recommendations.extend(fs_check.get("recommendations", []))

            # Check process capabilities
            caps_check = self._check_process_capabilities()
            details["process_capabilities"] = caps_check
            if caps_check.get("issues"):
                issues.extend(caps_check["issues"])
                recommendations.extend(caps_check.get("recommendations", []))

            # Determine security level
            if any("root" in issue.lower() for issue in issues):
                level = SecurityLevel.FAIL
                message = f"Critical security issues found: {'; '.join(issues)}"
            elif issues:
                level = SecurityLevel.WARNING
                message = f"Security warnings found: {'; '.join(issues)}"
            else:
                level = SecurityLevel.PASS
                message = "User permissions validation passed"

            details["issues"] = issues

            return SecurityResult(
                check_name=check_name,
                level=level,
                message=message,
                details=details,
                recommendations=recommendations,
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

        except Exception as e:
            self.logger.error(f"User permissions validation failed: {e}")
            return SecurityResult(
                check_name=check_name,
                level=SecurityLevel.FAIL,
                message=f"User permissions validation failed: {e}",
                details={"error": str(e)},
                recommendations=["Fix user permissions validation errors"],
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

    def _check_filesystem_permissions(self) -> dict[str, Any]:
        """Check filesystem permissions and access controls."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check write access to sensitive directories
            sensitive_dirs = ["/etc", "/usr", "/bin", "/sbin", "/lib"]
            writable_sensitive = []

            for dir_path in sensitive_dirs:
                if os.path.exists(dir_path) and os.access(dir_path, os.W_OK):
                    writable_sensitive.append(dir_path)

            if writable_sensitive:
                issues.append(
                    f"Write access to sensitive directories: {writable_sensitive}"
                )
                recommendations.append(
                    "Remove write permissions from sensitive system directories"
                )

            details["writable_sensitive_dirs"] = writable_sensitive

            # Check home directory permissions
            home_dir = os.path.expanduser("~")
            if os.path.exists(home_dir):
                home_stat = os.stat(home_dir)
                home_mode = oct(home_stat.st_mode)[-3:]
                details["home_directory_mode"] = home_mode

                # Check if home directory is world-writable
                if home_stat.st_mode & 0o002:
                    issues.append("Home directory is world-writable")
                    recommendations.append(
                        "Remove world-write permissions from home directory"
                    )

            # Check for setuid/setgid files
            setuid_files = self._find_setuid_files()
            if setuid_files:
                details["setuid_files"] = setuid_files
                if len(setuid_files) > 10:  # Arbitrary threshold
                    issues.append(
                        f"Many setuid/setgid files found: {len(setuid_files)}"
                    )
                    recommendations.append("Review and minimize setuid/setgid files")

        except Exception as e:
            issues.append(f"Filesystem permission check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _find_setuid_files(self) -> list[str]:
        """Find setuid and setgid files in common directories."""
        setuid_files = []
        search_dirs = ["/usr", "/bin", "/sbin"]

        for search_dir in search_dirs:
            if not os.path.exists(search_dir):
                continue

            try:
                # Use find command to locate setuid/setgid files
                result = subprocess.run(
                    [
                        "find",
                        search_dir,
                        "-type",
                        "f",
                        "(",
                        "-perm",
                        "-4000",
                        "-o",
                        "-perm",
                        "-2000",
                        ")",
                        "-ls",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if line.strip():
                            # Extract filename from ls output
                            parts = line.split()
                            if len(parts) >= 11:
                                filename = " ".join(parts[10:])
                                setuid_files.append(filename)

            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                # Skip if find command fails
                continue

        return setuid_files[:20]  # Limit to first 20 files

    def _check_process_capabilities(self) -> dict[str, Any]:
        """Check process capabilities and security settings."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check if running in privileged mode
            if os.path.exists("/proc/self/status"):
                with open("/proc/self/status") as f:
                    status_content = f.read()

                # Look for capability information
                cap_lines = [
                    line for line in status_content.split("\n") if "Cap" in line
                ]
                details["capabilities"] = cap_lines

                # Check for full capabilities (privileged container)
                for line in cap_lines:
                    if "CapEff:" in line:
                        cap_eff = line.split(":")[1].strip()
                        if (
                            cap_eff == "0000003fffffffff"
                            or cap_eff == "ffffffffffffffff"
                        ):
                            issues.append(
                                "Container has full capabilities (privileged)"
                            )
                            recommendations.append(
                                "Drop unnecessary capabilities and avoid privileged mode"
                            )

            # Check container security configuration
            security_config = self.container_config.get("security", {})
            if security_config:
                drop_caps = security_config.get("drop_capabilities", [])
                if "ALL" not in drop_caps:
                    issues.append("Container not configured to drop all capabilities")
                    recommendations.append(
                        "Configure container to drop all capabilities by default"
                    )

                details["configured_drop_capabilities"] = drop_caps

        except Exception as e:
            issues.append(f"Process capabilities check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def validate_network_policies(self) -> SecurityResult:
        """
        Validate network policy and secure communication configuration.

        Checks:
        - Network isolation and segmentation
        - Secure communication protocols (TLS/SSL)
        - Port exposure and access controls
        - Network policy enforcement

        Returns:
            SecurityResult with network policy validation details
        """
        start_time = time.time()
        check_name = "network_policies"

        if not self.enable_network_validation:
            return SecurityResult(
                check_name=check_name,
                level=SecurityLevel.PASS,
                message="Network validation disabled",
                details={"enabled": False},
                recommendations=[],
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

        try:
            details = {}
            recommendations = []
            issues = []

            # Check network interfaces and configuration
            network_check = self._check_network_interfaces()
            details["network_interfaces"] = network_check
            if network_check.get("issues"):
                issues.extend(network_check["issues"])
                recommendations.extend(network_check.get("recommendations", []))

            # Check listening ports and services
            ports_check = self._check_listening_ports()
            details["listening_ports"] = ports_check
            if ports_check.get("issues"):
                issues.extend(ports_check["issues"])
                recommendations.extend(ports_check.get("recommendations", []))

            # Check SSL/TLS configuration
            tls_check = self._check_tls_configuration()
            details["tls_configuration"] = tls_check
            if tls_check.get("issues"):
                issues.extend(tls_check["issues"])
                recommendations.extend(tls_check.get("recommendations", []))

            # Check container network configuration
            container_network_check = self._check_container_network_config()
            details["container_network"] = container_network_check
            if container_network_check.get("issues"):
                issues.extend(container_network_check["issues"])
                recommendations.extend(
                    container_network_check.get("recommendations", [])
                )

            # Determine security level
            critical_issues = [
                issue
                for issue in issues
                if any(
                    keyword in issue.lower()
                    for keyword in ["exposed", "insecure", "unencrypted"]
                )
            ]

            if critical_issues:
                level = SecurityLevel.FAIL
                message = (
                    f"Critical network security issues: {'; '.join(critical_issues)}"
                )
            elif issues:
                level = SecurityLevel.WARNING
                message = f"Network security warnings: {'; '.join(issues)}"
            else:
                level = SecurityLevel.PASS
                message = "Network policy validation passed"

            details["issues"] = issues

            return SecurityResult(
                check_name=check_name,
                level=level,
                message=message,
                details=details,
                recommendations=recommendations,
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

        except Exception as e:
            self.logger.error(f"Network policy validation failed: {e}")
            return SecurityResult(
                check_name=check_name,
                level=SecurityLevel.FAIL,
                message=f"Network policy validation failed: {e}",
                details={"error": str(e)},
                recommendations=["Fix network policy validation errors"],
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

    def _check_network_interfaces(self) -> dict[str, Any]:
        """Check network interfaces and configuration."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Get network interface information
            import netifaces

            interfaces = netifaces.interfaces()
            details["interfaces"] = interfaces

            interface_details = {}
            for interface in interfaces:
                addrs = netifaces.ifaddresses(interface)
                interface_details[interface] = addrs

                # Check for promiscuous mode (security risk)
                if interface != "lo":  # Skip loopback
                    try:
                        # This is a simplified check - in practice, you'd need
                        # more sophisticated network interface analysis
                        if_info = {"addresses": addrs}
                        interface_details[interface] = if_info
                    except Exception:
                        pass

            details["interface_details"] = interface_details

        except ImportError:
            # netifaces not available, use basic checks
            try:
                # Check for common network security issues using basic tools
                result = subprocess.run(
                    ["ip", "addr", "show"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    details["ip_addr_output"] = result.stdout
                    # Look for potential security issues in output
                    if "PROMISC" in result.stdout:
                        issues.append("Network interface in promiscuous mode detected")
                        recommendations.append(
                            "Disable promiscuous mode on network interfaces"
                        )
            except (
                subprocess.TimeoutExpired,
                subprocess.SubprocessError,
                FileNotFoundError,
            ):
                details["network_check"] = (
                    "Limited network interface checking available"
                )

        except Exception as e:
            issues.append(f"Network interface check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _check_listening_ports(self) -> dict[str, Any]:
        """Check listening ports and exposed services."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Get listening ports using netstat or ss
            listening_ports = []

            try:
                # Try ss first (more modern)
                result = subprocess.run(
                    ["ss", "-tlnp"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n")[1:]:  # Skip header
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                local_addr = parts[3]
                                if ":" in local_addr:
                                    port = local_addr.split(":")[-1]
                                    listening_ports.append(
                                        {
                                            "port": port,
                                            "address": local_addr,
                                            "protocol": "tcp",
                                        }
                                    )
            except (subprocess.SubprocessError, FileNotFoundError):
                # Fallback to netstat
                try:
                    result = subprocess.run(
                        ["netstat", "-tlnp"], capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split("\n"):
                            if "LISTEN" in line:
                                parts = line.split()
                                if len(parts) >= 4:
                                    local_addr = parts[3]
                                    if ":" in local_addr:
                                        port = local_addr.split(":")[-1]
                                        listening_ports.append(
                                            {
                                                "port": port,
                                                "address": local_addr,
                                                "protocol": "tcp",
                                            }
                                        )
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

            details["listening_ports"] = listening_ports

            # Check for potentially dangerous ports
            dangerous_ports = ["22", "23", "21", "80", "443", "3389", "5432", "3306"]
            exposed_dangerous = []

            for port_info in listening_ports:
                port = port_info["port"]
                address = port_info["address"]

                # Check if port is exposed on all interfaces (0.0.0.0)
                if address.startswith("0.0.0.0:") or address.startswith(":::"):
                    if port in dangerous_ports:
                        exposed_dangerous.append(f"{port} ({address})")

            if exposed_dangerous:
                issues.append(
                    f"Potentially dangerous ports exposed: {exposed_dangerous}"
                )
                recommendations.append(
                    "Restrict port exposure to specific interfaces or use firewall rules"
                )

            # Check for too many open ports
            if len(listening_ports) > 10:
                issues.append(f"Many ports listening: {len(listening_ports)}")
                recommendations.append(
                    "Review and minimize the number of listening ports"
                )

        except Exception as e:
            issues.append(f"Port scanning failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _check_tls_configuration(self) -> dict[str, Any]:
        """Check TLS/SSL configuration and secure communication."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check environment variables for TLS configuration
            tls_env_vars = [
                "CONTAINER_SECURITY_TLS_ENABLED",
                "CONTAINER_SECURITY_TLS_CERT_PATH",
                "CONTAINER_SECURITY_TLS_KEY_PATH",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            ]

            tls_config = {}
            for var in tls_env_vars:
                value = os.getenv(var)
                if value:
                    tls_config[var] = value

            details["tls_environment"] = tls_config

            # Check for certificate files
            cert_paths = [
                "/etc/ssl/certs",
                "/usr/local/share/ca-certificates",
                "/var/secrets/tls",
            ]

            cert_files = []
            for cert_path in cert_paths:
                if os.path.exists(cert_path):
                    try:
                        for file in os.listdir(cert_path):
                            if file.endswith((".crt", ".pem", ".cert")):
                                cert_files.append(os.path.join(cert_path, file))
                    except PermissionError:
                        pass

            details["certificate_files"] = cert_files

            # Check certificate validity (basic check)
            valid_certs = []
            expired_certs = []

            for cert_file in cert_files[:5]:  # Limit to first 5 certificates
                try:
                    result = subprocess.run(
                        ["openssl", "x509", "-in", cert_file, "-noout", "-dates"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0:
                        valid_certs.append(cert_file)
                    else:
                        expired_certs.append(cert_file)
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass

            details["valid_certificates"] = valid_certs
            details["expired_certificates"] = expired_certs

            if expired_certs:
                issues.append(f"Expired certificates found: {expired_certs}")
                recommendations.append("Update or remove expired certificates")

            # Check if TLS is properly configured
            if not tls_config and not cert_files:
                issues.append("No TLS configuration detected")
                recommendations.append(
                    "Configure TLS for secure communication where appropriate"
                )

        except Exception as e:
            issues.append(f"TLS configuration check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _check_container_network_config(self) -> dict[str, Any]:
        """Check container-specific network configuration."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check container network configuration from environment
            network_config = self.container_config.get("network", {})
            details["container_network_config"] = network_config

            # Check for host network mode (security risk)
            if network_config.get("mode") == "host":
                issues.append("Container using host network mode")
                recommendations.append(
                    "Use bridge or custom network instead of host network mode"
                )

            # Check for privileged network access
            if network_config.get("privileged", False):
                issues.append("Container has privileged network access")
                recommendations.append(
                    "Remove privileged network access if not required"
                )

            # Check network policies from container config
            security_config = self.container_config.get("security", {})
            if security_config:
                network_policies = security_config.get("network_policies", [])
                details["network_policies"] = network_policies

                if not network_policies:
                    issues.append("No network policies configured")
                    recommendations.append(
                        "Configure network policies to restrict container communication"
                    )

        except Exception as e:
            issues.append(f"Container network configuration check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def validate_secret_management(self) -> SecurityResult:
        """
        Validate secret management configuration and practices.

        Checks:
        - Secret storage and access patterns
        - Environment variable security
        - File-based secret management
        - Secret rotation capabilities

        Returns:
            SecurityResult with secret management validation details
        """
        start_time = time.time()
        check_name = "secret_management"

        try:
            details = {}
            recommendations = []
            issues = []

            # Check environment variables for secrets
            env_check = self._check_environment_secrets()
            details["environment_secrets"] = env_check
            if env_check.get("issues"):
                issues.extend(env_check["issues"])
                recommendations.extend(env_check.get("recommendations", []))

            # Check file-based secrets
            file_secrets_check = self._check_file_secrets()
            details["file_secrets"] = file_secrets_check
            if file_secrets_check.get("issues"):
                issues.extend(file_secrets_check["issues"])
                recommendations.extend(file_secrets_check.get("recommendations", []))

            # Check secret management configuration
            secret_config_check = self._check_secret_configuration()
            details["secret_configuration"] = secret_config_check
            if secret_config_check.get("issues"):
                issues.extend(secret_config_check["issues"])
                recommendations.extend(secret_config_check.get("recommendations", []))

            # Determine security level
            critical_issues = [
                issue
                for issue in issues
                if any(
                    keyword in issue.lower()
                    for keyword in ["plaintext", "exposed", "insecure"]
                )
            ]

            if critical_issues:
                level = SecurityLevel.FAIL
                message = (
                    f"Critical secret management issues: {'; '.join(critical_issues)}"
                )
            elif issues:
                level = SecurityLevel.WARNING
                message = f"Secret management warnings: {'; '.join(issues)}"
            else:
                level = SecurityLevel.PASS
                message = "Secret management validation passed"

            details["issues"] = issues

            return SecurityResult(
                check_name=check_name,
                level=level,
                message=message,
                details=details,
                recommendations=recommendations,
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

        except Exception as e:
            self.logger.error(f"Secret management validation failed: {e}")
            return SecurityResult(
                check_name=check_name,
                level=SecurityLevel.FAIL,
                message=f"Secret management validation failed: {e}",
                details={"error": str(e)},
                recommendations=["Fix secret management validation errors"],
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

    def _check_environment_secrets(self) -> dict[str, Any]:
        """Check environment variables for potential secrets."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Common secret patterns in environment variable names
            secret_patterns = [
                "password",
                "passwd",
                "pwd",
                "secret",
                "key",
                "token",
                "api_key",
                "apikey",
                "auth",
                "credential",
                "cred",
            ]

            potential_secrets = []
            env_vars = dict(os.environ)

            for var_name, var_value in env_vars.items():
                var_lower = var_name.lower()

                # Check if variable name suggests it contains a secret
                if any(pattern in var_lower for pattern in secret_patterns):
                    potential_secrets.append(
                        {
                            "name": var_name,
                            "value_length": len(var_value) if var_value else 0,
                            "has_value": bool(var_value),
                        }
                    )

            details["potential_secret_env_vars"] = potential_secrets
            details["total_env_vars"] = len(env_vars)

            # Check for secrets in plaintext
            plaintext_secrets = []
            for secret in potential_secrets:
                if secret["has_value"] and secret["value_length"] > 0:
                    # This is a simplified check - in practice, you'd want more
                    # sophisticated detection of what constitutes a "plaintext" secret
                    plaintext_secrets.append(secret["name"])

            if plaintext_secrets:
                issues.append(
                    f"Potential secrets in environment variables: {plaintext_secrets}"
                )
                recommendations.append(
                    "Use secure secret management instead of environment variables for sensitive data"
                )

            details["plaintext_secrets"] = plaintext_secrets

        except Exception as e:
            issues.append(f"Environment secret check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _check_file_secrets(self) -> dict[str, Any]:
        """Check file-based secret storage."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Common secret file locations
            secret_paths = [
                "/var/secrets",
                "/etc/secrets",
                "/run/secrets",
                "/tmp/secrets",
                os.path.expanduser("~/.secrets"),
            ]

            secret_files = []
            for secret_path in secret_paths:
                if os.path.exists(secret_path):
                    try:
                        for root, _dirs, files in os.walk(secret_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                file_stat = os.stat(file_path)
                                secret_files.append(
                                    {
                                        "path": file_path,
                                        "mode": oct(file_stat.st_mode)[-3:],
                                        "size": file_stat.st_size,
                                    }
                                )
                    except PermissionError:
                        pass

            details["secret_files"] = secret_files

            # Check file permissions
            insecure_files = []
            for file_info in secret_files:
                mode = file_info["mode"]
                # Check if file is world-readable or world-writable
                if mode[-1] != "0":  # World permissions
                    insecure_files.append(f"{file_info['path']} (mode: {mode})")

            if insecure_files:
                issues.append(f"Insecure secret file permissions: {insecure_files}")
                recommendations.append(
                    "Set restrictive permissions (600 or 640) on secret files"
                )

            details["insecure_files"] = insecure_files

            # Check for secrets in /tmp (security risk)
            tmp_secrets = [f for f in secret_files if f["path"].startswith("/tmp")]
            if tmp_secrets:
                issues.append(
                    f"Secrets stored in /tmp: {[f['path'] for f in tmp_secrets]}"
                )
                recommendations.append("Avoid storing secrets in /tmp directory")

        except Exception as e:
            issues.append(f"File secret check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def _check_secret_configuration(self) -> dict[str, Any]:
        """Check secret management configuration."""
        issues = []
        recommendations = []
        details = {}

        try:
            # Check container security configuration for secret management
            security_config = self.container_config.get("security", {})
            secrets_config = security_config.get("secrets", {})

            details["secrets_configuration"] = secrets_config

            # Check if secret management is properly configured
            if not secrets_config:
                issues.append("No secret management configuration found")
                recommendations.append(
                    "Configure proper secret management system (e.g., Kubernetes secrets, Docker secrets)"
                )

            # Check secret mount path security
            secrets_mount_path = security_config.get(
                "secrets_mount_path", "/var/secrets"
            )
            if secrets_mount_path and os.path.exists(secrets_mount_path):
                try:
                    mount_stat = os.stat(secrets_mount_path)
                    mount_mode = oct(mount_stat.st_mode)[-3:]
                    details["secrets_mount_permissions"] = mount_mode

                    # Check if mount point has secure permissions
                    if mount_mode != "700" and mount_mode != "750":
                        issues.append(
                            f"Insecure secrets mount permissions: {mount_mode}"
                        )
                        recommendations.append(
                            "Set restrictive permissions (700) on secrets mount directory"
                        )
                except OSError:
                    pass

        except Exception as e:
            issues.append(f"Secret configuration check failed: {e}")

        return {
            "issues": issues,
            "recommendations": recommendations,
            "details": details,
        }

    def scan_vulnerabilities(self) -> VulnerabilityReport:
        """
        Perform vulnerability scanning on the container environment.

        Scans for:
        - Known vulnerabilities in installed packages
        - Configuration vulnerabilities
        - Security misconfigurations

        Returns:
            VulnerabilityReport with vulnerability scan results
        """
        start_time = time.time()

        if not self.enable_vulnerability_scanning:
            return VulnerabilityReport(
                scan_type="disabled",
                vulnerabilities=[],
                total_count=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                scan_duration=time.time() - start_time,
                timestamp=datetime.now(),
            )

        try:
            vulnerabilities = []

            # Scan for package vulnerabilities
            package_vulns = self._scan_package_vulnerabilities()
            vulnerabilities.extend(package_vulns)

            # Scan for configuration vulnerabilities
            config_vulns = self._scan_configuration_vulnerabilities()
            vulnerabilities.extend(config_vulns)

            # Categorize vulnerabilities by severity
            critical_count = len(
                [v for v in vulnerabilities if v.get("severity") == "critical"]
            )
            high_count = len(
                [v for v in vulnerabilities if v.get("severity") == "high"]
            )
            medium_count = len(
                [v for v in vulnerabilities if v.get("severity") == "medium"]
            )
            low_count = len([v for v in vulnerabilities if v.get("severity") == "low"])

            return VulnerabilityReport(
                scan_type="comprehensive",
                vulnerabilities=vulnerabilities,
                total_count=len(vulnerabilities),
                critical_count=critical_count,
                high_count=high_count,
                medium_count=medium_count,
                low_count=low_count,
                scan_duration=time.time() - start_time,
                timestamp=datetime.now(),
            )

        except Exception as e:
            self.logger.error(f"Vulnerability scanning failed: {e}")
            return VulnerabilityReport(
                scan_type="failed",
                vulnerabilities=[
                    {
                        "id": "SCAN_ERROR",
                        "title": "Vulnerability scan failed",
                        "description": str(e),
                        "severity": "high",
                        "component": "scanner",
                    }
                ],
                total_count=1,
                critical_count=0,
                high_count=1,
                medium_count=0,
                low_count=0,
                scan_duration=time.time() - start_time,
                timestamp=datetime.now(),
            )

    def _scan_package_vulnerabilities(self) -> list[dict[str, Any]]:
        """Scan for vulnerabilities in installed packages."""
        vulnerabilities = []

        try:
            # Try to get package information using different package managers
            packages = []

            # Check for apt packages (Debian/Ubuntu)
            try:
                result = subprocess.run(
                    ["dpkg", "-l"], capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.startswith("ii "):
                            parts = line.split()
                            if len(parts) >= 3:
                                packages.append(
                                    {
                                        "name": parts[1],
                                        "version": parts[2],
                                        "manager": "apt",
                                    }
                                )
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

            # Check for yum/rpm packages (RedHat/CentOS)
            try:
                result = subprocess.run(
                    ["rpm", "-qa", "--queryformat", "%{NAME} %{VERSION}\n"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 2:
                                packages.append(
                                    {
                                        "name": parts[0],
                                        "version": parts[1],
                                        "manager": "rpm",
                                    }
                                )
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

            # Simple vulnerability check based on known vulnerable packages
            # In a real implementation, this would query a vulnerability database
            vulnerable_packages = {
                "openssl": ["1.0.1", "1.0.2"],  # Example vulnerable versions
                "bash": ["4.3"],  # Shellshock vulnerability
                "glibc": ["2.17"],  # Example vulnerable version
            }

            for package in packages[:50]:  # Limit to first 50 packages
                pkg_name = package["name"]
                pkg_version = package["version"]

                if pkg_name in vulnerable_packages:
                    vulnerable_versions = vulnerable_packages[pkg_name]
                    for vuln_version in vulnerable_versions:
                        if vuln_version in pkg_version:
                            vulnerabilities.append(
                                {
                                    "id": f"PKG-{pkg_name.upper()}-001",
                                    "title": f"Vulnerable {pkg_name} package",
                                    "description": f"Package {pkg_name} version {pkg_version} has known vulnerabilities",
                                    "severity": "high",
                                    "component": pkg_name,
                                    "version": pkg_version,
                                    "fix": f"Update {pkg_name} to latest version",
                                }
                            )

        except Exception as e:
            self.logger.debug(f"Package vulnerability scan failed: {e}")

        return vulnerabilities

    def _scan_configuration_vulnerabilities(self) -> list[dict[str, Any]]:
        """Scan for configuration-based vulnerabilities."""
        vulnerabilities = []

        try:
            # Check for common configuration vulnerabilities

            # 1. Check for default passwords or weak configurations
            if os.path.exists("/etc/passwd"):
                try:
                    with open("/etc/passwd") as f:
                        passwd_content = f.read()
                        # Check for users with empty passwords (simplified check)
                        for line in passwd_content.split("\n"):
                            if "::" in line:  # Empty password field
                                user = line.split(":")[0]
                                vulnerabilities.append(
                                    {
                                        "id": "CFG-PASSWD-001",
                                        "title": "User with empty password",
                                        "description": f"User '{user}' has empty password",
                                        "severity": "critical",
                                        "component": "authentication",
                                        "fix": "Set strong password or disable account",
                                    }
                                )
                except PermissionError:
                    pass

            # 2. Check for world-writable files in sensitive locations
            sensitive_dirs = ["/etc", "/usr/bin", "/usr/sbin"]
            for dir_path in sensitive_dirs:
                if os.path.exists(dir_path):
                    try:
                        for root, _dirs, files in os.walk(dir_path):
                            for file in files[:10]:  # Limit check
                                file_path = os.path.join(root, file)
                                try:
                                    file_stat = os.stat(file_path)
                                    if file_stat.st_mode & 0o002:  # World-writable
                                        vulnerabilities.append(
                                            {
                                                "id": "CFG-PERM-001",
                                                "title": "World-writable sensitive file",
                                                "description": f"File {file_path} is world-writable",
                                                "severity": "medium",
                                                "component": "filesystem",
                                                "fix": f"Remove world-write permission from {file_path}",
                                            }
                                        )
                                except OSError:
                                    pass
                    except PermissionError:
                        pass

            # 3. Check for SSH configuration issues
            ssh_config_paths = ["/etc/ssh/sshd_config", "/etc/ssh/ssh_config"]
            for config_path in ssh_config_paths:
                if os.path.exists(config_path):
                    try:
                        with open(config_path) as f:
                            ssh_config = f.read()
                            if "PermitRootLogin yes" in ssh_config:
                                vulnerabilities.append(
                                    {
                                        "id": "CFG-SSH-001",
                                        "title": "SSH root login enabled",
                                        "description": "SSH configuration allows root login",
                                        "severity": "high",
                                        "component": "ssh",
                                        "fix": "Set PermitRootLogin to 'no' in SSH configuration",
                                    }
                                )
                    except PermissionError:
                        pass

        except Exception as e:
            self.logger.debug(f"Configuration vulnerability scan failed: {e}")

        return vulnerabilities

    def comprehensive_security_validation(self) -> SecurityValidationReport:
        """
        Perform comprehensive security validation of the container environment.

        Returns:
            SecurityValidationReport with complete security assessment
        """
        start_time = time.time()

        self.logger.info("Starting comprehensive security validation")

        checks = {}
        vulnerability_reports = []
        recommendations = []

        try:
            # Perform all security checks
            checks["user_permissions"] = self.validate_user_permissions()
            checks["network_policies"] = self.validate_network_policies()
            checks["secret_management"] = self.validate_secret_management()

            # Perform vulnerability scanning
            if self.enable_vulnerability_scanning:
                vuln_report = self.scan_vulnerabilities()
                vulnerability_reports.append(vuln_report)

            # Collect all recommendations
            for check in checks.values():
                recommendations.extend(check.recommendations)

            # Calculate summary
            summary = {
                "total_checks": len(checks),
                "passed_checks": len(
                    [c for c in checks.values() if c.level == SecurityLevel.PASS]
                ),
                "warning_checks": len(
                    [c for c in checks.values() if c.level == SecurityLevel.WARNING]
                ),
                "failed_checks": len(
                    [c for c in checks.values() if c.level == SecurityLevel.FAIL]
                ),
            }

            # Determine overall status
            if summary["failed_checks"] > 0:
                overall_status = SecurityLevel.FAIL
            elif summary["warning_checks"] > 0:
                overall_status = SecurityLevel.WARNING
            else:
                overall_status = SecurityLevel.PASS

            # Check compliance status
            compliance_status = {
                "non_root_execution": checks["user_permissions"].level
                != SecurityLevel.FAIL,
                "network_security": checks["network_policies"].level
                != SecurityLevel.FAIL,
                "secret_management": checks["secret_management"].level
                != SecurityLevel.FAIL,
                "vulnerability_free": len(vulnerability_reports) == 0
                or all(vr.critical_count == 0 for vr in vulnerability_reports),
            }

            total_duration = time.time() - start_time

            self.logger.info(
                f"Security validation completed in {total_duration:.2f}s - "
                f"Overall status: {overall_status.value}"
            )

            return SecurityValidationReport(
                overall_status=overall_status,
                checks=checks,
                vulnerability_reports=vulnerability_reports,
                summary=summary,
                recommendations=list(set(recommendations)),  # Remove duplicates
                compliance_status=compliance_status,
                timestamp=datetime.now(),
                total_duration=total_duration,
            )

        except Exception as e:
            self.logger.error(f"Comprehensive security validation failed: {e}")

            return SecurityValidationReport(
                overall_status=SecurityLevel.FAIL,
                checks=checks,
                vulnerability_reports=vulnerability_reports,
                summary={
                    "total_checks": 0,
                    "passed_checks": 0,
                    "warning_checks": 0,
                    "failed_checks": 1,
                },
                recommendations=["Fix security validation system errors"],
                compliance_status={"validation_error": True},
                timestamp=datetime.now(),
                total_duration=time.time() - start_time,
            )

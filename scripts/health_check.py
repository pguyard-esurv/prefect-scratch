#!/usr/bin/env python3
"""
Health check script for base container image and flow-specific validation.
Validates core system components, dependencies, and flow-specific requirements.
"""

import argparse
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BaseImageHealthChecker:
    """Health checker for base container image validation."""

    def __init__(self):
        self.health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "errors": [],
        }

    def check_python_environment(self) -> bool:
        """Check Python environment and core dependencies."""
        try:
            # Check Python version
            python_version = sys.version_info
            if python_version.major != 3 or python_version.minor < 11:
                self.health_status["errors"].append(
                    f"Python version {python_version.major}.{python_version.minor} not supported"
                )
                return False

            self.health_status["checks"]["python_version"] = {
                "status": "ok",
                "version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
            }
            return True

        except Exception as e:
            self.health_status["errors"].append(
                f"Python environment check failed: {str(e)}"
            )
            return False

    def check_core_modules(self) -> bool:
        """Check that core modules are available and importable."""
        core_modules = [
            "core.config",
            "core.database",
            "core.distributed",
            "core.tasks",
            "core.monitoring",
        ]

        failed_modules = []

        for module_name in core_modules:
            try:
                importlib.import_module(module_name)
                self.health_status["checks"][f"module_{module_name}"] = {"status": "ok"}
            except ImportError as e:
                failed_modules.append(f"{module_name}: {str(e)}")
                self.health_status["checks"][f"module_{module_name}"] = {
                    "status": "failed",
                    "error": str(e),
                }

        if failed_modules:
            self.health_status["errors"].extend(failed_modules)
            return False

        return True

    def check_system_dependencies(self) -> bool:
        """Check system dependencies and tools."""
        dependencies = [
            {"name": "gcc", "command": ["gcc", "--version"]},
            {"name": "curl", "command": ["curl", "--version"]},
            {"name": "uv", "command": ["uv", "--version"]},
        ]

        failed_deps = []

        for dep in dependencies:
            try:
                result = subprocess.run(
                    dep["command"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    self.health_status["checks"][f"dependency_{dep['name']}"] = {
                        "status": "ok"
                    }
                else:
                    failed_deps.append(f"{dep['name']}: command failed")
                    self.health_status["checks"][f"dependency_{dep['name']}"] = {
                        "status": "failed",
                        "error": "command failed",
                    }
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                failed_deps.append(f"{dep['name']}: {str(e)}")
                self.health_status["checks"][f"dependency_{dep['name']}"] = {
                    "status": "failed",
                    "error": str(e),
                }

        if failed_deps:
            self.health_status["errors"].extend(failed_deps)
            return False

        return True

    def check_file_permissions(self) -> bool:
        """Check file system permissions and directory structure."""
        required_dirs = ["/app", "/app/logs", "/app/data", "/app/output"]

        permission_errors = []

        for dir_path in required_dirs:
            try:
                if not os.path.exists(dir_path):
                    permission_errors.append(f"Directory {dir_path} does not exist")
                    continue

                # Check if directory is writable
                test_file = os.path.join(dir_path, ".health_check_test")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)

                self.health_status["checks"][f"permissions_{dir_path}"] = {
                    "status": "ok"
                }

            except (OSError, PermissionError) as e:
                permission_errors.append(f"Permission error for {dir_path}: {str(e)}")
                self.health_status["checks"][f"permissions_{dir_path}"] = {
                    "status": "failed",
                    "error": str(e),
                }

        if permission_errors:
            self.health_status["errors"].extend(permission_errors)
            return False

        return True

    def check_user_security(self) -> bool:
        """Check that container is running as non-root user."""
        try:
            uid = os.getuid()
            if uid == 0:
                self.health_status["errors"].append(
                    "Container running as root user (security risk)"
                )
                self.health_status["checks"]["user_security"] = {
                    "status": "failed",
                    "error": "running as root",
                }
                return False

            self.health_status["checks"]["user_security"] = {"status": "ok", "uid": uid}
            return True

        except Exception as e:
            self.health_status["errors"].append(f"User security check failed: {str(e)}")
            return False

    def run_all_checks(self) -> bool:
        """Run all health checks and return overall status."""
        checks = [
            self.check_python_environment,
            self.check_core_modules,
            self.check_system_dependencies,
            self.check_file_permissions,
            self.check_user_security,
        ]

        all_passed = True

        for check in checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                self.health_status["errors"].append(f"Health check failed: {str(e)}")
                all_passed = False

        if not all_passed:
            self.health_status["status"] = "unhealthy"

        return all_passed

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        return self.health_status


class FlowHealthChecker(BaseImageHealthChecker):
    """Extended health checker for flow-specific validation."""

    def __init__(self, flow_name: str):
        super().__init__()
        self.flow_name = flow_name
        self.flow_dir = Path(f"/app/flows/{flow_name}")

    def check_flow_structure(self) -> bool:
        """Check flow directory structure and required files."""
        try:
            required_files = ["workflow.py", "__init__.py"]

            required_dirs = ["data", "output"]

            missing_items = []

            # Check required files
            for file_name in required_files:
                file_path = self.flow_dir / file_name
                if not file_path.exists():
                    missing_items.append(f"Missing file: {file_path}")
                else:
                    self.health_status["checks"][f"flow_file_{file_name}"] = {
                        "status": "ok"
                    }

            # Check required directories
            for dir_name in required_dirs:
                dir_path = self.flow_dir / dir_name
                if not dir_path.exists():
                    missing_items.append(f"Missing directory: {dir_path}")
                else:
                    self.health_status["checks"][f"flow_dir_{dir_name}"] = {
                        "status": "ok"
                    }

            if missing_items:
                self.health_status["errors"].extend(missing_items)
                return False

            return True

        except Exception as e:
            self.health_status["errors"].append(
                f"Flow structure check failed: {str(e)}"
            )
            return False

    def check_flow_configuration(self) -> bool:
        """Check flow-specific configuration and environment variables."""
        try:
            # Check flow-specific environment variables
            flow_env_vars = {
                "FLOW_NAME": self.flow_name,
                "FLOW_TYPE": None,  # Should be set but value varies
                "PREFECT_FLOW_NAME": None,  # Should be set but value varies
            }

            config_errors = []

            for var_name, expected_value in flow_env_vars.items():
                actual_value = os.environ.get(var_name)

                if actual_value is None:
                    config_errors.append(f"Missing environment variable: {var_name}")
                    self.health_status["checks"][f"env_{var_name}"] = {
                        "status": "failed",
                        "error": "not set",
                    }
                elif expected_value is not None and actual_value != expected_value:
                    config_errors.append(
                        f"Incorrect {var_name}: expected '{expected_value}', got '{actual_value}'"
                    )
                    self.health_status["checks"][f"env_{var_name}"] = {
                        "status": "failed",
                        "error": f"incorrect value: {actual_value}",
                    }
                else:
                    self.health_status["checks"][f"env_{var_name}"] = {
                        "status": "ok",
                        "value": actual_value,
                    }

            if config_errors:
                self.health_status["errors"].extend(config_errors)
                return False

            return True

        except Exception as e:
            self.health_status["errors"].append(
                f"Flow configuration check failed: {str(e)}"
            )
            return False

    def check_flow_dependencies(self) -> bool:
        """Check flow-specific dependencies and imports."""
        try:
            # Try to import the flow workflow module
            flow_module_path = f"flows.{self.flow_name}.workflow"

            try:
                importlib.import_module(flow_module_path)
                self.health_status["checks"]["flow_workflow_import"] = {"status": "ok"}
            except ImportError as e:
                self.health_status["errors"].append(
                    f"Cannot import flow workflow: {str(e)}"
                )
                self.health_status["checks"]["flow_workflow_import"] = {
                    "status": "failed",
                    "error": str(e),
                }
                return False

            # Check flow-specific configuration module
            try:
                from core.config import ConfigManager

                config = ConfigManager(self.flow_name)
                # Test basic configuration access
                _ = config.environment
                self.health_status["checks"]["flow_config_access"] = {"status": "ok"}
            except Exception as e:
                self.health_status["errors"].append(
                    f"Flow configuration access failed: {str(e)}"
                )
                self.health_status["checks"]["flow_config_access"] = {
                    "status": "failed",
                    "error": str(e),
                }
                return False

            return True

        except Exception as e:
            self.health_status["errors"].append(
                f"Flow dependencies check failed: {str(e)}"
            )
            return False

    def check_database_connectivity(self) -> bool:
        """Check database connectivity for the flow."""
        try:
            # Only check if distributed processing is available
            try:
                from core.database import DatabaseManager

                # Test RPA database connection
                rpa_db = DatabaseManager("rpa_db")
                health_result = rpa_db.health_check()

                if health_result.get("status") == "healthy":
                    self.health_status["checks"]["database_rpa_db"] = {"status": "ok"}
                else:
                    self.health_status["checks"]["database_rpa_db"] = {
                        "status": "degraded",
                        "error": health_result.get("error", "Unknown error"),
                    }
                    # Don't fail the health check for database issues in startup mode

            except ImportError:
                # Database module not available, skip check
                self.health_status["checks"]["database_connectivity"] = {
                    "status": "skipped",
                    "reason": "database module not available",
                }
            except Exception as e:
                self.health_status["checks"]["database_connectivity"] = {
                    "status": "degraded",
                    "error": str(e),
                }

            return True  # Don't fail health check for database connectivity issues

        except Exception as e:
            self.health_status["errors"].append(
                f"Database connectivity check failed: {str(e)}"
            )
            return False

    def run_flow_checks(self) -> bool:
        """Run flow-specific health checks."""
        flow_checks = [
            self.check_flow_structure,
            self.check_flow_configuration,
            self.check_flow_dependencies,
            self.check_database_connectivity,
        ]

        all_passed = True

        for check in flow_checks:
            try:
                if not check():
                    all_passed = False
            except Exception as e:
                self.health_status["errors"].append(
                    f"Flow health check failed: {str(e)}"
                )
                all_passed = False

        return all_passed

    def run_all_checks(self) -> bool:
        """Run both base and flow-specific health checks."""
        base_healthy = super().run_all_checks()
        flow_healthy = self.run_flow_checks()

        overall_healthy = base_healthy and flow_healthy

        if not overall_healthy:
            self.health_status["status"] = "unhealthy"

        return overall_healthy


def main():
    """Main health check execution."""
    parser = argparse.ArgumentParser(description="Container health check")
    parser.add_argument("--flow", help="Flow name for flow-specific checks")
    parser.add_argument(
        "--startup-check", action="store_true", help="Perform startup validation checks"
    )
    parser.add_argument(
        "--quick-check", action="store_true", help="Perform quick health check"
    )

    args = parser.parse_args()

    try:
        if args.flow:
            # Flow-specific health check
            if args.flow not in ["rpa1", "rpa2", "rpa3"]:
                print(
                    json.dumps(
                        {
                            "status": "unhealthy",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "errors": [f"Invalid flow name: {args.flow}"],
                        },
                        indent=2,
                    )
                )
                sys.exit(1)

            checker = FlowHealthChecker(args.flow)
        else:
            # Base image health check
            checker = BaseImageHealthChecker()

        if args.quick_check:
            # Quick check - only essential validations
            is_healthy = (
                checker.check_python_environment() and checker.check_core_modules()
            )
        else:
            # Full health check
            is_healthy = checker.run_all_checks()

        health_status = checker.get_health_status()

        # Output health status as JSON
        print(json.dumps(health_status, indent=2))

        # Exit with appropriate code
        sys.exit(0 if is_healthy else 1)

    except Exception as e:
        error_status = {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": [f"Health check execution failed: {str(e)}"],
        }
        print(json.dumps(error_status, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Enhanced Container Startup Script with Lifecycle Management

This script provides comprehensive container startup with integrated lifecycle
management, dependency checking, health monitoring, graceful shutdown, and
restart policies.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.container_config import ContainerConfigManager
from core.container_lifecycle_manager import (
    ContainerLifecycleManager,
    DependencyCheck,
    RestartConfig,
    RestartPolicy,
)
from core.database import DatabaseManager


class EnhancedContainerStartup:
    """Enhanced container startup with comprehensive lifecycle management"""

    def __init__(self, flow_name: str, container_id: Optional[str] = None):
        """
        Initialize enhanced container startup.

        Args:
            flow_name: Name of the flow/container
            container_id: Optional container ID (auto-generated if not provided)
        """
        self.flow_name = flow_name
        self.container_id = container_id or f"{flow_name}-{int(time.time())}"

        # Initialize configuration
        self.config_manager = ContainerConfigManager(flow_name)

        # Initialize restart configuration
        self.restart_config = self._create_restart_config()

        # Initialize lifecycle manager
        self.lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=flow_name,
            config_manager=self.config_manager,
            restart_config=self.restart_config,
        )

        # Setup logging
        self.logger = self._setup_logging()

        self.logger.info(
            f"Enhanced container startup initialized for {flow_name} "
            f"(container_id: {self.container_id})"
        )

    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging for container startup"""
        logger = logging.getLogger(f"container_startup_{self.flow_name}")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"component": "container_startup", "container_id": "'
                + self.container_id
                + '", '
                '"flow": "' + self.flow_name + '", "message": "%(message)s"}'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        return logger

    def _create_restart_config(self) -> RestartConfig:
        """Create restart configuration from environment variables"""
        restart_policy_str = os.getenv("CONTAINER_RESTART_POLICY", "on-failure").lower()

        # Map string to enum
        policy_mapping = {
            "no": RestartPolicy.NO,
            "always": RestartPolicy.ALWAYS,
            "on-failure": RestartPolicy.ON_FAILURE,
            "unless-stopped": RestartPolicy.UNLESS_STOPPED,
        }

        restart_policy = policy_mapping.get(
            restart_policy_str, RestartPolicy.ON_FAILURE
        )

        return RestartConfig(
            policy=restart_policy,
            max_restart_attempts=int(os.getenv("CONTAINER_MAX_RESTART_ATTEMPTS", "5")),
            restart_delay_seconds=int(
                os.getenv("CONTAINER_RESTART_DELAY_SECONDS", "10")
            ),
            exponential_backoff=os.getenv(
                "CONTAINER_RESTART_EXPONENTIAL_BACKOFF", "true"
            ).lower()
            == "true",
            max_delay_seconds=int(
                os.getenv("CONTAINER_MAX_RESTART_DELAY_SECONDS", "300")
            ),
            restart_window_minutes=int(
                os.getenv("CONTAINER_RESTART_WINDOW_MINUTES", "60")
            ),
        )

    def setup_dependency_checks(self):
        """Setup flow-specific dependency checks"""
        self.logger.info("Setting up dependency checks")

        # Database dependency (always required)
        self.lifecycle_manager.add_dependency_check(
            DependencyCheck(
                name="rpa_database",
                check_function=self._check_rpa_database,
                timeout_seconds=120,
                required=True,
                description="RPA database connectivity and health",
            )
        )

        # SurveyHub database (optional, flow-specific)
        if os.getenv("CONTAINER_DATABASE_SURVEY_HUB_HOST"):
            self.lifecycle_manager.add_dependency_check(
                DependencyCheck(
                    name="surveyhub_database",
                    check_function=self._check_surveyhub_database,
                    timeout_seconds=60,
                    required=False,
                    description="SurveyHub database connectivity",
                )
            )

        # Prefect server dependency
        if os.getenv("CONTAINER_PREFECT_API_URL"):
            self.lifecycle_manager.add_dependency_check(
                DependencyCheck(
                    name="prefect_server",
                    check_function=self._check_prefect_server,
                    timeout_seconds=60,
                    required=self._is_prefect_required(),
                    description="Prefect server connectivity and health",
                )
            )

        # Flow-specific dependencies
        self._setup_flow_specific_dependencies()

    def _check_rpa_database(self) -> bool:
        """Check RPA database connectivity and health"""
        try:
            db_manager = DatabaseManager("rpa_db")
            health_result = db_manager.health_check()
            return health_result.get("status") in ["healthy", "degraded"]
        except Exception as e:
            self.logger.debug(f"RPA database check failed: {e}")
            return False

    def _check_surveyhub_database(self) -> bool:
        """Check SurveyHub database connectivity"""
        try:
            db_manager = DatabaseManager("SurveyHub")
            health_result = db_manager.health_check()
            return health_result.get("status") in ["healthy", "degraded"]
        except Exception as e:
            self.logger.debug(f"SurveyHub database check failed: {e}")
            return False

    def _check_prefect_server(self) -> bool:
        """Check Prefect server connectivity"""
        try:
            return self.lifecycle_manager.service_orchestrator.wait_for_prefect_server(
                timeout=30
            )
        except Exception as e:
            self.logger.debug(f"Prefect server check failed: {e}")
            return False

    def _is_prefect_required(self) -> bool:
        """Determine if Prefect server is required for this flow"""
        # Prefect is required for flows that use Prefect orchestration
        execution_mode = os.getenv("CONTAINER_EXECUTION_MODE", "daemon")
        return execution_mode in ["server", "agent"]

    def _setup_flow_specific_dependencies(self):
        """Setup flow-specific dependency checks"""
        if self.flow_name == "rpa1":
            # RPA1 might need file system access
            self.lifecycle_manager.add_dependency_check(
                DependencyCheck(
                    name="rpa1_input_directory",
                    check_function=lambda: os.path.exists("/app/flows/rpa1/data"),
                    timeout_seconds=5,
                    required=True,
                    description="RPA1 input directory accessibility",
                )
            )

        elif self.flow_name == "rpa2":
            # RPA2 might need specific validation services
            validation_endpoint = os.getenv("CONTAINER_RPA2_VALIDATION_ENDPOINT")
            if validation_endpoint:
                self.lifecycle_manager.add_dependency_check(
                    DependencyCheck(
                        name="rpa2_validation_service",
                        check_function=lambda: self._check_http_endpoint(
                            validation_endpoint
                        ),
                        timeout_seconds=30,
                        required=False,
                        description="RPA2 validation service endpoint",
                    )
                )

        elif self.flow_name == "rpa3":
            # RPA3 might need concurrent processing resources
            self.lifecycle_manager.add_dependency_check(
                DependencyCheck(
                    name="rpa3_concurrent_resources",
                    check_function=self._check_concurrent_resources,
                    timeout_seconds=10,
                    required=True,
                    description="RPA3 concurrent processing resources",
                )
            )

    def _check_http_endpoint(self, endpoint: str) -> bool:
        """Check HTTP endpoint availability"""
        try:
            import requests

            response = requests.get(endpoint, timeout=5)
            return response.status_code < 500
        except Exception:
            return False

    def _check_concurrent_resources(self) -> bool:
        """Check if system has sufficient resources for concurrent processing"""
        try:
            import psutil

            # Check CPU cores
            cpu_count = psutil.cpu_count()
            required_workers = int(os.getenv("CONTAINER_RPA3_CONCURRENT_WORKERS", "4"))

            if cpu_count < required_workers:
                self.logger.warning(
                    f"Insufficient CPU cores: {cpu_count} available, {required_workers} required"
                )
                return False

            # Check available memory
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)
            required_mb = required_workers * 128  # 128MB per worker

            if available_mb < required_mb:
                self.logger.warning(
                    f"Insufficient memory: {available_mb:.0f}MB available, {required_mb}MB required"
                )
                return False

            return True

        except Exception as e:
            self.logger.debug(f"Concurrent resources check failed: {e}")
            return False

    def setup_cleanup_handlers(self):
        """Setup cleanup handlers for graceful shutdown"""
        self.logger.info("Setting up cleanup handlers")

        # Flow-specific cleanup
        if self.flow_name == "rpa1":
            self.lifecycle_manager.add_cleanup_handler(self._cleanup_rpa1_resources)
        elif self.flow_name == "rpa2":
            self.lifecycle_manager.add_cleanup_handler(self._cleanup_rpa2_resources)
        elif self.flow_name == "rpa3":
            self.lifecycle_manager.add_cleanup_handler(self._cleanup_rpa3_resources)

        # Common cleanup handlers
        self.lifecycle_manager.add_cleanup_handler(self._cleanup_temp_files)
        self.lifecycle_manager.add_cleanup_handler(self._cleanup_log_files)
        self.lifecycle_manager.add_cleanup_handler(self._export_final_metrics)

    def _cleanup_rpa1_resources(self):
        """Cleanup RPA1-specific resources"""
        self.logger.info("Cleaning up RPA1 resources")

        try:
            # Close any open file handles
            output_dir = "/app/flows/rpa1/output"
            if os.path.exists(output_dir):
                # Ensure all files are properly closed and synced
                import subprocess

                subprocess.run(["sync"], check=False)

            self.logger.info("RPA1 resource cleanup completed")
        except Exception as e:
            self.logger.error(f"RPA1 resource cleanup failed: {e}")

    def _cleanup_rpa2_resources(self):
        """Cleanup RPA2-specific resources"""
        self.logger.info("Cleaning up RPA2 resources")

        try:
            # Cleanup validation caches or temporary data
            cache_dir = "/tmp/rpa2_validation_cache"
            if os.path.exists(cache_dir):
                import shutil

                shutil.rmtree(cache_dir, ignore_errors=True)

            self.logger.info("RPA2 resource cleanup completed")
        except Exception as e:
            self.logger.error(f"RPA2 resource cleanup failed: {e}")

    def _cleanup_rpa3_resources(self):
        """Cleanup RPA3-specific resources"""
        self.logger.info("Cleaning up RPA3 resources")

        try:
            # Cleanup concurrent processing resources
            # This might involve stopping worker threads, closing connections, etc.

            # Cleanup shared memory or temporary processing files
            temp_processing_dir = "/tmp/rpa3_processing"
            if os.path.exists(temp_processing_dir):
                import shutil

                shutil.rmtree(temp_processing_dir, ignore_errors=True)

            self.logger.info("RPA3 resource cleanup completed")
        except Exception as e:
            self.logger.error(f"RPA3 resource cleanup failed: {e}")

    def _cleanup_temp_files(self):
        """Cleanup temporary files"""
        self.logger.info("Cleaning up temporary files")

        try:
            temp_dirs = [f"/tmp/{self.flow_name}", "/tmp/container_temp"]

            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    import shutil

                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.logger.debug(f"Cleaned up temporary directory: {temp_dir}")

            self.logger.info("Temporary file cleanup completed")
        except Exception as e:
            self.logger.error(f"Temporary file cleanup failed: {e}")

    def _cleanup_log_files(self):
        """Cleanup and rotate log files"""
        self.logger.info("Cleaning up log files")

        try:
            log_dir = "/app/logs"
            if os.path.exists(log_dir):
                # Rotate large log files
                max_size_mb = 100

                for root, _dirs, files in os.walk(log_dir):
                    for file in files:
                        if file.endswith(".log"):
                            file_path = os.path.join(root, file)
                            try:
                                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                if size_mb > max_size_mb:
                                    # Rotate the file
                                    rotated_path = f"{file_path}.{int(time.time())}"
                                    os.rename(file_path, rotated_path)
                                    self.logger.debug(
                                        f"Rotated large log file: {file_path}"
                                    )
                            except Exception:
                                pass  # Ignore individual file errors

            self.logger.info("Log file cleanup completed")
        except Exception as e:
            self.logger.error(f"Log file cleanup failed: {e}")

    def _export_final_metrics(self):
        """Export final lifecycle metrics"""
        self.logger.info("Exporting final lifecycle metrics")

        try:
            metrics_file = f"/app/logs/{self.flow_name}_lifecycle_metrics.json"
            self.lifecycle_manager.export_lifecycle_report(metrics_file)
            self.logger.info(f"Lifecycle metrics exported to {metrics_file}")
        except Exception as e:
            self.logger.error(f"Failed to export lifecycle metrics: {e}")

    def run_application_loop(self):
        """Run the main application loop based on execution mode"""
        execution_mode = os.getenv("CONTAINER_EXECUTION_MODE", "daemon")

        self.logger.info(f"Starting application loop in {execution_mode} mode")

        if execution_mode == "daemon":
            self._run_daemon_mode()
        elif execution_mode == "single":
            self._run_single_mode()
        elif execution_mode == "server":
            self._run_server_mode()
        else:
            self.logger.error(f"Unknown execution mode: {execution_mode}")
            return False

        return True

    def _run_daemon_mode(self):
        """Run in daemon mode with continuous execution"""
        execution_interval = int(os.getenv("CONTAINER_EXECUTION_INTERVAL", "300"))

        self.logger.info(f"Running in daemon mode (interval: {execution_interval}s)")

        while not self.lifecycle_manager.shutdown_requested:
            try:
                self.logger.info("Executing workflow iteration")

                # Import and run the flow workflow
                workflow_module = self._import_workflow_module()
                if workflow_module and hasattr(workflow_module, "main"):
                    workflow_module.main()
                    self.logger.info("Workflow iteration completed successfully")
                else:
                    self.logger.error("Workflow module or main function not found")

                # Wait for next execution
                self.logger.info(f"Waiting {execution_interval}s before next execution")

                # Sleep with interrupt checking
                sleep_start = time.time()
                while (
                    time.time() - sleep_start < execution_interval
                    and not self.lifecycle_manager.shutdown_requested
                ):
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in daemon mode execution: {e}")
                time.sleep(10)  # Brief pause before retry

    def _run_single_mode(self):
        """Run in single execution mode"""
        self.logger.info("Running in single execution mode")

        try:
            workflow_module = self._import_workflow_module()
            if workflow_module and hasattr(workflow_module, "main"):
                workflow_module.main()
                self.logger.info("Single execution completed successfully")
            else:
                self.logger.error("Workflow module or main function not found")
                raise RuntimeError("Workflow execution failed")
        except Exception as e:
            self.logger.error(f"Single execution failed: {e}")
            raise

    def _run_server_mode(self):
        """Run in server mode (Prefect agent)"""
        self.logger.info("Running in server mode (Prefect agent)")

        try:
            # This would start a Prefect agent
            # For now, simulate server mode
            while not self.lifecycle_manager.shutdown_requested:
                self.logger.info("Server mode running (simulated)")
                time.sleep(30)
        except Exception as e:
            self.logger.error(f"Server mode failed: {e}")
            raise

    def _import_workflow_module(self):
        """Import the workflow module for this flow"""
        try:
            import importlib

            module_name = f"flows.{self.flow_name}.workflow"
            return importlib.import_module(module_name)
        except ImportError as e:
            self.logger.error(f"Failed to import workflow module {module_name}: {e}")
            return None

    def run_with_lifecycle_management(self) -> int:
        """
        Run container with full lifecycle management including restart handling.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        self.logger.info("Starting container with lifecycle management")

        while True:
            try:
                # Setup dependency checks and cleanup handlers
                self.setup_dependency_checks()
                self.setup_cleanup_handlers()

                # Attempt startup
                if not self.lifecycle_manager.startup():
                    self.logger.error("Container startup failed")

                    # Check if we should restart
                    if self.lifecycle_manager.should_restart():
                        if self.lifecycle_manager.attempt_restart():
                            continue  # Restart successful, continue loop
                        else:
                            self.logger.error("Restart attempts exhausted")
                            return 1
                    else:
                        return 1

                # Start health monitoring in background
                import threading

                health_thread = threading.Thread(
                    target=self.lifecycle_manager.run_health_monitoring_loop,
                    daemon=True,
                )
                health_thread.start()

                # Run main application
                self.run_application_loop()

                # Normal shutdown
                self.lifecycle_manager.graceful_shutdown()
                self.logger.info("Container shutdown completed normally")
                return 0

            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal")
                self.lifecycle_manager.graceful_shutdown()
                return 0

            except Exception as e:
                self.logger.error(f"Container execution failed: {e}")

                # Check if we should restart on failure
                if self.lifecycle_manager.should_restart():
                    if self.lifecycle_manager.attempt_restart():
                        continue  # Restart successful, continue loop
                    else:
                        self.logger.error("Restart attempts exhausted after failure")
                        return 1
                else:
                    return 1

    def run_simple(self) -> int:
        """
        Run container with basic lifecycle management (no restart handling).

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            # Setup dependency checks and cleanup handlers
            self.setup_dependency_checks()
            self.setup_cleanup_handlers()

            # Startup
            if not self.lifecycle_manager.startup():
                self.logger.error("Container startup failed")
                return 1

            # Start health monitoring
            import threading

            health_thread = threading.Thread(
                target=self.lifecycle_manager.run_health_monitoring_loop, daemon=True
            )
            health_thread.start()

            # Run application
            self.run_application_loop()

            # Graceful shutdown
            self.lifecycle_manager.graceful_shutdown()
            return 0

        except Exception as e:
            self.logger.error(f"Container execution failed: {e}")
            return 1


def main():
    """Main entry point for enhanced container startup"""
    parser = argparse.ArgumentParser(
        description="Enhanced container startup with lifecycle management"
    )
    parser.add_argument("--flow-name", required=True, help="Name of the flow/container")
    parser.add_argument(
        "--container-id", help="Container ID (auto-generated if not provided)"
    )
    parser.add_argument(
        "--mode",
        choices=["simple", "managed"],
        default="managed",
        help="Startup mode: simple (no restart) or managed (with restart handling)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create and run enhanced startup
    startup = EnhancedContainerStartup(
        flow_name=args.flow_name, container_id=args.container_id
    )

    if args.mode == "managed":
        return startup.run_with_lifecycle_management()
    else:
        return startup.run_simple()


if __name__ == "__main__":
    sys.exit(main())

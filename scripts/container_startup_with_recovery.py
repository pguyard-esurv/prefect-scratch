#!/usr/bin/env python3
"""
Container startup script with comprehensive error recovery.

This script provides container startup with integrated error handling,
recovery mechanisms, health monitoring, and graceful shutdown capabilities.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import ConfigManager
from core.database import DatabaseManager
from core.error_recovery import (
    AlertManager,
    ErrorRecoveryManager,
    ErrorSeverity,
    file_alert_handler,
    log_alert_handler,
)
from core.health_monitor import HealthMonitor


class ContainerStartupManager:
    """Manages container startup with error recovery."""

    def __init__(self, flow_name: str, config_manager: Optional[ConfigManager] = None):
        """
        Initialize container startup manager.

        Args:
            flow_name: Name of the flow/container
            config_manager: Optional config manager instance
        """
        self.flow_name = flow_name
        self.config_manager = config_manager or ConfigManager()
        self.logger = self._setup_logging()

        # Initialize components
        self.database_managers = {}
        self.health_monitor = None
        self.error_recovery_manager = None
        self.shutdown_requested = False

        # Setup signal handlers
        self._setup_signal_handlers()

        self.logger.info(f"Container startup manager initialized for flow: {flow_name}")

    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging for container."""
        logger = logging.getLogger(f"container_startup_{self.flow_name}")

        if not logger.handlers:
            # Create handler
            handler = logging.StreamHandler()

            # JSON formatter for structured logging
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"component": "container_startup", "flow": "' + self.flow_name + '", '
                '"message": "%(message)s"}'
            )
            handler.setFormatter(formatter)

            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        return logger

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown_requested = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def validate_environment(self) -> bool:
        """
        Validate container environment configuration.

        Returns:
            True if environment is valid, False otherwise
        """
        self.logger.info("Validating container environment configuration")

        try:
            # Check required environment variables
            required_vars = [
                "CONTAINER_DATABASE_RPA_DB_HOST",
                "CONTAINER_DATABASE_RPA_DB_NAME",
                "CONTAINER_FLOW_NAME",
            ]

            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                self.logger.error(
                    f"Missing required environment variables: {missing_vars}"
                )
                return False

            # Validate flow name matches
            env_flow_name = os.getenv("CONTAINER_FLOW_NAME")
            if env_flow_name != self.flow_name:
                self.logger.error(
                    f"Flow name mismatch: expected {self.flow_name}, "
                    f"got {env_flow_name}"
                )
                return False

            self.logger.info("Environment validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Environment validation failed: {e}")
            return False

    def initialize_database_managers(self) -> bool:
        """
        Initialize database managers with error recovery.

        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing database managers")

        try:
            # Initialize RPA database manager
            rpa_db_manager = DatabaseManager("rpa_db")

            # Test connectivity with retry
            max_retries = 5
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    health_result = rpa_db_manager.health_check()
                    if health_result.get("status") == "healthy":
                        self.database_managers["rpa_db"] = rpa_db_manager
                        self.logger.info("RPA database connection established")
                        break
                    else:
                        raise RuntimeError(
                            f"Database health check failed: {health_result}"
                        )

                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.warning(
                            f"Database connection attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {retry_delay} seconds..."
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        self.logger.error(
                            f"Failed to connect to database after {max_retries} attempts: {e}"
                        )
                        return False

            # Initialize other database managers if configured
            survey_hub_host = os.getenv("CONTAINER_DATABASE_SURVEY_HUB_HOST")
            if survey_hub_host:
                try:
                    survey_hub_manager = DatabaseManager("SurveyHub")
                    health_result = survey_hub_manager.health_check()
                    if health_result.get("status") in ["healthy", "degraded"]:
                        self.database_managers["SurveyHub"] = survey_hub_manager
                        self.logger.info("SurveyHub database connection established")
                    else:
                        self.logger.warning(
                            "SurveyHub database connection degraded, continuing without it"
                        )
                except Exception as e:
                    self.logger.warning(f"SurveyHub database connection failed: {e}")

            return len(self.database_managers) > 0

        except Exception as e:
            self.logger.error(f"Database manager initialization failed: {e}")
            return False

    def initialize_health_monitoring(self) -> bool:
        """
        Initialize health monitoring system.

        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing health monitoring system")

        try:
            self.health_monitor = HealthMonitor(
                database_managers=self.database_managers,
                enable_prometheus=True,
                enable_structured_logging=True,
            )

            # Perform initial health check
            health_report = self.health_monitor.comprehensive_health_check()

            self.logger.info(
                f"Health monitoring initialized. Overall status: {health_report['overall_status']}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Health monitoring initialization failed: {e}")
            return False

    def initialize_error_recovery(self) -> bool:
        """
        Initialize error recovery system.

        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing error recovery system")

        try:
            # Setup alert manager with handlers
            alert_manager = AlertManager()
            alert_manager.add_alert_handler(log_alert_handler)
            alert_manager.add_alert_handler(file_alert_handler)

            # Initialize error recovery manager
            self.error_recovery_manager = ErrorRecoveryManager(
                database_managers=self.database_managers,
                local_queue_path=f"/app/data/{self.flow_name}_queue.json",
                disk_monitor_paths=["/", "/app", "/tmp", "/var/log"],
                alert_manager=alert_manager,
            )

            self.logger.info("Error recovery system initialized")
            return True

        except Exception as e:
            self.logger.error(f"Error recovery initialization failed: {e}")
            return False

    def run_startup_checks(self) -> bool:
        """
        Run comprehensive startup checks.

        Returns:
            True if all checks pass, False otherwise
        """
        self.logger.info("Running startup checks")

        checks = [
            ("Environment Validation", self.validate_environment),
            ("Database Initialization", self.initialize_database_managers),
            ("Health Monitoring", self.initialize_health_monitoring),
            ("Error Recovery", self.initialize_error_recovery),
        ]

        for check_name, check_func in checks:
            try:
                self.logger.info(f"Running check: {check_name}")

                if not check_func():
                    self.logger.error(f"Startup check failed: {check_name}")
                    return False

                self.logger.info(f"Startup check passed: {check_name}")

            except Exception as e:
                self.logger.error(f"Startup check error in {check_name}: {e}")
                return False

        self.logger.info("All startup checks passed")
        return True

    def run_maintenance_loop(self):
        """Run maintenance loop for ongoing operations."""
        self.logger.info("Starting maintenance loop")

        last_health_check = 0
        last_queue_processing = 0
        last_disk_monitoring = 0

        health_check_interval = 30  # seconds
        queue_processing_interval = 10  # seconds
        disk_monitoring_interval = 300  # seconds (5 minutes)

        while not self.shutdown_requested:
            try:
                current_time = time.time()

                # Health monitoring
                if current_time - last_health_check >= health_check_interval:
                    if self.health_monitor:
                        health_report = self.health_monitor.comprehensive_health_check()

                        if health_report["overall_status"] != "healthy":
                            self.logger.warning(
                                f"Health check status: {health_report['overall_status']}"
                            )

                    last_health_check = current_time

                # Process queued operations
                if current_time - last_queue_processing >= queue_processing_interval:
                    if self.error_recovery_manager:
                        result = self.error_recovery_manager.process_queued_operations()

                        if result["operations_processed"] > 0:
                            self.logger.info(
                                f"Processed {result['operations_processed']} queued operations"
                            )

                    last_queue_processing = current_time

                # Disk space monitoring
                if current_time - last_disk_monitoring >= disk_monitoring_interval:
                    if self.error_recovery_manager:
                        disk_result = (
                            self.error_recovery_manager.monitor_and_cleanup_disk_space()
                        )

                        if disk_result["cleanup_performed"]:
                            self.logger.info("Disk cleanup performed")

                    last_disk_monitoring = current_time

                # Sleep for a short interval
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in maintenance loop: {e}")

                if self.error_recovery_manager:
                    self.error_recovery_manager.alert_manager.send_alert(
                        ErrorSeverity.HIGH,
                        "Maintenance Loop Error",
                        f"Error in container maintenance loop: {e}",
                        {"flow_name": self.flow_name},
                    )

                # Continue running despite errors
                time.sleep(5)

    def graceful_shutdown(self):
        """Perform graceful shutdown operations."""
        self.logger.info("Starting graceful shutdown")

        try:
            # Process remaining queued operations
            if self.error_recovery_manager:
                self.logger.info("Processing remaining queued operations")
                result = self.error_recovery_manager.process_queued_operations()

                if result["operations_processed"] > 0:
                    self.logger.info(
                        f"Processed {result['operations_processed']} operations during shutdown"
                    )

            # Final health check
            if self.health_monitor:
                self.logger.info("Performing final health check")
                health_report = self.health_monitor.comprehensive_health_check()
                self.logger.info(
                    f"Final health status: {health_report['overall_status']}"
                )

            # Send shutdown alert
            if self.error_recovery_manager:
                self.error_recovery_manager.alert_manager.send_alert(
                    ErrorSeverity.MEDIUM,
                    "Container Shutdown",
                    f"Container {self.flow_name} shutting down gracefully",
                    {
                        "flow_name": self.flow_name,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            self.logger.info("Graceful shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")

    def run(self) -> int:
        """
        Run the container startup and maintenance process.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            self.logger.info(f"Starting container for flow: {self.flow_name}")

            # Run startup checks
            if not self.run_startup_checks():
                self.logger.error("Startup checks failed")
                return 1

            self.logger.info("Container startup completed successfully")

            # Send startup success alert
            if self.error_recovery_manager:
                self.error_recovery_manager.alert_manager.send_alert(
                    ErrorSeverity.LOW,
                    "Container Started",
                    f"Container {self.flow_name} started successfully",
                    {"flow_name": self.flow_name},
                )

            # Run maintenance loop
            self.run_maintenance_loop()

            # Graceful shutdown
            self.graceful_shutdown()

            return 0

        except Exception as e:
            self.logger.error(f"Container startup failed: {e}")

            # Send failure alert if possible
            if self.error_recovery_manager:
                try:
                    self.error_recovery_manager.alert_manager.send_alert(
                        ErrorSeverity.CRITICAL,
                        "Container Startup Failed",
                        f"Container {self.flow_name} startup failed: {e}",
                        {"flow_name": self.flow_name, "error": str(e)},
                    )
                except Exception:
                    pass  # Don't fail on alert failure

            return 1


def main():
    """Main entry point for container startup script."""
    parser = argparse.ArgumentParser(
        description="Container startup script with error recovery"
    )
    parser.add_argument("--flow-name", required=True, help="Name of the flow/container")
    parser.add_argument("--config-file", help="Optional configuration file path")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Initialize config manager
    config_manager = None
    if args.config_file:
        try:
            config_manager = ConfigManager()
            # Load additional config if needed
        except Exception as e:
            print(f"Failed to load config file: {e}")
            return 1

    # Create and run startup manager
    startup_manager = ContainerStartupManager(
        flow_name=args.flow_name, config_manager=config_manager
    )

    return startup_manager.run()


if __name__ == "__main__":
    sys.exit(main())

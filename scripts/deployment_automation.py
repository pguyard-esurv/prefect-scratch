#!/usr/bin/env python3
"""
Deployment Automation Scripts

This module provides automated deployment capabilities with rolling updates,
rollback functionality, and deployment validation.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from core.operational_manager import (
    DeploymentConfig,
    DeploymentStatus,
    OperationalManager,
    ScalingPolicy,
)


class DeploymentAutomation:
    """Automated deployment management"""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize deployment automation"""
        self.operational_manager = OperationalManager()
        self.config_file = config_file
        self.logger = self._setup_logging()

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        return logging.getLogger(__name__)

    def deploy_service(
        self, service_name: str, image_tag: str, config_overrides: Optional[dict] = None
    ) -> bool:
        """
        Deploy a service with automated rollback on failure

        Args:
            service_name: Name of the service to deploy
            image_tag: Docker image tag to deploy
            config_overrides: Optional configuration overrides

        Returns:
            True if deployment successful, False otherwise
        """
        try:
            # Load deployment configuration
            config = self._load_deployment_config(
                service_name, image_tag, config_overrides
            )

            self.logger.info(
                f"Starting deployment of {service_name} with image {image_tag}"
            )

            # Perform deployment
            result = self.operational_manager.deploy_containers(config)

            if result.status == DeploymentStatus.COMPLETED:
                self.logger.info(f"Deployment of {service_name} completed successfully")
                return True
            elif result.status == DeploymentStatus.ROLLED_BACK:
                self.logger.warning(
                    f"Deployment of {service_name} failed and was rolled back"
                )
                return False
            else:
                self.logger.error(
                    f"Deployment of {service_name} failed: {result.error_message}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Deployment automation failed: {str(e)}")
            return False

    def _load_deployment_config(
        self, service_name: str, image_tag: str, config_overrides: Optional[dict] = None
    ) -> DeploymentConfig:
        """Load deployment configuration for a service"""

        # Default configuration
        config_data = {
            "replicas": 1,
            "rolling_update_config": {
                "update_parallelism": 1,
                "update_delay": "10s",
                "update_failure_action": "rollback",
            },
            "health_check_config": {
                "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3,
            },
            "environment_variables": {},
            "resource_limits": {"cpu_limit": "1.0", "memory_limit": "512M"},
            "rollback_enabled": True,
            "max_rollback_attempts": 3,
        }

        # Load from config file if provided
        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file) as f:
                    file_config = json.load(f)
                    service_config = file_config.get(service_name, {})
                    config_data.update(service_config)
            except Exception as e:
                self.logger.warning(f"Failed to load config file: {str(e)}")

        # Apply overrides
        if config_overrides:
            config_data.update(config_overrides)

        return DeploymentConfig(
            service_name=service_name, image_tag=image_tag, **config_data
        )

    def deploy_all_services(self, deployment_manifest: str) -> bool:
        """
        Deploy all services from a deployment manifest

        Args:
            deployment_manifest: Path to deployment manifest file

        Returns:
            True if all deployments successful, False otherwise
        """
        try:
            with open(deployment_manifest) as f:
                manifest = json.load(f)

            services = manifest.get("services", {})
            deployment_order = manifest.get("deployment_order", list(services.keys()))

            success_count = 0
            total_count = len(deployment_order)

            for service_name in deployment_order:
                if service_name not in services:
                    self.logger.error(f"Service {service_name} not found in manifest")
                    continue

                service_config = services[service_name]
                image_tag = service_config.get("image_tag")

                if not image_tag:
                    self.logger.error(
                        f"No image_tag specified for service {service_name}"
                    )
                    continue

                self.logger.info(
                    f"Deploying service {service_name} ({success_count + 1}/{total_count})"
                )

                if self.deploy_service(service_name, image_tag, service_config):
                    success_count += 1
                    self.logger.info(f"Service {service_name} deployed successfully")
                else:
                    self.logger.error(f"Service {service_name} deployment failed")

                    # Check if we should continue on failure
                    if not manifest.get("continue_on_failure", False):
                        self.logger.error("Stopping deployment due to failure")
                        break

                # Wait between deployments if specified
                delay = manifest.get("deployment_delay", 0)
                if delay > 0:
                    self.logger.info(f"Waiting {delay} seconds before next deployment")
                    time.sleep(delay)

            self.logger.info(
                f"Deployment completed: {success_count}/{total_count} services successful"
            )
            return success_count == total_count

        except Exception as e:
            self.logger.error(f"Failed to deploy from manifest: {str(e)}")
            return False

    def rollback_service(
        self, service_name: str, target_version: Optional[str] = None
    ) -> bool:
        """
        Rollback a service to a previous version

        Args:
            service_name: Name of the service to rollback
            target_version: Specific version to rollback to (optional)

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            # Get deployment history for the service
            deployment_history = [
                d
                for d in self.operational_manager.deployment_history
                if d.service_name == service_name
                and d.status == DeploymentStatus.COMPLETED
            ]

            if not deployment_history:
                self.logger.error(
                    f"No successful deployment history found for {service_name}"
                )
                return False

            # Find target deployment
            if target_version:
                target_deployment = None
                for deployment in reversed(deployment_history):
                    if target_version in deployment.metrics.get("image_tag", ""):
                        target_deployment = deployment
                        break

                if not target_deployment:
                    self.logger.error(
                        f"Target version {target_version} not found in deployment history"
                    )
                    return False
            else:
                # Use the second most recent successful deployment
                if len(deployment_history) < 2:
                    self.logger.error(
                        f"Not enough deployment history for rollback of {service_name}"
                    )
                    return False
                target_deployment = deployment_history[-2]

            # Perform rollback deployment
            rollback_config = DeploymentConfig(
                service_name=service_name,
                image_tag=target_deployment.metrics.get("image_tag", ""),
                replicas=target_deployment.metrics.get("replicas", 1),
                rollback_enabled=False,  # Don't rollback a rollback
            )

            self.logger.info(f"Rolling back {service_name} to previous version")
            result = self.operational_manager.deploy_containers(rollback_config)

            if result.status == DeploymentStatus.COMPLETED:
                self.logger.info(f"Rollback of {service_name} completed successfully")
                return True
            else:
                self.logger.error(
                    f"Rollback of {service_name} failed: {result.error_message}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Rollback automation failed: {str(e)}")
            return False

    def validate_deployment(self, service_name: str) -> bool:
        """
        Validate a deployment by running health checks and tests

        Args:
            service_name: Name of the service to validate

        Returns:
            True if validation successful, False otherwise
        """
        try:
            self.logger.info(f"Validating deployment of {service_name}")

            # Get operational metrics
            metrics = self.operational_manager.monitor_operations()

            # Check if service exists and is healthy
            if service_name not in metrics.services:
                self.logger.error(
                    f"Service {service_name} not found in operational metrics"
                )
                return False

            service_info = metrics.services[service_name]
            service_status = service_info.get("status", "unknown")

            if service_status != "healthy":
                self.logger.error(
                    f"Service {service_name} is not healthy: {service_status}"
                )
                return False

            # Additional validation checks could be added here
            # - API endpoint tests
            # - Database connectivity tests
            # - Integration tests

            self.logger.info(f"Deployment validation of {service_name} passed")
            return True

        except Exception as e:
            self.logger.error(f"Deployment validation failed: {str(e)}")
            return False

    def setup_scaling_policies(self, scaling_config_file: str) -> bool:
        """
        Setup scaling policies from configuration file

        Args:
            scaling_config_file: Path to scaling configuration file

        Returns:
            True if setup successful, False otherwise
        """
        try:
            with open(scaling_config_file) as f:
                scaling_config = json.load(f)

            for service_name, policy_config in scaling_config.items():
                policy = ScalingPolicy(service_name=service_name, **policy_config)

                self.operational_manager.register_scaling_policy(policy)
                self.logger.info(f"Registered scaling policy for {service_name}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to setup scaling policies: {str(e)}")
            return False


def main():
    """Main entry point for deployment automation"""
    parser = argparse.ArgumentParser(description="Container Deployment Automation")
    parser.add_argument(
        "action",
        choices=["deploy", "deploy-all", "rollback", "validate", "setup-scaling"],
        help="Action to perform",
    )
    parser.add_argument("--service", help="Service name")
    parser.add_argument("--image", help="Docker image tag")
    parser.add_argument("--manifest", help="Deployment manifest file")
    parser.add_argument("--config", help="Configuration file")
    parser.add_argument("--target-version", help="Target version for rollback")
    parser.add_argument("--scaling-config", help="Scaling configuration file")

    args = parser.parse_args()

    # Initialize deployment automation
    automation = DeploymentAutomation(config_file=args.config)

    success = False

    if args.action == "deploy":
        if not args.service or not args.image:
            print("Error: --service and --image are required for deploy action")
            sys.exit(1)
        success = automation.deploy_service(args.service, args.image)

    elif args.action == "deploy-all":
        if not args.manifest:
            print("Error: --manifest is required for deploy-all action")
            sys.exit(1)
        success = automation.deploy_all_services(args.manifest)

    elif args.action == "rollback":
        if not args.service:
            print("Error: --service is required for rollback action")
            sys.exit(1)
        success = automation.rollback_service(args.service, args.target_version)

    elif args.action == "validate":
        if not args.service:
            print("Error: --service is required for validate action")
            sys.exit(1)
        success = automation.validate_deployment(args.service)

    elif args.action == "setup-scaling":
        if not args.scaling_config:
            print("Error: --scaling-config is required for setup-scaling action")
            sys.exit(1)
        success = automation.setup_scaling_policies(args.scaling_config)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

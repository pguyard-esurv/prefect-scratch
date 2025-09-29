#!/usr/bin/env python3
"""
Development Workflow Automation for Container Testing System

Provides comprehensive development workflow automation including environment setup,
container management, testing, and optimization tools.

Requirements: 4.5, 4.6, 4.7, 5.4
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import docker


class DevelopmentEnvironmentManager:
    """Manages development environment setup and configuration"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.docker_client = docker.from_env()
        self.logger = logging.getLogger(__name__)

    def setup_development_environment(self) -> dict:
        """Set up the complete development environment"""
        self.logger.info("Setting up development environment...")

        steps = [
            ("Checking Docker", self._check_docker),
            ("Building base image", self._build_base_image),
            ("Starting infrastructure", self._start_infrastructure),
            ("Waiting for services", self._wait_for_services),
            ("Running initial tests", self._run_initial_tests),
            ("Setting up file watcher", self._setup_file_watcher),
        ]

        results = {}

        for step_name, step_func in steps:
            self.logger.info(f"Executing: {step_name}")
            try:
                result = step_func()
                results[step_name] = {"status": "success", "result": result}
            except Exception as e:
                self.logger.error(f"Failed: {step_name} - {e}")
                results[step_name] = {"status": "error", "error": str(e)}
                break

        return results

    def _check_docker(self) -> dict:
        """Check Docker availability and version"""
        try:
            version = self.docker_client.version()
            return {
                "docker_version": version["Version"],
                "api_version": version["ApiVersion"],
                "available": True,
            }
        except Exception as e:
            raise Exception(f"Docker not available: {e}") from e

    def _build_base_image(self) -> dict:
        """Build the base container image"""
        try:
            # Check if base image exists and is recent
            try:
                image = self.docker_client.images.get("rpa-base:latest")
                created = datetime.fromisoformat(
                    image.attrs["Created"].replace("Z", "+00:00")
                )

                # If image is less than 1 hour old, skip rebuild
                if (datetime.now().astimezone() - created).total_seconds() < 3600:
                    return {"status": "skipped", "reason": "Recent image exists"}
            except docker.errors.ImageNotFound:
                pass

            # Build base image
            self.logger.info("Building base image...")

            result = subprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    "Dockerfile.base",
                    "-t",
                    "rpa-base:latest",
                    ".",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                raise Exception(f"Base image build failed: {result.stderr}") from None

            return {"status": "built", "output": result.stdout}

        except Exception as e:
            raise Exception(f"Failed to build base image: {e}") from e

    def _start_infrastructure(self) -> dict:
        """Start infrastructure services (PostgreSQL, Prefect)"""
        try:
            # Start infrastructure services
            result = subprocess.run(
                ["docker-compose", "up", "-d", "postgres", "prefect-server"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                raise Exception(
                    f"Failed to start infrastructure: {result.stderr}"
                ) from None

            return {"status": "started", "services": ["postgres", "prefect-server"]}

        except Exception as e:
            raise Exception(f"Failed to start infrastructure: {e}") from e

    def _wait_for_services(self) -> dict:
        """Wait for services to become healthy"""
        services = ["rpa-postgres", "rpa-prefect-server"]
        timeout = 120  # 2 minutes
        start_time = time.time()

        while time.time() - start_time < timeout:
            all_healthy = True

            for service_name in services:
                try:
                    container = self.docker_client.containers.get(service_name)

                    if container.status != "running":
                        all_healthy = False
                        break

                    # Check health if available
                    health = container.attrs.get("State", {}).get("Health", {})
                    if health and health.get("Status") != "healthy":
                        all_healthy = False
                        break

                except docker.errors.NotFound:
                    all_healthy = False
                    break

            if all_healthy:
                return {
                    "status": "healthy",
                    "services": services,
                    "wait_time": time.time() - start_time,
                }

            time.sleep(5)

        raise Exception(
            f"Services did not become healthy within {timeout} seconds"
        ) from None

    def _run_initial_tests(self) -> dict:
        """Run initial smoke tests to verify environment"""
        try:
            # Run a quick smoke test
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "pytest",
                    "core/test/test_config.py",
                    "-v",
                    "--tb=short",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output": result.stdout,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _setup_file_watcher(self) -> dict:
        """Set up file watcher for hot reloading"""
        try:
            # Start file watcher in development profile
            result = subprocess.run(
                [
                    "docker-compose",
                    "--profile",
                    "development",
                    "up",
                    "-d",
                    "file-watcher",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                self.logger.warning(f"File watcher setup failed: {result.stderr}")
                return {"status": "failed", "error": result.stderr}

            return {"status": "started", "service": "file-watcher"}

        except Exception as e:
            return {"status": "error", "error": str(e)}


class ContainerWorkflowManager:
    """Manages container-specific development workflows"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.logger = logging.getLogger(__name__)

    def rebuild_and_restart(self, flow_name: str = None) -> dict:
        """Rebuild and restart containers"""
        if flow_name:
            return self._rebuild_single_flow(flow_name)
        else:
            return self._rebuild_all_flows()

    def _rebuild_single_flow(self, flow_name: str) -> dict:
        """Rebuild and restart a single flow container"""
        try:
            container_name = f"rpa-{flow_name}-worker"
            dockerfile = f"Dockerfile.{flow_name}"
            image_name = f"rpa-{flow_name}:latest"

            # Stop container if running
            try:
                container = self.docker_client.containers.get(container_name)
                container.stop()
                self.logger.info(f"Stopped container: {container_name}")
            except docker.errors.NotFound:
                pass

            # Rebuild image
            result = subprocess.run(
                ["docker", "build", "-f", dockerfile, "-t", image_name, "."],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception(f"Build failed: {result.stderr}") from None

            # Restart container
            result = subprocess.run(
                ["docker-compose", "up", "-d", f"{flow_name}-worker"],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception(f"Restart failed: {result.stderr}") from None

            return {
                "status": "success",
                "flow": flow_name,
                "actions": ["stopped", "rebuilt", "restarted"],
            }

        except Exception as e:
            return {"status": "error", "flow": flow_name, "error": str(e)}

    def _rebuild_all_flows(self) -> dict:
        """Rebuild and restart all flow containers"""
        flows = ["rpa1", "rpa2", "rpa3"]
        results = {}

        for flow in flows:
            results[flow] = self._rebuild_single_flow(flow)

        return {
            "status": "completed",
            "flows": results,
            "success_count": sum(
                1 for r in results.values() if r["status"] == "success"
            ),
        }

    def scale_containers(self, flow_name: str, replicas: int) -> dict:
        """Scale containers for load testing"""
        try:
            result = subprocess.run(
                [
                    "docker-compose",
                    "up",
                    "-d",
                    "--scale",
                    f"{flow_name}-worker={replicas}",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise Exception(f"Scaling failed: {result.stderr}") from None

            return {"status": "success", "flow": flow_name, "replicas": replicas}

        except Exception as e:
            return {"status": "error", "flow": flow_name, "error": str(e)}

    def get_container_status(self) -> dict:
        """Get status of all RPA containers"""
        containers = {}

        try:
            for container in self.docker_client.containers.list(all=True):
                if container.name.startswith("rpa-"):
                    containers[container.name] = {
                        "status": container.status,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        "created": container.attrs["Created"],
                        "ports": container.ports,
                    }
        except Exception as e:
            self.logger.error(f"Error getting container status: {e}")

        return containers


class TestWorkflowManager:
    """Manages test execution workflows"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def run_test_workflow(self, test_type: str = "smart") -> dict:
        """Run test workflow based on type"""
        try:
            if test_type == "smart":
                return self._run_smart_tests()
            elif test_type == "full":
                return self._run_full_tests()
            elif test_type == "container":
                return self._run_container_tests()
            else:
                raise ValueError(f"Unknown test type: {test_type}") from None

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_smart_tests(self) -> dict:
        """Run smart tests using the fast test runner"""
        try:
            result = subprocess.run(
                ["python", "scripts/fast_test_runner.py", "smart"],
                capture_output=True,
                text=True,
            )

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_full_tests(self) -> dict:
        """Run full test suite"""
        try:
            result = subprocess.run(
                ["python", "scripts/fast_test_runner.py", "all"],
                capture_output=True,
                text=True,
            )

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_container_tests(self) -> dict:
        """Run container-specific tests"""
        try:
            result = subprocess.run(
                [
                    "docker-compose",
                    "run",
                    "--rm",
                    "test-runner",
                    "python",
                    "-m",
                    "pytest",
                    "core/test/test_container_*.py",
                    "-v",
                ],
                capture_output=True,
                text=True,
            )

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "passed": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}


class DevelopmentDashboard:
    """Provides a unified development dashboard"""

    def __init__(self):
        self.env_manager = DevelopmentEnvironmentManager()
        self.container_manager = ContainerWorkflowManager()
        self.test_manager = TestWorkflowManager()
        self.logger = logging.getLogger(__name__)

    def get_development_status(self) -> dict:
        """Get comprehensive development environment status"""
        return {
            "timestamp": datetime.now().isoformat(),
            "containers": self.container_manager.get_container_status(),
            "environment": self._check_environment_health(),
            "recent_activity": self._get_recent_activity(),
        }

    def _check_environment_health(self) -> dict:
        """Check overall environment health"""
        try:
            docker_client = docker.from_env()

            # Check Docker
            docker_info = docker_client.info()

            # Check key services
            services = ["rpa-postgres", "rpa-prefect-server"]
            service_status = {}

            for service in services:
                try:
                    container = docker_client.containers.get(service)
                    service_status[service] = {
                        "running": container.status == "running",
                        "healthy": self._is_container_healthy(container),
                    }
                except docker.errors.NotFound:
                    service_status[service] = {"running": False, "healthy": False}

            return {
                "docker": {
                    "available": True,
                    "containers_running": docker_info["ContainersRunning"],
                    "images": docker_info["Images"],
                },
                "services": service_status,
                "overall_health": all(
                    s["running"] and s["healthy"] for s in service_status.values()
                ),
            }

        except Exception as e:
            return {
                "docker": {"available": False, "error": str(e)},
                "overall_health": False,
            }

    def _is_container_healthy(self, container) -> bool:
        """Check if a container is healthy"""
        try:
            health = container.attrs.get("State", {}).get("Health", {})
            if health:
                return health.get("Status") == "healthy"
            else:
                # No health check configured, assume healthy if running
                return container.status == "running"
        except Exception:
            return False

    def _get_recent_activity(self) -> list[dict]:
        """Get recent development activity"""
        # This would typically read from logs or activity tracking
        # For now, return a placeholder
        return [
            {
                "timestamp": datetime.now().isoformat(),
                "type": "status_check",
                "message": "Development status checked",
            }
        ]


async def main():
    """Main CLI interface for development workflow automation"""
    parser = argparse.ArgumentParser(description="Development Workflow Automation")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Environment commands
    env_parser = subparsers.add_parser("env", help="Environment management")
    env_parser.add_argument("action", choices=["setup", "status", "reset"])

    # Container commands
    container_parser = subparsers.add_parser("containers", help="Container management")
    container_parser.add_argument(
        "action", choices=["rebuild", "restart", "scale", "status"]
    )
    container_parser.add_argument("--flow", help="Specific flow name")
    container_parser.add_argument(
        "--replicas", type=int, default=1, help="Number of replicas"
    )

    # Test commands
    test_parser = subparsers.add_parser("test", help="Test management")
    test_parser.add_argument(
        "type", choices=["smart", "full", "container"], help="Test type to run"
    )

    # Dashboard commands
    dashboard_parser = subparsers.add_parser("dashboard", help="Development dashboard")
    dashboard_parser.add_argument("action", choices=["status", "monitor"])

    # Utility commands
    util_parser = subparsers.add_parser("utils", help="Utility commands")
    util_parser.add_argument("action", choices=["logs", "debug", "cleanup"])
    util_parser.add_argument("--service", help="Service name for logs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        if args.command == "env":
            env_manager = DevelopmentEnvironmentManager()

            if args.action == "setup":
                result = env_manager.setup_development_environment()
                print(json.dumps(result, indent=2))

            elif args.action == "status":
                dashboard = DevelopmentDashboard()
                status = dashboard.get_development_status()
                print(json.dumps(status, indent=2))

            elif args.action == "reset":
                print("Environment reset not implemented yet")

        elif args.command == "containers":
            container_manager = ContainerWorkflowManager()

            if args.action == "rebuild":
                result = container_manager.rebuild_and_restart(args.flow)
                print(json.dumps(result, indent=2))

            elif args.action == "restart":
                result = container_manager.rebuild_and_restart(args.flow)
                print(json.dumps(result, indent=2))

            elif args.action == "scale":
                if not args.flow:
                    print("Error: --flow required for scale action")
                    return 1

                result = container_manager.scale_containers(args.flow, args.replicas)
                print(json.dumps(result, indent=2))

            elif args.action == "status":
                status = container_manager.get_container_status()
                print(json.dumps(status, indent=2))

        elif args.command == "test":
            test_manager = TestWorkflowManager()
            result = test_manager.run_test_workflow(args.type)
            print(json.dumps(result, indent=2))

            # Exit with test result code
            return 0 if result.get("passed", False) else 1

        elif args.command == "dashboard":
            dashboard = DevelopmentDashboard()

            if args.action == "status":
                status = dashboard.get_development_status()
                print(json.dumps(status, indent=2))

            elif args.action == "monitor":
                print("Dashboard monitoring not implemented yet")

        elif args.command == "utils":
            if args.action == "logs":
                if args.service:
                    subprocess.run(["docker-compose", "logs", "-f", args.service])
                else:
                    subprocess.run(["docker-compose", "logs", "-f"])

            elif args.action == "debug":
                subprocess.run(
                    ["python", "scripts/debug_toolkit.py", "dashboard", "status"]
                )

            elif args.action == "cleanup":
                print("Cleanup not implemented yet")

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))

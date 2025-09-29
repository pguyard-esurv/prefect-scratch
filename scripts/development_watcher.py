#!/usr/bin/env python3
"""
Development File Watcher for Container Testing System

Monitors code changes and triggers selective container rebuilding for fast development iteration.
Implements hot reloading and automatic container restart based on file change patterns.

Requirements: 4.5, 4.6, 4.7, 5.4
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import docker
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


@dataclass
class ChangeDetectionConfig:
    """Configuration for file change detection and rebuild triggers"""

    # File patterns that trigger different rebuild types
    base_image_patterns: set[str] = field(
        default_factory=lambda: {
            "core/**/*.py",
            "requirements.txt",
            "pyproject.toml",
            "Dockerfile.base",
            "scripts/setup_*.py",
        }
    )

    flow_patterns: dict[str, set[str]] = field(
        default_factory=lambda: {
            "rpa1": {"flows/rpa1/**/*.py", "Dockerfile.flow1"},
            "rpa2": {"flows/rpa2/**/*.py", "Dockerfile.flow2"},
            "rpa3": {"flows/rpa3/**/*.py", "Dockerfile.flow3"},
        }
    )

    config_patterns: set[str] = field(
        default_factory=lambda: {
            "docker-compose.yml",
            "docker-compose.override.yml",
            ".env*",
            "core/envs/**/*.env",
        }
    )

    test_patterns: set[str] = field(
        default_factory=lambda: {"**/test_*.py", "conftest.py", "core/test/**/*.py"}
    )

    # Debounce settings
    debounce_seconds: float = 2.0
    batch_rebuild_delay: float = 5.0


@dataclass
class RebuildAction:
    """Represents a rebuild action to be performed"""

    action_type: str  # "base_image", "flow_image", "restart_service", "run_tests"
    target: Optional[str] = None  # flow name for flow rebuilds
    priority: int = 0  # Lower numbers = higher priority
    timestamp: datetime = field(default_factory=datetime.now)


class DevelopmentFileWatcher(FileSystemEventHandler):
    """Watches for file changes and triggers appropriate rebuild actions"""

    def __init__(self, config: ChangeDetectionConfig):
        super().__init__()
        self.config = config
        self.docker_client = docker.from_env()
        self.pending_actions: dict[str, RebuildAction] = {}
        self.last_change_time = datetime.now()

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # Track container states
        self.container_states: dict[str, str] = {}
        self._update_container_states()

    def _update_container_states(self):
        """Update the current state of all containers"""
        try:
            containers = self.docker_client.containers.list(all=True)
            for container in containers:
                if container.name.startswith("rpa-"):
                    self.container_states[container.name] = container.status
        except Exception as e:
            self.logger.error(f"Failed to update container states: {e}")

    def _matches_pattern(self, file_path: str, patterns: set[str]) -> bool:
        """Check if file path matches any of the given patterns"""
        from fnmatch import fnmatch

        for pattern in patterns:
            if fnmatch(file_path, pattern):
                return True
        return False

    def _determine_rebuild_actions(self, file_path: str) -> list[RebuildAction]:
        """Determine what rebuild actions are needed for a changed file"""
        actions = []

        # Check for base image changes (highest priority)
        if self._matches_pattern(file_path, self.config.base_image_patterns):
            actions.append(RebuildAction(action_type="base_image", priority=1))
            # Base image changes require all flow images to be rebuilt
            for flow_name in self.config.flow_patterns.keys():
                actions.append(
                    RebuildAction(
                        action_type="flow_image", target=flow_name, priority=2
                    )
                )

        # Check for flow-specific changes
        for flow_name, patterns in self.config.flow_patterns.items():
            if self._matches_pattern(file_path, patterns):
                actions.append(
                    RebuildAction(
                        action_type="flow_image", target=flow_name, priority=3
                    )
                )

        # Check for configuration changes
        if self._matches_pattern(file_path, self.config.config_patterns):
            actions.append(RebuildAction(action_type="restart_services", priority=4))

        # Check for test changes
        if self._matches_pattern(file_path, self.config.test_patterns):
            actions.append(RebuildAction(action_type="run_tests", priority=5))

        return actions

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        self._handle_file_change(event.src_path)

    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return

        self._handle_file_change(event.src_path)

    def _handle_file_change(self, file_path: str):
        """Process a file change and queue appropriate actions"""
        # Convert to relative path
        try:
            rel_path = os.path.relpath(file_path)
        except ValueError:
            return

        # Skip temporary files and hidden files
        if any(part.startswith(".") for part in Path(rel_path).parts):
            return
        if rel_path.endswith((".tmp", ".swp", ".pyc", "__pycache__")):
            return

        self.logger.info(f"File changed: {rel_path}")

        # Determine required actions
        actions = self._determine_rebuild_actions(rel_path)

        # Queue actions (deduplicate by action key)
        for action in actions:
            action_key = f"{action.action_type}:{action.target or 'all'}"

            # Only update if this is a higher priority action or newer
            if (
                action_key not in self.pending_actions
                or action.priority < self.pending_actions[action_key].priority
            ):
                self.pending_actions[action_key] = action

        self.last_change_time = datetime.now()

        # Schedule batch processing
        asyncio.create_task(self._process_pending_actions())

    async def _process_pending_actions(self):
        """Process pending actions after debounce period"""
        # Wait for debounce period
        await asyncio.sleep(self.config.debounce_seconds)

        # Check if more changes occurred during debounce
        if datetime.now() - self.last_change_time < timedelta(
            seconds=self.config.debounce_seconds
        ):
            return  # More changes coming, wait longer

        if not self.pending_actions:
            return

        self.logger.info(f"Processing {len(self.pending_actions)} pending actions")

        # Sort actions by priority
        sorted_actions = sorted(self.pending_actions.values(), key=lambda x: x.priority)

        # Execute actions
        for action in sorted_actions:
            try:
                await self._execute_action(action)
            except Exception as e:
                self.logger.error(f"Failed to execute action {action.action_type}: {e}")

        # Clear processed actions
        self.pending_actions.clear()

    async def _execute_action(self, action: RebuildAction):
        """Execute a specific rebuild action"""
        self.logger.info(
            f"Executing action: {action.action_type} (target: {action.target})"
        )

        if action.action_type == "base_image":
            await self._rebuild_base_image()

        elif action.action_type == "flow_image":
            await self._rebuild_flow_image(action.target)

        elif action.action_type == "restart_services":
            await self._restart_services()

        elif action.action_type == "run_tests":
            await self._run_tests()

    async def _rebuild_base_image(self):
        """Rebuild the base container image"""
        self.logger.info("Rebuilding base image...")

        try:
            # Build base image
            process = await asyncio.create_subprocess_exec(
                "docker",
                "build",
                "-f",
                "Dockerfile.base",
                "-t",
                "rpa-base:latest",
                ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info("Base image rebuilt successfully")
            else:
                self.logger.error(f"Base image rebuild failed: {stderr.decode()}")

        except Exception as e:
            self.logger.error(f"Error rebuilding base image: {e}")

    async def _rebuild_flow_image(self, flow_name: str):
        """Rebuild a specific flow container image"""
        self.logger.info(f"Rebuilding {flow_name} image...")

        try:
            dockerfile = f"Dockerfile.{flow_name}"
            image_name = f"rpa-{flow_name}:latest"

            # Build flow image
            process = await asyncio.create_subprocess_exec(
                "docker",
                "build",
                "-f",
                dockerfile,
                "-t",
                image_name,
                ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info(f"{flow_name} image rebuilt successfully")

                # Restart the corresponding container
                await self._restart_container(f"rpa-{flow_name}-worker")
            else:
                self.logger.error(
                    f"{flow_name} image rebuild failed: {stderr.decode()}"
                )

        except Exception as e:
            self.logger.error(f"Error rebuilding {flow_name} image: {e}")

    async def _restart_container(self, container_name: str):
        """Restart a specific container"""
        try:
            container = self.docker_client.containers.get(container_name)

            self.logger.info(f"Restarting container: {container_name}")
            container.restart()

            # Wait for container to be healthy
            await self._wait_for_container_health(container_name)

        except docker.errors.NotFound:
            self.logger.warning(f"Container {container_name} not found")
        except Exception as e:
            self.logger.error(f"Error restarting container {container_name}: {e}")

    async def _wait_for_container_health(self, container_name: str, timeout: int = 60):
        """Wait for a container to become healthy"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                container = self.docker_client.containers.get(container_name)

                if container.status == "running":
                    # Check health if health check is configured
                    health = container.attrs.get("State", {}).get("Health", {})
                    if health:
                        if health.get("Status") == "healthy":
                            self.logger.info(f"Container {container_name} is healthy")
                            return
                    else:
                        # No health check configured, assume healthy if running
                        self.logger.info(f"Container {container_name} is running")
                        return

                await asyncio.sleep(2)

            except Exception as e:
                self.logger.error(f"Error checking container health: {e}")
                await asyncio.sleep(2)

        self.logger.warning(
            f"Container {container_name} did not become healthy within {timeout}s"
        )

    async def _restart_services(self):
        """Restart all services to pick up configuration changes"""
        self.logger.info("Restarting services for configuration changes...")

        try:
            # Use docker-compose to restart services
            process = await asyncio.create_subprocess_exec(
                "docker-compose",
                "restart",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info("Services restarted successfully")
            else:
                self.logger.error(f"Service restart failed: {stderr.decode()}")

        except Exception as e:
            self.logger.error(f"Error restarting services: {e}")

    async def _run_tests(self):
        """Run tests in response to test file changes"""
        self.logger.info("Running tests...")

        try:
            # Run tests using the test-runner service
            process = await asyncio.create_subprocess_exec(
                "docker-compose",
                "run",
                "--rm",
                "test-runner",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.logger.info("Tests completed successfully")
                print(stdout.decode())
            else:
                self.logger.error("Tests failed")
                print(stderr.decode())

        except Exception as e:
            self.logger.error(f"Error running tests: {e}")


class DevelopmentWorkflowManager:
    """Manages the overall development workflow and file watching"""

    def __init__(self, watch_path: str = "."):
        self.watch_path = Path(watch_path).resolve()
        self.config = ChangeDetectionConfig()
        self.observer = Observer()
        self.event_handler = DevelopmentFileWatcher(self.config)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def start_watching(self):
        """Start watching for file changes"""
        self.logger.info(f"Starting development file watcher on {self.watch_path}")

        # Setup file system observer
        self.observer.schedule(self.event_handler, str(self.watch_path), recursive=True)

        self.observer.start()

        try:
            # Keep the watcher running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Stopping development file watcher...")
            self.observer.stop()

        self.observer.join()

    def generate_status_report(self) -> dict:
        """Generate a status report of the development environment"""
        try:
            docker_client = docker.from_env()
            containers = docker_client.containers.list(all=True)

            container_status = {}
            for container in containers:
                if container.name.startswith("rpa-"):
                    container_status[container.name] = {
                        "status": container.status,
                        "image": (
                            container.image.tags[0]
                            if container.image.tags
                            else "unknown"
                        ),
                        "created": container.attrs["Created"],
                        "ports": container.ports,
                    }

            return {
                "timestamp": datetime.now().isoformat(),
                "containers": container_status,
                "watcher_config": {
                    "watch_path": str(self.watch_path),
                    "debounce_seconds": self.config.debounce_seconds,
                    "patterns": {
                        "base_image": list(self.config.base_image_patterns),
                        "flows": {
                            k: list(v) for k, v in self.config.flow_patterns.items()
                        },
                        "config": list(self.config.config_patterns),
                        "tests": list(self.config.test_patterns),
                    },
                },
            }

        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


async def main():
    """Main entry point for the development watcher"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Development File Watcher for Container Testing System"
    )
    parser.add_argument("--watch-path", default=".", help="Path to watch for changes")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--config", help="Path to configuration file")

    args = parser.parse_args()

    manager = DevelopmentWorkflowManager(args.watch_path)

    if args.status:
        status = manager.generate_status_report()
        print(json.dumps(status, indent=2))
        return

    # Start watching for changes
    manager.start_watching()


if __name__ == "__main__":
    asyncio.run(main())

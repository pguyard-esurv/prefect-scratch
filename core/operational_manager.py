"""
Operational Manager for Container Lifecycle Management

This module provides comprehensive operational management capabilities for the container
testing system, including deployment automation, scaling policies, monitoring, and
incident response.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

import docker
from docker.models.services import Service


class DeploymentStatus(Enum):
    """Deployment status enumeration"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ScalingDirection(Enum):
    """Scaling direction enumeration"""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class IncidentSeverity(Enum):
    """Incident severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DeploymentConfig:
    """Configuration for container deployment"""

    service_name: str
    image_tag: str
    replicas: int = 1
    rolling_update_config: dict[str, Any] = field(default_factory=dict)
    health_check_config: dict[str, Any] = field(default_factory=dict)
    environment_variables: dict[str, str] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)
    rollback_enabled: bool = True
    max_rollback_attempts: int = 3


@dataclass
class DeploymentResult:
    """Result of a deployment operation"""

    deployment_id: str
    status: DeploymentStatus
    service_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_performed: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScalingPolicy:
    """Configuration for horizontal scaling policies"""

    service_name: str
    min_replicas: int = 1
    max_replicas: int = 10
    target_cpu_utilization: float = 70.0
    target_memory_utilization: float = 80.0
    scale_up_threshold: float = 85.0
    scale_down_threshold: float = 30.0
    cooldown_period: int = 300  # seconds
    scale_up_step: int = 1
    scale_down_step: int = 1


@dataclass
class ScalingResult:
    """Result of a scaling operation"""

    scaling_id: str
    service_name: str
    direction: ScalingDirection
    previous_replicas: int
    new_replicas: int
    timestamp: datetime
    reason: str
    success: bool
    error_message: Optional[str] = None


@dataclass
class OperationalMetrics:
    """Operational metrics for monitoring"""

    timestamp: datetime
    services: dict[str, dict[str, Any]]
    resource_utilization: dict[str, float]
    deployment_history: list[DeploymentResult]
    scaling_history: list[ScalingResult]
    incident_count: int
    uptime_percentage: float


@dataclass
class Incident:
    """Incident information"""

    incident_id: str
    service_name: str
    severity: IncidentSeverity
    description: str
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    actions_taken: list[str] = field(default_factory=list)


@dataclass
class IncidentResponse:
    """Response to an incident"""

    incident_id: str
    actions_performed: list[str]
    resolution_successful: bool
    resolution_time: datetime
    follow_up_required: bool = False
    escalation_needed: bool = False


class OperationalManager:
    """
    Manages container operations including deployment, scaling, monitoring, and incident response.

    This class provides comprehensive operational management capabilities for containerized
    applications, supporting rolling deployments, automatic scaling, health monitoring,
    and automated incident response.
    """

    def __init__(self, docker_client: Optional[docker.DockerClient] = None):
        """Initialize the operational manager"""
        self.docker_client = docker_client or docker.from_env()
        self.logger = logging.getLogger(__name__)
        self.deployment_history: list[DeploymentResult] = []
        self.scaling_history: list[ScalingResult] = []
        self.active_incidents: dict[str, Incident] = {}
        self.scaling_policies: dict[str, ScalingPolicy] = {}
        self.incident_handlers: dict[str, Callable] = {}
        self._setup_default_incident_handlers()

    def _setup_default_incident_handlers(self):
        """Setup default incident response handlers"""
        self.incident_handlers.update(
            {
                "container_crash": self._handle_container_crash,
                "high_cpu_usage": self._handle_high_cpu_usage,
                "high_memory_usage": self._handle_high_memory_usage,
                "service_unavailable": self._handle_service_unavailable,
                "deployment_failure": self._handle_deployment_failure,
            }
        )

    def deploy_containers(self, config: DeploymentConfig) -> DeploymentResult:
        """
        Deploy containers with rolling updates and rollback capabilities

        Args:
            config: Deployment configuration

        Returns:
            DeploymentResult with deployment status and metrics
        """
        deployment_id = f"deploy_{config.service_name}_{int(time.time())}"
        start_time = datetime.now()

        result = DeploymentResult(
            deployment_id=deployment_id,
            status=DeploymentStatus.PENDING,
            service_name=config.service_name,
            start_time=start_time,
        )

        try:
            self.logger.info(
                f"Starting deployment {deployment_id} for service {config.service_name}"
            )
            result.status = DeploymentStatus.IN_PROGRESS

            # Get current service state for potential rollback
            current_service = self._get_service_info(config.service_name)

            # Perform rolling update
            success = self._perform_rolling_update(config, result)

            if success:
                # Validate deployment health
                if self._validate_deployment_health(config):
                    result.status = DeploymentStatus.COMPLETED
                    result.end_time = datetime.now()
                    self.logger.info(
                        f"Deployment {deployment_id} completed successfully"
                    )
                else:
                    # Health check failed, initiate rollback
                    if config.rollback_enabled and current_service:
                        self.logger.warning(
                            f"Health check failed for {deployment_id}, initiating rollback"
                        )
                        rollback_success = self._perform_rollback(
                            config, current_service
                        )
                        result.rollback_performed = True
                        result.status = (
                            DeploymentStatus.ROLLED_BACK
                            if rollback_success
                            else DeploymentStatus.FAILED
                        )
                    else:
                        result.status = DeploymentStatus.FAILED
                        result.error_message = (
                            "Health check failed and rollback disabled"
                        )
            else:
                result.status = DeploymentStatus.FAILED
                result.error_message = "Rolling update failed"

        except Exception as e:
            self.logger.error(f"Deployment {deployment_id} failed: {str(e)}")
            result.status = DeploymentStatus.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()

            # Attempt rollback on failure
            if config.rollback_enabled:
                try:
                    current_service = self._get_service_info(config.service_name)
                    if current_service:
                        self._perform_rollback(config, current_service)
                        result.rollback_performed = True
                except Exception as rollback_error:
                    self.logger.error(
                        f"Rollback failed for {deployment_id}: {str(rollback_error)}"
                    )

        self.deployment_history.append(result)
        return result

    def _perform_rolling_update(
        self, config: DeploymentConfig, result: DeploymentResult
    ) -> bool:
        """Perform rolling update of containers"""
        try:
            # Check if service exists
            try:
                service = self.docker_client.services.get(config.service_name)
                # Update existing service
                service.update(
                    image=config.image_tag,
                    env=[
                        f"{k}={v}" for k, v in config.environment_variables.items()
                    ],
                    **config.rolling_update_config,
                )
            except docker.errors.NotFound:
                # Create new service
                self.docker_client.services.create(
                    image=config.image_tag,
                    name=config.service_name,
                    replicas=config.replicas,
                    env=[
                        f"{k}={v}" for k, v in config.environment_variables.items()
                    ],
                    **config.resource_limits,
                )

            # Wait for update to complete
            return self._wait_for_service_update(config.service_name, timeout=600)

        except Exception as e:
            self.logger.error(f"Rolling update failed: {str(e)}")
            return False

    def _validate_deployment_health(self, config: DeploymentConfig) -> bool:
        """Validate deployment health after update"""
        try:
            service = self.docker_client.services.get(config.service_name)
            tasks = service.tasks()

            # Check if all tasks are running
            running_tasks = [
                task
                for task in tasks
                if task.get("Status", {}).get("State") == "running"
            ]

            if len(running_tasks) < config.replicas:
                return False

            # Perform health checks if configured
            if config.health_check_config:
                return self._perform_health_checks(config)

            return True

        except Exception as e:
            self.logger.error(f"Health validation failed: {str(e)}")
            return False

    def _perform_health_checks(self, config: DeploymentConfig) -> bool:
        """Perform configured health checks"""
        # Implementation would depend on specific health check configuration
        # For now, return True as placeholder
        return True

    def _perform_rollback(
        self, config: DeploymentConfig, previous_service_info: dict
    ) -> bool:
        """Perform rollback to previous service state"""
        try:
            service = self.docker_client.services.get(config.service_name)
            service.update(
                image=previous_service_info.get("image"),
                env=previous_service_info.get("env", []),
            )

            return self._wait_for_service_update(config.service_name, timeout=300)

        except Exception as e:
            self.logger.error(f"Rollback failed: {str(e)}")
            return False

    def _get_service_info(self, service_name: str) -> Optional[dict]:
        """Get current service information for rollback purposes"""
        try:
            service = self.docker_client.services.get(service_name)
            attrs = service.attrs
            return {
                "image": attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"],
                "env": attrs["Spec"]["TaskTemplate"]["ContainerSpec"].get("Env", []),
            }
        except docker.errors.NotFound:
            return None
        except Exception as e:
            self.logger.error(f"Failed to get service info: {str(e)}")
            return None

    def _wait_for_service_update(self, service_name: str, timeout: int = 300) -> bool:
        """Wait for service update to complete"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                service = self.docker_client.services.get(service_name)
                tasks = service.tasks()

                # Check if update is complete
                if all(
                    task.get("Status", {}).get("State") in ["running", "complete"]
                    for task in tasks
                ):
                    return True

                time.sleep(5)

            except Exception as e:
                self.logger.error(f"Error waiting for service update: {str(e)}")
                return False

        return False

    def scale_containers(self, scaling_policy: ScalingPolicy) -> ScalingResult:
        """
        Scale containers based on scaling policy and current metrics

        Args:
            scaling_policy: Scaling policy configuration

        Returns:
            ScalingResult with scaling operation details
        """
        scaling_id = f"scale_{scaling_policy.service_name}_{int(time.time())}"
        timestamp = datetime.now()

        try:
            # Get current service state
            service = self.docker_client.services.get(scaling_policy.service_name)
            current_replicas = service.attrs["Spec"]["Mode"]["Replicated"]["Replicas"]

            # Get current metrics
            metrics = self._get_service_metrics(scaling_policy.service_name)
            cpu_usage = metrics.get("cpu_usage", 0)
            memory_usage = metrics.get("memory_usage", 0)

            # Determine scaling decision
            scaling_decision = self._determine_scaling_action(
                scaling_policy, current_replicas, cpu_usage, memory_usage
            )

            if scaling_decision["action"] == ScalingDirection.STABLE:
                return ScalingResult(
                    scaling_id=scaling_id,
                    service_name=scaling_policy.service_name,
                    direction=ScalingDirection.STABLE,
                    previous_replicas=current_replicas,
                    new_replicas=current_replicas,
                    timestamp=timestamp,
                    reason="No scaling needed",
                    success=True,
                )

            # Perform scaling
            new_replicas = scaling_decision["new_replicas"]
            service.update(mode={"Replicated": {"Replicas": new_replicas}})

            # Wait for scaling to complete
            success = self._wait_for_service_update(scaling_policy.service_name)

            result = ScalingResult(
                scaling_id=scaling_id,
                service_name=scaling_policy.service_name,
                direction=scaling_decision["action"],
                previous_replicas=current_replicas,
                new_replicas=new_replicas,
                timestamp=timestamp,
                reason=scaling_decision["reason"],
                success=success,
            )

            if success:
                self.logger.info(
                    f"Scaling {scaling_id} completed: {current_replicas} -> {new_replicas}"
                )
            else:
                result.error_message = "Scaling operation timed out"
                self.logger.error(f"Scaling {scaling_id} failed: timeout")

            self.scaling_history.append(result)
            return result

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Scaling {scaling_id} failed: {error_msg}")

            result = ScalingResult(
                scaling_id=scaling_id,
                service_name=scaling_policy.service_name,
                direction=ScalingDirection.STABLE,
                previous_replicas=0,
                new_replicas=0,
                timestamp=timestamp,
                reason="Scaling failed",
                success=False,
                error_message=error_msg,
            )

            self.scaling_history.append(result)
            return result

    def _determine_scaling_action(
        self,
        policy: ScalingPolicy,
        current_replicas: int,
        cpu_usage: float,
        memory_usage: float,
    ) -> dict[str, Any]:
        """Determine what scaling action to take based on current metrics"""

        # Check if we need to scale up
        if (
            cpu_usage > policy.scale_up_threshold
            or memory_usage > policy.scale_up_threshold
        ):

            if current_replicas < policy.max_replicas:
                new_replicas = min(
                    current_replicas + policy.scale_up_step, policy.max_replicas
                )
                return {
                    "action": ScalingDirection.UP,
                    "new_replicas": new_replicas,
                    "reason": f"High resource usage: CPU={cpu_usage}%, Memory={memory_usage}%",
                }

        # Check if we need to scale down
        elif (
            cpu_usage < policy.scale_down_threshold
            and memory_usage < policy.scale_down_threshold
        ):

            if current_replicas > policy.min_replicas:
                new_replicas = max(
                    current_replicas - policy.scale_down_step, policy.min_replicas
                )
                return {
                    "action": ScalingDirection.DOWN,
                    "new_replicas": new_replicas,
                    "reason": f"Low resource usage: CPU={cpu_usage}%, Memory={memory_usage}%",
                }

        return {
            "action": ScalingDirection.STABLE,
            "new_replicas": current_replicas,
            "reason": f"Resource usage within thresholds: CPU={cpu_usage}%, Memory={memory_usage}%",
        }

    def _get_service_metrics(self, service_name: str) -> dict[str, float]:
        """Get current service metrics for scaling decisions"""
        try:
            # This would integrate with monitoring system (Prometheus, etc.)
            # For now, return mock metrics
            return {
                "cpu_usage": 50.0,  # Placeholder
                "memory_usage": 60.0,  # Placeholder
            }
        except Exception as e:
            self.logger.error(f"Failed to get metrics for {service_name}: {str(e)}")
            return {"cpu_usage": 0.0, "memory_usage": 0.0}

    def register_scaling_policy(self, policy: ScalingPolicy):
        """Register a scaling policy for a service"""
        self.scaling_policies[policy.service_name] = policy
        self.logger.info(f"Registered scaling policy for {policy.service_name}")

    def monitor_operations(self) -> OperationalMetrics:
        """
        Monitor operational metrics across all services

        Returns:
            OperationalMetrics with current system state
        """
        timestamp = datetime.now()

        try:
            # Get service information
            services = {}
            for service in self.docker_client.services.list():
                service_name = service.name
                services[service_name] = {
                    "replicas": service.attrs["Spec"]["Mode"]["Replicated"]["Replicas"],
                    "image": service.attrs["Spec"]["TaskTemplate"]["ContainerSpec"][
                        "Image"
                    ],
                    "status": self._get_service_status(service),
                    "metrics": self._get_service_metrics(service_name),
                }

            # Calculate resource utilization
            resource_utilization = self._calculate_resource_utilization(services)

            # Calculate uptime percentage
            uptime_percentage = self._calculate_uptime_percentage()

            return OperationalMetrics(
                timestamp=timestamp,
                services=services,
                resource_utilization=resource_utilization,
                deployment_history=self.deployment_history[-10:],  # Last 10 deployments
                scaling_history=self.scaling_history[
                    -10:
                ],  # Last 10 scaling operations
                incident_count=len(self.active_incidents),
                uptime_percentage=uptime_percentage,
            )

        except Exception as e:
            self.logger.error(f"Failed to collect operational metrics: {str(e)}")
            return OperationalMetrics(
                timestamp=timestamp,
                services={},
                resource_utilization={},
                deployment_history=[],
                scaling_history=[],
                incident_count=0,
                uptime_percentage=0.0,
            )

    def _get_service_status(self, service: Service) -> str:
        """Get the current status of a service"""
        try:
            tasks = service.tasks()
            if not tasks:
                return "no_tasks"

            running_tasks = [
                t for t in tasks if t.get("Status", {}).get("State") == "running"
            ]
            total_tasks = len(tasks)

            if len(running_tasks) == total_tasks:
                return "healthy"
            elif len(running_tasks) > 0:
                return "degraded"
            else:
                return "unhealthy"

        except Exception:
            return "unknown"

    def _calculate_resource_utilization(self, services: dict) -> dict[str, float]:
        """Calculate overall resource utilization"""
        total_cpu = 0.0
        total_memory = 0.0
        service_count = len(services)

        if service_count == 0:
            return {"cpu": 0.0, "memory": 0.0}

        for service_info in services.values():
            metrics = service_info.get("metrics", {})
            total_cpu += metrics.get("cpu_usage", 0.0)
            total_memory += metrics.get("memory_usage", 0.0)

        return {
            "cpu": total_cpu / service_count,
            "memory": total_memory / service_count,
        }

    def _calculate_uptime_percentage(self) -> float:
        """Calculate system uptime percentage"""
        # This would integrate with monitoring system
        # For now, return a placeholder value
        return 99.5

    def handle_incidents(self, incident: Incident) -> IncidentResponse:
        """
        Handle incidents with automated response

        Args:
            incident: Incident information

        Returns:
            IncidentResponse with actions taken
        """
        self.logger.warning(
            f"Handling incident {incident.incident_id}: {incident.description}"
        )

        # Store incident
        self.active_incidents[incident.incident_id] = incident

        # Determine incident type and get appropriate handler
        incident_type = self._classify_incident(incident)
        handler = self.incident_handlers.get(
            incident_type, self._handle_generic_incident
        )

        try:
            # Execute incident response
            response = handler(incident)

            # Update incident status if resolved
            if response.resolution_successful:
                incident.resolved = True
                incident.resolution_time = datetime.now()
                if incident.incident_id in self.active_incidents:
                    del self.active_incidents[incident.incident_id]

            self.logger.info(
                f"Incident {incident.incident_id} handled: {response.resolution_successful}"
            )
            return response

        except Exception as e:
            self.logger.error(
                f"Failed to handle incident {incident.incident_id}: {str(e)}"
            )
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=[f"Error handling incident: {str(e)}"],
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

    def _classify_incident(self, incident: Incident) -> str:
        """Classify incident type for appropriate handling"""
        description_lower = incident.description.lower()

        if "crash" in description_lower or "exit" in description_lower:
            return "container_crash"
        elif "cpu" in description_lower and "high" in description_lower:
            return "high_cpu_usage"
        elif "memory" in description_lower and "high" in description_lower:
            return "high_memory_usage"
        elif "unavailable" in description_lower or "unreachable" in description_lower:
            return "service_unavailable"
        elif "deployment" in description_lower and "fail" in description_lower:
            return "deployment_failure"
        else:
            return "generic"

    def _handle_container_crash(self, incident: Incident) -> IncidentResponse:
        """Handle container crash incidents"""
        actions = []

        try:
            # Restart the service
            service = self.docker_client.services.get(incident.service_name)
            service.update(force_update=True)
            actions.append(f"Restarted service {incident.service_name}")

            # Wait for service to be healthy
            if self._wait_for_service_update(incident.service_name, timeout=120):
                actions.append("Service restart successful")
                return IncidentResponse(
                    incident_id=incident.incident_id,
                    actions_performed=actions,
                    resolution_successful=True,
                    resolution_time=datetime.now(),
                )
            else:
                actions.append("Service restart timed out")
                return IncidentResponse(
                    incident_id=incident.incident_id,
                    actions_performed=actions,
                    resolution_successful=False,
                    resolution_time=datetime.now(),
                    escalation_needed=True,
                )

        except Exception as e:
            actions.append(f"Failed to restart service: {str(e)}")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

    def _handle_high_cpu_usage(self, incident: Incident) -> IncidentResponse:
        """Handle high CPU usage incidents"""
        actions = []

        try:
            # Check if scaling policy exists
            if incident.service_name in self.scaling_policies:
                policy = self.scaling_policies[incident.service_name]
                scaling_result = self.scale_containers(policy)

                if (
                    scaling_result.success
                    and scaling_result.direction == ScalingDirection.UP
                ):
                    actions.append(f"Scaled up service {incident.service_name}")
                    return IncidentResponse(
                        incident_id=incident.incident_id,
                        actions_performed=actions,
                        resolution_successful=True,
                        resolution_time=datetime.now(),
                    )

            actions.append("No scaling policy available or scaling failed")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                follow_up_required=True,
            )

        except Exception as e:
            actions.append(f"Failed to handle high CPU usage: {str(e)}")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

    def _handle_high_memory_usage(self, incident: Incident) -> IncidentResponse:
        """Handle high memory usage incidents"""
        # Similar to CPU handling but with memory-specific actions
        return self._handle_high_cpu_usage(incident)  # Reuse logic for now

    def _handle_service_unavailable(self, incident: Incident) -> IncidentResponse:
        """Handle service unavailable incidents"""
        actions = []

        try:
            # Check service status
            service = self.docker_client.services.get(incident.service_name)
            tasks = service.tasks()

            unhealthy_tasks = [
                t for t in tasks if t.get("Status", {}).get("State") != "running"
            ]

            if unhealthy_tasks:
                # Force update to restart unhealthy tasks
                service.update(force_update=True)
                actions.append(f"Forced update for service {incident.service_name}")

                if self._wait_for_service_update(incident.service_name, timeout=180):
                    actions.append("Service recovery successful")
                    return IncidentResponse(
                        incident_id=incident.incident_id,
                        actions_performed=actions,
                        resolution_successful=True,
                        resolution_time=datetime.now(),
                    )

            actions.append("Service recovery failed or timed out")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

        except Exception as e:
            actions.append(f"Failed to handle service unavailable: {str(e)}")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

    def _handle_deployment_failure(self, incident: Incident) -> IncidentResponse:
        """Handle deployment failure incidents"""
        actions = []

        try:
            # Check recent deployment history for this service
            recent_deployments = [
                d
                for d in self.deployment_history
                if d.service_name == incident.service_name
                and d.start_time > datetime.now() - timedelta(hours=1)
            ]

            if recent_deployments:
                latest_deployment = recent_deployments[-1]

                if (
                    latest_deployment.status == DeploymentStatus.FAILED
                    and not latest_deployment.rollback_performed
                ):
                    # Attempt manual rollback
                    actions.append("Attempting manual rollback")
                    # Implementation would depend on stored previous state

            actions.append("Deployment failure handled")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,  # Manual intervention likely needed
                resolution_time=datetime.now(),
                follow_up_required=True,
            )

        except Exception as e:
            actions.append(f"Failed to handle deployment failure: {str(e)}")
            return IncidentResponse(
                incident_id=incident.incident_id,
                actions_performed=actions,
                resolution_successful=False,
                resolution_time=datetime.now(),
                escalation_needed=True,
            )

    def _handle_generic_incident(self, incident: Incident) -> IncidentResponse:
        """Handle generic incidents that don't match specific patterns"""
        actions = ["Logged incident for manual review"]

        return IncidentResponse(
            incident_id=incident.incident_id,
            actions_performed=actions,
            resolution_successful=False,
            resolution_time=datetime.now(),
            follow_up_required=True,
        )

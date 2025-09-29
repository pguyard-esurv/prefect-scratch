"""
Unit tests for OperationalManager

Tests the operational management functionality including deployment automation,
scaling policies, incident response, and monitoring capabilities.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from core.operational_manager import (
    DeploymentConfig,
    DeploymentStatus,
    Incident,
    IncidentSeverity,
    OperationalManager,
    OperationalMetrics,
    ScalingDirection,
    ScalingPolicy,
)


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing"""
    client = Mock()

    # Mock service
    mock_service = Mock()
    mock_service.name = "test-service"
    mock_service.attrs = {
        "Spec": {
            "Mode": {"Replicated": {"Replicas": 2}},
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": "test-image:latest",
                    "Env": ["VAR1=value1", "VAR2=value2"],
                }
            },
        }
    }
    mock_service.tasks.return_value = [
        {"Status": {"State": "running"}},
        {"Status": {"State": "running"}},
    ]
    mock_service.update = Mock()

    client.services.get.return_value = mock_service
    client.services.list.return_value = [mock_service]
    client.services.create = Mock()

    return client


@pytest.fixture
def operational_manager(mock_docker_client):
    """Create OperationalManager instance with mocked dependencies"""
    return OperationalManager(docker_client=mock_docker_client)


@pytest.fixture
def deployment_config():
    """Sample deployment configuration"""
    return DeploymentConfig(
        service_name="test-service",
        image_tag="test-image:v1.0.0",
        replicas=2,
        rolling_update_config={"update_parallelism": 1, "update_delay": "10s"},
        environment_variables={"ENV_VAR": "test_value"},
        rollback_enabled=True,
    )


@pytest.fixture
def scaling_policy():
    """Sample scaling policy"""
    return ScalingPolicy(
        service_name="test-service",
        min_replicas=1,
        max_replicas=5,
        target_cpu_utilization=70.0,
        scale_up_threshold=85.0,
        scale_down_threshold=30.0,
    )


class TestDeploymentOperations:
    """Test deployment operations"""

    def test_successful_deployment(
        self, operational_manager, deployment_config, mock_docker_client
    ):
        """Test successful container deployment"""
        # Mock successful service update
        mock_docker_client.services.get.return_value.update = Mock()

        # Mock health validation
        with patch.object(
            operational_manager, "_validate_deployment_health", return_value=True
        ):
            with patch.object(
                operational_manager, "_wait_for_service_update", return_value=True
            ):
                result = operational_manager.deploy_containers(deployment_config)

        assert result.status == DeploymentStatus.COMPLETED
        assert result.service_name == "test-service"
        assert result.error_message is None
        assert not result.rollback_performed

    def test_deployment_with_rollback(
        self, operational_manager, deployment_config, mock_docker_client
    ):
        """Test deployment that fails and triggers rollback"""
        # Mock failed health validation
        with patch.object(
            operational_manager, "_validate_deployment_health", return_value=False
        ):
            with patch.object(
                operational_manager, "_wait_for_service_update", return_value=True
            ):
                with patch.object(
                    operational_manager, "_perform_rollback", return_value=True
                ):
                    result = operational_manager.deploy_containers(deployment_config)

        assert result.status == DeploymentStatus.ROLLED_BACK
        assert result.rollback_performed

    def test_deployment_failure(
        self, operational_manager, deployment_config, mock_docker_client
    ):
        """Test deployment failure without rollback"""
        deployment_config.rollback_enabled = False

        # Mock failed health validation
        with patch.object(
            operational_manager, "_validate_deployment_health", return_value=False
        ):
            with patch.object(
                operational_manager, "_wait_for_service_update", return_value=True
            ):
                result = operational_manager.deploy_containers(deployment_config)

        assert result.status == DeploymentStatus.FAILED
        assert not result.rollback_performed
        assert "Health check failed" in result.error_message


class TestScalingOperations:
    """Test scaling operations"""

    def test_scale_up_decision(self, operational_manager, scaling_policy):
        """Test scaling up decision based on high resource usage"""
        decision = operational_manager._determine_scaling_action(
            scaling_policy, 2, 90.0, 85.0
        )

        assert decision["action"] == ScalingDirection.UP
        assert decision["new_replicas"] == 3
        assert "High resource usage" in decision["reason"]

    def test_scale_down_decision(self, operational_manager, scaling_policy):
        """Test scaling down decision based on low resource usage"""
        decision = operational_manager._determine_scaling_action(
            scaling_policy, 3, 20.0, 25.0
        )

        assert decision["action"] == ScalingDirection.DOWN
        assert decision["new_replicas"] == 2
        assert "Low resource usage" in decision["reason"]

    def test_no_scaling_decision(self, operational_manager, scaling_policy):
        """Test no scaling needed decision"""
        decision = operational_manager._determine_scaling_action(
            scaling_policy, 2, 50.0, 60.0
        )

        assert decision["action"] == ScalingDirection.STABLE
        assert decision["new_replicas"] == 2
        assert "within thresholds" in decision["reason"]


class TestIncidentResponse:
    """Test incident response functionality"""

    def test_incident_classification(self, operational_manager):
        """Test incident classification logic"""
        # Test container crash classification
        incident = Incident(
            incident_id="test_001",
            service_name="test-service",
            severity=IncidentSeverity.HIGH,
            description="Container crashed with exit code 1",
            timestamp=datetime.now(),
        )

        incident_type = operational_manager._classify_incident(incident)
        assert incident_type == "container_crash"

        # Test high CPU classification
        incident.description = "High CPU usage detected on service"
        incident_type = operational_manager._classify_incident(incident)
        assert incident_type == "high_cpu_usage"

    def test_container_crash_handling(self, operational_manager, mock_docker_client):
        """Test container crash incident handling"""
        incident = Incident(
            incident_id="crash_001",
            service_name="test-service",
            severity=IncidentSeverity.HIGH,
            description="Container crashed",
            timestamp=datetime.now(),
        )

        with patch.object(
            operational_manager, "_wait_for_service_update", return_value=True
        ):
            response = operational_manager._handle_container_crash(incident)

        assert response.resolution_successful is True
        assert "Restarted service" in response.actions_performed[0]


class TestMonitoringOperations:
    """Test monitoring and metrics operations"""

    def test_operational_metrics_collection(
        self, operational_manager, mock_docker_client
    ):
        """Test operational metrics collection"""
        with patch.object(
            operational_manager,
            "_get_service_metrics",
            return_value={"cpu_usage": 50.0, "memory_usage": 60.0},
        ):
            with patch.object(
                operational_manager, "_calculate_uptime_percentage", return_value=99.5
            ):
                metrics = operational_manager.monitor_operations()

        assert isinstance(metrics, OperationalMetrics)
        assert len(metrics.services) > 0
        assert "test-service" in metrics.services
        assert metrics.uptime_percentage == 99.5
        assert metrics.incident_count == 0


if __name__ == "__main__":
    pytest.main([__file__])

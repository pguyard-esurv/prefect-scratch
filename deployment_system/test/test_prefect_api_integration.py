"""
Integration tests for Prefect API integration.

Tests the integration with Prefect API for deployment creation and management.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from deployment_system.api.deployment_api import DeploymentAPI
from deployment_system.api.prefect_client import PrefectClient
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.discovery.metadata import FlowMetadata


class TestPrefectClient:
    """Test PrefectClient functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client_wrapper = PrefectClient("http://localhost:4200/api")

    @patch("deployment_system.api.prefect_client.get_client")
    def test_client_initialization(self, mock_get_client):
        """Test client initialization."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        assert client.api_url == "http://localhost:4200/api"

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_get_client_async(self, mock_get_client):
        """Test getting async client."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        async_client = await client.get_client()

        assert async_client == mock_client
        mock_get_client.assert_called_once()

    @patch("deployment_system.api.prefect_client.get_client")
    def test_run_async_helper(self, mock_get_client):
        """Test run_async helper method."""
        mock_client = AsyncMock()
        mock_get_client.return_value = mock_client

        @pytest.mark.asyncio
    async def test_coro():
            return "test_result"

        client = PrefectClient("http://localhost:4200/api")

        with patch("asyncio.run") as mock_run:
            mock_run.return_value = "test_result"
            result = client.run_async(test_coro())
            assert result == "test_result"

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_create_deployment_async(self, mock_get_client):
        """Test creating deployment asynchronously."""
        mock_client = AsyncMock()
        mock_client.create_deployment.return_value = Mock(id="deployment-123")
        mock_get_client.return_value = mock_client

        deployment_data = {
            "name": "test-deployment",
            "flow_name": "test-flow",
            "entrypoint": "flows.test.workflow:test_flow",
            "work_pool_name": "default-pool",
        }

        client = PrefectClient("http://localhost:4200/api")
        deployment_id = await client.create_deployment_async(deployment_data)

        assert deployment_id == "deployment-123"
        mock_client.create_deployment.assert_called_once()

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_update_deployment_async(self, mock_get_client):
        """Test updating deployment asynchronously."""
        mock_client = AsyncMock()
        mock_client.update_deployment.return_value = Mock(id="deployment-123")
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        result = await client.update_deployment_async(
            "deployment-123", {"name": "updated-name"}
        )

        assert result.id == "deployment-123"
        mock_client.update_deployment.assert_called_once_with(
            "deployment-123", {"name": "updated-name"}
        )

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_get_deployment_async(self, mock_get_client):
        """Test getting deployment asynchronously."""
        mock_client = AsyncMock()
        mock_deployment = Mock(id="deployment-123", name="test-deployment")
        mock_client.read_deployment.return_value = mock_deployment
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        deployment = await client.get_deployment_async("deployment-123")

        assert deployment.id == "deployment-123"
        assert deployment.name == "test-deployment"
        mock_client.read_deployment.assert_called_once_with("deployment-123")

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_list_deployments_async(self, mock_get_client):
        """Test listing deployments asynchronously."""
        mock_client = AsyncMock()
        mock_deployments = [
            Mock(id="deployment-1", name="deployment-1"),
            Mock(id="deployment-2", name="deployment-2"),
        ]
        mock_client.read_deployments.return_value = mock_deployments
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        deployments = await client.list_deployments_async()

        assert len(deployments) == 2
        assert deployments[0].id == "deployment-1"
        assert deployments[1].id == "deployment-2"
        mock_client.read_deployments.assert_called_once()

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_delete_deployment_async(self, mock_get_client):
        """Test deleting deployment asynchronously."""
        mock_client = AsyncMock()
        mock_client.delete_deployment.return_value = None
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        result = await client.delete_deployment_async("deployment-123")

        assert result is True
        mock_client.delete_deployment.assert_called_once_with("deployment-123")

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_validate_work_pool_async(self, mock_get_client):
        """Test validating work pool asynchronously."""
        mock_client = AsyncMock()
        mock_work_pool = Mock(name="test-pool")
        mock_client.read_work_pool.return_value = mock_work_pool
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        is_valid = await client.validate_work_pool_async("test-pool")

        assert is_valid is True
        mock_client.read_work_pool.assert_called_once_with("test-pool")

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_validate_work_pool_async_not_found(self, mock_get_client):
        """Test validating non-existent work pool."""
        mock_client = AsyncMock()
        mock_client.read_work_pool.side_effect = Exception("Work pool not found")
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        is_valid = await client.validate_work_pool_async("nonexistent-pool")

        assert is_valid is False

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_async(self, mock_get_client):
        """Test checking API connectivity."""
        mock_client = AsyncMock()
        mock_client.hello.return_value = {"message": "Hello from Prefect!"}
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        is_connected = await client.check_api_connectivity_async()

        assert is_connected is True
        mock_client.hello.assert_called_once()

    @patch("deployment_system.api.prefect_client.get_client")
    @pytest.mark.asyncio
    async def test_check_api_connectivity_async_failure(self, mock_get_client):
        """Test API connectivity check failure."""
        mock_client = AsyncMock()
        mock_client.hello.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client

        client = PrefectClient("http://localhost:4200/api")
        is_connected = await client.check_api_connectivity_async()

        assert is_connected is False


class TestDeploymentAPI:
    """Test DeploymentAPI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deployment_api = DeploymentAPI("http://localhost:4200/api")

    def test_deployment_api_initialization(self):
        """Test DeploymentAPI initialization."""
        api = DeploymentAPI("http://localhost:4200/api")
        assert api.client.api_url == "http://localhost:4200/api"
        assert hasattr(api, "client")

    @patch.object(PrefectClient, "run_async")
    def test_create_or_update_deployment(self, mock_run_async):
        """Test creating or updating deployment."""
        mock_run_async.return_value = "deployment-123"

        deployment_config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        deployment_id = self.deployment_api.create_or_update_deployment(
            deployment_config
        )

        assert deployment_id == "deployment-123"
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_get_deployment(self, mock_run_async):
        """Test getting deployment."""
        mock_deployment = Mock(id="deployment-123", name="test-deployment")
        mock_run_async.return_value = mock_deployment

        deployment = self.deployment_api.get_deployment("deployment-123")

        assert deployment.id == "deployment-123"
        assert deployment.name == "test-deployment"
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_list_deployments(self, mock_run_async):
        """Test listing deployments."""
        mock_deployments = [
            Mock(id="deployment-1", name="deployment-1"),
            Mock(id="deployment-2", name="deployment-2"),
        ]
        mock_run_async.return_value = mock_deployments

        deployments = self.deployment_api.list_deployments()

        assert len(deployments) == 2
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_delete_deployment(self, mock_run_async):
        """Test deleting deployment."""
        mock_run_async.return_value = True

        result = self.deployment_api.delete_deployment("deployment-123")

        assert result is True
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_validate_work_pool(self, mock_run_async):
        """Test validating work pool."""
        mock_run_async.return_value = True

        is_valid = self.deployment_api.validate_work_pool("test-pool")

        assert is_valid is True
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_check_api_connectivity(self, mock_run_async):
        """Test checking API connectivity."""
        mock_run_async.return_value = True

        is_connected = self.deployment_api.check_api_connectivity()

        assert is_connected is True
        mock_run_async.assert_called_once()

    def test_convert_config_to_deployment_data(self):
        """Test converting deployment config to Prefect deployment data."""
        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-pool",
            entrypoint="flows.test.workflow:test_flow",
            parameters={"param1": "value1"},
            job_variables={"env": {"VAR1": "value1"}},
            tags=["env:development", "type:python"],
            description="Test deployment",
            schedule="0 0 * * *",
        )

        deployment_data = self.deployment_api.convert_config_to_deployment_data(config)

        assert deployment_data["name"] == "test-deployment"
        assert deployment_data["flow_name"] == "test-flow"
        assert deployment_data["entrypoint"] == "flows.test.workflow:test_flow"
        assert deployment_data["work_pool_name"] == "default-pool"
        assert deployment_data["parameters"] == {"param1": "value1"}
        assert deployment_data["job_variables"] == {"env": {"VAR1": "value1"}}
        assert deployment_data["tags"] == ["env:development", "type:python"]
        assert deployment_data["description"] == "Test deployment"

    def test_convert_config_to_deployment_data_minimal(self):
        """Test converting minimal deployment config."""
        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        deployment_data = self.deployment_api.convert_config_to_deployment_data(config)

        assert deployment_data["name"] == "test-deployment"
        assert deployment_data["flow_name"] == "test-flow"
        assert deployment_data["entrypoint"] == "flows.test.workflow:test_flow"
        assert deployment_data["work_pool_name"] == "default-pool"
        assert deployment_data.get("parameters") == {}
        assert deployment_data.get("job_variables") == {}
        assert deployment_data.get("tags") == []

    @patch.object(PrefectClient, "run_async")
    def test_deployment_exists(self, mock_run_async):
        """Test checking if deployment exists."""
        mock_run_async.return_value = Mock(id="deployment-123")

        exists = self.deployment_api.deployment_exists("test-deployment")

        assert exists is True
        mock_run_async.assert_called_once()

    @patch.object(PrefectClient, "run_async")
    def test_deployment_exists_not_found(self, mock_run_async):
        """Test checking if deployment exists when not found."""
        mock_run_async.side_effect = Exception("Deployment not found")

        exists = self.deployment_api.deployment_exists("nonexistent-deployment")

        assert exists is False

    @patch.object(PrefectClient, "run_async")
    def test_get_deployment_by_name(self, mock_run_async):
        """Test getting deployment by name."""
        mock_deployments = [
            Mock(id="deployment-1", name="test-deployment"),
            Mock(id="deployment-2", name="other-deployment"),
        ]
        mock_run_async.return_value = mock_deployments

        deployment = self.deployment_api.get_deployment_by_name("test-deployment")

        assert deployment.id == "deployment-1"
        assert deployment.name == "test-deployment"

    @patch.object(PrefectClient, "run_async")
    def test_get_deployment_by_name_not_found(self, mock_run_async):
        """Test getting deployment by name when not found."""
        mock_run_async.return_value = []

        deployment = self.deployment_api.get_deployment_by_name(
            "nonexistent-deployment"
        )

        assert deployment is None


class TestPrefectAPIIntegration:
    """Integration tests for Prefect API functionality."""

    @pytest.fixture
    def sample_deployment_config(self):
        """Create sample deployment configuration."""
        return DeploymentConfig(
            flow_name="integration-test-flow",
            deployment_name="integration-test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.integration.workflow:integration_test_flow",
            parameters={"test_param": "test_value"},
            job_variables={
                "env": {
                    "ENVIRONMENT": "DEVELOPMENT",
                    "PYTHONPATH": "/app",
                }
            },
            tags=["integration-test", "env:development"],
            description="Integration test deployment",
        )

    @patch("deployment_system.api.prefect_client.get_client")
    def test_end_to_end_deployment_creation(
        self, mock_get_client, sample_deployment_config
    ):
        """Test end-to-end deployment creation workflow."""
        # Mock Prefect client
        mock_client = AsyncMock()
        mock_client.create_deployment.return_value = Mock(id="deployment-123")
        mock_get_client.return_value = mock_client

        # Create deployment API
        api = DeploymentAPI("http://localhost:4200/api")

        # Mock the async run
        with patch.object(api.client, "run_async") as mock_run_async:
            mock_run_async.return_value = "deployment-123"

            # Create deployment
            deployment_id = api.create_or_update_deployment(sample_deployment_config)

            assert deployment_id == "deployment-123"
            mock_run_async.assert_called_once()

    @patch("deployment_system.api.prefect_client.get_client")
    def test_deployment_lifecycle_management(
        self, mock_get_client, sample_deployment_config
    ):
        """Test complete deployment lifecycle (create, read, update, delete)."""
        # Mock Prefect client
        mock_client = AsyncMock()
        mock_deployment = Mock(
            id="deployment-123",
            name="integration-test-deployment",
            flow_name="integration-test-flow",
        )

        mock_client.create_deployment.return_value = mock_deployment
        mock_client.read_deployment.return_value = mock_deployment
        mock_client.update_deployment.return_value = mock_deployment
        mock_client.delete_deployment.return_value = None
        mock_get_client.return_value = mock_client

        api = DeploymentAPI("http://localhost:4200/api")

        # Mock async operations
        with patch.object(api.client, "run_async") as mock_run_async:
            # Create
            mock_run_async.return_value = "deployment-123"
            deployment_id = api.create_or_update_deployment(sample_deployment_config)
            assert deployment_id == "deployment-123"

            # Read
            mock_run_async.return_value = mock_deployment
            deployment = api.get_deployment("deployment-123")
            assert deployment.id == "deployment-123"

            # Update
            mock_run_async.return_value = mock_deployment
            updated_config = sample_deployment_config
            updated_config.description = "Updated description"
            updated_id = api.create_or_update_deployment(updated_config)
            assert updated_id == "deployment-123"

            # Delete
            mock_run_async.return_value = True
            result = api.delete_deployment("deployment-123")
            assert result is True

    @patch("deployment_system.api.prefect_client.get_client")
    def test_work_pool_validation_integration(self, mock_get_client):
        """Test work pool validation integration."""
        mock_client = AsyncMock()
        mock_work_pool = Mock(name="test-pool")
        mock_client.read_work_pool.return_value = mock_work_pool
        mock_get_client.return_value = mock_client

        api = DeploymentAPI("http://localhost:4200/api")

        with patch.object(api.client, "run_async") as mock_run_async:
            mock_run_async.return_value = True
            is_valid = api.validate_work_pool("test-pool")
            assert is_valid is True

    @patch("deployment_system.api.prefect_client.get_client")
    def test_api_connectivity_integration(self, mock_get_client):
        """Test API connectivity integration."""
        mock_client = AsyncMock()
        mock_client.hello.return_value = {"message": "Hello from Prefect!"}
        mock_get_client.return_value = mock_client

        api = DeploymentAPI("http://localhost:4200/api")

        with patch.object(api.client, "run_async") as mock_run_async:
            mock_run_async.return_value = True
            is_connected = api.check_api_connectivity()
            assert is_connected is True

    @patch("deployment_system.api.prefect_client.get_client")
    def test_deployment_listing_and_filtering(self, mock_get_client):
        """Test deployment listing and filtering."""
        mock_client = AsyncMock()
        mock_deployments = [
            Mock(id="deployment-1", name="test-deployment-1", flow_name="flow-1"),
            Mock(id="deployment-2", name="test-deployment-2", flow_name="flow-2"),
            Mock(id="deployment-3", name="other-deployment", flow_name="flow-1"),
        ]
        mock_client.read_deployments.return_value = mock_deployments
        mock_get_client.return_value = mock_client

        api = DeploymentAPI("http://localhost:4200/api")

        with patch.object(api.client, "run_async") as mock_run_async:
            mock_run_async.return_value = mock_deployments
            deployments = api.list_deployments()
            assert len(deployments) == 3

            # Test filtering by name pattern
            mock_run_async.return_value = [
                d for d in mock_deployments if "test-deployment" in d.name
            ]
            filtered_deployments = api.list_deployments(name_pattern="test-deployment")
            assert len(filtered_deployments) == 2

    @patch("deployment_system.api.prefect_client.get_client")
    def test_error_handling_integration(self, mock_get_client):
        """Test error handling in API integration."""
        mock_client = AsyncMock()
        mock_client.create_deployment.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client

        api = DeploymentAPI("http://localhost:4200/api")

        sample_config = DeploymentConfig(
            flow_name="error-test-flow",
            deployment_name="error-test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-pool",
            entrypoint="flows.error.workflow:error_flow",
        )

        with patch.object(api.client, "run_async") as mock_run_async:
            mock_run_async.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                api.create_or_update_deployment(sample_config)

    def test_deployment_data_conversion_accuracy(self):
        """Test accuracy of deployment data conversion."""
        api = DeploymentAPI("http://localhost:4200/api")

        config = DeploymentConfig(
            flow_name="conversion-test-flow",
            deployment_name="conversion-test-deployment",
            environment="production",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.conversion.workflow:conversion_flow",
            parameters={"batch_size": 100, "timeout": 300},
            job_variables={
                "image": "conversion-flow:latest",
                "env": {
                    "ENVIRONMENT": "PRODUCTION",
                    "LOG_LEVEL": "INFO",
                },
                "volumes": ["/data:/app/data"],
                "networks": ["production-network"],
            },
            tags=["production", "batch-processing", "docker"],
            description="Production batch processing flow",
            schedule="0 2 * * *",  # Daily at 2 AM
        )

        deployment_data = api.convert_config_to_deployment_data(config)

        # Verify all fields are correctly converted
        assert deployment_data["name"] == "conversion-test-deployment"
        assert deployment_data["flow_name"] == "conversion-test-flow"
        assert (
            deployment_data["entrypoint"] == "flows.conversion.workflow:conversion_flow"
        )
        assert deployment_data["work_pool_name"] == "docker-pool"

        assert deployment_data["parameters"]["batch_size"] == 100
        assert deployment_data["parameters"]["timeout"] == 300

        assert deployment_data["job_variables"]["image"] == "conversion-flow:latest"
        assert deployment_data["job_variables"]["env"]["ENVIRONMENT"] == "PRODUCTION"
        assert deployment_data["job_variables"]["volumes"] == ["/data:/app/data"]
        assert deployment_data["job_variables"]["networks"] == ["production-network"]

        assert "production" in deployment_data["tags"]
        assert "batch-processing" in deployment_data["tags"]
        assert "docker" in deployment_data["tags"]

        assert deployment_data["description"] == "Production batch processing flow"

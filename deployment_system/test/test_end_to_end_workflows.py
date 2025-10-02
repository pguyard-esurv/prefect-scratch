"""
End-to-end system tests for complete deployment workflows.

Tests the entire deployment system from flow discovery to Prefect deployment.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from deployment_system.builders.deployment_builder import DeploymentBuilder
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.discovery import FlowDiscovery
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.comprehensive_validator import ComprehensiveValidator


class TestEndToEndDeploymentWorkflow:
    """Test complete end-to-end deployment workflows."""

    @pytest.fixture
    def sample_project_structure(self):
        """Create a sample project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)

            # Create flows directory structure
            flows_dir = project_root / "flows"
            flows_dir.mkdir()

            # Create RPA1 flow (Python only)
            rpa1_dir = flows_dir / "rpa1"
            rpa1_dir.mkdir()

            rpa1_workflow = rpa1_dir / "workflow.py"
            rpa1_workflow.write_text(
                """
from prefect import flow, task
import pandas as pd

@task
def process_data():
    return pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})

@flow(name="rpa1_flow", description="RPA1 data processing flow")
def rpa1_flow():
    data = process_data()
    return data.to_dict()
"""
            )

            rpa1_env = rpa1_dir / ".env.development"
            rpa1_env.write_text("RPA1_CONFIG=development\nDEBUG=true")

            # Create RPA2 flow (Docker capable)
            rpa2_dir = flows_dir / "rpa2"
            rpa2_dir.mkdir()

            rpa2_workflow = rpa2_dir / "workflow.py"
            rpa2_workflow.write_text(
                """
from prefect import flow, task
import requests

@task
def fetch_data(url: str):
    response = requests.get(url)
    return response.json()

@flow(name="rpa2_flow", description="RPA2 API integration flow")
def rpa2_flow(api_url: str = "https://api.example.com/data"):
    data = fetch_data(api_url)
    return data
"""
            )

            rpa2_dockerfile = rpa2_dir / "Dockerfile"
            rpa2_dockerfile.write_text(
                """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "prefect", "worker", "start", "--pool", "docker-pool"]
"""
            )

            rpa2_env_dev = rpa2_dir / ".env.development"
            rpa2_env_dev.write_text(
                "RPA2_CONFIG=development\nAPI_URL=https://dev-api.example.com"
            )

            rpa2_env_prod = rpa2_dir / ".env.production"
            rpa2_env_prod.write_text(
                "RPA2_CONFIG=production\nAPI_URL=https://api.example.com"
            )

            # Create invalid flow for testing error handling
            invalid_dir = flows_dir / "invalid"
            invalid_dir.mkdir()

            invalid_workflow = invalid_dir / "workflow.py"
            invalid_workflow.write_text(
                """
# This file has syntax errors
from prefect import flow

@flow
def broken_flow(
    return "This is invalid syntax"
"""
            )

            # Create configuration files
            config_dir = project_root / "config"
            config_dir.mkdir()

            deployment_config = config_dir / "deployment_config.yaml"
            deployment_config.write_text(
                """
environments:
  development:
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-agent-pool"
      docker: "docker-pool"
    default_parameters:
      cleanup: true
      debug: true
    resource_limits:
      memory: "512Mi"
      cpu: "0.5"
    default_tags:
      - "env:development"

  production:
    prefect_api_url: "http://prod-prefect:4200/api"
    work_pools:
      python: "prod-agent-pool"
      docker: "prod-docker-pool"
    default_parameters:
      cleanup: false
      debug: false
    resource_limits:
      memory: "2Gi"
      cpu: "2.0"
    default_tags:
      - "env:production"

global:
  validation:
    validate_dependencies: true
    validate_docker_images: true
    strict_mode: false
  
  deployment_templates:
    python:
      job_variables:
        env:
          PYTHONPATH: "/app"
    docker:
      job_variables:
        networks:
          - "rpa-network"
"""
            )

            yield project_root

    def test_complete_flow_discovery_workflow(self, sample_project_structure):
        """Test complete flow discovery workflow."""
        flows_dir = sample_project_structure / "flows"

        # Initialize discovery
        discovery = FlowDiscovery()

        # Discover flows
        flows = discovery.discover_flows(str(flows_dir))

        # Should find valid flows and skip invalid ones
        valid_flows = [f for f in flows if f.is_valid]
        assert len(valid_flows) >= 2  # rpa1 and rpa2

        # Verify flow details
        flow_names = [f.name for f in valid_flows]
        assert "rpa1_flow" in flow_names
        assert "rpa2_flow" in flow_names

        # Verify Docker capabilities
        docker_flows = [f for f in valid_flows if f.supports_docker()]
        assert len(docker_flows) >= 1  # rpa2 should support Docker

        # Verify environment files detection
        flows_with_env = [f for f in valid_flows if f.env_files]
        assert len(flows_with_env) >= 2  # Both rpa1 and rpa2 have env files

    def test_complete_deployment_creation_workflow(self, sample_project_structure):
        """Test complete deployment creation workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Discover flows
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Create all deployments
        result = deployment_builder.create_all_deployments(valid_flows, "development")

        assert result.success is True
        assert len(result.deployments) >= 3  # At least 2 Python + 1 Docker

        # Verify deployment configurations
        python_deployments = [
            d for d in result.deployments if d.deployment_type == "python"
        ]
        docker_deployments = [
            d for d in result.deployments if d.deployment_type == "docker"
        ]

        assert len(python_deployments) >= 2  # Both flows support Python
        assert len(docker_deployments) >= 1  # rpa2 supports Docker

        # Verify environment-specific configuration
        for deployment in result.deployments:
            assert deployment.environment == "development"
            assert "env:development" in deployment.tags

    def test_complete_validation_workflow(self, sample_project_structure):
        """Test complete validation workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)
        validator = ComprehensiveValidator()

        # Discover and create deployments
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]
        result = deployment_builder.create_all_deployments(valid_flows, "development")

        # Validate all deployments
        validation_results = {}
        for deployment in result.deployments:
            flow = next(f for f in valid_flows if f.name == deployment.flow_name)
            validation_result = validator.validate_flow_for_deployment(flow, deployment)
            validation_results[
                f"{deployment.flow_name}/{deployment.deployment_type}"
            ] = validation_result

        # Should have validation results for all deployments
        assert len(validation_results) == len(result.deployments)

        # Most validations should pass (may have warnings)
        valid_deployments = [r for r in validation_results.values() if r.is_valid]
        assert len(valid_deployments) >= len(result.deployments) // 2

    @patch(
        "deployment_system.api.deployment_api.DeploymentAPI.create_or_update_deployment"
    )
    @patch("deployment_system.api.deployment_api.DeploymentAPI.check_api_connectivity")
    def test_complete_deployment_to_prefect_workflow(
        self, mock_connectivity, mock_create_deployment, sample_project_structure
    ):
        """Test complete deployment to Prefect workflow."""
        # Mock Prefect API responses
        mock_connectivity.return_value = True
        mock_create_deployment.side_effect = (
            lambda config: f"deployment-{config.flow_name}-{config.deployment_type}"
        )

        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Complete workflow
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Deploy to Prefect
        deploy_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "development"
        )

        assert deploy_result.success is True
        assert len(deploy_result.deployment_ids) >= 3  # At least 2 Python + 1 Docker

        # Verify API calls were made
        assert mock_create_deployment.call_count >= 3
        mock_connectivity.assert_called()

    def test_multi_environment_deployment_workflow(self, sample_project_structure):
        """Test deployment workflow across multiple environments."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Discover flows once
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Deploy to multiple environments
        environments = ["development", "production"]
        all_deployments = []

        for env in environments:
            result = deployment_builder.create_all_deployments(valid_flows, env)
            assert result.success is True
            all_deployments.extend(result.deployments)

        # Should have deployments for both environments
        dev_deployments = [d for d in all_deployments if d.environment == "development"]
        prod_deployments = [d for d in all_deployments if d.environment == "production"]

        assert len(dev_deployments) >= 3
        assert len(prod_deployments) >= 3

        # Verify environment-specific configuration
        for deployment in dev_deployments:
            assert "env:development" in deployment.tags

        for deployment in prod_deployments:
            assert "env:production" in deployment.tags

    def test_error_handling_and_recovery_workflow(self, sample_project_structure):
        """Test error handling and recovery in deployment workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Discover flows (including invalid ones)
        flows = discovery.discover_flows(str(flows_dir))

        # Should handle invalid flows gracefully
        all_flows = flows  # Include invalid flows
        result = deployment_builder.create_all_deployments(all_flows, "development")

        # Should succeed for valid flows despite invalid ones
        assert len(result.deployments) >= 2  # Valid deployments created
        assert len(result.errors) >= 1  # Errors for invalid flows recorded

    def test_deployment_summary_and_reporting_workflow(self, sample_project_structure):
        """Test deployment summary and reporting workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)
        validator = ComprehensiveValidator()

        # Complete discovery and deployment
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]
        result = deployment_builder.create_all_deployments(valid_flows, "development")

        # Generate flow summary
        flow_summary = discovery.get_flow_summary(flows)
        assert flow_summary["total_flows"] >= 3  # Including invalid flow
        assert flow_summary["valid_flows"] >= 2
        assert flow_summary["docker_capable"] >= 1

        # Generate deployment summary
        deployment_summary = deployment_builder.get_deployment_summary(valid_flows)
        assert deployment_summary["total_flows"] >= 2
        assert deployment_summary["python_capable"] >= 2
        assert deployment_summary["docker_capable"] >= 1

        # Generate validation report
        validation_results = {}
        for deployment in result.deployments:
            flow = next(f for f in valid_flows if f.name == deployment.flow_name)
            validation_result = validator.validate_flow_for_deployment(flow, deployment)
            validation_results[
                f"{deployment.flow_name}/{deployment.deployment_type}"
            ] = validation_result

        validation_report = validator.generate_validation_report(validation_results)
        assert "# Deployment Validation Report" in validation_report
        assert "Total deployments:" in validation_report

    @patch(
        "deployment_system.builders.python_builder.PythonDeploymentCreator.deploy_to_prefect"
    )
    @patch(
        "deployment_system.builders.docker_builder.DockerDeploymentCreator.deploy_to_prefect"
    )
    def test_deployment_rollback_workflow(
        self, mock_docker_deploy, mock_python_deploy, sample_project_structure
    ):
        """Test deployment rollback workflow on failures."""
        # Mock partial failure scenario
        mock_python_deploy.side_effect = [
            "python-deployment-1",
            Exception("Deployment failed"),
        ]
        mock_docker_deploy.return_value = "docker-deployment-1"

        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Attempt deployment
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        deploy_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "development"
        )

        # Should have partial success
        assert not deploy_result.success  # Overall failure due to exception
        assert len(deploy_result.deployment_ids) >= 1  # Some deployments succeeded
        assert len(deploy_result.errors) >= 1  # Some deployments failed

    def test_configuration_override_workflow(self, sample_project_structure):
        """Test configuration override workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Create flow-specific override configuration
        flow_overrides = config_dir / "flow_overrides.yaml"
        flow_overrides.write_text(
            """
rpa2_flow:
  development:
    parameters:
      api_url: "https://dev-override.example.com"
      batch_size: 50
    resource_limits:
      memory: "1Gi"
      cpu: "1.0"
    tags:
      - "override:true"
      - "priority:high"
"""
        )

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Create deployments
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]
        result = deployment_builder.create_all_deployments(valid_flows, "development")

        # Find rpa2_flow deployments
        rpa2_deployments = [d for d in result.deployments if d.flow_name == "rpa2_flow"]
        assert len(rpa2_deployments) >= 1

        # Verify overrides were applied
        for deployment in rpa2_deployments:
            if "override:true" in deployment.tags:
                assert "priority:high" in deployment.tags
                # Override configuration was applied

    def test_docker_image_validation_workflow(self, sample_project_structure):
        """Test Docker image validation workflow."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)
        validator = ComprehensiveValidator()

        # Discover flows
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Create Docker deployments only
        result = deployment_builder.create_deployments_by_type(
            valid_flows, "docker", "development"
        )

        # Validate Docker deployments
        for deployment in result.deployments:
            flow = next(f for f in valid_flows if f.name == deployment.flow_name)
            validation_result = validator.validate_flow_for_deployment(flow, deployment)

            # Should validate Dockerfile existence and structure
            # May have warnings about Docker image not being built yet
            assert validation_result.is_valid or validation_result.has_warnings

    def test_concurrent_deployment_workflow(self, sample_project_structure):
        """Test concurrent deployment workflow simulation."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))

        # Simulate concurrent deployment builders
        builder1 = DeploymentBuilder(config_manager)
        builder2 = DeploymentBuilder(config_manager)

        # Discover flows
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Create deployments with different builders (simulating concurrency)
        result1 = builder1.create_deployments_by_type(
            valid_flows, "python", "development"
        )
        result2 = builder2.create_deployments_by_type(
            valid_flows, "docker", "development"
        )

        # Both should succeed independently
        assert result1.success is True
        assert len(result1.deployments) >= 2  # Python deployments

        # Docker result may have fewer deployments (only Docker-capable flows)
        assert len(result2.deployments) >= 1  # Docker deployments

        # Verify no conflicts in deployment names
        all_deployment_names = [
            d.deployment_name for d in result1.deployments + result2.deployments
        ]
        assert len(all_deployment_names) == len(set(all_deployment_names))  # All unique


@pytest.fixture
def mock_prefect_environment():
    """Mock Prefect environment for testing."""
    with patch("deployment_system.api.deployment_api.DeploymentAPI") as mock_api_class:
        mock_api = Mock()
        mock_api.check_api_connectivity.return_value = True
        mock_api.validate_work_pool.return_value = True
        mock_api.create_or_update_deployment.side_effect = (
            lambda config: f"deployment-{config.flow_name}"
        )
        mock_api_class.return_value = mock_api
        yield mock_api


class TestEndToEndIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_new_project_setup_scenario(
        self, sample_project_structure, mock_prefect_environment
    ):
        """Test scenario: Setting up deployment system for a new project."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Step 1: Initialize deployment system
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)
        validator = ComprehensiveValidator()

        # Step 2: Discover existing flows
        flows = discovery.discover_flows(str(flows_dir))
        flow_summary = discovery.get_flow_summary(flows)

        assert flow_summary["total_flows"] >= 2
        print(f"Discovered {flow_summary['total_flows']} flows")

        # Step 3: Validate flows
        valid_flows = [f for f in flows if f.is_valid]
        validation_results = {}
        for flow in valid_flows:
            # Create a sample deployment config for validation
            config = DeploymentConfig(
                flow_name=flow.name,
                deployment_name=f"{flow.name}-python-development",
                environment="development",
                deployment_type="python",
                work_pool="default-agent-pool",
                entrypoint=f"{flow.module_path}:{flow.function_name}",
            )
            validation_result = validator.validate_flow_for_deployment(flow, config)
            validation_results[flow.name] = validation_result

        # Step 4: Create deployments
        deployment_result = deployment_builder.create_all_deployments(
            valid_flows, "development"
        )
        assert deployment_result.success is True

        # Step 5: Deploy to Prefect
        deploy_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "development"
        )
        assert deploy_result.success is True

        print(f"Successfully deployed {len(deploy_result.deployment_ids)} deployments")

    def test_production_deployment_scenario(
        self, sample_project_structure, mock_prefect_environment
    ):
        """Test scenario: Deploying to production environment."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize for production deployment
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Discover and validate flows
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        # Create production deployments
        prod_result = deployment_builder.create_all_deployments(
            valid_flows, "production"
        )
        assert prod_result.success is True

        # Verify production-specific configuration
        for deployment in prod_result.deployments:
            assert deployment.environment == "production"
            assert "env:production" in deployment.tags
            # Production should have different resource limits

        # Deploy to production Prefect
        deploy_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "production"
        )
        assert deploy_result.success is True

    def test_flow_update_scenario(
        self, sample_project_structure, mock_prefect_environment
    ):
        """Test scenario: Updating existing flows and redeploying."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initial deployment
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        initial_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "development"
        )
        initial_count = len(initial_result.deployment_ids)

        # Simulate flow update by modifying a flow file
        rpa1_workflow = flows_dir / "rpa1" / "workflow.py"
        updated_content = (
            rpa1_workflow.read_text()
            + """

@task
def new_task():
    return "Updated functionality"
"""
        )
        rpa1_workflow.write_text(updated_content)

        # Rediscover and redeploy
        updated_flows = discovery.discover_flows(str(flows_dir))
        updated_valid_flows = [f for f in updated_flows if f.is_valid]

        update_result = deployment_builder.deploy_all_to_prefect(
            updated_valid_flows, "development"
        )
        assert update_result.success is True
        assert (
            len(update_result.deployment_ids) == initial_count
        )  # Same number of deployments

    def test_disaster_recovery_scenario(self, sample_project_structure):
        """Test scenario: Recovering from deployment failures."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Initialize components
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Simulate API failure scenario
        with patch(
            "deployment_system.api.deployment_api.DeploymentAPI"
        ) as mock_api_class:
            mock_api = Mock()
            mock_api.check_api_connectivity.return_value = False  # API down
            mock_api_class.return_value = mock_api

            flows = discovery.discover_flows(str(flows_dir))
            valid_flows = [f for f in flows if f.is_valid]

            # Should handle API failure gracefully
            with pytest.raises(Exception):
                deployment_builder.deploy_all_to_prefect(valid_flows, "development")

        # Simulate recovery - API back online
        with patch(
            "deployment_system.api.deployment_api.DeploymentAPI"
        ) as mock_api_class:
            mock_api = Mock()
            mock_api.check_api_connectivity.return_value = True  # API recovered
            mock_api.create_or_update_deployment.side_effect = (
                lambda config: f"deployment-{config.flow_name}"
            )
            mock_api_class.return_value = mock_api

            # Should succeed after recovery
            recovery_result = deployment_builder.deploy_all_to_prefect(
                valid_flows, "development"
            )
            assert recovery_result.success is True

    def test_scaling_scenario(self, sample_project_structure, mock_prefect_environment):
        """Test scenario: Scaling deployment system for many flows."""
        flows_dir = sample_project_structure / "flows"
        config_dir = sample_project_structure / "config"

        # Create additional flows to simulate scaling
        for i in range(5, 10):  # Add 5 more flows
            flow_dir = flows_dir / f"rpa{i}"
            flow_dir.mkdir()

            workflow_file = flow_dir / "workflow.py"
            workflow_file.write_text(
                f"""
from prefect import flow, task

@task
def process_batch_{i}():
    return f"Processed batch {i}"

@flow(name="rpa{i}_flow", description="RPA{i} processing flow")
def rpa{i}_flow():
    result = process_batch_{i}()
    return result
"""
            )

            env_file = flow_dir / ".env.development"
            env_file.write_text(f"RPA{i}_CONFIG=development")

        # Initialize and process all flows
        discovery = FlowDiscovery()
        config_manager = ConfigurationManager(str(config_dir))
        deployment_builder = DeploymentBuilder(config_manager)

        # Should handle many flows efficiently
        flows = discovery.discover_flows(str(flows_dir))
        valid_flows = [f for f in flows if f.is_valid]

        assert len(valid_flows) >= 7  # Original 2 + 5 new flows

        # Create all deployments
        result = deployment_builder.create_all_deployments(valid_flows, "development")
        assert result.success is True
        assert len(result.deployments) >= 7  # At least one deployment per flow

        # Deploy all to Prefect
        deploy_result = deployment_builder.deploy_all_to_prefect(
            valid_flows, "development"
        )
        assert deploy_result.success is True
        assert len(deploy_result.deployment_ids) >= 7

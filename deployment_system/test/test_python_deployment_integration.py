"""
Integration Tests for Python Deployment Creator

Tests all requirements for task 4: Build Python deployment creator.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add deployment_system to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system.builders.python_builder import PythonDeploymentCreator
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.metadata import FlowMetadata


class TestPythonDeploymentCreatorRequirements:
    """Test that all requirements for task 4 are met."""

    def test_requirement_2_1_native_python_deployments(self):
        """
        Requirement 2.1: WHEN creating Python deployments THEN the system SHALL
        generate deployments that run flows as native Python processes
        """
        creator = PythonDeploymentCreator()

        flow = FlowMetadata(
            name="test-flow",
            path="/app/flows/test/workflow.py",
            module_path="flows.test.workflow",
            function_name="test_flow",
            is_valid=True,
        )

        config = creator.create_deployment(flow, "development")

        # Verify it's a Python deployment
        assert config.deployment_type == "python"

        # Verify entrypoint format for Python execution
        assert ":" in config.entrypoint
        assert config.entrypoint == "flows.test.workflow:test_flow"

        # Verify Python-specific job variables
        assert "env" in config.job_variables
        assert config.job_variables["env"]["PYTHONPATH"] == "/app"
        assert "runtime:python" in config.tags

    def test_requirement_2_3_both_deployment_types_supported(self):
        """
        Requirement 2.3: WHEN generating deployments THEN the system SHALL
        support both deployment types for the same flow
        """
        creator = PythonDeploymentCreator()

        flow = FlowMetadata(
            name="multi-deploy-flow",
            path="/app/flows/multi/workflow.py",
            module_path="flows.multi.workflow",
            function_name="multi_flow",
            dockerfile_path="/app/flows/multi/Dockerfile",  # Supports Docker too
            is_valid=True,
        )

        # Should support Python deployment
        assert flow.supports_python_deployment

        # Should also support Docker deployment (has Dockerfile)
        assert flow.supports_docker_deployment

        # Create Python deployment
        python_config = creator.create_deployment(flow, "development")
        assert python_config.deployment_type == "python"
        assert python_config.entrypoint == "flows.multi.workflow:multi_flow"

    def test_requirement_6_1_environment_specific_configuration(self):
        """
        Requirement 6.1: WHEN creating deployments THEN the system SHALL
        support environment-specific configuration files
        """
        config_manager = ConfigurationManager()
        creator = PythonDeploymentCreator(config_manager)

        flow = FlowMetadata(
            name="env-test-flow",
            path="/app/flows/env/workflow.py",
            module_path="flows.env.workflow",
            function_name="env_flow",
            is_valid=True,
        )

        # Test different environments
        environments = ["development", "staging", "production"]

        for env in environments:
            config = creator.create_deployment(flow, env)

            # Verify environment-specific configuration
            assert config.environment == env
            assert f"environment:{env}" in config.tags
            assert config.job_variables["env"]["ENVIRONMENT"] == env.upper()

            # Verify environment-specific work pools
            env_config = config_manager.get_environment_config(env)
            if env_config:
                expected_work_pool = env_config.get_work_pool("python")
                assert config.work_pool == expected_work_pool

    def test_requirement_6_2_environment_appropriate_settings(self):
        """
        Requirement 6.2: WHEN deploying to different environments THEN the system
        SHALL use the appropriate configuration for that environment
        """
        config_manager = ConfigurationManager()
        creator = PythonDeploymentCreator(config_manager)

        flow = FlowMetadata(
            name="settings-test-flow",
            path="/app/flows/settings/workflow.py",
            module_path="flows.settings.workflow",
            function_name="settings_flow",
            is_valid=True,
        )

        # Create deployments for different environments
        dev_config = creator.create_deployment(flow, "development")
        prod_config = creator.create_deployment(flow, "production")

        # Verify different settings per environment
        assert dev_config.parameters != prod_config.parameters
        assert dev_config.work_pool != prod_config.work_pool

        # Development should have debug settings
        dev_env_config = config_manager.get_environment_config("development")
        prod_env_config = config_manager.get_environment_config("production")

        assert dev_env_config.default_parameters["cleanup"]
        assert not dev_env_config.default_parameters["use_distributed"]

        assert not prod_env_config.default_parameters["cleanup"]
        assert prod_env_config.default_parameters["use_distributed"]

    def test_deployment_configuration_templates(self):
        """
        Test that deployment configuration templates are properly implemented.
        """
        creator = PythonDeploymentCreator()

        # Get default template
        template = creator.get_deployment_template()

        # Verify template structure
        assert isinstance(template, dict)
        assert "work_pool" in template
        assert "job_variables" in template
        assert "parameters" in template
        assert "tags" in template

        # Verify Python-specific template elements
        assert "env" in template["job_variables"]
        assert "PYTHONPATH" in template["job_variables"]["env"]
        assert "runtime:python" in template["tags"]

    def test_environment_specific_parameter_handling(self):
        """
        Test that environment-specific parameters are properly handled.
        """
        config_manager = ConfigurationManager()
        creator = PythonDeploymentCreator(config_manager)

        flow = FlowMetadata(
            name="param-test-flow",
            path="/app/flows/param/workflow.py",
            module_path="flows.param.workflow",
            function_name="param_flow",
            dependencies=["numpy>=1.20.0"],
            env_files=[".env.development", ".env.production"],
            is_valid=True,
        )

        config = creator.create_deployment(flow, "development")

        # Verify environment-specific parameters are included
        assert config.parameters  # Should have environment defaults

        # Verify Python-specific enhancements
        assert config.job_variables["pip_install_requirements"] == flow.dependencies
        assert config.job_variables["env_files"] == flow.env_files

        # Verify environment variables
        env_vars = config.job_variables["env"]
        assert env_vars["ENVIRONMENT"] == "DEVELOPMENT"
        assert env_vars["FLOW_NAME"] == flow.name
        assert env_vars["DEPLOYMENT_TYPE"] == "python"

    def test_prefect_api_integration(self):
        """
        Test integration with Prefect API for deployment creation.
        """
        # Create creator with mocked API
        creator = PythonDeploymentCreator()

        # Mock the deployment API
        mock_api = Mock()
        mock_api.create_or_update_deployment.return_value = "deployment-123"
        mock_api.validate_work_pool.return_value = True
        creator.deployment_api = mock_api

        flow = FlowMetadata(
            name="api-test-flow",
            path="/app/flows/api/workflow.py",
            module_path="flows.api.workflow",
            function_name="api_flow",
            is_valid=True,
        )

        # Test deployment to Prefect
        deployment_id = creator.deploy_to_prefect(flow, "development")

        # Verify API was called
        assert deployment_id == "deployment-123"
        mock_api.create_or_update_deployment.assert_called_once()

        # Verify correct configuration was passed
        call_args = mock_api.create_or_update_deployment.call_args[0][0]
        assert isinstance(call_args, DeploymentConfig)
        assert call_args.deployment_type == "python"
        assert call_args.flow_name == "api-test-flow"

    def test_validation_and_error_handling(self):
        """
        Test validation and error handling for Python deployments.
        """
        creator = PythonDeploymentCreator()

        # Test with invalid flow
        invalid_flow = FlowMetadata(
            name="invalid-flow",
            path="/app/flows/invalid/workflow.py",
            module_path="flows.invalid.workflow",
            function_name="invalid_flow",
            is_valid=False,
            validation_errors=["Missing @flow decorator"],
        )

        # Should raise error for invalid flow
        with pytest.raises(ValueError, match="does not support Python deployment"):
            creator.create_deployment(invalid_flow, "development")

        # Test validation of deployment config
        valid_config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="test-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        result = creator.validate_deployment_config(valid_config)
        assert result.is_valid

        # Test invalid config - create manually to bypass validation
        invalid_config = DeploymentConfig.__new__(DeploymentConfig)
        invalid_config.flow_name = ""  # Missing flow name
        invalid_config.deployment_name = "test-deployment"
        invalid_config.environment = "development"
        invalid_config.deployment_type = "python"
        invalid_config.work_pool = ""  # Missing work pool
        invalid_config.entrypoint = "invalid_entrypoint"  # Invalid format
        invalid_config.schedule = None
        invalid_config.parameters = {}
        invalid_config.job_variables = {}
        invalid_config.tags = []
        invalid_config.description = ""
        invalid_config.version = "1.0.0"

        result = creator.validate_deployment_config(invalid_config)
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_deployment_type_identification(self):
        """
        Test that the deployment type is correctly identified.
        """
        creator = PythonDeploymentCreator()

        assert creator.get_deployment_type() == "python"

    def test_comprehensive_deployment_creation(self):
        """
        Test comprehensive deployment creation with all features.
        """
        config_manager = ConfigurationManager()
        creator = PythonDeploymentCreator(config_manager)

        # Create a comprehensive flow with all features
        flow = FlowMetadata(
            name="comprehensive-flow",
            path="/app/flows/comprehensive/workflow.py",
            module_path="flows.comprehensive.workflow",
            function_name="comprehensive_flow",
            dependencies=["pandas>=1.5.0", "requests>=2.28.0", "numpy>=1.20.0"],
            dockerfile_path="/app/flows/comprehensive/Dockerfile",
            env_files=[".env.development", ".env.production"],
            is_valid=True,
            validation_errors=[],
            metadata={
                "description": "Comprehensive test flow",
                "version": "1.0.0",
                "author": "Test Suite",
            },
        )

        config = creator.create_deployment(flow, "production")

        # Verify all aspects of the deployment
        assert config.flow_name == "comprehensive-flow"
        assert config.deployment_type == "python"
        assert config.environment == "production"
        assert config.entrypoint == "flows.comprehensive.workflow:comprehensive_flow"

        # Verify tags
        expected_tags = [
            "environment:production",
            "type:python",
            "flow:comprehensive-flow",
            "runtime:python",
            "has-dependencies",
        ]
        for tag in expected_tags:
            assert tag in config.tags

        # Verify job variables
        assert "env" in config.job_variables
        assert "pip_install_requirements" in config.job_variables
        assert "env_files" in config.job_variables

        # Verify environment variables
        env_vars = config.job_variables["env"]
        assert env_vars["PYTHONPATH"] == "/app"
        assert env_vars["ENVIRONMENT"] == "PRODUCTION"
        assert env_vars["FLOW_NAME"] == "comprehensive-flow"
        assert env_vars["DEPLOYMENT_TYPE"] == "python"

        # Verify dependencies and env files
        assert config.job_variables["pip_install_requirements"] == flow.dependencies
        assert config.job_variables["env_files"] == flow.env_files

        # Verify validation passes
        validation_result = creator.validate_deployment_config(config)
        assert validation_result.is_valid or len(validation_result.errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Test Makefile Integration

Tests for the Makefile integration commands.
"""

import subprocess


class TestMakefileIntegration:
    """Test Makefile integration commands."""

    def test_discover_flows_command(self):
        """Test that make discover-flows command works."""
        result = subprocess.run(
            ["make", "discover-flows"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0
        assert "Discovered" in result.stdout
        assert "flows:" in result.stdout

    def test_deployment_status_command(self):
        """Test that make deployment-status command works."""
        result = subprocess.run(
            ["make", "deployment-status"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0
        assert "Deployment System Status:" in result.stdout
        assert "Total flows:" in result.stdout

    def test_validate_deployments_command(self):
        """Test that make validate-deployments command works."""
        result = subprocess.run(
            ["make", "validate-deployments"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0
        assert "Validating deployments" in result.stdout

    def test_build_deployments_command(self):
        """Test that make build-deployments command works."""
        result = subprocess.run(
            ["make", "build-deployments"], capture_output=True, text=True, timeout=60
        )

        assert result.returncode == 0
        assert "Building deployments" in result.stdout
        assert "deployments" in result.stdout

    def test_help_includes_deployment_commands(self):
        """Test that make help includes deployment system commands."""
        result = subprocess.run(
            ["make", "help"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0
        assert "discover-flows" in result.stdout
        assert "build-deployments" in result.stdout
        assert "deploy-python" in result.stdout
        assert "deploy-containers" in result.stdout
        assert "deploy-all" in result.stdout
        assert "clean-deployments" in result.stdout
        assert "deployment-status" in result.stdout

    def test_cli_help_command(self):
        """Test that the CLI help command works."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "deployment_system.cli.main", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "Prefect Deployment System CLI" in result.stdout
        assert "discover-flows" in result.stdout
        assert "build-deployments" in result.stdout

    def test_environment_specific_commands_exist(self):
        """Test that environment-specific commands are available."""
        result = subprocess.run(
            ["make", "help"], capture_output=True, text=True, timeout=30
        )

        assert result.returncode == 0
        assert "deploy-dev" in result.stdout
        assert "deploy-staging" in result.stdout
        assert "deploy-prod" in result.stdout
        assert "deploy-dev-python" in result.stdout
        assert "deploy-dev-containers" in result.stdout

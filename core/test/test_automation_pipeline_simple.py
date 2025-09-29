#!/usr/bin/env python3
"""
Simple tests for the Test Automation Pipeline

Basic unit tests that verify core functionality without complex async operations
or external dependencies that might cause hanging.
"""

import pytest
from unittest.mock import Mock

from core.config import ConfigManager
from core.test.test_automation_pipeline import AutomationPipeline, TrendAnalyzer


class TestAutomationPipelineBasic:
    """Basic tests for automation pipeline functionality"""

    def setup_method(self):
        """Setup for each test method"""
        self.config_manager = ConfigManager()
        self.mock_db = Mock()
        self.database_managers = {"rpa_db": self.mock_db}

    def test_pipeline_initialization(self):
        """Test that pipeline initializes correctly"""
        pipeline = AutomationPipeline(
            database_managers=self.database_managers, config_manager=self.config_manager
        )

        assert pipeline is not None
        assert pipeline.database_managers == self.database_managers
        assert pipeline.config_manager == self.config_manager
        assert len(pipeline.test_categories) > 0
        assert len(pipeline.chaos_scenarios) > 0

    def test_pipeline_with_empty_databases(self):
        """Test pipeline handles empty database managers"""
        pipeline = AutomationPipeline(
            database_managers={}, config_manager=self.config_manager
        )

        assert pipeline is not None
        assert len(pipeline.database_managers) == 0
        assert len(pipeline.test_categories) > 0

    def test_test_categories_structure(self):
        """Test that test categories are properly structured"""
        pipeline = AutomationPipeline(
            database_managers=self.database_managers, config_manager=self.config_manager
        )

        # Check that required categories exist
        required_categories = ["unit", "integration", "container"]
        for category in required_categories:
            assert category in pipeline.test_categories

        # Check category structure
        for category_name, category in pipeline.test_categories.items():
            assert hasattr(category, "name")
            assert hasattr(category, "description")
            assert hasattr(category, "test_files")
            assert isinstance(category.test_files, list)

    def test_chaos_scenarios_structure(self):
        """Test that chaos scenarios are properly structured"""
        pipeline = AutomationPipeline(
            database_managers=self.database_managers, config_manager=self.config_manager
        )

        assert len(pipeline.chaos_scenarios) > 0

        for scenario in pipeline.chaos_scenarios:
            assert hasattr(scenario, "name")
            assert hasattr(scenario, "failure_type")
            assert hasattr(scenario, "duration_seconds")
            assert scenario.duration_seconds > 0

    def test_execution_order_calculation(self):
        """Test execution order calculation"""
        pipeline = AutomationPipeline(
            database_managers=self.database_managers, config_manager=self.config_manager
        )

        execution_order = pipeline._calculate_execution_order()

        assert isinstance(execution_order, list)
        assert len(execution_order) > 0

        # Unit tests should come before integration tests if both exist
        if "unit" in execution_order and "integration" in execution_order:
            unit_index = execution_order.index("unit")
            integration_index = execution_order.index("integration")
            assert unit_index < integration_index

    def test_ci_config_generation(self):
        """Test CI/CD configuration generation"""
        pipeline = AutomationPipeline(
            database_managers=self.database_managers, config_manager=self.config_manager
        )

        # Test GitHub Actions config
        github_config = pipeline.generate_ci_config("github")
        assert "name: Container Testing Pipeline" in github_config
        assert "on:" in github_config
        assert "jobs:" in github_config

        # Test GitLab CI config
        gitlab_config = pipeline.generate_ci_config("gitlab")
        assert "stages:" in gitlab_config
        assert "test" in gitlab_config

        # Test Jenkins config
        jenkins_config = pipeline.generate_ci_config("jenkins")
        assert "pipeline {" in jenkins_config
        assert "stages {" in jenkins_config


class TestTrendAnalyzerBasic:
    """Basic tests for trend analyzer"""

    def test_trend_analyzer_initialization(self):
        """Test trend analyzer initialization"""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            analyzer = TrendAnalyzer(temp_dir)

            assert analyzer is not None
            assert analyzer.results_dir.exists()

    def test_trend_analyzer_empty_analysis(self):
        """Test trend analyzer with no data"""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            analyzer = TrendAnalyzer(temp_dir)

            # Should handle empty data gracefully
            trends = analyzer.analyze_trends(days_back=1)
            assert "error" in trends or "total_pipeline_runs" in trends


class TestConfigurationValidation:
    """Test configuration validation"""

    def test_config_manager_initialization(self):
        """Test that config manager initializes"""
        config_manager = ConfigManager()
        assert config_manager is not None
        assert config_manager.environment is not None

    def test_pipeline_config_loading(self):
        """Test that pipeline can load its configuration"""
        config_manager = ConfigManager()
        pipeline = AutomationPipeline({}, config_manager)

        # Should not raise exceptions
        assert pipeline is not None
        assert len(pipeline.test_categories) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

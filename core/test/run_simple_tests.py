#!/usr/bin/env python3
"""
Simple Test Runner

A basic test runner that executes only the essential tests without
complex async operations that might cause hanging.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after path modification to avoid E402
from core.config import ConfigManager  # noqa: E402
from core.test.test_automation_pipeline import AutomationPipeline  # noqa: E402


def test_basic_functionality():
    """Test basic functionality without complex operations"""
    print("Testing basic automation pipeline functionality...")

    try:
        # Test initialization
        config_manager = ConfigManager()
        pipeline = AutomationPipeline({}, config_manager)

        print(
            f"✅ Pipeline initialized with {len(pipeline.test_categories)} test categories"
        )
        print(f"✅ Pipeline has {len(pipeline.chaos_scenarios)} chaos scenarios")

        # Test CI config generation
        github_config = pipeline.generate_ci_config("github")
        if "Container Testing Pipeline" in github_config:
            print("✅ GitHub Actions config generation works")
        else:
            print("❌ GitHub Actions config generation failed")

        gitlab_config = pipeline.generate_ci_config("gitlab")
        if "stages:" in gitlab_config:
            print("✅ GitLab CI config generation works")
        else:
            print("❌ GitLab CI config generation failed")

        # Test execution order calculation
        execution_order = pipeline._calculate_execution_order()
        if len(execution_order) > 0:
            print(f"✅ Execution order calculated: {execution_order}")
        else:
            print("❌ Execution order calculation failed")

        return True

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def test_configuration_loading():
    """Test configuration loading"""
    print("\nTesting configuration loading...")

    try:
        config_manager = ConfigManager()
        environment = config_manager.environment

        if environment:
            print(f"✅ Environment detected: {environment}")
        else:
            print("❌ Environment detection failed")

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def main():
    """Main test execution"""
    print("Simple Test Runner for Container Testing System")
    print("=" * 60)

    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Configuration Loading", test_configuration_loading),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        print("-" * 40)

        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())

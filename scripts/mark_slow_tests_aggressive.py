#!/usr/bin/env python3
"""
Script to mark slow tests more aggressively based on duration analysis.
Marks tests taking >2 seconds as slow.
"""

import re
from pathlib import Path

# Tests that take >2 seconds based on the duration report
SLOW_TESTS = [
    # Container lifecycle tests (20+ seconds)
    ("core/test/test_container_lifecycle_manager.py", "test_restart_attempt_success"),
    ("core/test/test_container_lifecycle_manager.py", "test_restart_count_reset_outside_window"),
    ("core/test/test_container_lifecycle_manager.py", "test_check_dependencies_success"),
    ("core/test/test_container_lifecycle_manager.py", "test_check_dependencies_with_retry"),
    ("core/test/test_container_lifecycle_manager.py", "test_check_dependencies_required_failure"),

    # Container config tests (5+ seconds)
    ("core/test/test_container_config.py", "test_wait_for_dependencies_timeout"),

    # Distributed tests with retries (6+ seconds)
    ("core/test/test_distributed.py", "test_claim_records_batch_with_retry_transient_failure"),
    ("core/test/test_distributed.py", "test_mark_record_completed_with_retry_transient_failure"),
    ("core/test/test_distributed.py", "test_retry_only_on_transient_errors"),

    # Database manager retry tests (2+ seconds)
    ("core/test/test_database_manager.py", "test_health_check_with_retry_exhausted_attempts"),
    ("core/test/test_database_manager.py", "test_execute_query_with_retry_transient_failure_then_success"),
    ("core/test/test_database_manager.py", "test_execute_query_with_retry_exhausted_attempts"),
    ("core/test/test_database_manager.py", "test_health_check_with_retry_connection_failure_then_success"),

    # Service orchestrator tests (2+ seconds)
    ("core/test/test_service_orchestrator_integration.py", "test_service_dependency_timeout_scenario"),
    ("core/test/test_service_orchestrator_integration.py", "test_database_connection_retry_with_exponential_backoff"),
    ("core/test/test_service_orchestrator_integration.py", "test_health_check_caching_behavior"),

    # Flow template config tests (2+ seconds)
    ("core/test/test_flow_template_config.py", "test_distributed_processing_flow_config_validation"),

    # Security validator tests (2+ seconds)
    ("core/test/test_security_validator.py", "test_real_user_permissions_check"),
]

def mark_test_as_slow(file_path: str, test_name: str) -> bool:
    """Mark a specific test as slow if not already marked."""
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    content = path.read_text()

    # Look for the test function
    pattern = rf"(\s+)def {re.escape(test_name)}\(.*?\):"
    match = re.search(pattern, content)

    if not match:
        print(f"❌ Test not found: {test_name} in {file_path}")
        return False

    # Check if already marked as slow
    before_function = content[:match.start()]
    if "@pytest.mark.slow" in before_function.split("def " + test_name)[0].split("def ")[-1]:
        print(f"✅ Already marked: {test_name} in {file_path}")
        return False

    # Add the slow marker
    indentation = match.group(1)
    replacement = f"{indentation}@pytest.mark.slow\n{match.group(0)}"
    new_content = content[:match.start()] + replacement + content[match.end():]

    # Ensure pytest is imported
    if "import pytest" not in new_content:
        # Find the best place to add the import
        import_lines = []
        lines = new_content.split('\n')
        insert_index = 0

        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_lines.append(i)
                insert_index = i + 1
            elif line.strip() == "" and import_lines:
                insert_index = i
                break

        if import_lines:
            lines.insert(insert_index, "import pytest")
            new_content = '\n'.join(lines)
        else:
            # Add at the beginning if no imports found
            new_content = "import pytest\n\n" + new_content

    path.write_text(new_content)
    print(f"✅ Marked as slow: {test_name} in {file_path}")
    return True

def main():
    """Mark all identified slow tests."""
    print("🔍 Marking slow tests (>2 seconds)...")

    marked_count = 0
    for file_path, test_name in SLOW_TESTS:
        if mark_test_as_slow(file_path, test_name):
            marked_count += 1

    print(f"\n✅ Marked {marked_count} additional tests as slow")
    print("🏃 Fast tests should now be much faster!")

if __name__ == "__main__":
    main()

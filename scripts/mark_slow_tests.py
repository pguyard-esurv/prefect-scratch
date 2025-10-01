#!/usr/bin/env python3
"""
Script to automatically identify and mark slow tests.
Adds @pytest.mark.slow to tests that are likely to be slow based on patterns.
"""

import re
from pathlib import Path


def identify_slow_test_files() -> list[str]:
    """Identify test files that are likely to contain slow tests."""
    slow_patterns = [
        "performance",
        "integration",
        "container",
        "distributed",
        "database_performance",
        "health_monitoring_integration",
        "deployment_automation",
        "automation_pipeline"
    ]

    test_dir = Path("core/test")
    slow_files = []

    for test_file in test_dir.glob("test_*.py"):
        filename = test_file.name
        if any(pattern in filename for pattern in slow_patterns):
            slow_files.append(str(test_file))

    return slow_files

def identify_slow_test_patterns(file_content: str) -> list[tuple[int, str]]:
    """Identify test functions that are likely to be slow."""
    slow_patterns = [
        r'time\.sleep\(',
        r'asyncio\.sleep\(',
        r'docker',
        r'subprocess',
        r'requests\.',
        r'for.*range\(.*100',  # Large loops
        r'@pytest\.mark\.integration',
        r'@pytest\.mark\.performance',
        r'test.*performance',
        r'test.*integration',
        r'test.*container',
        r'test.*distributed'
    ]

    lines = file_content.split('\n')
    slow_test_lines = []

    for i, line in enumerate(lines):
        # Look for test function definitions
        if re.match(r'\s*def test_', line):
            test_name = line.strip()
            # Check if this test or the next few lines contain slow patterns
            test_block = '\n'.join(lines[i:i+20])  # Check next 20 lines
            if any(re.search(pattern, test_block, re.IGNORECASE) for pattern in slow_patterns):
                slow_test_lines.append((i, test_name))

    return slow_test_lines

def add_slow_markers(file_path: str) -> bool:
    """Add @pytest.mark.slow to identified slow tests."""
    with open(file_path) as f:
        content = f.read()

    lines = content.split('\n')
    slow_tests = identify_slow_test_patterns(content)

    if not slow_tests:
        return False

    # Add imports if needed
    has_pytest_import = any('import pytest' in line for line in lines[:20])
    modified = False

    if not has_pytest_import:
        # Find where to add import
        import_line = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_line = i + 1
        lines.insert(import_line, 'import pytest')
        modified = True
        # Adjust line numbers for slow tests
        slow_tests = [(line_num + 1, test_name) for line_num, test_name in slow_tests]

    # Add markers to slow tests
    for line_num, _test_name in reversed(slow_tests):  # Reverse to maintain line numbers
        # Check if marker already exists
        if line_num > 0 and '@pytest.mark.slow' in lines[line_num - 1]:
            continue

        # Find the actual function line (might have moved due to imports)
        actual_line = None
        for i in range(max(0, line_num - 2), min(len(lines), line_num + 3)):
            if lines[i].strip().startswith('def test_'):
                actual_line = i
                break

        if actual_line is not None:
            # Add marker before the test function
            indent = len(lines[actual_line]) - len(lines[actual_line].lstrip())
            marker = ' ' * indent + '@pytest.mark.slow'
            lines.insert(actual_line, marker)
            modified = True

    if modified:
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
        return True

    return False

def main():
    """Main function to mark slow tests."""
    print("🔍 Identifying slow test files...")
    slow_files = identify_slow_test_files()

    print(f"Found {len(slow_files)} potentially slow test files:")
    for file in slow_files:
        print(f"  - {file}")

    print("\n🏷️  Adding @pytest.mark.slow markers...")
    modified_files = []

    for file_path in slow_files:
        if add_slow_markers(file_path):
            modified_files.append(file_path)
            print(f"  ✅ Modified: {file_path}")
        else:
            print(f"  ℹ️  No changes needed: {file_path}")

    print(f"\n🎉 Complete! Modified {len(modified_files)} files.")

    if modified_files:
        print("\nYou can now use:")
        print("  make test-fast    # Run only fast tests")
        print("  make test-slow    # Run only slow tests")
        print("  make test         # Run all tests")

if __name__ == "__main__":
    main()

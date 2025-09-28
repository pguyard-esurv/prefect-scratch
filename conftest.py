"""Pytest configuration and fixtures for Prefect testing."""

import pytest
from prefect.testing.utilities import prefect_test_harness


@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    """Session-scoped fixture for Prefect test harness.

    This fixture provides a clean Prefect environment for all tests,
    using an ephemeral SQLite database for isolation.
    """
    with prefect_test_harness():
        yield

import pytest


def pytest_configure(config):
    """Configure pytest for our tests"""
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test"
    )


@pytest.fixture(autouse=True)
def env_setup(monkeypatch):
    """Set up environment variables for testing"""
    # You could add environment variables here if needed
    pass 
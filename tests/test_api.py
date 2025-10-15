"""
Basic API endpoint tests.
Note: These tests require mocking or a test database setup.
"""
import pytest


def test_root_endpoint(client):
    """Test the root endpoint returns app information."""
    # This test requires MongoDB to be properly mocked
    # Skipping for now as it needs more setup
    pytest.skip("Requires MongoDB mock setup")


def test_config_validation():
    """Test configuration validation."""
    from app.core.config import settings
    
    # Verify critical settings are present
    assert settings.AGENT_BASE_URL is not None
    assert settings.AGENT_MODEL is not None
    assert settings.MAX_FILE_SIZE_MB > 0
    assert settings.MAX_FILE_SIZE_MB <= 500

"""
Pytest configuration and fixtures for testing EcoOpen LLM.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI application.
    Note: This fixture requires MongoDB and other dependencies to be mocked or available.
    """
    # Import here to avoid circular imports
    from app.main import app
    return TestClient(app)

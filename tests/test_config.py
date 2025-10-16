"""
Test configuration and settings validation.
"""
import pytest
from app.core.config import Settings


def test_default_settings(monkeypatch):
    """Test that default settings are properly initialized."""
    # Override environment to avoid local .env influencing defaults
    monkeypatch.setenv("AGENT_MODEL", "")
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    settings = Settings()

    assert settings.MAX_FILE_SIZE_MB == 50
    assert settings.AGENT_MODEL == "llama3.1"
    assert settings.OLLAMA_EMBED_MODEL == "nomic-embed-text"
    assert settings.LOG_LEVEL == "INFO"
    assert "localhost" in settings.CORS_ORIGINS[0]


def test_agent_base_url_normalization():
    """Test that AGENT_BASE_URL is normalized correctly."""
    # Test with trailing slash
    settings = Settings(_env_file=None, AGENT_BASE_URL="http://localhost:11434/v1/")
    assert settings.AGENT_BASE_URL == "http://localhost:11434/v1"

    # Test with empty value
    settings = Settings(_env_file=None, AGENT_BASE_URL="")
    assert settings.AGENT_BASE_URL == "http://localhost:11434/v1"


def test_log_level_validation():
    """Test that log level validation works correctly."""
    # Valid log level
    settings = Settings(_env_file=None, LOG_LEVEL="DEBUG")
    assert settings.LOG_LEVEL == "DEBUG"

    # Invalid log level should default to INFO
    settings = Settings(_env_file=None, LOG_LEVEL="INVALID")
    assert settings.LOG_LEVEL == "INFO"

    # Case insensitive
    settings = Settings(_env_file=None, LOG_LEVEL="debug")
    assert settings.LOG_LEVEL == "DEBUG"


def test_cors_origins_parsing():
    """Test CORS origins parsing from different formats."""
    # JSON array format
    settings = Settings(_env_file=None, CORS_ORIGINS='["http://example.com", "http://test.com"]')
    assert "http://example.com" in settings.CORS_ORIGINS
    assert "http://test.com" in settings.CORS_ORIGINS

    # Comma-separated format
    settings = Settings(_env_file=None, CORS_ORIGINS="http://example.com, http://test.com")
    assert "http://example.com" in settings.CORS_ORIGINS
    assert "http://test.com" in settings.CORS_ORIGINS

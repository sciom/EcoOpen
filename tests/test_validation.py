"""
Test validation utilities.
"""
import pytest
from app.core.validation import (
    validate_doi,
    validate_url,
    sanitize_filename,
    validate_file_extension,
)


def test_validate_doi_valid():
    """Test DOI validation with valid DOIs."""
    assert validate_doi("10.1234/test") == "10.1234/test"
    assert validate_doi("doi:10.1234/test") == "10.1234/test"
    assert validate_doi("https://doi.org/10.1234/test") == "10.1234/test"
    assert validate_doi("http://dx.doi.org/10.1234/test.v1") == "10.1234/test.v1"


def test_validate_doi_invalid():
    """Test DOI validation with invalid DOIs."""
    assert validate_doi(None) is None
    assert validate_doi("") is None
    assert validate_doi("not-a-doi") is None
    assert validate_doi("11.1234/test") is None  # Must start with 10.


def test_validate_url_valid():
    """Test URL validation with valid URLs."""
    assert validate_url("http://example.com") is True
    assert validate_url("https://github.com/user/repo") is True
    assert validate_url("https://data.example.org/dataset/123") is True


def test_validate_url_invalid():
    """Test URL validation with invalid URLs."""
    assert validate_url("") is False
    assert validate_url("not-a-url") is False
    assert validate_url("ftp://example.com") is False  # Only http/https
    assert validate_url("http://") is False
    assert validate_url("short") is False


def test_sanitize_filename():
    """Test filename sanitization."""
    # Normal filename
    assert sanitize_filename("document.pdf") == "document.pdf"
    
    # Path traversal attempts - leading dots are stripped
    result = sanitize_filename("../../../etc/passwd")
    assert "/" not in result and "\\" not in result
    assert "etc_passwd" in result
    
    result = sanitize_filename("..\\windows\\system32")
    assert "/" not in result and "\\" not in result
    assert "windows_system32" in result
    
    # Null bytes
    assert sanitize_filename("file\x00.pdf") == "file.pdf"
    
    # Leading dots and spaces
    assert sanitize_filename("  ...file.pdf") == "file.pdf"
    
    # Empty or None
    assert sanitize_filename("") == "unnamed.pdf"
    
    # Long filename
    long_name = "a" * 300 + ".pdf"
    result = sanitize_filename(long_name)
    assert len(result) <= 255
    assert result.endswith(".pdf")


def test_validate_file_extension():
    """Test file extension validation."""
    allowed = {".pdf", ".txt"}
    
    assert validate_file_extension("document.pdf", allowed) is True
    assert validate_file_extension("document.txt", allowed) is True
    assert validate_file_extension("document.PDF", allowed) is True  # Case insensitive
    assert validate_file_extension("document.doc", allowed) is False
    assert validate_file_extension("document", allowed) is False
    assert validate_file_extension("", allowed) is False

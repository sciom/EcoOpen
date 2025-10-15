"""
Validation utilities for input sanitization and security.
"""
import re
from typing import Optional


def validate_doi(doi: Optional[str]) -> Optional[str]:
    """
    Validate and normalize a DOI string.
    
    Args:
        doi: DOI string to validate
        
    Returns:
        Normalized DOI string or None if invalid
    """
    if not doi:
        return None
    
    doi = doi.strip()
    
    # Remove common prefixes and URLs
    doi = re.sub(r"^(?:doi:|DOI:|https?://(?:dx\.)?doi\.org/)", "", doi)
    doi = doi.strip()
    
    # Basic DOI pattern validation - must start with 10.
    doi_pattern = r"^10\.\d{4,9}/[^\s\"<>]+$"
    if re.match(doi_pattern, doi):
        # Clean up trailing punctuation
        doi = re.sub(r"[.,;)\]]+$", "", doi)
        return doi
    
    return None


def validate_url(url: str) -> bool:
    """
    Validate if a string is a reasonable URL.
    
    Args:
        url: URL string to validate
        
    Returns:
        True if the URL looks valid
    """
    if not url or len(url) < 10:
        return False
    
    # Basic URL pattern check
    url_pattern = r"^https?://[a-zA-Z0-9][\w\-\.]*\.[a-zA-Z]{2,}(/[^\s]*)?$"
    return bool(re.match(url_pattern, url))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
    if not filename:
        return "unnamed.pdf"
    
    # Remove directory separators and null bytes
    filename = filename.replace("\x00", "").replace("/", "_").replace("\\", "_")
    
    # Remove leading dots and spaces
    filename = filename.lstrip(". ")
    
    # Limit length
    if len(filename) > 255:
        # Keep extension if present
        parts = filename.rsplit(".", 1)
        if len(parts) == 2:
            name, ext = parts
            filename = name[:250] + "." + ext[:10]
        else:
            filename = filename[:255]
    
    return filename or "unnamed.pdf"


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Check if a filename has an allowed extension.
    
    Args:
        filename: Filename to check
        allowed_extensions: Set of allowed extensions (e.g., {'.pdf', '.txt'})
        
    Returns:
        True if extension is allowed
    """
    if not filename:
        return False
    
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return f".{ext}" in allowed_extensions or ext in {e.lstrip(".") for e in allowed_extensions}

"""
Domain-specific errors for PDF analysis pipeline.
These help distinguish functional failures from transport/API errors.
"""

class DomainError(Exception):
    """Base class for domain-level errors."""


class InvalidPDFError(DomainError):
    """Raised when the uploaded/loaded file is not a valid PDF or cannot be parsed as a PDF."""


class PDFReadError(DomainError):
    """Raised when there is a problem reading PDF content from storage or filesystem."""


class EmbeddingModelMissingError(DomainError):
    """Raised when the required embedding model is not available on the embeddings backend."""


class LLMServiceError(DomainError):
    """Raised when the LLM service is unreachable or returns an error that prevents analysis."""


class AnalysisTimeoutError(DomainError):
    """Raised when an analysis operation exceeds the configured timeout."""

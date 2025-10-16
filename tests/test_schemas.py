"""
Test data models and schemas.
"""
import pytest
from app.models.schemas import (
    PDFAnalysisResultModel,
    BatchProgress,
    BatchStatusModel,
    HealthModel,
)


def test_pdf_analysis_result_model():
    """Test PDFAnalysisResultModel creation and validation."""
    result = PDFAnalysisResultModel(
        title="Test Paper",
        doi="10.1234/test",
        data_availability_statement="Data is available",
        source_file="test.pdf"
    )

    assert result.title == "Test Paper"
    assert result.doi == "10.1234/test"
    assert result.data_availability_statement == "Data is available"
    assert result.source_file == "test.pdf"
    assert result.data_links == []
    assert result.code_links == []
    assert result.confidence_scores == {}


def test_pdf_analysis_result_with_links():
    """Test PDFAnalysisResultModel with links."""
    result = PDFAnalysisResultModel(
        title="Test Paper",
        data_links=["http://example.com/data"],
        code_links=["http://github.com/repo"]
    )

    assert len(result.data_links) == 1
    assert len(result.code_links) == 1
    assert result.data_links[0] == "http://example.com/data"


def test_batch_progress_model():
    """Test BatchProgress model."""
    progress = BatchProgress(current=5, total=10)

    assert progress.current == 5
    assert progress.total == 10


def test_batch_status_model():
    """Test BatchStatusModel creation."""
    progress = BatchProgress(current=0, total=5)
    status = BatchStatusModel(
        job_id="test-job-123",
        status="queued",
        progress=progress
    )

    assert status.job_id == "test-job-123"
    assert status.status == "queued"
    assert status.progress.current == 0
    assert status.progress.total == 5
    assert status.results is None


def test_health_model():
    """Test HealthModel creation."""
    health = HealthModel(
        status="ok",
        agent_model="llama3.1",
        agent_reachable=True,
        embeddings_reachable=True
    )

    assert health.status == "ok"
    assert health.agent_model == "llama3.1"
    assert health.agent_reachable is True
    assert health.embeddings_reachable is True

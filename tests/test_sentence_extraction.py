"""
Tests for sentence extraction in PDF parsing.
"""

import pytest
from app.services.agent import AgentRunner


class TestSentenceExtraction:
    """Test sentence extraction functionality in AgentRunner._normalize_text."""

    @pytest.fixture
    def runner(self):
        """Create an AgentRunner instance for testing."""
        return AgentRunner.__new__(AgentRunner)

    def test_simple_sentences(self, runner):
        """Test extraction of simple sentences."""
        text = "This is the first sentence. This is the second sentence."
        result = runner._normalize_text(text)
        assert "first sentence" in result
        assert "second sentence" in result
        # Sentences should be on separate lines or clearly separated
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        assert len(lines) >= 2

    def test_mixed_punctuation(self, runner):
        """Test sentences with different punctuation marks."""
        text = "Is this a question? Yes it is! This is a statement."
        result = runner._normalize_text(text)
        assert "question" in result
        assert "Yes it is" in result
        assert "statement" in result
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        assert len(lines) >= 3

    def test_semicolon_separation(self, runner):
        """Test that semicolons properly separate clauses."""
        text = "This is the first clause; this is the second clause."
        result = runner._normalize_text(text)
        assert "first clause" in result
        assert "second clause" in result

    def test_multiline_text(self, runner):
        """Test text that already has line breaks."""
        text = "First sentence.\nSecond sentence on new line.\nThird sentence."
        result = runner._normalize_text(text)
        assert "First sentence" in result
        assert "Second sentence" in result
        assert "Third sentence" in result

    def test_sentences_on_same_line(self, runner):
        """Test multiple sentences on the same line get separated."""
        text = "Sentence one. Sentence two. Sentence three."
        result = runner._normalize_text(text)
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        # Should have separate sentences
        assert len(lines) >= 2

    def test_preserves_urls(self, runner):
        """Test that URLs are preserved correctly."""
        text = "Visit https://example.com for more. This is another sentence."
        result = runner._normalize_text(text)
        assert "https://example.com" in result
        assert "another sentence" in result

    def test_hyphenated_words(self, runner):
        """Test that hyphenated words across lines are joined."""
        text = "This is a hyphen-\nated word in a sentence. Next sentence."
        result = runner._normalize_text(text)
        assert "hyphenated" in result
        assert "Next sentence" in result

    def test_empty_text(self, runner):
        """Test handling of empty text."""
        result = runner._normalize_text("")
        assert result == ""

    def test_no_punctuation(self, runner):
        """Test text without sentence-ending punctuation."""
        text = "This is some text without proper punctuation"
        result = runner._normalize_text(text)
        assert "text without proper punctuation" in result

    def test_no_extra_spaces_before_punctuation(self, runner):
        """Test that punctuation is properly attached without extra spaces."""
        text = "First sentence. Second sentence!"
        result = runner._normalize_text(text)
        # Should not have space before punctuation
        assert "sentence ." not in result
        assert "sentence !" not in result
        assert "sentence." in result
        assert "sentence!" in result

    def test_sentence_wrapping_across_lines(self, runner):
        """Test that sentences wrapping across lines are properly joined."""
        text = "The data underlying this article\nare available in the repository. Next sentence."
        result = runner._normalize_text(text)
        # Should join the wrapped sentence
        assert "article are available" in result
        # Should still separate sentences
        lines = [line.strip() for line in result.split("\n") if line.strip()]
        assert len(lines) >= 2

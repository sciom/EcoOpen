"""
Fast and clean PDF text extraction using PyMuPDF (fitz).
Optimized for clear text PDFs (non-OCR scientific papers).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

logger = logging.getLogger(__name__)


@dataclass
class ParagraphBlock:
    text: str
    page: int
    column: int
    seq: int


class PyMuPDFExtractor:
    """Fast PDF text extractor using PyMuPDF for clean text PDFs."""
    
    def __init__(self):
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) not installed. Install with: pip install pymupdf")
    
    def extract(self, pdf_path: str) -> List[ParagraphBlock]:
        """Extract text blocks from PDF with proper spacing and layout preservation."""
        blocks: List[ParagraphBlock] = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text with layout preservation
                # flags=0 gives clean text, flags=fitz.TEXT_PRESERVE_WHITESPACE preserves layout
                text = page.get_text("text")
                
                if not text.strip():
                    continue
                
                # Split into paragraphs (double newline = paragraph break)
                paragraphs = self._split_paragraphs(text)
                
                for seq, para in enumerate(paragraphs):
                    if para.strip():
                        blocks.append(
                            ParagraphBlock(
                                text=para.strip(),
                                page=page_num + 1,
                                column=0,
                                seq=seq,
                            )
                        )
            
            doc.close()
            
            if not blocks:
                raise ValueError("No text content found in PDF")
            
            logger.debug(f"PyMuPDF extracted {len(blocks)} blocks from PDF")
            return blocks
            
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {e}")
            raise
    
    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs while preserving structure."""
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split on double newlines (paragraph breaks)
        paragraphs = []
        current = []
        
        lines = text.split('\n')
        for line in lines:
            line_stripped = line.strip()
            
            if not line_stripped:
                # Empty line = paragraph break
                if current:
                    paragraphs.append(' '.join(current))
                    current = []
            else:
                current.append(line_stripped)
        
        # Add last paragraph
        if current:
            paragraphs.append(' '.join(current))
        
        return paragraphs

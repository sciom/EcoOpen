#!/usr/bin/env python3
"""
EcoOpen - Simplified LLM-based Data Availability Extraction
===========================================================

A streamlined package for extracting data and code availability information from 
scientific PDFs using Large Language Models (Ollama + LangChain + ChromaDB).

Features:
- LLM-based intelligent extraction (no keyword matching)
- Direct PDF processing from DOIs or local files
- Clean CSV output with standardized columns
- Metadata extraction from OpenAlex API
- Simple, focused codebase

Author: Domagoj K. Hackenberger
License: MIT
"""

import os
import sys
import csv
import json
import logging
import tempfile
import requests
import pandas as pd
import time
import subprocess
import re
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from urllib.parse import urlparse, urljoin
import fitz  # PyMuPDF
from tqdm import tqdm

# LLM dependencies (graceful fallback if not available)
try:
    import chromadb
    # Disable ChromaDB telemetry to avoid version compatibility errors
    import chromadb.config
    from chromadb.config import Settings
    import os
    
    # Set environment variable to disable telemetry
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    # Create settings with telemetry disabled
    settings = Settings(anonymized_telemetry=False)
    
    from langchain_ollama import OllamaLLM, OllamaEmbeddings
    from langchain_community.document_loaders import PyPDFLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain.embeddings.base import Embeddings
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    print(f"LLM dependencies not available: {e}")
    print("Install with: pip install langchain langchain-ollama langchain-community langchain-chroma chromadb pypdf")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# Constants and Configuration
# =============================================================================

DEFAULT_OLLAMA_URL = "http://localhost:11434"
# Use auto-detection for optimal phi model selection (phi4 preferred, phi3:mini fallback)
DEFAULT_LLM_MODEL = None  # Will be auto-detected
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"

# Phi model recommendations - only phi4 for consistent quality
HARDWARE_OPTIMIZED_MODELS = [
    {"name": "phi4", "size_gb": 10.0, "quality": "excellent", "speed": "moderate", "min_vram": 4.0},
]

def get_gpu_memory() -> float:
    """Get available GPU memory in GB."""
    try:
        # Try nvidia-smi first
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            memory_mb = int(result.stdout.strip().split('\n')[0])
            return memory_mb / 1024.0
    except Exception:
        pass
    
    try:
        # Fallback: try to get from /proc if available
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if 'MemTotal' in line:
                    # Use system RAM as fallback (assume no GPU)
                    kb = int(line.split()[1])
                    return (kb / 1024 / 1024) * 0.1  # Use 10% of system RAM as conservative estimate
    except Exception:
        pass
    
    # Default fallback for unknown systems
    return 4.0  # Assume 4GB as conservative default

def get_optimal_model(available_vram_gb: float) -> str:
    """Always use phi4 for consistent quality - no fallbacks."""
    logger.info(f"Using phi4 for consistent quality (detected {available_vram_gb:.1f}GB VRAM)")
    
    if available_vram_gb >= 12.0:
        logger.info("✅ Sufficient VRAM for phi4 - using GPU acceleration")
    else:
        logger.warning(f"⚠️  Limited VRAM ({available_vram_gb:.1f}GB) - phi4 will run on CPU (slower but consistent quality)")
    
    logger.info(f"   Selected: phi4 (10GB, excellent quality)")
    return "phi4"

def auto_detect_best_model() -> str:
    """Always use phi4 for consistent quality."""
    try:
        # Get available VRAM for logging purposes
        available_vram = get_gpu_memory()
        optimal_model = get_optimal_model(available_vram)
        
        # Check if phi4 is available locally
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            available_models = result.stdout.lower()
            
            # Check if phi4 is available
            if "phi4" in available_models:
                logger.info(f"✅ Using phi4 (available locally)")
                return "phi4"
            else:
                logger.info(f"📥 phi4 not found locally")
                logger.info(f"   Install with: ollama pull phi4")
                logger.info(f"   Proceeding with phi4 anyway (will auto-download)")
                return "phi4"
        
    except Exception as e:
        logger.warning(f"Could not check available models: {e}")
    
    # Always return phi4
    logger.info("Using phi4 for consistent quality")
    return "phi4"

def check_ollama_performance() -> Dict[str, Any]:
    """Check Ollama model performance and provide optimization suggestions."""
    try:
        # Check what's currently running
        result = subprocess.run(['ollama', 'ps'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Skip header
                model_line = lines[1]
                # Split by multiple spaces to handle the columnar format
                import re
                parts = re.split(r'\s{2,}', model_line.strip())
                
                if len(parts) >= 4:
                    model_name = parts[0]
                    size_str = parts[2]
                    processor_info = parts[3]
                    
                    # Parse size (e.g., "10 GB")
                    size_gb = 0
                    if 'GB' in size_str:
                        size_gb = float(size_str.replace('GB', '').strip())
                    elif 'MB' in size_str:
                        size_gb = float(size_str.replace('MB', '').strip()) / 1024
                    
                    # Parse processor split (e.g., "31%/69% CPU/GPU")
                    cpu_pct = gpu_pct = 0
                    if '%' in processor_info and '/' in processor_info:
                        # Extract just the percentage part
                        percent_match = re.search(r'(\d+)%/(\d+)%', processor_info)
                        if percent_match:
                            cpu_pct = int(percent_match.group(1))
                            gpu_pct = int(percent_match.group(2))
                    
                    performance_info = {
                        'model_name': model_name,
                        'size_gb': round(size_gb, 1),
                        'cpu_percent': cpu_pct,
                        'gpu_percent': gpu_pct,
                        'is_fully_gpu': gpu_pct >= 95,
                        'is_mixed': 30 <= cpu_pct <= 70,
                        'recommendations': []
                    }
                    
                    if cpu_pct > 30:
                        performance_info['recommendations'].append(
                            f"Model is {cpu_pct}% on CPU - consider using a smaller model for faster processing"
                        )
                    
                    return performance_info
        
        return {"error": "No models currently running. Start a model with: ollama run phi4"}
    except Exception as e:
        return {"error": f"Performance check failed: {e}"}

# Required CSV columns in exact order (your specification)
CSV_COLUMNS = [
    'identifier', 'doi', 'title', 'authors', 'published', 'url', 'journal',
    'has_fulltext', 'is_oa', 'path', 'pdf_content_length', 'data_links',
    'data_availability_statements', 'code_availability_statements', 'format',
    'repository', 'repository_url', 'data_download_path', 'data_size',
    'number_of_files', 'license'
]

# =============================================================================
# LLM Extraction Engine
# =============================================================================

class SafeOllamaEmbeddings(Embeddings):
    """Safe wrapper for Ollama embeddings with string conversion."""
    
    def __init__(self, base_embeddings):
        self.base_embeddings = base_embeddings

    def embed_documents(self, texts):
        clean_texts = [str(t) if not isinstance(t, str) else t for t in texts]
        return self.base_embeddings.embed_documents(clean_texts)

    def embed_query(self, text):
        return self.base_embeddings.embed_query(str(text))


class LLMExtractor:
    """Simplified LLM-based data availability extractor."""
    
    def __init__(self, llm_model: str = None, 
                 embedding_model: str = DEFAULT_EMBEDDING_MODEL,
                 ollama_url: str = DEFAULT_OLLAMA_URL):
        if not LLM_AVAILABLE:
            raise ImportError("LLM dependencies not available. Install requirements_llm.txt")
        
        # Auto-detect best model if none specified
        if llm_model is None:
            llm_model = auto_detect_best_model()
        
        self.llm = OllamaLLM(model=llm_model, base_url=ollama_url)
        self.embeddings = SafeOllamaEmbeddings(
            OllamaEmbeddings(model=embedding_model, base_url=ollama_url)
        )
        
        # Use temporary ChromaDB for each extraction
        self.chroma_client = None
        logger.info(f"LLM extractor initialized with {llm_model}")

    def extract_from_pdf(self, pdf_content: bytes, allowed_formats: List[str] = None) -> Dict[str, Any]:
        """Extract availability and metadata from PDF using DOI + OpenAlex + LLM."""
        logger.info("Starting extraction with DOI + OpenAlex + LLM...")
        start_time = time.time()
        
        try:
            # Step 1: Extract DOI from PDF
            doi = extract_doi_from_pdf(pdf_content)
            
            # Step 2: Get metadata from OpenAlex if DOI found
            metadata = {}
            if doi:
                logger.info(f"📄 Found DOI: {doi}")
                metadata = fetch_openalex_metadata(doi)
                if metadata:
                    logger.info("✅ Successfully retrieved metadata from OpenAlex")
                else:
                    logger.warning("⚠️  OpenAlex metadata retrieval failed")
            else:
                logger.info("❌ No DOI found in PDF")
            
            # Step 3: Convert PDF to vector store for availability extraction
            vectorstore = self._pdf_to_vectorstore(pdf_content)
            
            # Step 4: Extract availability information using LLM (still needed)
            availability = self._extract_availability(vectorstore)
            
            # Step 5: Extract data URLs from text
            # Get more text for URL extraction
            all_docs = vectorstore.similarity_search("data code repository github zenodo figshare", k=20)
            full_text = "\n\n".join([doc.page_content for doc in all_docs])
            data_urls = extract_data_urls_from_text(full_text, allowed_formats)
            
            # Add data URLs to availability results
            if 'data_links' not in availability:
                availability['data_links'] = []
            availability['data_links'].extend(data_urls)
            
            # Step 6: If no metadata from OpenAlex, try LLM fallback (minimal)
            if not metadata or not metadata.get('title'):
                logger.info("📝 Falling back to LLM for basic metadata...")
                llm_metadata = self._extract_basic_metadata_llm(vectorstore)
                if llm_metadata:
                    # Merge with OpenAlex data (OpenAlex takes priority)
                    for key, value in llm_metadata.items():
                        if key not in metadata or not metadata[key]:
                            metadata[key] = value
            
            total_time = time.time() - start_time
            logger.info(f"✓ Total PDF processing time: {total_time:.1f}s")
            
            return {
                'availability': availability,
                'metadata': metadata,
                'success': True,
                'processing_time': total_time,
                'doi': doi,
                'data_urls': data_urls
            }
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                'availability': self._empty_availability(),
                'metadata': {},
                'success': False,
                'error': str(e),
                'doi': None,
                'data_urls': []
            }

    def _pdf_to_vectorstore(self, pdf_content: bytes) -> Chroma:
        """Convert PDF to searchable vector store with improved chunking for better structure preservation."""
        logger.info(f"Processing PDF ({len(pdf_content)} bytes)...")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_content)
            tmp_file_path = tmp_file.name

        try:
            logger.info("Loading PDF document...")
            loader = PyPDFLoader(tmp_file_path)
            documents = loader.load()
            logger.info(f"✓ Loaded {len(documents)} pages")

            # Improved chunking strategy for better structure preservation
            logger.info("Splitting document with structure-aware chunking...")
            
            # First, create larger chunks to preserve context
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,  # Larger chunks for better context
                chunk_overlap=300,  # More overlap to preserve relationships
                separators=[
                    "\n\n\n",  # Multiple line breaks (section separators)
                    "\n\n",    # Paragraph breaks
                    "\n",      # Line breaks
                    ". ",      # Sentence breaks
                    ", ",      # Clause breaks
                    " "        # Word breaks
                ],
                keep_separator=True  # Keep separators to preserve structure
            )
            splits = text_splitter.split_documents(documents)
            logger.info(f"✓ Created {len(splits)} text chunks")

            # Clean and prepare texts with enhanced metadata
            logger.info("Preparing text for embedding with enhanced metadata...")
            texts = []
            metadatas = []
            
            for i, doc in enumerate(splits):
                if doc.page_content.strip():
                    # Clean the text content
                    clean_content = doc.page_content.strip()
                    
                    # Add position-based importance weighting
                    page_num = doc.metadata.get('page', 0)
                    is_early_page = page_num <= 2  # Title/abstract usually on first 2 pages
                    
                    # Detect potential title/header content
                    lines = clean_content.split('\n')
                    first_line = lines[0].strip() if lines else ""
                    
                    # Enhanced metadata for better retrieval
                    metadata = doc.metadata.copy()
                    metadata.update({
                        'chunk_id': i,
                        'chunk_position': 'early' if i < 5 else 'middle' if i < len(splits) - 5 else 'late',
                        'is_early_page': is_early_page,
                        'first_line': first_line,
                        'content_length': len(clean_content),
                        'line_count': len(lines),
                        'has_caps': any(line.isupper() and len(line) > 5 for line in lines[:3]),  # Potential title in caps
                        'potential_title': is_early_page and len(first_line) > 10 and len(first_line) < 200
                    })
                    
                    texts.append(clean_content)
                    metadatas.append(metadata)

            if not texts:
                raise ValueError("No valid text found in PDF")
            
            logger.info(f"✓ Prepared {len(texts)} text chunks for embedding")
            logger.info(f"   - Early page chunks: {sum(1 for m in metadatas if m['is_early_page'])}")
            logger.info(f"   - Potential title chunks: {sum(1 for m in metadatas if m['potential_title'])}")

            # Create vector store with enhanced settings
            logger.info("Creating embeddings with improved retrieval settings...")
            vectorstore = Chroma.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas,
                collection_name=f"ecoopen_{hash(str(texts[:3]))}",
                client_settings=Settings(anonymized_telemetry=False)
            )
            logger.info("✓ Vector store created with enhanced embeddings")

            return vectorstore

        finally:
            os.unlink(tmp_file_path)

    def _extract_availability(self, vectorstore: Chroma) -> Dict[str, Any]:
        """Extract data and code availability using LLM."""
        logger.info("Searching for data/code availability sections...")
        
        # Use similarity search to find relevant sections
        availability_query = "data availability code availability software repository github zenodo dryad supplementary materials supporting information"
        docs = vectorstore.similarity_search(availability_query, k=10)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Limit context to prevent LLM confusion
        if len(context) > 3000:
            context = context[:3000] + "..."
        
        logger.info(f"Found {len(docs)} relevant chunks for availability analysis")
        
        prompt = PromptTemplate(
            input_variables=["context"],
            template="""
You are a scientific paper analyzer. Find data and code availability information.

Look for:
- Data availability statements
- Code/software availability 
- Repository mentions (GitHub, Zenodo, Dryad, etc.)
- Supplementary materials

Text from paper:
{context}

Respond with ONLY this exact JSON format (no extra text):
{{
  "data_statements": ["quote exact data availability text"],
  "code_statements": ["quote exact code availability text"],
  "data_urls": ["list any data URLs found"],
  "summary": "one sentence summary"
}}
"""
        )
        
        try:
            logger.info("Running LLM analysis for availability extraction...")
            result = self.llm.invoke(prompt.format(context=context))
            logger.debug(f"🔍 Raw LLM response: {result[:200]}...")
            
            # Clean and parse the result
            parsed_result = self._parse_simple_json_result(result)
            
            # Convert to expected format
            availability_result = {
                'data_availability': {
                    'found': bool(parsed_result.get('data_statements', [])),
                    'statements': parsed_result.get('data_statements', []),
                    'access_type': 'open' if parsed_result.get('data_statements') else 'not_available',
                    'repositories': [],
                    'urls': parsed_result.get('data_urls', [])
                },
                'code_availability': {
                    'found': bool(parsed_result.get('code_statements', [])),
                    'statements': parsed_result.get('code_statements', []),
                    'access_type': 'open' if parsed_result.get('code_statements') else 'not_available',
                    'repositories': [],
                    'urls': []
                },
                'data_links': parsed_result.get('data_urls', []),
                'summary': parsed_result.get('summary', 'No availability information found')
            }
            
            # Log what was found for debugging
            data_found = bool(parsed_result.get('data_statements', []))
            code_found = bool(parsed_result.get('code_statements', []))
            data_statements = parsed_result.get('data_statements', [])
            code_statements = parsed_result.get('code_statements', [])
            
            logger.info(f"� Extraction results: Data={data_found} ({len(data_statements)} statements), Code={code_found} ({len(code_statements)} statements)")
            
            return availability_result
        except Exception as e:
            logger.warning(f"LLM availability extraction failed: {e}")
            return self._empty_availability()

    def _extract_basic_metadata_llm(self, vectorstore: Chroma) -> Dict[str, Any]:
        """Extract basic metadata using LLM with improved title detection."""
        logger.info("Extracting basic metadata using improved LLM approach...")
        
        # Strategy 1: Look for chunks marked as potential titles
        title_docs = vectorstore.similarity_search(
            "title", 
            k=10,
            filter={"potential_title": True}  # Use enhanced metadata
        )
        
        # Strategy 2: If no title chunks found, get early page content
        if not title_docs:
            title_docs = vectorstore.similarity_search(
                "title abstract introduction", 
                k=5,
                filter={"is_early_page": True}
            )
        
        # Strategy 3: Fallback to first few chunks
        if not title_docs:
            title_docs = vectorstore.similarity_search("paper title research", k=3)
        
        # Combine contexts with emphasis on structure
        contexts = []
        for doc in title_docs:
            # Add structural hints to help LLM understand position
            page_info = f"[Page {doc.metadata.get('page', 'unknown')}]"
            chunk_pos = doc.metadata.get('chunk_position', 'unknown')
            position_hint = f"[{chunk_pos} document section]"
            
            context_with_hints = f"{page_info} {position_hint}\n{doc.page_content}"
            contexts.append(context_with_hints)
        
        full_context = "\n\n---\n\n".join(contexts)
        
        prompt = PromptTemplate(
            input_variables=["context"],
            template="""
You are extracting the main title from a scientific paper. Look carefully at the document structure.

The title is typically:
- At the top of the first page
- In larger font or caps
- Stands alone on lines
- Describes the research topic
- Is NOT: author names, affiliations, journal names, abstracts, or section headers

Document sections with position indicators:
{context}

Extract ONLY the main paper title. Return valid JSON:
{{
  "title": "exact main title of the paper"
}}
"""
        )
        
        try:
            logger.info("Running improved LLM analysis for title extraction...")
            logger.debug(f"Using {len(title_docs)} chunks for title extraction")
            
            result = self.llm.invoke(prompt.format(context=full_context))
            logger.debug(f"🔍 Raw LLM response for title: {result}")
            
            # Clean up the response
            result = result.strip()
            if result.startswith('```json'):
                result = result.replace('```json', '').replace('```', '').strip()
            
            parsed = json.loads(result)
            
            # Log extracted title for debugging
            title = parsed.get('title', 'NO TITLE FOUND')
            logger.info(f"📖 Improved LLM extracted title: {title}")
            
            return parsed
            
        except Exception as e:
            logger.warning(f"Improved LLM metadata extraction failed: {e}")
            
            # Enhanced fallback: try to extract title from structured text
            try:
                logger.info("Trying enhanced fallback title extraction...")
                
                # Look for lines that could be titles in early chunks
                for doc in title_docs:
                    if doc.metadata.get('is_early_page', False):
                        lines = doc.page_content.split('\n')
                        for i, line in enumerate(lines[:10]):
                            line = line.strip()
                            # Title heuristics
                            if (10 < len(line) < 200 and  # Reasonable length
                                not line.lower().startswith(('abstract', 'introduction', 'keywords', 'author', 'university', 'department')) and
                                not line.endswith((',', ';', ':')) and  # Not a fragment
                                not re.search(r'\d{4}', line)):  # Probably not a date/year line
                                
                                logger.info(f"Enhanced fallback found title: {line[:100]}...")
                                return {"title": line}
                
                # Final fallback
                if title_docs:
                    first_meaningful_line = None
                    for doc in title_docs:
                        lines = doc.page_content.split('\n')
                        for line in lines:
                            line = line.strip()
                            if len(line) > 15:  # Get first substantial line
                                first_meaningful_line = line
                                break
                        if first_meaningful_line:
                            break
                    
                    if first_meaningful_line:
                        logger.info(f"Final fallback title: {first_meaningful_line[:100]}...")
                        return {"title": first_meaningful_line}
                        
            except Exception as e2:
                logger.warning(f"Enhanced fallback also failed: {e2}")
            
            return {}

    def _parse_simple_json_result(self, result: str) -> Dict[str, Any]:
        """Parse LLM JSON result with robust fallback."""
        logger.debug(f"Attempting to parse simple LLM result: {result[:200]}...")
        
        try:
            # Try direct JSON parsing first
            parsed = json.loads(result)
            logger.debug("✓ Successfully parsed JSON directly")
            return parsed
        except json.JSONDecodeError:
            logger.debug("Direct JSON parsing failed, trying cleanup...")
            
            # Clean the result
            result = result.strip()
            
            # Remove markdown code blocks if present
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    logger.debug("✓ Successfully extracted JSON from markdown")
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON-like structure
            json_match = re.search(r'(\{.*?\})', result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    logger.debug("✓ Successfully extracted JSON structure")
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # If all parsing fails, create a simple structure from the text
            logger.warning(f"Failed to parse as JSON, creating fallback structure")
            return {
                'data_statements': [],
                'code_statements': [],
                'data_urls': [],
                'summary': 'Failed to parse LLM response'
            }

    def _parse_json_result(self, result: str) -> Dict[str, Any]:
        """Parse LLM JSON result with fallback."""
        logger.debug(f"Attempting to parse LLM result: {result[:200]}...")
        
        try:
            # Try direct JSON parsing
            parsed = json.loads(result)
            logger.debug("✓ Successfully parsed JSON directly")
            return parsed
        except json.JSONDecodeError as e:
            logger.debug(f"Direct JSON parsing failed: {e}")
            
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    logger.debug("✓ Successfully extracted JSON from markdown")
                    return parsed
                except json.JSONDecodeError as e2:
                    logger.debug(f"Markdown JSON parsing failed: {e2}")
            
            # Try to find JSON-like structure without markdown
            json_match = re.search(r'(\{.*?\})', result, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    logger.debug("✓ Successfully extracted JSON structure")
                    return parsed
                except json.JSONDecodeError as e3:
                    logger.debug(f"JSON structure parsing failed: {e3}")
            
            # Fallback: return raw text with error flag
            logger.warning(f"Failed to parse LLM response as JSON. Raw response: {result[:1000]}")
            return {
                'data_availability': {'found': False, 'statements': [result], 'access_type': 'unknown'},
                'code_availability': {'found': False, 'statements': [], 'access_type': 'unknown'},
                'data_links': [],
                'summary': 'Failed to parse LLM response',
                'raw_response': result,
                'parsing_error': True
            }

    def _empty_availability(self) -> Dict[str, Any]:
        """Return empty availability structure."""
        return {
            'data_availability': {'found': False, 'statements': [], 'access_type': 'not_available', 'repositories': [], 'urls': []},
            'code_availability': {'found': False, 'statements': [], 'access_type': 'not_available', 'repositories': [], 'urls': []},
            'data_links': [],
            'summary': 'No availability information found'
        }


# =============================================================================
# Metadata and PDF Handling
# =============================================================================

# This function was replaced by fetch_openalex_metadata for consistency


def download_pdf(url: str) -> Optional[bytes]:
    """Download PDF from URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200 and 'application/pdf' in response.headers.get('content-type', ''):
            return response.content
    except Exception as e:
        logger.warning(f"PDF download failed: {e}")
    
    return None


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """Extract text from PDF for basic analysis."""
    try:
        pdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
        text = ""
        for page in pdf_doc:
            text += page.get_text()
        pdf_doc.close()
        return text
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        return ""


# =============================================================================
# DOI Extraction and OpenAlex Integration
# =============================================================================

def extract_doi_from_text(text: str) -> Optional[str]:
    """Extract DOI from text using regex patterns."""
    # Common DOI patterns
    doi_patterns = [
        r'doi:\s*10\.\d{4,}/[^\s\]]+',  # doi: prefix
        r'DOI:\s*10\.\d{4,}/[^\s\]]+',  # DOI: prefix
        r'https?://doi\.org/10\.\d{4,}/[^\s\]]+',  # doi.org URL
        r'https?://dx\.doi\.org/10\.\d{4,}/[^\s\]]+',  # dx.doi.org URL
        r'10\.\d{4,}/[^\s\]]+',  # Plain DOI
    ]
    
    logger.debug(f"Searching for DOI in text ({len(text)} chars)...")
    
    for pattern in doi_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Clean up the DOI
            doi = match.replace('doi:', '').replace('DOI:', '')
            doi = doi.replace('https://doi.org/', '').replace('https://dx.doi.org/', '')
            doi = doi.strip()
            
            # Validate DOI format
            if re.match(r'10\.\d{4,}/\S+', doi):
                logger.info(f"📄 Found DOI: {doi}")
                return doi
    
    logger.debug("No DOI found in text")
    return None

# Try to import pdf2doi for robust DOI extraction
try:
    from pdf2doi.pdf2doi_extract import extract_doi as pdf2doi_extract_doi
    PDF2DOI_AVAILABLE = True
except ImportError:
    PDF2DOI_AVAILABLE = False
    pdf2doi_extract_doi = None

def extract_doi_from_pdf(pdf_content: bytes) -> Optional[str]:
    """Extract DOI from PDF using pdf2doi (if available), text extraction, and LLM fallback."""
    # 1. Try pdf2doi if available
    if PDF2DOI_AVAILABLE:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()
                result = pdf2doi_extract_doi(tmp_file.name)
                if result and isinstance(result, dict):
                    doi = result.get("doi")
                    if doi and isinstance(doi, str) and doi.startswith("10."):
                        logger.info(f"📄 Found DOI via pdf2doi: {doi}")
                        return doi
        except Exception as e:
            logger.warning(f"pdf2doi DOI extraction failed: {e}")
    # 2. Fallback: original text extraction and LLM
    try:
        # First try direct text extraction
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        # Search in first few pages where DOI is typically located
        text_to_search = ""
        for page_num in range(min(3, len(doc))):
            page = doc[page_num]
            text_to_search += page.get_text()
        doc.close()
        # Try regex extraction first
        doi = extract_doi_from_text(text_to_search)
        if doi:
            return doi
        logger.debug("DOI not found via regex, trying LLM fallback...")
        # If no DOI found via regex, try LLM as fallback
        if LLM_AVAILABLE:
            try:
                from langchain_ollama import OllamaLLM
                # Use phi4 for DOI extraction
                model_name = globals().get('_current_model', 'phi4')
                llm = OllamaLLM(model=model_name, base_url=DEFAULT_OLLAMA_URL)
                # Limit text to avoid LLM confusion
                search_text = text_to_search[:1500] if len(text_to_search) > 1500 else text_to_search
                # Simple prompt for DOI extraction
                prompt = f"""Find the DOI in this academic paper text.\n\nText from paper:\n{search_text}\n\nRespond with ONLY the DOI in format \"10.xxxx/xxxxx\" or \"NONE\" if not found.\nDOI:"""
                result = llm.invoke(prompt)
                result = result.strip()
                # Clean and validate LLM result
                result = result.replace('DOI:', '').replace('doi:', '').strip()
                if result != "NONE" and re.match(r'10\\.\\d{4,}/\\S+', result):
                    logger.info(f"📄 Found DOI via LLM: {result}")
                    return result
            except Exception as e:
                logger.debug(f"LLM DOI extraction failed: {e}")
        return None
    except Exception as e:
        logger.error(f"DOI extraction failed: {e}")
        return None

def fetch_openalex_metadata(doi: str) -> Dict[str, Any]:
    """Fetch metadata from OpenAlex API using DOI."""
    try:
        # OpenAlex API endpoint
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        
        logger.info(f"🔍 Fetching metadata from OpenAlex for DOI: {doi}")
        
        headers = {
            'User-Agent': 'EcoOpen/1.0 (mailto:your-email@example.com)'  # Be polite to API
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract relevant metadata
        metadata = {
            'doi': doi,
            'title': data.get('title', ''),
            'authors': [],
            'journal': '',
            'year': '',
            'abstract': data.get('abstract', ''),
            'open_access': data.get('open_access', {}).get('is_oa', False),
            'publication_date': data.get('publication_date', ''),
            'type': data.get('type', ''),
            'cited_by_count': data.get('cited_by_count', 0),
            'url': data.get('doi', ''),
            'openalex_id': data.get('id', '')
        }
        
        # Extract authors
        authorships = data.get('authorships', [])
        for authorship in authorships:
            author = authorship.get('author', {})
            display_name = author.get('display_name', '')
            if display_name:
                metadata['authors'].append(display_name)
        
        # Extract journal/venue information
        primary_location = data.get('primary_location', {})
        if primary_location:
            source = primary_location.get('source', {})
            if source:
                metadata['journal'] = source.get('display_name', '')
        
        # Extract year from publication date
        pub_date = data.get('publication_date', '')
        if pub_date:
            try:
                metadata['year'] = str(pub_date.split('-')[0])
            except:
                pass
        
        logger.info(f"✅ Successfully fetched OpenAlex metadata")
        logger.info(f"   Title: {metadata['title'][:80]}...")
        logger.info(f"   Authors: {len(metadata['authors'])} found")
        logger.info(f"   Journal: {metadata['journal']}")
        logger.info(f"   Year: {metadata['year']}")
        
        return metadata
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"OpenAlex API request failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"OpenAlex metadata extraction failed: {e}")
        return {}

# =============================================================================
# Enhanced Data Downloading Module
# =============================================================================

# Supported data formats categorized by type
DATA_FORMATS = {
    'tabular': ['csv', 'tsv', 'xlsx', 'xls', 'ods'],
    'text': ['txt', 'json', 'xml', 'yaml', 'yml'],
    'scientific': ['nc', 'hdf5', 'h5', 'mat', 'npz', 'fits'],
    'archives': ['zip', 'tar.gz', 'tar.bz2', 'rar', '7z'],
    'images': ['png', 'jpg', 'jpeg', 'tiff', 'gif', 'svg'],
    'code': ['py', 'r', 'ipynb', 'js', 'cpp', 'java', 'sh'],
    'documents': ['pdf', 'doc', 'docx', 'rtf', 'tex'],
    'other': ['dat', 'bin', 'log']
}

def get_file_format_category(file_extension: str) -> str:
    """Determine the category of a file based on its extension."""
    file_extension = file_extension.lower().lstrip('.')
    
    for category, extensions in DATA_FORMATS.items():
        if file_extension in extensions:
            return category
    return 'other'

def extract_data_urls_from_text(text: str, allowed_formats: List[str] = None) -> List[str]:
    """Extract potential data URLs from text with optional format filtering."""
    urls = []
    
    # Build file extension pattern based on allowed formats
    if allowed_formats:
        # Get all extensions for the allowed format categories
        allowed_extensions = []
        for format_cat in allowed_formats:
            if format_cat in DATA_FORMATS:
                allowed_extensions.extend(DATA_FORMATS[format_cat])
        
        # Create pattern for specific extensions
        ext_pattern = '|'.join(re.escape(ext) for ext in allowed_extensions)
        file_patterns = [
            f'https?://[^\\s\\]]+\\.(?:{ext_pattern})',
        ]
    else:
        # Default patterns for all file types
        file_patterns = [
            r'https?://[^\s\]]+\.(?:csv|tsv|xlsx?|xls|json|xml|zip|tar\.gz|gz|dat|txt|nc|hdf5?|h5|mat|npz|py|r|ipynb)',
        ]
    
    # Repository and data platform patterns (always included)
    repo_patterns = [
        r'https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[^\s\]]+',  # Code repositories
        r'https?://(?:www\.)?(?:zenodo\.org|figshare\.com|dryad\.org)/[^\s\]]+',  # Data repositories
        r'https?://(?:www\.)?(?:dataverse\.harvard\.edu|data\.mendeley\.com)/[^\s\]]+',  # Academic data
        r'https?://[^\s\]]*(?:dataset|data|download|repository)[^\s\]]*',  # Generic data URLs
    ]
    
    all_patterns = file_patterns + repo_patterns
    
    logger.debug(f"Searching for data URLs in text ({len(text)} chars)...")
    if allowed_formats:
        logger.debug(f"Filtering for formats: {allowed_formats}")
    
    for pattern in all_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Clean up URL
            url = match.strip('.,;:)]}>')
            if url not in urls:
                urls.append(url)
    
    if urls:
        logger.info(f"🔗 Found {len(urls)} potential data URLs")
        for url in urls[:5]:  # Log first 5 URLs
            logger.debug(f"   • {url}")
    
    return urls

def classify_url_by_content_type(url: str) -> Dict[str, Any]:
    """Classify URL by making a HEAD request to check content type."""
    try:
        head_response = requests.head(url, timeout=10, allow_redirects=True)
        content_type = head_response.headers.get('content-type', '').lower()
        content_length = head_response.headers.get('content-length')
        
        # Extract file extension from URL
        parsed_url = urlparse(url)
        file_ext = Path(parsed_url.path).suffix.lower().lstrip('.')
        
        classification = {
            'url': url,
            'content_type': content_type,
            'file_extension': file_ext,
            'format_category': get_file_format_category(file_ext),
            'size_bytes': int(content_length) if content_length else None,
            'accessible': head_response.status_code == 200
        }
        
        return classification
        
    except Exception as e:
        logger.debug(f"Could not classify URL {url}: {e}")
        return {
            'url': url,
            'content_type': 'unknown',
            'file_extension': '',
            'format_category': 'other',
            'size_bytes': None,
            'accessible': False
        }

def download_data_file(url: str, download_dir: str, max_size_mb: int = 100, 
                      allowed_formats: List[str] = None) -> Dict[str, Any]:
    """Download a data file from URL with size limit and format filtering."""
    try:
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📥 Attempting to download: {url}")
        
        # Classify URL first if format filtering is enabled
        if allowed_formats:
            classification = classify_url_by_content_type(url)
            if classification['format_category'] not in allowed_formats:
                logger.info(f"   Skipping {url}: format '{classification['format_category']}' not in allowed formats")
                return {'success': False, 'error': f"Format '{classification['format_category']}' not allowed"}
        
        # Head request to check file size
        try:
            head_response = requests.head(url, timeout=10, allow_redirects=True)
            content_length = head_response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > max_size_mb:
                    logger.warning(f"   File too large: {size_mb:.1f}MB (limit: {max_size_mb}MB)")
                    return {'success': False, 'error': f'File too large: {size_mb:.1f}MB'}
        except:
            logger.debug("Could not check file size via HEAD request")
        
        # Download the file
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        
        # Determine filename
        filename = None
        if 'content-disposition' in response.headers:
            import re
            cd = response.headers['content-disposition']
            match = re.search(r'filename="?([^"]+)"?', cd)
            if match:
                filename = match.group(1)
        
        if not filename:
            filename = Path(urlparse(url).path).name
            if not filename or '.' not in filename:
                filename = f"data_file_{int(time.time())}"
        
        file_path = download_path / filename
        
        # Download with progress tracking
        total_size = 0
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
                    
                    # Check size limit during download
                    if total_size > max_size_mb * 1024 * 1024:
                        f.close()
                        file_path.unlink()  # Delete partial file
                        logger.warning(f"   Download stopped: size exceeded {max_size_mb}MB")
                        return {'success': False, 'error': f'Download exceeded size limit'}
        
        size_mb = total_size / (1024 * 1024)
        file_ext = Path(filename).suffix.lower().lstrip('.')
        format_category = get_file_format_category(file_ext)
        
        logger.info(f"✅ Successfully downloaded: {filename} ({size_mb:.2f}MB, {format_category})")
        
        return {
            'success': True,
            'file_path': str(file_path),
            'filename': filename,
            'size_bytes': total_size,
            'size_mb': size_mb,
            'url': url,
            'format_category': format_category,
            'file_extension': file_ext
        }
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"   Download failed: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f"   Download error: {e}")
        return {'success': False, 'error': str(e)}

def download_paper_data(data_urls: List[str], download_dir: str, max_files: int = 5, 
                       allowed_formats: List[str] = None, max_size_mb: int = 100) -> List[Dict[str, Any]]:
    """Download data files from a list of URLs with format filtering."""
    if not data_urls:
        return []
    
    logger.info(f"📦 Starting data download for {len(data_urls)} URLs...")
    if allowed_formats:
        logger.info(f"🎯 Filtering for formats: {', '.join(allowed_formats)}")
    
    download_results = []
    downloaded_count = 0
    
    for url in data_urls:
        if downloaded_count >= max_files:
            logger.info(f"   Reached maximum download limit ({max_files} files)")
            break
        
        result = download_data_file(url, download_dir, max_size_mb, allowed_formats)
        download_results.append(result)
        
        if result['success']:
            downloaded_count += 1
    
    success_count = sum(1 for r in download_results if r['success'])
    
    # Summarize by format
    format_summary = {}
    for result in download_results:
        if result['success']:
            fmt = result.get('format_category', 'unknown')
            format_summary[fmt] = format_summary.get(fmt, 0) + 1
    
    logger.info(f"📊 Download summary: {success_count}/{len(data_urls)} files downloaded successfully")
    if format_summary:
        logger.info(f"📁 Formats downloaded: {', '.join([f'{fmt}({count})' for fmt, count in format_summary.items()])}")
    
    return download_results


# =============================================================================
# PDF Folder Processing Functions
# =============================================================================

def find_pdf_files(folder_path: str, recursive: bool = False) -> List[str]:
    """Find all PDF files in a folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    
    if recursive:
        pdf_files = list(folder.rglob("*.pdf"))
    else:
        pdf_files = list(folder.glob("*.pdf"))
    
    pdf_paths = [str(pdf) for pdf in pdf_files]
    logger.info(f"📁 Found {len(pdf_paths)} PDF files in {folder_path}")
    
    if recursive:
        logger.info("   (searched recursively in subfolders)")
    
    return pdf_paths

def process_pdf_folder_to_csv(folder_path: str, output_file: str = "ecoopen_output.csv",
                             recursive: bool = False, download_data: bool = False, 
                             data_dir: str = "./data_downloads", max_data_files: int = 5,
                             allowed_formats: List[str] = None, max_size_mb: int = 100) -> pd.DataFrame:
    """Process all PDFs in a folder and save results to CSV."""
    
    # Find all PDF files
    pdf_files = find_pdf_files(folder_path, recursive)
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {folder_path}")
        return pd.DataFrame()
    
    logger.info(f"Starting batch processing of {len(pdf_files)} PDF files...")
    logger.info(f"Output file: {output_file}")
    if download_data:
        logger.info(f"Data files will be downloaded to: {data_dir}")
        logger.info(f"Max data files per paper: {max_data_files}")
        if allowed_formats:
            logger.info(f"Filtering for formats: {', '.join(allowed_formats)}")
        logger.info(f"Max file size: {max_size_mb}MB")
    
    results = []
    successful = 0
    failed = 0
    
    for i, pdf_path in enumerate(tqdm(pdf_files, desc="Processing PDFs"), 1):
        logger.info(f"\n--- Processing PDF {i}/{len(pdf_files)}: {Path(pdf_path).name} ---")
        try:
            result = process_single_pdf_file(
                pdf_path,
                download_data=download_data,
                data_dir=data_dir,
                max_data_files=max_data_files,
                allowed_formats=allowed_formats,
                max_size_mb=max_size_mb
            )
            result['identifier'] = f"{i:03d}"
            result['path'] = pdf_path
            results.append(result)
            
            successful += 1
            logger.info(f"✓ Successfully processed {Path(pdf_path).name}")
                
        except Exception as e:
            failed += 1
            logger.error(f"✗ Failed to process {Path(pdf_path).name}: {e}")
            # Add empty result to maintain order
            empty_result = {col: '' for col in CSV_COLUMNS}
            empty_result['identifier'] = f"{i:03d}"
            empty_result['path'] = pdf_path
            results.append(empty_result)
    
    # Convert to DataFrame and save CSV
    logger.info(f"\nSaving results to {output_file}...")
    df = pd.DataFrame(results, columns=CSV_COLUMNS)
    df.to_csv(output_file, sep=';', index=False)
    
    logger.info(f"✓ Batch processing complete!")
    logger.info(f"  - Total PDFs: {len(pdf_files)}")
    logger.info(f"  - Successful: {successful}")
    logger.info(f"  - Failed: {failed}")
    logger.info(f"  - Results saved to: {output_file}")
    
    return df

def process_single_pdf_file(pdf_path: str, download_data: bool = False, 
                           data_dir: str = "./data_downloads", max_data_files: int = 5,
                           allowed_formats: List[str] = None, max_size_mb: int = 100) -> Dict[str, Any]:
    """Process a single PDF file with DOI extraction and OpenAlex integration."""
    if not LLM_AVAILABLE:
        raise ImportError("LLM dependencies required for PDF processing")
    
    logger.info(f"📄 Processing: {Path(pdf_path).name}")
    
    # Read PDF content
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
    
    # Initialize result structure
    result = {
        'identifier': '001',
        'doi': '',
        'title': '',
        'authors': '',
        'published': '',
        'url': '',
        'journal': '',
        'has_fulltext': True,
        'is_oa': False,
        'path': pdf_path,
        'pdf_content_length': len(pdf_content),
        'data_links': [],
        'data_availability_statements': '',
        'code_availability_statements': '',
        'format': '',
        'repository': '',
        'repository_url': '',
        'data_download_path': '',
        'data_size': 0,
        'number_of_files': 0,
        'license': ''
    }
    
    # Step 1: Extract DOI from PDF
    doi = extract_doi_from_pdf(pdf_content)
    result['doi'] = doi if doi else ''
    
    # Step 2: Get metadata from OpenAlex if DOI found
    if doi:
        logger.info(f"📄 Found DOI: {doi}")
        openalex_metadata = fetch_openalex_metadata(doi)
        if openalex_metadata:
            logger.info("✅ Successfully retrieved metadata from OpenAlex")
            result.update({
                'title': openalex_metadata.get('title', ''),
                'authors': '; '.join(openalex_metadata.get('authors', [])),
                'published': openalex_metadata.get('year', ''),
                'url': openalex_metadata.get('url', ''),
                'journal': openalex_metadata.get('journal', ''),
                'is_oa': openalex_metadata.get('open_access', False)
            })
        else:
            logger.warning("⚠️  OpenAlex metadata retrieval failed")
    else:
        logger.info("❌ No DOI found in PDF")
    
    # Step 3: Extract data/code availability using LLM
    try:
        logger.info("🤖 Starting LLM extraction...")
        model_name = globals().get('_current_model', 'phi4')
        extractor = LLMExtractor(llm_model=model_name)
        extraction = extractor.extract_from_pdf(pdf_content, allowed_formats)
        
        if extraction['success']:
            logger.info("✅ LLM extraction successful")
            avail = extraction['availability']
            
            # Collect all data links
            all_data_links = []
            
            # From availability analysis
            if avail.get('data_links'):
                all_data_links.extend(avail['data_links'])
            
            # From direct URL extraction
            if extraction.get('data_urls'):
                all_data_links.extend(extraction['data_urls'])
            
            # Remove duplicates
            seen = set()
            unique_data_links = []
            for link in all_data_links:
                if link not in seen:
                    seen.add(link)
                    unique_data_links.append(link)
            
            result['data_links'] = unique_data_links
            
            # Extract statements and clean them
            data_statements = avail.get('data_availability', {}).get('statements', [])
            code_statements = avail.get('code_availability', {}).get('statements', [])
            
            # Clean statements (remove JSON artifacts and limit length)
            def clean_statement(stmt):
                if isinstance(stmt, str):
                    # Remove JSON artifacts
                    stmt = re.sub(r'[{}"\\]', '', stmt)
                    # Limit length to prevent corruption
                    if len(stmt) > 500:
                        stmt = stmt[:500] + "..."
                    return stmt.strip()
                return ""
            
            cleaned_data_statements = [clean_statement(stmt) for stmt in data_statements if clean_statement(stmt)]
            cleaned_code_statements = [clean_statement(stmt) for stmt in code_statements if clean_statement(stmt)]
            
            result['data_availability_statements'] = '; '.join(cleaned_data_statements) if cleaned_data_statements else ''
            result['code_availability_statements'] = '; '.join(cleaned_code_statements) if cleaned_code_statements else ''
            
            # Extract repository info
            data_repos = avail.get('data_availability', {}).get('repositories', [])
            if data_repos:
                result['repository'] = data_repos[0]
            
            data_urls = avail.get('data_availability', {}).get('urls', [])
            if data_urls:
                result['repository_url'] = data_urls[0]
            
            # If no OpenAlex metadata, try LLM fallback for title
            if not result['title'] and extraction.get('metadata', {}).get('title'):
                result['title'] = extraction['metadata']['title']
                logger.info(f"📖 Using LLM-extracted title: {result['title'][:80]}...")
            
            logger.info(f"📊 Found {len(data_statements)} data statements, {len(code_statements)} code statements")
            logger.info(f"🔗 Found {len(unique_data_links)} unique data URLs")
            
            # Step 4: Download data files if requested
            if download_data and unique_data_links:
                logger.info(f"📦 Starting data download for {len(unique_data_links)} URLs...")
                download_results = download_paper_data(
                    unique_data_links, 
                    data_dir,
                    max_data_files,
                    allowed_formats,
                    max_size_mb
                )
                
                # Update result with download info
                successful_downloads = [r for r in download_results if r['success']]
                if successful_downloads:
                    result['data_download_path'] = data_dir
                    result['number_of_files'] = len(successful_downloads)
                    total_size = sum(r.get('size_bytes', 0) for r in successful_downloads)
                    result['data_size'] = total_size
                    logger.info(f"📊 Successfully downloaded {len(successful_downloads)} files ({total_size / 1024 / 1024:.2f} MB)")
        
        else:
            logger.warning("⚠️  LLM extraction failed")
        
    except Exception as e:
        logger.warning(f"LLM extraction failed for {Path(pdf_path).name}: {e}")
    
    return result


# =============================================================================
# Module-level Variables for CLI Support
# =============================================================================

# Global variable to store current model choice
_current_model = None

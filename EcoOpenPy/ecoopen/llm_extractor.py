"""
LLM-based data availability extraction for EcoOpen
Uses Ollama + LangChain + ChromaDB for intelligent document analysis
"""

import os
import tempfile
import logging
from typing import Dict, List, Optional, Any
import chromadb
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.embeddings.base import Embeddings
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SafeOllamaEmbeddings(Embeddings):
    """Safe wrapper for Ollama embeddings to handle string conversion."""
    
    def __init__(self, base_embeddings):
        self.base_embeddings = base_embeddings

    def embed_documents(self, texts):
        clean_texts = [str(t) if not isinstance(t, str) else t for t in texts]
        return self.base_embeddings.embed_documents(clean_texts)

    def embed_query(self, text):
        return self.base_embeddings.embed_query(str(text))

class LLMDataExtractor:
    """LLM-based data availability and accessibility information extractor."""
    
    def __init__(self, 
                 llm_model: str = "phi4",
                 embedding_model: str = "nomic-embed-text",
                 ollama_base_url: str = "http://localhost:11434",
                 chroma_path: str = "./chroma_db_ecoopen"):
        """
        Initialize the LLM-based extractor.
        
        Args:
            llm_model: Ollama LLM model name
            embedding_model: Ollama embedding model name
            ollama_base_url: Ollama server URL
            chroma_path: ChromaDB persistence path
        """
        self.llm = OllamaLLM(model=llm_model, base_url=ollama_base_url)
        self.embeddings = SafeOllamaEmbeddings(
            OllamaEmbeddings(model=embedding_model, base_url=ollama_base_url)
        )
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self.collection_name = "ecoopen_documents"
        
        logger.info(f"Initialized LLM extractor with {llm_model} and {embedding_model}")

    def process_pdf_to_vectorstore(self, pdf_content: bytes) -> Chroma:
        """Process PDF content and create vector store."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_content)
            tmp_file_path = tmp_file.name

        try:
            loader = PyPDFLoader(tmp_file_path)
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, 
                chunk_overlap=200,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            splits = text_splitter.split_documents(documents)

            # Filter and clean text chunks
            texts = []
            metadatas = []
            for i, doc in enumerate(splits):
                if isinstance(doc.page_content, str) and doc.page_content.strip():
                    texts.append(str(doc.page_content))
                    metadata = doc.metadata.copy()
                    metadata['chunk_id'] = i
                    metadatas.append(metadata)

            if not texts:
                raise ValueError("No valid text chunks found in the PDF.")

            # Create vector store
            vectorstore = Chroma.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas,
                client=self.chroma_client,
                collection_name=f"{self.collection_name}_{hash(str(texts[:3]))}"
            )

            logger.info(f"Created vector store with {len(texts)} chunks")
            return vectorstore

        finally:
            os.unlink(tmp_file_path)

    def extract_data_availability(self, vectorstore: Chroma) -> Dict[str, Any]:
        """Extract data availability information using LLM reasoning."""
        
        # Search for relevant chunks about data availability
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        
        # Prompt for data availability detection
        availability_prompt = PromptTemplate(
            input_variables=["context"],
            template="""
You are an expert at analyzing scientific papers for data and code availability information.

Based on the following text chunks from a scientific paper, identify and extract:

1. DATA AVAILABILITY: Any statements about where data can be accessed, shared, or obtained
2. CODE AVAILABILITY: Any statements about where code, scripts, or software can be accessed
3. SUPPLEMENTARY MATERIALS: Any mentions of supplementary files, appendices, or additional materials
4. REPOSITORIES: Any mentions of data repositories, databases, or archives (like Zenodo, Dryad, GitHub, etc.)
5. ACCESS CONDITIONS: Any conditions, restrictions, or requirements for accessing data/code
6. CONTACT INFORMATION: Any contact details for data/code requests

For each category found, provide:
- The exact text/statement
- A confidence level (high/medium/low)
- The type of availability (open/restricted/upon request/not available)

Context from paper:
{context}

Respond in JSON format:
{{
  "data_availability": {{
    "found": true/false,
    "statements": ["exact text 1", "exact text 2"],
    "confidence": "high/medium/low",
    "access_type": "open/restricted/upon_request/not_available",
    "repositories": ["repository names"],
    "urls": ["any URLs found"]
  }},
  "code_availability": {{
    "found": true/false,
    "statements": ["exact text"],
    "confidence": "high/medium/low", 
    "access_type": "open/restricted/upon_request/not_available",
    "repositories": ["repository names"],
    "urls": ["any URLs found"]
  }},
  "supplementary_materials": {{
    "found": true/false,
    "statements": ["exact text"],
    "types": ["type of materials"]
  }},
  "contact_info": {{
    "found": true/false,
    "emails": ["email addresses"],
    "statements": ["contact statements"]
  }},
  "overall_assessment": {{
    "data_openly_available": true/false,
    "code_openly_available": true/false,
    "confidence": "high/medium/low",
    "summary": "brief summary of availability"
  }}
}}
"""
        )
        
        # Create chain for availability detection
        availability_chain = {
            "context": retriever | (lambda docs: "\n\n".join([f"Chunk {i+1}:\n{doc.page_content}" for i, doc in enumerate(docs)]))
        } | availability_prompt | self.llm | StrOutputParser()
        
        try:
            result = availability_chain.invoke({})
            logger.info("LLM extraction completed")
            
            # Try to parse JSON response
            try:
                parsed_result = json.loads(result)
                return parsed_result
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON, returning raw text")
                return {
                    "raw_response": result,
                    "parsing_error": True,
                    "overall_assessment": {
                        "confidence": "low",
                        "summary": "Failed to parse LLM response"
                    }
                }
                
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {
                "error": str(e),
                "overall_assessment": {
                    "data_openly_available": False,
                    "code_openly_available": False,
                    "confidence": "low",
                    "summary": "Extraction failed"
                }
            }

    def extract_additional_metadata(self, vectorstore: Chroma) -> Dict[str, Any]:
        """Extract additional paper metadata using LLM."""
        
        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
        
        metadata_prompt = PromptTemplate(
            input_variables=["context"],
            template="""
Based on the following text from a scientific paper, extract:

1. Paper title
2. Authors
3. Journal/publication venue
4. Publication year
5. DOI
6. Research field/domain
7. Study type (experimental, observational, review, etc.)

Context:
{context}

Respond in JSON format:
{{
  "title": "paper title",
  "authors": ["author names"],
  "journal": "journal name",
  "year": "year",
  "doi": "DOI if found",
  "research_field": "field/domain",
  "study_type": "type of study"
}}
"""
        )
        
        metadata_chain = {
            "context": retriever | (lambda docs: "\n\n".join([doc.page_content for doc in docs]))
        } | metadata_prompt | self.llm | StrOutputParser()
        
        try:
            result = metadata_chain.invoke({})
            return json.loads(result)
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            return {"error": str(e)}

    def extract_all_information(self, pdf_content: bytes) -> Dict[str, Any]:
        """
        Complete extraction pipeline: process PDF and extract all information.
        
        Args:
            pdf_content: PDF file content as bytes
            
        Returns:
            Dictionary with extracted information
        """
        try:
            # Process PDF to vector store
            vectorstore = self.process_pdf_to_vectorstore(pdf_content)
            
            # Extract data availability
            availability_info = self.extract_data_availability(vectorstore)
            
            # Extract metadata
            metadata_info = self.extract_additional_metadata(vectorstore)
            
            # Combine results
            result = {
                "extraction_method": "LLM",
                "model_info": {
                    "llm_model": self.llm.model,
                    "embedding_model": "nomic-embed-text"
                },
                "availability_info": availability_info,
                "metadata_info": metadata_info,
                "success": True
            }
            
            logger.info("Complete extraction finished successfully")
            return result
            
        except Exception as e:
            logger.error(f"Complete extraction failed: {e}")
            return {
                "extraction_method": "LLM",
                "error": str(e),
                "success": False
            }

# Convenience function for backward compatibility
def extract_text_from_pdf_llm(pdf_content: bytes) -> str:
    """Extract text from PDF using LangChain (for compatibility)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_content)
        tmp_file_path = tmp_file.name
    
    try:
        loader = PyPDFLoader(tmp_file_path)
        documents = loader.load()
        return "\n\n".join([doc.page_content for doc in documents])
    finally:
        os.unlink(tmp_file_path)

def extract_all_information_llm(pdf_content: bytes) -> Dict[str, Any]:
    """
    Main function for LLM-based extraction (for easy integration).
    
    Args:
        pdf_content: PDF file content as bytes
        
    Returns:
        Dictionary with extracted information
    """
    extractor = LLMDataExtractor()
    return extractor.extract_all_information(pdf_content)

# For testing
if __name__ == "__main__":
    # Test with a sample PDF
    extractor = LLMDataExtractor()
    
    # You can test with a PDF file like this:
    # with open("test.pdf", "rb") as f:
    #     result = extractor.extract_all_information(f.read())
    #     print(json.dumps(result, indent=2))
    
    print("LLM extractor initialized successfully!")

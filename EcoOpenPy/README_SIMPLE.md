# EcoOpen - LLM-based Data Availability Extraction

A streamlined, modern Python package for extracting data and code availability information from scientific PDFs using Large Language Models.

## Key Features

- **LLM-powered extraction** using Ollama (phi4 model) for intelligent analysis
- **No keyword matching** - understands context and meaning
- **Clean CSV output** with standardized columns matching your requirements
- **Simple, focused codebase** - easy to understand and modify
- **Metadata integration** via OpenAlex API
- **Batch processing** for multiple DOIs

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements_simple.txt
```

### 2. Set up Ollama

```bash
# Install Ollama (one-time setup)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required models
ollama pull phi4
ollama pull nomic-embed-text
```

### 3. Test Installation

```bash
python test_simple.py
```

### 4. Basic Usage

#### Command Line

```bash
# Process DOIs from command line
python ecoopen.py --dois "10.1111/2041-210X.12952" "10.5194/bg-15-3521-2018"

# Process DOIs from file
echo "10.1111/2041-210X.12952" > dois.txt
echo "10.5194/bg-15-3521-2018" >> dois.txt
python ecoopen.py --dois-file dois.txt

# Process single PDF file
python ecoopen.py --pdf paper.pdf

# Save PDFs while processing
python ecoopen.py --dois "10.1111/2041-210X.12952" --save-pdfs --pdf-dir ./downloads
```

#### Python API

```python
from ecoopen import process_dois_to_csv, process_single_doi

# Process multiple DOIs to CSV
dois = ["10.1111/2041-210X.12952", "10.5194/bg-15-3521-2018"]
df = process_dois_to_csv(dois, "results.csv")

# Process single DOI
result = process_single_doi("10.1111/2041-210X.12952")
print(result['data_availability_statements'])
```

## CSV Output Format

The package generates a CSV file with these exact columns (semicolon-separated):

```
identifier;doi;title;authors;published;url;journal;has_fulltext;is_oa;path;pdf_content_length;data_links;data_availability_statements;code_availability_statements;format;repository;repository_url;data_download_path;data_size;number_of_files;license
```

### Column Descriptions

- `identifier`: Sequential ID (001, 002, ...)
- `doi`: Digital Object Identifier
- `title`: Paper title
- `authors`: Author list (semicolon-separated)
- `published`: Publication date
- `url`: Paper landing page URL
- `journal`: Journal name
- `has_fulltext`: Boolean - PDF available
- `is_oa`: Boolean - Open access
- `path`: Local PDF file path (if saved)
- `pdf_content_length`: PDF size in bytes
- `data_links`: URLs to data repositories/files
- `data_availability_statements`: Extracted data availability text
- `code_availability_statements`: Extracted code availability text
- `format`: Data format information
- `repository`: Primary repository name
- `repository_url`: Repository URL
- `data_download_path`: Local data download path
- `data_size`: Downloaded data size
- `number_of_files`: Number of data files
- `license`: Data license information

## How It Works

1. **Metadata Retrieval**: Gets paper info from OpenAlex API
2. **PDF Download**: Downloads open-access PDFs when available
3. **Text Processing**: Converts PDF to searchable chunks using LangChain
4. **Vector Storage**: Creates embeddings using ChromaDB for context-aware search
5. **LLM Analysis**: Uses phi4 model to intelligently extract data/code availability
6. **Structured Output**: Formats results into standardized CSV

## LLM Advantages

Unlike keyword-based approaches, the LLM extractor:

- **Understands context** - distinguishes between mentioning data and actually sharing data
- **Handles variations** - recognizes different ways of expressing availability
- **Extracts relationships** - links statements to repositories and URLs
- **Provides confidence** - includes reasoning about availability type
- **Adapts to new patterns** - works with evolving data sharing practices

## Configuration

Key settings in `ecoopen.py`:

```python
DEFAULT_LLM_MODEL = "phi4"           # Ollama model for analysis
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"  # Embedding model
DEFAULT_OLLAMA_URL = "http://localhost:11434"  # Ollama server
```

## Troubleshooting

### LLM Not Available
```bash
# Check if Ollama is running
python ecoopen.py --check-llm

# Start Ollama if needed
ollama serve
```

### PDF Download Issues
- Some papers may not have open-access PDFs
- Check paper URLs manually if needed
- The extractor will process available PDFs and note missing ones

### Memory Issues
- Large batch processing may require more RAM
- Process in smaller batches if needed
- ChromaDB is temporary and cleaned up automatically

## Dependencies

Core dependencies:
- `pandas` - Data handling
- `requests` - HTTP requests
- `PyMuPDF` - PDF processing
- `tqdm` - Progress bars

LLM dependencies:
- `langchain` - LLM framework
- `langchain-ollama` - Ollama integration
- `chromadb` - Vector database
- `pypdf` - PDF loading

## Compared to Original EcoOpen

This simplified version:

- ✅ **Focused on LLM extraction** (removed keyword matching)
- ✅ **Cleaner, simpler codebase** (easier to understand/modify)
- ✅ **Exact CSV format match** (your specified columns)
- ✅ **Modern dependencies** (latest LangChain, etc.)
- ✅ **Better error handling** (graceful fallbacks)
- ✅ **Streamlined workflow** (fewer moving parts)

Removed features:
- ❌ Keyword-based extraction (replaced by LLM)
- ❌ Complex data downloading (focused on availability detection)
- ❌ Legacy spaCy components (using LLM tokenization)

## License

MIT License - feel free to modify and extend as needed.

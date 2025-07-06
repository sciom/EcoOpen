# EcoOpen - LLM-based Data Availability Extraction

A streamlined Python package for extracting data and code availability information from scientific PDFs using Large Language Models (Ollama + LangChain + ChromaDB).

**🎯 Optimized for Microsoft Phi Models**: Uses phi4 by default with automatic fallback to phi3:mini for lower VRAM systems.

## 🚀 Features

- **Batch PDF Processing**: Process entire folders of PDFs automatically
- **DOI Extraction**: Automatically extract DOIs from each PDF using regex and LLM fallback
- **OpenAlex Integration**: Fetch comprehensive metadata (title, authors, journal, year) for each DOI
- **LLM-based Extraction**: Intelligent extraction of data/code availability statements (no keyword matching)
- **Data URL Discovery**: Find and extract data repository URLs from papers
- **Format-Specific Downloads**: Choose which data formats to download (tabular, scientific, code, etc.)
- **Smart File Filtering**: Automatically classify and filter files by type and size
- **Clean CSV Output**: Standardized output with 21 columns of metadata
- **Robust Error Handling**: Continues processing even when individual PDFs fail
- **Progress Tracking**: Real-time progress bars and detailed logging

## 📋 Requirements

- Python 3.8+
- Ollama (for LLM processing)
- **Phi models only**: phi4 (preferred) or phi3:mini (fallback)
- At least 4GB RAM (8GB+ recommended)
- GPU with 4GB+ VRAM for phi3:mini, 8GB+ for phi4

## 🛠️ Installation

### Option 1: Install from Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/ecoopen.git
cd ecoopen/EcoOpenPy

# Install the package in development mode
pip install -e .

# Or install normally
pip install .
```

### Option 2: Install from PyPI (when available)

```bash
pip install ecoopen
```

### Option 3: Manual Installation

```bash
# Download the code
# Navigate to the EcoOpenPy directory

# Install dependencies
pip install -r requirements.txt

# Install the package
python setup.py install
```

### 2. Install Ollama

#### Linux/macOS

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Windows

Download and install from [ollama.ai](https://ollama.ai/)

### 3. Install LLM Model

```bash
# Install phi4 (preferred, requires 8GB+ VRAM)
ollama pull phi4

# OR install phi3:mini (fallback, works with 4GB+ VRAM)
ollama pull phi3:mini

# Start Ollama service
ollama serve
```

### 4. Verify Installation

```bash
# Check if LLM is available
python ecoopen.py --check-llm

# Check performance
python ecoopen.py --check-performance
```

## 🖥️ Streamlit GUI

For a user-friendly web interface, use the Streamlit GUI (optimized for phi models):

```bash
# Install GUI dependencies
cd EcoOpenGUI
pip install -r requirements.txt

# Launch the GUI
./run_gui.sh
# Or manually: streamlit run main.py
```

Open your browser to `http://localhost:8501` to access the GUI features:

- **📁 Batch Processing**: Upload multiple PDFs for batch processing
- **📄 Single File**: Process individual PDF files  
- **🤖 Phi Model Selection**: Choose between phi4 and phi3:mini or use auto-detect
- **🎯 Format Selection**: Choose specific data formats to download
- **📊 Progress Tracking**: Real-time processing progress
- **💾 Result Downloads**: Download CSV, JSON, and data file archives
- **🔧 System Status**: Monitor Ollama and GPU status
- **⚙️ Easy Configuration**: Visual controls for all processing options

## 📖 Usage

### Command Line Interface

After installation, you can use the `ecoopen` command:

```bash
# Process a single PDF
ecoopen --pdf path/to/paper.pdf

# Process a folder of PDFs
ecoopen --pdf-folder path/to/pdf/folder --output results.csv

# Process with data download
ecoopen --pdf-folder path/to/pdfs --download-data --data-dir ./downloads

# Check system compatibility
ecoopen --check-llm
ecoopen --check-performance
ecoopen --list-models
```

### Python API

You can also use EcoOpen programmatically:

```python
import ecoopen

# Process a single PDF
result = ecoopen.process_single_pdf_file("paper.pdf")

# Process a folder of PDFs
df = ecoopen.process_pdf_folder_to_csv("pdf_folder/", "results.csv")

# Use the LLM extractor directly
extractor = ecoopen.LLMExtractor()
with open("paper.pdf", "rb") as f:
    pdf_content = f.read()
    result = extractor.extract_from_pdf(pdf_content)
```

### Legacy Usage (Direct Script)

You can still run the script directly if not installed as a package:

```bash
# Process a single PDF
python ecoopen/core.py --pdf path/to/paper.pdf

# Process a folder of PDFs
python ecoopen/core.py --pdf-folder path/to/pdf/folder --output results.csv
```

### Basic PDF Folder Processing

```bash
# Process all PDFs in a folder
ecoopen --pdf-folder /path/to/pdfs --output results.csv

# Process with recursive search in subfolders
ecoopen --pdf-folder /path/to/pdfs --output results.csv --recursive

# Enable debug logging to see detailed processing
ecoopen --pdf-folder /path/to/pdfs --output results.csv --debug
```

### Single PDF Processing

```bash
# Process a single PDF file
ecoopen --pdf /path/to/paper.pdf --output single_result.csv
```

### Advanced Options

```bash
# Download data files found in papers
ecoopen --pdf-folder /path/to/pdfs --output results.csv --download-data --data-dir ./downloads

# Download only specific data formats (NEW!)
ecoopen --pdf-folder /path/to/pdfs --output results.csv --download-data --formats tabular scientific

# Use a specific phi model
ecoopen --pdf-folder /path/to/pdfs --output results.csv --model phi4

# Limit data file downloads
ecoopen --pdf-folder /path/to/pdfs --output results.csv --download-data --max-data-files 3 --max-file-size 50
```

### Model Management

```bash
# List recommended models for your hardware
python ecoopen.py --list-models

# Check current model performance
python ecoopen.py --check-performance
```

## 📊 Output Format

The script generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `identifier` | Sequential ID (001, 002, ...) |
| `doi` | Digital Object Identifier |
| `title` | Paper title from OpenAlex/LLM |
| `authors` | Semicolon-separated author list |
| `published` | Publication year |
| `url` | DOI URL |
| `journal` | Journal name |
| `has_fulltext` | Whether PDF was processed |
| `is_oa` | Open access status |
| `path` | Path to PDF file |
| `pdf_content_length` | PDF file size in bytes |
| `data_links` | Array of data URLs found |
| `data_availability_statements` | Extracted data availability text |
| `code_availability_statements` | Extracted code availability text |
| `format` | Data format information |
| `repository` | Repository name |
| `repository_url` | Repository URL |
| `data_download_path` | Downloaded data location |
| `data_size` | Total downloaded data size |
| `number_of_files` | Number of downloaded files |
| `license` | License information |

## 🎯 Example Output

```csv
identifier;doi;title;authors;published;journal;data_availability_statements
001;10.1007/s00606-007-0516-3;A phylogenetic study of Echidnopsis...;"Mike Thiv; Ulrich Meve";2007;Plant Systematics and Evolution;"Data available upon request."
002;10.5194/bg-15-5377-2018;Integrated management of a Swiss cropland...;"Carmen Emmel; Annina Winkler; ...";2018;Biogeosciences;"Data available under https://doi.org/10.3929/ethz-b-000260058; Also, NEE uncertainty calculations..."
```

## ⚙️ Configuration

### Recommended Models by Hardware

**Note: EcoOpen now exclusively uses phi models for optimal compatibility and performance.**

| GPU Memory | Recommended Model | Size | Speed | Quality |
|------------|------------------|------|-------|---------|
| 4-8GB | `phi3:mini` | 3.8GB | Fast | Very Good |
| 8GB+ | `phi4` | 10GB | Moderate | Excellent |

**Auto-detection**: Use `--model auto-detect` (default) to automatically select the best phi model for your hardware.

### Performance Tips

1. **Use SSD storage** for better PDF loading speed
2. **Ensure sufficient RAM** (8GB+ recommended for large PDFs)
3. **Use GPU acceleration** when available
4. **Process in batches** for very large collections (100+ PDFs)

## 🐛 Troubleshooting

### Common Issues

#### LLM dependencies not available

```bash
pip install langchain langchain-ollama langchain-community langchain-chroma chromadb pypdf
```

#### Failed to connect to Ollama

```bash
# Start Ollama service
ollama serve

# Check if model is installed
ollama list
```

#### PDF parsing failed

- Some PDFs may be corrupted or have unusual formats
- The script will continue processing other PDFs
- Check the debug logs for specific error details

#### Slow processing

```bash
# Check model performance
python ecoopen.py --check-performance

# Try the faster phi model
python ecoopen.py --pdf-folder /path/to/pdfs --model phi3:mini
```

### Debug Mode

Enable detailed logging to diagnose issues:

```bash
python ecoopen.py --pdf-folder /path/to/pdfs --output results.csv --debug
```

## 📈 Performance Benchmarks

- **Average processing time**: 10-15 seconds per PDF
- **Memory usage**: 2-4GB RAM for typical documents
- **Throughput**: ~240 PDFs per hour (with phi3:mini on GPU)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with sample PDFs
5. Submit a pull request

## 📄 License

MIT License - see LICENSE.txt for details

## 👨‍💻 Author

Domagoj K. Hackenberger

## 🙏 Acknowledgments

- OpenAlex API for metadata
- Ollama for local LLM inference
- LangChain for document processing
- ChromaDB for vector storage

---

**Need help?** Open an issue or check the troubleshooting section above.

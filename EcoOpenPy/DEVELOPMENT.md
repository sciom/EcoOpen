# Development Setup

This guide explains how to set up EcoOpen for development.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Git

## Development Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ecoopen.git
   cd ecoopen/EcoOpenPy
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode:**
   ```bash
   pip install -e .
   ```

4. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

## Project Structure

```
EcoOpenPy/
├── ecoopen/                 # Main package directory
│   ├── __init__.py         # Package initialization
│   ├── core.py             # Core functionality
│   └── cli.py              # Command line interface
├── tests/                  # Test files
├── setup.py               # Package setup (legacy)
├── pyproject.toml         # Modern package configuration
├── requirements.txt       # Dependencies
├── README.md             # Documentation
├── LICENSE               # License file
├── MANIFEST.in           # Package manifest
└── CHANGELOG.md          # Version history
```

## Development Workflow

1. **Make changes** to the code in the `ecoopen/` directory
2. **Test your changes** using the command line:
   ```bash
   ecoopen --help
   ecoopen --check-llm
   ```
3. **Test with PDFs:**
   ```bash
   ecoopen --pdf path/to/test.pdf
   ```

## Building the Package

To build the package for distribution:

```bash
pip install build
python -m build
```

This creates distribution files in the `dist/` directory.

## Installing from Local Build

To install from a local build:

```bash
pip install dist/ecoopen-1.0.0-py3-none-any.whl
```

## Code Formatting

We recommend using black for code formatting:

```bash
pip install black
black ecoopen/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Common Development Tasks

### Update version number:
Edit `pyproject.toml` and update the version field.

### Add new dependencies:
Add to `pyproject.toml` under `dependencies` section.

### Run tests:
```bash
python -m pytest tests/
```

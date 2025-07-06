#!/usr/bin/env python3
"""
Setup script for EcoOpen package.
"""

from setuptools import setup, find_packages
import os

# Read README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="ecoopen",
    version="1.0.0",
    author="Domagoj K. Hackenberger",
    author_email="domagoj.hackenberger@example.com",
    description="LLM-based Data Availability Extraction from Scientific PDFs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ecoopen",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "gui": [
            "streamlit>=1.28.0",
            "plotly>=5.15.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ecoopen=ecoopen.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "ecoopen": ["*.txt", "*.md"],
    },
    keywords="pdf extraction data availability scientific papers LLM ollama",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/ecoopen/issues",
        "Source": "https://github.com/yourusername/ecoopen",
        "Documentation": "https://github.com/yourusername/ecoopen/blob/main/README.md",
    },
)

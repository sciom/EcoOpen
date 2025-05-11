from setuptools import setup, find_packages

setup(
    name="ecoopen",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A package to process DOIs, download PDFs, and analyze data and code availability statements.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ecoopen",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "requests",
        "spacy",
        "pyalex",
        "beautifulsoup4",
        "tqdm",
        "PyMuPDF",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            "ecoopen = ecoopen.cli:main",
        ],
    },
)
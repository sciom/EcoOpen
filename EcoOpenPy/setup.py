from setuptools import setup, find_packages

setup(
    name="ecoopen",
    version="0.1.0",
    description="A package to search and download open-access scientific papers",
    author="Domagoj",
    author_email="domagojhack@gmail.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "pandas>=2.0.0",
        "validators>=0.20.0",
        "tqdm>=4.65.0",
        "pyalex>=0.12.0",
    ],
    entry_points={
        "console_scripts": [
            "ecoopen=ecoopen:main",
        ],
    },
    python_requires=">=3.8",
)
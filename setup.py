#!/usr/bin/env python3
"""
Setup script for Vendra Quote Parser
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()

setup(
    name="vendra-quote-parser",
    version="1.0.0",
    author="Vendra Intern Coding Challenge",
    author_email="mmandapa@ucsc.edu",
    description="A robust Python-based parser for extracting structured quote data from supplier PDFs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mmandapa/vendra-oa",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "vendra-parser=vendra_parser.cli:cli",
        ],
    },
    include_package_data=True,
    zip_safe=False,
) 
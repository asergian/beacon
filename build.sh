#!/bin/bash
set -e  # Exit on error

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Make sure to activate the environment

# Install and upgrade build dependencies
python -m pip install --upgrade pip
pip install --upgrade wheel setuptools

# Split requirements into core and ML
grep -v "torch\|transformers\|spacy\|sentence-transformers\|nvidia" requirements.txt > requirements.core.txt
grep "torch\|transformers\|spacy\|sentence-transformers\|nvidia" requirements.txt > requirements.ml.txt

# Install core dependencies
pip install -r requirements.core.txt

# Install ML dependencies with specific platform tags
pip install -r requirements.ml.txt --index-url https://download.pytorch.org/whl/cpu

# Check if spaCy model is already installed (skip download if it is)
python -c "import spacy; spacy.load('en_core_web_sm')" || python -m spacy download en_core_web_sm
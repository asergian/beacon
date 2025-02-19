#!/bin/bash
set -e  # Exit on error

# Create and activate virtual environment
python -m venv .venv
. .venv/bin/activate

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

# Download spacy model explicitly (only if not already downloaded)
if [ ! -d ".venv/lib/python*/site-packages/en_core_web_sm" ]; then
    python -m spacy download en_core_web_sm
fi

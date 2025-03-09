#!/bin/bash
set -e  # Exit on error

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install and upgrade build dependencies
python -m pip install --upgrade pip
pip install --upgrade wheel setuptools

# Install pipreqs for automatic dependency detection
pip install pipreqs

# Automatically generate requirements.txt based on imports in the code
echo "Generating requirements.txt from actual imports..."
pipreqs . --force --encoding=latin1

# Install all dependencies from requirements.txt
# This now includes both app and documentation dependencies
pip install -r requirements.txt

# Build documentation
cd docs/sphinx
make html
cd ../..
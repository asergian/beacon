#!/bin/bash
set -e  # Exit on error

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install and upgrade build dependencies
python -m pip install --upgrade pip
pip install --upgrade wheel setuptools

# Install all dependencies from requirements.txt
pip install -r requirements.txt
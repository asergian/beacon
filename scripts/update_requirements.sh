#!/bin/bash
set -e  # Exit on error

# Install pipreqs if not already installed
pip install pipreqs

# Back up current requirements
if [ -f "requirements.txt" ]; then
  echo "Backing up current requirements.txt to requirements.txt.backup"
  cp requirements.txt requirements.txt.backup
fi

# Generate new requirements file
echo "Generating new requirements.txt from code imports..."
pipreqs . --force

echo "Requirements file has been updated successfully!"
echo "If you need to restore the previous version, use: mv requirements.txt.backup requirements.txt" 
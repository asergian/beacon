# Scripts Directory

This directory contains utility scripts for development, documentation management, and maintenance tasks related to the Beacon application.

## Overview

The scripts in this directory provide various tools that help with development workflows, documentation generation, testing, and other maintenance tasks. They are designed to automate common tasks and ensure consistency across the codebase.

## Available Scripts

### Documentation Scripts

| Script | Description |
|--------|-------------|
| `generate_readme.py` | Automatically generates standardized README.md files for modules in the codebase based on module structure, docstrings, and configuration. |
| `check_readme.py` | Checks existing README.md files for completeness, consistency, and adherence to project documentation standards. |
| `update_docs.py` | Maintains documentation consistency by rebuilding Sphinx documentation, checking docstring coverage, and creating documentation reports. |
| `check_docstrings.py` | Analyzes docstring coverage in the codebase and generates reports of missing docstrings to help prioritize documentation efforts. |
| `generate_docstrings.py` | Automatically generates Google-style docstring templates for Python functions and methods that are missing them. |

### Development Tools

| Script | Description |
|--------|-------------|
| `generate_cert.py` | Creates self-signed SSL certificates for local development with HTTPS. |
| `generate_demo_analysis.py` | Pre-generates and caches analysis results for all demo emails to ensure a smooth demo experience without API delays. |

## Usage

### Documentation Generation

Generate README for a specific module:

```bash
python scripts/generate_readme.py --module app.email.clients

# With increased verbosity (more detailed content)
python scripts/generate_readme.py --module app.email.clients --verbosity 3

# Generate and validate
python scripts/generate_readme.py --module app.email.clients --validate
```

Check existing README files for compliance:

```bash
# Check a specific README
python scripts/check_readme.py --path app/email/clients/README.md

# Check all READMEs recursively with more detail
python scripts/check_readme.py --path app/ --recursive --verbose
```

Update documentation and check docstring coverage:

```bash
python scripts/update_docs.py --report
```

Check docstring coverage and get a report of missing docstrings:

```bash
python scripts/check_docstrings.py app --min-coverage 80.0 --output docstring_report.txt
```

Generate Google-style docstrings for functions:

```bash
# Preview docstrings for a specific file
python scripts/generate_docstrings.py --path app/module.py --preview

# Generate docstrings for all Python files in a directory
python scripts/generate_docstrings.py --path app/ --recursive

# Generate a diff report without applying changes
python scripts/generate_docstrings.py --path app/ --diff-report docstrings.diff

# Exclude certain directories
python scripts/generate_docstrings.py --path app/ --recursive --exclude "tests,migrations"
```

### Development Tools

Generate self-signed certificates for HTTPS development:

```bash
python scripts/generate_cert.py
```

Pre-generate analysis for demo emails:

```bash
python scripts/generate_demo_analysis.py
```

## Adding New Scripts

When adding new scripts to this directory, please follow these guidelines:

1. Include a comprehensive module-level docstring explaining the script's purpose
2. Add proper docstrings for all functions with Args, Returns, and Raises sections
3. Use argparse for command-line argument parsing
4. Include a main() function for the main script logic
5. Add proper error handling and informative error messages
6. Update this README.md with information about the new script

## Script Dependencies

Script dependencies are included in the main project's `requirements.txt` file in the root directory. No separate installation is needed beyond the main project dependencies.

```bash
# To install all dependencies including those needed for scripts
pip install -r requirements.txt
```

If your script requires additional dependencies, please update the main `requirements.txt` file in the "Script utilities" section. 
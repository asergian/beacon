#!/usr/bin/env python
"""Documentation update helper.

This script helps maintain documentation consistency by:
1. Rebuilding Sphinx documentation
2. Checking docstring coverage
3. Creating a documentation report
"""

import subprocess
import os
import sys
import argparse
import time
from pathlib import Path
import json
from datetime import datetime


def run_cmd(cmd, cwd=None):
    """Run a shell command and return output.
    
    Args:
        cmd: Command to run
        cwd: Working directory for command
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        cwd=cwd,
        shell=True,
        universal_newlines=True
    )
    stdout, stderr = process.communicate()
    return stdout, stderr, process.returncode


def build_sphinx_docs():
    """Build the Sphinx documentation.
    
    Returns:
        Boolean indicating success
    """
    print("Building Sphinx documentation...")
    docs_dir = Path(__file__).parent.parent / "docs" / "sphinx"
    stdout, stderr, returncode = run_cmd("make html", cwd=docs_dir)
    
    if returncode == 0:
        print("✅ Sphinx documentation built successfully")
        print(f"   Documentation available at: {docs_dir}/build/html/index.html")
        return True
    else:
        print("❌ Sphinx documentation build failed")
        print(f"Error: {stderr}")
        return False


def check_docstrings():
    """Check docstring coverage using interrogate.
    
    Returns:
        Tuple of (coverage percentage, missing count, success boolean)
    """
    print("Checking docstring coverage...")
    app_dir = Path(__file__).parent.parent / "app"
    
    try:
        stdout, stderr, returncode = run_cmd(f"interrogate -v {app_dir}")
        
        if returncode == 0:
            # Parse coverage from output
            lines = stdout.split('\n')
            total_line = [l for l in lines if "TOTAL" in l and "|" in l]
            if total_line:
                parts = [p.strip() for p in total_line[0].split("|") if p.strip()]
                if len(parts) >= 5:
                    coverage = float(parts[3].replace("%", ""))
                    missing = int(parts[2])
                    print(f"✅ Docstring coverage: {coverage}% ({missing} missing)")
                    return coverage, missing, True
        
        print("❌ Failed to analyze docstring coverage")
        return 0, 0, False
    except Exception as e:
        print(f"❌ Error checking docstrings: {e}")
        return 0, 0, False


def create_doc_report(sphinx_success, coverage, missing):
    """Create a documentation status report.
    
    Args:
        sphinx_success: Whether Sphinx build succeeded
        coverage: Docstring coverage percentage
        missing: Number of missing docstrings
        
    Returns:
        Report filename
    """
    print("Creating documentation report...")
    docs_dir = Path(__file__).parent.parent / "docs"
    report_file = docs_dir / f"doc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write(f"BEACON DOCUMENTATION REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("Sphinx Documentation:\n")
        f.write(f"  Status: {'✅ Built successfully' if sphinx_success else '❌ Build failed'}\n")
        f.write(f"  Location: docs/sphinx/build/html/index.html\n\n")
        
        f.write("Docstring Coverage:\n")
        f.write(f"  Coverage: {coverage}%\n")
        f.write(f"  Missing: {missing} docstrings\n\n")
        
        # List main documentation files
        f.write("Documentation Files:\n")
        for doc_file in docs_dir.glob("*.md"):
            f.write(f"  - {doc_file.name} ({doc_file.stat().st_size / 1024:.1f} KB)\n")
        
        f.write("\n")
        f.write("=" * 80 + "\n")
    
    print(f"✅ Report created: {report_file}")
    return report_file


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Update and check documentation")
    parser.add_argument("--skip-sphinx", action="store_true", help="Skip Sphinx build")
    parser.add_argument("--report", action="store_true", help="Generate documentation report")
    args = parser.parse_args()
    
    sphinx_success = True
    if not args.skip_sphinx:
        sphinx_success = build_sphinx_docs()
    
    coverage, missing, docstring_success = check_docstrings()
    
    if args.report or not (sphinx_success and docstring_success):
        report_file = create_doc_report(sphinx_success, coverage, missing)
    
    if not sphinx_success or not docstring_success:
        sys.exit(1)


if __name__ == "__main__":
    main() 
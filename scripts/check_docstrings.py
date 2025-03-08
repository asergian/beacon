#!/usr/bin/env python
"""Docstring checker script.

This script runs interrogate to analyze docstring coverage in the codebase
and generates a report of missing docstrings to help prioritize documentation.
It can be used to maintain high docstring coverage as the codebase evolves.
"""

import subprocess
import sys
import os
import argparse
from typing import List, Dict, Any, Tuple
import json
from pathlib import Path


def run_interrogate(directory: str, verbose: bool = False, min_coverage: float = 95.0) -> Tuple[str, bool]:
    """Run interrogate on the specified directory.
    
    Args:
        directory: The directory to analyze
        verbose: Whether to include detailed output
        min_coverage: Minimum acceptable coverage percentage
        
    Returns:
        Tuple containing the output text and whether the command was successful
    """
    cmd = ["interrogate", directory, "-f", str(min_coverage)]
    if verbose:
        cmd.append("-v")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.returncode == 0
    except Exception as e:
        return f"Error running interrogate: {e}", False


def parse_results(output: str) -> Dict[str, Any]:
    """Parse the interrogate output to structured data.
    
    Args:
        output: The text output from interrogate
        
    Returns:
        Dictionary with parsed results including total coverage and file details
    """
    lines = output.split("\n")
    results = {
        "files": {},
        "total_coverage": 0.0,
        "total_missing": 0,
        "success": False,
    }
    
    # Extract file details
    current_file = None
    file_section = False
    for line in lines:
        if "Summary" in line and "----" in lines[lines.index(line) + 1]:
            file_section = False
            
        if file_section and "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 5:
                # Skip separator lines that contain only dashes
                if all(c == '-' for part in parts for c in part):
                    continue
                    
                file_path = parts[0]
                
                # Skip if not valid data (check if we can parse numbers)
                try:
                    total = int(parts[1])
                    missing = int(parts[2])
                    # Handle percentage form (e.g., "100%" or "100.0%")
                    cover_str = parts[4].replace("%", "").strip()
                    coverage = float(cover_str) if "." in cover_str else int(cover_str)
                    
                    results["files"][file_path] = {
                        "total": total,
                        "missing": missing,
                        "coverage": coverage
                    }
                except (ValueError, IndexError):
                    # This could be a header row or separator, skip it
                    continue
                
        if "Name" in line and "Total" in line and "Miss" in line and "Cover" in line:
            file_section = True
            
        # Extract total coverage
        if "TOTAL" in line and "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 5:
                try:
                    # Get the total coverage percentage from the correct column
                    total_coverage_str = parts[4].replace("%", "").strip()
                    results["total_coverage"] = float(total_coverage_str)
                    results["total_missing"] = int(parts[2])
                except (ValueError, IndexError):
                    # Skip if we can't parse the values
                    continue
                
        # Check if passed
        if "RESULT: PASSED" in line:
            results["success"] = True
    
    return results


def create_report(results: Dict[str, Any], min_coverage: float = 95.0) -> str:
    """Create a human-readable report from the parsed results.
    
    Args:
        results: The parsed interrogate results
        min_coverage: The minimum acceptable coverage percentage
        
    Returns:
        A formatted report string
    """
    report = []
    report.append("=" * 80)
    report.append(f"DOCSTRING COVERAGE REPORT - {results['total_coverage']:.1f}% coverage")
    report.append("=" * 80)
    
    # Overall status
    if results["success"]:
        report.append("\n✅ PASSED - Docstring coverage meets or exceeds requirements")
    else:
        report.append("\n❌ FAILED - Docstring coverage below requirements")
    
    report.append(f"\nTotal missing docstrings: {results['total_missing']}")
    
    # Files with low coverage
    low_coverage = {k: v for k, v in results["files"].items() 
                   if v["coverage"] < min_coverage and v["missing"] > 0}
    
    if low_coverage:
        report.append("\nFILES WITH LOW COVERAGE:")
        report.append("-" * 80)
        
        # Sort by coverage (ascending)
        sorted_files = sorted(low_coverage.items(), key=lambda x: x[1]["coverage"])
        
        for file_path, data in sorted_files:
            report.append(f"{file_path:<60} {data['coverage']}% ({data['missing']} missing)")
    
    # Suggest next files to improve
    if results["total_missing"] > 0:
        report.append("\nPRIORITY FILES TO FIX:")
        report.append("-" * 80)
        
        # Sort by number of missing docstrings (descending)
        missing_sorted = sorted(
            [(k, v) for k, v in results["files"].items() if v["missing"] > 0],
            key=lambda x: x[1]["missing"],
            reverse=True
        )
        
        for file_path, data in missing_sorted[:10]:  # Top 10
            report.append(f"{file_path:<60} {data['missing']} missing")
    
    return "\n".join(report)


def main():
    """Run the script."""
    parser = argparse.ArgumentParser(description="Check docstring coverage in the codebase")
    parser.add_argument("directory", nargs="?", default="app", help="Directory to analyze")
    parser.add_argument("--min-coverage", type=float, default=95.0, 
                        help="Minimum acceptable coverage percentage")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Show verbose output")
    parser.add_argument("--output", "-o", type=str, help="Output file for report")
    args = parser.parse_args()
    
    # Run interrogate
    print(f"Analyzing docstring coverage in '{args.directory}'...")
    output, success = run_interrogate(args.directory, args.verbose, args.min_coverage)
    
    if args.verbose:
        print(output)
    
    # Parse and create report
    results = parse_results(output)
    report = create_report(results, args.min_coverage)
    
    # Output report
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main() 
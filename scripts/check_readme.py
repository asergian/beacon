#!/usr/bin/env python
"""README Checker Script

This script checks existing README.md files for completeness, consistency,
and adherence to project documentation standards.

It analyzes the content of README files to ensure they contain all required
sections with sufficient detail, following the project's documentation guidelines.
The script can be run on individual files or recursively on directories, with
options for strict validation and detailed reporting.

Example usage:
    # Check a single README file
    python scripts/check_readme.py --path app/module/README.md
    
    # Check all READMEs in a directory recursively
    python scripts/check_readme.py --path app/ --recursive
    
    # Apply stricter validation rules
    python scripts/check_readme.py --path app/ --recursive --strict
"""

import os
import sys
import argparse
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Required sections and their minimum content lengths
REQUIRED_SECTIONS = {
    "overview": 100,          # Overview should be at least 100 chars
    "directory structure": 20, # Directory structure should be at least 20 chars
    "components": 50,         # Components should be at least 50 chars
    "usage examples": 50,     # Usage examples should be at least 50 chars
    "internal design": 50,    # Internal design should be at least 50 chars
    "dependencies": 10,       # Dependencies should list at least something
    "additional resources": 10 # Should have at least one link
}

# Optional but recommended sections
RECOMMENDED_SECTIONS = [
    "installation",
    "configuration",
    "troubleshooting"
]


def parse_args():
    """Parse command-line arguments for the README checker.
    
    Sets up the argument parser with options for the path to check,
    recursive checking, strict validation, and verbose output.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Check README.md files for completeness")
    parser.add_argument(
        "--path", 
        help="Path to check (directory containing README.md or direct path to README.md)",
        default="."
    )
    parser.add_argument(
        "--recursive", 
        action="store_true", 
        help="Recursively check all README.md files in subdirectories"
    )
    parser.add_argument(
        "--strict", 
        action="store_true", 
        help="Enforce stricter requirements on content"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Show detailed information about each README"
    )
    return parser.parse_args()


def find_readme_files(start_path: str, recursive: bool = False) -> List[Path]:
    """Find README.md files starting from the given path.
    
    Searches for README.md files in the specified path. If the path points
    directly to a README.md file, returns just that file. If it points to a
    directory, checks for a README.md in that directory and optionally in all
    subdirectories if recursive is True.
    
    Args:
        start_path (str): The file or directory path to search.
        recursive (bool, optional): Whether to recursively search subdirectories.
                                   Defaults to False.
    
    Returns:
        List[Path]: A list of Path objects pointing to README.md files.
    """
    path = Path(start_path)
    
    if path.is_file() and path.name.lower() == "readme.md":
        return [path]
    
    readme_files = []
    
    if path.is_dir():
        # Check for README.md in the current directory
        readme_path = path / "README.md"
        if readme_path.exists():
            readme_files.append(readme_path)
        
        # Check subdirectories if recursive is True
        if recursive:
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith((".", "__")):
                    readme_files.extend(find_readme_files(item, recursive))
    
    return readme_files


def parse_readme_sections(readme_path: Path) -> Dict[str, str]:
    """Parse a README.md file into sections.
    
    Reads a README.md file and parses it into a dictionary of sections based on
    the markdown headings (## Section Title). The content of each section is
    extracted, and the title of the README is also extracted if present.
    
    Args:
        readme_path (Path): Path to the README.md file to parse.
    
    Returns:
        Dict[str, str]: A dictionary mapping section names (lowercase) to their content.
                      The 'header' key contains content before the first section,
                      and 'title' contains the main title if found.
    """
    sections = {}
    current_section = "header"
    current_content = []
    
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line in lines:
            # Check for section headers (## Title)
            if line.startswith("## "):
                # Save the previous section
                if current_section and current_content:
                    sections[current_section.lower()] = "".join(current_content).strip()
                
                # Start a new section
                current_section = line[3:].strip().lower()
                current_content = []
            else:
                current_content.append(line)
        
        # Save the last section
        if current_section and current_content:
            sections[current_section.lower()] = "".join(current_content).strip()
        
        # If there's content before the first section header, save it as "header"
        if "header" in sections and sections["header"].strip():
            # Extract the title from the header (# Title)
            title_match = re.search(r'^# (.+)$', sections["header"], re.MULTILINE)
            if title_match:
                sections["title"] = title_match.group(1).strip()
    
    except Exception as e:
        print(f"Error parsing {readme_path}: {e}")
        return {}
    
    return sections


def check_readme(readme_path: Path, strict: bool = False) -> Dict[str, object]:
    """Check a README file for completeness and consistency.
    
    Analyzes a README.md file to ensure it contains all required sections
    with sufficient content. The function performs various checks including
    section presence, content length, code examples, and more.
    
    Args:
        readme_path (Path): Path to the README.md file to check.
        strict (bool, optional): Whether to apply stricter validation rules.
                               Defaults to False.
    
    Returns:
        Dict[str, object]: Results of the check, including:
            - path: The path to the README file
            - missing_sections: List of required sections that are missing
            - short_sections: List of sections with insufficient content
            - missing_recommended: List of recommended sections that are missing
            - has_code_examples: Whether the file contains code examples
            - section_count: Total number of sections
            - word_count: Total word count
            - pass: Whether the README passed validation
    """
    sections = parse_readme_sections(readme_path)
    
    # Initialize results
    results = {
        "path": readme_path,
        "missing_sections": [],
        "short_sections": [],
        "missing_recommended": [],
        "has_code_examples": False,
        "section_count": len(sections),
        "word_count": sum(len(content.split()) for content in sections.values()),
        "pass": True
    }
    
    # Check required sections
    for section, min_length in REQUIRED_SECTIONS.items():
        if section not in sections:
            results["missing_sections"].append(section)
            results["pass"] = False
        elif len(sections[section]) < min_length:
            results["short_sections"].append((section, len(sections[section]), min_length))
            if strict:
                results["pass"] = False
    
    # Check recommended sections
    for section in RECOMMENDED_SECTIONS:
        if section not in sections:
            results["missing_recommended"].append(section)
    
    # Check for code examples
    if "usage examples" in sections:
        if "```" in sections["usage examples"]:
            results["has_code_examples"] = True
        elif strict:
            results["pass"] = False
    
    # Additional checks in strict mode
    if strict:
        # Check for empty title
        if "title" not in sections or not sections["title"]:
            results["missing_sections"].append("title")
            results["pass"] = False
        
        # Check for short title
        elif len(sections["title"]) < 10:
            results["short_sections"].append(("title", len(sections["title"]), 10))
            results["pass"] = False
        
        # Check for links in additional resources
        if "additional resources" in sections and "[" not in sections["additional resources"]:
            results["short_sections"].append(("additional resources - missing links", 0, 1))
            results["pass"] = False
    
    return results


def print_results(results: Dict[str, object], verbose: bool = False):
    """Print the check results in a readable format.
    
    Formats and displays the results of the README validation checks,
    highlighting any issues found and providing details based on the
    verbosity level.
    
    Args:
        results (Dict[str, object]): The validation results from check_readme().
        verbose (bool, optional): Whether to include detailed information
                                 about the README. Defaults to False.
    """
    path = results["path"]
    
    if results["pass"]:
        print(f"✅ PASS: {path}")
        
        if verbose:
            print(f"  Sections: {results['section_count']}")
            print(f"  Word count: {results['word_count']}")
            
            if results["missing_recommended"]:
                print(f"  Missing recommended sections: {', '.join(results['missing_recommended'])}")
            
            print("")
    else:
        print(f"❌ FAIL: {path}")
        
        if results["missing_sections"]:
            print(f"  Missing required sections: {', '.join(results['missing_sections'])}")
        
        if results["short_sections"]:
            for section, length, min_length in results["short_sections"]:
                print(f"  Section '{section}' is too short: {length} chars (min: {min_length})")
        
        if not results["has_code_examples"] and "usage examples" not in results["missing_sections"]:
            print("  Usage Examples section exists but has no code blocks")
        
        if verbose:
            print(f"  Sections: {results['section_count']}")
            print(f"  Word count: {results['word_count']}")
            
            if results["missing_recommended"]:
                print(f"  Missing recommended sections: {', '.join(results['missing_recommended'])}")
        
        print("")


def main():
    """Main function to run the README checker.
    
    Parses command-line arguments, finds README files to check, 
    performs validation on each file, and prints the results.
    Exits with status code 0 if all files pass, 1 otherwise.
    """
    args = parse_args()
    
    readme_files = find_readme_files(args.path, args.recursive)
    
    if not readme_files:
        print(f"No README.md files found at {args.path}")
        sys.exit(1)
    
    print(f"Checking {len(readme_files)} README.md files...")
    print("")
    
    all_pass = True
    for readme_path in readme_files:
        results = check_readme(readme_path, args.strict)
        print_results(results, args.verbose)
        
        if not results["pass"]:
            all_pass = False
    
    if all_pass:
        print("All README files passed validation!")
        sys.exit(0)
    else:
        print("Some README files need attention.")
        sys.exit(1)


if __name__ == "__main__":
    main() 
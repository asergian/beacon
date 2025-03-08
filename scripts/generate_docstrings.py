#!/usr/bin/env python3
"""Generate Google-style docstrings for Python functions.

This script analyzes Python files to find functions and methods without
docstrings, then automatically generates Google-style docstring templates
based on type hints, parameter names, and function names.

It can process individual files or entire directories, and can either:
1. Apply the changes directly to the files
2. Show a preview of the changes without modifying files
3. Generate a diff report showing all proposed changes

Example usage:
    # Preview docstrings for a single file
    python scripts/generate_docstrings.py --path app/module.py --preview

    # Generate docstrings for all Python files in a directory
    python scripts/generate_docstrings.py --path app/ --recursive

    # Generate a diff report
    python scripts/generate_docstrings.py --path app/ --diff-report report.diff
"""

import os
import sys
import ast
import re
import argparse
import inspect
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional, Any, Union


def parse_args():
    """Parse command-line arguments for the docstring generator.
    
    Sets up the argument parser with options for the path to process,
    recursive processing, preview mode, and diff reporting.
    
    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate Google-style docstrings for Python functions and methods"
    )
    parser.add_argument(
        "--path",
        help="Path to a Python file or directory containing Python files",
        required=True
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively process Python files in subdirectories"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview changes without modifying files"
    )
    parser.add_argument(
        "--diff-report",
        help="Generate a diff report file instead of applying changes"
    )
    parser.add_argument(
        "--exclude",
        help="Comma-separated list of directories or files to exclude"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Generate docstrings until this coverage percentage is reached"
    )
    return parser.parse_args()


def find_python_files(start_path: str, recursive: bool = False, exclude: List[str] = None) -> List[Path]:
    """Find Python files starting from the given path.
    
    Args:
        start_path: The file or directory path to search
        recursive: Whether to recursively search subdirectories
        exclude: List of directory or file names to exclude
    
    Returns:
        A list of Path objects pointing to Python files
    """
    exclude = exclude or []
    path = Path(start_path)
    python_files = []
    
    if path.is_file() and path.name.endswith(".py"):
        python_files.append(path)
        return python_files
    
    if path.is_dir():
        for item in path.glob("**/*.py" if recursive else "*.py"):
            # Check if the item should be excluded
            if any(ex in str(item) for ex in exclude):
                continue
            python_files.append(item)
    
    return python_files


class DocstringVisitor(ast.NodeVisitor):
    """AST visitor to find functions and methods without docstrings."""
    
    def __init__(self):
        """Initialize the visitor with empty collections for tracking functions."""
        self.functions_without_docstrings = []
        self.total_functions = 0
    
    def visit_FunctionDef(self, node):
        """Visit a function definition node in the AST.
        
        Args:
            node: The FunctionDef node being visited
        """
        self.total_functions += 1
        
        # Check if function has a docstring
        docstring = ast.get_docstring(node)
        if not docstring:
            # Collect info about functions without docstrings
            self.functions_without_docstrings.append({
                'name': node.name,
                'lineno': node.lineno,
                'end_lineno': getattr(node, 'end_lineno', None),
                'args': node.args,
                'returns': self._get_return_annotation(node),
                'is_method': self._is_method(node),
                'body': node.body,
                'raises': self._extract_raises(node)
            })
        
        # Continue visiting any functions defined inside this one
        self.generic_visit(node)
    
    def _get_return_annotation(self, node):
        """Extract return type annotation from a function node.
        
        Args:
            node: The FunctionDef node
            
        Returns:
            The return annotation if present, None otherwise
        """
        if node.returns:
            return node.returns
        
        # Try to infer return from return statements
        return_values = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and child.value:
                return_values.append(child.value)
        
        # TODO: Implement more sophisticated return type inference if needed
        return None
    
    def _is_method(self, node):
        """Determine if a function node represents a method in a class.
        
        Args:
            node: The FunctionDef node
            
        Returns:
            True if the function is a method, False otherwise
        """
        # Check if the parent is a class definition
        for parent in ast.walk(ast.parse("")):
            for child in ast.iter_child_nodes(parent):
                if isinstance(parent, ast.ClassDef) and child is node:
                    return True
        return False
    
    def _extract_raises(self, node):
        """Extract exception types that may be raised by this function.
        
        Args:
            node: The FunctionDef node
            
        Returns:
            A list of exception types that the function may raise
        """
        exceptions = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                if isinstance(child.exc, ast.Name):
                    exceptions.append(child.exc.id)
                elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                    exceptions.append(child.exc.func.id)
        return list(set(exceptions))


def extract_undocumented_functions(file_path: Path) -> Tuple[List[Dict], int]:
    """Extract information about functions without docstrings from a Python file.
    
    Args:
        file_path: Path to the Python file to analyze
    
    Returns:
        A tuple containing a list of dictionaries with function information
        and the total number of functions found
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
        visitor = DocstringVisitor()
        visitor.visit(tree)
        return visitor.functions_without_docstrings, visitor.total_functions
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
        return [], 0


def format_google_docstring(func_info: Dict) -> str:
    """Format a Google-style docstring based on function information.
    
    Args:
        func_info: Dictionary with function information
    
    Returns:
        A formatted Google-style docstring
    """
    # Start with the basic docstring template
    docstring_lines = ['"""', ""]
    
    # Try to generate a meaningful description based on function name
    func_name = func_info["name"]
    
    # Exclude certain special methods
    if func_name == "__init__":
        docstring_lines[0] = '"""Initialize the class.'
    elif func_name.startswith("get_"):
        docstring_lines[0] = f'"""Get the {func_name[4:].replace("_", " ")}.'
    elif func_name.startswith("set_"):
        docstring_lines[0] = f'"""Set the {func_name[4:].replace("_", " ")}.'
    elif func_name.startswith("is_"):
        docstring_lines[0] = f'"""Check if {func_name[3:].replace("_", " ")}.'
    elif func_name.startswith("has_"):
        docstring_lines[0] = f'"""Check if {func_name[4:].replace("_", " ")} exists.'
    elif func_name == "main":
        docstring_lines[0] = '"""Main function that orchestrates the program execution.'
    else:
        # For other functions, just convert underscores to spaces and capitalize
        description = func_name.replace("_", " ")
        docstring_lines[0] = f'"""{description.capitalize()}.'
    
    # Add Args section if there are arguments
    args = func_info["args"]
    
    # Filter out self/cls for methods
    arg_names = [arg.arg for arg in args.args 
                if arg.arg not in ("self", "cls") or not func_info["is_method"]]
    
    if arg_names:
        docstring_lines.extend(["", "Args:"])
        for arg in args.args:
            if arg.arg in ("self", "cls") and func_info["is_method"]:
                continue
                
            arg_name = arg.arg
            arg_type = ""
            if arg.annotation:
                try:
                    if isinstance(arg.annotation, ast.Name):
                        arg_type = arg.annotation.id
                    elif isinstance(arg.annotation, ast.Subscript):
                        if isinstance(arg.annotation.value, ast.Name):
                            arg_type = arg.annotation.value.id
                            if isinstance(arg.annotation.slice, ast.Name):
                                arg_type += f"[{arg.annotation.slice.id}]"
                            elif hasattr(arg.annotation.slice, 'value') and isinstance(arg.annotation.slice.value, ast.Name):
                                arg_type += f"[{arg.annotation.slice.value.id}]"
                except (AttributeError, ValueError):
                    pass
                
            # Format the argument
            if arg_type:
                docstring_lines.append(f"    {arg_name} ({arg_type}): Description of {arg_name}")
            else:
                docstring_lines.append(f"    {arg_name}: Description of {arg_name}")
    
    # Add Returns section if the function returns something
    returns = func_info["returns"]
    if returns:
        return_type = ""
        try:
            if isinstance(returns, ast.Name):
                return_type = returns.id
            elif isinstance(returns, ast.Subscript):
                if isinstance(returns.value, ast.Name):
                    return_type = returns.value.id
                    if isinstance(returns.slice, ast.Name):
                        return_type += f"[{returns.slice.id}]"
                    elif hasattr(returns.slice, 'value') and isinstance(returns.slice.value, ast.Name):
                        return_type += f"[{returns.slice.value.id}]"
        except (AttributeError, ValueError):
            pass
            
        docstring_lines.extend(["", "Returns:"])
        if return_type:
            docstring_lines.append(f"    {return_type}: Description of return value")
        else:
            docstring_lines.append("    Description of return value")
    
    # Add Raises section if the function raises exceptions
    raises = func_info["raises"]
    if raises:
        docstring_lines.extend(["", "Raises:"])
        for exception in raises:
            docstring_lines.append(f"    {exception}: Description of when this error is raised")
    
    docstring_lines.append('"""')
    return "\n".join(docstring_lines)


def insert_docstring(content: str, func_info: Dict, docstring: str) -> str:
    """Insert a docstring into a function in the source code.
    
    Args:
        content: The source code content
        func_info: Dictionary with function information
        docstring: The formatted docstring to insert
    
    Returns:
        The modified source code with the docstring inserted
    """
    lines = content.splitlines()
    
    # Find the line after function definition
    lineno = func_info["lineno"]
    line = lines[lineno - 1]
    
    # Find where to insert the docstring (after colon and any comments)
    indent = len(line) - len(line.lstrip())
    insert_indent = indent + 4  # Standard indentation for docstring
    
    # Format the docstring with proper indentation
    docstring_lines = docstring.splitlines()
    indented_docstring = [" " * indent + docstring_lines[0]]
    for d_line in docstring_lines[1:]:
        indented_docstring.append(" " * insert_indent + d_line if d_line else d_line)
    
    # Insert the docstring after the function declaration
    result = lines[:lineno]
    result.append(indented_docstring[0])
    result.extend(indented_docstring[1:])
    result.extend(lines[lineno:])
    
    return "\n".join(result)


def process_file(file_path: Path, preview: bool = False) -> Tuple[int, int, List[str]]:
    """Process a single file to add missing docstrings.
    
    Args:
        file_path: Path to the Python file to process
        preview: Whether to preview changes without modifying the file
    
    Returns:
        A tuple containing the number of docstrings added, total functions,
        and a list of preview strings if preview=True
    """
    print(f"Processing {file_path}...")
    
    # Extract functions without docstrings
    funcs_without_docstrings, total_functions = extract_undocumented_functions(file_path)
    
    if not funcs_without_docstrings:
        print(f"  All functions in {file_path} already have docstrings!")
        return 0, total_functions, []
    
    # Read the file content
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    original_content = content
    preview_data = []
    
    # Sort functions by line number (descending) to insert from bottom to top
    # This prevents line numbers from shifting as we insert docstrings
    for func_info in sorted(funcs_without_docstrings, key=lambda x: x["lineno"], reverse=True):
        # Generate docstring
        docstring = format_google_docstring(func_info)
        
        # Preview or insert
        if preview:
            preview_data.append({
                "file": str(file_path),
                "function": func_info["name"],
                "line": func_info["lineno"],
                "docstring": docstring
            })
        else:
            # Insert the docstring
            content = insert_docstring(content, func_info, docstring)
    
    # Write the modified content back to the file if not in preview mode
    if not preview and content != original_content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    # Calculate preview strings
    preview_strings = []
    for data in preview_data:
        preview_strings.append(f"File: {data['file']}")
        preview_strings.append(f"Function: {data['function']} (line {data['line']})")
        preview_strings.append("Generated docstring:")
        preview_strings.append("-" * 40)
        preview_strings.append(data['docstring'])
        preview_strings.append("-" * 40)
        preview_strings.append("")
    
    return len(funcs_without_docstrings), total_functions, preview_strings


def generate_diff_report(file_path: Path, output_file: str):
    """Generate a diff report showing docstring changes without applying them.
    
    Args:
        file_path: Path to process (file or directory)
        output_file: Path to the output diff report file
    """
    import difflib
    
    args = parse_args()
    python_files = find_python_files(
        str(file_path), 
        args.recursive,
        args.exclude.split(",") if args.exclude else []
    )
    
    diff_lines = []
    
    for py_file in python_files:
        # Extract functions without docstrings
        funcs_without_docstrings, _ = extract_undocumented_functions(py_file)
        
        if not funcs_without_docstrings:
            continue
        
        # Read the file content
        with open(py_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        original_content = content
        
        # Sort functions by line number (descending)
        for func_info in sorted(funcs_without_docstrings, key=lambda x: x["lineno"], reverse=True):
            # Generate docstring
            docstring = format_google_docstring(func_info)
            
            # Insert the docstring
            content = insert_docstring(content, func_info, docstring)
        
        # If changes were made, add to diff
        if content != original_content:
            diff = difflib.unified_diff(
                original_content.splitlines(True),
                content.splitlines(True),
                fromfile=str(py_file),
                tofile=str(py_file) + " (with docstrings)"
            )
            diff_lines.extend(diff)
            diff_lines.append("\n")
    
    # Write the diff report
    with open(output_file, "w", encoding="utf-8") as f:
        f.writelines(diff_lines)
    
    print(f"Diff report generated at {output_file}")


def calculate_coverage(functions_with_docstrings: int, total_functions: int) -> float:
    """Calculate the docstring coverage percentage.
    
    Args:
        functions_with_docstrings: Number of functions with docstrings
        total_functions: Total number of functions
    
    Returns:
        The coverage percentage as a float
    """
    if total_functions == 0:
        return 100.0
    return (functions_with_docstrings / total_functions) * 100


def main():
    """Main function that orchestrates the docstring generation process."""
    args = parse_args()
    
    # Generate diff report if requested
    if args.diff_report:
        generate_diff_report(Path(args.path), args.diff_report)
        return
    
    # Find Python files to process
    python_files = find_python_files(
        args.path, 
        args.recursive,
        args.exclude.split(",") if args.exclude else []
    )
    
    if not python_files:
        print(f"No Python files found at {args.path}")
        sys.exit(1)
    
    print(f"Found {len(python_files)} Python files to process")
    
    # Process files
    total_added = 0
    total_functions = 0
    all_previews = []
    
    for py_file in python_files:
        added, functions, previews = process_file(py_file, args.preview)
        total_added += added
        total_functions += functions
        all_previews.extend(previews)
    
    # Calculate coverage
    current_coverage = calculate_coverage(
        total_functions - total_added, 
        total_functions
    )
    new_coverage = calculate_coverage(
        total_functions, 
        total_functions
    )
    
    # Print summary
    print("\nSummary:")
    print(f"Files processed: {len(python_files)}")
    print(f"Total functions: {total_functions}")
    print(f"Missing docstrings: {total_added}")
    print(f"Current coverage: {current_coverage:.1f}%")
    print(f"New coverage: {new_coverage:.1f}%")
    
    # Print previews if requested
    if args.preview and all_previews:
        print("\nPreviews of generated docstrings:")
        print("=" * 60)
        print("\n".join(all_previews))
        print("=" * 60)
        print(f"\nRun without --preview to apply these changes to {total_added} functions")


if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Markdown to HTML converter for Sphinx documentation.

This script converts Markdown README files to HTML files that can be embedded 
in the Sphinx documentation using iframes. It recursively searches for README.md 
files in the specified directories and converts them to HTML.

Usage:
    python convert_md_to_html.py

The script is automatically run during the Sphinx build process.
"""

import os
import sys
import markdown
import re
from pathlib import Path


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            padding: 0;
            margin: 0;
            color: #333;
        }}
        .markdown-body {{
            padding: 15px;
        }}
        h1 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }}
        h2 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 0.3em;
        }}
        pre {{
            background-color: #f6f8fa;
            border-radius: 3px;
            padding: 16px;
            overflow: auto;
        }}
        code {{
            background-color: rgba(27, 31, 35, 0.05);
            border-radius: 3px;
            padding: 0.2em 0.4em;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
        }}
        pre code {{
            background-color: transparent;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding: 0 1em;
            color: #6a737d;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
        }}
        table th, table td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
        }}
        table tr:nth-child(2n) {{
            background-color: #f6f8fa;
        }}
    </style>
</head>
<body>
    <div class="markdown-body">
        {content}
    </div>
</body>
</html>
"""


def convert_markdown_to_html(markdown_file: Path, output_file: Path):
    """
    Convert a Markdown file to HTML.
    
    Args:
        markdown_file: Path to the Markdown file to convert.
        output_file: Path where the HTML file will be saved.
    """
    try:
        # Read the Markdown content
        with open(markdown_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            md_content,
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.codehilite',
            ]
        )
        
        # Extract title from the first heading
        title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
        title = title_match.group(1) if title_match else "Module Documentation"
        
        # Create HTML using the template
        html = HTML_TEMPLATE.format(title=title, content=html_content)
        
        # Write the HTML file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
            
        print(f"Converted {markdown_file} to {output_file}")
    
    except Exception as e:
        print(f"Error converting {markdown_file}: {e}")


def find_and_convert_readmes(base_dir: Path):
    """
    Find README.md files in the given directory and its subdirectories and convert them to HTML.
    
    Args:
        base_dir: Base directory to search for README.md files.
    """
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "README.md":
                md_file = Path(root) / file
                rel_path = md_file.relative_to(base_dir.parent)
                html_file = md_file.with_suffix('.html')
                convert_markdown_to_html(md_file, html_file)


def main():
    """Main function to run the conversion process."""
    # Get the project root directory (2 levels up from this script)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent.parent
    app_dir = project_root / "app"
    
    # Find and convert README files in the app directory
    print(f"Converting README.md files in {app_dir}...")
    find_and_convert_readmes(app_dir)
    
    # Also convert the docs directory README files
    docs_dir = project_root / "docs"
    print(f"Converting README.md files in {docs_dir}...")
    find_and_convert_readmes(docs_dir)
    
    print("Conversion complete!")


if __name__ == "__main__":
    main() 
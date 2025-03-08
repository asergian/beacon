#!/usr/bin/env python
"""
Smart Requirements Generator

This script:
1. Uses pipreqs to analyze imports in your code
2. Preserves existing comments and version pins from your current requirements.txt
3. Adds any new packages found by pipreqs
4. Creates a merged requirements file
5. Handles case insensitivity and package naming differences

Usage:
    python scripts/smart_requirements.py
"""

import subprocess
import re
import os
import sys
from collections import defaultdict

# Common package name transformations (import name -> pip name)
PACKAGE_NAME_MAPPINGS = {
    "flask_sqlalchemy": "flask-sqlalchemy",
    "flask-sqlalchemy": "flask-sqlalchemy",
    "flask_migrate": "flask-migrate",
    "flask-migrate": "flask-migrate",
    "flask_limiter": "flask-limiter",
    "flask-limiter": "flask-limiter",
    "python_dotenv": "python-dotenv",
    "google_api_python_client": "google-api-python-client",
    "google-api-python-client": "google-api-python-client",
    "google_auth_oauthlib": "google-auth-oauthlib",
    "google-auth-oauthlib": "google-auth-oauthlib",
    "upstash_redis": "upstash-redis",
    "upstash-redis": "upstash-redis",
}

def normalize_package_name(name):
    """Normalize package name to handle case and format differences."""
    # First convert to lowercase
    name_lower = name.lower()
    
    # Special handling for Flask extensions which can have different formats
    if name_lower.startswith(('flask_', 'flask-')):
        # Convert Flask-Something or flask_something to flask-something
        if '_' in name_lower:
            name_lower = name_lower.replace('_', '-')
        return name_lower
        
    # Replace underscores with hyphens for common packages
    normalized = name_lower.replace('_', '-')
    
    # Use specific mappings if available
    return PACKAGE_NAME_MAPPINGS.get(normalized, normalized)

def are_same_package(name1, name2):
    """Determine if two package names refer to the same package."""
    return normalize_package_name(name1) == normalize_package_name(name2)

def run_pipreqs():
    """Run pipreqs and return detected packages."""
    print("Installing pipreqs if needed...")
    subprocess.run(["pip", "install", "pipreqs"], check=True, capture_output=True)
    
    print("Running pipreqs to detect imports...")
    temp_file = "requirements.pipreqs.txt"
    subprocess.run(["pipreqs", ".", "--force", "--savepath", temp_file], check=True)
    
    packages = {}
    with open(temp_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    # Store with normalized name
                    normalized_name = normalize_package_name(name)
                    packages[normalized_name] = version
                else:
                    normalized_name = normalize_package_name(line)
                    packages[normalized_name] = None
    
    # Clean up temporary file
    os.remove(temp_file)
    return packages

def read_current_requirements():
    """Read current requirements.txt and parse into sections with comments."""
    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        return {}, [], {}
    
    sections = defaultdict(list)
    current_section = "default"
    package_versions = {}
    comments = []
    original_package_lines = {}  # Store original lines for each package
    
    with open(req_file, 'r') as f:
        for line in f:
            line = line.rstrip()
            if not line:
                # Only add empty line if the last line in this section wasn't already empty
                if sections[current_section] and sections[current_section][-1] != "":
                    sections[current_section].append("")
            elif line.startswith('#'):
                # This is a comment or section header
                sections[current_section].append(line)
                comments.append(line)
                # Check if this comment looks like a section header
                if line.startswith('# ') and line[2:].strip() and not any(c in line[2:] for c in '=<>():'):
                    current_section = line[2:].strip()
            else:
                sections[current_section].append(line)
                # Extract package name and version
                name = line
                if '==' in line:
                    parts = line.split('==', 1)
                    name = parts[0].strip()
                    # Handle [async] and similar extras
                    if '[' in name:
                        name = name.split('[')[0].strip()
                    normalized_name = normalize_package_name(name)
                    version = parts[1].strip()
                    package_versions[normalized_name] = version
                    original_package_lines[normalized_name] = line
                elif '>=' in line or '~=' in line or '<=' in line:
                    # Handle other version specifiers
                    name = re.split('[<>=~]', line)[0].strip()
                    # Handle [async] and similar extras
                    if '[' in name:
                        name = name.split('[')[0].strip()
                    normalized_name = normalize_package_name(name)
                    package_versions[normalized_name] = line[len(name):].strip()
                    original_package_lines[normalized_name] = line
                else:
                    # Handle [async] and similar extras
                    if '[' in name:
                        name = name.split('[')[0].strip()
                    normalized_name = normalize_package_name(name)
                    package_versions[normalized_name] = None
                    original_package_lines[normalized_name] = line
    
    return sections, comments, package_versions, original_package_lines

def merge_requirements(pipreqs_packages, sections, existing_versions, original_lines):
    """Merge pipreqs output with existing requirements structure."""
    # Identify new packages not in the current requirements.txt
    new_packages = {}
    for name, version in pipreqs_packages.items():
        is_new = True
        for existing_name in existing_versions:
            if are_same_package(name, existing_name):
                is_new = False
                break
        if is_new:
            new_packages[name] = version
    
    # Also identify packages with newer versions
    updated_packages = {}
    for name, version in pipreqs_packages.items():
        for existing_name, existing_version in existing_versions.items():
            if are_same_package(name, existing_name) and existing_version != version and version is not None and existing_version is not None and not existing_version.startswith('>'):
                updated_packages[name] = (existing_version, version)
    
    if new_packages:
        print(f"\nFound {len(new_packages)} new package(s) to add:")
        for pkg in sorted(new_packages.keys()):
            version = new_packages[pkg]
            if version:
                print(f"  - {pkg}=={version}")
            else:
                print(f"  - {pkg}")
                
        # If there's a "# New Packages" section, add them there, otherwise create one
        if "New Packages" in sections:
            # Add new packages to the New Packages section
            for pkg, version in sorted(new_packages.items()):
                if version:
                    sections["New Packages"].append(f"{pkg}=={version}")
                else:
                    sections["New Packages"].append(pkg)
        else:
            # No existing section for new packages, so add one
            if sections["default"] and sections["default"][-1] != "":
                sections["default"].append("")  # Add a blank line for separation
            sections["default"].append("# New Packages (detected by pipreqs)")
            for pkg, version in sorted(new_packages.items()):
                if version:
                    sections["default"].append(f"{pkg}=={version}")
                else:
                    sections["default"].append(pkg)
    else:
        print("\nNo new packages found to add.")
    
    # Print information about version updates
    if updated_packages:
        print(f"\nFound {len(updated_packages)} package(s) with version differences:")
        for pkg, (old_ver, new_ver) in sorted(updated_packages.items()):
            print(f"  - {pkg}: {old_ver} -> {new_ver}")
        
        print("\nNote: Version differences were detected but not applied automatically.")
        print("Review these differences and update manually if needed.")
    
    return sections

def write_requirements(sections):
    """Write merged requirements to file."""
    # Prepare content to write with proper spacing
    content = []
    
    # Write default section first
    if "default" in sections:
        content.extend(sections["default"])
        del sections["default"]
    
    # Write remaining sections (except New Packages)
    for section, lines in sections.items():
        if section == "New Packages":
            continue  # We'll handle New Packages section last
        if content and content[-1] != "":
            content.append("")  # Add a blank line between sections if needed
        content.extend(lines)
    
    # Write New Packages section last if it exists
    if "New Packages" in sections:
        if content and content[-1] != "":
            content.append("")  # Add a blank line before New Packages section
        content.extend(sections["New Packages"])
    
    # Remove consecutive empty lines and trailing empty lines
    cleaned_content = []
    for i, line in enumerate(content):
        # Skip consecutive empty lines
        if line == "" and (i > 0 and content[i-1] == ""):
            continue
        cleaned_content.append(line)
    
    # Remove trailing empty lines
    while cleaned_content and cleaned_content[-1] == "":
        cleaned_content.pop()
    
    # Write to file
    with open("requirements.txt", 'w') as f:
        for line in cleaned_content:
            f.write(line + '\n')

def remove_duplicates():
    """Remove duplicate packages from requirements.txt by checking for case insensitive matches."""
    try:
        print("\nChecking for duplicates...")
        # Read current requirements.txt
        with open("requirements.txt", 'r') as f:
            lines = f.readlines()
        
        # Parse package names and versions
        packages = defaultdict(list)  # normalized_name -> list of line indices
        comment_lines = []
        empty_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                empty_lines.append(i)
                continue
            if line.startswith('#'):
                comment_lines.append(i)
                continue
                
            # Check if this is a package line
            if '==' in line or '>=' in line or '<=' in line or '~=' in line:
                # Extract package name (handle extras like [async])
                name = re.split(r'[<>=~\[]', line)[0].strip()
                if '[' in name:
                    base_name = name.split('[')[0].strip()
                else:
                    base_name = name
                
                normalized_name = normalize_package_name(base_name)
                packages[normalized_name].append(i)
            else:
                # Package without version
                if '[' in line:
                    base_name = line.split('[')[0].strip()
                else:
                    base_name = line
                
                normalized_name = normalize_package_name(base_name)
                packages[normalized_name].append(i)
        
        # Find duplicates and mark lines to keep
        lines_to_keep = set(range(len(lines)))
        duplicates_found = False
        
        # Print duplicates
        for pkg, indices in packages.items():
            if len(indices) > 1:
                duplicates_found = True
                print(f"  - Found duplicate for '{pkg}':")
                
                # Find the best version to keep
                # Scoring system for package line preference
                def get_line_score(idx):
                    line = lines[idx]
                    score = 0
                    
                    # Prefer lines with extras like [async]
                    if '[' in line:
                        score += 100
                    
                    # Prefer exact versions (==) over constraints
                    if '==' in line:
                        score += 50
                    
                    # Prefer version constraints (>=) over no version
                    if '>=' in line or '<=' in line or '~=' in line:
                        score += 25
                    
                    # Prefer capitalized package names (more canonical)
                    pkg_name = re.split(r'[<>=~\[]', line)[0].strip()
                    if pkg_name[0].isupper():
                        score += 10
                    
                    # Prefer hyphenated names over underscore
                    if '-' in pkg_name and '_' not in pkg_name:
                        score += 5
                    
                    return score
                
                # Sort indices by preference score (higher is better)
                sorted_indices = sorted(indices, key=get_line_score, reverse=True)
                
                keep_idx = sorted_indices[0]
                for i in indices:
                    if i != keep_idx:
                        lines_to_keep.remove(i)
                        print(f"      Removing: {lines[i].strip()}")
                print(f"      Keeping: {lines[keep_idx].strip()}")
        
        if not duplicates_found:
            print("  No duplicates found!")
            return False
        
        # Write cleaned file
        clean_lines = [lines[i] for i in sorted(lines_to_keep)]
        
        # Remove consecutive empty lines
        result_lines = []
        prev_empty = False
        for line in clean_lines:
            is_empty = line.strip() == ""
            if is_empty and prev_empty:
                continue
            result_lines.append(line)
            prev_empty = is_empty
            
        # Write back to file
        with open("requirements.txt", 'w') as f:
            f.writelines(result_lines)
        
        print(f"  Removed {len(lines) - len(lines_to_keep)} duplicate entries.")
        return True
        
    except Exception as e:
        print(f"Error removing duplicates: {e}")
        return False

def main():
    """Main function to run the smart requirements generator."""
    print("Smart Requirements Generator")
    print("===========================")
    
    # Create backup
    if os.path.exists("requirements.txt"):
        print("Creating backup of current requirements.txt...")
        with open("requirements.txt", 'r') as src, open("requirements.txt.backup", 'w') as dst:
            dst.write(src.read())
    
    # Run pipreqs to get automatically detected packages
    detected_packages = run_pipreqs()
    print(f"Detected {len(detected_packages)} packages from imports in your code.")
    
    # Read current requirements.txt
    sections, comments, existing_versions, original_lines = read_current_requirements()
    
    # Merge pipreqs results with existing requirements
    updated_sections = merge_requirements(detected_packages, sections, existing_versions, original_lines)
    
    # Write the updated requirements.txt
    write_requirements(updated_sections)
    
    # Remove duplicates from the final file
    remove_duplicates()
    
    print("\nRequirements file updated successfully!")
    print("A backup of your original file was saved to requirements.txt.backup")

if __name__ == "__main__":
    main() 
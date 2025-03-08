# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
import importlib
import importlib.util
import subprocess
from pathlib import Path

# Make sure the app directory is in the path
project_root = os.path.abspath('../../..')
app_dir = os.path.join(project_root, 'app')
sys.path.insert(0, project_root)

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Beacon'
copyright = '2024, Beacon Team'
author = 'Beacon Team'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'myst_parser',
]

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']

# Custom CSS
html_css_files = [
    'custom.css',
]

# Furo theme options
html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "announcement": "This is the new modern documentation for Beacon.",
    "light_css_variables": {
        "color-brand-primary": "#0366d6",
        "color-brand-content": "#0366d6",
        "color-admonition-background": "#f5f7fa",
    },
    "dark_css_variables": {
        "color-brand-primary": "#58a6ff",
        "color-brand-content": "#58a6ff",
        "color-admonition-background": "#2d333b",
    },
}

# Pygments syntax highlight style
pygments_style = "friendly"
pygments_dark_style = "monokai"

# -- Autodoc configuration ----------------------------------------------------
autodoc_typehints = 'description'
autodoc_member_order = 'bysource'
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': True,
    'special-members': True,
    'show-inheritance': True,
}

# Napoleon settings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

# MyST Parser settings
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'myst',
}

myst_enable_extensions = [
    'colon_fence',
    'deflist',
    'tasklist',
    'fieldlist',
    'attrs_inline',
    'attrs_block',
    'html_image',
    'html_admonition',
    'substitution',
]

# Enable MyST to parse all Markdown files
myst_all_links_external = False
myst_heading_anchors = 3

# -- Preparation steps for the build process ---------------------------------

def setup_build_environment(_):
    """Set up the build environment by installing packages and generating resources."""
    # 1. Install required packages
    packages = [
        'myst-parser',
        'furo',
        'pillow',
    ]
    
    for package in packages:
        try:
            importlib.import_module(package.replace('-', '_'))
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    # 2. Generate placeholder images only if they don't already exist
    image_script = os.path.join(os.path.dirname(__file__), '_static', 'create_images.py')
    if os.path.exists(image_script):
        print("Checking for required placeholder images (won't overwrite existing)...")
        subprocess.check_call([sys.executable, image_script])
    else:
        print(f"Warning: Image generation script not found at {image_script}")

def setup(app):
    """Setup Sphinx extension and build environment."""
    app.connect('builder-inited', setup_build_environment)

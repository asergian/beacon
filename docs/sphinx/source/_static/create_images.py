#!/usr/bin/env python3
"""
Create placeholder images for Sphinx documentation.

This script creates simple placeholder images for the Sphinx documentation.
Run this script during the documentation build process to ensure all required
images are available.
"""

import os
import sys
from pathlib import Path

# Try to import PIL, install if not available
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess
    print("Installing Pillow (PIL)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw, ImageFont

def create_image(filename, width, height, bg_color, text, text_color=(255, 255, 255)):
    """Create a simple image with text."""
    # Skip creating the image if it already exists and has been recently modified
    # (assume it's our custom image)
    if os.path.exists(filename):
        file_age = os.path.getmtime(filename)
        script_age = os.path.getmtime(__file__)
        
        # If the image is newer than this script, don't overwrite it
        if file_age > script_age:
            print(f"Skipping image creation, using existing file: {filename}")
            return
    
    img = Image.new('RGB', (width, height), color=bg_color)
    d = ImageDraw.Draw(img)
    
    # Try to use a system font, fall back to default if not available
    try:
        font = ImageFont.truetype("Arial", 24)  # Adjust size as needed
    except IOError:
        font = ImageFont.load_default()
    
    # Calculate text position for center
    text_bbox = d.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2
    
    d.text((text_x, text_y), text, font=font, fill=text_color)
    
    img.save(filename)
    print(f"Created image: {filename}")

def main():
    """Create all required placeholder images."""
    # Get the directory where this script is located
    image_dir = Path(__file__).parent
    
    # Create beacon logo
    create_image(
        image_dir / "beacon_logo.png",
        width=400,
        height=200,
        bg_color=(20, 60, 100),
        text="Beacon Logo",
    )
    
    # Create email analysis flow diagram
    create_image(
        image_dir / "email_analysis_flow.png",
        width=800,
        height=400,
        bg_color=(60, 100, 20),
        text="Email Analysis Flow Diagram",
    )

if __name__ == "__main__":
    main() 
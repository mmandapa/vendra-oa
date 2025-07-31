#!/usr/bin/env python3
"""
File picker module for selecting PDF files using macOS Finder.
"""

import os
import subprocess
import sys
from typing import Optional


def open_file_picker(prompt: str = "Select a PDF file to upload") -> Optional[str]:
    """
    Open macOS Finder file picker and return the selected file path.
    
    Args:
        prompt: The prompt text to show in the file picker dialog
        
    Returns:
        The selected file path or None if cancelled
    """
    try:
        # AppleScript command to open file picker
        script = f'''
        tell application "System Events"
            set theFile to choose file with prompt "{prompt}" of type {{"PDF"}}
            return POSIX path of theFile
        end tell
        '''
        
        # Run AppleScript
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=True
        )
        
        file_path = result.stdout.strip()
        
        if file_path and os.path.exists(file_path):
            return file_path
        else:
            return None
            
    except subprocess.CalledProcessError:
        # User cancelled the file picker
        return None
    except Exception as e:
        print(f"Error opening file picker: {e}")
        return None


def validate_pdf_file(file_path: str) -> bool:
    """
    Validate that the file is a PDF and exists.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if valid PDF, False otherwise
    """
    if not file_path:
        return False
        
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
        
    if not file_path.lower().endswith('.pdf'):
        print("❌ File must be a PDF (.pdf extension)")
        return False
        
    return True


def get_pdf_via_picker() -> Optional[str]:
    """
    Open file picker and return a valid PDF file path.
    
    Returns:
        Valid PDF file path or None if cancelled/invalid
    """
    print("📁 Opening file picker...")
    file_path = open_file_picker("Select a PDF quote file to parse")
    
    if file_path:
        if validate_pdf_file(file_path):
            print(f"✅ Selected: {file_path}")
            return file_path
        else:
            print("❌ Invalid file selected. Please try again.")
            return None
    else:
        print("❌ No file selected.")
        return None


if __name__ == "__main__":
    # Test the file picker
    selected_file = get_pdf_via_picker()
    if selected_file:
        print(f"Successfully selected: {selected_file}")
    else:
        print("No file selected or invalid file.") 
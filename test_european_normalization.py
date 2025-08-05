#!/usr/bin/env python3
"""
Test European format normalization
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vendra_parser.ocr_parser import DynamicOCRParser

def test_european_normalization():
    print("=" * 80)
    print("TESTING EUROPEAN FORMAT NORMALIZATION")
    print("=" * 80)
    
    parser = DynamicOCRParser()
    
    test_cases = [
        "2.311,25",  # European format
        "2,311.25",  # US format
        "€2.311,25", # European with Euro symbol
        "$2,311.25", # US with dollar symbol
    ]
    
    print("🔍 TESTING NORMALIZATION:")
    print("-" * 50)
    
    for test_case in test_cases:
        result = parser.normalize_price(test_case)
        print(f"'{test_case}' -> '{result}'")

if __name__ == "__main__":
    test_european_normalization() 
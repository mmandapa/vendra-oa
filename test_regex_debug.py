#!/usr/bin/env python3
"""
Debug the regex pattern for European format
"""

import re

def test_regex_debug():
    print("=" * 80)
    print("DEBUGGING REGEX FOR EUROPEAN FORMAT")
    print("=" * 80)
    
    # Test the current regex pattern
    pattern = r'^subtotal\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)'
    
    test_cases = [
        "SUBTOTAL €2.311,25",
        "SUBTOTAL $2,311.25",
        "SUBTOTAL 2.311,25",
        "SUBTOTAL 2,311.25",
    ]
    
    print("🔍 TESTING REGEX PATTERN:")
    print("-" * 50)
    
    for test_case in test_cases:
        match = re.match(pattern, test_case, re.IGNORECASE)
        if match:
            captured = match.group(1)
            print(f"✅ '{test_case}' -> captured: '{captured}'")
            
            # Test what happens when this goes through normalize_price
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
            from vendra_parser.ocr_parser import DynamicOCRParser
            
            parser = DynamicOCRParser()
            normalized = parser.normalize_price(captured)
            print(f"   Normalized: '{captured}' -> '{normalized}'")
        else:
            print(f"❌ '{test_case}' -> no match")

if __name__ == "__main__":
    test_regex_debug() 
#!/usr/bin/env python3
"""
Test European format regex matching
"""

import re

def test_european_regex():
    print("=" * 80)
    print("TESTING EUROPEAN FORMAT REGEX")
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
        else:
            print(f"❌ '{test_case}' -> no match")
    
    # Test improved pattern for European format
    print("\n🔍 TESTING IMPROVED EUROPEAN PATTERN:")
    print("-" * 50)
    
    # Improved pattern that better handles European format
    improved_pattern = r'^subtotal\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)'
    
    for test_case in test_cases:
        match = re.match(improved_pattern, test_case, re.IGNORECASE)
        if match:
            captured = match.group(1)
            print(f"✅ '{test_case}' -> captured: '{captured}'")
        else:
            print(f"❌ '{test_case}' -> no match")

if __name__ == "__main__":
    test_european_regex() 
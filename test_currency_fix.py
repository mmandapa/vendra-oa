#!/usr/bin/env python3
"""
Test the currency detection fix
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vendra_parser.ocr_parser import DynamicOCRParser

def test_currency_fix():
    print("=" * 80)
    print("TESTING CURRENCY DETECTION FIX")
    print("=" * 80)
    
    parser = DynamicOCRParser()
    
    # Test cases that were failing
    test_cases = [
        # USD cases (should work normally)
        ("$100.00", "100.00"),
        ("$1,234.56", "1234.56"),
        ("$1,234", "1234.00"),
        ("100.00", "100.00"),  # No currency symbol
        ("1,234.56", "1234.56"),  # No currency symbol
        
        # EUR cases (should work with European format)
        ("€100,00", "100.00"),
        ("€1 234,56", "1234.56"),
        ("EUR 100,00", "100.00"),
        
        # GBP cases
        ("£100.00", "100.00"),
        ("GBP 100.00", "100.00"),
        
        # JPY cases
        ("¥10,000", "10000.00"),
        ("JPY 10,000", "10000.00"),
        
        # Problematic cases from the logs
        ("14 287.40", "14287.40"),  # This was causing the error
        ("2.31125", "2.31"),
        
        # Additional test cases for format inference
        ("1 234,56", "1234.56"),  # European format without currency symbol
        ("1 234.56", "1234.56"),  # USD with space thousands separator
        ("1234.56", "1234.56"),   # Standard USD format
    ]
    
    print("🔍 TESTING CURRENCY NORMALIZATION:")
    print("-" * 50)
    
    passed = 0
    failed = 0
    
    for input_price, expected in test_cases:
        result = parser.normalize_price(input_price)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_price:20} -> {result:15} (expected: {expected})")
        
        if result == expected:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 RESULTS: {passed} passed, {failed} failed")
    return passed, failed

if __name__ == "__main__":
    test_currency_fix() 
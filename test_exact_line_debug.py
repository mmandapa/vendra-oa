#!/usr/bin/env python3
"""
Debug the exact line from the PDF
"""

import re

def test_exact_line_debug():
    print("=" * 80)
    print("DEBUGGING EXACT LINE FROM PDF")
    print("=" * 80)
    
    # The exact line from the debug output
    exact_line = "SUBTOTAL €2.311,25"
    
    print(f"🔍 EXACT LINE: '{exact_line}'")
    print(f"🔍 LENGTH: {len(exact_line)}")
    print(f"🔍 BYTES: {exact_line.encode('utf-8')}")
    print("-" * 50)
    
    # Test the current regex pattern
    pattern = r'^subtotal\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)'
    
    match = re.match(pattern, exact_line, re.IGNORECASE)
    if match:
        captured = match.group(1)
        print(f"✅ MATCH: captured '{captured}'")
        
        # Test what happens when this goes through normalize_price
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from vendra_parser.ocr_parser import DynamicOCRParser
        
        parser = DynamicOCRParser()
        normalized = parser.normalize_price(captured)
        print(f"   Normalized: '{captured}' -> '{normalized}'")
    else:
        print(f"❌ NO MATCH")
        
        # Try different patterns
        print("\n🔍 TRYING DIFFERENT PATTERNS:")
        patterns = [
            r'^subtotal\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)',
            r'^subtotal\s*.*?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)',
            r'^subtotal.*?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)',
            r'(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)',
        ]
        
        for i, pattern in enumerate(patterns, 1):
            match = re.search(pattern, exact_line, re.IGNORECASE)
            if match:
                captured = match.group(1)
                print(f"   Pattern {i}: captured '{captured}'")
            else:
                print(f"   Pattern {i}: no match")

if __name__ == "__main__":
    test_exact_line_debug() 
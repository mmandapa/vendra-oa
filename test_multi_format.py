#!/usr/bin/env python3
"""
Test to compare the old OCR parser with the new multi-format parser
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vendra_parser.ocr_parser import DynamicOCRParser
from vendra_parser.multi_format_parser import MultiFormatPDFParser

def test_parser_comparison():
    print("=" * 80)
    print("COMPARING OLD OCR PARSER vs NEW MULTI-FORMAT PARSER")
    print("=" * 80)
    
    test_pdfs = [
        "/Users/maharshi12/Downloads/Quote-Template_Word.pdf",
        "/Users/maharshi12/Downloads/Quote-Template-2-Word.pdf",
        "/Users/maharshi12/Downloads/VendraSampleQuote-01.pdf",
    ]
    
    for pdf_path in test_pdfs:
        print(f"\n📄 Testing: {os.path.basename(pdf_path)}")
        print("-" * 60)
        
        # Test old OCR parser
        try:
            print("🔧 OLD OCR PARSER:")
            old_parser = DynamicOCRParser()
            old_result = old_parser.parse_quote(pdf_path)
            old_items = sum(len(group.get('lineItems', [])) for group in old_result.get('groups', []))
            old_total = old_result.get('summary', {}).get('totalCost', '0')
            print(f"   Line items found: {old_items}")
            print(f"   Total cost: ${old_total}")
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
        
        # Test new multi-format parser
        try:
            print("🚀 NEW MULTI-FORMAT PARSER:")
            new_parser = MultiFormatPDFParser()
            new_result = new_parser.parse_quote(pdf_path)
            new_items = sum(len(group.get('lineItems', [])) for group in new_result.get('groups', []))
            new_total = new_result.get('summary', {}).get('totalCost', '0')
            print(f"   Line items found: {new_items}")
            print(f"   Total cost: ${new_total}")
            
            # Show improvement
            if old_items > 0 and new_items > 0:
                improvement = ((new_items - old_items) / old_items) * 100
                print(f"   📈 Improvement: {improvement:+.1f}% more items")
            elif new_items > old_items:
                print(f"   ✅ New parser found {new_items} items vs {old_items}")
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")

if __name__ == "__main__":
    test_parser_comparison() 
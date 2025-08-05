#!/usr/bin/env python3
"""
Debug script to see what's happening with Quote-Template-2-Word.pdf
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vendra_parser.ocr_parser import DynamicOCRParser

def debug_quote_2():
    print("=" * 80)
    print("DEBUGGING QUOTE-TEMPLATE-2-WORD.PDF")
    print("=" * 80)
    
    pdf_path = "/Users/maharshi12/Downloads/Quote-Template-2-Word.pdf"
    parser = DynamicOCRParser()
    
    # Extract text
    text = parser.extract_text_with_ocr(pdf_path)
    print("📄 EXTRACTED TEXT:")
    print("-" * 50)
    print(text)
    print("-" * 50)
    
    # Extract summary adjustments
    adjustments = parser.extract_summary_adjustments(text)
    print(f"\n📋 SUMMARY ADJUSTMENTS FOUND: {len(adjustments)}")
    for i, adj in enumerate(adjustments, 1):
        print(f"  {i}. {adj['type']}: {adj['value']} ({adj['raw_text']})")
    
    # Extract line items
    line_items = parser.discover_line_items_dynamically(text)
    print(f"\n📋 LINE ITEMS FOUND: {len(line_items)}")
    for i, item in enumerate(line_items, 1):
        print(f"  {i}. {item.description} | Qty: {item.quantity} | Price: {item.unit_price} | Cost: {item.cost}")

if __name__ == "__main__":
    debug_quote_2() 
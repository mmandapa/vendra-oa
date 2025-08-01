#!/usr/bin/env python3
"""
Simple PDF Quote Parser
A user-friendly script to parse supplier quote PDFs.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vendra_parser import OCRParser, DynamicOCRParser


def main():
    """Main function for PDF parsing."""
    print("🎯 VENDRA QUOTE PARSER")
    print("=" * 50)
    print("This tool extracts structured quote data from supplier PDFs.")
    print("It will help you parse pricing, quantities, and line items.")
    print("=" * 50)
    
    try:
        # Get PDF file path
        while True:
            pdf_path = input("\n📄 Please enter the path to your PDF quote file: ").strip()
            
            if not pdf_path:
                print("❌ No file path provided. Please try again.")
                continue
                
            # Remove quotes if user added them
            pdf_path = pdf_path.strip('"\'')
            
            if not os.path.exists(pdf_path):
                print(f"❌ File not found: {pdf_path}")
                print("Please check the file path and try again.")
                continue
                
            if not pdf_path.lower().endswith('.pdf'):
                print("❌ File must be a PDF (.pdf extension)")
                continue
                
            break
        
        # Using OCR Parser (only available parser)
        parser_type = "ocr"
        print("\n🔧 Using OCR Parser (dynamic PDF parsing with OCR capabilities)")
        
        # Get output preference
        while True:
            choice = input("\n💾 How would you like to save the results?\n"
                          "1. Print to terminal only\n"
                          "2. Save to JSON file\n"
                          "3. Both\n"
                          "Enter your choice (1-3): ").strip()
            
            if choice == "1":
                output_file = None
                break
            elif choice == "2":
                filename = input("Enter JSON filename (or press Enter for 'quote_result.json'): ").strip()
                output_file = filename if filename else "quote_result.json"
                break
            elif choice == "3":
                filename = input("Enter JSON filename (or press Enter for 'quote_result.json'): ").strip()
                output_file = filename if filename else "quote_result.json"
                break
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
        
        # Parse the quote
        print(f"\n🔄 Parsing PDF: {pdf_path}")
        print(f"📊 Using OCR Parser...")
        
        parser = DynamicOCRParser()
        
        # Parse and get results
        result = parser.parse_quote_to_json(pdf_path, output_file)
        
        # Display results
        print("\n✅ Parsing completed successfully!")
        print("=" * 50)
        
        if output_file is None or choice == "3":
            print("\n📋 PARSED RESULTS:")
            print(result)
        
        if output_file:
            print(f"\n💾 Results saved to: {output_file}")
        
        # Show summary
        try:
            parsed_data = json.loads(result) if isinstance(result, str) else result
            print(f"\n📈 SUMMARY:")
            print(f"   • Found {len(parsed_data)} quote group(s)")
            for i, group in enumerate(parsed_data, 1):
                print(f"   • Group {i}: Qty {group['quantity']}, "
                      f"Unit Price ${group['unitPrice']}, "
                      f"Total ${group['totalPrice']}")
                print(f"     Line items: {len(group['lineItems'])}")
        
        except Exception as e:
            print(f"⚠️  Could not display summary: {e}")
        
        print("\n🎉 Thank you for using Vendra Quote Parser!")
        
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please check your PDF file and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main() 
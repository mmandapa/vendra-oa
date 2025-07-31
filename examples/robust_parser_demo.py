#!/usr/bin/env python3
"""
Demonstration of the Robust OCR Parser with enhanced accuracy and validation strategies.
This script showcases all 6 OCR improvement strategies implemented in the robust parser.
"""

import sys
import os
import json
import logging
from pathlib import Path

# Add the src directory to the path so we can import the vendra_parser module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendra_parser.robust_parser import RobustQuoteParser
from vendra_parser.robust_ocr import RobustOCREngine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def demonstrate_ocr_preprocessing():
    """Demonstrate Strategy 1: OCR Preprocessing & Configuration"""
    print("\n" + "="*60)
    print("STRATEGY 1: OCR Preprocessing & Configuration")
    print("="*60)
    
    print("This strategy enhances image quality before OCR processing:")
    print("• Converts to grayscale")
    print("• Increases contrast using CLAHE")
    print("• Applies denoising")
    print("• Sharpens the image")
    print("• Binarizes to black and white")
    print("• Uses multiple PSM modes for different content types")
    
    # Note: This would require an actual image file to demonstrate
    print("\nNote: Image preprocessing requires OpenCV and an actual image file.")
    print("The robust parser automatically applies this preprocessing when available.")


def demonstrate_multi_engine_ocr():
    """Demonstrate Strategy 2: Multiple OCR Engine Approach"""
    print("\n" + "="*60)
    print("STRATEGY 2: Multiple OCR Engine Approach")
    print("="*60)
    
    print("This strategy tries multiple OCR engines and compares results:")
    print("• Tesseract (primary engine)")
    print("• Tesseract with preprocessing")
    print("• EasyOCR (if available)")
    print("• PaddleOCR (if available)")
    
    # Initialize the OCR engine to show available engines
    engine = RobustOCREngine()
    print(f"\nAvailable OCR engines: {engine.ocr_engines}")
    
    print("\nThe robust parser automatically selects the best result based on:")
    print("• Text length")
    print("• Confidence scores")
    print("• Pattern validation")


def demonstrate_ocr_validation():
    """Demonstrate Strategy 3: OCR Result Validation"""
    print("\n" + "="*60)
    print("STRATEGY 3: OCR Result Validation")
    print("="*60)
    
    print("This strategy validates OCR extracted numbers:")
    print("• Checks for unrealistic values (>$1M)")
    print("• Flags prices missing decimals")
    print("• Validates number formats")
    print("• Checks for expected patterns")
    
    # Example validation
    sample_text = "BASE 6 240.92 1445.52 SOLDER 6 213.42 1280.52 TOOLING 1 2000 2000"
    engine = RobustOCREngine()
    issues = engine.validate_ocr_numbers(sample_text)
    
    print(f"\nSample validation of text: '{sample_text}'")
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("No validation issues found")


def demonstrate_error_correction():
    """Demonstrate Strategy 4: Smart Error Correction"""
    print("\n" + "="*60)
    print("STRATEGY 4: Smart Error Correction")
    print("="*60)
    
    print("This strategy fixes common OCR character recognition errors:")
    print("• O → 0 (letter O to zero)")
    print("• l → 1 (lowercase L to one)")
    print("• I → 1 (capital I to one)")
    print("• S → 5 (letter S to five)")
    print("• G → 6 (letter G to six)")
    print("• Fixes decimal point issues")
    
    # Example corrections
    engine = RobustOCREngine()
    sample_errors = [
        "BASE 6 24O.92 1445.52",  # O instead of 0
        "SOLDER 6 2l3.42 1280.52",  # l instead of 1
        "TOOLING 1 2000 2000",  # No errors
        "123 45 becomes 123.45",  # Decimal point issue
    ]
    
    print("\nExample error corrections:")
    for text in sample_errors:
        corrected = engine.correct_common_ocr_errors(text)
        print(f"  Original: {text}")
        print(f"  Corrected: {corrected}")
        print()


def demonstrate_confidence_parsing():
    """Demonstrate Strategy 5: Confidence-Based Parsing"""
    print("\n" + "="*60)
    print("STRATEGY 5: Confidence-Based Parsing")
    print("="*60)
    
    print("This strategy uses confidence scores to determine reliability:")
    print("• Extracts text with confidence scores")
    print("• Separates high-confidence from low-confidence text")
    print("• Flags results that need manual review")
    print("• Uses multiple fallback strategies")
    
    print("\nConfidence thresholds:")
    print("• High confidence: >70% (trusted)")
    print("• Low confidence: <70% (flagged for review)")
    print("• Manual review: When OCR fails or confidence is too low")


def demonstrate_pattern_validation():
    """Demonstrate Strategy 6: Pattern-Based Validation"""
    print("\n" + "="*60)
    print("STRATEGY 6: Pattern-Based Validation")
    print("="*60)
    
    print("This strategy validates extracted data against expected patterns:")
    print("• Checks for presence of quantities")
    print("• Validates price formats")
    print("• Ensures total keywords are present")
    print("• Verifies reasonable document structure")
    
    # Example validation
    engine = RobustOCREngine()
    sample_texts = [
        "BASE 6 240.92 1445.52 SOLDER 6 213.42 1280.52 TOOLING 1 2000 2000",  # Good
        "Just some random text without numbers",  # Bad
        "Phone: 555-1234 Address: 123 Main St",  # Bad (no pricing)
    ]
    
    print("\nExample pattern validation:")
    for text in sample_texts:
        validation = engine.validate_against_expected_patterns(text)
        print(f"\nText: '{text[:50]}...'")
        print(f"Validation: {validation['validations']}")
        print(f"Confidence: {validation['confidence']:.2f}")
        print(f"Needs review: {validation['needs_manual_review']}")


def demonstrate_robust_parsing():
    """Demonstrate the complete robust parsing workflow"""
    print("\n" + "="*60)
    print("COMPLETE ROBUST PARSING WORKFLOW")
    print("="*60)
    
    print("The robust parser combines all 6 strategies:")
    print("1. OCR Preprocessing & Configuration")
    print("2. Multiple OCR Engine Approach")
    print("3. OCR Result Validation")
    print("4. Smart Error Correction")
    print("5. Confidence-Based Parsing")
    print("6. Pattern-Based Validation")
    
    print("\nAdditional features:")
    print("• Cross-validation of quantities and prices")
    print("• Smart quantity and price corrections")
    print("• Math validation (qty × price = total)")
    print("• Comprehensive error reporting")
    print("• Manual review flagging")
    
    print("\nUsage example:")
    print("```python")
    print("from vendra_parser.robust_parser import RobustQuoteParser")
    print("")
    print("parser = RobustQuoteParser()")
    print("result = parser.parse_quote('path/to/quote.pdf')")
    print("")
    print("# Check if manual review is needed")
    print("if result['validation']['needs_manual_review']:")
    print("    print('Manual review recommended')")
    print("    print('Issues:', result['validation']['issues'])")
    print("")
    print("# Access parsed data")
    print("quote_groups = result['quote_groups']")
    print("line_items = result['line_items']")
    print("```")


def main():
    """Main demonstration function"""
    print("🚀 ROBUST OCR PARSER DEMONSTRATION")
    print("="*60)
    print("This demonstration showcases the enhanced OCR accuracy and")
    print("validation strategies implemented in the Vendra Quote Parser.")
    print("="*60)
    
    # Demonstrate each strategy
    demonstrate_ocr_preprocessing()
    demonstrate_multi_engine_ocr()
    demonstrate_ocr_validation()
    demonstrate_error_correction()
    demonstrate_confidence_parsing()
    demonstrate_pattern_validation()
    demonstrate_robust_parsing()
    
    print("\n" + "="*60)
    print("INSTALLATION INSTRUCTIONS")
    print("="*60)
    print("To use the robust OCR parser, install the required dependencies:")
    print("")
    print("pip install opencv-python pytesseract Pillow")
    print("")
    print("Optional OCR engines (for enhanced accuracy):")
    print("pip install easyocr paddlepaddle paddleocr")
    print("")
    print("System requirements:")
    print("• Tesseract OCR engine (install via package manager)")
    print("• pdftoppm (usually comes with poppler)")
    print("")
    print("Usage:")
    print("• CLI: vendra-parser parse-robust path/to/quote.pdf")
    print("• Python: from vendra_parser.robust_parser import RobustQuoteParser")
    print("="*60)
    
    print("\n🎉 Demonstration completed!")
    print("The robust parser is now ready to handle challenging PDFs with")
    print("enhanced accuracy, validation, and error correction.")


if __name__ == "__main__":
    main() 
#!/usr/bin/env python3
"""
Test script for the Vendra Quote Parser
Demonstrates the parser functionality with sample data.
"""

import json
import tempfile
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendra_parser import QuoteParser, AdvancedQuoteParser


def create_sample_pdf_content():
    """Create sample PDF content for testing."""
    sample_content = """
    SUPPLIER QUOTE
    
    Quantity: 12 units
    
    LINE ITEMS:
    BASE        6    240.92    1445.52
    SOLDER      6    213.42    1280.52
    TOOLING     1    2000.00   2000.00
    
    Total Price: $3926.04
    Unit Price: $455.00
    
    ---
    
    Alternative Quote:
    Quantity: 1, 3, 5
    
    Qty 1: $600.00
    Qty 3: $500.00 each
    Qty 5: $455.00 each
    """
    return sample_content


def test_basic_parser():
    """Test the basic quote parser."""
    print("Testing Basic Quote Parser...")
    
    # Create a temporary text file to simulate PDF content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(create_sample_pdf_content())
        temp_file = f.name
    
    try:
        parser = QuoteParser()
        
        # Test with the sample content by directly calling the parsing methods
        text = create_sample_pdf_content()
        
        # Extract quantities
        quantities = parser.extract_quantities(text)
        print(f"Found quantities: {quantities}")
        
        # Extract line items
        line_items = parser.extract_line_items(text)
        print(f"Found {len(line_items)} line items")
        
        # Create result structure manually
        result = []
        for quantity in quantities:
            total_price = parser.calculate_total_price(line_items)
            unit_price = parser.calculate_unit_price(total_price, quantity)
            
            group_dict = {
                "quantity": quantity,
                "unitPrice": unit_price,
                "totalPrice": total_price,
                "lineItems": [
                    {
                        "description": item.description,
                        "quantity": item.quantity,
                        "unitPrice": item.unit_price,
                        "cost": item.cost
                    }
                    for item in line_items
                ]
            }
            result.append(group_dict)
        
        print("Basic Parser Result:")
        print(json.dumps(result, indent=2))
        
        return result
        
    finally:
        # Clean up
        os.unlink(temp_file)


def test_advanced_parser():
    """Test the advanced quote parser."""
    print("\nTesting Advanced Quote Parser...")
    
    # Create a temporary text file to simulate PDF content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(create_sample_pdf_content())
        temp_file = f.name
    
    try:
        parser = AdvancedQuoteParser()
        
        # Test with the sample content by directly calling the parsing methods
        text = create_sample_pdf_content()
        
        # Extract quantities
        quantities = parser.extract_quantities(text)
        print(f"Found quantities: {quantities}")
        
        # Extract line items
        line_items = parser.extract_line_items(text)
        print(f"Found {len(line_items)} line items")
        
        # Create result structure manually
        result = []
        for quantity in quantities:
            total_price = parser.calculate_total_price(line_items)
            unit_price = parser.calculate_unit_price(total_price, quantity)
            
            group_dict = {
                "quantity": quantity,
                "unitPrice": unit_price,
                "totalPrice": total_price,
                "lineItems": [
                    {
                        "description": item.description,
                        "quantity": item.quantity,
                        "unitPrice": item.unit_price,
                        "cost": item.cost
                    }
                    for item in line_items
                ]
            }
            result.append(group_dict)
        
        print("Advanced Parser Result:")
        print(json.dumps(result, indent=2))
        
        return result
        
    finally:
        # Clean up
        os.unlink(temp_file)


def test_price_normalization():
    """Test price normalization functionality."""
    print("\nTesting Price Normalization...")
    
    parser = QuoteParser()
    
    test_prices = [
        "$1,234.56",
        "1234.56",
        "$1,234",
        "1,234 USD",
        "€1,234.56",
        "invalid",
        ""
    ]
    
    for price in test_prices:
        normalized = parser.normalize_price(price)
        print(f"'{price}' -> '{normalized}'")


def test_quantity_extraction():
    """Test quantity extraction functionality."""
    print("\nTesting Quantity Extraction...")
    
    parser = QuoteParser()
    
    test_texts = [
        "Quantity: 12 units",
        "Qty: 1, 3, 5",
        "Quote for 100 pieces",
        "5 ea",
        "No quantities here",
    ]
    
    for text in test_texts:
        quantities = parser.extract_quantities(text)
        print(f"'{text}' -> {quantities}")


def main():
    """Run all tests."""
    print("Vendra Quote Parser - Test Suite")
    print("=" * 50)
    
    # Test price normalization
    test_price_normalization()
    
    # Test quantity extraction
    test_quantity_extraction()
    
    # Test basic parser
    basic_result = test_basic_parser()
    
    # Test advanced parser
    advanced_result = test_advanced_parser()
    
    # Compare results
    print("\n" + "=" * 50)
    print("Comparison:")
    print(f"Basic parser found {len(basic_result)} quote groups")
    print(f"Advanced parser found {len(advanced_result)} quote groups")
    
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main() 
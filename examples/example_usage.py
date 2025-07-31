#!/usr/bin/env python3
"""
Example usage of the Vendra Quote Parser
Demonstrates how to use the parser with sample data.
"""

import json
import tempfile
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendra_parser import QuoteParser, AdvancedQuoteParser


def create_sample_quote_text():
    """Create sample quote text for demonstration."""
    return """
    SUPPLIER QUOTE - ACME MANUFACTURING
    
    Quote Date: 2025-01-15
    Quote Number: Q-2025-001
    
    PART: Custom PCB Assembly
    DESCRIPTION: 4-layer PCB with SMT components
    
    QUANTITY BREAKDOWN:
    Qty 1:  $600.00 per unit
    Qty 3:  $500.00 per unit  
    Qty 5:  $455.00 per unit
    Qty 12: $392.04 per unit
    
    DETAILED BREAKDOWN (Qty 12):
    
    LINE ITEM          QTY    UNIT PRICE    TOTAL COST
    -------------------------------------------------
    BASE MATERIAL      6      $240.92       $1,445.52
    SOLDER ASSEMBLY    6      $213.42       $1,280.52
    TOOLING SETUP      1      $2,000.00     $2,000.00
    -------------------------------------------------
    SUBTOTAL:                                    $4,726.04
    DISCOUNT (15%):                              -$708.91
    TOTAL:                                        $4,017.13
    
    TERMS: Net 30
    DELIVERY: 4-6 weeks
    
    Contact: sales@acmemanufacturing.com
    Phone: (555) 123-4567
    """


def demonstrate_basic_parser():
    """Demonstrate the basic quote parser."""
    print("=" * 60)
    print("DEMONSTRATION: Basic Quote Parser")
    print("=" * 60)
    
    # Create temporary file with sample quote
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(create_sample_quote_text())
        temp_file = f.name
    
    try:
        # Initialize parser
        parser = QuoteParser()
        
        # Parse the quote by directly calling the parsing methods
        text = create_sample_quote_text()
        
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
        
        # Display results
        print("Parsed Quote Data:")
        print(json.dumps(result, indent=2))
        
        # Save to JSON file
        output_file = "sample_quote_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        
    finally:
        # Clean up
        os.unlink(temp_file)


def demonstrate_advanced_parser():
    """Demonstrate the advanced quote parser."""
    print("\n" + "=" * 60)
    print("DEMONSTRATION: Advanced Quote Parser")
    print("=" * 60)
    
    # Create temporary file with sample quote
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(create_sample_quote_text())
        temp_file = f.name
    
    try:
        # Initialize advanced parser
        parser = AdvancedQuoteParser()
        
        # Parse the quote by directly calling the parsing methods
        text = create_sample_quote_text()
        
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
        
        # Display results
        print("Parsed Quote Data (Advanced Parser):")
        print(json.dumps(result, indent=2))
        
        # Save to JSON file
        output_file = "sample_quote_advanced_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        
    finally:
        # Clean up
        os.unlink(temp_file)


def demonstrate_cli_usage():
    """Demonstrate CLI usage."""
    print("\n" + "=" * 60)
    print("DEMONSTRATION: CLI Usage")
    print("=" * 60)
    
    # Create temporary file with sample quote
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(create_sample_quote_text())
        temp_file = f.name
    
    try:
        print("CLI Commands to try:")
        print(f"1. Basic parser: python -m vendra_parser.cli parse {temp_file}")
        print(f"2. Save to file: python -m vendra_parser.cli parse {temp_file} --output result.json")
        print(f"3. Verbose mode: python -m vendra_parser.cli parse {temp_file} --verbose")
        print(f"4. Advanced parser: python -m vendra_parser.cli parse-advanced {temp_file}")
        
        print(f"\nSample file created at: {temp_file}")
        print("You can run the CLI commands above to test the parser.")
        
    except Exception as e:
        print(f"Error: {e}")


def analyze_results():
    """Analyze and compare parser results."""
    print("\n" + "=" * 60)
    print("RESULT ANALYSIS")
    print("=" * 60)
    
    # Check if result files exist
    basic_file = "sample_quote_result.json"
    advanced_file = "sample_quote_advanced_result.json"
    
    if os.path.exists(basic_file):
        with open(basic_file, 'r') as f:
            basic_result = json.load(f)
        print(f"Basic parser found {len(basic_result)} quote group(s)")
        
        for i, group in enumerate(basic_result):
            print(f"  Group {i+1}: Qty {group['quantity']}, "
                  f"Unit Price ${group['unitPrice']}, "
                  f"Total ${group['totalPrice']}")
            print(f"    Line items: {len(group['lineItems'])}")
    
    if os.path.exists(advanced_file):
        with open(advanced_file, 'r') as f:
            advanced_result = json.load(f)
        print(f"\nAdvanced parser found {len(advanced_result)} quote group(s)")
        
        for i, group in enumerate(advanced_result):
            print(f"  Group {i+1}: Qty {group['quantity']}, "
                  f"Unit Price ${group['unitPrice']}, "
                  f"Total ${group['totalPrice']}")
            print(f"    Line items: {len(group['lineItems'])}")


def main():
    """Run all demonstrations."""
    print("VENDRA QUOTE PARSER - EXAMPLE USAGE")
    print("This script demonstrates the quote parser functionality.")
    
    # Demonstrate basic parser
    demonstrate_basic_parser()
    
    # Demonstrate advanced parser
    demonstrate_advanced_parser()
    
    # Demonstrate CLI usage
    demonstrate_cli_usage()
    
    # Analyze results
    analyze_results()
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("Check the generated JSON files to see the parsed results.")
    print("You can also run the CLI commands shown above to test the parser.")


if __name__ == "__main__":
    main() 
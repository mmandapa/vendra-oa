#!/usr/bin/env python3
"""
Enhanced Table Parser Demo
Demonstrates the enhanced table parser's ability to handle grouped quotes
and varied PDF formats using pdfplumber's table extraction capabilities.
"""

import sys
import os
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendra_parser.enhanced_table_parser import parse_quote_tables, EnhancedTableParser


def create_sample_table_data():
    """Create sample table data to demonstrate the parser's capabilities."""
    
    # Sample 1: Simple grouped quotes
    sample1 = [
        ["Description", "Qty", "Unit Price", "Total"],
        ["BASE MATERIAL", "5", "$240.92", "$1,204.60"],
        ["SOLDER ASSEMBLY", "5", "$213.42", "$1,067.10"],
        ["TOOLING SETUP", "1", "$2,000.00", "$2,000.00"],
        ["", "", "", ""],
        ["Description", "Qty", "Unit Price", "Total"],
        ["BASE MATERIAL", "10", "$220.00", "$2,200.00"],
        ["SOLDER ASSEMBLY", "10", "$200.00", "$2,000.00"],
        ["TOOLING SETUP", "1", "$2,000.00", "$2,000.00"],
    ]
    
    # Sample 2: Complex table with multiple quantity groups
    sample2 = [
        ["Item", "Qty 1", "Qty 3", "Qty 5", "Qty 10"],
        ["BASE MATERIAL", "$600.00", "$500.00", "$455.00", "$400.00"],
        ["SOLDER ASSEMBLY", "$150.00", "$140.00", "$130.00", "$120.00"],
        ["TOOLING SETUP", "$2,000.00", "$2,000.00", "$2,000.00", "$2,000.00"],
        ["PACKAGING", "$50.00", "$45.00", "$40.00", "$35.00"],
    ]
    
    # Sample 3: Unstructured table data
    sample3 = [
        ["Quote for 5 units:"],
        ["BASE MATERIAL", "5", "240.92", "1204.60"],
        ["SOLDER ASSEMBLY", "5", "213.42", "1067.10"],
        ["TOOLING SETUP", "1", "2000.00", "2000.00"],
        ["", "", "", ""],
        ["Quote for 12 units:"],
        ["BASE MATERIAL", "12", "220.00", "2640.00"],
        ["SOLDER ASSEMBLY", "12", "200.00", "2400.00"],
        ["TOOLING SETUP", "1", "2000.00", "2000.00"],
    ]
    
    return [sample1, sample2, sample3]


def demonstrate_table_analysis():
    """Demonstrate table structure analysis capabilities."""
    print("🔍 TABLE STRUCTURE ANALYSIS DEMO")
    print("=" * 50)
    
    parser = EnhancedTableParser()
    samples = create_sample_table_data()
    
    for i, sample in enumerate(samples, 1):
        print(f"\n📊 Sample Table {i}:")
        print("-" * 30)
        
        # Analyze table structure
        analysis = parser._analyze_table_structure(sample)
        
        print(f"• Is Quote Table: {analysis['is_quote_table']}")
        print(f"• Has Prices: {analysis['has_prices']}")
        print(f"• Has Quantities: {analysis['has_quantities']}")
        print(f"• Has Line Items: {analysis['has_line_items']}")
        print(f"• Max Columns: {analysis['max_columns']}")
        print(f"• Total Rows: {analysis['total_rows']}")
        
        if analysis['is_quote_table']:
            # Extract quantities
            quantities = parser._identify_quantities_from_table(sample)
            print(f"• Identified Quantities: {quantities}")
            
            # Extract line items
            line_items = parser._extract_line_items_from_table(sample)
            print(f"• Extracted Line Items: {len(line_items)}")
            for item in line_items[:3]:  # Show first 3
                print(f"  - {item.description}: {item.quantity} x ${item.unit_price} = ${item.cost}")


def demonstrate_quantity_detection():
    """Demonstrate quantity detection capabilities."""
    print("\n🔢 QUANTITY DETECTION DEMO")
    print("=" * 50)
    
    parser = EnhancedTableParser()
    samples = create_sample_table_data()
    
    for i, sample in enumerate(samples, 1):
        print(f"\n📊 Sample {i} Quantities:")
        print("-" * 30)
        
        quantities = parser._identify_quantities_from_table(sample)
        print(f"Detected quantities: {quantities}")
        
        # Show how quantities are found in the table
        for row in sample:
            if row:
                row_text = ' '.join(row)
                for qty in quantities:
                    if qty in row_text:
                        print(f"  Found quantity {qty} in: {row_text[:50]}...")


def demonstrate_line_item_extraction():
    """Demonstrate line item extraction capabilities."""
    print("\n📋 LINE ITEM EXTRACTION DEMO")
    print("=" * 50)
    
    parser = EnhancedTableParser()
    samples = create_sample_table_data()
    
    for i, sample in enumerate(samples, 1):
        print(f"\n📊 Sample {i} Line Items:")
        print("-" * 30)
        
        line_items = parser._extract_line_items_from_table(sample)
        
        if line_items:
            for j, item in enumerate(line_items, 1):
                print(f"{j}. {item.description}")
                print(f"   Quantity: {item.quantity}")
                print(f"   Unit Price: ${item.unit_price}")
                print(f"   Total Cost: ${item.cost}")
                print()
        else:
            print("No line items extracted")


def demonstrate_quote_group_creation():
    """Demonstrate quote group creation capabilities."""
    print("\n💰 QUOTE GROUP CREATION DEMO")
    print("=" * 50)
    
    parser = EnhancedTableParser()
    samples = create_sample_table_data()
    
    for i, sample in enumerate(samples, 1):
        print(f"\n📊 Sample {i} Quote Groups:")
        print("-" * 30)
        
        # Analyze table and extract quote groups
        analysis = parser._analyze_table_structure(sample)
        if analysis['is_quote_table']:
            quote_groups = parser._extract_quote_groups_from_table(sample, analysis)
            
            for j, group in enumerate(quote_groups, 1):
                print(f"Quote Group {j}:")
                print(f"  Quantity: {group['quantity']}")
                print(f"  Unit Price: ${group['unitPrice']}")
                print(f"  Total Price: ${group['totalPrice']}")
                print(f"  Line Items: {len(group['lineItems'])}")
                print()


def demonstrate_pdfplumber_integration():
    """Demonstrate how the parser would work with actual PDF tables."""
    print("\n📄 PDFPLUMBER INTEGRATION DEMO")
    print("=" * 50)
    
    print("The enhanced table parser uses pdfplumber's table extraction capabilities:")
    print("• Extracts tables with spatial relationships preserved")
    print("• Handles complex table structures")
    print("• Identifies column headers and data types")
    print("• Supports multiple table formats")
    print("• No hardcoded assumptions about table structure")
    
    print("\nKey Features:")
    print("✅ Dynamic table structure analysis")
    print("✅ Automatic quantity group detection")
    print("✅ Flexible line item extraction")
    print("✅ Column type identification")
    print("✅ Fallback to text parsing if needed")
    print("✅ Handles varied PDF formats")


def main():
    """Main demonstration function."""
    print("🎯 ENHANCED TABLE PARSER DEMONSTRATION")
    print("=" * 60)
    print("This demo shows how the enhanced table parser handles:")
    print("• Grouped quotes with multiple quantities")
    print("• Varied PDF table formats")
    print("• Dynamic structure analysis")
    print("• No hardcoded assumptions")
    print("=" * 60)
    
    try:
        # Run demonstrations
        demonstrate_table_analysis()
        demonstrate_quantity_detection()
        demonstrate_line_item_extraction()
        demonstrate_quote_group_creation()
        demonstrate_pdfplumber_integration()
        
        print("\n🎉 DEMONSTRATION COMPLETED!")
        print("\nTo use the enhanced table parser:")
        print("1. CLI: vendra-parser parse-table your_file.pdf")
        print("2. Interactive: vendra-parser (choose option 3)")
        print("3. Python: from vendra_parser.enhanced_table_parser import parse_quote_tables")
        
    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
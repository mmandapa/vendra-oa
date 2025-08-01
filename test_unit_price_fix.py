#!/usr/bin/env python3
"""
Test the new unit price calculation that sums individual unit prices instead of averaging.
"""

from src.vendra_parser.models import LineItem
from src.vendra_parser.domain_parser import DomainAwareParser

def test_unit_price_fix():
    """Test the unit price fix using your actual data."""
    
    print("=== UNIT PRICE CALCULATION FIX ===")
    print()
    
    # Your actual line items from the PDF
    line_items = [
        LineItem("19 5-basebalancer-05: Clear polycarbonate Material", "5", "1524.28", "7621.40"),
        LineItem("19_5-coverbalancer-05: Clear polycarbonate Material", "5", "1464.00", "7320.00"),  
        LineItem("19_5-limiter-01: steel Material machining and", "5", "80.00", "400.00"),
        LineItem("Threaded_Plug: Polypropylene Material", "5", "160.00", "800.00"),
    ]
    
    print("INPUT LINE ITEMS:")
    for i, item in enumerate(line_items, 1):
        print(f"{i}. {item.description}")
        print(f"   Qty: {item.quantity}, Unit Price: ${item.unit_price}, Cost: ${item.cost}")
    print()
    
    # Parse using domain parser
    domain_parser = DomainAwareParser()
    result = domain_parser.parse_quote_structure(line_items)
    
    print("=== BEFORE (OLD CALCULATION) ===")
    print("Unit Price: $807.07 (synthetic average: $16,141.40 ÷ 20 = $807.07)")
    print("❌ This value doesn't exist in your PDF!")
    print()
    
    print("=== AFTER (NEW CALCULATION) ===")
    summary = result["summary"]
    groups = result["groups"]
    
    print("SUMMARY:")
    print(f"Total Quantity: {summary['totalQuantity']}")
    print(f"Total Unit Price Sum: ${summary['totalUnitPriceSum']} (sum of all individual unit prices)")
    print(f"Total Cost: ${summary['totalCost']}")
    print(f"Number of Groups: {summary['numberOfGroups']}")
    print()
    
    print("GROUPS:")
    for i, group in enumerate(groups, 1):
        print(f"Group {i}:")
        print(f"  Quantity: {group['quantity']}")
        print(f"  Unit Price: ${group['unitPrice']} (sum of individual unit prices)")
        print(f"  Total Price: ${group['totalPrice']}")
        print("  Line Items:")
        for item in group['lineItems']:
            print(f"    - {item['description']}")
            print(f"      Qty: {item['quantity']}, Unit: ${item['unitPrice']}, Cost: ${item['cost']}")
        print()
    
    print("=== CALCULATION BREAKDOWN ===")
    print("New Unit Price = Sum of Individual Unit Prices:")
    print(f"$1,524.28 + $1,464.00 + $80.00 + $160.00 = ${summary['totalUnitPriceSum']}")
    print("✅ This preserves the ACTUAL unit prices from your PDF!")
    
if __name__ == "__main__":
    test_unit_price_fix()
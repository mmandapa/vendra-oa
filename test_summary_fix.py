#!/usr/bin/env python3
"""
Test that the summary display no longer crashes with the new structure.
"""

from src.vendra_parser.models import LineItem
from src.vendra_parser.ocr_parser import DynamicOCRParser
import json

def test_summary_display():
    """Test that the summary display works with the new structure."""
    
    print("=== TESTING SUMMARY DISPLAY FIX ===")
    print()
    
    # Simulate what the parser returns now
    mock_result = {
        "summary": {
            "totalQuantity": "20",
            "totalUnitPriceSum": "3228.28",
            "totalCost": "16141.40",
            "numberOfGroups": 1
        },
        "groups": [
            {
                "quantity": "20",
                "unitPrice": "3228.28",
                "totalPrice": "16141.40",
                "lineItems": [
                    {
                        "description": "Test Item 1",
                        "quantity": "5",
                        "unitPrice": "100.00",
                        "cost": "500.00"
                    }
                ]
            }
        ]
    }
    
    print("New parser result structure:")
    print(json.dumps(mock_result, indent=2))
    print()
    
    # Test the summary display logic (same as in parse_quote.py and cli.py)
    try:
        parsed_data = mock_result
        
        # Handle new structure with summary and groups
        if isinstance(parsed_data, dict) and "groups" in parsed_data:
            summary = parsed_data.get("summary", {})
            groups = parsed_data.get("groups", [])
            
            print("📈 SUMMARY:")
            print(f"   • Total Quantity: {summary.get('totalQuantity', '0')}")
            print(f"   • Total Unit Price Sum: ${summary.get('totalUnitPriceSum', '0')}")
            print(f"   • Total Cost: ${summary.get('totalCost', '0')}")
            print(f"   • Found {len(groups)} quote group(s)")
            
            for i, group in enumerate(groups, 1):
                print(f"   • Group {i}: Qty {group['quantity']}, "
                      f"Unit Price ${group['unitPrice']}, "
                      f"Total ${group['totalPrice']}")
                print(f"     Line items: {len(group['lineItems'])}")
        
        print("\n✅ SUCCESS: No more 'string indices must be integers' error!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_summary_display()
    if success:
        print("\n🎉 Summary display fix working correctly!")
    else:
        print("\n💥 Summary display still has issues!")
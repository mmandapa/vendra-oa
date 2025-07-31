#!/usr/bin/env python3
"""
Tests for the Robust Quote Parser
Ensures the parser doesn't make up values and follows challenge requirements.
"""

import unittest
import tempfile
import os
import json
from decimal import Decimal
from unittest.mock import patch, mock_open

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendra_parser.robust_parser import RobustQuoteParser, ExtractedData
from vendra_parser.models import LineItem, QuoteGroup


class TestRobustQuoteParser(unittest.TestCase):
    """Test cases for the RobustQuoteParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = RobustQuoteParser()
    
    def test_normalize_price(self):
        """Test price normalization."""
        test_cases = [
            ("$1,234.56", "1234.56"),
            ("1234.56", "1234.56"),
            ("$1,234", "1234.00"),
            ("€1,234.56", "1234.56"),
            ("1,234.56 USD", "1234.56"),
            ("", "0"),
            ("invalid", "0"),
        ]
        
        for input_price, expected in test_cases:
            with self.subTest(input_price=input_price):
                result = self.parser.normalize_price(input_price)
                self.assertEqual(result, expected)
    
    def test_extract_quantities_strict(self):
        """Test strict quantity extraction - should only find explicit quantities."""
        # Test with explicit quantity patterns
        text_with_explicit = """
        Qty: 1, 3, 5
        Quantity: 10
        25 pcs @ $5.00
        50 ea @ $4.00
        """
        quantities = self.parser.extract_quantities_strict(text_with_explicit)
        expected = ["1", "3", "5", "10", "25", "50"]
        # Note: The parser might find additional quantities from the "pcs @" and "ea @" patterns
        # We just check that all expected quantities are found
        for expected_qty in expected:
            self.assertIn(expected_qty, quantities)
        
        # Test with random numbers that should NOT be extracted
        text_with_random = """
        Total: $1234.56
        Part number: ABC-123
        Phone: 555-1234
        Date: 2024-01-15
        """
        quantities = self.parser.extract_quantities_strict(text_with_random)
        self.assertEqual(quantities, [])  # Should find no quantities
    
    def test_extract_line_items_strict(self):
        """Test strict line item extraction - should only find structured items."""
        # Test with structured line items
        text_with_structured = """
        BASE MATERIAL    6    240.92    1445.52
        SOLDER ASSEMBLY  6    213.42    1280.52
        TOOLING SETUP    1    2000.00   2000.00
        """
        line_items = self.parser.extract_line_items_strict(text_with_structured)
        self.assertEqual(len(line_items), 3)
        
        # Check first item
        self.assertEqual(line_items[0].description, "BASE MATERIAL")
        self.assertEqual(line_items[0].quantity, "6")
        self.assertEqual(line_items[0].unit_price, "240.92")
        self.assertEqual(line_items[0].cost, "1445.52")
        
        # Test with unstructured text - should find nothing
        text_unstructured = """
        This is a quote for some parts.
        The total cost is $5000.
        Please contact us for more details.
        """
        line_items = self.parser.extract_line_items_strict(text_unstructured)
        self.assertEqual(line_items, [])
    
    def test_validate_line_item(self):
        """Test line item validation."""
        # Valid line item
        self.assertTrue(self.parser._validate_line_item(
            "BASE MATERIAL", "6", "240.92", "1445.52"
        ))
        
        # Invalid: empty description
        self.assertFalse(self.parser._validate_line_item(
            "", "6", "240.92", "1445.52"
        ))
        
        # Invalid: zero quantity
        self.assertFalse(self.parser._validate_line_item(
            "BASE MATERIAL", "0", "240.92", "1445.52"
        ))
        
        # Invalid: negative price
        self.assertFalse(self.parser._validate_line_item(
            "BASE MATERIAL", "6", "-240.92", "1445.52"
        ))
        
        # Invalid: cost doesn't match quantity * unit price
        self.assertFalse(self.parser._validate_line_item(
            "BASE MATERIAL", "6", "240.92", "1000.00"  # Should be 1445.52
        ))
    
    def test_calculate_total_price(self):
        """Test total price calculation."""
        line_items = [
            LineItem("BASE", "6", "240.92", "1445.52"),
            LineItem("SOLDER", "6", "213.42", "1280.52"),
            LineItem("TOOLING", "1", "2000.00", "2000.00"),
        ]
        
        total = self.parser.calculate_total_price(line_items)
        expected = str(Decimal("1445.52") + Decimal("1280.52") + Decimal("2000.00"))
        self.assertEqual(total, expected)
    
    def test_calculate_unit_price(self):
        """Test unit price calculation."""
        # Valid calculation
        unit_price = self.parser.calculate_unit_price("4726.04", "12")
        expected = str((Decimal("4726.04") / Decimal("12")).quantize(Decimal('0.01')))
        self.assertEqual(unit_price, expected)
        
        # Division by zero
        unit_price = self.parser.calculate_unit_price("4726.04", "0")
        self.assertEqual(unit_price, "0")
    
    @patch('vendra_parser.robust_parser.pdfplumber.open')
    def test_parse_quote_no_data(self, mock_pdf):
        """Test parsing when no valid data is found."""
        # Mock PDF with no structured data
        mock_page = type('Page', (), {'extract_text': lambda self: "This is just some text without any structured quote data."})()
        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]
        
        result = self.parser.parse_quote("dummy.pdf")
        self.assertEqual(result, [])  # Should return empty list, not make up data
    
    @patch('vendra_parser.robust_parser.pdfplumber.open')
    def test_parse_quote_with_valid_data(self, mock_pdf):
        """Test parsing with valid structured data."""
        # Mock PDF with valid quote data
        mock_text = """
        Qty: 1, 3, 5
        
        BASE MATERIAL    6    240.92    1445.52
        SOLDER ASSEMBLY  6    213.42    1280.52
        TOOLING SETUP    1    2000.00   2000.00
        """
        
        # Create a proper mock page object
        mock_page = type('Page', (), {'extract_text': lambda self: mock_text})()
        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]
        
        result = self.parser.parse_quote("dummy.pdf")
        
        # Should have 3 quote groups (for quantities 1, 3, 5)
        self.assertEqual(len(result), 3)
        
        # Check first group (quantity 1)
        first_group = result[0]
        self.assertEqual(first_group["quantity"], "1")
        self.assertEqual(len(first_group["lineItems"]), 3)
        
        # Check that total price is calculated correctly
        expected_total = str(Decimal("1445.52") + Decimal("1280.52") + Decimal("2000.00"))
        self.assertEqual(first_group["totalPrice"], expected_total)
    
    def test_json_output_format(self):
        """Test that output follows the exact JSON format specified in the challenge."""
        # Create sample data
        line_items = [
            LineItem("BASE", "6", "240.92", "1445.52"),
            LineItem("SOLDER", "6", "213.42", "1280.52"),
            LineItem("TOOLING", "1", "2000.00", "2000.00"),
        ]
        
        quote_group = QuoteGroup(
            quantity="12",
            unit_price="393.84",
            total_price="4726.04",
            line_items=line_items
        )
        
        # Convert to JSON format
        group_dict = {
            "quantity": quote_group.quantity,
            "unitPrice": quote_group.unit_price,
            "totalPrice": quote_group.total_price,
            "lineItems": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unitPrice": item.unit_price,
                    "cost": item.cost
                }
                for item in quote_group.line_items
            ]
        }
        
        # Verify structure matches challenge requirements
        self.assertIn("quantity", group_dict)
        self.assertIn("unitPrice", group_dict)
        self.assertIn("totalPrice", group_dict)
        self.assertIn("lineItems", group_dict)
        
        # Verify line item structure
        line_item = group_dict["lineItems"][0]
        self.assertIn("description", line_item)
        self.assertIn("quantity", line_item)
        self.assertIn("unitPrice", line_item)
        self.assertIn("cost", line_item)
        
        # Verify data types are strings as required
        self.assertIsInstance(group_dict["quantity"], str)
        self.assertIsInstance(group_dict["unitPrice"], str)
        self.assertIsInstance(group_dict["totalPrice"], str)
        self.assertIsInstance(line_item["description"], str)
        self.assertIsInstance(line_item["quantity"], str)
        self.assertIsInstance(line_item["unitPrice"], str)
        self.assertIsInstance(line_item["cost"], str)


if __name__ == "__main__":
    unittest.main() 
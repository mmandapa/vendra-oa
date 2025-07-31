#!/usr/bin/env python3
"""
Enhanced table parser using pdfplumber for extracting grouped quotes from PDF tables.
Handles varied quote formats without hardcoding any values.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation
import pdfplumber

from .models import LineItem, QuoteGroup

logger = logging.getLogger(__name__)


class EnhancedTableParser:
    """
    Enhanced table parser that uses pdfplumber's table extraction capabilities.
    Can identify and separate grouped quotes without hardcoding any values.
    """
    
    def __init__(self):
        # Dynamic patterns that adapt to the content found
        self.price_patterns = [
            r'[\$\€\£\¥]?\s*([\d,]+\.?\d*)',  # Currency symbols optional
            r'([\d,]+\.?\d*)\s*USD?',  # USD suffix
            r'([\d,]+\.?\d*)\s*per\s*unit',  # Per unit pricing
            r'([\d,]+\.?\d*)\s*each',  # Each pricing
        ]
        
        self.quantity_patterns = [
            r'qty[:\s]*(\d+)',
            r'quantity[:\s]*(\d+)',
            r'(\d+)\s*(?:pcs?|pieces?|units?)',
            r'(\d+)\s*ea',
            r'(\d+)\s*per\s*quote',
            r'quote\s*for\s*(\d+)',
        ]
        
        # Keywords that help identify line items (but not hardcoded values)
        self.line_item_indicators = [
            'material', 'labor', 'setup', 'tooling', 'assembly', 'finishing',
            'packaging', 'shipping', 'design', 'prototype', 'testing',
            'machining', 'de-burr', 'steel', 'polypropylene', 'clear pc'
        ]
    
    def parse_quote_tables(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Parse quote tables from PDF using pdfplumber's table extraction.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of quote groups with quantities and line items
        """
        logger.info(f"Parsing quote tables from: {pdf_path}")
        
        try:
            # Extract tables using pdfplumber
            tables = self._extract_tables_from_pdf(pdf_path)
            logger.info(f"Found {len(tables)} tables in PDF")
            
            if not tables:
                logger.warning("No tables found in PDF")
                return []
            
            # Analyze tables to find quote structure
            quote_groups = self._analyze_tables_for_quotes(tables)
            
            if not quote_groups:
                logger.warning("No quote groups found in tables")
                return []
            
            logger.info(f"Successfully parsed {len(quote_groups)} quote groups")
            return quote_groups
            
        except Exception as e:
            logger.error(f"Error parsing quote tables: {e}")
            return []
    
    def _extract_tables_from_pdf(self, pdf_path: str) -> List[List[List[str]]]:
        """Extract tables from PDF using pdfplumber."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_tables = []
                for page_num, page in enumerate(pdf.pages):
                    # Extract tables with different settings
                    tables = page.extract_tables()
                    if tables:
                        logger.info(f"Found {len(tables)} tables on page {page_num + 1}")
                        for table in tables:
                            if table and len(table) > 1:  # Skip empty or single-row tables
                                all_tables.append(table)
                
                return all_tables
        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            return []
    
    def _analyze_tables_for_quotes(self, tables: List[List[List[str]]]) -> List[Dict[str, Any]]:
        """
        Analyze tables to identify quote groups and line items.
        Dynamically adapts to the table structure found.
        """
        quote_groups = []
        
        for table_idx, table in enumerate(tables):
            logger.info(f"Analyzing table {table_idx + 1} with {len(table)} rows")
            
            # Analyze table structure
            table_analysis = self._analyze_table_structure(table)
            
            if table_analysis['is_quote_table']:
                # Extract quote groups from this table
                groups = self._extract_quote_groups_from_table(table, table_analysis)
                quote_groups.extend(groups)
        
        return quote_groups
    
    def _analyze_table_structure(self, table: List[List[str]]) -> Dict[str, Any]:
        """
        Analyze table structure to determine if it contains quote data.
        No hardcoded assumptions - adapts to what's found.
        """
        if not table or len(table) < 2:
            return {'is_quote_table': False}
        
        # Flatten table to analyze content
        all_text = ' '.join([' '.join(row) for row in table if row])
        all_text_lower = all_text.lower()
        
        # Look for indicators of quote data
        has_prices = any(re.search(pattern, all_text) for pattern in self.price_patterns)
        has_quantities = any(re.search(pattern, all_text) for pattern in self.quantity_patterns)
        has_line_items = any(indicator in all_text_lower for indicator in self.line_item_indicators)
        has_numbers = bool(re.search(r'\d+', all_text))
        
        # Count columns to understand structure
        max_cols = max(len(row) for row in table if row)
        
        # Determine if this looks like a quote table
        is_quote_table = (
            has_prices and 
            has_numbers and 
            max_cols >= 3 and  # At least description, quantity, price columns
            (has_quantities or has_line_items)
        )
        
        return {
            'is_quote_table': is_quote_table,
            'has_prices': has_prices,
            'has_quantities': has_quantities,
            'has_line_items': has_line_items,
            'max_columns': max_cols,
            'total_rows': len(table)
        }
    
    def _extract_quote_groups_from_table(self, table: List[List[str]], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract quote groups from a table that has been identified as containing quote data.
        Dynamically identifies quantities and line items.
        """
        quote_groups = []
        
        # First, try to identify quantity groups
        quantities = self._identify_quantities_from_table(table)
        
        if quantities:
            # Create quote groups for each quantity
            for quantity in quantities:
                line_items = self._extract_line_items_for_quantity(table, quantity)
                if line_items:
                    quote_group = self._create_quote_group(quantity, line_items)
                    quote_groups.append(quote_group)
        else:
            # No specific quantities found, treat as single quote
            line_items = self._extract_line_items_from_table(table)
            if line_items:
                # Try to infer quantity from line items
                inferred_quantity = self._infer_quantity_from_line_items(line_items)
                quote_group = self._create_quote_group(inferred_quantity, line_items)
                quote_groups.append(quote_group)
        
        return quote_groups
    
    def _identify_quantities_from_table(self, table: List[List[str]]) -> List[str]:
        """
        Identify quantities from table content.
        Looks for patterns that indicate different quote quantities.
        """
        quantities = set()
        
        # Look for quantity patterns in table content
        for row in table:
            if not row:
                continue
            
            row_text = ' '.join(row)
            
            # Look for explicit quantity patterns
            for pattern in self.quantity_patterns:
                matches = re.findall(pattern, row_text, re.IGNORECASE)
                quantities.update(matches)
            
            # Look for standalone numbers that might be quantities
            numbers = re.findall(r'\b(\d{1,4})\b', row_text)
            for num in numbers:
                num_val = int(num)
                # Check if this number appears in a quantity context
                if 1 <= num_val <= 1000:
                    # Look for context clues
                    context = row_text.lower()
                    if any(keyword in context for keyword in ['qty', 'quantity', 'quote', 'price', 'unit']):
                        quantities.add(num)
        
        # Also look for quantity columns in table structure
        if len(table) > 1:
            header_row = table[0]
            for col_idx, header in enumerate(header_row):
                if header and any(keyword in header.lower() for keyword in ['qty', 'quantity', 'units']):
                    # This column likely contains quantities
                    for row in table[1:]:
                        if col_idx < len(row) and row[col_idx]:
                            cell_value = row[col_idx].strip()
                            if cell_value.isdigit() and 1 <= int(cell_value) <= 1000:
                                quantities.add(cell_value)
        
        return sorted(list(quantities), key=int)
    
    def _extract_line_items_for_quantity(self, table: List[List[str]], quantity: str) -> List[LineItem]:
        """
        Extract line items for a specific quantity from the table.
        """
        line_items = []
        
        # Look for rows that contain this quantity
        for row in table:
            if not row:
                continue
            
            row_text = ' '.join(row)
            
            # Check if this row contains the quantity
            if quantity in row_text:
                line_item = self._parse_row_as_line_item(row, quantity)
                if line_item:
                    line_items.append(line_item)
        
        # If no specific rows found for this quantity, extract all line items
        if not line_items:
            line_items = self._extract_line_items_from_table(table)
        
        return line_items
    
    def _extract_line_items_from_table(self, table: List[List[str]]) -> List[LineItem]:
        """
        Extract line items from table rows.
        Dynamically identifies which columns contain what data.
        """
        line_items = []
        
        if len(table) < 2:
            return line_items
        
        # Analyze table structure to identify columns
        column_analysis = self._analyze_table_columns(table)
        
        for row_idx, row in enumerate(table[1:], 1):  # Skip header row
            if not row or len(row) < 3:
                continue
            
            line_item = self._parse_row_with_column_analysis(row, column_analysis)
            if line_item:
                line_items.append(line_item)
        
        return line_items
    
    def _analyze_table_columns(self, table: List[List[str]]) -> Dict[str, int]:
        """
        Analyze table columns to identify which columns contain what type of data.
        """
        if len(table) < 2:
            return {}
        
        header_row = table[0]
        column_types = {}
        
        for col_idx, header in enumerate(header_row):
            if not header:
                continue
            
            header_lower = header.lower()
            
            # Identify column types based on header content
            if any(keyword in header_lower for keyword in ['desc', 'item', 'part', 'name']):
                column_types['description'] = col_idx
            elif any(keyword in header_lower for keyword in ['qty', 'quantity', 'units']):
                column_types['quantity'] = col_idx
            elif any(keyword in header_lower for keyword in ['rate', 'price', 'unit', 'cost']):
                column_types['unit_price'] = col_idx
            elif any(keyword in header_lower for keyword in ['total', 'amount', 'cost']):
                column_types['total_cost'] = col_idx
        
        return column_types
    
    def _parse_row_with_column_analysis(self, row: List[str], column_analysis: Dict[str, int]) -> Optional[LineItem]:
        """
        Parse a table row using column analysis to identify data types.
        """
        if len(row) < 3:
            return None
        
        # Extract data based on column analysis
        description = ""
        quantity = "1"
        unit_price = "0"
        total_cost = "0"
        
        # Get description
        if 'description' in column_analysis:
            desc_col = column_analysis['description']
            if desc_col < len(row) and row[desc_col]:
                description = row[desc_col].strip()
        
        # Get quantity
        if 'quantity' in column_analysis:
            qty_col = column_analysis['quantity']
            if qty_col < len(row) and row[qty_col]:
                quantity = self._normalize_quantity(row[qty_col])
        
        # Get unit price
        if 'unit_price' in column_analysis:
            price_col = column_analysis['unit_price']
            if price_col < len(row) and row[price_col]:
                unit_price = self._normalize_price(row[price_col])
        
        # Get total cost
        if 'total_cost' in column_analysis:
            cost_col = column_analysis['total_cost']
            if cost_col < len(row) and row[cost_col]:
                total_cost = self._normalize_price(row[cost_col])
        
        # If we don't have column analysis, try to infer from row content
        if not description or unit_price == "0":
            return self._parse_row_as_line_item(row)
        
        # Validate the line item
        if description and unit_price != "0":
            return LineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                cost=total_cost if total_cost != "0" else str(Decimal(unit_price) * Decimal(quantity))
            )
        
        return None
    
    def _parse_row_as_line_item(self, row: List[str], expected_quantity: str = None) -> Optional[LineItem]:
        """
        Parse a table row as a line item using pattern matching.
        """
        if not row or len(row) < 2:
            return None
        
        row_text = ' '.join(row)
        
        # Look for patterns in the row
        # Pattern: DESCRIPTION QTY UNIT_PRICE TOTAL
        patterns = [
            r'^([A-Za-z0-9\s\-_]+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
            r'^([A-Za-z0-9\s\-_]+)\s+(\d+)\s+\$?([\d,]+\.?\d*)\s+\$?([\d,]+\.?\d*)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, row_text.strip())
            if match:
                description = match.group(1).strip()
                quantity = match.group(2)
                unit_price = self._normalize_price(match.group(3))
                cost = self._normalize_price(match.group(4))
                
                # Use expected quantity if provided and this row doesn't have a specific quantity
                if expected_quantity and quantity == "1":
                    quantity = expected_quantity
                
                return LineItem(
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    cost=cost
                )
        
        # If no pattern match, try to extract numbers and create line item
        numbers = re.findall(r'[\d,]+\.?\d*', row_text)
        if len(numbers) >= 2:
            # Assume first number is quantity, second is unit price
            quantity = self._normalize_quantity(numbers[0])
            unit_price = self._normalize_price(numbers[1])
            
            # Extract description (everything before the first number)
            description_match = re.match(r'^([A-Za-z0-9\s\-_]+)', row_text)
            description = description_match.group(1).strip() if description_match else "Item"
            
            return LineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                cost=str(Decimal(unit_price) * Decimal(quantity))
            )
        
        return None
    
    def _infer_quantity_from_line_items(self, line_items: List[LineItem]) -> str:
        """
        Infer quantity from line items when no explicit quantity is found.
        """
        if not line_items:
            return "1"
        
        # Look for common quantities in line items
        quantities = [item.quantity for item in line_items if item.quantity.isdigit()]
        
        if quantities:
            # Return the most common quantity
            from collections import Counter
            quantity_counts = Counter(quantities)
            return max(quantity_counts, key=quantity_counts.get)
        
        return "1"
    
    def _create_quote_group(self, quantity: str, line_items: List[LineItem]) -> Dict[str, Any]:
        """
        Create a quote group from quantity and line items.
        """
        if not line_items:
            return {}
        
        # Calculate total price
        total_price = sum(Decimal(item.cost) for item in line_items)
        
        # Calculate unit price
        qty_decimal = Decimal(quantity)
        unit_price = total_price / qty_decimal if qty_decimal > 0 else Decimal('0')
        
        return {
            "quantity": quantity,
            "unitPrice": str(unit_price.quantize(Decimal('0.01'))),
            "totalPrice": str(total_price.quantize(Decimal('0.01'))),
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
    
    def _normalize_price(self, price_str: str) -> str:
        """Normalize price string by removing currency symbols and formatting."""
        if not price_str:
            return "0"
        
        # Remove currency symbols and extra whitespace
        price_str = re.sub(r'[\$\€\£\¥]', '', price_str.strip())
        
        # Remove commas from numbers
        price_str = re.sub(r',', '', price_str)
        
        # Extract numeric value
        match = re.search(r'(-?[\d]+\.?\d*)', price_str)
        if match:
            try:
                value = Decimal(match.group(1))
                return str(value)
            except InvalidOperation:
                logger.warning(f"Invalid price format: {price_str}")
                return "0"
        
        return "0"
    
    def _normalize_quantity(self, qty_str: str) -> str:
        """Normalize quantity string."""
        if not qty_str:
            return "1"
        
        # Remove non-numeric characters
        qty_str = re.sub(r'[^\d]', '', qty_str)
        
        if qty_str:
            try:
                qty = int(qty_str)
                return str(qty) if qty > 0 else "1"
            except ValueError:
                return "1"
        
        return "1"


def parse_quote_tables(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Convenience function to parse quote tables from PDF.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of quote groups
    """
    parser = EnhancedTableParser()
    return parser.parse_quote_tables(pdf_path) 
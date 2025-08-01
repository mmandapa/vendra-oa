#!/usr/bin/env python3
"""
Domain-aware parser for manufacturing quotes with abbreviation handling.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation
import json

from .models import LineItem, QuoteGroup

logger = logging.getLogger(__name__)


class ManufacturingAbbreviationHandler:
    """Handles manufacturing domain-specific abbreviations and terminology."""
    
    def __init__(self):
        # Manufacturing abbreviations dictionary
        self.abbreviations = {
            # Quantity-related
            'qty': 'quantity',
            'ea': 'each',
            'pcs': 'pieces',
            'pc': 'piece',
            'units': 'units',
            'unit': 'unit',
            'moq': 'minimum order quantity',
            'min': 'minimum',
            'max': 'maximum',
            
            # Pricing-related
            'rate': 'unit_price',
            'price': 'unit_price',
            'cost': 'total_cost',
            'total': 'total_cost',
            'amt': 'amount',
            'subtotal': 'subtotal',
            'discount': 'discount',
            'tax': 'tax',
            'shipping': 'shipping',
            'handling': 'handling',
            
            # Material-related
            'mat': 'material',
            'matl': 'material',
            'pc': 'polycarbonate',
            'pp': 'polypropylene',
            'abs': 'abs',
            'steel': 'steel',
            'alum': 'aluminum',
            'al': 'aluminum',
            'ss': 'stainless steel',
            'brass': 'brass',
            'copper': 'copper',
            
            # Process-related
            'mach': 'machining',
            'machine': 'machining',
            'deburr': 'de-burring',
            'de-burr': 'de-burring',
            'finish': 'finishing',
            'polish': 'polishing',
            'anodize': 'anodizing',
            'plate': 'plating',
            'coat': 'coating',
            'paint': 'painting',
            
            # Delivery-related
            'cod': 'cash on delivery',
            'net': 'net terms',
            'fob': 'free on board',
            'cif': 'cost insurance freight',
            'lead': 'lead time',
            'delivery': 'delivery',
            'ship': 'shipping',
            
            # Quality-related
            'tolerance': 'tolerance',
            'spec': 'specification',
            'cert': 'certification',
            'iso': 'iso certified',
            'rohs': 'rohs compliant',
            'reach': 'reach compliant',
        }
        
        # Fuzzy matching patterns for common variations
        self.fuzzy_patterns = {
            r'qty\w*': 'quantity',
            r'quant\w*': 'quantity',
            r'rate\w*': 'unit_price',
            r'price\w*': 'unit_price',
            r'cost\w*': 'total_cost',
            r'total\w*': 'total_cost',
            r'mat\w*': 'material',
            r'mach\w*': 'machining',
            r'debur\w*': 'de-burring',
            r'finish\w*': 'finishing',
            r'cod\w*': 'cash on delivery',
        }
    
    def normalize_header(self, header: str) -> str:
        """Normalize header text using abbreviation dictionary and fuzzy matching."""
        header_lower = header.lower().strip()
        
        # Direct abbreviation lookup
        if header_lower in self.abbreviations:
            return self.abbreviations[header_lower]
        
        # Fuzzy pattern matching
        for pattern, replacement in self.fuzzy_patterns.items():
            if re.search(pattern, header_lower):
                return replacement
        
        # Try partial matches
        for abbr, full in self.abbreviations.items():
            if abbr in header_lower or full in header_lower:
                return full
        
        return header_lower
    
    def expand_abbreviations(self, text: str) -> str:
        """Expand abbreviations in text for better parsing."""
        text_lower = text.lower()
        expanded = text
        
        for abbr, full in self.abbreviations.items():
            if abbr in text_lower:
                # Replace abbreviation with full term
                expanded = re.sub(r'\b' + re.escape(abbr) + r'\b', full, expanded, flags=re.IGNORECASE)
        
        return expanded


class DomainAwareParser:
    """Domain-aware parser for manufacturing quotes."""
    
    def __init__(self):
        self.abbreviation_handler = ManufacturingAbbreviationHandler()
    
    def parse_quote_structure(self, line_items: List[LineItem]) -> List[Dict[str, Any]]:
        """
        Parse quote structure correctly for manufacturing quotes.
        Groups line items by quantity and creates separate quote groups for each quantity level.
        """
        if not line_items:
            return []
        
        # Group line items by their quantities
        quantity_groups = self._group_items_by_quantity(line_items)
        
        # Create quote groups for each quantity level
        quote_groups = []
        
        for quantity, items in quantity_groups.items():
            quote_group = self._create_quantity_quote_group(quantity, items)
            if quote_group:  # Only add non-empty groups
                quote_groups.append(quote_group)
        
        # Sort quote groups by quantity (ascending)
        quote_groups.sort(key=lambda x: int(x["quantity"]))
        
        return quote_groups
    
    def _calculate_total(self, line_items: List[LineItem]) -> str:
        """Calculate total price from line items, including negative values."""
        total = Decimal('0')
        for item in line_items:
            try:
                cost = Decimal(item.cost)
                total += cost  # This will handle negative values automatically
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid cost value: {item.cost}")
        
        return str(total.quantize(Decimal('0.01')))
    
    def _calculate_total_quantity(self, line_items: List[LineItem]) -> int:
        """Calculate total quantity by summing all line item quantities."""
        total_quantity = 0
        for item in line_items:
            try:
                quantity = int(item.quantity)
                total_quantity += quantity
            except (ValueError, TypeError):
                logger.warning(f"Invalid quantity value: {item.quantity}")
                # Default to 1 if quantity can't be parsed
                total_quantity += 1
        
        return total_quantity
    
    def _calculate_unit_price_from_totals(self, total_cost: str, total_quantity: int) -> Decimal:
        """Calculate unit price from total cost and total quantity."""
        try:
            cost_decimal = Decimal(total_cost)
            
            if total_quantity > 0:
                unit_price = cost_decimal / Decimal(str(total_quantity))
                # Use higher precision rounding to avoid accumulation errors
                return unit_price.quantize(Decimal('0.0001')).quantize(Decimal('0.01'))
            else:
                return Decimal('0.00')
                
        except (InvalidOperation, ValueError):
            return Decimal('0.00')
    
    def _group_items_by_quantity(self, line_items: List[LineItem]) -> Dict[str, List[LineItem]]:
        """Group line items by their quantity values."""
        quantity_groups = {}
        
        for item in line_items:
            quantity = item.quantity
            if quantity not in quantity_groups:
                quantity_groups[quantity] = []
            quantity_groups[quantity].append(item)
        
        return quantity_groups
    
    def _create_quantity_quote_group(self, quantity: str, items: List[LineItem]) -> Dict[str, Any]:
        """Create a quote group for items with the same quantity."""
        if not items:
            return {}
        
        # Calculate total cost for this quantity group
        total_cost = self._calculate_total(items)
        
        # Calculate total item count (multiply quantity by number of items)
        try:
            qty_per_item = int(quantity)
            total_item_count = qty_per_item * len(items)
        except (ValueError, TypeError):
            total_item_count = len(items)  # Fallback to just item count
        
        # Calculate unit price = total cost / total item count
        unit_price = self._calculate_unit_price_from_totals(total_cost, total_item_count)
        
        return {
            "quantity": str(total_item_count),  # Total items in this quantity group
            "unitPrice": str(unit_price),
            "totalPrice": total_cost,
            "lineItems": [
                {
                    "description": item.description,
                    "quantity": item.quantity,
                    "unitPrice": item.unit_price,
                    "cost": item.cost
                }
                for item in items
            ]
        }
    
    def normalize_line_item(self, line_item: LineItem) -> LineItem:
        """Normalize line item using domain knowledge."""
        # Expand abbreviations in description
        expanded_desc = self.abbreviation_handler.expand_abbreviations(line_item.description)
        
        # Clean up description
        cleaned_desc = self._clean_description(expanded_desc)
        
        return LineItem(
            description=cleaned_desc,
            quantity=line_item.quantity,
            unit_price=line_item.unit_price,
            cost=line_item.cost
        )
    
    def _clean_description(self, description: str) -> str:
        """Clean up description while preserving manufacturing terminology."""
        # Remove special characters but keep alphanumeric, spaces, hyphens, underscores, colons, parentheses
        description = re.sub(r'[^\w\s\-_:()]', ' ', description)
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        return description


def parse_with_domain_knowledge(line_items: List[LineItem]) -> List[Dict[str, Any]]:
    """
    Parse line items using manufacturing domain knowledge.
    
    Args:
        line_items: List of extracted line items
        
    Returns:
        Properly structured quote groups
    """
    parser = DomainAwareParser()
    
    # Normalize line items
    normalized_items = [parser.normalize_line_item(item) for item in line_items]
    
    # Parse structure
    return parser.parse_quote_structure(normalized_items) 
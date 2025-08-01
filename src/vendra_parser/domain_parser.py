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
        Parse quote structure correctly based on manufacturing domain knowledge.
        Returns properly structured quote groups.
        """
        if not line_items:
            return []
        
        # Group line items by quantity to create separate quote groups
        # This handles cases where different quantities have different pricing
        quantity_groups = {}
        
        for item in line_items:
            quantity = item.quantity
            if quantity not in quantity_groups:
                quantity_groups[quantity] = []
            quantity_groups[quantity].append(item)
        
        # Create separate quote groups for each quantity
        quote_groups = []
        
        for quantity, items in quantity_groups.items():
            # Calculate total price for this quantity group
            total_price = self._calculate_total(items)
            
            # Calculate unit price for this quantity group
            unit_price = str(round(Decimal(total_price) / Decimal(quantity), 2)) if Decimal(quantity) > 0 else "0"
            
            # Create quote group for this quantity
            quote_group = {
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
                    for item in items
                ]
            }
            
            quote_groups.append(quote_group)
        
        # Sort quote groups by quantity (ascending)
        quote_groups.sort(key=lambda x: int(x["quantity"]))
        
        return quote_groups
    
    def _calculate_total(self, line_items: List[LineItem]) -> str:
        """Calculate total price from line items."""
        total = Decimal('0')
        for item in line_items:
            try:
                total += Decimal(item.cost)
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid cost value: {item.cost}")
        
        return str(total)
    
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
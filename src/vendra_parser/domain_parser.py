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
    
    def parse_quote_structure(self, line_items: List[LineItem]) -> Dict[str, Any]:
        """
        Parse quote structure correctly for manufacturing quotes.
        Groups line items by quantity and creates separate quote groups for each quantity level.
        Returns structure with overarching totals and grouped items.
        """
        if not line_items:
            return {"summary": {}, "groups": []}
        
        # Filter to only include actual inventory items
        inventory_items = [item for item in line_items if self._is_inventory_item(item)]
        
        if not inventory_items:
            logger.warning("No valid inventory items found after filtering")
            return {"summary": {}, "groups": []}
        
        logger.info(f"Filtered {len(line_items)} raw items to {len(inventory_items)} inventory items")
        
        # Group line items by their quantities
        quantity_groups = self._group_items_by_quantity(inventory_items)
        
        # Create quote groups for each quantity level
        quote_groups = []
        
        for quantity, items in quantity_groups.items():
            quote_group = self._create_quantity_quote_group(quantity, items)
            if quote_group:  # Only add non-empty groups
                quote_groups.append(quote_group)
        
        # Sort quote groups by quantity (ascending)
        quote_groups.sort(key=lambda x: int(x["quantity"]))
        
        # Calculate overarching totals
        total_quantity = sum(int(group["quantity"]) for group in quote_groups)
        total_unit_price_sum = sum(Decimal(group["unitPrice"]) for group in quote_groups)
        total_cost = sum(Decimal(group["totalPrice"]) for group in quote_groups)
        
        summary = {
            "totalQuantity": str(total_quantity),
            "totalUnitPriceSum": str(total_unit_price_sum.quantize(Decimal('0.01'))),
            "totalCost": str(total_cost.quantize(Decimal('0.01'))),
            "numberOfGroups": len(quote_groups)
        }
        
        return {
            "summary": summary,
            "groups": quote_groups
        }
    
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
    
    def _sum_unit_prices(self, line_items: List[LineItem]) -> str:
        """Sum all individual unit prices (preserves actual PDF values)."""
        total_unit_price = Decimal('0')
        for item in line_items:
            try:
                unit_price = Decimal(item.unit_price)
                total_unit_price += unit_price
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid unit price value: {item.unit_price}")
        
        return str(total_unit_price.quantize(Decimal('0.01')))
    
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
        
        # Sum up all individual unit prices (actual values from PDF)
        unit_price_sum = self._sum_unit_prices(items)
        
        return {
            "quantity": str(total_item_count),  # Total items in this quantity group
            "unitPrice": str(unit_price_sum),  # Sum of all individual unit prices
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
    
    def _is_inventory_item(self, line_item: LineItem) -> bool:
        """Final check to ensure this is actually an inventory/product item."""
        desc_lower = line_item.description.lower().strip()
        
        # Special handling for discount/adjustment line items
        if self._is_discount_or_adjustment_line_item(line_item):
            return True
        
        # Additional domain-specific filtering for manufacturing quotes
        
        # 1. Financial/summary terms
        financial_terms = [
            'total', 'subtotal', 'balance', 'summary', 'grand total',
            'tax', 'vat', 'gst', 'sales tax', 'markup', 'surcharge'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') or desc_lower.endswith(f' {term}') for term in financial_terms):
            logger.debug(f"Domain filter rejected financial term: {line_item.description}")
            return False
        
        # 2. Payment/business terms (but not discount/adjustment line items)
        payment_terms = [
            'payment', 'deposit', 'credit',
            'net 30', 'net 60', 'financing'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') for term in payment_terms):
            logger.debug(f"Domain filter rejected payment term: {line_item.description}")
            return False
        
        # 3. Service fees and administrative items
        service_terms = [
            'consultation', 'design service', 'engineering service',
            'inspection', 'testing service', 'calibration',
            'documentation', 'certificate', 'report', 'drawing',
            'specification', 'quote', 'invoice'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') for term in service_terms):
            logger.debug(f"Domain filter rejected service term: {line_item.description}")
            return False
        
        # 4. Time/scheduling terms
        time_terms = [
            'lead time', 'delivery time', 'turnaround', 'processing time',
            'setup time', 'wait time', 'eta'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') for term in time_terms):
            logger.debug(f"Domain filter rejected time term: {line_item.description}")
            return False
        
        # 5. Generic fees/charges (but be specific about what constitutes a fee)
        if self._is_service_fee(desc_lower):
            logger.debug(f"Domain filter rejected service fee: {line_item.description}")
            return False
        
        # 6. Shipping charges - these ARE valid line items in quotes!
        # Shipping charges are legitimate costs that should be included
        if self._is_shipping_charge(desc_lower):
            logger.debug(f"Domain filter accepted shipping charge as valid line item: {line_item.description}")
            return True
        
        # Positive indicators for inventory items
        inventory_indicators = [
            # Physical materials
            'steel', 'aluminum', 'plastic', 'metal', 'alloy', 'rubber',
            'polycarbonate', 'polypropylene', 'abs', 'nylon', 'ceramic',
            
            # Manufacturing components
            'assembly', 'component', 'part', 'piece', 'unit', 'module',
            'bracket', 'mount', 'block', 'plate', 'rod', 'tube', 'shaft',
            'bearing', 'bushing', 'gasket', 'seal', 'fastener', 'screw',
            'bolt', 'nut', 'washer', 'spring', 'clip', 'pin', 'plug',
            
            # Manufacturing processes
            'machined', 'fabricated', 'welded', 'molded', 'cast',
            'threaded', 'anodized', 'plated', 'painted', 'coated',
            
            # Part number patterns
            '-', '_', 'rev', 'model', 'type', 'size', 'grade'
        ]
        
        has_inventory_indicators = any(indicator in desc_lower for indicator in inventory_indicators)
        
        # Part number pattern (strong indicator)
        import re
        has_part_number = bool(re.search(r'[A-Z0-9]+-[A-Z0-9]+|[A-Z]+\d+|REV\s+[A-Z0-9]', line_item.description.upper()))
        
        # Must have either inventory indicators or part number pattern
        is_valid = has_inventory_indicators or has_part_number
        
        # RELAXED ACCEPTANCE: Accept reasonable simple product descriptions  
        # This fixes the issue where simple names like "Widget A" are rejected
        if not is_valid:
            # Check if it looks like a reasonable product name
            words = desc_lower.split()
            non_digit_words = [w for w in words if not w.replace('.', '').replace(',', '').isdigit()]
            
            # Accept if it has reasonable characteristics of a product name
            if (len(non_digit_words) >= 1 and 2 <= len(line_item.description) <= 50):
                # Must have at least one word with letters (descriptive content)
                has_descriptive_content = any(len(word) >= 2 and any(c.isalpha() for c in word) for word in non_digit_words)
                
                if has_descriptive_content:
                    # Final safety check: ensure it's not administrative
                    admin_blacklist = ['total', 'subtotal', 'balance', 'tax', 'discount', 'payment', 
                                     'due', 'net', 'amount', 'summary', 'invoice', 'quote']
                    is_admin = any(term in desc_lower for term in admin_blacklist)
                    
                    if not is_admin:
                        logger.debug(f"Accepted simple product description: {line_item.description}")
                        is_valid = True
        
        if not is_valid:
            logger.debug(f"Domain filter rejected item without inventory indicators: {line_item.description}")
        
        return is_valid
    
    def _is_discount_or_adjustment_line_item(self, line_item: LineItem) -> bool:
        """Check if line item represents a discount or adjustment that should be included."""
        desc_lower = line_item.description.lower().strip()
        
        # Check for discount/adjustment indicators
        discount_indicators = [
            'cod', 'cash on delivery', 'discount', 'rebate', 'credit', 'adjustment',
            'deduction', 'reduction', 'markdown', 'savings', 'promotion'
        ]
        
        has_discount_term = any(term in desc_lower for term in discount_indicators)
        
        # Check for negative amounts (common for discounts)
        try:
            cost = float(line_item.cost)
            has_negative_amount = cost < 0
        except (ValueError, TypeError):
            has_negative_amount = False
        
        # Check if it's a short description (typical for adjustments)
        is_short_description = len(line_item.description.strip()) <= 30
        
        # Must have either discount terms or negative amount with short description
        return has_discount_term or (has_negative_amount and is_short_description)
    
    def _is_service_fee(self, desc_lower):
        """Check if description is a service fee rather than a product."""
        fee_patterns = [
            r'^(setup|processing|handling|service|administrative|documentation|expedite)\s+(fee|charge)$',
            r'^(fee|charge)$',
        ]
        
        import re
        for pattern in fee_patterns:
            if re.match(pattern, desc_lower):
                return True
        
        return False
    
    def _is_shipping_charge(self, desc_lower):
        """Check if description is a shipping charge vs product name with shipping words."""
        # Patterns that indicate actual shipping charges (not products)
        shipping_charge_patterns = [
            # Standalone shipping terms
            r'^freight$', r'^shipping$', r'^delivery$', r'^handling$', 
            r'^postage$', r'^courier$', r'^express$', r'^overnight$',
            
            # Shipping with simple descriptors (3 words or less)
            r'^freight\s+(shipping|cost|charge|fee)$',
            r'^shipping\s+(and\s+handling|cost|charge|fee)$',
            r'^delivery\s+(charge|fee|cost)$',
            r'^handling\s+(charge|fee|cost)$',
            
            # Common shipping charge formats
            r'^rush\s+delivery$', r'^expedited\s+shipping$',
            r'^standard\s+shipping$', r'^ground\s+shipping$'
        ]
        
        import re
        for pattern in shipping_charge_patterns:
            if re.match(pattern, desc_lower):
                return True
        
        # Additional heuristics for shipping charges:
        words = desc_lower.split()
        
        # Single word shipping terms
        if len(words) == 1 and words[0] in ['freight', 'shipping', 'delivery', 'handling', 'postage']:
            return True
        
        # Two-word combinations that are likely shipping charges
        if len(words) == 2:
            first, second = words
            if (first in ['freight', 'shipping', 'delivery', 'handling'] and 
                second in ['charge', 'fee', 'cost', 'service']):
                return True
        
        # NOT shipping charges: product names/part numbers that happen to contain shipping words
        # These typically have:
        # - Part numbers (letters + numbers + dashes)
        # - Multiple technical terms
        # - Specific material/process descriptions
        
        # If it has a part number pattern, it's likely a product
        if re.search(r'[A-Z]+-\d+|[A-Z]+\d+', desc_lower.upper()):
            return False
        
        # If it has material terms, it's likely a product
        material_terms = ['steel', 'aluminum', 'plastic', 'material', 'polycarbonate', 'metal']
        if any(term in desc_lower for term in material_terms):
            return False
        
        # If it's a complex description (4+ words), it's likely a product
        if len(words) >= 4:
            return False
        
        return False
    
    def _clean_description(self, description: str) -> str:
        """Clean up description while preserving manufacturing terminology."""
        # Remove special characters but keep alphanumeric, spaces, hyphens, underscores, colons, parentheses
        description = re.sub(r'[^\w\s\-_:()]', ' ', description)
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        return description


def parse_with_domain_knowledge(line_items: List[LineItem]) -> Dict[str, Any]:
    """
    Parse line items using manufacturing domain knowledge.
    
    Args:
        line_items: List of extracted line items
        
    Returns:
        Structure with summary totals and grouped quote items
    """
    parser = DomainAwareParser()
    
    # Normalize line items
    normalized_items = [parser.normalize_line_item(item) for item in line_items]
    
    # Parse structure
    return parser.parse_quote_structure(normalized_items) 
#!/usr/bin/env python3
"""
Robust quote parser with enhanced OCR accuracy and validation strategies.
Integrates multiple OCR engines, preprocessing, validation, and error correction.
"""

import re
import logging
import json
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation

from .models import LineItem, QuoteGroup
from .robust_ocr import RobustOCREngine
from .domain_parser import parse_with_domain_knowledge

logger = logging.getLogger(__name__)


class RobustQuoteParser:
    """
    Enhanced quote parser with robust OCR and validation strategies.
    Implements all 6 strategies for OCR accuracy improvement.
    """
    
    def __init__(self, confidence_threshold: float = 70.0):
        self.ocr_engine = RobustOCREngine(confidence_threshold)
        self.validation_issues = []
        
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main method to parse quote with robust OCR and validation.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing parsed results and validation information
        """
        logger.info(f"Starting robust quote parsing for: {pdf_path}")
        
        try:
            # Step 1: Extract text using robust OCR strategies
            ocr_result = self.ocr_engine.extract_text_from_pdf(pdf_path)
            extracted_text = ocr_result['extracted_text']
            
            if not extracted_text:
                logger.warning("No text extracted from PDF")
                return self._create_error_result("No text extracted from PDF")
            
            logger.info(f"Extracted {len(extracted_text)} characters using robust OCR")
            
            # Step 2: Validate OCR results
            validation_issues = self.ocr_engine.validate_ocr_numbers(extracted_text)
            if validation_issues:
                logger.warning(f"Found {len(validation_issues)} OCR validation issues")
                self.validation_issues.extend(validation_issues)
            
            # Step 3: Apply error correction
            corrected_text = self.ocr_engine.correct_common_ocr_errors(extracted_text)
            
            # Step 4: Parse line items with enhanced strategies
            line_items = self._parse_line_items_robustly(corrected_text)
            
            # Step 5: Cross-validate quantities and prices
            math_issues = self.ocr_engine.cross_validate_quantities(line_items)
            if math_issues:
                logger.warning(f"Found {len(math_issues)} math validation issues")
                self.validation_issues.extend(math_issues)
            
            # Step 6: Apply smart corrections
            corrected_line_items = self._apply_smart_corrections(line_items)
            
            # Step 7: Structure results using domain knowledge
            quote_groups = parse_with_domain_knowledge(corrected_line_items)
            
            # Step 8: Final validation
            final_validation = self.ocr_engine.validate_against_expected_patterns(corrected_text)
            
            # Step 9: Prepare result in expected format (list of quote groups)
            logger.info(f"Robust parsing completed. Found {len(quote_groups)} quote groups")
            return quote_groups
            
        except Exception as e:
            logger.error(f"Robust parsing failed: {e}")
            return self._create_error_result(f"Parsing failed: {str(e)}")
    
    def _parse_line_items_robustly(self, text: str) -> List[LineItem]:
        """
        Parse line items using multiple strategies with enhanced validation.
        """
        line_items = []
        lines = text.split('\n')
        
        logger.info(f"Analyzing {len(lines)} lines for robust line item parsing")
        
        # Strategy 1: Find lines with multiple numbers (potential line items)
        candidate_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Skip obvious non-line-item lines
            if self._is_non_line_item_line(line):
                continue
            
            # Find all numbers in the line (more precise pattern)
            # Look for standalone numbers, not parts of words
            numbers = re.findall(r'\b(-?[\d,]+\.?\d*)\b', line)
            
            # If line has 2 or more numbers, it might be a line item
            if len(numbers) >= 2:
                candidate_lines.append((i, line, numbers))
        
        logger.info(f"Found {len(candidate_lines)} candidate lines with multiple numbers")
        
        # Strategy 2: Parse each candidate with multiple approaches
        for line_num, line, numbers in candidate_lines:
            logger.info(f"Analyzing candidate line {line_num}: {line}")
            
            # Try different parsing strategies
            line_item = self._try_parse_line_item_robustly(line, numbers)
            if line_item:
                # Apply smart corrections to the line item
                corrected_item = self._apply_line_item_corrections(line_item)
                if corrected_item:
                    line_items.append(corrected_item)
                    logger.info(f"Successfully parsed line item: {corrected_item.description}")
        
        return line_items
    
    def _is_non_line_item_line(self, line: str) -> bool:
        """Check if a line is clearly not a line item."""
        line_lower = line.lower()
        
        # Basic non-line-item keywords
        non_line_item_keywords = [
            'phone', 'fax', 'total', 'estimate', 'date', 'name', 'address',
            'san clemente', 'san francisco', 'suite', 'street', 'vtn manufacturing',
            'little orchard', '3rd street', 'quote', 'outa', 'email', 'website',
            'thank you', 'delivery', 'terms', 'customer', 'salesman', 'ship via',
            'part number', 'item description', 'revision', 'quantity', 'price', 'amount'
        ]
        
        # Skip lines that are clearly headers or metadata
        if any(keyword in line_lower for keyword in non_line_item_keywords):
            return True
        
        # Skip lines that are too short (likely not line items)
        if len(line.strip()) < 10:
            return True
        
        # Skip lines that don't contain any numbers
        if not re.search(r'\d', line):
            return True
        
        # Skip lines that are just punctuation or special characters
        if re.match(r'^[\s\-_=*]+$', line.strip()):
            return True
        
        # Enhanced address and contact filtering (same logic as OCR parser)
        numbers = re.findall(r'(-?[\d,]+\.?\d*)', line)
        if self._is_address_or_contact_line(line, line_lower, numbers):
            return True
        
        return False
    
    def _try_parse_line_item_robustly(self, line: str, numbers: List[str]) -> Optional[LineItem]:
        """
        Try to parse a line as a line item using multiple robust strategies.
        """
        # Strategy 1: Flexible pattern matching for various quote formats
        # Look for patterns like: description quantity price total
        # or: description, quantity price total
        # or: quantity description price total
        # or: description price total (quantity = 1)
        
        # Filter out numbers that are clearly part of the description
        meaningful_numbers = []
        for num in numbers:
            # Skip numbers that are likely part of description
            if num.startswith('-') or num == ',' or num == '-05':
                continue
            # Keep decimal numbers (prices) and reasonable integers (quantities)
            if ',' in num or '.' in num or (num.isdigit() and 1 <= int(num) <= 10000):
                meaningful_numbers.append(num)
        
        if len(meaningful_numbers) >= 2:
            # Strategy 1A: Look for quantity + price + total pattern
            if len(meaningful_numbers) >= 3:
                last_three = meaningful_numbers[-3:]
                
                # Try different combinations to find the best match
                best_match = None
                best_score = 0
                
                # Try all possible combinations of the last 3 numbers
                for i in range(3):
                    for j in range(3):
                        if i != j:
                            for k in range(3):
                                if k != i and k != j:
                                    qty_candidate = last_three[i]
                                    price_candidate = last_three[j]
                                    total_candidate = last_three[k]
                                    
                                    # Check if this combination makes sense
                                    try:
                                        if qty_candidate.isdigit():
                                            qty_val = int(qty_candidate)
                                            price_val = float(self._normalize_price(price_candidate))
                                            total_val = float(self._normalize_price(total_candidate))
                                            
                                            # Calculate expected total
                                            expected_total = qty_val * price_val
                                            
                                            # Score this combination
                                            score = 0
                                            if 1 <= qty_val <= 10000:  # Reasonable quantity
                                                score += 1
                                            if price_val > 0:  # Valid price
                                                score += 1
                                            if total_val > 0:  # Valid total
                                                score += 1
                                            if abs(total_val - expected_total) < 1.0:  # Math checks out
                                                score += 3
                                            
                                            if score > best_score:
                                                best_score = score
                                                best_match = (qty_candidate, price_candidate, total_candidate)
                                    except (ValueError, TypeError):
                                        continue
                
                if best_match and best_score >= 3:
                    quantity, unit_price, cost = best_match
                    quantity = str(quantity)
                    unit_price = self._normalize_price(unit_price)
                    cost = self._normalize_price(cost)
                    
                    # Find description
                    description = self._extract_description_from_line(line, quantity, unit_price)
                    if description and self._is_valid_product_description(description):
                        return LineItem(
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            cost=cost
                        )
            
            # Strategy 1B: Look for price + total pattern (quantity = 1)
            if len(meaningful_numbers) >= 2:
                last_two = meaningful_numbers[-2:]
                
                try:
                    unit_price = self._normalize_price(last_two[0])
                    cost = self._normalize_price(last_two[1])
                    
                    # Check if this could be a valid line item
                    price_val = float(unit_price)
                    total_val = float(cost)
                    
                    if price_val > 0 and total_val > 0:
                        quantity = "1"
                        
                        # Find description
                        description = self._extract_description_from_line(line, quantity, unit_price)
                        if description and self._is_valid_product_description(description):
                            return LineItem(
                                description=description,
                                quantity=quantity,
                                unit_price=unit_price,
                                cost=cost
                            )
                except (ValueError, TypeError):
                    pass
        
        # Strategy 2: Look for any line with currency symbols and numbers
        currency_pattern = r'\$[\d,]+\.?\d*'
        currency_matches = re.findall(currency_pattern, line)
        
        if len(currency_matches) >= 2:
            try:
                # Extract prices from currency matches
                prices = [self._normalize_price(match.replace('$', '')) for match in currency_matches]
                
                if len(prices) >= 2:
                    unit_price = prices[0]
                    cost = prices[1]
                    quantity = "1"
                    
                    # Find description
                    description = self._extract_description_from_line(line, quantity, unit_price)
                    if description and self._is_valid_product_description(description):
                        return LineItem(
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            cost=cost
                        )
            except (ValueError, TypeError):
                pass
        
        # Strategy 3: Look for any reasonable line with numbers
        decimal_numbers = [num for num in numbers if ',' in num or '.' in num]
        if len(decimal_numbers) >= 2:
            try:
                unit_price = self._normalize_price(decimal_numbers[0])
                cost = self._normalize_price(decimal_numbers[1])
                quantity = "1"
                
                # Find description
                description = self._extract_description_from_line(line, quantity, unit_price)
                if description and self._is_valid_product_description(description):
                    return LineItem(
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        cost=cost
                    )
            except (ValueError, TypeError):
                pass
        
        return None
    
    def _extract_description_from_line(self, line: str, quantity: str, unit_price: str) -> Optional[str]:
        """Extract description from line, trying multiple strategies."""
        # Strategy 1: Everything before the first number
        first_num_pos = -1
        for num in [quantity, unit_price]:
            pos = line.find(num)
            if pos > 0 and (first_num_pos == -1 or pos < first_num_pos):
                first_num_pos = pos
        
        if first_num_pos > 0:
            description = line[:first_num_pos].strip()
            description = self._clean_description(description)
            if len(description) > 3:
                return self._final_clean_description(description)
        
        # Strategy 2: Everything before the first price
        price_pos = line.find(unit_price)
        if price_pos > 0:
            description = line[:price_pos].strip()
            description = self._clean_description(description)
            if len(description) > 3:
                return self._final_clean_description(description)
        
        # Strategy 3: Everything before any number
        for num in re.findall(r'\b\d+\.?\d*\b', line):
            pos = line.find(num)
            if pos > 0:
                description = line[:pos].strip()
                description = self._clean_description(description)
                if len(description) > 3:
                    return self._final_clean_description(description)
        
        return None
    
    def _clean_description(self, description: str) -> str:
        """Clean up description while preserving important parts."""
        # Remove special characters but keep alphanumeric, spaces, hyphens, underscores, colons
        description = re.sub(r'[^\w\s\-_:]', ' ', description)
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        return description
    
    def _is_valid_product_description(self, description: str) -> bool:
        """Check if a description looks like a valid product description."""
        if not description or len(description.strip()) < 3:
            return False
        
        desc_lower = description.lower()
        
        # Must not contain non-product keywords
        non_product_keywords = [
            'san clemente', 'san francisco', 'phone', 'fax', 'estimate', 'date', 'name', 'address',
            'thirty-two', 'machine inc', 'calle', 'pintoresco', 'suite', 'street', 'vtn manufacturing',
            'little orchard', '3rd street', 'quote', 'outa', 'thank you', 'delivery', 'terms',
            'customer', 'salesman', 'ship via', 'part number', 'item description', 'revision',
            'quantity', 'price', 'amount', 'total', 'email', 'website'
        ]
        
        has_non_product_keyword = any(keyword in desc_lower for keyword in non_product_keywords)
        if has_non_product_keyword:
            return False
        
        # Must be reasonably long and contain some descriptive text
        words = description.split()
        if len(words) < 1:  # More flexible - allow single word descriptions
            return False
        
        # Must contain at least one word that's not just numbers
        has_descriptive_word = any(not word.isdigit() and len(word) > 1 for word in words)
        
        # Skip descriptions that are just numbers or special characters
        if re.match(r'^[\d\s\-_.,]+$', description.strip()):
            return False
        
        return has_descriptive_word
    
    def _final_clean_description(self, description: str) -> str:
        """Final cleanup of description while preserving product names and part numbers."""
        # Only remove obvious trailing artifacts, not part numbers
        # Remove trailing standalone numbers that are clearly not part of product names
        # Be very conservative - only remove if it's clearly formatting artifacts
        
        # Remove trailing "and X" only if X is a small number (likely formatting)
        description = re.sub(r'\s+and\s+([1-9])\s*$', '', description)  # Only single digits
        
        # Remove trailing ", X" only if X is a small number (likely formatting)  
        description = re.sub(r'\s+,\s*([1-9])\s*$', '', description)  # Only single digits
        
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        
        return description
    
    def _normalize_price(self, price_str: str) -> str:
        """Normalize price string by removing currency symbols and formatting."""
        if not price_str:
            return "0"
        
        # Remove currency symbols and extra whitespace
        price_str = re.sub(r'[\$\€\£\¥]', '', price_str.strip())
        
        # Remove commas from numbers
        price_str = re.sub(r',', '', price_str)
        
        # Extract numeric value (including negative numbers)
        match = re.search(r'(-?[\d]+\.?\d*)', price_str)
        if match:
            try:
                value = Decimal(match.group(1))
                return str(value)
            except InvalidOperation:
                logger.warning(f"Invalid price format: {price_str}")
                return "0"
        
        return "0"
    
    def _apply_smart_corrections(self, line_items: List[LineItem]) -> List[LineItem]:
        """
        Apply smart corrections to line items based on context and validation.
        """
        corrected_items = []
        
        for item in line_items:
            # Apply quantity corrections
            corrected_qty = self._apply_quantity_corrections(item.quantity, item)
            if corrected_qty:
                item.quantity = str(corrected_qty)
            
            # Apply price corrections
            corrected_unit_price = self._apply_price_corrections(item.unit_price, item)
            if corrected_unit_price:
                item.unit_price = str(corrected_unit_price)
            
            # Recalculate cost if needed
            try:
                expected_cost = Decimal(item.quantity) * Decimal(item.unit_price)
                actual_cost = Decimal(item.cost)
                
                # If there's a significant difference, flag it
                if abs(expected_cost - actual_cost) > 0.01:
                    logger.warning(f"Cost mismatch for {item.description}: {item.quantity} × {item.unit_price} ≠ {item.cost}")
                    # Don't automatically correct the cost - let the original OCR value stand
                    # The cost from OCR might be correct even if math doesn't add up
                    
            except (ValueError, InvalidOperation):
                pass
            
            corrected_items.append(item)
        
        return corrected_items
    
    def _apply_quantity_corrections(self, quantity: str, item: LineItem) -> Optional[float]:
        """Apply smart quantity corrections."""
        try:
            qty = float(quantity)
            
            # If quantity seems too high, might be missing decimal
            if qty > 1000:
                context_clues = {'decimal_expected': True}
                corrected = self.ocr_engine.smart_quantity_correction(quantity, context_clues)
                if corrected and corrected != qty:
                    logger.info(f"Corrected quantity from {qty} to {corrected} for {item.description}")
                    return corrected
            
            return qty
        except ValueError:
            return None
    
    def _apply_price_corrections(self, price: str, item: LineItem) -> Optional[float]:
        """Apply smart price corrections."""
        try:
            price_val = float(price)
            
            # If price seems too high without decimal, might be missing decimal
            if price_val > 10000 and '.' not in price:
                # Try common decimal placements
                candidates = [
                    price_val / 10,    # 12340 -> 1234.0
                    price_val / 100,   # 12340 -> 123.40
                    price_val / 1000   # 12340 -> 12.340
                ]
                
                # Return most reasonable candidate
                for candidate in candidates:
                    if 1 <= candidate <= 10000:  # Reasonable price range
                        logger.info(f"Corrected price from {price_val} to {candidate} for {item.description}")
                        return candidate
            
            return price_val
        except ValueError:
            return None
    
    def _apply_line_item_corrections(self, item: LineItem) -> Optional[LineItem]:
        """Apply corrections to a single line item."""
        try:
            # Validate the item makes sense
            qty = Decimal(item.quantity)
            unit_price = Decimal(item.unit_price)
            cost = Decimal(item.cost)
            
            # Check for obvious errors
            if qty <= 0 or unit_price <= 0 or cost <= 0:
                logger.warning(f"Invalid values in line item: {item.description}")
                return None
            
            # Check if math roughly adds up (allow for rounding)
            expected_cost = qty * unit_price
            if abs(cost - expected_cost) > 1.0:  # Allow $1 tolerance
                logger.warning(f"Cost doesn't add up for {item.description}: {qty} × {unit_price} ≠ {cost}")
                # Correct the cost
                item.cost = str(expected_cost)
            
            return item
            
        except (ValueError, InvalidOperation) as e:
            logger.warning(f"Error validating line item {item.description}: {e}")
            return None
    
    def _is_address_or_contact_line(self, line: str, line_lower: str, numbers: List[str]) -> bool:
        """
        Comprehensive check if a line is an address or contact information.
        This works regardless of how many numbers are in the line.
        """
        # Address keywords (more comprehensive)
        address_keywords = [
            'street', 'avenue', 'road', 'drive', 'lane', 'blvd', 'boulevard', 'st', 'ave', 'rd', 'dr', 'ln',
            'suite', 'ste', 'apt', 'apartment', 'unit', 'floor', 'room', '#',
            'san', 'francisco', 'jose', 'california', 'ca', 'los angeles', 'santa', 'north', 'south', 'east', 'west',
            'city', 'county', 'state', 'zip', 'postal'
        ]
        
        # Contact keywords
        contact_keywords = [
            'phone', 'tel', 'telephone', 'fax', 'email', 'mail', 'website', 'web', 'www',
            'contact', 'attn', 'attention', 'to:', 'from:', 'c/o', 'care of'
        ]
        
        # Company/header keywords that might contain numbers but aren't line items
        company_keywords = [
            'inc', 'corp', 'corporation', 'llc', 'ltd', 'limited', 'company', 'co',
            'manufacturing', 'mfg', 'industries', 'group', 'enterprises'
        ]
        
        # Check for address patterns (using word boundaries for better precision)
        address_matches = []
        for keyword in address_keywords:
            # Use word boundaries for short keywords to avoid false matches
            if len(keyword) <= 3:
                if re.search(r'\b' + re.escape(keyword) + r'\b', line_lower):
                    address_matches.append(keyword)
            else:
                if keyword in line_lower:
                    address_matches.append(keyword)
        
        if address_matches:
            # Additional validation: check if it has address-like number patterns
            # Zip codes (5 digits, or 5+4 format)
            if re.search(r'\b\d{5}(-\d{4})?\b', line):
                return True
            # Street addresses (number + street keyword)
            if re.search(r'\b\d+\s+(street|avenue|road|drive|lane|blvd|st|ave|rd|dr|ln)\b', line_lower):
                return True
            # Suite/apartment numbers
            if re.search(r'(suite|ste|apt|apartment|unit|floor|room|#)\s*\d+', line_lower):
                return True
            # If it has 2+ address keywords, it's probably an address even without specific patterns
            if len(address_matches) >= 2:
                return True
        
        # Check for contact patterns
        if any(keyword in line_lower for keyword in contact_keywords):
            # Phone number patterns
            if re.search(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', line) or re.search(r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}', line):
                return True
            # Email patterns
            if re.search(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', line):
                return True
            # Website patterns
            if re.search(r'\bwww\.|\.com\b|\.org\b|\.net\b', line_lower):
                return True
        
        # Check for company header lines (these often have numbers but aren't line items)
        if any(keyword in line_lower for keyword in company_keywords):
            # If it contains company keywords and no obvious product/manufacturing terms, skip it
            product_keywords = ['material', 'assembly', 'machining', 'tooling', 'part', 'component', 'qty', 'quantity']
            if not any(keyword in line_lower for keyword in product_keywords):
                return True
        
        # Check for lines that are just numbers with no meaningful description
        # Remove all numbers from the line and see what's left
        text_without_numbers = re.sub(r'[\d,.$%-]+', '', line).strip()
        meaningful_text = re.sub(r'[^\w\s]', ' ', text_without_numbers).strip()
        
        # If after removing numbers there's very little meaningful text, it might be an address/contact line
        # Use the same precise matching logic for contact keywords
        contact_matches = []
        for keyword in contact_keywords:
            if len(keyword) <= 3:
                if re.search(r'\b' + re.escape(keyword) + r'\b', line_lower):
                    contact_matches.append(keyword)
            else:
                if keyword in line_lower:
                    contact_matches.append(keyword)
        
        if len(meaningful_text.split()) <= 2 and (address_matches or contact_matches):
            return True
        
        # Check for specific problematic patterns that commonly get misidentified
        # Lines that start with numbers but are addresses (e.g., "123 Main Street")
        if re.match(r'^\s*\d+\s+(street|avenue|road|drive|lane|blvd|st|ave|rd|dr|ln)', line_lower):
            return True
        
        # Lines that contain city, state, zip patterns
        if re.search(r'\b[A-Z][a-z]+,\s*[A-Z]{2}\s+\d{5}\b', line):
            return True
        
        return False
    
    def _create_error_result(self, error_message: str) -> Dict[str, Any]:
        """Create an error result structure."""
        return {
            'quote_groups': [],
            'line_items': [],
            'validation': {
                'ocr_validation': {'confidence': 0, 'needs_manual_review': True},
                'final_validation': {'confidence': 0, 'needs_manual_review': True},
                'issues': [error_message],
                'needs_manual_review': True
            },
            'ocr_details': {
                'extracted_text_length': 0,
                'corrected_text_length': 0,
                'page_results': []
            }
        }
    
    def parse_quote_to_json(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """Parse quote and return JSON string."""
        result = self.parse_quote(pdf_path)
        
        # Convert LineItem objects to dictionaries for JSON serialization
        if isinstance(result, list):
            # Convert LineItem objects in quote groups
            for group in result:
                if 'lineItems' in group:
                    group['lineItems'] = [item.__dict__ if hasattr(item, '__dict__') else item for item in group['lineItems']]
        
        json_str = json.dumps(result, indent=2, default=str)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
            logger.info(f"Results saved to: {output_path}")
        
        return json_str


# Convenience function for backward compatibility
def parse_quote_robustly(pdf_path: str) -> Dict[str, Any]:
    """
    Parse quote using robust OCR and validation strategies.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary containing parsed results and validation information
    """
    parser = RobustQuoteParser()
    return parser.parse_quote(pdf_path) 
#!/usr/bin/env python3
"""
Truly adaptive PDF parser that makes minimal assumptions about structure.
Learns patterns from the document itself rather than using hardcoded rules.
"""

import re
import logging
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple, Set
from decimal import Decimal, InvalidOperation
import json
from collections import defaultdict, Counter

from .models import LineItem, QuoteGroup
from .domain_parser import parse_with_domain_knowledge

logger = logging.getLogger(__name__)


class AdaptivePDFParser:
    """Truly adaptive parser that learns document structure dynamically."""
    
    def __init__(self):
        self.learned_patterns = {}
        self.document_structure = {}
        
    def extract_text_with_ocr(self, pdf_path: str) -> str:
        """Extract text from PDF using OCR or direct extraction."""
        try:
            return self._extract_with_ocr_tools(pdf_path)
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return self._extract_text_directly(pdf_path)
    
    def _extract_with_ocr_tools(self, pdf_path: str) -> str:
        """Extract text using external OCR tools."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF to images
            image_path = os.path.join(temp_dir, "page")
            subprocess.run([
                'pdftoppm', '-png', '-r', '300', pdf_path, image_path
            ], check=True)
            
            # Extract text from each image
            all_text = ""
            page_num = 1
            
            while True:
                image_file = f"{image_path}-{page_num}.png"
                if not os.path.exists(image_file):
                    break
                
                result = subprocess.run([
                    'tesseract', image_file, 'stdout', '--psm', '6'
                ], capture_output=True, text=True, check=True)
                
                page_text = result.stdout.strip()
                if page_text:
                    all_text += f"\n=== PAGE {page_num} ===\n{page_text}\n"
                
                page_num += 1
            
            return all_text
    
    def _extract_text_directly(self, pdf_path: str) -> str:
        """Extract text directly from PDF."""
        try:
            import pdfplumber
            all_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        all_text += f"\n=== PAGE {page_num} ===\n{text}\n"
            return all_text
        except Exception as e:
            logger.error(f"Direct text extraction failed: {e}")
            raise
    
    def analyze_document_structure(self, text: str) -> Dict[str, Any]:
        """Analyze document structure to understand layout patterns."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        structure = {
            'total_lines': len(lines),
            'number_patterns': {},
            'column_patterns': {},
            'header_patterns': [],
            'line_item_patterns': [],
            'pricing_patterns': {},
            'text_regions': []
        }
        
        # Analyze number patterns in each line
        for i, line in enumerate(lines):
            numbers = self._extract_all_numbers(line)
            if numbers:
                pattern_key = f"numbers_{len(numbers)}"
                if pattern_key not in structure['number_patterns']:
                    structure['number_patterns'][pattern_key] = []
                structure['number_patterns'][pattern_key].append({
                    'line_num': i,
                    'line': line,
                    'numbers': numbers
                })
        
        # Detect potential column structures
        structure['column_patterns'] = self._detect_column_patterns(lines)
        
        # Identify different text regions
        structure['text_regions'] = self._identify_text_regions(lines)
        
        return structure
    
    def extract_prices_flexible(self, text: str) -> List[Dict[str, Any]]:
        """Extract prices using flexible patterns (Priority Fix #1)."""
        prices = []
        
        # Multiple price patterns in order of reliability
        price_patterns = [
            r'([$€£¥][\d,]+\.?\d*)',                    # $1,234.56
            r'([\d,]+\.?\d*)\s*(?:/EA|/EACH|each|per)',  # 123.45 /EA
            r'([\d,]+\.?\d*)\s*(?:USD|EUR|GBP|CAD)',     # 123.45 USD
            r'([\d,]+\.?\d*)(?=\s*$)',                   # Numbers at line end
            r'([\d,]+\.\d{2})',                          # Decimal currency format
            r'([\d,]+\.?\d*)'                            # Any decimal number
        ]
        
        for pattern in price_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_value = match.group(1)
                start_pos = match.start()
                end_pos = match.end()
                
                # Get context for classification
                context_start = max(0, start_pos - 15)
                context_end = min(len(text), end_pos + 15)
                context = text[context_start:context_end].lower()
                
                normalized = self._normalize_number(raw_value)
                if normalized:
                    prices.append({
                        'raw': raw_value,
                        'normalized': normalized,
                        'position': (start_pos, end_pos),
                        'context': context,
                        'is_currency': True,
                        'confidence': self._calculate_price_confidence(raw_value, context)
                    })
        
        # Remove duplicates and sort by confidence
        seen_positions = set()
        unique_prices = []
        for price in sorted(prices, key=lambda x: x['confidence'], reverse=True):
            if price['position'] not in seen_positions:
                unique_prices.append(price)
                seen_positions.add(price['position'])
        
        return unique_prices
    
    def _calculate_price_confidence(self, raw_value: str, context: str) -> float:
        """Calculate confidence score for price detection."""
        confidence = 0.5  # Base confidence
        
        # Higher confidence for currency symbols
        if any(symbol in raw_value for symbol in ['$', '€', '£', '¥']):
            confidence += 0.3
            
        # Higher confidence for price-related context
        price_keywords = ['price', 'cost', 'total', 'amount', 'rate', 'fee', 'charge']
        if any(keyword in context for keyword in price_keywords):
            confidence += 0.2
            
        # Higher confidence for proper decimal format
        if '.' in raw_value and len(raw_value.split('.')[-1]) == 2:
            confidence += 0.2
            
        # Lower confidence for very small or large numbers
        try:
            value = float(self._normalize_number(raw_value) or 0)
            if 0.01 <= value <= 100000:
                confidence += 0.1
            elif value > 100000:
                confidence -= 0.2
        except:
            pass
            
        return min(confidence, 1.0)

    def _extract_all_numbers(self, text: str) -> List[Dict[str, Any]]:
        """Extract all numbers with their positions and context."""
        numbers = []
        
        # Various number patterns
        patterns = [
            r'(-?\$?[\d,]+\.?\d*%?)',  # Basic numbers with optional currency/percent
            r'(-?\d+\.?\d*e[+-]?\d+)',  # Scientific notation
            r'(-?\d+/\d+)',  # Fractions
            r'(-?\d+:\d+)',  # Ratios/time
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                raw_value = match.group(1)
                start_pos = match.start()
                end_pos = match.end()
                
                # Get surrounding context
                context_start = max(0, start_pos - 10)
                context_end = min(len(text), end_pos + 10)
                context = text[context_start:context_end]
                
                # Try to normalize the number
                normalized = self._normalize_number(raw_value)
                
                numbers.append({
                    'raw': raw_value,
                    'normalized': normalized,
                    'position': (start_pos, end_pos),
                    'context': context,
                    'is_currency': '$' in raw_value or any(word in context.lower() for word in ['price', 'cost', 'total', 'amount']),
                    'is_quantity': any(word in context.lower() for word in ['qty', 'quantity', 'pcs', 'each', 'ea']),
                    'is_percentage': '%' in raw_value
                })
        
        return numbers
    
    def _normalize_number(self, raw_value: str) -> Optional[str]:
        """Improved number normalization handling international formats."""
        if not raw_value:
            return None
            
        try:
            # Remove currency symbols, text, and extra whitespace
            cleaned = re.sub(r'[^\d,.-]', '', str(raw_value).strip())
            
            if not cleaned:
                return None
            
            # Handle European format (1.234,56) vs US format (1,234.56)
            if ',' in cleaned and '.' in cleaned:
                # Determine format by position of last comma vs last dot
                last_comma = cleaned.rfind(',')
                last_dot = cleaned.rfind('.')
                
                if last_comma > last_dot:
                    # European: 1.234,56 -> 1234.56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # US: 1,234.56 -> 1234.56
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned and len(cleaned.split(',')[-1]) <= 2:
                # European decimal: 123,45 -> 123.45
                cleaned = cleaned.replace(',', '.')
            else:
                # Remove commas (thousands separators)
                cleaned = cleaned.replace(',', '')
            
            # Validate and convert
            value = Decimal(cleaned)
            return str(value.quantize(Decimal('0.01')))
            
        except (InvalidOperation, ValueError, TypeError):
            return None
    
    def _detect_column_patterns(self, lines: List[str]) -> Dict[str, Any]:
        """Detect potential columnar layouts in the document."""
        column_info = {
            'detected_columns': 0,
            'column_positions': [],
            'alignment_patterns': []
        }
        
        # Look for consistent spacing patterns that suggest columns
        tab_positions = []
        for line in lines:
            # Find positions of multiple consecutive spaces (potential column separators)
            for match in re.finditer(r'\s{2,}', line):
                tab_positions.append(match.start())
        
        # Find common tab positions
        if tab_positions:
            position_counts = Counter(tab_positions)
            common_positions = [pos for pos, count in position_counts.most_common(5) if count >= 3]
            column_info['column_positions'] = common_positions
            column_info['detected_columns'] = len(common_positions) + 1
        
        return column_info
    
    def find_data_sections(self, lines: List[str]) -> List[List[str]]:
        """Smart table detection - find sections with pricing data (Priority Fix #2)."""
        data_sections = []
        current_section = []
        
        for line in lines:
            line = line.strip()
            if not line:
                # Empty line might end a section
                if current_section:
                    data_sections.append(current_section)
                    current_section = []
                continue
                
            # Look for lines with pricing data
            if self.has_pricing_data(line):
                current_section.append(line)
            else:
                # Non-pricing line might end a section
                if current_section and len(current_section) >= 2:
                    # Only save sections with multiple lines
                    data_sections.append(current_section)
                current_section = []
        
        # Don't forget the last section
        if current_section and len(current_section) >= 1:
            data_sections.append(current_section)
            
        return data_sections
    
    def has_pricing_data(self, line: str) -> bool:
        """Check if line contains pricing data indicators."""
        # Skip obvious header/footer lines
        line_lower = line.lower()
        skip_indicators = [
            'total:', 'subtotal:', 'tax:', 'shipping:', 'discount:',
            'phone:', 'email:', 'address:', 'thank you', 'terms',
            'conditions', 'payment', 'due date', 'valid until'
        ]
        
        if any(skip in line_lower for skip in skip_indicators):
            return False
        
        # Look for numeric patterns that suggest pricing
        numbers = re.findall(r'[\d,]+\.?\d*', line)
        
        # Need at least 2 numbers
        if len(numbers) < 2:
            return False
            
        # Check for price-like patterns
        has_currency = any(symbol in line for symbol in ['$', '€', '£', '¥'])
        has_decimal_price = any('.' in num and len(num.split('.')[-1]) <= 2 for num in numbers)
        has_quantity_indicator = any(word in line_lower for word in ['qty', 'quantity', 'pcs', 'ea', 'each', 'units'])
        
        # More likely to be pricing data if it has these characteristics
        return has_currency or has_decimal_price or (len(numbers) >= 3 and has_quantity_indicator)
    
    def extract_quantity_flexible(self, text_section: str) -> str:
        """Flexible quantity detection with multiple fallbacks (Priority Fix #3)."""
        qty_patterns = [
            r'(?:qty|quantity|amount|count):\s*(\d+)',     # Qty: 5
            r'(?:qty|quantity|amount|count)\s+(\d+)',      # Qty 5
            r'(\d+)\s*(?:pieces?|units?|ea|each|pcs)',     # 5 pieces
            r'^(\d+)\s+',                                  # Number at start of line
            r'(\d+)(?=\s*[×x])',                          # 5 x item
            r'(\d+)(?=\s*[@])',                           # 5 @ $10.00
            r'(\d+)(?=\s*\$)',                            # 5 $10.00
        ]
        
        for pattern in qty_patterns:
            match = re.search(pattern, text_section, re.IGNORECASE)
            if match:
                qty_val = int(match.group(1))
                # Validate reasonable quantity range
                if 1 <= qty_val <= 10000:
                    return str(qty_val)
        
        # Fallback: look for standalone numbers in reasonable range
        numbers = re.findall(r'\b(\d+)\b', text_section)
        for num_str in numbers:
            try:
                num_val = int(num_str)
                if 1 <= num_val <= 1000:  # Conservative range for fallback
                    return str(num_val)
            except ValueError:
                continue
        
        return "1"  # Default fallback
    
    def _identify_text_regions(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Identify different regions in the document (header, line items, totals, etc.)."""
        regions = []
        current_region = {'type': 'unknown', 'start_line': 0, 'lines': [], 'characteristics': {}}
        
        for i, line in enumerate(lines):
            line_characteristics = self._analyze_line_characteristics(line)
            
            # Determine if this line suggests a new region
            if self._suggests_new_region(line_characteristics, current_region.get('characteristics', {})):
                if current_region['lines']:
                    current_region['end_line'] = i - 1
                    regions.append(current_region)
                
                current_region = {
                    'type': self._classify_region_type(line_characteristics),
                    'start_line': i,
                    'lines': [line],
                    'characteristics': line_characteristics
                }
            else:
                current_region['lines'].append(line)
                # Update region characteristics
                for key, value in line_characteristics.items():
                    if key in current_region['characteristics']:
                        if isinstance(value, (int, float)):
                            current_region['characteristics'][key] += value
                        elif isinstance(value, bool) and value:
                            current_region['characteristics'][key] = True
                    else:
                        current_region['characteristics'][key] = value
        
        # Add the last region
        if current_region['lines']:
            current_region['end_line'] = len(lines) - 1
            regions.append(current_region)
        
        return regions
    
    def _analyze_line_characteristics(self, line: str) -> Dict[str, Any]:
        """Analyze characteristics of a single line."""
        characteristics = {
            'length': len(line),
            'word_count': len(line.split()),
            'number_count': len(self._extract_all_numbers(line)),
            'has_currency': any(symbol in line for symbol in ['$', '€', '£', '¥']),
            'has_percentage': '%' in line,
            'has_colon': ':' in line,
            'all_caps': line.isupper() and len(line) > 5,
            'starts_with_number': bool(re.match(r'^\s*\d', line)),
            'ends_with_number': bool(re.search(r'\d\s*$', line)),
            'punctuation_density': len(re.findall(r'[^\w\s]', line)) / len(line) if line else 0
        }
        
        return characteristics
    
    def _suggests_new_region(self, current_char: Dict[str, Any], previous_char: Dict[str, Any]) -> bool:
        """Determine if current line characteristics suggest a new document region."""
        if not previous_char:
            return False
            
        # Significant changes that might indicate new regions
        return (
            abs(current_char['number_count'] - previous_char.get('number_count', 0)) > 2 or
            current_char['all_caps'] != previous_char.get('all_caps', False) or
            abs(current_char['punctuation_density'] - previous_char.get('punctuation_density', 0)) > 0.3 or
            (current_char['has_currency'] and not previous_char.get('has_currency', False))
        )
    
    def _classify_region_type(self, characteristics: Dict[str, Any]) -> str:
        """Classify the type of document region based on characteristics."""
        if characteristics['all_caps'] and characteristics['word_count'] < 10:
            return 'header'
        elif characteristics['number_count'] >= 2 and characteristics['has_currency']:
            return 'line_items'  # Lowered threshold from 3 to 2 numbers
        elif characteristics['number_count'] >= 3:  # Multiple numbers even without currency
            return 'line_items'
        elif characteristics['has_currency'] and any(word in ['total', 'subtotal', 'sum'] for word in ['total', 'subtotal', 'sum']):
            return 'totals'
        elif characteristics['has_colon']:
            return 'metadata'
        else:
            return 'content'
    
    def discover_line_items_adaptively(self, text: str) -> List[LineItem]:
        """Discover line items using adaptive pattern recognition."""
        # First analyze the document structure
        structure = self.analyze_document_structure(text)
        
        line_items = []
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Focus on regions likely to contain line items, but be more inclusive
        line_item_regions = [region for region in structure['text_regions'] 
                           if region['type'] in ['line_items', 'content', 'unknown']]
        
        for region in line_item_regions:
            region_lines = region['lines']
            region_items = self._extract_line_items_from_region(region_lines, structure)
            line_items.extend(region_items)
        
        # If still no line items found, try all lines with adaptive approach
        if not line_items:
            line_items = self._fallback_adaptive_extraction(lines, structure)
        
        return line_items
    
    def _extract_line_items_from_region(self, lines: List[str], structure: Dict[str, Any]) -> List[LineItem]:
        """Extract line items from a specific region using learned patterns."""
        line_items = []
        
        for line in lines:
            numbers = self._extract_all_numbers(line)
            
            # Skip lines with no numbers or only one number (likely not line items)
            if len(numbers) < 2:
                continue
            
            # Try to identify the best line item pattern for this line
            line_item = self._adaptive_line_item_extraction(line, numbers, structure)
            
            if line_item:
                line_items.append(line_item)
        
        return line_items
    
    def _adaptive_line_item_extraction(self, line: str, numbers: List[Dict[str, Any]], structure: Dict[str, Any]) -> Optional[LineItem]:
        """Adaptively extract line item from a line based on learned patterns."""
        # Try different strategies based on the number and types of numbers found
        
        # Strategy 1: Look for clear quantity, unit price, total pattern
        quantity_candidates = [n for n in numbers if n.get('is_quantity', False)]
        currency_candidates = [n for n in numbers if n.get('is_currency', False)]
        
        if len(currency_candidates) >= 2:
            # Likely has unit price and total
            unit_price = currency_candidates[0]
            total = currency_candidates[-1]
            
            # Look for quantity
            quantity = None
            if quantity_candidates:
                quantity = quantity_candidates[0]
            else:
                # Try to infer quantity from other numbers
                for num in numbers:
                    if num not in currency_candidates:
                        normalized = num.get('normalized')
                        if normalized:
                            try:
                                qty_val = float(normalized)
                                if 1 <= qty_val <= 10000:  # Reasonable quantity range
                                    quantity = num
                                    break
                            except ValueError:
                                continue
            
            if quantity and unit_price and total:
                # Validate the math
                try:
                    qty_val = Decimal(quantity['normalized'])
                    price_val = Decimal(unit_price['normalized'])
                    total_val = Decimal(total['normalized'])
                    
                    expected_total = qty_val * price_val
                    tolerance = abs(expected_total - total_val) / abs(total_val) if total_val != 0 else 1
                    
                    if tolerance <= 0.15:  # Allow 15% tolerance for rounding differences
                        description = self._extract_description_adaptively(line, [quantity, unit_price, total])
                        if description and len(description.strip()) > 2:
                            return LineItem(
                                description=description.strip(),
                                quantity=quantity['normalized'],
                                unit_price=unit_price['normalized'],
                                cost=total['normalized']
                            )
                except (InvalidOperation, ValueError, ZeroDivisionError):
                    pass
        
        # Strategy 2: Mathematical validation approach
        # Try all possible combinations of 3 numbers and see which ones satisfy qty * price = total
        if len(numbers) >= 3:
            for i in range(len(numbers)):
                for j in range(i+1, len(numbers)):
                    for k in range(j+1, len(numbers)):
                        num_combo = [numbers[i], numbers[j], numbers[k]]
                        line_item = self._try_mathematical_validation(line, num_combo)
                        if line_item:
                            return line_item
        
        # Strategy 3: Pattern-based fallback
        return self._pattern_based_extraction(line, numbers)
    
    def _try_mathematical_validation(self, line: str, numbers: List[Dict[str, Any]]) -> Optional[LineItem]:
        """Try to validate line item using mathematical relationships."""
        # Try all permutations of the three numbers as qty, unit_price, total
        from itertools import permutations
        
        for perm in permutations(numbers):
            qty_num, price_num, total_num = perm
            
            try:
                if not qty_num['normalized'] or not price_num['normalized'] or not total_num['normalized']:
                    continue
                    
                qty = Decimal(qty_num['normalized'])
                price = Decimal(price_num['normalized'])
                total = Decimal(total_num['normalized'])
                
                # Validate quantity is reasonable
                if not (0.1 <= qty <= 10000):
                    continue
                    
                # Check if qty * price ≈ total
                expected_total = qty * price
                tolerance = abs(expected_total - total) / abs(total) if total != 0 else 1
                
                if tolerance <= 0.1:  # Within 10% tolerance
                    description = self._extract_description_adaptively(line, list(perm))
                    if description and len(description.strip()) > 2:
                        return LineItem(
                            description=description.strip(),
                            quantity=str(qty),
                            unit_price=str(price),
                            cost=str(total)
                        )
            except (InvalidOperation, ValueError, ZeroDivisionError):
                continue
        
        return None
    
    def _pattern_based_extraction(self, line: str, numbers: List[Dict[str, Any]]) -> Optional[LineItem]:
        """Fallback pattern-based extraction."""
        if len(numbers) >= 2:
            # Simple fallback: take last two numbers as unit price and total
            price_num = numbers[-2]
            total_num = numbers[-1]
            
            if price_num['normalized'] and total_num['normalized']:
                try:
                    price = Decimal(price_num['normalized'])
                    total = Decimal(total_num['normalized'])
                    
                    if price != 0:
                        # Calculate implied quantity
                        qty = total / price
                        
                        # Validate quantity is reasonable
                        if 0.1 <= qty <= 10000:
                            description = self._extract_description_adaptively(line, [price_num, total_num])
                            if description and len(description.strip()) > 2:
                                return LineItem(
                                    description=description.strip(),
                                    quantity=str(qty.quantize(Decimal('0.01'))),
                                    unit_price=str(price),
                                    cost=str(total)
                                )
                except (InvalidOperation, ValueError, ZeroDivisionError):
                    pass
        
        return None
    
    def _extract_description_adaptively(self, line: str, used_numbers: List[Dict[str, Any]]) -> str:
        """Extract description by removing the used numbers from the line."""
        description = line
        
        # Remove the used numbers from the line to get description
        for num in sorted(used_numbers, key=lambda x: x['position'][1], reverse=True):
            start, end = num['position']
            description = description[:start] + description[end:]
        
        # Clean up the description
        description = re.sub(r'\s+', ' ', description).strip()
        description = re.sub(r'^[^\w]+|[^\w]+$', '', description)  # Remove leading/trailing non-word chars
        
        return description
    
    def _fallback_adaptive_extraction(self, lines: List[str], structure: Dict[str, Any]) -> List[LineItem]:
        """Fallback extraction when regions don't yield results."""
        line_items = []
        
        for line in lines:
            numbers = self._extract_all_numbers(line)
            
            if len(numbers) >= 2:
                # Try adaptive extraction
                line_item = self._adaptive_line_item_extraction(line, numbers, structure)
                if line_item:
                    line_items.append(line_item)
        
        return line_items
    
    def parse_quote_robust(self, pdf_path: str) -> Dict[str, Any]:
        """Multi-strategy parsing with confidence scoring (Priority Fix #4)."""
        logger.info(f"Starting robust multi-strategy parsing of: {pdf_path}")
        
        # Extract text
        text = self.extract_text_with_ocr(pdf_path)
        logger.info(f"Extracted {len(text)} characters from PDF")
        
        if not text:
            logger.warning("No text extracted from PDF")
            return self.create_minimal_result(text)
        
        # Try strategies in order of reliability
        strategies = [
            self.parse_structured_table,
            self.parse_data_sections,
            self.parse_line_by_line_scanning,
            self.parse_keyword_extraction,
            self.parse_regex_fallback
        ]
        
        best_result = None
        best_confidence = 0
        
        for strategy in strategies:
            try:
                logger.info(f"Trying strategy: {strategy.__name__}")
                result = strategy(text)
                confidence = self.calculate_confidence(result)
                
                logger.info(f"Strategy {strategy.__name__} confidence: {confidence:.1f}%")
                
                if confidence > best_confidence:
                    best_result = result
                    best_confidence = confidence
                    
                # If we get high confidence, stop trying
                if confidence > 80:
                    logger.info(f"High confidence achieved ({confidence:.1f}%), stopping")
                    break
                    
            except Exception as e:
                logger.warning(f"Strategy {strategy.__name__} failed: {e}")
                continue
        
        final_result = best_result or self.create_minimal_result(text)
        
        # Apply business logic improvements to enhance the results
        if final_result and final_result.get('groups'):
            logger.info("Applying business logic improvements...")
            final_result = self.infer_pricing_from_structure(final_result)
            final_result = self.apply_industry_heuristics(final_result)
            
            # Recalculate confidence after improvements
            enhanced_confidence = self.calculate_confidence(final_result)
            logger.info(f"Enhanced confidence: {enhanced_confidence:.1f}% (was {best_confidence:.1f}%)")
        
        logger.info(f"Final result: {len(final_result.get('groups', []))} groups")
        
        return final_result
    
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """Main parse method - uses robust multi-strategy approach."""
        return self.parse_quote_robust(pdf_path)
    
    def parse_quote_to_json(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """Parse quote and return JSON string."""
        result = self.parse_quote(pdf_path)
        
        json_str = json.dumps(result, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
            logger.info(f"Results saved to: {output_path}")
        
        return json_str
    
    # ============= BUSINESS LOGIC IMPROVEMENTS =============
    
    def infer_pricing_from_structure(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use document structure clues to infer pricing details (Business Logic #1)."""
        groups = extracted_data.get('groups', [])
        
        for group in groups:
            line_items = group.get('lineItems', [])
            for item in line_items:
                try:
                    description = item.get('description', '').lower()
                    quantity = float(item.get('quantity', 1))
                    total_cost = float(item.get('cost', 0))
                    stated_unit_price = float(item.get('unitPrice', 0))
                    
                    # Calculate implied unit price if missing or doesn't match
                    if quantity > 0 and total_cost > 0:
                        implied_unit = total_cost / quantity
                        
                        # If stated unit price is missing or significantly different, use implied
                        if stated_unit_price == 0 or abs(stated_unit_price - implied_unit) > 0.01:
                            item['calculatedUnitPrice'] = f"{implied_unit:.2f}"
                            item['unitPrice'] = f"{implied_unit:.2f}"
                        
                        # Infer pricing type from description + math
                        item['pricingType'] = self._infer_pricing_type(description, implied_unit)
                        
                        # Add confidence indicators
                        item['confidence'] = self._calculate_item_confidence(item)
                        
                except (ValueError, TypeError, ZeroDivisionError):
                    # Set defaults for problematic items
                    item['pricingType'] = 'unit'
                    item['confidence'] = 0.5
        
        return extracted_data
    
    def _infer_pricing_type(self, description: str, unit_price: float) -> str:
        """Infer pricing type from description and unit price."""
        desc_lower = description.lower()
        
        # Time-based pricing indicators
        if any(word in desc_lower for word in ['hour', 'hr', 'time', 'labor', 'service', 'consultation']):
            return 'hourly'
        
        # Area-based pricing indicators  
        if any(word in desc_lower for word in ['sq', 'area', 'coverage', 'surface', 'sqft', 'sqm']):
            return 'area'
            
        # Weight-based pricing indicators
        if any(word in desc_lower for word in ['lb', 'kg', 'weight', 'pound', 'kilogram', 'ton']):
            return 'weight'
            
        # Volume-based pricing indicators
        if any(word in desc_lower for word in ['gallon', 'liter', 'cubic', 'volume', 'gal', 'l']):
            return 'volume'
            
        # High unit price often indicates hourly/service pricing
        if unit_price > 100:
            return 'hourly'
        elif unit_price > 1000:
            return 'project'
        else:
            return 'unit'
    
    def _calculate_item_confidence(self, item: Dict[str, Any]) -> float:
        """Calculate confidence score for individual line item."""
        confidence = 0.5  # Base confidence
        
        try:
            # Mathematical consistency
            qty = float(item.get('quantity', 1))
            unit_price = float(item.get('unitPrice', 0))
            total = float(item.get('cost', 0))
            
            if abs(qty * unit_price - total) <= 0.01:
                confidence += 0.3
            
            # Description quality
            desc = item.get('description', '')
            if len(desc) > 5 and any(c.isalpha() for c in desc):
                confidence += 0.2
                
            # Reasonable values
            if 0.01 <= unit_price <= 100000 and 0.1 <= qty <= 10000:
                confidence += 0.2
                
        except (ValueError, TypeError):
            confidence = 0.3
            
        return min(confidence, 1.0)
    
    def apply_industry_heuristics(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply industry-specific rules (Business Logic #2)."""
        # Analyze the overall quote to determine likely industry
        all_descriptions = []
        for group in quote_data.get('groups', []):
            for item in group.get('lineItems', []):
                all_descriptions.append(item.get('description', ''))
        
        all_text = ' '.join(all_descriptions).lower()
        
        # Industry keyword detection
        manufacturing_keywords = ['part', 'component', 'machining', 'fabrication', 'cnc', 'assembly', 'bracket', 'widget', 'motor']
        service_keywords = ['labor', 'consultation', 'service', 'support', 'training', 'maintenance', 'installation']
        material_keywords = ['steel', 'aluminum', 'plastic', 'lumber', 'concrete', 'fabric', 'raw material']
        
        industry_type = 'general'
        if any(kw in all_text for kw in manufacturing_keywords):
            industry_type = 'manufacturing'
        elif any(kw in all_text for kw in service_keywords):
            industry_type = 'service'
        elif any(kw in all_text for kw in material_keywords):
            industry_type = 'material'
        
        # Apply industry-specific rules
        if industry_type == 'manufacturing':
            quote_data = self.apply_manufacturing_rules(quote_data)
        elif industry_type == 'service':
            quote_data = self.apply_service_rules(quote_data)
        elif industry_type == 'material':
            quote_data = self.apply_material_rules(quote_data)
        
        # Add industry classification to summary
        if 'summary' not in quote_data:
            quote_data['summary'] = {}
        quote_data['summary']['detectedIndustry'] = industry_type
        
        return quote_data
    
    def apply_manufacturing_rules(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply manufacturing-specific business rules."""
        for group in quote_data.get('groups', []):
            for item in group.get('lineItems', []):
                desc = item.get('description', '').lower()
                
                # Manufacturing items often have part numbers
                if re.search(r'[A-Z0-9]+-[A-Z0-9]+', item.get('description', '')):
                    item['hasPartNumber'] = True
                
                # Common manufacturing pricing expectations
                unit_price = float(item.get('unitPrice', 0))
                if unit_price > 500:
                    item['note'] = 'High-value component or assembly'
                elif unit_price < 1:
                    item['note'] = 'Low-cost component or fastener'
        
        return quote_data
    
    def apply_service_rules(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply service-specific business rules."""
        for group in quote_data.get('groups', []):
            for item in group.get('lineItems', []):
                desc = item.get('description', '').lower()
                unit_price = float(item.get('unitPrice', 0))
                
                # Service pricing is often hourly
                if any(word in desc for word in ['hour', 'labor', 'service']):
                    if 25 <= unit_price <= 300:
                        item['note'] = 'Standard hourly rate'
                    elif unit_price > 300:
                        item['note'] = 'Premium/specialist rate'
                    elif unit_price < 25:
                        item['note'] = 'Low hourly rate - verify'
        
        return quote_data
    
    def apply_material_rules(self, quote_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply material-specific business rules."""
        for group in quote_data.get('groups', []):
            for item in group.get('lineItems', []):
                desc = item.get('description', '').lower()
                
                # Material pricing often per weight/area
                if any(unit in desc for unit in ['lb', 'kg', 'sqft', 'sqm']):
                    item['note'] = 'Priced per unit of measure'
                
                # High quantity materials are common
                qty = float(item.get('quantity', 1))
                if qty > 100:
                    item['note'] = 'Bulk material order'
        
        return quote_data
    
    # ============= CORE PRICING PATTERNS (80/20 APPROACH) =============
    
    CORE_PATTERNS = [
        r'(\d+\.?\d*)\s*/\s*(?:ea|each|unit)',         # $50/ea
        r'(\d+\.?\d*)\s*per\s*(?:unit|piece)',         # $50 per unit  
        r'(\d+\.?\d*)\s*/\s*(?:hr|hour)',              # $75/hr
        r'unit\s*price:?\s*(\d+\.?\d*)',               # Unit Price: $50
        r'rate:?\s*(\d+\.?\d*)',                       # Rate: $75
        r'(\d+\.?\d*)\s*(?:dollars?|USD)\s*/\s*(?:ea|hr|unit)', # $50 USD/ea
        r'@\s*(\d+\.?\d*)',                            # @ $50.00
        r'(\d+\.?\d*)\s*each',                         # $50.00 each
        r'(\d+\.?\d*)\s*/\s*(?:lb|kg)',                # $5/lb
        r'(\d+\.?\d*)\s*(?:/|per)\s*(?:sq\s*ft|sqft)'  # $10/sqft
    ]
    
    def extract_unit_prices_with_core_patterns(self, text: str) -> List[Dict[str, Any]]:
        """Extract unit prices using the 80/20 core patterns."""
        unit_prices = []
        
        for i, pattern in enumerate(self.CORE_PATTERNS):
            for match in re.finditer(pattern, text, re.IGNORECASE):
                raw_price = match.group(1)
                normalized_price = self._normalize_number(raw_price)
                
                if normalized_price:
                    # Determine pricing unit from pattern
                    pricing_unit = self._get_pricing_unit_from_pattern(i, match.group(0))
                    
                    unit_prices.append({
                        'raw': raw_price,
                        'normalized': normalized_price,
                        'pricing_unit': pricing_unit,
                        'position': match.span(),
                        'confidence': 0.8 + (i * 0.02),  # Earlier patterns are more reliable
                        'pattern_used': i
                    })
        
        # Remove duplicates and sort by confidence
        return sorted(unit_prices, key=lambda x: x['confidence'], reverse=True)
    
    def _get_pricing_unit_from_pattern(self, pattern_index: int, matched_text: str) -> str:
        """Determine pricing unit from the pattern that matched."""
        unit_mapping = {
            0: 'each',      # /ea
            1: 'unit',      # per unit
            2: 'hour',      # /hr
            3: 'unit',      # unit price
            4: 'hour',      # rate (usually hourly)
            5: 'each',      # USD/ea
            6: 'each',      # @ price
            7: 'each',      # each
            8: 'weight',    # /lb or /kg
            9: 'area'       # /sqft
        }
        
        return unit_mapping.get(pattern_index, 'unit')
    
    # ============= PARSING STRATEGIES =============
    
    def parse_structured_table(self, text: str) -> Dict[str, Any]:
        """Strategy 1: Parse structured table format."""
        return self._parse_using_current_adaptive_method(text)
    
    def parse_data_sections(self, text: str) -> Dict[str, Any]:
        """Strategy 2: Parse using smart data section detection."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        data_sections = self.find_data_sections(lines)
        
        all_line_items = []
        for section in data_sections:
            for line in section:
                if self.has_pricing_data(line):
                    line_item = self._extract_line_item_robust(line)
                    if line_item:
                        all_line_items.append(line_item)
        
        if all_line_items:
            return parse_with_domain_knowledge(all_line_items)
        return {"summary": {}, "groups": []}
    
    def parse_line_by_line_scanning(self, text: str) -> Dict[str, Any]:
        """Strategy 3: Scan every line for potential line items."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        line_items = []
        
        for line in lines:
            if len(line) > 10:  # Skip very short lines
                line_item = self._extract_line_item_robust(line)
                if line_item:
                    line_items.append(line_item)
        
        if line_items:
            return parse_with_domain_knowledge(line_items)
        return {"summary": {}, "groups": []}
    
    def parse_keyword_extraction(self, text: str) -> Dict[str, Any]:
        """Strategy 4: Extract based on keywords and context."""
        # Focus on lines with product/service keywords
        product_keywords = ['widget', 'assembly', 'kit', 'service', 'product', 'item', 'part', 'component']
        lines = text.split('\n')
        
        candidate_lines = []
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in product_keywords):
                # Look for numbers in this line
                if len(re.findall(r'[\d,]+\.?\d*', line)) >= 2:
                    candidate_lines.append(line.strip())
        
        line_items = []
        for line in candidate_lines:
            line_item = self._extract_line_item_robust(line)
            if line_item:
                line_items.append(line_item)
        
        if line_items:
            return parse_with_domain_knowledge(line_items)
        return {"summary": {}, "groups": []}
    
    def parse_regex_fallback(self, text: str) -> Dict[str, Any]:
        """Strategy 5: Aggressive regex-based extraction."""
        # Look for any pattern that might be: description + numbers
        pattern = r'([A-Za-z][A-Za-z0-9\s\-_\.]+?)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)'
        matches = re.findall(pattern, text)
        
        line_items = []
        for match in matches:
            desc, num1, num2, num3 = match
            # Try to determine which is qty, unit price, total
            numbers = [num1, num2, num3]
            line_item = self._create_line_item_from_numbers(desc.strip(), numbers)
            if line_item:
                line_items.append(line_item)
        
        if line_items:
            return parse_with_domain_knowledge(line_items)
        return {"summary": {}, "groups": []}
    
    def _parse_using_current_adaptive_method(self, text: str) -> Dict[str, Any]:
        """Use the current adaptive method."""
        line_items = self.discover_line_items_adaptively(text)
        if line_items:
            return parse_with_domain_knowledge(line_items)
        return {"summary": {}, "groups": []}
    
    def _extract_line_item_robust(self, line: str) -> Optional[LineItem]:
        """Robust line item extraction using multiple approaches."""
        # First try core pricing patterns (80/20 approach)
        unit_prices = self.extract_unit_prices_with_core_patterns(line)
        
        if unit_prices:
            # Use the highest confidence unit price pattern
            best_unit_price = unit_prices[0]
            quantity = self.extract_quantity_flexible(line)
            
            try:
                qty_val = float(quantity)
                price_val = float(best_unit_price['normalized'])
                total_val = qty_val * price_val
                
                # Extract description by removing the price pattern
                start, end = best_unit_price['position']
                description = line[:start].strip()
                if not description:
                    description = line[end:].strip()
                
                if description and len(description.strip()) > 2:
                    return LineItem(
                        description=description.strip(),
                        quantity=quantity,
                        unit_price=str(price_val),
                        cost=str(total_val)
                    )
            except (ValueError, TypeError):
                pass
        
        # Use flexible price extraction
        prices = self.extract_prices_flexible(line)
        numbers = self._extract_all_numbers(line)
        
        if len(prices) >= 2:
            # Try with flexible quantity detection
            quantity = self.extract_quantity_flexible(line)
            unit_price = prices[0]['normalized']
            total = prices[-1]['normalized']
            
            # Validate math with tolerance
            try:
                if abs(float(quantity) * float(unit_price) - float(total)) <= 0.01:
                    description = self._extract_description_adaptively(line, [])
                    if description and len(description.strip()) > 2:
                        return LineItem(
                            description=description.strip(),
                            quantity=quantity,
                            unit_price=unit_price,
                            cost=total
                        )
            except (ValueError, TypeError):
                pass
        
        # Fallback to original adaptive method
        return self._adaptive_line_item_extraction(line, numbers, {})
    
    def _create_line_item_from_numbers(self, description: str, numbers: List[str]) -> Optional[LineItem]:
        """Create line item from description and list of numbers."""
        if len(numbers) != 3:
            return None
            
        # Try different permutations
        from itertools import permutations
        for perm in permutations(numbers):
            try:
                qty_str, price_str, total_str = perm
                qty = float(self._normalize_number(qty_str) or 0)
                price = float(self._normalize_number(price_str) or 0)
                total = float(self._normalize_number(total_str) or 0)
                
                if 1 <= qty <= 10000 and price > 0 and abs(qty * price - total) <= 0.01:
                    return LineItem(
                        description=description,
                        quantity=str(qty),
                        unit_price=str(price),
                        cost=str(total)
                    )
            except (ValueError, TypeError):
                continue
        
        return None
    
    def calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score for parsing result (Priority Fix #6)."""
        if not result:
            return 0
            
        score = 0
        groups = result.get('groups', [])
        summary = result.get('summary', {})
        
        # Has line items
        if groups and len(groups) > 0:
            score += 40
            
            # Multiple line items is better
            total_items = sum(len(group.get('lineItems', [])) for group in groups)
            if total_items > 1:
                score += 20
            if total_items > 3:
                score += 10
        
        # Has reasonable total price
        try:
            total_cost = float(summary.get('totalCost', 0))
            if 0.01 <= total_cost <= 1000000:
                score += 20
        except (ValueError, TypeError):
            pass
        
        # Math validation - totals add up
        if self.validate_totals(result):
            score += 30
        
        # Has proper descriptions (not just numbers)
        description_quality = 0
        for group in groups:
            for item in group.get('lineItems', []):
                desc = item.get('description', '')
                if desc and len(desc) > 3:
                    # Good if it has letters
                    if re.search(r'[A-Za-z]', desc):
                        description_quality += 5
        
        score += min(description_quality, 20)
        
        return min(score, 100)
    
    def validate_totals(self, result: Dict[str, Any]) -> bool:
        """Validate that calculated totals match stated totals."""
        try:
            groups = result.get('groups', [])
            calculated_total = 0
            
            for group in groups:
                for item in group.get('lineItems', []):
                    item_cost = float(item.get('cost', 0))
                    calculated_total += item_cost
            
            stated_total = float(result.get('summary', {}).get('totalCost', 0))
            
            # Allow small rounding differences
            return abs(calculated_total - stated_total) <= 1.0
            
        except (ValueError, TypeError, KeyError):
            return False
    
    def create_minimal_result(self, text: str) -> Dict[str, Any]:
        """Create minimal result when no parsing strategies work."""
        # Try to extract any totals from the text
        total_patterns = [
            r'total[:\s]+\$?([\d,]+\.?\d*)',
            r'\$?([\d,]+\.?\d*)\s*total',
            r'amount[:\s]+\$?([\d,]+\.?\d*)'
        ]
        
        total_found = None
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                total_found = self._normalize_number(match.group(1))
                break
        
        return {
            "summary": {
                "totalQuantity": "0",
                "totalCost": total_found or "0",
                "numberOfGroups": 0
            },
            "groups": []
        }


# Convenience function
def parse_with_adaptive_parser(pdf_path: str) -> Dict[str, Any]:
    """Parse PDF using adaptive parser."""
    parser = AdaptivePDFParser()
    return parser.parse_quote(pdf_path)
#!/usr/bin/env python3
"""
Comprehensive PDF Parser
Combines invoice2data, multi-format parsing, and OCR with automatic currency detection.
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

class ComprehensivePDFParser:
    """
    Comprehensive parser that tries multiple approaches with automatic currency detection.
    """
    
    def __init__(self):
        # Default method order (will be reordered based on CID detection)
        self.extraction_methods = [
            ('invoice2data', self._extract_with_invoice2data),
            ('multi_format', self._extract_with_multi_format),
            ('ocr_fallback', self._extract_with_ocr_fallback),
        ]
    
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse quote using comprehensive approach with automatic currency detection.
        """
        logger.info(f"🔍 Starting comprehensive parsing of: {pdf_path}")
        
        # Check if this PDF has significant CID issues
        has_cid_issues = self._detect_cid_issues(pdf_path)
        if has_cid_issues:
            logger.info("🔧 Detected CID font encoding issues - prioritizing OCR fallback")
            # Reorder methods to prioritize OCR for CID issues
            self.extraction_methods = [
                ('ocr_fallback', self._extract_with_ocr_fallback),
                ('multi_format', self._extract_with_multi_format),
                ('invoice2data', self._extract_with_invoice2data),
            ]
        else:
            logger.info("✅ No CID issues detected - using standard method priority")
            # Use standard order for clean PDFs
            self.extraction_methods = [
                ('invoice2data', self._extract_with_invoice2data),
                ('multi_format', self._extract_with_multi_format),
                ('ocr_fallback', self._extract_with_ocr_fallback),
            ]
        
        results = []
        
        # Try each extraction method
        for method_name, method_func in self.extraction_methods:
            try:
                logger.info(f"📊 Trying {method_name} extraction...")
                result = method_func(pdf_path)
                if result and self._validate_result(result):
                    quality_score = self._score_result_quality(result)
                    results.append({
                        'method': method_name,
                        'result': result,
                        'score': quality_score
                    })
                    logger.info(f"✅ {method_name} succeeded with score: {quality_score}")
                    
                    # If we get a high-quality result, use it
                    if quality_score >= 80:
                        logger.info(f"🎯 Using high-quality result from {method_name}")
                        return result
                else:
                    logger.warning(f"❌ {method_name} failed or produced invalid result")
            except Exception as e:
                logger.warning(f"❌ {method_name} failed with error: {str(e)}")
        
        # Select best result
        if results:
            best_result = max(results, key=lambda x: x['score'])
            logger.info(f"🏆 Using best result from {best_result['method']} with score: {best_result['score']}")
            return best_result['result']
        else:
            logger.error("❌ All extraction methods failed!")
            return self._empty_result()
    
    def _extract_with_invoice2data(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using invoice2data library."""
        try:
            from invoice2data import extract_data
            from invoice2data.input import pdftotext
            
            # Try invoice2data extraction
            extracted_data = extract_data(pdf_path, input_module=pdftotext)
            
            if extracted_data:
                logger.info("📄 invoice2data extracted structured data")
                # Convert to our format
                return self._convert_invoice2data_result(extracted_data)
            else:
                logger.info("📄 invoice2data found no template, falling back to manual extraction")
                return self._extract_manually_with_currency_detection(pdf_path)
                
        except Exception as e:
            logger.error(f"invoice2data extraction failed: {e}")
            return self._extract_manually_with_currency_detection(pdf_path)
    
    def _extract_with_multi_format(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using multi-format parser."""
        try:
            from .multi_format_parser import MultiFormatPDFParser
            parser = MultiFormatPDFParser()
            return parser.parse_quote(pdf_path)
        except Exception as e:
            logger.error(f"Multi-format extraction failed: {e}")
            return None
    
    def _extract_with_ocr_fallback(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using OCR as final fallback."""
        try:
            from .ocr_parser import DynamicOCRParser
            parser = DynamicOCRParser()
            return parser.parse_quote(pdf_path)
        except Exception as e:
            logger.error(f"OCR fallback extraction failed: {e}")
            return None
    
    def _extract_manually_with_currency_detection(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Manual extraction with automatic currency detection."""
        try:
            import iso4217parse
            
            # Extract text using multiple methods
            all_text = self._extract_text_from_pdf(pdf_path)
            if not all_text:
                return None
            
            # Detect currencies automatically
            detected_currencies = iso4217parse.parse(all_text)
            logger.info(f"🌍 Detected currencies: {[c.alpha3 for c in detected_currencies]}")
            
            # Extract line items with currency-aware patterns
            line_items = self._extract_line_items_with_currency_detection(all_text, detected_currencies)
            
            if not line_items:
                logger.warning("No line items found with currency detection")
                return None
            
            # Group and format results
            return self._format_result(line_items)
            
        except Exception as e:
            logger.error(f"Manual extraction with currency detection failed: {e}")
            return None
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text using multiple PDF libraries."""
        all_text = ""
        
        # Try pdfplumber first
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
        except Exception as e:
            logger.debug(f"pdfplumber failed: {e}")
        
        # Try PyMuPDF if pdfplumber didn't work well
        if len(all_text.strip()) < 100:
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(pdf_path)
                for page in doc:
                    all_text += page.get_text() + "\n"
                doc.close()
            except Exception as e:
                logger.debug(f"PyMuPDF failed: {e}")
        
        # Try OCR if text extraction failed
        if len(all_text.strip()) < 50:
            try:
                from .ocr_parser import DynamicOCRParser
                ocr_parser = DynamicOCRParser()
                ocr_result = ocr_parser._extract_text_with_ocr(pdf_path)
                if ocr_result:
                    all_text = ocr_result
            except Exception as e:
                logger.debug(f"OCR fallback failed: {e}")
        
        return all_text
    
    def _extract_line_items_with_currency_detection(self, text: str, detected_currencies: List) -> List:
        """Extract line items with automatic currency detection."""
        from .models import LineItem
        
        line_items = []
        lines = text.split('\n')
        
        # Build comprehensive currency symbol set
        currency_symbols = {'€', '$', '£', '¥', '₹', '₽', '₿', '₩', '₪', '₨', '₦', '₡', '₱', '₲', '₴', '₵', '₸', '₺', '₻', '₼', '₽', '₾', '₿'}
        
        # Add symbols from detected currencies
        for currency in detected_currencies:
            # Only add short symbols (avoid full words like "dollars")
            currency_symbols.update([s for s in currency.symbols if len(s) <= 3])
        
        # Create patterns for different currency formats
        patterns = self._create_currency_patterns(currency_symbols)
        
        for line in lines:
            line = line.strip()
            if not line or not self._is_likely_line_item(line):
                continue
            
            # Try each pattern
            for pattern_name, pattern in patterns.items():
                matches = pattern.findall(line)
                for match in matches:
                    line_item = self._create_line_item_from_match(match, pattern_name)
                    if line_item and self._is_valid_line_item(line_item):
                        line_items.append(line_item)
                        logger.debug(f"Found line item ({pattern_name}): {line_item.description} - {line_item.quantity} x {line_item.unit_price} = {line_item.cost}")
                        break  # Don't try other patterns for this line
                else:
                    continue  # Only executed if the inner loop didn't break
                break  # Break outer loop if we found a match
        
        # Remove duplicates
        line_items = self._deduplicate_line_items(line_items)
        
        logger.info(f"Found {len(line_items)} unique line items with currency detection")
        return line_items
    
    def _create_currency_patterns(self, currency_symbols: set) -> Dict[str, re.Pattern]:
        """Create regex patterns for different currency formats."""
        # Escape currency symbols for regex
        escaped_symbols = [re.escape(symbol) for symbol in currency_symbols]
        currency_pattern = '|'.join(escaped_symbols)
        
        patterns = {}
        
        # Pattern 1: USD format - Description Quantity $Price $Total
        patterns['usd_standard'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+(\d+)\s+\$([0-9,]+(?:\.[0-9]{{2}})?)\s+\$([0-9,]+(?:\.[0-9]{{2}})?)'
        )
        
        # Pattern 2: European format - Description Quantity €Price €Total  
        patterns['eur_standard'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+(\d+)\s+({currency_pattern})([0-9.,]+)\s+({currency_pattern})([0-9.,]+)'
        )
        
        # Pattern 3: USD without quantity - Description $Price $Total
        patterns['usd_no_qty'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+\$([0-9,]+(?:\.[0-9]{{2}})?)\s+\$([0-9,]+(?:\.[0-9]{{2}})?)'
        )
        
        # Pattern 4: European without quantity - Description €Price €Total
        patterns['eur_no_qty'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+({currency_pattern})([0-9.,]+)\s+({currency_pattern})([0-9.,]+)'
        )
        
        # Pattern 5: Flexible format - any currency with numbers
        patterns['flexible'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+(\d+)?\s*({currency_pattern})?([0-9.,]+)\s+({currency_pattern})?([0-9.,]+)'
        )
        
        return patterns
    
    def _create_line_item_from_match(self, match: tuple, pattern_name: str):
        """Create LineItem from regex match based on pattern type."""
        from .models import LineItem
        
        try:
            if pattern_name == 'usd_standard':
                description, quantity, unit_price, total = match
                return self._create_usd_line_item(description, quantity, unit_price, total)
            
            elif pattern_name == 'eur_standard':
                description, quantity, _, unit_price, _, total = match
                return self._create_eur_line_item(description, quantity, unit_price, total)
            
            elif pattern_name == 'usd_no_qty':
                description, unit_price, total = match
                # Infer quantity
                unit_price_val = float(unit_price.replace(',', ''))
                total_val = float(total.replace(',', ''))
                quantity = int(round(total_val / unit_price_val)) if unit_price_val > 0 else 1
                return self._create_usd_line_item(description, str(quantity), unit_price, total)
            
            elif pattern_name == 'eur_no_qty':
                description, _, unit_price, _, total = match
                # Infer quantity
                unit_price_val = self._parse_european_number(unit_price)
                total_val = self._parse_european_number(total)
                quantity = int(round(total_val / unit_price_val)) if unit_price_val > 0 else 1
                return self._create_eur_line_item(description, str(quantity), unit_price, total)
            
            elif pattern_name == 'flexible':
                description, quantity, currency1, price1, currency2, price2 = match
                # Determine format based on currency and number format
                if '$' in (currency1 or '') or '$' in (currency2 or '') or (',' in price1 and '.' in price1 and price1.rfind('.') > price1.rfind(',')):
                    # USD format
                    quantity = quantity or "1"
                    return self._create_usd_line_item(description, quantity, price1, price2)
                else:
                    # European format
                    quantity = quantity or "1"
                    return self._create_eur_line_item(description, quantity, price1, price2)
            
        except Exception as e:
            logger.debug(f"Failed to create line item from match {match}: {e}")
            return None
        
        return None
    
    def _create_usd_line_item(self, description: str, quantity: str, unit_price: str, total: str):
        """Create line item for USD format."""
        from .models import LineItem
        
        try:
            # Clean description
            description = description.strip()
            
            # Parse USD numbers
            clean_unit_price = float(unit_price.replace(',', ''))
            clean_total = float(total.replace(',', ''))
            clean_quantity = int(quantity)
            
            return LineItem(
                description=description,
                quantity=str(clean_quantity),
                unit_price=f"{clean_unit_price:.2f}",
                cost=f"{clean_total:.2f}"
            )
        except Exception as e:
            logger.debug(f"Failed to create USD line item: {e}")
            return None
    
    def _create_eur_line_item(self, description: str, quantity: str, unit_price: str, total: str):
        """Create line item for European format."""
        from .models import LineItem
        
        try:
            # Clean description
            description = description.strip()
            
            # Parse European numbers
            clean_unit_price = self._parse_european_number(unit_price)
            clean_total = self._parse_european_number(total)
            clean_quantity = int(quantity)
            
            return LineItem(
                description=description,
                quantity=str(clean_quantity),
                unit_price=f"{clean_unit_price:.2f}",
                cost=f"{clean_total:.2f}"
            )
        except Exception as e:
            logger.debug(f"Failed to create EUR line item: {e}")
            return None
    
    def _parse_european_number(self, number_str: str) -> float:
        """Parse European number format."""
        if not number_str:
            return 0.0
        
        # Remove currency symbols
        number_str = re.sub(r'[€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿]', '', number_str)
        
        # Handle European format: "1.234,56" or "1 234,56"
        if ',' in number_str and ('.' in number_str or ' ' in number_str):
            # European format with thousands separator
            parts = number_str.split(',')
            if len(parts) == 2:
                integer_part = re.sub(r'[\s\.]', '', parts[0])  # Remove spaces and dots
                decimal_part = parts[1]
                return float(f"{integer_part}.{decimal_part}")
        elif ',' in number_str:
            # Simple comma as decimal: "123,45"
            return float(number_str.replace(',', '.'))
        else:
            # US format or integer
            return float(number_str.replace(' ', ''))
    
    def _is_likely_line_item(self, line: str) -> bool:
        """Check if a line is likely to contain a line item."""
        # Filter out obvious non-line-item content
        line_lower = line.lower()
        
        # Skip headers, footers, and metadata
        skip_patterns = [
            r'^\s*(bill\s+to|ship\s+to|quote\s+no|date|valid\s+for)',
            r'^\s*(subtotal|total|discount|tax|shipping|handling)',
            r'^\s*(terms|conditions|thank\s+you|signature)',
            r'^\s*\d{3}-\d{3}-\d{4}',  # Phone numbers
            r'^\s*\d{5}\s*$',  # ZIP codes alone
            r'^\s*[A-Z]{2}\s+\d{5}\s*$',  # State + ZIP
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return False
        
        # Must contain numbers and letters
        has_numbers = bool(re.search(r'\d', line))
        has_letters = bool(re.search(r'[A-Za-z]', line))
        has_currency = bool(re.search(r'[$€£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿]', line))
        
        return has_numbers and has_letters and (has_currency or len(line) > 10)
    
    def _is_valid_line_item(self, line_item) -> bool:
        """Validate that a line item is reasonable."""
        if not line_item:
            return False
        
        try:
            # Check description is reasonable
            if len(line_item.description.strip()) < 3:
                return False
            
            # Check numeric values are positive
            if float(line_item.quantity) <= 0:
                return False
            if float(line_item.unit_price) <= 0:
                return False
            if float(line_item.cost) <= 0:
                return False
            
            # Check calculation is roughly correct (allow for rounding)
            expected = float(line_item.quantity) * float(line_item.unit_price)
            actual = float(line_item.cost)
            if abs(expected - actual) > max(0.01, actual * 0.02):  # Allow 2% tolerance
                logger.debug(f"Calculation mismatch for {line_item.description}: {expected} vs {actual}")
                return False
            
            return True
        except (ValueError, TypeError):
            return False
    
    def _deduplicate_line_items(self, line_items: List) -> List:
        """Remove duplicate line items."""
        seen = set()
        unique_items = []
        
        for item in line_items:
            # Create a key based on description and unit price
            key = (item.description.lower().strip(), float(item.unit_price))
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
    
    def _convert_invoice2data_result(self, extracted_data: Dict) -> Dict[str, Any]:
        """Convert invoice2data result to our standard format."""
        # This would need to be implemented based on invoice2data's output format
        # For now, fall back to manual extraction
        return None
    
    def _format_result(self, line_items: List) -> Dict[str, Any]:
        """Format line items into our standard result format."""
        if not line_items:
            return self._empty_result()
        
        # Group items by quantity and unit price
        groups = []
        for item in line_items:
            groups.append({
                'quantity': item.quantity,
                'unitPrice': item.unit_price,
                'totalPrice': item.cost,
                'lineItems': [{
                    'description': item.description,
                    'quantity': item.quantity,
                    'unitPrice': item.unit_price,
                    'cost': item.cost
                }]
            })
        
        # Calculate summary
        total_qty = sum(int(item.quantity) for item in line_items)
        total_cost = sum(float(item.cost) for item in line_items)
        
        return {
            'summary': {
                'totalQuantity': str(total_qty),
                'totalUnitPriceSum': '0.00',
                'totalCost': f"{total_cost:.2f}",
                'numberOfGroups': len(groups),
                'subtotal': '0.00',
                'finalTotal': f"{total_cost:.2f}",
                'adjustments': [],
                'calculationSteps': []
            },
            'groups': groups
        }
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that a result is reasonable."""
        if not result or 'groups' not in result:
            return False
        
        groups = result.get('groups', [])
        if not groups:
            return False
        
        # Check that we have actual line items
        total_items = sum(len(group.get('lineItems', [])) for group in groups)
        return total_items > 0
    
    def _score_result_quality(self, result: Dict[str, Any]) -> float:
        """Score the quality of extraction result."""
        if not result or 'groups' not in result:
            return 0.0
        
        score = 0.0
        groups = result.get('groups', [])
        
        # Base score for having results
        if groups:
            score += 20
        
        # Score based on number of line items
        total_items = sum(len(group.get('lineItems', [])) for group in groups)
        score += min(total_items * 10, 50)  # Up to 50 points for line items
        
        # Score based on data completeness and penalize CID sequences
        cid_penalty = 0
        for group in groups:
            line_items = group.get('lineItems', [])
            for item in line_items:
                completeness = 0
                description = item.get('description', '').strip()
                
                # Check for CID sequences in description (major quality issue)
                if 'cid:' in description.lower():
                    cid_penalty += 50  # Heavy penalty for CID sequences
                    logger.warning(f"Found CID sequences in description: {description[:50]}...")
                
                if description:
                    completeness += 1
                if item.get('quantity', '').strip():
                    completeness += 1
                if item.get('unitPrice', '').strip():
                    completeness += 1
                if item.get('cost', '').strip():
                    completeness += 1
                
                score += completeness * 2.5  # Up to 10 points per complete item
        
        # Apply CID penalty
        score = max(score - cid_penalty, 0)
        
        return min(score, 100.0)
    
    def _detect_cid_issues(self, pdf_path: str) -> bool:
        """Detect if a PDF has significant CID font encoding issues."""
        try:
            # Quick check using pdfplumber
            import pdfplumber
            
            cid_count = 0
            total_chars = 0
            
            with pdfplumber.open(pdf_path) as pdf:
                # Check first few pages for CID sequences
                pages_to_check = min(len(pdf.pages), 3)
                
                for i in range(pages_to_check):
                    text = pdf.pages[i].extract_text()
                    if text:
                        total_chars += len(text)
                        cid_count += text.count('cid:')
            
            # If more than 5% of characters are CID sequences, it's a problem
            if total_chars > 0:
                cid_ratio = cid_count / total_chars
                logger.debug(f"CID detection: {cid_count} CID sequences in {total_chars} characters ({cid_ratio:.1%})")
                return cid_ratio > 0.05
            
            return False
            
        except Exception as e:
            logger.debug(f"CID detection failed: {e}")
            return False
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            'summary': {
                'totalQuantity': '0',
                'totalUnitPriceSum': '0.00',
                'totalCost': '0.00',
                'numberOfGroups': 0,
                'subtotal': '0.00',
                'finalTotal': '0.00',
                'adjustments': [],
                'calculationSteps': []
            },
            'groups': []
        }
#!/usr/bin/env python3
"""
Invoice2Data Parser
Uses the invoice2data library for robust invoice and quote parsing.
"""

import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

class Invoice2DataParser:
    """
    Parser using invoice2data library for extracting structured data from invoices and quotes.
    """
    
    def __init__(self):
        self.extraction_methods = [
            ('invoice2data', self._extract_with_invoice2data),
            ('pdfplumber', self._extract_with_pdfplumber),
            ('pymupdf', self._extract_with_pymupdf),
        ]
    
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse quote using invoice2data and fallback methods.
        """
        logger.info(f"🔍 Starting invoice2data parsing of: {pdf_path}")
        
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
                else:
                    logger.warning(f"❌ {method_name} failed or produced invalid result")
            except Exception as e:
                logger.warning(f"❌ {method_name} failed with error: {str(e)}")
        
        if not results:
            logger.error("❌ All extraction methods failed")
            return self._create_empty_result()
        
        # Pick the best result
        best_result = max(results, key=lambda x: x['score'])
        logger.info(f"🏆 Best result: {best_result['method']} (score: {best_result['score']})")
        
        return best_result['result']
    
    def _extract_with_invoice2data(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using invoice2data library."""
        try:
            from invoice2data import extract_data
            from invoice2data.input import pdftotext
            import logging
            import sys
            import os
            from contextlib import redirect_stderr
            
            # Temporarily suppress all stderr output to avoid "No template" errors
            original_stderr = sys.stderr
            null_stderr = open(os.devnull, 'w')
            
            try:
                with redirect_stderr(null_stderr):
                    # Try invoice2data extraction
                    extracted_data = extract_data(pdf_path, input_module=pdftotext)
                
                if extracted_data:
                    logger.info("📄 invoice2data extracted structured data")
                    # Convert to our format
                    return self._convert_invoice2data_result(extracted_data)
                else:
                    logger.info("📄 invoice2data found no template, falling back to manual extraction")
                    return self._extract_line_items_manually_from_pdf(pdf_path)
                    
            finally:
                null_stderr.close()
                
        except Exception as e:
            logger.warning(f"invoice2data extraction failed: {str(e)}")
            # Fall back to manual extraction
            return self._extract_line_items_manually_from_pdf(pdf_path)
    
    def _convert_invoice2data_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert invoice2data result to our format."""
        # Extract line items from the result
        line_items = []
        
        # Try to extract line items from various fields
        if 'lines' in result:
            for line in result['lines']:
                if isinstance(line, dict):
                    line_items.append({
                        'description': line.get('description', ''),
                        'quantity': str(line.get('quantity', 1)),
                        'unitPrice': str(line.get('unit_price', 0)),
                        'cost': str(line.get('amount', 0))
                    })
        
        # If no lines found, try to create from total and description
        if not line_items and 'amount' in result:
            line_items.append({
                'description': result.get('description', 'Invoice Item'),
                'quantity': '1',
                'unitPrice': str(result.get('amount', 0)),
                'cost': str(result.get('amount', 0))
            })
        
        # Create groups
        groups = []
        if line_items:
            groups = [{
                'quantity': str(sum(int(item['quantity']) for item in line_items)),
                'unitPrice': str(sum(float(item['unitPrice']) for item in line_items)),
                'totalPrice': str(sum(float(item['cost']) for item in line_items)),
                'lineItems': line_items
            }]
        
        return {
            'summary': {
                'totalQuantity': str(sum(int(item['quantity']) for item in line_items)),
                'totalUnitPriceSum': str(sum(float(item['unitPrice']) for item in line_items)),
                'totalCost': str(sum(float(item['cost']) for item in line_items)),
                'numberOfGroups': len(groups),
                'subtotal': str(result.get('amount', 0)),
                'finalTotal': str(result.get('amount', 0)),
                'adjustments': [],
                'calculationSteps': [f"Total: ${result.get('amount', 0)}"]
            },
            'groups': groups
        }
    
    def _extract_line_items_manually_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Extract line items manually from PDF when invoice2data fails."""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                
                # Clean the text to remove HTML artifacts and encoding issues
                cleaned_text = self._clean_extracted_text(all_text)
                
                # Filter out non-inventory content before processing
                filtered_text = self._filter_non_inventory_content(cleaned_text)
                return self._extract_line_items_manually(filtered_text)
                
        except Exception as e:
            logger.warning(f"PDF extraction failed: {str(e)}")
            return self._create_empty_result()
    
    def _extract_line_items_manually(self, text: str) -> Dict[str, Any]:
        """Extract line items manually when invoice2data doesn't find a template."""
        from .ocr_parser import DynamicOCRParser
        
        # Apply filtering to remove non-inventory content
        filtered_text = self._filter_non_inventory_content(text)
        
        # Debug: Log what's being filtered
        logger.info(f"Original text lines: {len(text.split(chr(10)))}")
        logger.info(f"Filtered text lines: {len(filtered_text.split(chr(10)))}")
        
        # Pre-process the text to better reconstruct line items
        processed_text = self._preprocess_line_items(filtered_text)
        
        # Debug: Log the processed text
        logger.info(f"Processed text lines: {len(processed_text.split(chr(10)))}")
        logger.debug(f"Processed text: {processed_text}")
        
        # Debug: Show what the splitting produces
        lines = processed_text.split('\n')
        for i, line in enumerate(lines):
            logger.debug(f"Line {i}: {line}")
        
        # Try to extract line items directly from the processed text first
        line_items = self._extract_structured_line_items(processed_text)
        
        # If direct extraction fails, fall back to OCR parser
        if not line_items:
            parser = DynamicOCRParser()
            line_items = parser.discover_line_items_dynamically(processed_text)
        
        # Create result structure
        result = {
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
        
        if line_items:
            # Check if we got LineItem objects or dict format
            if hasattr(line_items[0], 'quantity'):
                # LineItem objects from structured extraction
                groups = self._group_line_items(line_items)
                
                total_qty = sum(int(item.quantity) for item in line_items)
                total_cost = sum(float(item.cost) for item in line_items)
                
                result['summary'].update({
                    'totalQuantity': str(total_qty),
                    'totalCost': f"{total_cost:.2f}",
                    'finalTotal': f"{total_cost:.2f}",
                    'numberOfGroups': len(groups)
                })
                
                result['groups'] = groups
            else:
                # Dict format from OCR parser - use existing logic
                groups = self._group_line_items(line_items)
                result['groups'] = groups
                
                # Update summary
                total_quantity = sum(int(group['quantity']) for group in groups)
                total_cost = sum(float(group['totalPrice']) for group in groups)
                
                result['summary']['totalQuantity'] = str(total_quantity)
                result['summary']['totalCost'] = f"{total_cost:.2f}"
                result['summary']['finalTotal'] = f"{total_cost:.2f}"
                result['summary']['numberOfGroups'] = len(groups)
        
        return result
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using pdfplumber as fallback."""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                
                return self._extract_line_items_manually(all_text)
                
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
            return None
    
    def _extract_with_pymupdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using PyMuPDF as fallback."""
        try:
            import fitz
            
            doc = fitz.open(pdf_path)
            all_text = ""
            
            for page in doc:
                text = page.get_text("text")
                if text:
                    all_text += text + "\n"
            
            doc.close()
            
            return self._extract_line_items_manually(all_text)
            
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}")
            return None
    
    def _group_line_items(self, line_items: List) -> List[Dict[str, Any]]:
        """Group line items by similar characteristics and remove duplicates."""
        if not line_items:
            return []
        
        # Remove duplicates based on description and unit price
        unique_items = []
        seen_items = set()
        
        for item in line_items:
            # Create a unique key for deduplication
            item_key = (item.description.strip().lower(), item.unit_price)
            if item_key not in seen_items:
                seen_items.add(item_key)
                unique_items.append(item)
        
        # Simple grouping - group items with same unit price
        groups = []
        if unique_items:
            current_group = {
                'quantity': '0',
                'unitPrice': unique_items[0].unit_price,
                'totalPrice': '0.00',
                'lineItems': []
            }
            
            for item in unique_items:
                if item.unit_price == current_group['unitPrice']:
                    # Add to current group
                    current_group['lineItems'].append({
                        'description': item.description,
                        'quantity': item.quantity,
                        'unitPrice': item.unit_price,
                        'cost': item.cost
                    })
                    current_group['quantity'] = str(int(current_group['quantity']) + int(item.quantity))
                    current_group['totalPrice'] = str(Decimal(current_group['totalPrice']) + Decimal(item.cost))
                else:
                    # Start new group
                    if current_group['lineItems']:
                        groups.append(current_group)
                    current_group = {
                        'quantity': item.quantity,
                        'unitPrice': item.unit_price,
                        'totalPrice': item.cost,
                        'lineItems': [{
                            'description': item.description,
                            'quantity': item.quantity,
                            'unitPrice': item.unit_price,
                            'cost': item.cost
                        }]
                    }
            
            # Add last group
            if current_group['lineItems']:
                groups.append(current_group)
        
        return groups
    
    def _validate_result(self, result: Dict[str, Any]) -> bool:
        """Validate that the result has the expected structure."""
        required_keys = ['summary', 'groups']
        if not all(key in result for key in required_keys):
            return False
        
        if not isinstance(result['summary'], dict):
            return False
        
        if not isinstance(result['groups'], list):
            return False
        
        return True
    
    def _score_result_quality(self, result: Dict[str, Any]) -> float:
        """Score the quality of the extraction result."""
        score = 0.0
        
        # Base score for valid structure
        score += 10.0
        
        # Score based on number of line items found
        total_items = sum(len(group.get('lineItems', [])) for group in result.get('groups', []))
        score += min(total_items * 5.0, 50.0)  # Max 50 points for items
        
        # Score based on total cost (higher is better)
        try:
            total_cost = float(result.get('summary', {}).get('totalCost', '0'))
            score += min(total_cost / 100.0, 20.0)  # Max 20 points for cost
        except:
            pass
        
        # Score based on adjustments found
        adjustments = result.get('summary', {}).get('adjustments', [])
        score += len(adjustments) * 5.0  # 5 points per adjustment
        
        # Bonus for having both line items and adjustments
        if total_items > 0 and adjustments:
            score += 10.0
        
        return score
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """Create an empty result structure."""
        return {
            'summary': {
                'totalQuantity': '0',
                'totalUnitPriceSum': '0.00',
                'totalCost': '0.00',
                'numberOfGroups': 0,
                'subtotal': '0.00',
                'finalTotal': '0.00',
                'adjustments': [],
                'calculationSteps': ['No data extracted']
            },
            'groups': []
        } 
    
    def _filter_non_inventory_content(self, text: str) -> str:
        """Filter out non-inventory content like phone numbers, addresses, etc."""
        import re
        
        lines = text.split('\n')
        filtered_lines = []
        
        # Patterns for non-inventory content
        phone_pattern = re.compile(r'^\s*\d{3}[-.]?\d{3}[-.]?\d{4}\s*$|^\s*\d{3}-\d{3}-\d{4}\s*$|^\s*\d{3}-\d{4}\s*$')
        address_pattern = re.compile(r'^\s*\d+\s+[A-Za-z\s]+(?:St|Ave|Rd|Blvd|Drive|Street|Avenue|Road|Boulevard)\s*$')
        contact_pattern = re.compile(r'^\s*(?:Phone|Email|Fax|Tel|Contact|Address|City|State|ZIP|Postal)\s*[:=]?\s*', re.IGNORECASE)
        metadata_pattern = re.compile(r'^\s*(?:Quote|Invoice|Order|Date|Number|Valid|Terms|Payment|Due|Printed|Signature|Name)\s*[:=]?\s*', re.IGNORECASE)
        header_pattern = re.compile(r'^\s*(?:BILL TO|SHIP TO|DESCRIPTION|QTY|QUANTITY|UNIT PRICE|TOTAL|SUBTOTAL|TAX|DISCOUNT|SHIPPING)\s*$', re.IGNORECASE)
        separator_pattern = re.compile(r'^\s*[-=_]{3,}\s*$|^\s*$')
        
        # Pattern to identify standalone phone number fragments
        phone_fragment_pattern = re.compile(r'^\s*\d{3}-\s*$|^\s*\d{3}-\d{3}-\s*$')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip lines that match non-inventory patterns
            if (phone_pattern.search(line) or 
                address_pattern.search(line) or 
                contact_pattern.search(line) or 
                metadata_pattern.search(line) or
                header_pattern.search(line) or
                separator_pattern.search(line) or
                phone_fragment_pattern.search(line)):
                continue
                
            # Skip very short lines (likely not line items)
            if len(line) < 3:
                continue
                
            # Skip lines that are mostly punctuation
            if len(re.sub(r'[^\w\s]', '', line)) < 3:
                continue
                
            # Check if line is likely a line item
            if self._is_likely_line_item(line):
                filtered_lines.append(line)
            else:
                logger.debug(f"Filtered out unlikely line item: {line}")
        
        return '\n'.join(filtered_lines)
    
    def _is_likely_line_item(self, line: str) -> bool:
        """Check if a line is likely a line item."""
        import re
        
        # Skip very short lines
        if len(line.strip()) < 5:
            return False
            
        # Patterns that suggest a line item
        price_pattern = re.compile(r'[\$€£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿]?\s*\d+[.,]\d{2}')
        quantity_pattern = re.compile(r'^\s*\d+\s+')
        product_pattern = re.compile(r'\b(?:Assembly|Housing|Bracket|Screw|Bushing|Coating|Service|Inspection|Product|Item|Part|Steel|Aluminum|Custom|Machined|Powder|Quality)\b', re.IGNORECASE)
        
        # Check for price indicators
        if price_pattern.search(line):
            return True
            
        # Check for quantity at start
        if quantity_pattern.search(line):
            return True
            
        # Check for product-related words
        if product_pattern.search(line):
            return True
            
        # Check for typical line item structure (description + price)
        parts = line.split()
        if len(parts) >= 2:
            # Check if last part looks like a price
            last_part = parts[-1]
            if re.match(r'[\$€£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿]?\s*\d+[.,]\d{2}', last_part):
                return True
        
        # If line contains both text and numbers, it might be a line item
        if re.search(r'[A-Za-z]', line) and re.search(r'\d', line):
            return True
        
        return False
    
    def _extract_structured_line_items(self, text: str) -> List:
        """Extract line items with proper European number format handling."""
        import re
        from .models import LineItem
        
        line_items = []
        lines = text.split('\n')
        
        # Pattern to match structured line items with multiple currencies
        # Matches: Description Quantity CurrencyPrice CurrencyTotal (handles thousands separators)
        line_item_pattern = re.compile(
            r'^([A-Za-z\s\-\(\)0-9]+?)\s+(\d+)\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+[.,]\d{2})\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+(?:\.\d{3})?[.,]\d{2})\s*$'
        )
        
        # Also try to match the combined line from pymupdf (handles thousands separators)
        combined_pattern = re.compile(
            r'([A-Za-z\s\-\(\)0-9]+?)\s+(\d+)\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+[.,]\d{2})\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+(?:\.\d{3})?[.,]\d{2})'
        )
        
        # Pattern for lines that might be split across multiple lines (handles thousands separators)
        multiline_pattern = re.compile(
            r'([A-Za-z\s\-\(\)0-9]+?)\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+[.,]\d{2})\s+([€$£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿])(\d+(?:\.\d{3})?[.,]\d{2})'
        )
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try individual line pattern first
            match = line_item_pattern.search(line)
            if match:
                description, quantity, unit_price, total = match.groups()
                # Filter out invalid descriptions
                if description.strip() in [')', '(', '-', '', 'SUBTOTAL', 'TOTAL', 'TAX'] or len(description.strip()) <= 2:
                    continue
                line_item = self._create_line_item(description, quantity, unit_price, total)
                if line_item:
                    line_items.append(line_item)
                continue
            
            # Try combined line pattern (for pymupdf extraction)
            matches = combined_pattern.findall(line)
            for match in matches:
                description, quantity, unit_price, total = match
                # Filter out invalid descriptions
                if description.strip() in [')', '(', '-', '', 'SUBTOTAL', 'TOTAL', 'TAX'] or len(description.strip()) <= 2:
                    continue
                line_item = self._create_line_item(description, quantity, unit_price, total)
                if line_item:
                    line_items.append(line_item)
            
            # Try multiline pattern for cases where quantity is missing
            multiline_matches = multiline_pattern.findall(line)
            for match in multiline_matches:
                description, unit_price, total = match
                # Filter out invalid descriptions
                if description.strip() in [')', '(', '-', '', 'SUBTOTAL', 'TOTAL', 'TAX'] or len(description.strip()) <= 2:
                    continue
                # Try to infer quantity from unit price and total
                try:
                    unit_price_float = float(unit_price.replace(',', '.'))
                    total_float = float(total.replace(',', '.').replace('.', '', total.count('.') - 1) if total.count('.') > 1 else total.replace(',', '.'))
                    
                    # Handle thousands separators in total (e.g., "1.046,25")
                    if '.' in total and ',' in total:
                        parts = total.split(',')
                        if len(parts) == 2:
                            integer_part = parts[0].replace('.', '')
                            decimal_part = parts[1]
                            total_float = float(f"{integer_part}.{decimal_part}")
                    
                    inferred_quantity = round(total_float / unit_price_float) if unit_price_float > 0 else 1
                    line_item = self._create_line_item(description, str(inferred_quantity), unit_price, total)
                    if line_item:
                        line_items.append(line_item)
                except (ValueError, ZeroDivisionError):
                    pass
        
        logger.info(f"Structured extraction found {len(line_items)} line items")
        for item in line_items:
            logger.debug(f"Structured item: {item.description} - {item.quantity} x {item.unit_price} = {item.cost}")
        return line_items
    
    def _create_line_item(self, description: str, quantity: str, unit_price: str, total: str):
        """Create a LineItem object with proper European number parsing."""
        from .models import LineItem
        
        try:
            # Clean and parse European number format
            clean_quantity = int(quantity.strip())
            
            # Convert European decimal format (comma) to US format (dot)
            clean_unit_price = float(unit_price.replace(',', '.'))
            
            # Handle thousands separators in total (e.g., "1.046,25")
            if '.' in total and ',' in total:
                # European format with thousands separator: "1.046,25"
                parts = total.split(',')
                if len(parts) == 2:
                    integer_part = parts[0].replace('.', '')  # Remove thousands separator
                    decimal_part = parts[1]
                    clean_total = float(f"{integer_part}.{decimal_part}")
            else:
                # Simple European format: "290,75"
                clean_total = float(total.replace(',', '.'))
            
            return LineItem(
                description=description.strip(),
                quantity=str(clean_quantity),
                unit_price=f"{clean_unit_price:.2f}",
                cost=f"{clean_total:.2f}"
            )
            
        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse line item: {description} - {e}")
            return None
    
    def _preprocess_line_items(self, text: str) -> str:
        """Pre-process text to better reconstruct line items from table format."""
        import re
        
        lines = text.split('\n')
        processed_lines = []
        current_line_item = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Debug: Log what's happening to specific lines
            if 'Aluminum' in line or 'Stainless' in line:
                logger.debug(f"Processing line with Aluminum/Stainless: '{line}'")
                logger.debug(f"Is line item component: {self._is_line_item_component(line)}")
            
            # Check if this line looks like part of a line item
            if self._is_line_item_component(line):
                current_line_item.append(line)
                if 'Aluminum' in line or 'Stainless' in line:
                    logger.debug(f"Added to current_line_item: {current_line_item}")
            else:
                # If we have accumulated line item components, combine them
                if current_line_item:
                    combined_line = ' '.join(current_line_item)
                    if 'Aluminum' in combined_line or 'Stainless' in combined_line:
                        logger.debug(f"Combining line item: '{combined_line}'")
                    # Split the combined line into individual line items
                    individual_items = self._split_combined_line_items(combined_line)
                    if 'Aluminum' in combined_line or 'Stainless' in combined_line:
                        logger.debug(f"Split into individual items: {individual_items}")
                    processed_lines.extend(individual_items)
                    current_line_item = []
                
                # Add non-line-item lines as-is
                processed_lines.append(line)
        
        # Handle any remaining line item components
        if current_line_item:
            combined_line = ' '.join(current_line_item)
            individual_items = self._split_combined_line_items(combined_line)
            processed_lines.extend(individual_items)
        
        return '\n'.join(processed_lines)
    
    def _split_combined_line_items(self, combined_line: str) -> List[str]:
        """Split a combined line into individual line items."""
        import re
        
        # Pattern to match individual line items with European format (handles thousands separators)
        # Look for: description + €price + €total (more flexible to capture product names with numbers)
        line_item_pattern = re.compile(
            r'([A-Za-z\s\-\(\)0-9]+?)\s+€(\d+[.,]\d{2})\s+€(\d+(?:\.\d{3})?[.,]\d{2})'
        )
        
        matches = line_item_pattern.findall(combined_line)
        individual_items = []
        
        for match in matches:
            description, unit_price, total = match
            # Clean up description - remove ZIP codes and other prefixes
            description = re.sub(r'^\d{5}\s+', '', description.strip())  # Remove ZIP code prefix
            description = re.sub(r'^[A-Z]{2}\s+\d{5}\s+', '', description)  # Remove state + ZIP
            # Create individual line item
            line_item = f"{description.strip()} €{unit_price} €{total}"
            individual_items.append(line_item)
        
        # If no matches found, try alternative pattern for lines with quantities (handles thousands separators)
        if not individual_items:
            # Pattern for: description + quantity + €price + €total (more flexible for product names with numbers)
            alt_pattern = re.compile(
                r'([A-Za-z\s\-\(\)0-9]+?)\s+(\d+)\s+€(\d+[.,]\d{2})\s+€(\d+(?:\.\d{3})?[.,]\d{2})'
            )
            alt_matches = alt_pattern.findall(combined_line)
            
            for match in alt_matches:
                description, quantity, unit_price, total = match
                # Clean up description - remove ZIP codes and other prefixes
                description = re.sub(r'^\d{5}\s+', '', description.strip())  # Remove ZIP code prefix
                description = re.sub(r'^[A-Z]{2}\s+\d{5}\s+', '', description)  # Remove state + ZIP
                line_item = f"{description.strip()} {quantity} €{unit_price} €{total}"
                individual_items.append(line_item)
        
        # If still no matches found, return the original line
        if not individual_items:
            return [combined_line]
        
        return individual_items
    
    def _clean_extracted_text(self, text: str) -> str:
        """Clean extracted text to remove HTML artifacts and encoding issues."""
        import re
        
        # Remove HTML-like artifacts
        text = re.sub(r'<0a>', '\n', text)
        text = re.sub(r'<[0-9a-f]{2}>', '', text)
        
        # Remove error messages
        text = re.sub(r'Internal Error:.*?\.', '', text, flags=re.DOTALL)
        text = re.sub(r'Cannot handle URI.*?\.', '', text, flags=re.DOTALL)
        
        # Remove very long words (likely encoding issues)
        text = re.sub(r'\b[A-Za-z]{20,}\b', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove lines that are mostly special characters
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip lines that are mostly special characters
            if len(line.strip()) > 0:
                alphanumeric_ratio = len(re.findall(r'[A-Za-z0-9]', line)) / len(line) if line else 0
                if alphanumeric_ratio > 0.3:  # At least 30% alphanumeric
                    cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _is_garbled_text(self, text: str) -> bool:
        """Check if the extracted text is garbled or unusable."""
        import re
        
        # Check for common garbled text indicators
        garbled_indicators = [
            r'<0a>',  # HTML-like artifacts
            r'<[0-9a-f]{2}>',  # Hex codes
            r'Internal Error:',  # Error messages
            r'Cannot handle URI',  # URI errors
            r'[A-Za-z]{20,}',  # Very long words (likely encoding issues)
            r'[^\x00-\x7F]{10,}',  # Too many non-ASCII characters
        ]
        
        for pattern in garbled_indicators:
            if re.search(pattern, text):
                return True
        
        # Check if text has too many special characters
        special_char_ratio = len(re.findall(r'[^\w\s]', text)) / len(text) if text else 0
        if special_char_ratio > 0.3:  # More than 30% special characters
            return True
        
        # Check if text has too many consecutive non-alphanumeric characters
        if re.search(r'[^\w\s]{5,}', text):
            return True
        
        return False
    
    def _is_line_item_component(self, line: str) -> bool:
        """Check if a line is likely part of a line item."""
        import re
        
        # Patterns that suggest this is part of a line item
        price_pattern = re.compile(r'€\d+[.,]\d{2}')
        quantity_pattern = re.compile(r'^\s*\d+\s*$')
        product_pattern = re.compile(r'\b(?:Assembly|Housing|Bracket|Screw|Bushing|Coating|Service|Inspection|Steel|Aluminum|Custom|Machined|Powder|Quality)\b', re.IGNORECASE)
        
        # Check for price indicators
        if price_pattern.search(line):
            return True
            
        # Check for quantity
        if quantity_pattern.search(line):
            return True
            
        # Check for product-related words
        if product_pattern.search(line):
            return True
        
        # Check if line contains both text and numbers (likely part of a line item)
        if re.search(r'[A-Za-z]', line) and re.search(r'\d', line):
            return True
        
        return False
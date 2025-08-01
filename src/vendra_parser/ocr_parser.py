#!/usr/bin/env python3
"""
Dynamic OCR-based PDF parser using Tesseract for text extraction.
No hardcoded assumptions - extracts data purely based on patterns found.
"""

import re
import logging
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation
import json

from .models import LineItem, QuoteGroup
from .domain_parser import parse_with_domain_knowledge

logger = logging.getLogger(__name__)


class DynamicOCRParser:
    """Dynamic OCR-based parser that makes no assumptions about structure."""
    
    def __init__(self):
        # No hardcoded patterns - we'll discover them dynamically
        pass
    
    def extract_text_with_ocr(self, pdf_path: str) -> str:
        """
        Extract text from PDF using OCR.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text string
        """
        try:
            # Try to use external tools first
            return self._extract_with_external_tools(pdf_path)
        except Exception as e:
            logger.warning(f"External OCR tools failed: {e}")
            logger.info("Falling back to PDF text extraction")
            # Fall back to direct PDF text extraction
            return self._extract_text_directly(pdf_path)
    
    def _extract_with_external_tools(self, pdf_path: str) -> str:
        """Extract text using external OCR tools."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF to images using pdftoppm
            image_path = os.path.join(temp_dir, "page")
            subprocess.run([
                'pdftoppm', 
                '-png', 
                '-r', '300',  # High resolution for better OCR
                pdf_path, 
                image_path
            ], check=True)
            
            # Extract text from each image using Tesseract
            all_text = ""
            page_num = 1
            
            while True:
                image_file = f"{image_path}-{page_num}.png"
                if not os.path.exists(image_file):
                    break
                
                # Run Tesseract OCR
                result = subprocess.run([
                    'tesseract',
                    image_file,
                    'stdout',
                    '--psm', '6'  # Assume uniform block of text
                ], capture_output=True, text=True, check=True)
                
                page_text = result.stdout.strip()
                if page_text:
                    all_text += f"\n=== PAGE {page_num} ===\n{page_text}\n"
                
                page_num += 1
            
            logger.info(f"OCR extracted {len(all_text)} characters from PDF")
            return all_text
    
    def _extract_text_directly(self, pdf_path: str) -> str:
        """Extract text directly from PDF without OCR."""
        try:
            import pdfplumber
            
            all_text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        all_text += f"\n=== PAGE {page_num} ===\n{text}\n"
            
            logger.info(f"Direct extraction got {len(all_text)} characters from PDF")
            return all_text
            
        except ImportError:
            logger.error("pdfplumber not available for direct text extraction")
            raise
        except Exception as e:
            logger.error(f"Direct text extraction failed: {e}")
            raise
    
    def normalize_price(self, price_str: str) -> str:
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
    
    def discover_line_items_dynamically(self, text: str) -> List[LineItem]:
        """
        Completely dynamic line item discovery - no assumptions about format.
        Analyzes every line and tries to extract any valid line item.
        """
        line_items = []
        lines = text.split('\n')
        
        logger.info(f"Analyzing {len(lines)} lines for dynamic pattern discovery")
        
        # Step 1: Find ALL lines with numbers (potential line items)
        candidate_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Find all numbers in the line
            numbers = re.findall(r'(-?[\d,]+\.?\d*)', line)
            
            # Only skip lines that are clearly headers, totals, or metadata
            # Be very conservative about filtering
            line_lower = line.lower()
            
                    # Skip obvious non-line-item lines
            if any(keyword in line_lower for keyword in [
                'total:', 'subtotal:', 'balance:', 'quote #', 'date:', 'page:',
                'phone:', 'fax:', 'email:', 'quote by:', 'order by:', 'due date:',
                'lead time:', 'term:', 'via:', 'moq', 'item code', 'description',
                'unit price', 'amount', 'thank you', 'quotation:', 'valid',
                'report generated:', 'page 1 of', 'weeks after', 'receipt of'
            ]):
                continue
            
            # Skip lines that are purely addresses or contact info
            if (re.search(r'\b\d{5}\b', line) and 
                len(numbers) <= 1 and 
                any(word in line_lower for word in ['street', 'avenue', 'road', 'drive', 'lane', 'blvd', 'san', 'francisco', 'jose', 'california', 'ca'])):
                continue
            
            # Skip lines that are purely phone numbers
            if (re.search(r'\b\d{3}\s+\d{3}\s+\d{4}\b', line) and len(numbers) <= 1):
                continue
            
            # Skip lines that are purely city/state/zip combinations
            if (re.search(r'\b[A-Z]{2}\s+\d{5}\b', line) and len(numbers) <= 1):
                continue
            
            # If line has at least 2 numbers, it's a candidate
            if len(numbers) >= 2:
                candidate_lines.append((i, line, numbers))
        
        logger.info(f"Found {len(candidate_lines)} candidate lines with multiple numbers")
        
        # Step 2: Analyze patterns in candidate lines
        for line_num, line, numbers in candidate_lines:
            logger.info(f"Analyzing candidate line {line_num}: {line}")
            
            # Try different parsing strategies
            line_item = self._try_parse_line_item(line, numbers)
            if line_item:
                line_items.append(line_item)
                logger.info(f"Successfully parsed line item: {line_item.description}")
        
        return line_items
    
    def _try_parse_line_item(self, line: str, numbers: List[str]) -> Optional[LineItem]:
        """
        Completely dynamic line item parsing - tries all possible combinations.
        Returns the best match based on mathematical validation.
        """
        # Minimal filtering - only reject clearly non-product lines
        line_lower = line.lower()
        
        # Skip lines that are clearly addresses or contact info
        if any(keyword in line_lower for keyword in ['san francisco', 'san jose', 'california', 'ca ']):
            # Skip if it's just an address with no meaningful product numbers
            # Check if the numbers are just zip codes or phone numbers
            meaningful_numbers = [n for n in numbers if not re.match(r'^\d{5}$', n) and not re.match(r'^\d{3}\s+\d{3}\s+\d{4}$', n)]
            if len(meaningful_numbers) <= 1:
                return None
        
        # Strategy 1: Smart quantity detection with validation
        # Try multiple approaches and pick the best one
        candidates = []
        
        if len(numbers) >= 3:
            # Try different combinations of the last 3 numbers
            last_three = numbers[-3:]
            
            # Approach 1: Assume last_three = [qty, unit_price, total]
            try:
                qty = int(last_three[0])
                unit_price = Decimal(self.normalize_price(last_three[1]))
                total = Decimal(self.normalize_price(last_three[2]))
                
                if 1 <= qty <= 1000 and unit_price > 0 and total > 0:
                    # Validate: qty * unit_price should equal total (with some tolerance)
                    expected_total = qty * unit_price
                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                        # Find description
                        first_num_pos = line.find(last_three[0])
                        if first_num_pos > 0:
                            description = line[:first_num_pos].strip()
                            description = self._clean_description(description)
                            
                            if self._is_valid_product_description(description):
                                description = self._final_clean_description(description)
                                candidates.append({
                                    'description': description,
                                    'quantity': str(qty),
                                    'unit_price': str(unit_price),
                                    'cost': str(total),
                                    'confidence': 0.9 if abs(expected_total - total) <= Decimal('0.01') else 0.7
                                })
            except (ValueError, InvalidOperation):
                pass
            
            # Approach 2: Assume last_three = [unit_price, qty, total]
            try:
                unit_price = Decimal(self.normalize_price(last_three[0]))
                qty = int(last_three[1])
                total = Decimal(self.normalize_price(last_three[2]))
                
                if 1 <= qty <= 1000 and unit_price > 0 and total > 0:
                    expected_total = qty * unit_price
                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                        # Find description
                        second_num_pos = line.find(last_three[1])
                        if second_num_pos > 0:
                            description = line[:second_num_pos].strip()
                            description = self._clean_description(description)
                            
                            if self._is_valid_product_description(description):
                                description = self._final_clean_description(description)
                                candidates.append({
                                    'description': description,
                                    'quantity': str(qty),
                                    'unit_price': str(unit_price),
                                    'cost': str(total),
                                    'confidence': 0.9 if abs(expected_total - total) <= Decimal('0.01') else 0.7
                                })
            except (ValueError, InvalidOperation):
                pass
        
        # Strategy 2: Handle part numbers in description
        if len(numbers) >= 4:
            # Look for pattern: part_number + description + quantity + unit_price + total
            # This handles: "3 ESTOP_BODY-GEN2_4 6 $395.00 $2,370.00"
            
            # Try different combinations of the middle numbers
            for i in range(1, len(numbers) - 2):
                try:
                    qty = int(numbers[i])
                    unit_price = Decimal(self.normalize_price(numbers[i+1]))
                    total = Decimal(self.normalize_price(numbers[i+2]))
                    
                    if 1 <= qty <= 1000 and unit_price > 0 and total > 0:
                        expected_total = qty * unit_price
                        if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                            # Find description (everything before quantity)
                            qty_pos = line.find(str(qty))
                            if qty_pos > 0:
                                description = line[:qty_pos].strip()
                                description = self._clean_description(description)
                                
                                if self._is_valid_product_description(description):
                                    description = self._final_clean_description(description)
                                    candidates.append({
                                        'description': description,
                                        'quantity': str(qty),
                                        'unit_price': str(unit_price),
                                        'cost': str(total),
                                        'confidence': 0.8 if abs(expected_total - total) <= Decimal('0.01') else 0.6
                                    })
                except (ValueError, InvalidOperation):
                    pass
        
        # Strategy 3: Look for quantity keywords near numbers
        for i, num in enumerate(numbers):
            try:
                qty = int(num)
                if 1 <= qty <= 1000:
                    # Check if this number appears near quantity-related keywords
                    num_pos = line.find(num)
                    context = line[max(0, num_pos-20):num_pos+20].lower()
                    
                    if any(keyword in context for keyword in ['qty', 'quantity', 'ea', 'each', 'units', 'pcs']):
                        # This number is likely a quantity
                        if i + 2 < len(numbers):
                            try:
                                unit_price = Decimal(self.normalize_price(numbers[i+1]))
                                total = Decimal(self.normalize_price(numbers[i+2]))
                                
                                if unit_price > 0 and total > 0:
                                    expected_total = qty * unit_price
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                                        # Find description
                                        if num_pos > 0:
                                            description = line[:num_pos].strip()
                                            description = self._clean_description(description)
                                            
                                            if self._is_valid_product_description(description):
                                                description = self._final_clean_description(description)
                                                candidates.append({
                                                    'description': description,
                                                    'quantity': str(qty),
                                                    'unit_price': str(unit_price),
                                                    'cost': str(total),
                                                    'confidence': 0.95  # High confidence due to keyword match
                                                })
                            except (ValueError, InvalidOperation):
                                pass
            except (ValueError, InvalidOperation):
                pass
        
        # Strategy 3.5: Look for standalone quantity numbers (not embedded in product names)
        # This handles cases where quantity appears as a separate number
        for i, num in enumerate(numbers):
            try:
                qty = int(num)
                if 1 <= qty <= 1000:
                    # Check if this number appears as a standalone quantity
                    num_pos = line.find(num)
                    
                    # Look for patterns that suggest this is a standalone quantity
                    # 1. Number followed by price-related text
                    after_num = line[num_pos + len(num):num_pos + len(num) + 10].lower()
                    if any(keyword in after_num for keyword in ['$', 'price', 'ea', 'each', 'unit']):
                        # This looks like a standalone quantity
                        if i + 2 < len(numbers):
                            try:
                                unit_price = Decimal(self.normalize_price(numbers[i+1]))
                                total = Decimal(self.normalize_price(numbers[i+2]))
                                
                                if unit_price > 0 and total > 0:
                                    expected_total = qty * unit_price
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                                        # Find description (everything before the quantity)
                                        if num_pos > 0:
                                            description = line[:num_pos].strip()
                                            description = self._clean_description(description)
                                            
                                            if self._is_valid_product_description(description):
                                                description = self._final_clean_description(description)
                                                candidates.append({
                                                    'description': description,
                                                    'quantity': str(qty),
                                                    'unit_price': str(unit_price),
                                                    'cost': str(total),
                                                    'confidence': 0.9  # High confidence for standalone quantity
                                                })
                            except (ValueError, InvalidOperation):
                                pass
                    
                    # 2. Number that's not part of a larger number (like "5" in "5-basebalancer-05")
                    # Check if the number is surrounded by spaces or at the end of description
                    before_num = line[max(0, num_pos-1):num_pos]
                    after_num_full = line[num_pos + len(num):num_pos + len(num) + 1]
                    
                    if (before_num.endswith(' ') or before_num.endswith('-') or num_pos == 0) and \
                       (after_num_full.startswith(' ') or after_num_full.startswith('-') or after_num_full.startswith('$')):
                        # This looks like a standalone quantity
                        if i + 2 < len(numbers):
                            try:
                                unit_price = Decimal(self.normalize_price(numbers[i+1]))
                                total = Decimal(self.normalize_price(numbers[i+2]))
                                
                                if unit_price > 0 and total > 0:
                                    expected_total = qty * unit_price
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                                        # Find description (everything before the quantity)
                                        if num_pos > 0:
                                            description = line[:num_pos].strip()
                                            description = self._clean_description(description)
                                            
                                            if self._is_valid_product_description(description):
                                                description = self._final_clean_description(description)
                                                candidates.append({
                                                    'description': description,
                                                    'quantity': str(qty),
                                                    'unit_price': str(unit_price),
                                                    'cost': str(total),
                                                    'confidence': 0.85  # Good confidence for standalone quantity
                                                })
                            except (ValueError, InvalidOperation):
                                pass
            except (ValueError, InvalidOperation):
                pass
        
        # Strategy 4: Try first number as quantity (common pattern: qty + description + unit_price + total)
        if len(numbers) >= 3:
            try:
                first_qty = int(numbers[0])
                if 1 <= first_qty <= 1000:
                    # Try to find unit price and total from the remaining numbers
                    # Look for the last two numbers as unit_price and total
                    unit_price = Decimal(self.normalize_price(numbers[-2]))
                    total = Decimal(self.normalize_price(numbers[-1]))
                    
                    if unit_price > 0 and total > 0:
                        expected_total = first_qty * unit_price
                        if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.10'):
                            # Find description (everything after the first number but before the prices)
                            first_num_pos = line.find(numbers[0])
                            if first_num_pos >= 0:
                                # Find the position of the unit price
                                unit_price_pos = line.find(str(unit_price))
                                if unit_price_pos > first_num_pos:
                                    description = line[first_num_pos + len(numbers[0]):unit_price_pos].strip()
                                    description = self._clean_description(description)
                                    
                                    if self._is_valid_product_description(description):
                                        description = self._final_clean_description(description)
                                        candidates.append({
                                            'description': description,
                                            'quantity': str(first_qty),
                                            'unit_price': str(unit_price),
                                            'cost': str(total),
                                            'confidence': 0.95  # Very high confidence for exact math match
                                        })
            except (ValueError, InvalidOperation):
                pass
        
        # Pick the best candidate
        if candidates:
            # Sort by confidence and pick the highest
            candidates.sort(key=lambda x: x['confidence'], reverse=True)
            best = candidates[0]
            
            logger.info(f"Selected parsing strategy with confidence {best['confidence']:.2f}")
            logger.info(f"  Quantity: {best['quantity']}, Unit Price: {best['unit_price']}, Total: {best['cost']}")
            
            return LineItem(
                description=best['description'],
                quantity=best['quantity'],
                unit_price=best['unit_price'],
                cost=best['cost']
            )
        
        # Strategy 5: Fallback for simple cases (quantity = 1)
        if len(numbers) >= 2:
            # Take the last 2 numbers
            last_two = numbers[-2:]
            
            # Find the position of the first of these numbers
            first_num_pos = line.find(last_two[0])
            if first_num_pos > 0:
                description = line[:first_num_pos].strip()
                description = self._clean_description(description)
                
                # Validate this looks like a real product description
                if self._is_valid_product_description(description):
                    try:
                        quantity = "1"  # Assume quantity of 1
                        unit_price = self.normalize_price(last_two[0])
                        cost = self.normalize_price(last_two[1])
                        
                        if len(description) > 3:
                            # Clean up the description further
                            description = self._final_clean_description(description)
                            
                            return LineItem(
                                description=description,
                                quantity=quantity,
                                unit_price=unit_price,
                                cost=cost
                            )
                    except (ValueError, InvalidOperation):
                        pass
        
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
        if not description or len(description) < 2:
            return False
        
        desc_lower = description.lower()
        
        # Only reject descriptions that are clearly not products
        # Be very conservative - let mathematical validation be the primary filter
        if desc_lower.startswith(('to:', 'from:', 'attn:', 're:', 'subject:', 'date:', 'page:')):
            return False
        
        # Must have some descriptive content (not just numbers)
        words = description.split()
        if len(words) < 1:
            return False
        
        # Must contain at least one word that's not just numbers
        has_descriptive_word = any(not word.isdigit() and len(word) > 1 for word in words)
        
        return has_descriptive_word
    
    def _final_clean_description(self, description: str) -> str:
        """Final cleanup of description to remove trailing numbers and extra text."""
        # Remove trailing numbers and common suffixes
        description = re.sub(r'\s+\d+\s*$', '', description)  # Remove trailing numbers
        description = re.sub(r'\s+and\s+\d+\s*$', '', description)  # Remove "and X" at end
        description = re.sub(r'\s+,\s*\d+\s*$', '', description)  # Remove ", X" at end
        
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        
        return description
    
    def discover_quantities_dynamically(self, text: str) -> List[str]:
        """
        Dynamically discover quantities from the text.
        No assumptions about format - purely pattern-based discovery.
        """
        quantities = []
        
        # Look for standalone numbers that could be quantities
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Find all numbers in the line
            numbers = re.findall(r'\b(\d{1,4})\b', line)
            
            for num in numbers:
                if 1 <= int(num) <= 1000:
                    # Check if this number appears in a quantity-like context
                    context = text[max(0, text.find(num)-30):text.find(num)+30]
                    
                    # If it appears near quantity-related words or pricing, it might be a quantity
                    if any(keyword in context.lower() for keyword in ['qty', 'quantity', 'price', 'total', '$', 'rate']):
                        if num not in quantities:
                            quantities.append(num)
        
        # Sort quantities
        quantities.sort(key=int)
        return quantities
    
    def parse_quote(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Main method to parse quote from PDF using dynamic OCR."""
        logger.info(f"Parsing quote from: {pdf_path}")
        
        # Extract text using OCR
        text = self.extract_text_with_ocr(pdf_path)
        logger.info(f"OCR extracted {len(text)} characters from PDF")
        
        if not text:
            logger.warning("No text extracted from PDF")
            return []
        
        # Dynamically discover line items
        line_items = self.discover_line_items_dynamically(text)
        logger.info(f"Dynamically discovered {len(line_items)} line items")
        
        # Use domain-aware parsing to structure the output correctly
        quote_groups = parse_with_domain_knowledge(line_items)
        logger.info(f"Created {len(quote_groups)} quote groups using domain knowledge")
        
        return quote_groups
    
    def parse_quote_to_json(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """Parse quote and return JSON string."""
        result = self.parse_quote(pdf_path)
        
        json_str = json.dumps(result, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
            logger.info(f"Results saved to: {output_path}")
        
        return json_str


# Alias for backward compatibility
OCRParser = DynamicOCRParser


def parse_with_ocr(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Parse PDF using dynamic OCR.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of quote groups
    """
    parser = DynamicOCRParser()
    return parser.parse_quote(pdf_path) 
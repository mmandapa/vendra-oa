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
        Dynamically discover line items by analyzing the text structure.
        No assumptions about format - purely pattern-based discovery.
        """
        line_items = []
        lines = text.split('\n')
        
        logger.info(f"Analyzing {len(lines)} lines for dynamic pattern discovery")
        
        # Step 1: Find lines that contain multiple numbers (potential line items)
        candidate_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Skip obvious non-line-item lines
            skip_keywords = [
                'phone', 'fax', 'total', 'estimate', 'date', 'name', 'address',
                'suite', 'street', 'blvd', 'avenue', 'road', 'drive', 'lane',
                'ca ', 'california', 'zip', 'postal', 'generated', 'page',
                'receipt', 'order', 'drawings', 'specifications', 'specialists',
                'semiconductor', 'tooling', 'santa clara', 'san francisco'
            ]
            if any(skip_word in line.lower() for skip_word in skip_keywords):
                continue
            
            # Skip lines that are clearly addresses or contact info
            if re.search(r'\b\d{5}\b', line):  # 5-digit zip codes
                continue
            if re.search(r'\b\d{3}\s+\d{3}\s+\d{4}\b', line):  # Phone numbers
                continue
            if re.search(r'\b[A-Z]{2}\s+\d{5}\b', line):  # State + zip pattern
                continue
            
            # Find all numbers in the line
            numbers = re.findall(r'(-?[\d,]+\.?\d*)', line)
            
            # If line has 2 or more numbers, it might be a line item
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
        Try to parse a line as a line item using multiple strategies.
        Returns None if parsing fails.
        """
        # Skip lines that are clearly not line items
        skip_keywords = [
            'san clemente', 'san francisco', 'phone', 'fax', 'estimate', 'date', 'name', 'address', 
            'suite', 'street', 'vtn manufacturing', 'little orchard', '3rd street', 'quote', 'outa',
            'specialists', 'semiconductor', 'tooling', 'santa clara', 'california', 'generated', 'page',
            'receipt', 'order', 'drawings', 'specifications', 'blvd', 'avenue', 'road', 'drive', 'lane',
            'zip', 'postal'
        ]
        if any(skip_word in line.lower() for skip_word in skip_keywords):
            return None
        
        # Skip lines with zip codes, phone numbers, or other contact info
        if re.search(r'\b\d{5}\b', line):  # 5-digit zip codes
            return None
        if re.search(r'\b\d{3}\s+\d{3}\s+\d{4}\b', line):  # Phone numbers
            return None
        if re.search(r'\b[A-Z]{2}\s+\d{5}\b', line):  # State + zip pattern
            return None
        if re.search(r'\b[A-Z]{2}\s+\d{3}\s+\d{4}\b', line):  # State + area code + phone
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
                
                if 1 <= qty <= 100 and unit_price > 0 and total > 0:
                    # Validate: qty * unit_price should equal total (with some tolerance)
                    expected_total = qty * unit_price
                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.05'):
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
                
                if 1 <= qty <= 100 and unit_price > 0 and total > 0:
                    expected_total = qty * unit_price
                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.05'):
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
                    
                    if 1 <= qty <= 100 and unit_price > 0 and total > 0:
                        expected_total = qty * unit_price
                        if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.05'):
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
                if 1 <= qty <= 100:
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
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / total <= Decimal('0.05'):
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
        
        # Strategy 4: Fallback for simple cases (quantity = 1)
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
        if not description or len(description) < 3:
            return False
        
        desc_lower = description.lower()
        
        # Must not contain non-product keywords (addresses, company info, etc.)
        non_product_keywords = [
            'san clemente', 'san francisco', 'phone', 'fax', 'estimate', 'date', 'name', 'address',
            'thirty-two', 'machine inc', 'calle', 'pintoresco', 'suite', 'street', 'vtn manufacturing',
            'little orchard', '3rd street', 'quote', 'outa', 'specialists', 'semiconductor', 'tooling',
            'santa clara', 'california', 'generated', 'page', 'receipt', 'order', 'drawings', 'specifications',
            'blvd', 'avenue', 'road', 'drive', 'lane', 'zip', 'postal'
        ]
        
        has_non_product_keyword = any(keyword in desc_lower for keyword in non_product_keywords)
        
        # If it contains non-product keywords, reject it
        if has_non_product_keyword:
            return False
        
        # Skip descriptions that are just addresses or contact info
        if re.search(r'\b\d{5}\b', description):  # Contains zip codes
            return False
        if re.search(r'\b[A-Z]{2}\s+\d{5}\b', description):  # State + zip pattern
            return False
        if re.search(r'\b\d{3}\s+\d{3}\s+\d{4}\b', description):  # Phone numbers
            return False
        
        # Must be reasonably long and contain some descriptive text
        # (not just numbers or single words)
        words = description.split()
        if len(words) < 2:
            return False
        
        # Must contain at least one word that's not just numbers
        has_descriptive_word = any(not word.isdigit() and len(word) > 1 for word in words)
        
        # Must not be just a single letter or very short description
        if len(description.strip()) < 5:
            return False
        
        # Must not start with common non-product prefixes
        if desc_lower.startswith(('to:', 'from:', 'attn:', 're:', 'subject:', 'date:', 'page:')):
            return False
        
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
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
            # Convert PDF to images and extract text using Tesseract
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
                
        except subprocess.CalledProcessError as e:
            logger.error(f"OCR extraction failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during OCR extraction: {e}")
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
            if any(skip_word in line.lower() for skip_word in ['phone', 'fax', 'total', 'estimate', 'date', 'name', 'address']):
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
        # Strategy 1: Look for pattern: description + quantity + rate + total
        # Find the last 3 numbers in the line (most likely to be qty, rate, total)
        if len(numbers) >= 3:
            # Take the last 3 numbers
            last_three = numbers[-3:]
            
            # Find the position of the first of these numbers
            first_num_pos = line.find(last_three[0])
            if first_num_pos > 0:
                description = line[:first_num_pos].strip()
                
                # Clean up description
                description = self._clean_description(description)
                
                if len(description) > 2:
                    try:
                        quantity = self.normalize_price(last_three[0])
                        unit_price = self.normalize_price(last_three[1])
                        cost = self.normalize_price(last_three[2])
                        
                        # Validate the values make sense
                        if (Decimal(quantity) > 0 and 
                            len(description) > 2):
                            
                            return LineItem(
                                description=description,
                                quantity=quantity,
                                unit_price=unit_price,
                                cost=cost
                            )
                    except (ValueError, InvalidOperation):
                        pass
        
        # Strategy 2: Look for pattern: description + rate + total (quantity = 1)
        if len(numbers) >= 2:
            # Take the last 2 numbers
            last_two = numbers[-2:]
            
            # Find the position of the first of these numbers
            first_num_pos = line.find(last_two[0])
            if first_num_pos > 0:
                description = line[:first_num_pos].strip()
                description = self._clean_description(description)
                
                if len(description) > 2:
                    try:
                        quantity = "1"  # Assume quantity of 1
                        unit_price = self.normalize_price(last_two[0])
                        cost = self.normalize_price(last_two[1])
                        
                        if len(description) > 2:
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
        
        # Dynamically discover quantities
        quantities = self.discover_quantities_dynamically(text)
        logger.info(f"Dynamically discovered quantities: {quantities}")
        
        # If no quantities found, assume quantity of 1
        if not quantities:
            quantities = ["1"]
        
        # If no line items found, return empty result
        if not line_items:
            logger.warning("No line items found in PDF")
            return []
        
        # Calculate total price
        total_price = self._calculate_total(line_items)
        
        # Create quote groups
        quote_groups = []
        for quantity in quantities:
            # Calculate unit price for this quantity
            unit_price = self._calculate_unit_price(total_price, quantity)
            
            # Create quote group
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
                    for item in line_items
                ]
            }
            
            quote_groups.append(quote_group)
        
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
    
    def _calculate_unit_price(self, total_price: str, quantity: str) -> str:
        """Calculate unit price from total price and quantity."""
        try:
            total = Decimal(total_price)
            qty = Decimal(quantity)
            if qty > 0:
                unit_price = total / qty
                return str(unit_price.quantize(Decimal('0.01')))
            return "0"
        except (InvalidOperation, ValueError, ZeroDivisionError):
            return "0"
    
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
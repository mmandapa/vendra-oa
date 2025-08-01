#!/usr/bin/env python3
"""
Advanced Vendra Quote Parser
Enhanced parser with sophisticated pattern matching and fallback strategies.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation
import pdfplumber
import click
from collections import defaultdict

from .models import LineItem, QuoteGroup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedQuoteParser:
    """Advanced parser with sophisticated pattern matching and fallback strategies."""
    
    def __init__(self):
        # Enhanced price patterns
        self.price_patterns = [
            r'\$?\s*([\d,]+\.?\d*)',  # $1,234.56 or 1234.56
            r'([\d,]+\.?\d*)\s*USD',  # 1,234.56 USD
            r'([\d,]+\.?\d*)\s*\$',  # 1,234.56 $
            r'([\d,]+\.?\d*)\s*per\s*unit',  # 1,234.56 per unit
            r'([\d,]+\.?\d*)\s*each',  # 1,234.56 each
        ]
        
        # Enhanced quantity patterns
        self.quantity_patterns = [
            r'qty[:\s]*(\d+)',
            r'quantity[:\s]*(\d+)',
            r'(\d+)\s*(?:pcs?|pieces?|units?)',
            r'(\d+)\s*ea',
            r'(\d+)\s*per\s*quote',
            r'quote\s*for\s*(\d+)',
        ]
        
        # Enhanced line item patterns
        self.line_item_patterns = [
            # Standard format: DESCRIPTION QTY UNIT_PRICE TOTAL
            r'^([A-Z\s]+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
            r'^([A-Z\s]+)\s+(\d+)\s+\$?([\d,]+\.?\d*)\s+\$?([\d,]+\.?\d*)$',
            # Tabular format
            r'^([A-Z\s]+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)\s*$',
            # With currency symbols
            r'^([A-Z\s]+)\s+(\d+)\s+\$([\d,]+\.?\d*)\s+\$([\d,]+\.?\d*)$',
        ]
        
        # Common line item keywords with variations
        self.line_item_keywords = {
            'BASE': ['BASE', 'BASIC', 'STANDARD'],
            'SOLDER': ['SOLDER', 'SOLDERING', 'SOLDER ASSEMBLY'],
            'TOOLING': ['TOOLING', 'TOOLS', 'TOOL SETUP'],
            'MATERIAL': ['MATERIAL', 'MATERIALS', 'RAW MATERIAL'],
            'LABOR': ['LABOR', 'LABOUR', 'WORK'],
            'SETUP': ['SETUP', 'SET UP', 'INITIAL SETUP'],
            'MACHINING': ['MACHINING', 'MACHINE', 'CNC'],
            'ASSEMBLY': ['ASSEMBLY', 'ASSEMBLE'],
            'FINISHING': ['FINISHING', 'FINISH', 'SURFACE FINISH'],
            'PACKAGING': ['PACKAGING', 'PACKAGE', 'PACK'],
            'SHIPPING': ['SHIPPING', 'SHIP', 'DELIVERY'],
            'DESIGN': ['DESIGN', 'ENGINEERING'],
            'PROTOTYPE': ['PROTOTYPE', 'PROTO'],
            'TESTING': ['TESTING', 'TEST', 'QUALITY'],
        }

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file with enhanced error handling."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for i, page in enumerate(pdf.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += f"=== PAGE {i+1} ===\n{page_text}\n"
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {i+1}: {e}")
                        continue
                return text
        except Exception as e:
            logger.error(f"Error opening PDF file: {e}")
            raise

    def normalize_price(self, price_str: str) -> str:
        """Enhanced price normalization with better error handling."""
        if not price_str:
            return "0"
        
        # Remove currency symbols and extra whitespace
        price_str = re.sub(r'[\$\€\£\¥]', '', price_str.strip())
        
        # Remove commas from numbers
        price_str = re.sub(r',', '', price_str)
        
        # Extract numeric value with decimal support
        match = re.search(r'([\d]+\.?\d*)', price_str)
        if match:
            try:
                value = Decimal(match.group(1))
                return str(value.quantize(Decimal('0.01')))
            except InvalidOperation:
                logger.warning(f"Invalid price format: {price_str}")
                return "0"
        
        return "0"

    def extract_quantities(self, text: str) -> List[str]:
        """Enhanced quantity extraction with context analysis."""
        quantities = []
        
        # Look for explicit quantity patterns
        for pattern in self.quantity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            quantities.extend(matches)
        
        # Look for quantity tables or structured data
        # Pattern: Qty: 1, 3, 5 or similar
        table_patterns = [
            r'qty[:\s]*(\d+)[,\s]*(\d+)[,\s]*(\d+)',
            r'quantity[:\s]*(\d+)[,\s]*(\d+)[,\s]*(\d+)',
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                quantities.extend(match)
        
        # Look for standalone numbers in pricing context
        lines = text.split('\n')
        for line in lines:
            # Check if line contains pricing information
            if any(keyword in line.upper() for keyword in ['PRICE', 'TOTAL', '$', 'COST']):
                numbers = re.findall(r'\b(\d{1,4})\b', line)
                for num in numbers:
                    if 1 <= int(num) <= 1000 and num not in quantities:
                        quantities.append(num)
        
        # Remove duplicates and sort
        quantities = list(set(quantities))
        quantities.sort(key=int)
        
        # If no quantities found, look for any reasonable numbers
        if not quantities:
            all_numbers = re.findall(r'\b(\d{1,3})\b', text)
            for num in all_numbers:
                if 1 <= int(num) <= 100 and num not in quantities:
                    quantities.append(num)
        
        return quantities[:5]  # Limit to first 5 quantities

    def extract_line_items(self, text: str) -> List[LineItem]:
        """Enhanced line item extraction with multiple strategies."""
        line_items = []
        lines = text.split('\n')
        
        # Strategy 1: Pattern matching
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to match structured patterns
            for pattern in self.line_item_patterns:
                match = re.match(pattern, line)
                if match:
                    description = match.group(1).strip()
                    quantity = match.group(2)
                    unit_price = self.normalize_price(match.group(3))
                    cost = self.normalize_price(match.group(4))
                    
                    line_items.append(LineItem(
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        cost=cost
                    ))
                    break
        
        # Strategy 2: Keyword-based extraction
        if not line_items:
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                for category, keywords in self.line_item_keywords.items():
                    for keyword in keywords:
                        if keyword in line.upper():
                            # Extract numbers from the line
                            numbers = re.findall(r'[\d,]+\.?\d*', line)
                            if len(numbers) >= 2:
                                try:
                                    description = category
                                    quantity = "1"  # Default quantity
                                    unit_price = self.normalize_price(numbers[0])
                                    cost = self.normalize_price(numbers[1])
                                    
                                    # Avoid duplicates
                                    if not any(item.description == description for item in line_items):
                                        line_items.append(LineItem(
                                            description=description,
                                            quantity=quantity,
                                            unit_price=unit_price,
                                            cost=cost
                                        ))
                                except (IndexError, ValueError):
                                    continue
                            break
        
        # Strategy 3: Table-like structure detection
        if not line_items:
            # Look for lines that look like table rows
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if line has multiple numbers separated by spaces
                parts = line.split()
                if len(parts) >= 4:
                    numbers = []
                    description_parts = []
                    
                    for part in parts:
                        if re.match(r'[\d,]+\.?\d*', part):
                            numbers.append(part)
                        else:
                            description_parts.append(part)
                    
                    if len(numbers) >= 2 and description_parts:
                        description = ' '.join(description_parts).strip()
                        quantity = "1"
                        unit_price = self.normalize_price(numbers[0])
                        cost = self.normalize_price(numbers[1])
                        
                        line_items.append(LineItem(
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            cost=cost
                        ))
        
        return line_items

    def calculate_total_price(self, line_items: List[LineItem]) -> str:
        """Calculate total price from line items with validation."""
        total = Decimal('0')
        for item in line_items:
            try:
                cost = Decimal(item.cost)
                # Include all costs, including negative ones (for discounts, COD, etc.)
                total += cost
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid cost value: {item.cost}")
        
        return str(total.quantize(Decimal('0.01')))

    def calculate_unit_price(self, total_price: str, quantity: str) -> str:
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

    def parse_quote(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Main method to parse quote from PDF and return structured data."""
        logger.info(f"Parsing quote from: {pdf_path}")
        
        # Extract text from PDF
        text = self.extract_text_from_pdf(pdf_path)
        logger.info(f"Extracted {len(text)} characters from PDF")
        
        # Extract quantities
        quantities = self.extract_quantities(text)
        logger.info(f"Found quantities: {quantities}")
        
        # Extract line items
        line_items = self.extract_line_items(text)
        logger.info(f"Found {len(line_items)} line items")
        
        # If no quantities found, assume quantity of 1
        if not quantities:
            quantities = ["1"]
        
        # If no line items found, return empty result
        if not line_items:
            logger.warning("No line items found in PDF")
            return []
        
        # Create quote groups
        quote_groups = []
        for quantity in quantities:
            # Calculate total price for this quantity
            total_price = self.calculate_total_price(line_items)
            
            # Calculate unit price
            unit_price = self.calculate_unit_price(total_price, quantity)
            
            # Create quote group
            quote_group = QuoteGroup(
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
                line_items=line_items
            )
            
            quote_groups.append(quote_group)
        
        # Convert to JSON-serializable format
        result = []
        for group in quote_groups:
            group_dict = {
                "quantity": group.quantity,
                "unitPrice": group.unit_price,
                "totalPrice": group.total_price,
                "lineItems": [
                    {
                        "description": item.description,
                        "quantity": item.quantity,
                        "unitPrice": item.unit_price,
                        "cost": item.cost
                    }
                    for item in group.line_items
                ]
            }
            result.append(group_dict)
        
        return result

    def parse_quote_to_json(self, pdf_path: str, output_path: Optional[str] = None) -> str:
        """Parse quote and return JSON string, optionally save to file."""
        result = self.parse_quote(pdf_path)
        
        json_str = json.dumps(result, indent=2)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(json_str)
            logger.info(f"Results saved to: {output_path}")
        
        return json_str


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output JSON file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def main(pdf_path: str, output: Optional[str], verbose: bool):
    """Parse supplier quote PDF and extract structured data using advanced parser."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        parser = AdvancedQuoteParser()
        result = parser.parse_quote_to_json(pdf_path, output)
        
        if not output:
            print(result)
        
        click.echo("Advanced quote parsing completed successfully!")
        
    except Exception as e:
        click.echo(f"Error parsing quote: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main() 
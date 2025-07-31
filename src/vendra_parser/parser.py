#!/usr/bin/env python3
"""
Vendra Quote Parser
A robust parser for extracting structured quote data from supplier PDFs.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, InvalidOperation
import click

from .models import LineItem, QuoteGroup
from .pdf_extractor import extract_pdf_text, extract_pdf_tables

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuoteParser:
    """Main parser class for extracting quote data from PDFs."""
    
    def __init__(self):
        # Common patterns for extracting pricing information
        self.price_patterns = [
            r'\$?([\d,]+\.?\d*)',  # $1,234.56 or 1234.56
            r'([\d,]+\.?\d*)\s*USD',  # 1,234.56 USD
            r'([\d,]+\.?\d*)\s*\$',  # 1,234.56 $
        ]
        
        # Patterns for quantity detection
        self.quantity_patterns = [
            r'qty[:\s]*(\d+)',
            r'quantity[:\s]*(\d+)',
            r'(\d+)\s*(?:pcs?|pieces?|units?)',
            r'(\d+)\s*ea',
        ]
        
        # Patterns for line item detection
        self.line_item_patterns = [
            r'^([A-Z\s]+)\s+(\d+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)$',
            r'^([A-Z\s]+)\s+(\d+)\s+\$?([\d,]+\.?\d*)\s+\$?([\d,]+\.?\d*)$',
        ]
        
        # Common line item keywords
        self.line_item_keywords = [
            'BASE', 'SOLDER', 'TOOLING', 'MATERIAL', 'LABOR', 'SETUP',
            'MACHINING', 'ASSEMBLY', 'FINISHING', 'PACKAGING', 'SHIPPING'
        ]

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF file using enhanced extractor."""
        try:
            text = extract_pdf_text(pdf_path)
            if not text:
                logger.warning("No text extracted from PDF")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise

    def normalize_price(self, price_str: str) -> str:
        """Normalize price string by removing currency symbols and formatting."""
        if not price_str:
            return "0"
        
        # Remove currency symbols and extra whitespace
        price_str = re.sub(r'[\$\€\£\¥]', '', price_str.strip())
        
        # Remove commas from numbers
        price_str = re.sub(r',', '', price_str)
        
        # Extract numeric value
        match = re.search(r'([\d]+\.?\d*)', price_str)
        if match:
            try:
                # Convert to Decimal for precise arithmetic
                value = Decimal(match.group(1))
                return str(value)
            except InvalidOperation:
                logger.warning(f"Invalid price format: {price_str}")
                return "0"
        
        return "0"

    def extract_quantities(self, text: str) -> List[str]:
        """Extract quantity values from text."""
        quantities = []
        
        # Look for quantity patterns
        for pattern in self.quantity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            quantities.extend(matches)
        
        # Also look for standalone numbers that might be quantities
        # (numbers between 1-1000 that appear in context of pricing)
        number_matches = re.findall(r'\b(\d{1,4})\b', text)
        for num in number_matches:
            if 1 <= int(num) <= 1000 and num not in quantities:
                # Check if this number appears near pricing context
                context = text[max(0, text.find(num)-50):text.find(num)+50]
                if any(keyword in context.upper() for keyword in ['QTY', 'QUANTITY', 'PRICE', 'TOTAL', '$']):
                    quantities.append(num)
        
        # Remove duplicates and sort
        quantities = list(set(quantities))
        quantities.sort(key=int)
        
        return quantities

    def extract_line_items(self, text: str) -> List[LineItem]:
        """Extract line items from text."""
        line_items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to match line item patterns
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
            
            # If no pattern match, try to extract by keywords
            if not any(item.description in line for item in line_items):
                for keyword in self.line_item_keywords:
                    if keyword in line.upper():
                        # Try to extract numbers from the line
                        numbers = re.findall(r'[\d,]+\.?\d*', line)
                        if len(numbers) >= 2:
                            try:
                                description = keyword
                                quantity = "1"  # Default quantity
                                unit_price = self.normalize_price(numbers[0])
                                cost = self.normalize_price(numbers[1])
                                
                                line_items.append(LineItem(
                                    description=description,
                                    quantity=quantity,
                                    unit_price=unit_price,
                                    cost=cost
                                ))
                            except (IndexError, ValueError):
                                continue
                        break
        
        return line_items

    def calculate_total_price(self, line_items: List[LineItem]) -> str:
        """Calculate total price from line items."""
        total = Decimal('0')
        for item in line_items:
            try:
                total += Decimal(item.cost)
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid cost value: {item.cost}")
        
        return str(total)

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
    """Parse supplier quote PDF and extract structured data."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        parser = QuoteParser()
        result = parser.parse_quote_to_json(pdf_path, output)
        
        if not output:
            print(result)
        
        click.echo("Quote parsing completed successfully!")
        
    except Exception as e:
        click.echo(f"Error parsing quote: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main() 
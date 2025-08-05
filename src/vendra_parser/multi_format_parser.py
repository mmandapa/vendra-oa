#!/usr/bin/env python3
"""
Multi-Format PDF Parser
Uses multiple libraries to handle different PDF formats:
- pdfplumber: For table-based documents
- PyMuPDF: For text-based documents  
- tabula-py: For complex tables
- camelot-py: For irregular layouts
- pdf2image + OCR: For scanned documents
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

class MultiFormatPDFParser:
    """
    Advanced PDF parser that uses multiple libraries to handle different PDF formats.
    Tries different extraction methods and picks the best result.
    """
    
    def __init__(self):
        self.extraction_methods = [
            ('pdfplumber', self._extract_with_pdfplumber),
            ('pymupdf', self._extract_with_pymupdf),
            ('ocr', self._extract_with_ocr),
        ]
    
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse quote using multiple extraction methods and return the best result.
        """
        logger.info(f"🔍 Starting multi-format parsing of: {pdf_path}")
        
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
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using pdfplumber - best for table-based documents."""
        try:
            import pdfplumber
            
            with pdfplumber.open(pdf_path) as pdf:
                all_text = ""
                tables = []
                
                for page in pdf.pages:
                    # Extract text
                    text = page.extract_text()
                    if text:
                        all_text += text + "\n"
                    
                    # Extract tables and convert to text
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        if table and len(table) > 1:  # Skip empty tables
                            # Convert table to text format
                            table_text = ""
                            for row in table:
                                if row:
                                    # Filter out None values and join with tabs
                                    row_text = "\t".join([str(cell) if cell else "" for cell in row])
                                    table_text += row_text + "\n"
                            all_text += table_text + "\n"
                            tables.append(table)
                
                return self._process_extracted_data(all_text, tables, "pdfplumber")
                
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {str(e)}")
            return None
    
    def _extract_with_pymupdf(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using PyMuPDF - good for text-based documents."""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(pdf_path)
            all_text = ""
            
            for page in doc:
                # Get text with better formatting
                text = page.get_text("text")
                if text:
                    all_text += text + "\n"
                
                # Also try to get text with layout preservation
                try:
                    text_layout = page.get_text("dict")
                    if text_layout and "blocks" in text_layout:
                        for block in text_layout["blocks"]:
                            if "lines" in block:
                                for line in block["lines"]:
                                    if "spans" in line:
                                        line_text = " ".join([span["text"] for span in line["spans"]])
                                        if line_text.strip():
                                            all_text += line_text + "\n"
                except:
                    pass  # Fallback to basic text extraction
            
            doc.close()
            
            return self._process_extracted_data(all_text, [], "pymupdf")
            
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {str(e)}")
            return None
    

    
    def _extract_with_ocr(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using OCR - for scanned documents."""
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            # Convert PDF to images
            images = convert_from_path(pdf_path)
            
            all_text = ""
            for image in images:
                # Extract text using OCR
                text = pytesseract.image_to_string(image)
                if text:
                    all_text += text + "\n"
            
            return self._process_extracted_data(all_text, [], "ocr")
            
        except Exception as e:
            logger.warning(f"OCR extraction failed: {str(e)}")
            return None
    
    def _process_extracted_data(self, text: str, tables: List, method: str) -> Dict[str, Any]:
        """Process extracted text and tables into structured quote data."""
        logger.info(f"📝 Processing {method} data...")
        
        # Clean and filter the text before processing
        filtered_text = self._filter_non_inventory_content(text)
        
        # Use the existing OCR parser logic for processing
        from .ocr_parser import DynamicOCRParser
        parser = DynamicOCRParser()
        
        # Extract line items from filtered text
        line_items = parser.discover_line_items_dynamically(filtered_text)
        
        # Extract summary adjustments
        adjustments = parser.extract_summary_adjustments(text)
        
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
        
        # Process line items
        if line_items:
            # Group line items by similar characteristics
            groups = self._group_line_items(line_items)
            
            total_qty = sum(int(item.quantity) for item in line_items)
            total_cost = sum(Decimal(item.cost) for item in line_items)
            
            result['summary'].update({
                'totalQuantity': str(total_qty),
                'totalCost': str(total_cost),
                'numberOfGroups': len(groups)
            })
            
            result['groups'] = groups
        
        # Apply adjustments
        if adjustments:
            result = parser._apply_summary_adjustments(result, adjustments)
        
        return result
    
    def _filter_non_inventory_content(self, text: str) -> str:
        """Filter out non-inventory content like phone numbers, addresses, etc."""
        import re
        
        lines = text.split('\n')
        filtered_lines = []
        
        # Patterns to identify non-inventory content
        phone_patterns = [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US phone numbers
            r'\b\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,4}\b',  # General phone patterns
            r'\b\d{10,15}\b',  # Long number sequences
        ]
        
        address_patterns = [
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Place|Pl|Court|Ct)\b',
            r'\b[A-Za-z\s]+,?\s+[A-Z]{2}\s+\d{5}\b',  # City, State ZIP
            r'\b[A-Za-z\s]+\s+[A-Z]{2}\s+\d{5}\b',  # City State ZIP
        ]
        
        contact_patterns = [
            r'\b(?:Phone|Tel|Telephone|Fax|Email|E-mail|Contact|Address|Attn|Attention)\s*[:=]\s*\S+',
            r'\b(?:Phone|Tel|Telephone|Fax|Email|E-mail|Contact|Address|Attn|Attention)\b',
        ]
        
        metadata_patterns = [
            r'\b(?:Quote|Invoice|Order|PO|Purchase\s+Order)\s*#?\s*\d+\b',
            r'\b(?:Date|Due\s+Date|Valid\s+Until|Expires|Issue\s+Date)\s*[:=]\s*\S+',
            r'\b(?:Page|P)\s+\d+\s+(?:of|/)\s+\d+\b',
            r'\b(?:Terms|Conditions|Payment|Thank\s+You|Signature|Printed\s+Name)\b',
        ]
        
        # Compile patterns for efficiency
        phone_regex = re.compile('|'.join(phone_patterns), re.IGNORECASE)
        address_regex = re.compile('|'.join(address_patterns), re.IGNORECASE)
        contact_regex = re.compile('|'.join(contact_patterns), re.IGNORECASE)
        metadata_regex = re.compile('|'.join(metadata_patterns), re.IGNORECASE)
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that are clearly non-inventory
            if (phone_regex.search(line) or 
                address_regex.search(line) or 
                contact_regex.search(line) or 
                metadata_regex.search(line)):
                logger.debug(f"Filtered out non-inventory line: {line}")
                continue
            
            # Skip lines that are just numbers without context
            if re.match(r'^\s*\d+(?:[-.\s]\d+)*\s*$', line):
                logger.debug(f"Filtered out number-only line: {line}")
                continue
            
            # Skip lines that are too short to be meaningful descriptions
            if len(line.strip()) < 3:
                continue
            
            # Skip lines that are just punctuation or special characters
            if re.match(r'^\s*[^\w\s]*\s*$', line):
                continue
            
            # Skip lines that look like headers or labels
            if re.match(r'^\s*(?:Description|Item|Part|Qty|Quantity|Unit\s+Price|Amount|Total|Cost)\s*$', line, re.IGNORECASE):
                logger.debug(f"Filtered out header line: {line}")
                continue
            
            # Skip lines that are just separators or dividers
            if re.match(r'^\s*[-=_*]{3,}\s*$', line):
                continue
            
            # Only include lines that are likely to be line items
            if self._is_likely_line_item(line):
                filtered_lines.append(line)
            else:
                logger.debug(f"Filtered out unlikely line item: {line}")
        
        return '\n'.join(filtered_lines)
    
    def _is_likely_line_item(self, line: str) -> bool:
        """Check if a line is likely to be a line item based on content patterns."""
        import re
        
        # Look for price patterns
        price_patterns = [
            r'\$\d+(?:,\d{3})*(?:\.\d{2})?',  # $1,234.56
            r'\d+(?:,\d{3})*(?:\.\d{2})?\s*\$',  # 1,234.56 $
            r'\d+(?:,\d{3})*(?:\.\d{2})?',  # 1,234.56
        ]
        
        # Look for quantity patterns
        quantity_patterns = [
            r'\b\d+\s*(?:pcs?|pieces?|units?|items?)\b',  # 5 pcs, 3 pieces
            r'\b(?:qty|quantity)\s*[:=]?\s*\d+\b',  # Qty: 5
        ]
        
        # Look for product description patterns
        product_patterns = [
            r'\b(?:screw|bolt|nut|washer|bearing|motor|sensor|valve|pump|filter|cable|connector)\b',
            r'\b(?:steel|aluminum|plastic|copper|brass|stainless)\b',
            r'\b(?:machining|assembly|installation|service|maintenance|repair)\b',
        ]
        
        line_lower = line.lower()
        
        # Check for price patterns
        for pattern in price_patterns:
            if re.search(pattern, line):
                return True
        
        # Check for quantity patterns
        for pattern in quantity_patterns:
            if re.search(pattern, line_lower):
                return True
        
        # Check for product description patterns
        for pattern in product_patterns:
            if re.search(pattern, line_lower):
                return True
        
        # If line contains both text and numbers, it might be a line item
        if re.search(r'\d+', line) and re.search(r'[A-Za-z]', line):
            return True
        
        return False
    
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
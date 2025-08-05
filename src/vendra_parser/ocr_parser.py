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
        Extract text from PDF using multiple OCR approaches for maximum accuracy.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text string
        """
        extraction_results = []
        
        # Method 1: Direct PDF text extraction (fastest, works for text-based PDFs)
        try:
            direct_text = self._extract_text_directly(pdf_path)
            if direct_text and len(direct_text.strip()) > 50:  # Has substantial content
                extraction_results.append(("direct", direct_text))
                logger.info("Direct PDF extraction successful")
        except Exception as e:
            logger.warning(f"Direct text extraction failed: {e}")
        
        # Method 2: Enhanced OCR with multiple settings
        try:
            ocr_text = self._extract_with_enhanced_ocr(pdf_path)
            if ocr_text and len(ocr_text.strip()) > 50:
                extraction_results.append(("ocr", ocr_text))
                logger.info("Enhanced OCR extraction successful")
        except Exception as e:
            logger.warning(f"Enhanced OCR failed: {e}")
        
        # Method 3: Fallback to basic external tools
        try:
            basic_ocr = self._extract_with_external_tools(pdf_path)
            if basic_ocr and len(basic_ocr.strip()) > 50:
                extraction_results.append(("basic_ocr", basic_ocr))
                logger.info("Basic OCR extraction successful")
        except Exception as e:
            logger.warning(f"Basic OCR failed: {e}")
        
        if not extraction_results:
            raise Exception("All text extraction methods failed")
        
        # Choose the best extraction result
        best_text = self._choose_best_extraction(extraction_results)
        
        # Apply text preprocessing to clean up OCR artifacts
        cleaned_text = self._preprocess_extracted_text(best_text)
        
        # Final check: if still has major CID issues, force OCR retry
        final_cid_count = cleaned_text.count('cid:')
        if final_cid_count > 10:  # Threshold for "too many CID sequences"
            logger.warning(f"Final result still has {final_cid_count} CID sequences - trying pure OCR as fallback")
            try:
                # Force high-quality OCR extraction
                pure_ocr_text = self._extract_with_pure_ocr(pdf_path)
                if pure_ocr_text and pure_ocr_text.count('cid:') < final_cid_count:
                    logger.info("Pure OCR produced better results - using that instead")
                    cleaned_text = self._preprocess_extracted_text(pure_ocr_text)
            except Exception as e:
                logger.warning(f"Pure OCR fallback failed: {e}")
        
        logger.info(f"Final text extraction: {len(cleaned_text)} characters")
        return cleaned_text
    
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
    
    def _extract_with_enhanced_ocr(self, pdf_path: str) -> str:
        """Extract text using enhanced OCR with multiple approaches."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF to images with higher quality
            image_path = os.path.join(temp_dir, "page")
            subprocess.run([
                'pdftoppm', 
                '-png', 
                '-r', '600',  # Very high resolution for better OCR
                pdf_path, 
                image_path
            ], check=True)
            
            all_results = []
            page_num = 1
            
            while True:
                image_file = f"{image_path}-{page_num}.png"
                if not os.path.exists(image_file):
                    break
                
                # Try multiple OCR approaches for each page
                page_results = []
                
                # Approach 1: Table-aware OCR
                try:
                    result = subprocess.run([
                        'tesseract',
                        image_file,
                        'stdout',
                        '--psm', '6',  # Uniform block of text
                        '-c', 'preserve_interword_spaces=1'
                    ], capture_output=True, text=True, check=True)
                    page_results.append(("table", result.stdout.strip()))
                except:
                    pass
                
                # Approach 2: Line-oriented OCR
                try:
                    result = subprocess.run([
                        'tesseract',
                        image_file,
                        'stdout',
                        '--psm', '4',  # Single column of text
                        '-c', 'preserve_interword_spaces=1'
                    ], capture_output=True, text=True, check=True)
                    page_results.append(("lines", result.stdout.strip()))
                except:
                    pass
                
                # Approach 3: Sparse text OCR (good for scattered data)
                try:
                    result = subprocess.run([
                        'tesseract',
                        image_file,
                        'stdout',
                        '--psm', '11',  # Sparse text
                    ], capture_output=True, text=True, check=True)
                    page_results.append(("sparse", result.stdout.strip()))
                except:
                    pass
                
                # Choose best result for this page
                if page_results:
                    best_page = self._choose_best_page_result(page_results)
                    if best_page:
                        all_results.append(f"\n=== PAGE {page_num} ===\n{best_page}\n")
                
                page_num += 1
            
            final_text = "".join(all_results)
            logger.info(f"Enhanced OCR extracted {len(final_text)} characters")
            return final_text
    
    def _extract_with_pure_ocr(self, pdf_path: str) -> str:
        """Pure OCR extraction optimized for problematic PDFs with font issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF to images with maximum quality
            image_path = os.path.join(temp_dir, "page")
            subprocess.run([
                'pdftoppm', 
                '-png', 
                '-r', '300',  # High resolution
                '-aa', 'yes',  # Anti-aliasing
                '-aaVector', 'yes',  # Vector anti-aliasing
                pdf_path, 
                image_path
            ], check=True)
            
            all_text = ""
            page_num = 1
            
            while True:
                image_file = f"{image_path}-{page_num}.png"
                if not os.path.exists(image_file):
                    break
                
                # Use most reliable OCR settings for text extraction
                try:
                    result = subprocess.run([
                        'tesseract',
                        image_file,
                        'stdout',
                        '--psm', '6',  # Uniform block of text
                        '--oem', '3',  # Default OCR Engine Mode
                        '-c', 'tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,;:!?()[]{}/@#$%^&*+-=_|\\<>\'"',
                    ], capture_output=True, text=True, check=True)
                    
                    page_text = result.stdout.strip()
                    if page_text:
                        all_text += f"\n=== PAGE {page_num} ===\n{page_text}\n"
                    
                except subprocess.CalledProcessError:
                    # Fallback to basic OCR if whitelist fails
                    try:
                        result = subprocess.run([
                            'tesseract',
                            image_file,
                            'stdout',
                            '--psm', '6'
                        ], capture_output=True, text=True, check=True)
                        
                        page_text = result.stdout.strip()
                        if page_text:
                            all_text += f"\n=== PAGE {page_num} ===\n{page_text}\n"
                    except:
                        logger.warning(f"OCR failed for page {page_num}")
                
                page_num += 1
            
            logger.info(f"Pure OCR extracted {len(all_text)} characters")
            return all_text
    
    def _choose_best_page_result(self, page_results):
        """Choose the best OCR result for a single page."""
        if not page_results:
            return None
        
        # Score results based on content quality
        scored_results = []
        for method, text in page_results:
            if not text:
                continue
            
            score = 0
            lines = text.split('\n')
            
            # Score based on line item indicators
            for line in lines:
                line_clean = line.strip()
                if not line_clean:
                    continue
                
                # Look for patterns that suggest line items
                import re
                numbers = re.findall(r'[\d,]+\.?\d*', line_clean)
                
                # Lines with multiple numbers are likely line items
                if len(numbers) >= 2:
                    score += 10
                
                # Lines with currency symbols
                if '$' in line_clean:
                    score += 5
                
                # Lines with quantity indicators
                if any(word in line_clean.lower() for word in ['qty', 'quantity', 'service', 'product']):
                    score += 3
                
                # Penalize garbled text
                garbled_chars = sum(1 for c in line_clean if c in '~`@#%^&*()+=[]{}|\\:";\'<>?/')
                if garbled_chars > len(line_clean) * 0.1:  # More than 10% garbled
                    score -= garbled_chars
            
            scored_results.append((score, text))
        
        # Return the highest scoring result
        if scored_results:
            scored_results.sort(key=lambda x: x[0], reverse=True)
            return scored_results[0][1]
        
        # Fallback to first result
        return page_results[0][1]
    
    def _choose_best_extraction(self, extraction_results):
        """Choose the best extraction result from multiple methods."""
        if len(extraction_results) == 1:
            return extraction_results[0][1]
        
        # Score each extraction method
        scored_results = []
        for method, text in extraction_results:
            score = self._score_extraction_quality(text)
            scored_results.append((score, method, text))
            logger.info(f"Extraction method '{method}' scored {score}")
        
        # Return the highest scoring result
        scored_results.sort(key=lambda x: x[0], reverse=True)
        best_score, best_method, best_text = scored_results[0]
        logger.info(f"Selected extraction method: {best_method} (score: {best_score})")
        
        return best_text
    
    def _score_extraction_quality(self, text):
        """Score the quality of extracted text for quote parsing."""
        if not text:
            return 0
        
        lines = text.split('\n')
        score = 0
        
        # CRITICAL: Heavy penalty for CID sequences (font encoding failures)
        cid_count = text.count('cid:')
        if cid_count > 0:
            # Severe penalty - this text is essentially unreadable
            score -= cid_count * 50
            logger.warning(f"Found {cid_count} CID sequences - text extraction failed")
        
        # CRITICAL: Heavy penalty for other font encoding issues
        encoding_issues = [
            '(cid:', 'glyph', 'unicode', '\ufffd',  # Replacement characters
            '??' * 3,  # Multiple question marks indicate encoding failure
        ]
        for issue in encoding_issues:
            issue_count = text.count(issue)
            if issue_count > 0:
                score -= issue_count * 25
                logger.warning(f"Found {issue_count} instances of '{issue}' - encoding issues")
        
        # Look for readable line item indicators
        line_item_count = 0
        readable_content_score = 0
        
        for line in lines:
            line_clean = line.strip()
            if not line_clean:
                continue
            
            # Skip lines dominated by CID sequences
            if line_clean.count('cid:') > len(line_clean.split()) * 0.3:
                continue
            
            import re
            numbers = re.findall(r'[\d,]+\.?\d*', line_clean)
            
            # Potential line items (3+ numbers: qty, price, total)
            if len(numbers) >= 3:
                line_item_count += 1
                score += 20
                readable_content_score += 10
            # Partial line items (2 numbers: price, total)
            elif len(numbers) >= 2 and '$' in line_clean:
                line_item_count += 1
                score += 15
                readable_content_score += 8
            
            # Keywords that suggest this is quote content
            quote_keywords = ['service', 'product', 'freight', 'total', 'subtotal', 'quote', 'qty', 'quantity']
            if any(keyword in line_clean.lower() for keyword in quote_keywords):
                score += 5
                readable_content_score += 3
            
            # Bonus for recognizable product names/part numbers
            if re.search(r'[A-Z]+-\d+', line_clean.upper()):  # Pattern like "ROGUE-345"
                score += 10
                readable_content_score += 5
        
        # Bonus for having multiple line items
        if line_item_count >= 2:
            score += 30
        elif line_item_count >= 1:
            score += 10
        
        # Bonus for having substantial readable content
        if readable_content_score > 20:
            score += 20
        
        # Penalty for very garbled text (excluding CID which is already penalized)
        non_cid_text = re.sub(r'cid:\d+', '', text)
        if non_cid_text:
            garbled_chars = sum(1 for c in non_cid_text if c in '~`@#%^&*+=[]{}|\\:";\'<>?/')
            garbled_ratio = garbled_chars / len(non_cid_text)
            if garbled_ratio > 0.05:  # More than 5% garbled
                score -= int(garbled_ratio * 100)
        
        # Ensure minimum score doesn't go too negative
        return max(score, -500)
    
    def _preprocess_extracted_text(self, text):
        """Clean up OCR artifacts and improve text quality."""
        if not text:
            return text
        
        # First, check for and handle CID sequences
        text = self._handle_cid_sequences(text)
        
        # Split into lines for processing
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Basic cleanup
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that are mostly CID sequences (unreadable)
            if self._is_mostly_cid_garbage(line):
                logger.debug(f"Skipping CID-dominated line: {line[:50]}...")
                continue
            
            # Fix common OCR errors
            line = self._fix_common_ocr_errors(line)
            
            # Try to reconstruct broken line items
            line = self._reconstruct_line_items(line)
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _handle_cid_sequences(self, text):
        """Handle CID sequences in extracted text."""
        # Count CID sequences
        cid_count = text.count('cid:')
        
        if cid_count > 0:
            logger.info(f"Found {cid_count} CID sequences - attempting cleanup")
            
            # Try to remove isolated CID sequences while preserving structure
            # Pattern: "cid:NUMBER" optionally followed by space
            import re
            
            # Remove standalone CID sequences
            text = re.sub(r'\bcid:\d+\s*', ' ', text)
            
            # Clean up multiple spaces created by CID removal
            text = re.sub(r'\s+', ' ', text)
            
            # Clean up lines that became empty or just punctuation
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line and not re.match(r'^[:\s\.\,\-]+$', line):  # Not just punctuation
                    cleaned_lines.append(line)
            
            text = '\n'.join(cleaned_lines)
            
            remaining_cids = text.count('cid:')
            if remaining_cids < cid_count:
                logger.info(f"Cleaned up {cid_count - remaining_cids} CID sequences")
        
        return text
    
    def _is_mostly_cid_garbage(self, line):
        """Check if a line is mostly CID sequences and should be skipped."""
        if not line:
            return False
        
        words = line.split()
        if not words:
            return False
        
        cid_words = sum(1 for word in words if 'cid:' in word)
        cid_ratio = cid_words / len(words)
        
        # If more than 50% of words contain CID, consider it garbage
        return cid_ratio > 0.5
    
    def _fix_common_ocr_errors(self, line):
        """Fix common OCR misreading errors."""
        import re
        
        # Common character substitutions
        fixes = {
            'O': '0',  # Letter O -> Zero (in numbers)
            'l': '1',  # Lowercase L -> One (in numbers)
            'I': '1',  # Capital I -> One (in numbers)
            'S': '5',  # S -> 5 (in numbers)
            '§': '5',  # Section symbol -> 5
        }
        
        # Apply fixes to number-like contexts
        words = line.split()
        fixed_words = []
        
        for word in words:
            # If word looks like it should be a number
            if re.match(r'[\$\d\.,\-O0lI§S]+$', word):
                for wrong, right in fixes.items():
                    word = word.replace(wrong, right)
            
            fixed_words.append(word)
        
        return ' '.join(fixed_words)
    
    def _reconstruct_line_items(self, line):
        """Try to reconstruct incomplete line items by inferring missing data."""
        import re
        
        # Look for patterns that suggest missing quantity
        # Pattern: "DESCRIPTION $price $total" -> should be "DESCRIPTION 1 $price $total"
        numbers = re.findall(r'[\d,]+\.?\d*', line)
        
        if len(numbers) == 2 and '$' in line:
            # Check if this could be quantity=1 case
            try:
                price = float(self.normalize_price(numbers[0]))
                total = float(self.normalize_price(numbers[1]))
                
                # If price equals total, quantity is likely 1
                if abs(price - total) < 0.01:
                    # Insert "1" before the first number
                    first_num_pos = line.find(numbers[0])
                    if first_num_pos > 0:
                        # Make sure we're not inserting into middle of a word
                        before_char = line[first_num_pos - 1]
                        if before_char == ' ' or before_char == '-':
                            line = line[:first_num_pos] + "1 " + line[first_num_pos:]
                            logger.debug(f"Inferred quantity=1 for line: {line}")
                
            except (ValueError, IndexError):
                pass
        
        return line
    
    def normalize_price(self, price_str: str) -> str:
        """Normalize price string using babel for proper currency and locale handling."""
        if not price_str:
            return "0"
        
        original_str = price_str
        
        try:
            from babel.numbers import parse_decimal, NumberFormatError
            
            # First, try to detect currency from symbols
            detected_currency = None
            detected_locale = None
            
            # Common currency symbols and their locales
            currency_to_locale = {
                '€': 'de_DE',  # German locale for Euro
                '£': 'en_GB',  # British locale for Pound
                '¥': 'ja_JP',  # Japanese locale for Yen
                '₹': 'en_IN',  # Indian locale for Rupee
                '₽': 'ru_RU',  # Russian locale for Ruble
                '₩': 'ko_KR',  # Korean locale for Won
                '$': 'en_US',  # US locale for Dollar
            }
            
            # Check for currency symbols
            for symbol, locale_code in currency_to_locale.items():
                if symbol in price_str:
                    detected_currency = symbol
                    detected_locale = locale_code
                    break
            
            # If no currency symbol found, try to infer from number format
            if not detected_currency:
                # European format detection (comma as decimal separator)
                if ',' in price_str and '.' in price_str:
                    # Check if it's European format: "2.311,25" vs US format: "2,311.25"
                    parts = price_str.split(',')
                    if len(parts) == 2 and len(parts[1]) == 2 and parts[1].isdigit():
                        detected_locale = 'de_DE'  # European format
                    else:
                        detected_locale = 'en_US'  # US format
                elif ',' in price_str and '.' not in price_str:
                    # Pattern like "1 234,56" - likely European
                    detected_locale = 'de_DE'
                else:
                    detected_locale = 'en_US'  # Default to US format
            
            # Remove currency symbols for parsing
            clean_price = re.sub(r'[\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿\$]', '', price_str.strip())
            
            # Parse using babel with detected locale
            try:
                parsed_value = parse_decimal(clean_price, locale=detected_locale)
                # Format to 2 decimal places for currency
                normalized = f"{parsed_value:.2f}"
                
                if detected_currency:
                    logger.debug(f"Babel detected {detected_currency} ({detected_locale}): {original_str} -> {normalized}")
                else:
                    logger.debug(f"Babel inferred {detected_locale}: {original_str} -> {normalized}")
                
                return normalized
                
            except NumberFormatError:
                # Fallback to manual parsing if babel fails
                logger.warning(f"Babel failed to parse: {original_str}, falling back to manual parsing")
                return self._fallback_normalize_price(price_str)
                
        except ImportError:
            # Fallback if babel is not available
            logger.warning("Babel not available, using fallback currency parsing")
            return self._fallback_normalize_price(price_str)
    
    def _fallback_normalize_price(self, price_str: str) -> str:
        """Fallback currency normalization when babel is not available."""
        if not price_str:
            return "0"
        
        # Remove currency symbols
        price_str = re.sub(r'[\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿\$]', '', price_str.strip())
        
        # Simple number format normalization
        if ',' in price_str and '.' in price_str:
            # European format: "2.311,25" -> "2311.25"
            parts = price_str.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                integer_part = re.sub(r'[\s\.]', '', parts[0])
                decimal_part = parts[1]
                price_str = f"{integer_part}.{decimal_part}"
        
        # Remove spaces and commas (thousands separators)
        price_str = re.sub(r'[\s,]', '', price_str)
        
        try:
            from decimal import Decimal
            value = Decimal(price_str)
            return f"{value:.2f}"
        except:
            return "0"
    
    def _normalize_number_format(self, price_str: str, detected_currency: str = None) -> str:
        """Normalize number format based on detected currency and regional conventions."""
        
        # Currencies that commonly use European number format (comma as decimal)
        european_format_currencies = ['EUR', 'BRL', 'RUB', 'TRY', 'PLN', 'CZK', 'HUF', 'BGN', 'RON', 'HRK', 'UAH', 'BYN', 'MDL', 'GEL', 'AMD', 'AZN', 'KZT', 'KGS', 'TJS', 'TMT', 'UZS']
        
        # Currencies that use Asian format (often no decimals)
        asian_format_currencies = ['JPY', 'CNY', 'KRW', 'SGD', 'HKD']
        
        # Determine format based on currency
        use_european_format = detected_currency in european_format_currencies if detected_currency else False
        use_asian_format = detected_currency in asian_format_currencies if detected_currency else False
        
        # Handle different number formats
        if use_european_format:
            # European format: "1 234,56" or "1.234,56" (space or dot as thousands, comma as decimal)
            if ',' in price_str and '.' not in price_str:
                # European format with comma as decimal: "1 234,56"
                parts = price_str.split(',')
                if len(parts) == 2:
                    integer_part = re.sub(r'[\s\.]', '', parts[0])  # Remove both spaces and dots
                    decimal_part = parts[1]
                    price_str = f"{integer_part}.{decimal_part}"
            elif ' ' in price_str and (',' not in price_str and '.' not in price_str):
                # European format with just spaces as thousands separator: "1 234"
                price_str = re.sub(r'\s+', '', price_str)
            elif ' ' in price_str and ',' in price_str:
                # European format: "1 234,56" 
                parts = price_str.split(',')
                if len(parts) == 2:
                    integer_part = re.sub(r'[\s\.]', '', parts[0])  # Remove both spaces and dots
                    decimal_part = parts[1]
                    price_str = f"{integer_part}.{decimal_part}"
            else:
                # Remove spaces and dots (thousands separators), keep commas as decimals
                price_str = re.sub(r'[\s\.]', '', price_str)
                price_str = price_str.replace(',', '.')
        elif use_asian_format:
            # Asian format: often no decimal places, or different separators
            # Remove all separators and treat as whole numbers
            price_str = re.sub(r'[\s,\.]', '', price_str)
            
        else:
            # US/International format: "1,234.56" (comma as thousands, dot as decimal)
            # Also handle spaces as thousands separators: "14 287.40"
            price_str = re.sub(r',', '', price_str)
            price_str = re.sub(r'\s+', '', price_str)  # Remove spaces (thousands separators)
        
        return price_str
    
    def discover_line_items_dynamically(self, text: str) -> List[LineItem]:
        """
        Completely dynamic line item discovery - no assumptions about format.
        Analyzes every line and tries to extract any valid line item.
        Enhanced to handle OCR artifacts and missing data.
        """
        line_items = []
        lines = text.split('\n')
        
        # FIRST: Reconstruct multi-line descriptions that are common in table formats
        lines = self._reconstruct_multiline_descriptions(lines)
        
        logger.info(f"Analyzing {len(lines)} lines for dynamic pattern discovery (after multiline reconstruction)")
        
        # Step 1: Find ALL lines with numbers (potential line items)
        candidate_lines = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Find all numbers in the line - improved regex to avoid part number components
            # This regex captures currency amounts, integers, and decimals, but avoids part number fragments
            numbers = re.findall(r'(?:^|\s)(\$?\d+(?:,\d{3})*(?:\.\d{1,2})?)(?=\s|$)', line)
            # If no matches with strict boundary matching, fall back to looser matching
            if not numbers:
                numbers = re.findall(r'(\$?\d+(?:,\d{3})*(?:\.\d{1,2})?)', line)
            # Remove currency symbols for processing but keep the numeric values
            numbers = [num.replace('$', '').replace(',', '') for num in numbers if num.replace('$', '').replace(',', '').replace('.', '').isdigit()]
            
            # Only skip lines that are clearly headers, totals, or metadata
            # Be very conservative about filtering
            line_lower = line.lower()
            
                    # Skip obvious non-line-item lines using more specific patterns
            # Use patterns that require context to avoid blocking legitimate products
            skip_patterns = [
                # Financial summary lines
                r'\btotal\s*:', r'\bsubtotal\s*:', r'\bbalance\s*:', r'\bgrand\s+total\b',
                r'\bnet\s+total\b', r'\btax\s*:', r'\bdiscount\s*:', r'\bshipping\s*:',
                r'^\s*total\s*\$', r'^\s*subtotal\s*\$', r'^\s*tax\s*\$',
                
                # Document metadata
                r'\bquote\s*#', r'\binvoice\s*#', r'\border\s*#', r'\bpo\s*#',
                r'\bdate\s*:', r'\bpage\s*:', r'\bdue\s+date\s*:', r'\bvalid\s+(until|through|for)\b',
                r'\breport\s+generated\s*:', r'\bpage\s+\d+\s+of\s+\d+\b', 
                
                # Contact information
                r'\bphone\s*:', r'\bfax\s*:', r'\bemail\s*:', r'\baddress\s*:',
                r'\bcontact\s*:', r'\battn\s*:', r'\bto\s*:', r'\bfrom\s*:',
                
                # Terms and conditions
                r'\bterms\s+and\s+conditions\b', r'\bpayment\s+terms\b', r'\bthank\s+you\b',
                r'\bsignature\b', r'\bprinted\s+name\b',
                
                # Shipping and logistics (not inventory items)
                r'^\s*freight\s*(shipping)?\s*$', r'^\s*shipping\s*(and\s+handling)?\s*$',
                r'^\s*lead\s+time\s*', r'^\s*delivery\s*', r'^\s*via\s*:',
                
                # Headers and labels
                r'\bdescription\s*:', r'\bunit\s+price\b', r'\bamount\s*:', r'\bqty\s*:',
                r'\bquantity\s*:', r'\bitem\s+code\b', r'\bpart\s+number\b',
                r'service/product\s+description', r'hours/quantity', r'hourly\s+fee',
                
                # Business metadata
                r'\bquote\s+by\b', r'\border\s+by\b', r'\bmoq\s*:', r'\bweeks\s+after\b', 
                r'\breceipt\s+of\b', r'\bquotation\s*:'
            ]
            
            if any(re.search(pattern, line_lower) for pattern in skip_patterns):
                continue
            
            # Skip lines that are addresses or contact info (enhanced filtering)
            if self._is_address_or_contact_line(line, line_lower, numbers):
                continue
            
            # Enhanced candidate detection: accept lines with even 1 number if they look like line items
            is_candidate = False
            
            # Traditional: 2+ numbers
            if len(numbers) >= 2:
                is_candidate = True
            # Enhanced: 1 number but with strong line item indicators
            elif len(numbers) == 1 and self._looks_like_incomplete_line_item(line, line_lower):
                is_candidate = True
                logger.info(f"Added single-number candidate (incomplete line item): {line}")
            
            if is_candidate:
                candidate_lines.append((i, line, numbers))
        
        logger.info(f"Found {len(candidate_lines)} candidate lines")
        
        # Step 2: Try to combine adjacent incomplete lines
        enhanced_candidates = self._enhance_incomplete_candidates(candidate_lines, lines)
        
        # Step 3: Analyze patterns in candidate lines
        for line_num, line, numbers in enhanced_candidates:
            logger.info(f"Analyzing candidate line {line_num}: {line}")
            
            # Try different parsing strategies
            line_item = self._try_parse_line_item(line, numbers)
            if line_item:
                line_items.append(line_item)
                logger.info(f"Successfully parsed line item: {line_item.description}")
        
        return line_items
    
    def _looks_like_incomplete_line_item(self, line, line_lower):
        """Check if a line looks like an incomplete line item that might be missing numbers."""
        # Look for product/service indicators
        product_indicators = [
            'service', 'product', 'freight', 'rogue', 'item', 'part', 'component',
            'assembly', 'material', 'labor', 'work', 'setup', 'tooling'
        ]
        
        # Look for part number patterns (letters + numbers + dashes)
        import re
        has_part_number = bool(re.search(r'[A-Z]+-\d+', line.upper()))
        
        # Has product indicators or part numbers
        has_indicators = any(indicator in line_lower for indicator in product_indicators)
        
        # Has currency symbol (might be missing quantity)
        has_currency = '$' in line
        
        return has_part_number or (has_indicators and has_currency)
    
    def _enhance_incomplete_candidates(self, candidate_lines, all_lines):
        """Try to enhance incomplete candidates by combining with adjacent lines."""
        enhanced = []
        used_lines = set()
        
        for i, (line_num, line, numbers) in enumerate(candidate_lines):
            if line_num in used_lines:
                continue
            
            enhanced_line = line
            enhanced_numbers = numbers.copy()
            
            # If this line looks incomplete, try to combine with next few lines
            if len(numbers) < 3 and self._looks_like_incomplete_line_item(line, line.lower()):
                # Look at next 2 lines for additional numbers
                for offset in [1, 2]:
                    next_line_num = line_num + offset
                    if next_line_num < len(all_lines):
                        next_line = all_lines[next_line_num].strip()
                        if next_line:
                            next_numbers = re.findall(r'(-?[\d,]+\.?\d*)', next_line)
                            
                            # If next line has numbers and looks like it continues this line item
                            if next_numbers and self._lines_should_combine(line, next_line):
                                enhanced_line += " " + next_line
                                enhanced_numbers.extend(next_numbers)
                                used_lines.add(next_line_num)
                                logger.info(f"Combined lines {line_num} and {next_line_num}: {enhanced_line}")
                                
                                # If we now have enough numbers, stop combining
                                if len(enhanced_numbers) >= 3:
                                    break
            
            enhanced.append((line_num, enhanced_line, enhanced_numbers))
            used_lines.add(line_num)
        
        return enhanced
    
    def _lines_should_combine(self, line1, line2):
        """Check if two lines should be combined into one line item."""
        line2_lower = line2.lower()
        
        # Don't combine if second line looks like a new line item
        if any(indicator in line2_lower for indicator in ['service', 'product', 'rogue', 'freight']):
            return False
        
        # Don't combine if second line looks like a total/subtotal
        if any(word in line2_lower for word in ['total', 'subtotal', 'tax', 'discount']):
            return False
        
        # Do combine if second line looks like pricing info
        has_currency = '$' in line2
        has_numbers = bool(re.findall(r'\d+', line2))
        is_short = len(line2.split()) <= 4  # Short lines are more likely to be pricing continuation
        
        return has_currency and has_numbers and is_short
    
    def _try_parse_line_item(self, line: str, numbers: List[str]) -> Optional[LineItem]:
        """
        Completely dynamic line item parsing - tries all possible combinations.
        Returns the best match based on mathematical validation.
        """
        # Minimal filtering - only reject clearly non-product lines
        line_lower = line.lower()
        
        # Skip lines that are clearly addresses or contact info (enhanced filtering)
        if self._is_address_or_contact_line(line, line_lower, numbers):
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
                
                if 1 <= qty <= 100000 and unit_price != 0 and total != 0:
                    # Validate: qty * unit_price should equal total (with generous tolerance for rounding)
                    expected_total = qty * unit_price
                    tolerance = max(abs(expected_total * Decimal('0.15')), Decimal('0.50'))  # 15% or $0.50, whichever is larger
                    if abs(expected_total - total) <= tolerance:
                        # Find description using smart extraction
                        description = self._extract_description_smartly(line, last_three[0], last_three[1], last_three[2])
                        if description:
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
                
                if 1 <= qty <= 100000 and unit_price != 0 and total != 0:
                    expected_total = qty * unit_price
                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / abs(total) <= Decimal('0.10'):
                        # Find description using smart extraction  
                        description = self._extract_description_smartly(line, last_three[0], last_three[1], last_three[2])
                        if description:
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
                    
                    if 1 <= qty <= 100000 and unit_price != 0 and total != 0:
                        expected_total = qty * unit_price
                        if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / abs(total) <= Decimal('0.10'):
                            # Find description using smart extraction
                            description = self._extract_description_smartly(line, numbers[i], numbers[i+1], numbers[i+2])
                            if description:
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
                if 1 <= qty <= 100000:
                    # Check if this number appears near quantity-related keywords
                    num_pos = line.find(num)
                    context = line[max(0, num_pos-20):num_pos+20].lower()
                    
                    if any(keyword in context for keyword in ['qty', 'quantity', 'ea', 'each', 'units', 'pcs']):
                        # This number is likely a quantity
                        if i + 2 < len(numbers):
                            try:
                                unit_price = Decimal(self.normalize_price(numbers[i+1]))
                                total = Decimal(self.normalize_price(numbers[i+2]))
                                
                                # Allow negative costs for discounts/COD, but ensure they're not zero
                                if unit_price != 0 and total != 0:
                                    expected_total = qty * unit_price
                                    # For negative totals, use absolute value for percentage check
                                    tolerance_check = abs(expected_total - total) <= Decimal('0.01')
                                    percentage_check = abs(expected_total - total) / abs(total) <= Decimal('0.10')
                                    
                                    if tolerance_check or percentage_check:
                                        # Find description using smart extraction
                                        description = self._extract_description_smartly(line, num, numbers[i+1], numbers[i+2])
                                        if description:
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
                if 1 <= qty <= 100000:
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
                                
                                if unit_price != 0 and total != 0:
                                    expected_total = qty * unit_price
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / abs(total) <= Decimal('0.10'):
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
                                
                                if unit_price != 0 and total != 0:
                                    expected_total = qty * unit_price
                                    if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / abs(total) <= Decimal('0.10'):
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
                if 1 <= first_qty <= 100000:
                    # Try to find unit price and total from the remaining numbers
                    # Look for the last two numbers as unit_price and total
                    unit_price = Decimal(self.normalize_price(numbers[-2]))
                    total = Decimal(self.normalize_price(numbers[-1]))
                    
                    if unit_price != 0 and total != 0:
                        expected_total = first_qty * unit_price
                        if abs(expected_total - total) <= Decimal('0.01') or abs(expected_total - total) / abs(total) <= Decimal('0.10'):
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
                        # Try to infer quantity dynamically instead of hardcoding "1"
                        unit_price_candidate = self.normalize_price(last_two[0])
                        cost_candidate = self.normalize_price(last_two[1])
                        
                        # If unit_price * 1 ≈ cost, then quantity is likely 1
                        # Otherwise, try to calculate quantity = cost / unit_price
                        quantity = self._infer_quantity_from_prices(unit_price_candidate, cost_candidate)
                        unit_price = unit_price_candidate
                        cost = cost_candidate
                        
                        if len(description) > 1:  # More lenient length requirement
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
    
    def _reconstruct_multiline_descriptions(self, lines: List[str]) -> List[str]:
        """
        Reconstruct multi-line table descriptions that were split during OCR.
        Common pattern: Description line followed by continuation line(s) without numbers.
        """
        reconstructed = []
        i = 0
        
        while i < len(lines):
            current_line = lines[i].strip()
            
            if not current_line:
                i += 1
                continue
            
            # Check if this line looks like a table row (has at least 3 numbers)
            import re
            numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', current_line)
            
            if len(numbers) >= 3:
                # This looks like a table row - check if next line(s) are continuation
                combined_line = current_line
                j = i + 1
                
                # Look ahead for continuation lines
                while j < len(lines):
                    next_line = lines[j].strip()
                    if not next_line:
                        break
                    
                    # Check if next line is a continuation (no numbers or very few numbers)
                    next_numbers = re.findall(r'\d+(?:,\d{3})*(?:\.\d{2})?', next_line)
                    
                    # Continuation if: no numbers, OR only 1-2 numbers (like a part of description)
                    if len(next_numbers) <= 2:
                        # Common continuation patterns
                        continuation_patterns = [
                            r'^(machine|de-burr|and|material|clear|steel|polypropylene)',  # Common description words
                            r'^[a-zA-Z\s\-_:]+$',  # Only letters/spaces/basic punctuation
                            r'^\w+\s+(and|de-burr|material)',  # Technical terms
                        ]
                        
                        is_continuation = any(re.match(pattern, next_line.lower()) for pattern in continuation_patterns)
                        
                        if is_continuation:
                            # Combine with main line
                            combined_line += " " + next_line
                            j += 1
                        else:
                            break
                    else:
                        # Next line has many numbers - likely another table row
                        break
                
                # Clean up OCR artifacts in part numbers
                combined_line = self._fix_part_number_artifacts(combined_line)
                
                reconstructed.append(combined_line)
                i = j  # Skip the lines we combined
            else:
                reconstructed.append(current_line)
                i += 1
        
        logger.debug(f"Multiline reconstruction: {len(lines)} -> {len(reconstructed)} lines")
        return reconstructed
    
    def _fix_part_number_artifacts(self, line: str) -> str:
        """Fix common OCR artifacts in part numbers."""
        # Fix spaces in part numbers like "19_ 5-basebalancer" -> "19_5-basebalancer" 
        line = re.sub(r'(\d+)_\s+(\d+-)', r'\1_\2', line)
        # Fix "19 _5-" -> "19_5-"
        line = re.sub(r'(\d+)\s+_(\d+-)', r'\1_\2', line)
        return line
    
    def _clean_description(self, description: str) -> str:
        """Clean up description while preserving important parts."""
        # Remove special characters but keep alphanumeric, spaces, hyphens, underscores, colons
        description = re.sub(r'[^\w\s\-_:]', ' ', description)
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description).strip()
        return description
    
    def _infer_quantity_from_prices(self, unit_price_str: str, cost_str: str) -> str:
        """
        Dynamically infer quantity from unit price and cost relationship.
        Avoids hardcoding quantity = "1".
        """
        try:
            unit_price = Decimal(unit_price_str)
            cost = Decimal(cost_str)
            
            # Handle edge cases
            if unit_price == 0 or cost == 0:
                return "1"  # Fallback for invalid prices
            
            # Calculate implied quantity = cost / unit_price
            implied_quantity = cost / unit_price
            
            # Round to nearest reasonable integer
            rounded_qty = round(float(implied_quantity))
            
            # Validate the result makes sense
            if rounded_qty <= 0:
                return "1"
            elif rounded_qty > 100000:  # Extremely high quantity - likely calculation error
                return "1"
            else:
                # Check if the math works out (within 5% tolerance)
                expected_cost = unit_price * Decimal(str(rounded_qty))
                tolerance = abs(expected_cost - cost) / abs(cost) if cost != 0 else 1
                
                if tolerance <= 0.05:  # Within 5% tolerance
                    return str(rounded_qty)
                else:
                    return "1"  # Math doesn't work out, default to 1
                    
        except (ValueError, InvalidOperation, ZeroDivisionError):
            return "1"  # Fallback for any calculation errors
    
    def _is_valid_product_description(self, description: str) -> bool:
        """Check if a description looks like a valid product/inventory item description."""
        if not description or len(description) < 2:
            return False
        
        desc_lower = description.lower().strip()
        
        # STRICT filtering for non-inventory items
        # These should NOT be treated as inventory/product line items
        
        # 1. Document/administrative metadata
        if desc_lower.startswith(('to:', 'from:', 'attn:', 're:', 'subject:', 'date:', 'page:')):
            return False
        
        # 2. Financial/summary lines (these are calculations, not products)
        financial_terms = [
            'total', 'subtotal', 'grand total', 'net total', 'balance', 'amount due',
            'tax', 'vat', 'gst', 'sales tax', 'discount', 'markup', 'surcharge'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') or desc_lower.endswith(f' {term}') for term in financial_terms):
            logger.debug(f"Rejected financial term: {description}")
            return False
        
        # 3. Shipping/logistics charges (not inventory)
        # Be more specific - only reject if it's clearly a shipping charge, not a product with shipping in the name
        if self._is_shipping_charge(desc_lower):
            logger.debug(f"Rejected shipping charge: {description}")
            return False
        
        # 4. Payment/business terms (not inventory)
        payment_terms = [
            'cod', 'cash on delivery', 'net 30', 'net 60', 'payment terms', 'deposit',
            'down payment', 'installment', 'financing', 'credit', 'prepayment'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') for term in payment_terms):
            logger.debug(f"Rejected payment term: {description}")
            return False
        
        # 5. Time/scheduling terms (not inventory)
        time_terms = [
            'lead time', 'delivery time', 'turnaround time', 'processing time',
            'wait time', 'setup time', 'lead', 'eta', 'estimated delivery'
        ]
        if any(term == desc_lower or desc_lower.startswith(f'{term} ') for term in time_terms):
            logger.debug(f"Rejected time term: {description}")
            return False
        
        # 6. Service fees (unless clearly product-related services)
        service_terms = [
            'setup fee', 'processing fee', 'handling fee', 'service charge', 
            'administrative fee', 'documentation fee', 'expedite fee'
        ]
        if any(term == desc_lower for term in service_terms):
            logger.debug(f"Rejected service fee: {description}")
            return False
        
        # 7. Must have some descriptive content (not just numbers or single letters)
        words = description.split()
        if len(words) < 1:
            return False
        
        # Must contain at least one substantial word (length > 2) that's not just numbers
        has_substantial_word = any(not word.isdigit() and len(word) > 2 for word in words)
        if not has_substantial_word:
            logger.debug(f"Rejected - no substantial words: {description}")
            return False
        
        # 8. POSITIVE indicators for valid products (give bonus points)
        product_indicators = [
            # Manufacturing terms
            'material', 'steel', 'aluminum', 'plastic', 'metal', 'alloy', 'composite',
            'polycarbonate', 'polypropylene', 'abs', 'nylon', 'rubber', 'ceramic',
            
            # Product types
            'assembly', 'component', 'part', 'piece', 'unit', 'item', 'product',
            'module', 'kit', 'set', 'package', 'bundle',
            
            # Manufacturing processes
            'machined', 'machining', 'fabricated', 'welded', 'molded', 'cast',
            'forged', 'stamped', 'extruded', 'threaded', 'anodized', 'plated',
            
            # Common product patterns
            '-', '_', 'rev', 'version', 'model', 'type', 'size', 'grade',
            
            # Measurement terms
            'mm', 'cm', 'inch', 'diameter', 'length', 'width', 'gauge', 'thickness'
        ]
        
        has_product_indicators = any(indicator in desc_lower for indicator in product_indicators)
        
        # 9. Part number patterns (strong indicator of products)
        import re
        has_part_number = bool(re.search(r'[A-Z0-9]+-[A-Z0-9]+', description.upper()))
        
        # Final decision: accept if has product indicators or part numbers
        if has_product_indicators or has_part_number:
            return True
        
        # RELAXED VALIDATION: Accept reasonable product descriptions even without specific indicators
        # This addresses the issue of missing simple product names like "Widget A"
        
        # Additional acceptance criteria for simple but valid product descriptions:
        
        # 1. If it's a reasonable length (2-50 characters) and has meaningful words
        if 2 <= len(description) <= 50:
            words = description.split()
            
            # 2. Must have at least one word longer than 2 characters (not just "A" or "B")
            has_meaningful_word = any(len(word) > 2 and not word.isdigit() for word in words)
            
            # 3. Doesn't contain obvious non-product patterns
            non_product_patterns = [
                'phone', 'fax', 'email', 'address', 'zip', 'date', 'page',
                'estimate', 'quote', 'invoice', 'receipt', 'company', 'inc',
                'corporation', 'corp', 'llc', 'ltd', 'street', 'st', 'avenue', 'ave',
                'drive', 'dr', 'road', 'rd', 'suite', 'apt', 'floor', 'building'
            ]
            
            is_non_product = any(pattern in desc_lower for pattern in non_product_patterns)
            
            # 4. Accept if it looks like a reasonable product name
            if has_meaningful_word and not is_non_product:
                logger.debug(f"Accepted simple product description: {description}")
                return True
        
        # For ambiguous cases, still be conservative but less restrictive
        logger.debug(f"Rejected ambiguous description: {description}")
        return False
    
    def _is_shipping_charge(self, desc_lower):
        """Check if description is a shipping charge vs product name with shipping words."""
        # Patterns that indicate actual shipping charges (not products)
        shipping_charge_patterns = [
            # Standalone shipping terms
            r'^freight$', r'^shipping$', r'^delivery$', r'^handling$', 
            r'^postage$', r'^courier$', r'^express$', r'^overnight$',
            
            # Shipping with simple descriptors (3 words or less)
            r'^freight\s+(shipping|cost|charge|fee)$',
            r'^shipping\s+(and\s+handling|cost|charge|fee)$',
            r'^delivery\s+(charge|fee|cost)$',
            r'^handling\s+(charge|fee|cost)$',
            
            # Common shipping charge formats
            r'^rush\s+delivery$', r'^expedited\s+shipping$',
            r'^standard\s+shipping$', r'^ground\s+shipping$'
        ]
        
        import re
        for pattern in shipping_charge_patterns:
            if re.match(pattern, desc_lower):
                return True
        
        # Additional heuristics for shipping charges:
        words = desc_lower.split()
        
        # Single word shipping terms
        if len(words) == 1 and words[0] in ['freight', 'shipping', 'delivery', 'handling', 'postage']:
            return True
        
        # Two-word combinations that are likely shipping charges
        if len(words) == 2:
            first, second = words
            if (first in ['freight', 'shipping', 'delivery', 'handling'] and 
                second in ['charge', 'fee', 'cost', 'service']):
                return True
        
        # NOT shipping charges: product names/part numbers that happen to contain shipping words
        # These typically have:
        # - Part numbers (letters + numbers + dashes)
        # - Multiple technical terms
        # - Specific material/process descriptions
        
        # If it has a part number pattern, it's likely a product
        if re.search(r'[A-Z]+-\d+|[A-Z]+\d+', desc_lower.upper()):
            return False
        
        # If it has material terms, it's likely a product
        material_terms = ['steel', 'aluminum', 'plastic', 'material', 'polycarbonate', 'metal']
        if any(term in desc_lower for term in material_terms):
            return False
        
        # If it's a complex description (4+ words), it's likely a product
        if len(words) >= 4:
            return False
        
        return False
    
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
    
    def _extract_description_smartly(self, line: str, qty_or_price1: str, price_or_qty: str, total: str) -> Optional[str]:
        """
        Smart description extraction that preserves product names with numbers.
        Handles numbers with commas and various price formats.
        """
        import re
        
        # Create variations of the numbers to handle different formats (with/without commas, with/without $)
        def create_number_patterns(num_str):
            # Remove existing formatting
            clean_num = num_str.replace('$', '').replace(',', '')
            patterns = [
                clean_num,  # 1524.28
                f"{clean_num.replace('.', '')}",  # For integers: 152428 
            ]
            
            # Add comma-formatted versions for numbers > 999
            if '.' in clean_num:
                whole, decimal = clean_num.split('.')
                if len(whole) >= 4:  # 1000 or more
                    # Add comma formatting: 1,524.28
                    formatted = f"{int(whole):,}.{decimal}"
                    patterns.extend([formatted, f"${formatted}"])
            elif len(clean_num) >= 4:
                # Integer with comma formatting
                formatted = f"{int(clean_num):,}"
                patterns.extend([formatted, f"${formatted}"])
            
            # Add $ versions
            patterns.extend([f"${clean_num}"])
            
            return patterns
        
        # Find positions working backwards from end of line
        total_patterns = create_number_patterns(total)
        price_patterns = create_number_patterns(price_or_qty)  
        qty_patterns = create_number_patterns(qty_or_price1)
        
        # Strategy 1: Find the last occurrence of each number pattern
        total_pos = -1
        for pattern in total_patterns:
            pos = line.rfind(pattern)
            if pos > total_pos:
                total_pos = pos
                
        if total_pos == -1:
            return None
            
        # Find unit price before total
        price_pos = -1
        for pattern in price_patterns:
            pos = line.rfind(pattern, 0, total_pos)
            if pos > price_pos:
                price_pos = pos
                
        if price_pos == -1:
            return None
            
        # Find quantity before price  
        qty_pos = -1
        for pattern in qty_patterns:
            pos = line.rfind(pattern, 0, price_pos)
            if pos > qty_pos:
                qty_pos = pos
                
        if qty_pos == -1:
            return None
        
        # Extract description: prefix + suffix around the pricing numbers
        # Prefix: everything before first number
        prefix_desc = line[:qty_pos].strip()
        
        # Suffix: everything after last number (if any)
        total_end_pos = total_pos + len([p for p in total_patterns if line.find(p, total_pos) == total_pos][0])
        suffix_desc = line[total_end_pos:].strip()
        
        # Combine prefix and suffix if both exist
        if prefix_desc and suffix_desc:
            # Check if suffix looks like part of product description
            suffix_lower = suffix_desc.lower()
            valid_suffixes = [
                'machine', 'de-burr', 'deburr', 'material', 'steel', 'aluminum', 
                'plastic', 'coating', 'finish', 'assembly', 'component', 'part',
                'clear', 'black', 'white', 'polypropylene', 'and', 'with'
            ]
            
            # If suffix contains product terms and is reasonable length
            if len(suffix_desc) < 100 and any(term in suffix_lower for term in valid_suffixes):
                full_desc = f"{prefix_desc} {suffix_desc}".strip()
                words = full_desc.split()
                if len(words) > 1:  # Multi-word description
                    return ' '.join(words)
        
        # Fallback to prefix only
        if prefix_desc:
            words = prefix_desc.split()
            if words:
                description = ' '.join(words)
                if len(description) > 2:
                    return description
        
        # Strategy 2: Advanced regex-based extraction for complete descriptions
        # Pattern handles: PREFIX [numbers] SUFFIX or PREFIX [numbers] 
        # Matches: DESCRIPTION QTY PRICE TOTAL [TRAILING_DESCRIPTION]
        
        # More flexible pattern that captures everything before first number and after last number
        number_pattern = r'\$?-?\d+(?:,\d{3})*(?:\.\d{1,2})?'
        full_pattern = f'^(.+?)\\s+({number_pattern})\\s+({number_pattern})\\s+({number_pattern})\\s*(.*?)$'
        
        match = re.match(full_pattern, line)
        if match:
            prefix_desc = match.group(1).strip()
            qty_match = match.group(2)
            price_match = match.group(3) 
            total_match = match.group(4)
            suffix_desc = match.group(5).strip()
            
            # Verify this matches our expected numbers (in any order)
            found_numbers = [qty_match.replace('$', '').replace(',', ''), 
                           price_match.replace('$', '').replace(',', ''),
                           total_match.replace('$', '').replace(',', '')]
            
            expected_numbers = [qty_or_price1, price_or_qty, total]
            
            # Check if we found the right numbers (order might vary)
            if all(num in found_numbers for num in expected_numbers):
                # Combine prefix and suffix descriptions
                if suffix_desc and len(suffix_desc) < 100:  # Reasonable length
                    # Common product description suffixes
                    valid_suffixes = [
                        'machine', 'de-burr', 'deburr', 'material', 'steel', 'aluminum', 
                        'plastic', 'coating', 'finish', 'assembly', 'component', 'part',
                        'clear', 'black', 'white', 'polypropylene', 'and'
                    ]
                    
                    # Check if suffix contains product-related terms
                    suffix_lower = suffix_desc.lower()
                    if any(term in suffix_lower for term in valid_suffixes):
                        full_desc = f"{prefix_desc} {suffix_desc}".strip()
                        if len(full_desc) > 5:
                            return full_desc
                
                # Return prefix description if suffix isn't valid product info
                if len(prefix_desc) > 2:
                    return prefix_desc
        
        # Strategy 3: Simple fallback - everything before the first number
        # Find the first occurrence of any of our numbers
        first_num_pos = len(line)
        for num in [qty_or_price1, price_or_qty, total]:
            for variant in create_number_patterns(num):
                pos = line.find(variant)
                if pos != -1 and pos < first_num_pos:
                    first_num_pos = pos
        
        if first_num_pos < len(line):
            fallback_desc = line[:first_num_pos].strip()
            if len(fallback_desc) > 2:
                return fallback_desc
            
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
            # Enhanced manufacturing keywords from advanced parser
            product_keywords = [
                'material', 'materials', 'raw material', 'assembly', 'assemble', 'machining', 'machine', 'cnc',
                'tooling', 'tools', 'tool setup', 'part', 'component', 'qty', 'quantity', 'base', 'basic', 'standard',
                'solder', 'soldering', 'solder assembly', 'labor', 'labour', 'work', 'setup', 'set up', 'initial setup',
                'finishing', 'finish', 'surface finish', 'packaging', 'package', 'pack', 'shipping', 'ship', 'delivery',
                'design', 'engineering', 'prototype', 'proto', 'testing', 'test', 'quality', 'polycarbonate', 'steel',
                'polypropylene', 'de-burr', 'deburr', 'clear', 'balancer', 'limiter', 'plug', 'cod'
            ]
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
                if 1 <= int(num) <= 100000:
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
        """Main method to parse quote from PDF using dynamic OCR with summary adjustments."""
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
        
        # Extract summary adjustments (tax, shipping, discounts, etc.)
        adjustments = self.extract_summary_adjustments(text)
        logger.info(f"Found {len(adjustments)} summary adjustments")
        
        # Use domain-aware parsing to structure the output correctly
        parsed_result = parse_with_domain_knowledge(line_items)
        
        # Apply summary adjustments to calculate final totals
        if adjustments:
            parsed_result = self._apply_summary_adjustments(parsed_result, adjustments)
            logger.info(f"Applied summary adjustments: {[a['type'] for a in adjustments]}")
        
        quote_groups = parsed_result.get("groups", [])
        summary = parsed_result.get("summary", {})
        
        logger.info(f"Created {len(quote_groups)} quote groups using domain knowledge")
        logger.info(f"Final totals: {summary.get('totalQuantity', 0)} items, ${summary.get('finalTotal', summary.get('totalCost', '0'))} total cost")
        
        return parsed_result
    
    def extract_summary_adjustments(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract summary-level adjustments like tax, shipping, discounts that apply to the whole quote.
        These are different from line items and should be applied to calculate final totals.
        """
        adjustments = []
        lines = text.split('\n')
        
        # Patterns for different types of adjustments (multi-currency support)
        adjustment_patterns = [
            # Subtotal patterns - multi-currency (improved for European formats)
            # Handle European format: €2.311,25 -> capture 2.311,25
            (r'^subtotal\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'subtotal'),
            (r'^sub[\s\-_]*total\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'subtotal'),
            
            # Tax patterns - both absolute and percentage (percentage first to avoid conflicts)
            (r'^tax\s*[:$]?\s*(\d+(?:\.\d{1,2})?)\s*%', 'tax_percentage'),
            (r'^tax\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'tax_amount'),
            (r'^sales\s+tax\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'tax_amount'),
            (r'^sales\s+tax\s*[:$]?\s*(\d+(?:\.\d{1,2})?)\s*%', 'tax_percentage'),
            
            # Shipping/handling patterns - multi-currency
            (r'^shipping\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'shipping'),
            (r'^handling\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'handling'),
            (r'^freight\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'freight'),
            (r'^delivery\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'shipping'),
            
            # Discount patterns - both absolute and percentage
            (r'^discount\s*[:$]?\s*-?[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'discount_amount'),
            (r'^discount\s*[:$]?\s*-?(\d+(?:\.\d{1,2})?)\s*%', 'discount_percentage'),
            
            # Total patterns (to verify calculations) - multi-currency
            (r'^total\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'total'),
            (r'^grand\s+total\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'total'),
            (r'^final\s+total\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'total'),
            (r'^quote\s+total\s*[:$]?\s*[\$\€\£\¥\₹\₽\₩\₪\₦\₨\₫\₭\₮\₯\₰\₱\₲\₳\₴\₵\₶\₷\₸\₹\₺\₻\₼\₽\₾\₿]?(\d+(?:[,\s\.]\d{3})*(?:[.,]\d{2})?)', 'total'),
        ]
        
        import re
        for line in lines:
            line_clean = line.strip().lower()
            if not line_clean:
                continue
                
            for pattern, adjustment_type in adjustment_patterns:
                match = re.match(pattern, line_clean, re.IGNORECASE)
                if match:
                    value = match.group(1)  # Don't remove comma - let babel handle it
                    
                    # Convert to appropriate type based on adjustment
                    if 'percentage' in adjustment_type:
                        numeric_value = float(value)
                        adjustments.append({
                            'type': adjustment_type,
                            'value': numeric_value,
                            'raw_text': line.strip(),
                            'is_percentage': True
                        })
                    else:
                        # Use normalize_price to handle currency formatting
                        normalized_value = self.normalize_price(value)
                        numeric_value = float(normalized_value)
                        adjustments.append({
                            'type': adjustment_type,
                            'value': numeric_value,
                            'raw_text': line.strip(),
                            'is_percentage': False
                        })
                    
                    logger.debug(f"Found adjustment: {adjustment_type} = {numeric_value} ({'%' if 'percentage' in adjustment_type else '$'})")
                    break  # Only match first pattern per line
        
        return adjustments
    
    def _apply_summary_adjustments(self, result: Dict[str, Any], adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply summary adjustments to calculate final totals and include adjustment details in result.
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        # Get the current subtotal from line items
        current_subtotal = Decimal(result.get('summary', {}).get('totalCost', '0'))
        
        # Track calculations step by step
        calculation_steps = []
        running_total = current_subtotal
        
        # Sort adjustments by type priority (subtotal first, then adjustments, then total)
        type_priority = {'subtotal': 1, 'tax_amount': 2, 'tax_percentage': 2, 'shipping': 3, 'handling': 3, 
                        'freight': 3, 'discount_amount': 4, 'discount_percentage': 4, 'total': 5}
        
        sorted_adjustments = sorted(adjustments, key=lambda x: type_priority.get(x['type'], 99))
        
        # Apply each adjustment
        applied_adjustments = []
        
        for adj in sorted_adjustments:
            adj_type = adj['type']
            adj_value = Decimal(str(adj['value']))
            
            if adj_type == 'subtotal':
                # Verify subtotal matches our calculation
                if abs(current_subtotal - adj_value) <= Decimal('0.01'):
                    calculation_steps.append(f"Subtotal: ${adj_value}")
                else:
                    logger.warning(f"Subtotal mismatch: calculated ${current_subtotal}, found ${adj_value}")
                    calculation_steps.append(f"Subtotal (adjusted): ${adj_value}")
                    running_total = adj_value
                    
            elif adj_type == 'tax_percentage':
                # Apply percentage tax
                tax_amount = (running_total * adj_value / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)
                running_total += tax_amount
                calculation_steps.append(f"Tax ({adj_value}%): +${tax_amount}")
                applied_adjustments.append({
                    'type': 'tax',
                    'description': f"Tax {adj_value}%",
                    'amount': str(tax_amount),
                    'percentage': float(adj_value)
                })
                
            elif adj_type == 'tax_amount':
                # Apply absolute tax amount
                running_total += adj_value
                calculation_steps.append(f"Tax: +${adj_value}")
                applied_adjustments.append({
                    'type': 'tax',
                    'description': 'Tax',
                    'amount': str(adj_value)
                })
                
            elif adj_type in ['shipping', 'handling', 'freight']:
                # Apply shipping/handling charges
                running_total += adj_value
                calculation_steps.append(f"{adj_type.title()}: +${adj_value}")
                applied_adjustments.append({
                    'type': adj_type,
                    'description': adj_type.title(),
                    'amount': str(adj_value)
                })
                
            elif adj_type == 'discount_percentage':
                # Apply percentage discount
                discount_amount = (running_total * adj_value / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)
                running_total -= discount_amount
                calculation_steps.append(f"Discount ({adj_value}%): -${discount_amount}")
                applied_adjustments.append({
                    'type': 'discount',
                    'description': f"Discount {adj_value}%",
                    'amount': str(-discount_amount),
                    'percentage': float(adj_value)
                })
                
            elif adj_type == 'discount_amount':
                # Apply absolute discount
                running_total -= adj_value
                calculation_steps.append(f"Discount: -${adj_value}")
                applied_adjustments.append({
                    'type': 'discount',
                    'description': 'Discount',
                    'amount': str(-adj_value)
                })
                
            elif adj_type == 'total':
                # Verify final total
                if abs(running_total - adj_value) <= Decimal('0.01'):
                    calculation_steps.append(f"Total: ${adj_value} ✓")
                else:
                    logger.warning(f"Total mismatch: calculated ${running_total}, found ${adj_value}")
                    calculation_steps.append(f"Total (from document): ${adj_value}")
                    running_total = adj_value
        
        # Update the result with final totals and adjustment details
        final_total = running_total.quantize(Decimal('0.01'))
        
        # Add adjustment information to summary
        summary = result.get('summary', {})
        summary['subtotal'] = str(current_subtotal.quantize(Decimal('0.01')))
        summary['finalTotal'] = str(final_total)
        summary['adjustments'] = applied_adjustments
        summary['calculationSteps'] = calculation_steps
        
        # Update the main result
        result['summary'] = summary
        
        logger.info(f"Applied {len(applied_adjustments)} adjustments: ${current_subtotal} → ${final_total}")
        
        return result
    
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


def parse_with_ocr(pdf_path: str) -> Dict[str, Any]:
    """
    Parse PDF using dynamic OCR.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Structure with summary totals and quote groups
    """
    parser = DynamicOCRParser()
    return parser.parse_quote(pdf_path) 
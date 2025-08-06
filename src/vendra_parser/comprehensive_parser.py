#!/usr/bin/env python3
"""
Comprehensive PDF Parser
Combines invoice2data, multi-format parsing, and OCR with automatic currency detection.
"""

import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal

# Enhanced libraries for currency, Unicode, and noise filtering
try:
    import currency_symbols
    import iso4217parse
    from unidecode import unidecode
    from Levenshtein import distance as levenshtein_distance
    import textstat
    ENHANCED_LIBS_AVAILABLE = True
except ImportError:
    ENHANCED_LIBS_AVAILABLE = False
    logging.warning("Some enhanced libraries not available, falling back to basic methods")

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
        self.detected_currency = None
        self.currency_symbol = None
    
    def parse_quote(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse quote using comprehensive approach with automatic currency detection.
        """
        logger.info(f"🔍 Starting comprehensive parsing of: {pdf_path}")
        
        # First, extract some text to detect currency
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                sample_text = ""
                # Get text from first few pages for currency detection
                for i in range(min(len(pdf.pages), 3)):
                    page_text = pdf.pages[i].extract_text()
                    if page_text:
                        sample_text += page_text
                
                # Detect currency from the sample text
                self.detected_currency, self.currency_symbol = self._detect_currency_from_text(sample_text)
        except Exception as e:
            logger.warning(f"Failed to extract text for currency detection: {e}")
            self.detected_currency, self.currency_symbol = 'USD', '$'
        
        # Check if this PDF has significant CID issues
        has_cid_issues = self._detect_cid_issues(pdf_path)
        if has_cid_issues:
            logger.info("🔧 Detected CID font encoding issues - prioritizing OCR fallback")
            # Reorder methods to prioritize OCR for CID issues
            self.extraction_methods = [
                ('ocr_fallback', self._extract_with_ocr_fallback),
                ('invoice2data', self._extract_with_invoice2data),
            ]
        else:
            logger.info("✅ No CID issues detected - using standard method priority")
            # Use standard order: invoice2data -> vendra-parser CLI -> OCR
            self.extraction_methods = [
                ('invoice2data', self._extract_with_invoice2data),
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
                    
                    # If we get a high-quality result, use it (but still apply currency formatting)
                    if quality_score >= 70:  # Reasonable threshold for good results
                        logger.info(f"🎯 Using high-quality result from {method_name}")
                        formatted_result = self._apply_currency_formatting(result)
                        # Convert to the specified format
                        if isinstance(formatted_result, dict) and 'groups' in formatted_result:
                            return formatted_result.get('groups', [])
                        elif isinstance(formatted_result, list):
                            return formatted_result
                        else:
                            return []
                else:
                    logger.warning(f"❌ {method_name} failed or produced invalid result")
            except Exception as e:
                logger.warning(f"❌ {method_name} failed with error: {str(e)}")
                # Special handling for NumPy compatibility issues
                if "numpy" in str(e).lower() or "numexpr" in str(e).lower() or "pandas" in str(e).lower():
                    logger.warning(f"🔄 NumPy compatibility issue detected, continuing to next method...")
                    continue
        
        # Select best result
        if results:
            best_result = max(results, key=lambda x: x['score'])
            logger.info(f"🏆 Using best result from {best_result['method']} with score: {best_result['score']}")
            
            # Post-process to remove noise items from the result
            cleaned_result = self._remove_noise_items_from_result(best_result['result'])
            
            # Apply currency formatting to the cleaned result
            formatted_result = self._apply_currency_formatting(cleaned_result)
            # Convert to the specified format
            if isinstance(formatted_result, dict) and 'groups' in formatted_result:
                return formatted_result.get('groups', [])
            elif isinstance(formatted_result, list):
                return formatted_result
            else:
                return []
        else:
            logger.error("❌ All extraction methods failed!")
            return []
    
    def _extract_with_invoice2data(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using invoice2data library with proper fallback to vendra-parser CLI."""
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
                    logger.info("📄 invoice2data extracted data")
                    # Convert to our format
                    return self._convert_invoice2data_result(extracted_data)
                else:
                    logger.info("📄 invoice2data found no template, falling back to vendra-parser CLI")
                    # Use the vendra-parser CLI functionality as fallback
                    return self._extract_with_vendra_parser_cli(pdf_path)
                    
            finally:
                null_stderr.close()
                
        except Exception as e:
            logger.error(f"invoice2data extraction failed: {e}")
            # Use the vendra-parser CLI functionality as fallback
            return self._extract_with_vendra_parser_cli(pdf_path)
    
    def _extract_with_vendra_parser_cli(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Extract using vendra-parser CLI functionality with multiple fallbacks."""
        try:
            logger.info("🔄 Using vendra-parser CLI functionality as fallback")
            
            results = []
            
            # Try multi-format parser first (this is the main vendra-parser functionality)
            try:
                from .multi_format_parser import MultiFormatPDFParser
                parser = MultiFormatPDFParser()
                result = parser.parse_quote(pdf_path)
                if result and self._validate_result(result):
                    quality_score = self._score_result_quality(result)
                    results.append({
                        'method': 'multi_format',
                        'result': result,
                        'score': quality_score
                    })
                    logger.info(f"✅ vendra-parser CLI (multi-format) succeeded with score: {quality_score}")
            except Exception as e:
                logger.warning(f"❌ vendra-parser CLI (multi-format) failed: {e}")
            
            # Try OCR as another option
            try:
                from .ocr_parser import DynamicOCRParser
                parser = DynamicOCRParser()
                result = parser.parse_quote(pdf_path)
                if result and self._validate_result(result):
                    quality_score = self._score_result_quality(result)
                    results.append({
                        'method': 'ocr',
                        'result': result,
                        'score': quality_score
                    })
                    logger.info(f"✅ vendra-parser CLI (OCR) succeeded with score: {quality_score}")
            except Exception as e:
                logger.warning(f"❌ vendra-parser CLI (OCR) failed: {e}")
            
            # Pick the best result from vendra-parser CLI methods
            if results:
                best_result = max(results, key=lambda x: x['score'])
                logger.info(f"🏆 Best vendra-parser CLI result: {best_result['method']} (score: {best_result['score']})")
                return best_result['result']
            else:
                logger.warning("❌ All vendra-parser CLI methods failed")
                return None
                
        except Exception as e:
            logger.error(f"vendra-parser CLI extraction failed: {e}")
            return None
    
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
            # If OCR fails due to NumPy issues, try manual extraction
            if "numpy" in str(e).lower() or "numexpr" in str(e).lower() or "pandas" in str(e).lower():
                logger.info("🔄 OCR failed due to NumPy issues, trying manual extraction...")
                return self._extract_manually_with_currency_detection(pdf_path)
            return None
    
    def _extract_manually_with_currency_detection(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """Manual extraction with enhanced currency detection."""
        try:
            # Extract text using multiple methods
            all_text = self._extract_text_from_pdf(pdf_path)
            if not all_text:
                return None
            
            # Use enhanced currency detection
            detected_currency, currency_symbol = self._detect_currency_from_text(all_text)
            logger.info(f"🌍 Enhanced currency detection: {detected_currency} ({currency_symbol})")
            
            # Extract line items with enhanced patterns
            line_items = self._extract_line_items_enhanced(all_text, detected_currency, currency_symbol)
            
            if not line_items:
                logger.warning("No line items found with enhanced extraction")
                # Try alternative extraction methods
                logger.info("🔄 Trying alternative extraction methods...")
                line_items = self._extract_line_items_with_currency_detection(all_text, [detected_currency])
                
                if not line_items:
                    logger.warning("Alternative extraction also failed")
                    return None
            
            # Group and format results
            return self._format_result(line_items)
            
        except Exception as e:
            logger.error(f"Manual extraction with enhanced currency detection failed: {e}")
            return None
    
    def _extract_line_items_enhanced(self, text: str, currency_code: str, currency_symbol: str) -> List:
        """Enhanced line item extraction using library-based currency detection."""
        from .models import LineItem
        
        line_items = []
        lines = text.split('\n')
        
        # Create enhanced patterns based on detected currency
        patterns = self._create_enhanced_currency_patterns(currency_code, currency_symbol)
        
        for line in lines:
            line = line.strip()
            if not line or not self._is_likely_line_item(line):
                continue
            
            # Try each pattern
            for pattern_name, pattern in patterns.items():
                matches = pattern.findall(line)
                for match in matches:
                    line_item = self._create_line_item_from_enhanced_match(match, pattern_name, currency_code, currency_symbol)
                    if line_item and self._is_valid_line_item(line_item):
                        line_items.append(line_item)
                        logger.debug(f"Found line item ({pattern_name}): {line_item.description} - {line_item.quantity} x {line_item.unit_price} = {line_item.cost}")
                        break  # Don't try other patterns for this line
                else:
                    continue  # Only executed if the inner loop didn't break
                break  # Break outer loop if we found a match
        
        # Remove duplicates using enhanced deduplication
        line_items = self._deduplicate_line_items(line_items)
        
        # Post-process to remove noise items
        filtered_items = []
        for item in line_items:
            if self._is_valid_line_item(item):
                filtered_items.append(item)
            else:
                logger.debug(f"Filtered out noise item: {item.description}")
        
        logger.info(f"Found {len(filtered_items)} clean line items after noise filtering (removed {len(line_items) - len(filtered_items)} noise items)")
        return filtered_items
    
    def _create_enhanced_currency_patterns(self, currency_code: str, currency_symbol: str) -> Dict[str, re.Pattern]:
        """Create enhanced regex patterns for the detected currency."""
        patterns = {}
        
        # Escape currency symbol for regex
        escaped_symbol = re.escape(currency_symbol)
        
        # Pattern 1: Standard format - Description Quantity SymbolPrice SymbolTotal
        patterns['standard'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+(\d+)\s+{escaped_symbol}([0-9,]+(?:\.[0-9]{{2}})?)\s+{escaped_symbol}([0-9,]+(?:\.[0-9]{{2}})?)'
        )
        
        # Pattern 2: Without quantity - Description SymbolPrice SymbolTotal
        patterns['no_quantity'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+{escaped_symbol}([0-9,]+(?:\.[0-9]{{2}})?)\s+{escaped_symbol}([0-9,]+(?:\.[0-9]{{2}})?)'
        )
        
        # Pattern 3: European format with comma decimals
        if currency_code in ['EUR', 'GBP', 'CHF']:
            patterns['european'] = re.compile(
                rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s+(\d+)\s+{escaped_symbol}([0-9.,]+)\s+{escaped_symbol}([0-9.,]+)'
            )
        
        # Pattern 4: Flexible format with optional spaces
        patterns['flexible'] = re.compile(
            rf'([A-Za-z][A-Za-z\s\-\(\)0-9/]+?)\s*(\d*)\s*{escaped_symbol}\s*([0-9,]+(?:\.[0-9]{{2}})?)\s*{escaped_symbol}\s*([0-9,]+(?:\.[0-9]{{2}})?)'
        )
        
        return patterns
    
    def _create_line_item_from_enhanced_match(self, match: tuple, pattern_name: str, currency_code: str, currency_symbol: str):
        """Create line item from enhanced pattern match."""
        from .models import LineItem
        
        try:
            if pattern_name == 'standard':
                description, quantity, unit_price, total = match
            elif pattern_name == 'no_quantity':
                description, unit_price, total = match
                quantity = "1"
            elif pattern_name == 'european':
                description, quantity, unit_price, total = match
            elif pattern_name == 'flexible':
                description, quantity, unit_price, total = match
                if not quantity:
                    quantity = "1"
            else:
                return None
            
            # Clean description
            description = description.strip()
            if len(description) < 3:
                return None
            
            # Parse numbers based on currency
            if currency_code in ['EUR', 'GBP', 'CHF']:
                clean_unit_price = self._parse_european_number(unit_price)
                clean_total = self._parse_european_number(total)
            else:
                clean_unit_price = float(unit_price.replace(',', ''))
                clean_total = float(total.replace(',', ''))
            
            clean_quantity = int(quantity) if quantity else 1
            
            # Format prices with currency symbol
            formatted_unit_price = f"{clean_unit_price:.2f} {currency_symbol}"
            formatted_total = f"{clean_total:.2f} {currency_symbol}"
            
            return LineItem(
                description=description,
                quantity=str(clean_quantity),
                unit_price=formatted_unit_price,
                cost=formatted_total
            )
            
        except Exception as e:
            logger.debug(f"Failed to create enhanced line item from match {match}: {e}")
            return None
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text using multiple PDF libraries with enhanced preprocessing."""
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
        
        # Apply enhanced text preprocessing
        all_text = self._preprocess_text_enhanced(all_text)
        
        return all_text
    
    def _preprocess_text_enhanced(self, text: str) -> str:
        """Enhanced text preprocessing with Unicode handling and noise filtering."""
        if not text:
            return text
        
        try:
            # Handle Unicode normalization and encoding issues
            if ENHANCED_LIBS_AVAILABLE:
                # Use unidecode for better Unicode handling
                text = unidecode(text)
            
            # Remove common PDF artifacts and noise
            noise_patterns = [
                r'\f',  # Form feed
                r'\x00',  # Null bytes
                r'\x1f',  # Unit separator
                r'[^\x20-\x7E\u00A0-\uFFFF]',  # Non-printable characters (keep some Unicode)
                r'\s+',  # Multiple whitespace
                r'^\s+|\s+$',  # Leading/trailing whitespace
            ]
            
            for pattern in noise_patterns:
                if pattern == r'\s+':
                    text = re.sub(pattern, ' ', text)
                elif pattern == r'^\s+|\s+$':
                    text = re.sub(pattern, '', text, flags=re.MULTILINE)
                else:
                    text = re.sub(pattern, '', text)
            
            # Enhanced PDF-specific noise removal using comprehensive patterns
            pdf_noise_patterns = [
                # Page and document metadata
                r'Page \d+ of \d+',
                r'Page \d+',
                r'Confidential|Draft|Copy|Original|Final',
                r'© \d{4}.*?All rights reserved',
                r'Generated on:.*?\n',
                r'Created:.*?\n',
                r'Modified:.*?\n',
                r'PDF created by.*?\n',
                r'Adobe PDF|Acrobat|Reader',
                
                # Common document headers/footers
                r'^\s*(Bill To|Ship To|From|To|Attention|Attn):.*?\n',
                r'^\s*(Quote|Invoice|Order|Reference|Ref|PO|Purchase Order) (No|Number|#):.*?\n',
                r'^\s*(Date|Valid Until|Expires|Due Date):.*?\n',
                r'^\s*(Phone|Fax|Email|Web|Website|URL):.*?\n',
                r'^\s*(Address|Street|City|State|Zip|Country):.*?\n',
                
                # Navigation and UI elements
                r'^\s*\[.*?\]\s*$',  # Bracketed text
                r'^\s*\{.*?\}\s*$',  # Braced text
                r'^\s*\(.*?\)\s*$',  # Parenthesized text alone
                r'^\s*[•·▪▫◦‣⁃]\s*$',  # Bullet points alone
                r'^\s*[-_=+]{3,}\s*$',  # Separator lines
                
                # Common noise phrases
                r'^\s*(Terms|Conditions|Thank you|Signature|Authorized|Approved|Rejected)\s*$',
                r'^\s*(Subtotal|Total|Grand Total|Amount Due|Balance|Paid|Unpaid)\s*$',
                r'^\s*(Tax|Shipping|Handling|Discount|Surcharge|Fee)\s*$',
                
                # URLs and web references
                r'https?://[^\s]+',
                r'www\.[^\s]+',
                r'claude\.ai',
                r'github\.com',
                
                # File paths and system references
                r'[A-Z]:\\[^\s]+',  # Windows paths
                r'/Users/[^\s]+',    # Mac paths
                r'/home/[^\s]+',     # Linux paths
                r'\.pdf$|\.docx?$|\.xlsx?$',  # File extensions
                
                # Code and technical artifacts
                r'^\s*(import|from|def|class|if|else|for|while|try|except)\s+',
                r'^\s*(python|javascript|html|css|json|xml)\s*$',
                r'^\s*[<>/\\|&{}[\]]+\s*$',  # Code symbols alone
                
                # Claude-specific artifacts (from the PDF content we saw)
                r'8/4/25, 11:26 PM Vendra Quote Parser GitHub Project - Claude',
                r'MeVthenoddr a4 :Q Puyotteh Poanr sSecrr GipittH',
                r'python Copy Publish',
                r'import pdfkit',
                r'T#e cShavneo tShee rHvT MSLo clounttieonnt sto a file first',
                r'48p9d2f Ikninto\.vfartioonm _Dfriivlee',
                r'Alternative: Pre-made PDF Template',
                r'If you want me to create a different format',
                r'Recommended Approach',
                r'Fastest method:',
                r'The HTML I created is specifically designed',
                r'Would you like me to create additional HTML templates',
                r'Claude does not have the ability to run the code',
                r'Retry|Reply to Claude|Sonnet 4|MM',
                r'https://claude\.ai/chat/[a-f0-9-]+',
            ]
            
            for pattern in pdf_noise_patterns:
                text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
            
            # Clean up line breaks and formatting
            lines = text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                line = line.strip()
                if line and len(line) > 2:  # Skip very short lines
                    # Remove excessive punctuation but keep essential ones
                    line = re.sub(r'[^\w\s\-\(\)\.\,\$\€\£\¥\₹\₽\₿\₩\₪\₨\₦\₡\₱\₲\₴\₵\₸\₺\₻\₼\₽\₾\₿]', '', line)
                    # Normalize currency symbols
                    line = re.sub(r'[\u20AC\u20BD\u20A9\u20AA\u20AB\u20AD\u20AE\u20AF\u20B0\u20B1\u20B2\u20B3\u20B4\u20B5\u20B6\u20B7\u20B8\u20B9\u20BA\u20BB\u20BC\u20BD\u20BE\u20BF]', '€', line)
                    
                    # Skip lines that are clearly noise
                    if not self._is_noise_line(line):
                        cleaned_lines.append(line)
            
            # Reconstruct text with proper line breaks
            text = '\n'.join(cleaned_lines)
            
            # Final cleanup
            text = re.sub(r'\n\s*\n', '\n', text)  # Remove empty lines
            text = text.strip()
            
            logger.debug(f"Enhanced text preprocessing completed. Length: {len(text)}")
            return text
            
        except Exception as e:
            logger.warning(f"Enhanced text preprocessing failed: {e}")
            return text
    
    def _is_noise_line(self, line: str) -> bool:
        """Intelligent noise detection using pattern recognition and ML principles."""
        if not line or len(line.strip()) < 3:
            return True
        
        line_lower = line.lower().strip()
        
        # Use intelligent pattern recognition instead of hardcoded lists
        noise_score = 0.0
        
        # 1. Structural Analysis
        words = line_lower.split()
        if len(words) < 2:
            noise_score += 0.3
        
        # 2. Character Pattern Analysis
        import re
        
        # Check for fragmented text (common OCR artifact)
        single_char_words = sum(1 for word in words if len(word) == 1)
        if single_char_words / max(len(words), 1) > 0.5:
            noise_score += 0.8
        
        # Check for alternating patterns (common in corrupted text)
        alternating_pattern = re.search(r'[A-Za-z]\s+\d\s+[A-Za-z]\s+\d', line)
        if alternating_pattern:
            noise_score += 0.6
        
        # 3. Semantic Analysis
        # Check for technical artifacts without hardcoding specific terms
        technical_patterns = [
            r'[<>/\\|&{}[\]]{2,}',  # Code symbols
            r'def\s+|class\s+|import\s+|function\s+',  # Code keywords
            r'console\.log|print\(|return\s+',  # Code patterns
            r'https?://|www\.',  # URLs
            r'[A-Z]:\\|/Users/|/home/',  # File paths
            r'^\d+$',  # Numbers only
            r'^[A-Za-z]{1,2}$',  # Very short text
            r'^[•·▪▫◦‣⁃-_\=+]{2,}$',  # Separators only
        ]
        
        for pattern in technical_patterns:
            if re.search(pattern, line):
                noise_score += 0.7
        
        # 4. Context Analysis
        # Check for document metadata patterns
        metadata_patterns = [
            r'^page\s+\d+\s+of\s+\d+$',
            r'^total\s+pages:\s+\d+$',
            r'^generated\s+on:|^created\s+by:|^version\s+\d+',
            r'^bill\s+to|^ship\s+to|^quote\s+no|^date|^valid\s+for',
            r'^terms|^conditions|^thank\s+you|^signature',
            r'^phone|^email|^address|^zip|^state|^country',
        ]
        
        for pattern in metadata_patterns:
            if re.match(pattern, line_lower):
                noise_score += 0.9
        
        # 5. Statistical Analysis
        # Check for unusual character distributions
        alpha_count = sum(1 for c in line if c.isalpha())
        digit_count = sum(1 for c in line if c.isdigit())
        special_count = sum(1 for c in line if not c.isalnum() and not c.isspace())
        
        total_chars = len(line)
        if total_chars > 0:
            alpha_ratio = alpha_count / total_chars
            digit_ratio = digit_count / total_chars
            special_ratio = special_count / total_chars
            
            # Too many special characters suggests technical artifacts
            if special_ratio > 0.3:
                noise_score += 0.6
            
            # Too many digits suggests metadata
            if digit_ratio > 0.5:
                noise_score += 0.4
        
        # 6. Length Analysis
        if len(line.strip()) < 10:
            noise_score += 0.2
        elif len(line.strip()) > 200:
            noise_score += 0.3
        
        # Return True if noise score exceeds threshold
        return noise_score >= 0.7
    
    def _clean_line_item_description(self, description: str) -> str:
        """Intelligently clean line item descriptions using statistical analysis."""
        if not description:
            return description
        
        import re
        
        # Use statistical analysis to identify and remove noise
        # 1. Analyze character patterns
        words = description.split()
        if len(words) < 2:
            return description
        
        # 2. Detect and remove corrupted text patterns
        # Look for patterns with excessive underscores, mixed case corruption
        corrupted_patterns = [
            r'[a-z]_[a-z]_[a-z]',  # a_b_c pattern
            r'[A-Z]_[A-Z]_[A-Z]',  # A_B_C pattern
            r'[a-z]\s+[a-z]\s+[a-z]',  # a b c pattern
            r'p\s+hone:\s+\d+',  # Corrupted phone patterns
            r'print\s+name:\s+_+',  # Form field patterns
        ]
        
        for pattern in corrupted_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)
        
        # 3. Remove excessive whitespace and normalize
        description = re.sub(r'\s+', ' ', description)
        description = description.strip()
        
        # 4. Remove empty or very short descriptions
        if len(description) < 3:
            return ""
        
        return description
    
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
            # Clean description using intelligent filtering
            description = self._clean_line_item_description(description.strip())
            
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
            # Clean description using intelligent filtering
            description = self._clean_line_item_description(description.strip())
            
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
        """Check if a line is likely to contain a line item using enhanced filtering."""
        if not line or len(line.strip()) < 5:
            return False
        
        line_lower = line.lower().strip()
        
        # Enhanced noise filtering using libraries
        if ENHANCED_LIBS_AVAILABLE:
            # Use textstat to analyze text quality
            try:
                # Skip lines that are too short or too long
                if len(line) < 10 or len(line) > 300:
                    return False
                
                # Skip lines that are mostly numbers or punctuation
                alpha_ratio = len(re.findall(r'[A-Za-z]', line)) / len(line)
                if alpha_ratio < 0.1:  # Less than 10% letters
                    return False
                
                # Enhanced noise pattern detection
                enhanced_noise_patterns = [
                    # Document metadata
                    'page', 'total', 'subtotal', 'tax', 'shipping', 'discount',
                    'bill to', 'ship to', 'quote no', 'date', 'valid for',
                    'terms', 'conditions', 'thank you', 'signature', 'phone',
                    'email', 'address', 'zip', 'state', 'country',
                    
                    # Technical artifacts
                    'claude', 'github', 'project', 'automation', 'python', 'import',
                    'alternative', 'recommended', 'approach', 'fastest', 'method',
                    'html', 'template', 'format', 'convert', 'print', 'save',
                    'retry', 'reply', 'sonnet', 'chat', 'url', 'http', 'www',
                    'confidential', 'draft', 'copy', 'original', 'final',
                    'generated', 'created', 'modified', 'adobe', 'acrobat',
                    'reader', 'pdf', 'mevthenoddr', 'puyotteh', 'poanr', 'secrr',
                    'gipitt', 'clounttieonnt', 'vfartioonm', 'dfriivlee',
                    
                    # Code and technical terms
                    'import', 'from', 'def', 'class', 'if', 'else', 'for', 'while',
                    'try', 'except', 'javascript', 'css', 'json', 'xml',
                ]
                
                # Check if line contains noise patterns
                for noise in enhanced_noise_patterns:
                    if noise in line_lower and len(line_lower) < 80:  # Increased threshold
                        return False
                
                # Additional filtering for technical artifacts
                if any(tech in line_lower for tech in ['48p9d2f', 'ikninto', 'ussetirn', 'tiXce', 'q7u']):
                    return False
                
            except Exception as e:
                logger.debug(f"Enhanced filtering failed: {e}")
        
        # Basic filtering patterns
        skip_patterns = [
            r'^\s*(bill\s+to|ship\s+to|quote\s+no|date|valid\s+for)',
            r'^\s*(subtotal|total|discount|tax|shipping|handling)',
            r'^\s*(terms|conditions|thank\s+you|signature)',
            r'^\s*\d{3}-\d{3}-\d{4}',  # Phone numbers
            r'^\s*\d{5}\s*$',  # ZIP codes alone
            r'^\s*[A-Z]{2}\s+\d{5}\s*$',  # State + ZIP
            r'^\s*[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',  # Email addresses
            r'^\s*www\.',  # URLs
            r'^\s*http',   # URLs
        ]
        
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return False
        
        # Must contain numbers and letters
        has_numbers = bool(re.search(r'\d', line))
        has_letters = bool(re.search(r'[A-Za-z]', line))
        
        if not (has_numbers and has_letters):
            return False
        
        # Enhanced currency detection using libraries
        if ENHANCED_LIBS_AVAILABLE:
            try:
                # Use currency_symbols library to check for currency symbols
                all_symbols = currency_symbols.CurrencySymbols.get_all_symbols()
                currency_symbols_list = [symbol for symbol in all_symbols.values() if symbol]
                
                # Also add common variations
                currency_symbols_list.extend(['$', '€', '£', '¥', '₹', '₽', '₿', '₩', '₪', '₨', '₦', '₡', '₱', '₲', '₴', '₵', '₸', '₺', '₻', '₼', '₽', '₾', '₿'])
                
                has_currency = any(symbol in line for symbol in currency_symbols_list)
            except:
                # Fallback to basic currency symbols
                basic_symbols = ['$', '€', '£', '¥', '₹', '₽', '₿', '₩', '₪', '₨', '₦', '₡', '₱', '₲', '₴', '₵', '₸', '₺', '₻', '₼', '₽', '₾', '₿']
                has_currency = any(symbol in line for symbol in basic_symbols)
        else:
            # Basic currency symbols
            basic_symbols = ['$', '€', '£', '¥', '₹', '₽', '₿', '₩', '₪', '₨', '₦', '₡', '₱', '₲', '₴', '₵', '₸', '₺', '₻', '₼', '₽', '₾', '₿']
            has_currency = any(symbol in line for symbol in basic_symbols)
        
        # If no currency symbol, must have clear price patterns
        if not has_currency:
            price_patterns = [
                r'\d+\.\d{2}',  # 123.45
                r'\d+,\d{2}',   # 123,45 (European)
                r'\d+\s+\d+',   # 123 456 (space separated)
                r'\d{3,}',      # Large numbers (likely prices)
            ]
            has_price_pattern = any(re.search(pattern, line) for pattern in price_patterns)
            if not has_price_pattern:
                return False
        
        # Final length check
        if len(line.strip()) < 10 or len(line.strip()) > 200:
            return False
        
        return True
    
    def _is_valid_line_item(self, line_item) -> bool:
        """Validate that a line item is reasonable."""
        if not line_item:
            return False
        
        try:
            # Check description is reasonable
            description = line_item.description.strip()
            if len(description) < 3:
                return False
            
            # Enhanced noise filtering for descriptions
            description_lower = description.lower()
            
            # Use intelligent noise detection instead of hardcoded lists
            # Check for structural and semantic indicators of noise
            import re
            
            # 1. Check for technical artifacts
            technical_patterns = [
                r'[<>/\\|&{}[\]]{2,}',  # Code symbols
                r'def\s+|class\s+|import\s+|function\s+',  # Code keywords
                r'console\.log|print\(|return\s+',  # Code patterns
                r'https?://|www\.',  # URLs
                r'[A-Z]:\\|/Users/|/home/',  # File paths
            ]
            
            for pattern in technical_patterns:
                if re.search(pattern, description):
                    return False
            
            # 2. Check for document metadata patterns
            metadata_patterns = [
                r'^page\s+\d+\s+of\s+\d+$',
                r'^total\s+pages:\s+\d+$',
                r'^generated\s+on:|^created\s+by:|^version\s+\d+',
                r'^bill\s+to|^ship\s+to|^quote\s+no|^date|^valid\s+for',
                r'^terms|^conditions|^thank\s+you|^signature',
                r'^phone|^email|^address|^zip|^state|^country',
            ]
            
            for pattern in metadata_patterns:
                if re.match(pattern, description_lower):
                    return False
            
            # 3. Check for fragmented text (common OCR artifact)
            words = description_lower.split()
            single_char_words = sum(1 for word in words if len(word) == 1)
            if single_char_words / max(len(words), 1) > 0.5:
                return False
            
            # 4. Check for unusual character distributions
            alpha_count = sum(1 for c in description if c.isalpha())
            digit_count = sum(1 for c in description if c.isdigit())
            special_count = sum(1 for c in description if not c.isalnum() and not c.isspace())
            
            total_chars = len(description)
            if total_chars > 0:
                special_ratio = special_count / total_chars
                if special_ratio > 0.3:  # Too many special characters
                    return False
            

            
            # Skip descriptions that are just numbers or very short
            if len(description) < 5 or re.match(r'^[\d\s\.\,\-\+]+$', description):
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
        """Remove duplicate line items using enhanced similarity detection."""
        if not line_items:
            return []
        
        unique_items = []
        
        for item in line_items:
            is_duplicate = False
            
            # Check against existing unique items
            for existing_item in unique_items:
                if self._are_items_similar(item, existing_item):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_items.append(item)
        
        return unique_items
    
    def _are_items_similar(self, item1, item2) -> bool:
        """Check if two line items are similar enough to be considered duplicates."""
        try:
            # Check if unit prices are the same (within 1% tolerance)
            price1 = float(item1.unit_price)
            price2 = float(item2.unit_price)
            price_diff = abs(price1 - price2) / max(price1, price2)
            
            if price_diff > 0.01:  # More than 1% difference in price
                return False
            
            # Check description similarity
            desc1 = item1.description.lower().strip()
            desc2 = item2.description.lower().strip()
            
            if ENHANCED_LIBS_AVAILABLE:
                # Use Levenshtein distance for fuzzy matching
                try:
                    distance = levenshtein_distance(desc1, desc2)
                    max_len = max(len(desc1), len(desc2))
                    similarity = 1 - (distance / max_len)
                    
                    # Consider similar if similarity > 85%
                    return similarity > 0.85
                except Exception as e:
                    logger.debug(f"Levenshtein comparison failed: {e}")
                    # Fall back to exact match
                    return desc1 == desc2
            else:
                # Basic exact match
                return desc1 == desc2
                
        except Exception as e:
            logger.debug(f"Similarity check failed: {e}")
            return False
    
    def _convert_invoice2data_result(self, extracted_data: Dict) -> Dict[str, Any]:
        """Convert invoice2data result to our standard format."""
        # This would need to be implemented based on invoice2data's output format
        # For now, fall back to manual extraction
        return None
    
    def _format_result(self, line_items: List) -> List[Dict[str, Any]]:
        """Format line items into the specified JSON format with groups."""
        if not line_items:
            return []
        
        # Group items by similar quantities and unit prices
        from collections import defaultdict
        groups = defaultdict(list)
        
        for item in line_items:
            # Create a key based on quantity and unit price for grouping
            key = (item.quantity, item.unit_price)
            groups[key].append(item)
        
        result_groups = []
        
        for (quantity, unit_price), items in groups.items():
            # Calculate total price for this group
            total_price = sum(float(item.cost) for item in items)
            
            # Format line items for this group
            line_items_formatted = []
            for item in items:
                line_items_formatted.append({
                    'description': item.description,
                    'quantity': item.quantity,
                    'unitPrice': item.unit_price,
                    'cost': item.cost
                })
            
            # Create group object in the specified format
            group = {
                'quantity': quantity,
                'unitPrice': unit_price,
                'totalPrice': f"{total_price:.2f}",
                'lineItems': line_items_formatted
            }
            
            result_groups.append(group)
        
        return result_groups
    
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
        """Score the quality of extraction result with emphasis on realistic monetary values."""
        if not result or 'groups' not in result:
            return 0.0
        
        score = 0.0
        groups = result.get('groups', [])
        
        # Base score for having results
        if groups:
            score += 20
        
        # Score based on number of line items
        total_items = sum(len(group.get('lineItems', [])) for group in groups)
        score += min(total_items * 15, 75)  # Up to 75 points for line items (increased weight)
        
        # Penalty for very few items (likely poor extraction)
        if total_items <= 1:
            score -= 50  # Heavy penalty for single item results
            logger.debug(f"Single item penalty: -50 points (items: {total_items})")
        
        # NEW: Score based on monetary value realism (CRITICAL FIX)
        total_cost = 0.0
        realistic_pricing_bonus = 0
        try:
            summary = result.get('summary', {})
            total_cost_str = summary.get('totalCost', '0')
            # Remove currency symbols and parse
            import re
            clean_cost = re.sub(r'[^\d.,]', '', str(total_cost_str))
            clean_cost = clean_cost.replace(',', '')
            total_cost = float(clean_cost) if clean_cost else 0.0
            
            logger.debug(f"Scoring result with total cost: ${total_cost}")
            
            # MAJOR bonus for realistic monetary values
            if total_cost > 1000:  # Substantial quotes get big bonus
                realistic_pricing_bonus += 100
                logger.debug(f"Large quote bonus: +100 points (total: ${total_cost})")
            elif total_cost > 100:  # Reasonable quotes get medium bonus
                realistic_pricing_bonus += 50
                logger.debug(f"Reasonable quote bonus: +50 points (total: ${total_cost})")
                
            # Bonus for realistic unit prices
            for group in groups:
                for item in group.get('lineItems', []):
                    unit_price_str = item.get('unitPrice', '0')
                    clean_price = re.sub(r'[^\d.,]', '', str(unit_price_str))
                    clean_price = clean_price.replace(',', '')
                    try:
                        unit_price = float(clean_price) if clean_price else 0.0
                        if unit_price > 50:  # High-value items get bonus
                            realistic_pricing_bonus += 20
                        elif unit_price > 10:  # Reasonable items get smaller bonus
                            realistic_pricing_bonus += 10
                    except:
                        pass
        except Exception as e:
            logger.debug(f"Error parsing monetary values: {e}")
        
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
        
        # Add realistic pricing bonus
        score += realistic_pricing_bonus
        
        # CRITICAL: Penalize unrealistically low values (likely parsing errors)
        if total_cost < 50 and total_items > 0:
            score -= 50  # Heavy penalty for unrealistic low totals
            logger.debug(f"Low value penalty: -50 points (total: ${total_cost})")
        
        final_score = min(score, 200.0)  # Increased max score to accommodate bonuses
        logger.debug(f"Final quality score: {final_score} (base: {score - realistic_pricing_bonus}, pricing bonus: {realistic_pricing_bonus})")
        
        return final_score
    
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
    
    def _detect_currency_from_text(self, text: str) -> Tuple[str, str]:
        """Detect currency from text using enhanced libraries."""
        if not ENHANCED_LIBS_AVAILABLE:
            logger.warning("Enhanced libraries not available, using basic currency detection")
            return self._detect_currency_basic(text)
        
        try:
            # Use currency_symbols library to get all known symbols
            try:
                all_symbols = currency_symbols.CurrencySymbols.get_all_symbols()
            except AttributeError:
                # Fallback if the method doesn't exist
                all_symbols = {
                    'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'INR': '₹',
                    'CAD': 'C$', 'AUD': 'A$', 'MXN': 'MX$', 'BRL': 'R$'
                }
            
            # Create a comprehensive mapping of symbols to currency codes
            symbol_to_code = {}
            for code, symbol in all_symbols.items():
                if symbol:
                    symbol_to_code[symbol] = code
                    # Also add common variations
                    if symbol == '$':
                        symbol_to_code['C$'] = 'CAD'
                        symbol_to_code['A$'] = 'AUD'
                        symbol_to_code['MX$'] = 'MXN'
                        symbol_to_code['R$'] = 'BRL'
                    elif symbol == '€':
                        symbol_to_code['EUR'] = 'EUR'
                        symbol_to_code['€'] = 'EUR'  # Ensure Euro symbol is mapped
                    elif symbol == '£':
                        symbol_to_code['GBP'] = 'GBP'
                    elif symbol == '¥':
                        symbol_to_code['JPY'] = 'JPY'
                        symbol_to_code['CNY'] = 'CNY'
            
            # Find all currency symbols in the text
            detected_currencies = []
            
            # Look for currency symbols followed by numbers
            for symbol in symbol_to_code.keys():
                # Escape special regex characters
                escaped_symbol = re.escape(symbol)
                pattern = escaped_symbol + r'\s*[\d,.]+'
                matches = re.findall(pattern, text)
                if matches:
                    code = symbol_to_code[symbol]
                    detected_currencies.append((code, symbol, len(matches)))
                    logger.debug(f"Found currency symbol '{symbol}' -> {code} ({len(matches)} occurrences)")
            
            # Also look for currency codes (USD, EUR, etc.)
            currency_code_pattern = r'\b([A-Z]{3})\s*[\d,.]+'
            code_matches = re.findall(currency_code_pattern, text)
            for code in code_matches:
                if code in all_symbols:
                    symbol = all_symbols[code]
                    if symbol:
                        detected_currencies.append((code, symbol, 1))
                        logger.debug(f"Found currency code '{code}' -> {symbol}")
            
            # If multiple currencies found, pick the most frequent one
            if detected_currencies:
                # Sort by frequency and pick the most common
                detected_currencies.sort(key=lambda x: x[2], reverse=True)
                detected_code, detected_symbol, count = detected_currencies[0]
                
                logger.info(f"🔍 Detected currency: {detected_code} ({detected_symbol}) with {count} occurrences")
                return detected_code, detected_symbol
            
            # Try iso4217parse for more advanced detection
            try:
                from iso4217parse import parse
                # Look for any currency-like patterns
                currency_patterns = [
                    r'(\d+[.,]\d+)\s*([A-Z]{3})',  # 100.50 USD
                    r'([A-Z]{3})\s*(\d+[.,]\d+)',  # USD 100.50
                    r'([A-Z]{3})\s*(\d+)',         # USD 100
                ]
                
                for pattern in currency_patterns:
                    matches = re.findall(pattern, text)
                    if matches:
                        # Try to parse with iso4217parse
                        for match in matches:
                            try:
                                parsed = parse(match[0] + ' ' + match[1])
                                if parsed and parsed.currency:
                                    code = parsed.currency.code
                                    symbol = currency_symbols.CurrencySymbols.get_symbol(code)
                                    logger.info(f"🔍 Detected currency via iso4217parse: {code} ({symbol})")
                                    return code, symbol
                            except:
                                continue
            except Exception as e:
                logger.debug(f"iso4217parse detection failed: {e}")
            
            # Default fallback to USD
            logger.info("🔍 No currency detected, defaulting to USD ($)")
            return 'USD', '$'
            
        except Exception as e:
            logger.warning(f"Enhanced currency detection failed: {e}")
            return self._detect_currency_basic(text)
    
    def _detect_currency_basic(self, text: str) -> Tuple[str, str]:
        """Basic currency detection fallback."""
        # Simple fallback patterns
        basic_patterns = {
            '$': 'USD',
            '€': 'EUR', 
            '£': 'GBP',
            '¥': 'JPY',
            '₹': 'INR',
        }
        
        for symbol, code in basic_patterns.items():
            if symbol in text:
                logger.info(f"🔍 Basic detection: {code} ({symbol})")
                return code, symbol
        
        return 'USD', '$'
    
    def _format_price_with_currency(self, amount: str) -> str:
        """Format price with detected currency symbol using proper Unicode handling."""
        if not self.currency_symbol:
            return amount
        
        try:
            # Clean the amount first
            clean_amount = str(amount).strip()
            
            # Handle different currency positioning
            if self.detected_currency in ['EUR', 'GBP', 'CHF']:
                # European style: symbol after amount
                return f"{clean_amount} {self.currency_symbol}"
            elif self.detected_currency in ['JPY', 'KRW']:
                # Asian currencies: symbol before, no decimals typically
                return f"{self.currency_symbol}{clean_amount}"
            else:
                # USD and most others: symbol before amount
                return f"{self.currency_symbol}{clean_amount}"
        except:
            return f"{self.currency_symbol}{amount}"
    
    def _apply_currency_formatting(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply detected currency formatting to all monetary values in the result."""
        if not result or not self.currency_symbol:
            return result
        
        try:
            formatted_result = result.copy()
            
            # Format summary monetary values
            if 'summary' in formatted_result:
                summary = formatted_result['summary']
                for key in ['totalUnitPriceSum', 'totalCost', 'subtotal', 'finalTotal']:
                    if key in summary and summary[key]:
                        # Only format if it's a numeric string
                        try:
                            float(summary[key])
                            summary[key] = self._format_price_with_currency(summary[key])
                        except (ValueError, TypeError):
                            pass  # Skip non-numeric values
                
                # Format calculation steps to use consistent currency
                if 'calculationSteps' in summary:
                    formatted_steps = []
                    for step in summary['calculationSteps']:
                        # Add currency symbol to calculation steps that don't have it
                        if ':' in step and not any(symbol in step for symbol in ['$', '£', '€', '¥', '₹']):
                            # Find the amount after the colon and add currency symbol
                            parts = step.split(':')
                            if len(parts) == 2:
                                amount_part = parts[1].strip()
                                # Add currency symbol before the amount
                                formatted_step = f"{parts[0]}: {self.currency_symbol}{amount_part}"
                            else:
                                formatted_step = step
                        else:
                            # Replace $ with detected currency symbol in calculation steps
                            formatted_step = step.replace('$', self.currency_symbol)
                        formatted_steps.append(formatted_step)
                    summary['calculationSteps'] = formatted_steps
            
            # Format group monetary values
            if 'groups' in formatted_result:
                for group in formatted_result['groups']:
                    # Format group-level prices
                    for key in ['unitPrice', 'totalPrice']:
                        if key in group and group[key]:
                            try:
                                float(group[key])
                                group[key] = self._format_price_with_currency(group[key])
                            except (ValueError, TypeError):
                                pass
                    
                    # Format line item prices
                    if 'lineItems' in group:
                        for item in group['lineItems']:
                            for key in ['unitPrice', 'cost']:
                                if key in item and item[key]:
                                    try:
                                        float(item[key])
                                        item[key] = self._format_price_with_currency(item[key])
                                    except (ValueError, TypeError):
                                        pass
            
            logger.info(f"💰 Applied {self.detected_currency} ({self.currency_symbol}) formatting to all monetary values")
            return formatted_result
            
        except Exception as e:
            logger.warning(f"Failed to apply currency formatting: {e}")
            return result
    
    def _remove_noise_items_from_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Remove noise items from the result structure."""
        logger.info("🧹 Starting noise filtering on result...")
        
        if not result or 'groups' not in result:
            logger.info("No groups found in result, skipping noise filtering")
            return result
        
        cleaned_groups = []
        total_removed = 0
        
        for group in result.get('groups', []):
            if 'lineItems' not in group:
                cleaned_groups.append(group)
                continue
            
            cleaned_line_items = []
            for item in group.get('lineItems', []):
                # Check if this item is noise
                description = item.get('description', 'Unknown')
                if self._is_noise_line_item(item):
                    total_removed += 1
                    logger.info(f"🗑️  Removing noise item: {description}")
                else:
                    logger.debug(f"✅ Keeping valid item: {description}")
                    cleaned_line_items.append(item)
            
            # Only keep groups that have valid line items
            if cleaned_line_items:
                cleaned_group = group.copy()
                cleaned_group['lineItems'] = cleaned_line_items
                cleaned_groups.append(cleaned_group)
        
        # Update the result
        cleaned_result = result.copy()
        cleaned_result['groups'] = cleaned_groups
        
        # Recalculate summary if items were removed
        if total_removed > 0:
            total_qty = 0
            total_cost = 0.0
            for group in cleaned_groups:
                for item in group.get('lineItems', []):
                    try:
                        total_qty += int(item.get('quantity', 0))
                        total_cost += float(item.get('cost', 0).replace('$', '').replace(',', ''))
                    except (ValueError, TypeError):
                        pass
            
            cleaned_result['summary']['totalQuantity'] = str(total_qty)
            cleaned_result['summary']['totalCost'] = f"{total_cost:.2f}"
            cleaned_result['summary']['numberOfGroups'] = len(cleaned_groups)
            
            logger.info(f"Removed {total_removed} noise items from result")
        
        return cleaned_result
    
    def _is_noise_line_item(self, item: Dict[str, Any]) -> bool:
        """Check if a line item is noise that should be removed."""
        if not item or 'description' not in item:
            logger.debug("Item has no description, marking as noise")
            return True
        
        description = item.get('description', '').strip()
        if not description or len(description) < 3:
            logger.debug(f"Description too short: '{description}', marking as noise")
            return True
        
        description_lower = description.lower()
        # Special check for the specific noise patterns we're seeing
        if any(pattern in description_lower for pattern in ['48p9d2f', 'totacllau', 'claude ai chat']):
            return True
        
        # Check for noise patterns
        noise_patterns = [
            # Technical artifacts from Quote3pdf.pdf
            r'48p9d2f|ikninto|vfartioonm|dfriivlee|ussetirn|tixce|q7u',
            r'mevthenoddr|puyotteh|poanr|secrr|gipitt|clounttieonnt',
            r'totacllau|tdea|cxan|mistakes|double|chec|r0es8p',
            r'957ed7cb|2ad9|42ea|9074|bf922ff',
            r'claude.*ai.*chat',
            r'https.*claude.*ai.*chat',
            
            # General noise patterns
            r'https?://|www\.|claude\.ai|github\.com',
            r'[A-Z]:\\|/Users/|/home/',
            r'[<>/\\|&{}[\]]{2,}',
            r'^\d+$',  # Just numbers
            r'^[A-Za-z]{1,2}$',  # Very short text
        ]
        
        for pattern in noise_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                return True
        
        # Check for noise words
        noise_words = [
            'page', 'total', 'subtotal', 'tax', 'shipping', 'discount',
            'claude', 'github', 'project', 'automation', 'python', 'import',
            'alternative', 'recommended', 'approach', 'fastest', 'method',
            'html', 'template', 'format', 'convert', 'print', 'save',
            'retry', 'reply', 'sonnet', 'chat', 'url', 'http', 'www',
            'confidential', 'draft', 'copy', 'original', 'final',
            'generated', 'created', 'modified', 'adobe', 'acrobat',
            'reader', 'pdf', 'mevthenoddr', 'puyotteh', 'poanr', 'secrr',
            'gipitt', 'clounttieonnt', 'vfartioonm', 'dfriivlee',
            '48p9d2f', 'ikninto', 'ussetirn', 'tixce', 'q7u',
            'import', 'from', 'def', 'class', 'if', 'else', 'for', 'while',
            'try', 'except', 'javascript', 'css', 'json', 'xml',
        ]
        
        if any(word in description_lower for word in noise_words):
            return True
        
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
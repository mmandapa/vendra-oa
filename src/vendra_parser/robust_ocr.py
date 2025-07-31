#!/usr/bin/env python3
"""
Robust OCR with accuracy improvement and validation strategies.
Implements multiple OCR engines, preprocessing, validation, and error correction.
"""

import re
import logging
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal, InvalidOperation
import json
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# Optional imports for enhanced OCR capabilities
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False

logger = logging.getLogger(__name__)


class RobustOCREngine:
    """Enhanced OCR engine with multiple strategies for accuracy improvement."""
    
    def __init__(self, confidence_threshold: float = 70.0):
        self.confidence_threshold = confidence_threshold
        self.ocr_engines = self._initialize_engines()
        
    def _initialize_engines(self) -> Dict[str, Any]:
        """Initialize available OCR engines."""
        engines = {}
        
        # Tesseract (primary engine)
        if PYTESSERACT_AVAILABLE:
            engines['tesseract'] = 'available'
        else:
            engines['tesseract'] = 'not_installed'
            
        # EasyOCR (secondary engine)
        if EASYOCR_AVAILABLE:
            try:
                engines['easyocr'] = easyocr.Reader(['en'])
            except Exception as e:
                logger.warning(f"EasyOCR initialization failed: {e}")
                engines['easyocr'] = 'failed'
        else:
            engines['easyocr'] = 'not_installed'
            
        # PaddleOCR (tertiary engine)
        if PADDLEOCR_AVAILABLE:
            try:
                engines['paddleocr'] = PaddleOCR(use_angle_cls=True, lang='en')
            except Exception as e:
                logger.warning(f"PaddleOCR initialization failed: {e}")
                engines['paddleocr'] = 'failed'
        else:
            engines['paddleocr'] = 'not_installed'
            
        logger.info(f"Initialized OCR engines: {engines}")
        return engines
    
    def preprocess_image_for_ocr(self, image_path: str) -> np.ndarray:
        """
        Strategy 1: OCR Preprocessing & Configuration
        Enhance image quality before OCR processing.
        """
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available, skipping image preprocessing")
            return None
            
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"Failed to load image: {image_path}")
                return None
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Increase contrast using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(enhanced)
            
            # Sharpen
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            sharpened = cv2.filter2D(denoised, -1, kernel)
            
            # Binarize (black and white)
            _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            logger.info("Image preprocessing completed successfully")
            return binary
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return None
    
    def optimized_tesseract_extraction(self, image_path: str) -> List[Tuple[str, float, str]]:
        """
        Use optimized OCR settings for financial documents with multiple PSM modes.
        """
        if not PYTESSERACT_AVAILABLE:
            return []
            
        results = []
        
        # Different PSM modes for different content types
        ocr_configs = [
            '--psm 6 -c tessedit_char_whitelist=0123456789.,$ ',  # Numbers and currency only
            '--psm 6',  # Uniform block of text
            '--psm 4',  # Single column of text
            '--psm 3',  # Fully automatic page segmentation
            '--psm 11', # Sparse text
            '--psm 13'  # Raw line. Treat image as single text line
        ]
        
        for config in ocr_configs:
            try:
                text = pytesseract.image_to_string(image_path, config=config)
                confidence = self._get_tesseract_confidence(image_path, config)
                results.append((text, confidence, config))
            except Exception as e:
                logger.warning(f"Tesseract config {config} failed: {e}")
                continue
        
        # Return best result based on confidence
        if results:
            best_result = max(results, key=lambda x: x[1])
            logger.info(f"Best Tesseract result: confidence={best_result[1]:.1f}, config={best_result[2]}")
            return [best_result]
        
        return []
    
    def _get_tesseract_confidence(self, image_path: str, config: str) -> float:
        """Get OCR confidence scores from Tesseract."""
        try:
            data = pytesseract.image_to_data(image_path, config=config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            return sum(confidences) / len(confidences) if confidences else 0
        except Exception as e:
            logger.warning(f"Failed to get Tesseract confidence: {e}")
            return 0
    
    def multi_engine_ocr(self, image_path: str) -> Dict[str, str]:
        """
        Strategy 2: Multiple OCR Engine Approach
        Try multiple OCR approaches and compare results.
        """
        results = {}
        
        # Method 1: Standard Tesseract
        if PYTESSERACT_AVAILABLE:
            try:
                img = Image.open(image_path)
                results['tesseract'] = pytesseract.image_to_string(img)
            except Exception as e:
                logger.warning(f"Standard Tesseract failed: {e}")
                results['tesseract'] = ""
        
        # Method 2: Tesseract with preprocessing
        if PYTESSERACT_AVAILABLE and CV2_AVAILABLE:
            try:
                processed_img = self.preprocess_image_for_ocr(image_path)
                if processed_img is not None:
                    pil_img = Image.fromarray(processed_img)
                    results['tesseract_processed'] = pytesseract.image_to_string(pil_img)
                else:
                    results['tesseract_processed'] = ""
            except Exception as e:
                logger.warning(f"Tesseract with preprocessing failed: {e}")
                results['tesseract_processed'] = ""
        
        # Method 3: EasyOCR
        if self.ocr_engines.get('easyocr') and hasattr(self.ocr_engines['easyocr'], 'readtext'):
            try:
                result = self.ocr_engines['easyocr'].readtext(image_path)
                results['easyocr'] = ' '.join([item[1] for item in result])
            except Exception as e:
                logger.warning(f"EasyOCR failed: {e}")
                results['easyocr'] = ""
        
        # Method 4: PaddleOCR
        if self.ocr_engines.get('paddleocr') and hasattr(self.ocr_engines['paddleocr'], 'ocr'):
            try:
                result = self.ocr_engines['paddleocr'].ocr(image_path, cls=True)
                if result and result[0]:
                    text = ' '.join([item[1][0] for item in result[0] if item[1][1] > 0.5])
                    results['paddleocr'] = text
                else:
                    results['paddleocr'] = ""
            except Exception as e:
                logger.warning(f"PaddleOCR failed: {e}")
                results['paddleocr'] = ""
        
        # Filter out empty results
        results = {k: v for k, v in results.items() if v.strip()}
        logger.info(f"Multi-engine OCR completed. Engines: {list(results.keys())}")
        
        return results
    
    def validate_ocr_numbers(self, ocr_text: str, expected_patterns: Optional[List[str]] = None) -> List[str]:
        """
        Strategy 3: OCR Result Validation
        Validate OCR extracted numbers against expected patterns.
        """
        issues = []
        
        # Extract all numbers from OCR text
        numbers = re.findall(r'[\d,]+\.?\d*', ocr_text)
        
        # Check for common OCR errors
        for num_str in numbers:
            # Check for unrealistic values
            try:
                value = float(num_str.replace(',', ''))
                
                # Flag suspiciously large numbers (might be merged)
                if value > 1000000:  # Over $1M might be suspicious
                    issues.append(f"Suspiciously large number: {num_str}")
                
                # Flag numbers with no decimals for prices (might be missing decimal)
                if '.' not in num_str and value > 100 and '$' in ocr_text:
                    issues.append(f"Price missing decimal?: {num_str}")
                    
            except ValueError:
                issues.append(f"Invalid number format: {num_str}")
        
        # Check for missing expected patterns
        if expected_patterns:
            for pattern in expected_patterns:
                if not re.search(pattern, ocr_text):
                    issues.append(f"Missing expected pattern: {pattern}")
        
        return issues
    
    def cross_validate_quantities(self, line_items: List[Any]) -> List[str]:
        """
        Validate quantities make sense in context.
        Handles both dictionary and LineItem objects.
        """
        issues = []
        
        for item in line_items:
            try:
                # Handle both dictionary and LineItem objects
                if hasattr(item, 'quantity'):
                    # LineItem object
                    qty = float(item.quantity)
                    unit_price = float(item.unit_price)
                    total = float(item.cost)
                elif isinstance(item, dict):
                    # Dictionary object
                    qty = float(item.get('quantity', 0))
                    unit_price = float(item.get('unit_price', item.get('unitPrice', 0)))  # Handle both formats
                    total = float(item.get('cost', 0))
                else:
                    issues.append(f"Unsupported item type: {type(item)}")
                    continue
                
                # Check if math adds up
                expected_total = qty * unit_price
                if abs(total - expected_total) > 0.01:  # Allow for rounding
                    issues.append(f"Math doesn't add up: {qty} × {unit_price} ≠ {total}")
                    
                # Check for unrealistic quantities
                if qty > 10000:  # Very high quantity might be OCR error
                    issues.append(f"Suspiciously high quantity: {qty}")
                    
                if qty < 0:
                    issues.append(f"Negative quantity: {qty}")
                    
            except (ValueError, TypeError, AttributeError) as e:
                issues.append(f"Invalid numeric values in item: {item} - Error: {e}")
        
        return issues
    
    def correct_common_ocr_errors(self, text: str) -> str:
        """
        Strategy 4: Smart Error Correction
        Fix common OCR character recognition errors.
        """
        corrections = {
            # Common character confusions
            r'\bO\b': '0',  # O instead of 0
            r'\bl\b': '1',  # l instead of 1  
            r'\bI\b': '1',  # I instead of 1
            r'\bS\b': '5',  # S instead of 5 (in numbers context)
            r'\bG\b': '6',  # G instead of 6
            
            # Currency symbol issues  
            r'\$\s*([Oo])\b': r'$0',  # $O becomes $0
            r'\$\s*([Il])\b': r'$1',  # $I or $l becomes $1
            
            # Decimal point issues
            r'(\d)\s+(\d\d)\b': r'\1.\2',  # "123 45" becomes "123.45"
            r'(\d),(\d\d\d),(\d\d)\b': r'\1\2.\3',  # Fix comma/decimal confusion
        }
        
        corrected_text = text
        for pattern, replacement in corrections.items():
            corrected_text = re.sub(pattern, replacement, corrected_text)
        
        return corrected_text
    
    def smart_quantity_correction(self, extracted_qty: str, context_clues: Dict[str, Any]) -> Optional[float]:
        """
        Use context to correct quantity extraction errors.
        """
        try:
            qty = float(extracted_qty)
            
            # If quantity seems too high, might be missing decimal
            if qty > 1000 and context_clues.get('decimal_expected', False):
                # Try common decimal placements
                candidates = [
                    qty / 10,    # 1234 -> 123.4
                    qty / 100,   # 1234 -> 12.34
                    qty / 1000   # 1234 -> 1.234
                ]
                
                # Return most reasonable candidate
                for candidate in candidates:
                    if 1 <= candidate <= 100:  # Reasonable quantity range
                        return candidate
            
            return qty
        except ValueError:
            return None
    
    def extract_with_confidence(self, image_path: str) -> Dict[str, Any]:
        """
        Strategy 5: Confidence-Based Parsing
        Extract data with confidence scores.
        """
        if not PYTESSERACT_AVAILABLE:
            return {'high_confidence': '', 'low_confidence': [], 'needs_review': True}
        
        try:
            # Get OCR data with confidence
            data = pytesseract.image_to_data(
                Image.open(image_path), 
                output_type=pytesseract.Output.DICT
            )
            
            # Build confidence map
            confident_text = []
            suspicious_text = []
            
            for i, word in enumerate(data['text']):
                confidence = int(data['conf'][i])
                if confidence > self.confidence_threshold:
                    confident_text.append(word)
                elif word.strip():  # Non-empty low-confidence text
                    suspicious_text.append((word, confidence))
            
            return {
                'high_confidence': ' '.join(confident_text),
                'low_confidence': suspicious_text,
                'needs_review': len(suspicious_text) > 0
            }
        except Exception as e:
            logger.error(f"Confidence extraction failed: {e}")
            return {'high_confidence': '', 'low_confidence': [], 'needs_review': True}
    
    def parse_with_fallbacks(self, image_path: str) -> List[Tuple[str, str]]:
        """
        Parse with multiple fallback strategies.
        """
        results = []
        
        # Try 1: High confidence OCR only
        confident_result = self.extract_with_confidence(image_path)
        if not confident_result['needs_review']:
            results.append(('high_confidence', confident_result['high_confidence']))
        
        # Try 2: Multiple OCR engines
        multi_results = self.multi_engine_ocr(image_path)
        for engine, text in multi_results.items():
            if text.strip():
                results.append((engine, text))
        
        # Try 3: Manual intervention flag
        if not results:
            results.append(('manual_review_needed', f"OCR failed for {image_path}"))
        
        return results
    
    def validate_against_expected_patterns(self, extracted_data: str) -> Dict[str, Any]:
        """
        Strategy 6: Pattern-Based Validation
        Validate extracted data against expected quote patterns.
        """
        validations = {
            'has_quantities': bool(re.search(r'\b\d+\b', extracted_data)),  # Has numbers
            'has_prices': bool(re.search(r'\$\d+', extracted_data)),        # Has currency
            'has_totals': bool(re.search(r'total|amount', extracted_data, re.I)),  # Has total keywords
            'reasonable_structure': len(extracted_data.split('\n')) > 3,    # Multi-line structure
        }
        
        confidence_score = sum(validations.values()) / len(validations)
        
        return {
            'validations': validations,
            'confidence': confidence_score,
            'needs_manual_review': confidence_score < 0.7
        }
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main method to extract text from PDF using robust OCR strategies.
        """
        logger.info(f"Starting robust OCR extraction from: {pdf_path}")
        
        try:
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
                
                all_results = []
                page_num = 1
                
                while True:
                    image_file = f"{image_path}-{page_num}.png"
                    if not os.path.exists(image_file):
                        break
                    
                    logger.info(f"Processing page {page_num}")
                    
                    # Apply all OCR strategies
                    page_results = self._process_single_page(image_file)
                    page_results['page_number'] = page_num
                    all_results.append(page_results)
                    
                    page_num += 1
                
                # Combine and validate results
                combined_text = self._combine_page_results(all_results)
                validation_result = self.validate_against_expected_patterns(combined_text)
                
                return {
                    'extracted_text': combined_text,
                    'page_results': all_results,
                    'validation': validation_result,
                    'needs_manual_review': validation_result['needs_manual_review']
                }
                
        except subprocess.CalledProcessError as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during robust OCR extraction: {e}")
            raise
    
    def _process_single_page(self, image_file: str) -> Dict[str, Any]:
        """Process a single page image with all OCR strategies."""
        results = {}
        
        # Strategy 1: Multi-engine OCR
        multi_engine_results = self.multi_engine_ocr(image_file)
        results['multi_engine'] = multi_engine_results
        
        # Strategy 2: Confidence-based extraction
        confidence_results = self.extract_with_confidence(image_file)
        results['confidence_based'] = confidence_results
        
        # Strategy 3: Optimized Tesseract
        tesseract_results = self.optimized_tesseract_extraction(image_file)
        results['optimized_tesseract'] = tesseract_results
        
        # Strategy 4: Fallback parsing
        fallback_results = self.parse_with_fallbacks(image_file)
        results['fallback_parsing'] = fallback_results
        
        # Strategy 5: Error correction
        if multi_engine_results:
            # Apply error correction to the best result
            best_text = max(multi_engine_results.values(), key=len)
            corrected_text = self.correct_common_ocr_errors(best_text)
            results['error_corrected'] = corrected_text
        
        return results
    
    def _combine_page_results(self, page_results: List[Dict[str, Any]]) -> str:
        """Combine results from multiple pages."""
        combined_text = ""
        
        for page_result in page_results:
            page_num = page_result.get('page_number', 0)
            
            # Try to get the best text from various strategies
            best_text = ""
            
            # Priority 1: Error corrected text
            if 'error_corrected' in page_result:
                best_text = page_result['error_corrected']
            # Priority 2: High confidence text
            elif 'confidence_based' in page_result and not page_result['confidence_based']['needs_review']:
                best_text = page_result['confidence_based']['high_confidence']
            # Priority 3: Best multi-engine result
            elif 'multi_engine' in page_result and page_result['multi_engine']:
                best_text = max(page_result['multi_engine'].values(), key=len)
            # Priority 4: Any available text
            else:
                for strategy, result in page_result.items():
                    if isinstance(result, str) and result.strip():
                        best_text = result
                        break
            
            if best_text.strip():
                combined_text += f"\n=== PAGE {page_num} ===\n{best_text}\n"
        
        return combined_text.strip()


# Convenience function for backward compatibility
def extract_text_with_robust_ocr(pdf_path: str) -> str:
    """
    Extract text from PDF using robust OCR strategies.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text string
    """
    engine = RobustOCREngine()
    result = engine.extract_text_from_pdf(pdf_path)
    return result['extracted_text'] 
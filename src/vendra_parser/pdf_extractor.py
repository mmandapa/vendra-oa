#!/usr/bin/env python3
"""
Enhanced PDF text extraction with better handling of custom fonts and encoding.
"""

import pdfplumber
import re
import logging
from typing import List, Dict, Any, Optional
import subprocess
import tempfile
import os

logger = logging.getLogger(__name__)


class EnhancedPDFExtractor:
    """Enhanced PDF extractor with multiple extraction strategies."""
    
    def __init__(self):
        self.extraction_methods = [
            self._extract_with_pdfplumber,
            self._extract_with_pdftotext,
            self._extract_with_pdf2txt
        ]
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract text from PDF using multiple methods.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text string
        """
        for method in self.extraction_methods:
            try:
                text = method(pdf_path)
                if text and len(text.strip()) > 100:  # Ensure we got meaningful text
                    logger.info(f"Successfully extracted {len(text)} characters using {method.__name__}")
                    return text
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        # If all methods fail, return empty string
        logger.error("All extraction methods failed")
        return ""
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> str:
        """Extract text using pdfplumber with enhanced settings."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for i, page in enumerate(pdf.pages):
                    # Try different extraction strategies
                    page_text = page.extract_text()
                    if not page_text:
                        # Try extracting with different settings
                        page_text = page.extract_text(
                            layout=True,
                            x_tolerance=3,
                            y_tolerance=3
                        )
                    
                    if page_text:
                        text += f"\n=== PAGE {i+1} ===\n{page_text}\n"
                
                return text
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            raise
    
    def _extract_with_pdftotext(self, pdf_path: str) -> str:
        """Extract text using pdftotext command-line tool."""
        try:
            # Check if pdftotext is available
            result = subprocess.run(['which', 'pdftotext'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("pdftotext not available")
                return ""
            
            # Extract text using pdftotext
            result = subprocess.run([
                'pdftotext', 
                '-layout',  # Preserve layout
                '-raw',     # Raw text
                pdf_path, 
                '-'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"pdftotext failed: {result.stderr}")
                return ""
                
        except Exception as e:
            logger.warning(f"pdftotext extraction failed: {e}")
            return ""
    
    def _extract_with_pdf2txt(self, pdf_path: str) -> str:
        """Extract text using pdf2txt command-line tool."""
        try:
            # Check if pdf2txt is available
            result = subprocess.run(['which', 'pdf2txt'], capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning("pdf2txt not available")
                return ""
            
            # Extract text using pdf2txt
            result = subprocess.run([
                'pdf2txt', 
                '-o', '-',  # Output to stdout
                pdf_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"pdf2txt failed: {result.stderr}")
                return ""
                
        except Exception as e:
            logger.warning(f"pdf2txt extraction failed: {e}")
            return ""
    
    def clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing encoding artifacts and normalizing.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove CID encoding artifacts
        text = re.sub(r'\(cid:\d+\)', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page markers
        text = re.sub(r'=== PAGE \d+ ===', '', text)
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove empty lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        return text
    
    def extract_tables(self, pdf_path: str) -> List[List[List[str]]]:
        """
        Extract tables from PDF.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of tables (each table is a list of rows)
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                all_tables = []
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)
                return all_tables
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return []
    
    def extract_with_ocr_fallback(self, pdf_path: str) -> str:
        """
        Extract text with OCR fallback for image-based PDFs.
        This is a placeholder for future OCR implementation.
        """
        # TODO: Implement OCR fallback using tools like Tesseract
        logger.info("OCR fallback not yet implemented")
        return ""


def extract_pdf_text(pdf_path: str) -> str:
    """
    Convenience function to extract text from PDF.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted and cleaned text
    """
    extractor = EnhancedPDFExtractor()
    raw_text = extractor.extract_text(pdf_path)
    cleaned_text = extractor.clean_text(raw_text)
    
    logger.info(f"Extracted {len(cleaned_text)} characters from PDF")
    return cleaned_text


def extract_pdf_tables(pdf_path: str) -> List[List[List[str]]]:
    """
    Convenience function to extract tables from PDF.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of tables
    """
    extractor = EnhancedPDFExtractor()
    tables = extractor.extract_tables(pdf_path)
    
    logger.info(f"Extracted {len(tables)} tables from PDF")
    return tables 
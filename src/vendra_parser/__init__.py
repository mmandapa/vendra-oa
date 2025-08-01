"""
Vendra Quote Parser Package

A robust OCR-based parser for extracting structured quote data from supplier PDFs.
"""

__version__ = "1.0.0"
__author__ = "Vendra Intern Coding Challenge"
__description__ = "OCR-based quote parser for extracting structured data from supplier PDFs"

# Import main classes for OCR parsing
from .ocr_parser import OCRParser, DynamicOCRParser
from .domain_parser import DomainAwareParser, ManufacturingAbbreviationHandler
from .models import LineItem, QuoteGroup

# Public API - OCR parsing only
__all__ = [
    "OCRParser",
    "DynamicOCRParser",
    "DomainAwareParser",
    "ManufacturingAbbreviationHandler",
    "LineItem",
    "QuoteGroup"
] 
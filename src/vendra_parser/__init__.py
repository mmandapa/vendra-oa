"""
Vendra Quote Parser Package

A robust Python-based parser for extracting structured quote data from supplier PDFs.
"""

__version__ = "1.0.0"
__author__ = "Vendra Intern Coding Challenge"
__description__ = "Quote parser for extracting structured data from supplier PDFs"

from .parser import QuoteParser
from .advanced_parser import AdvancedQuoteParser
from .ocr_parser import OCRParser
from .models import LineItem, QuoteGroup

__all__ = [
    "QuoteParser",
    "AdvancedQuoteParser", 
    "OCRParser",
    "LineItem",
    "QuoteGroup"
] 
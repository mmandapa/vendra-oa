"""
Vendra Quote Parser

A robust Python-based parser for extracting structured quote data from supplier PDFs.
"""

__version__ = "1.0.0"
__author__ = "Vendra Intern Coding Challenge"
__email__ = "mmandapa@ucsc.edu"

from .comprehensive_parser import ComprehensivePDFParser
from .multi_format_parser import MultiFormatPDFParser
from .ocr_parser import OCRParser, DynamicOCRParser
from .invoice2data_parser import Invoice2DataParser

__all__ = [
    "ComprehensivePDFParser",
    "MultiFormatPDFParser", 
    "OCRParser",
    "DynamicOCRParser",
    "Invoice2DataParser",
] 
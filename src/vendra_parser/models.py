"""
Data models for the Vendra Quote Parser.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class LineItem:
    """Represents a single line item in a quote."""
    description: str
    quantity: str
    unit_price: str
    cost: str


@dataclass
class QuoteGroup:
    """Represents a group of quotes for a specific quantity."""
    quantity: str
    unit_price: str
    total_price: str
    line_items: List[LineItem] 
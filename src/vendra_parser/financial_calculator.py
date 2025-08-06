#!/usr/bin/env python3
"""
Financial Calculator for Quote Processing
Handles tax calculations, discounts, and other financial adjustments using the prices library.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

try:
    from prices import Money, TaxedMoney, flat_tax
except ImportError:
    logger.warning("prices library not available - financial calculations will be limited")
    Money = None
    TaxedMoney = None
    flat_tax = None

class FinancialCalculator:
    """
    Handles financial calculations for quotes including tax, discounts, and adjustments.
    """
    
    def __init__(self, currency_code: str = 'USD'):
        self.currency_code = currency_code
        self.currency_symbol = self._get_currency_symbol(currency_code)
        
    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol from currency code."""
        symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CAD': 'C$',
            'AUD': 'A$',
            'CHF': 'CHF',
            'SEK': 'kr',
            'NOK': 'kr',
            'DKK': 'kr',
        }
        return symbols.get(currency_code, currency_code)
    
    def calculate_financial_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive financial summary with tax, discounts, and adjustments.
        """
        if not result or 'groups' not in result:
            return result
            
        try:
            # Extract basic totals
            subtotal = self._extract_monetary_value(result.get('summary', {}).get('totalCost', '0'))
            
            # Detect and calculate adjustments from the document
            adjustments = self._detect_adjustments(result)
            
            # Calculate tax if applicable
            tax_info = self._calculate_tax(subtotal, adjustments)
            
            # Calculate final totals
            final_calculations = self._calculate_final_totals(subtotal, adjustments, tax_info)
            
            # Update the result with financial calculations
            result = self._update_result_with_financials(result, adjustments, tax_info, final_calculations)
            
            logger.info(f"Financial calculations completed: subtotal={subtotal}, final={final_calculations['final_total']}")
            
        except Exception as e:
            logger.error(f"Error in financial calculations: {e}")
            
        return result
    
    def _extract_monetary_value(self, value_str: str) -> Decimal:
        """Extract decimal value from currency string."""
        if not value_str:
            return Decimal('0')
            
        # Remove currency symbols and clean the string
        clean_str = re.sub(r'[^\d.,\-]', '', str(value_str))
        clean_str = clean_str.replace(',', '')
        
        try:
            return Decimal(clean_str)
        except:
            return Decimal('0')
    
    def _detect_adjustments(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect common adjustments like shipping, handling, discounts from line items.
        """
        adjustments = []
        groups = result.get('groups', [])
        
        for group in groups:
            line_items = group.get('lineItems', [])
            for item in line_items:
                description = item.get('description', '').lower()
                cost = self._extract_monetary_value(item.get('cost', '0'))
                
                # Detect different types of adjustments
                adjustment_type = self._classify_adjustment(description)
                if adjustment_type:
                    adjustments.append({
                        'type': adjustment_type,
                        'description': item.get('description', ''),
                        'amount': cost,
                        'formatted_amount': self._format_currency(cost)
                    })
                    logger.debug(f"Detected {adjustment_type}: {item.get('description')} = {cost}")
        
        return adjustments
    
    def _classify_adjustment(self, description: str) -> Optional[str]:
        """Classify line item as an adjustment type."""
        description = description.lower()
        
        # More precise shipping and handling detection
        # Only classify as shipping if it's clearly a shipping service, not a product
        shipping_keywords = ['shipping', 'delivery', 'handling']
        freight_keywords = ['freight shipping', 'freight cost', 'freight charge']
        
        # Check for exact shipping terms first
        if any(keyword in description for keyword in freight_keywords):
            return 'shipping'
        
        # Check for shipping keywords but exclude product descriptions
        if any(keyword in description for keyword in shipping_keywords):
            # Exclude if it looks like a product (contains model numbers, part numbers, etc.)
            if not any(exclude in description for exclude in ['model', 'part', 'service-', 'product', 'item']):
                return 'shipping'
            
        # Discounts (negative adjustments)
        if any(keyword in description for keyword in ['discount', 'rebate', 'credit', 'reduction']):
            return 'discount'
            
        # Tax (if explicitly mentioned)
        if any(keyword in description for keyword in ['tax', 'vat', 'gst', 'sales tax']):
            return 'tax'
            
        # Insurance
        if any(keyword in description for keyword in ['insurance', 'coverage']):
            return 'insurance'
            
        # Setup or installation fees
        if any(keyword in description for keyword in ['setup', 'installation', 'config']):
            return 'setup_fee'
            
        # Service charges
        if any(keyword in description for keyword in ['service charge', 'processing fee', 'admin fee']):
            return 'service_charge'
            
        return None
        
    def _calculate_tax(self, subtotal: Decimal, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate tax information based on subtotal and adjustments.
        """
        tax_info = {
            'tax_rate': Decimal('0'),
            'tax_amount': Decimal('0'),
            'tax_inclusive': False,
            'calculation_method': 'none'
        }
        
        # Check if tax is explicitly mentioned in adjustments
        tax_adjustments = [adj for adj in adjustments if adj['type'] == 'tax']
        if tax_adjustments:
            total_tax = sum(adj['amount'] for adj in tax_adjustments)
            tax_info.update({
                'tax_amount': total_tax,
                'tax_rate': (total_tax / subtotal * 100) if subtotal > 0 else Decimal('0'),
                'calculation_method': 'explicit'
            })
            logger.debug(f"Explicit tax found: {total_tax} ({tax_info['tax_rate']:.2f}%)")
            
        # If no explicit tax, try to detect common tax patterns
        elif subtotal > 0:
            # Common tax rates to check
            common_rates = [Decimal('0.05'), Decimal('0.08'), Decimal('0.10'), Decimal('0.15'), 
                          Decimal('0.20'), Decimal('0.25')]  # 5%, 8%, 10%, 15%, 20%, 25%
            
            # This is a placeholder - in a real implementation, you might:
            # 1. Check the customer's location for applicable tax rates
            # 2. Look for tax hints in the document text
            # 3. Use business rules based on product types
            
            logger.debug("No explicit tax found - using business rules if applicable")
        
        return tax_info
    
    def _calculate_final_totals(self, subtotal: Decimal, adjustments: List[Dict[str, Any]], 
                              tax_info: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate final totals including all adjustments and tax."""
        
        # Calculate adjustment totals by type
        shipping_total = sum(adj['amount'] for adj in adjustments if adj['type'] == 'shipping')
        discount_total = sum(adj['amount'] for adj in adjustments if adj['type'] == 'discount')
        other_adjustments = sum(adj['amount'] for adj in adjustments 
                              if adj['type'] not in ['shipping', 'discount', 'tax'])
        
        # Calculate pre-tax total
        pre_tax_total = subtotal + shipping_total - discount_total + other_adjustments
        
        # Add tax
        tax_amount = tax_info.get('tax_amount', Decimal('0'))
        final_total = pre_tax_total + tax_amount
        
        return {
            'subtotal': subtotal,
            'shipping_total': shipping_total,
            'discount_total': discount_total,
            'other_adjustments': other_adjustments,
            'pre_tax_total': pre_tax_total,
            'tax_amount': tax_amount,
            'final_total': final_total
        }
    
    def _update_result_with_financials(self, result: Dict[str, Any], adjustments: List[Dict[str, Any]], 
                                     tax_info: Dict[str, Any], calculations: Dict[str, Any]) -> Dict[str, Any]:
        """Update the result with comprehensive financial information."""
        
        summary = result.get('summary', {})
        
        # Update adjustments array (convert Decimal to string for JSON serialization)
        json_safe_adjustments = []
        for adj in adjustments:
            json_safe_adj = adj.copy()
            json_safe_adj['amount'] = str(adj['amount'])  # Convert Decimal to string
            json_safe_adjustments.append(json_safe_adj)
        summary['adjustments'] = json_safe_adjustments
        
        # Add detailed financial breakdown
        summary['financialBreakdown'] = {
            'subtotal': self._format_currency(calculations['subtotal']),
            'shipping': self._format_currency(calculations['shipping_total']),
            'discounts': self._format_currency(calculations['discount_total']),
            'otherAdjustments': self._format_currency(calculations['other_adjustments']),
            'preTaxTotal': self._format_currency(calculations['pre_tax_total']),
            'taxRate': f"{tax_info.get('tax_rate', 0):.2f}%",
            'taxAmount': self._format_currency(calculations['tax_amount']),
            'finalTotal': self._format_currency(calculations['final_total'])
        }
        
        # Update calculation steps
        steps = []
        if calculations['subtotal'] > 0:
            steps.append(f"Subtotal: {self._format_currency(calculations['subtotal'])}")
            
        if calculations['shipping_total'] > 0:
            steps.append(f"+ Shipping: {self._format_currency(calculations['shipping_total'])}")
            
        if calculations['discount_total'] > 0:
            steps.append(f"- Discounts: {self._format_currency(calculations['discount_total'])}")
            
        if calculations['other_adjustments'] > 0:
            steps.append(f"+ Other: {self._format_currency(calculations['other_adjustments'])}")
            
        if calculations['tax_amount'] > 0:
            steps.append(f"+ Tax ({tax_info.get('tax_rate', 0):.1f}%): {self._format_currency(calculations['tax_amount'])}")
            
        steps.append(f"= Final Total: {self._format_currency(calculations['final_total'])}")
        
        summary['calculationSteps'] = steps
        
        # Update final total in summary
        summary['finalTotal'] = self._format_currency(calculations['final_total'])
        
        # Add tax information if applicable
        if calculations['tax_amount'] > 0:
            summary['taxInfo'] = {
                'rate': f"{tax_info.get('tax_rate', 0):.2f}%",
                'amount': self._format_currency(calculations['tax_amount']),
                'method': tax_info.get('calculation_method', 'none')
            }
        
        result['summary'] = summary
        return result
    
    def _format_currency(self, amount: Decimal) -> str:
        """Format decimal amount as currency string."""
        if amount == 0:
            return f"{self.currency_symbol}0.00"
            
        # Round to 2 decimal places
        rounded_amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Format with commas for thousands
        formatted = f"{rounded_amount:,.2f}"
        
        # Add currency symbol
        if self.currency_code in ['EUR']:
            return f"{formatted} {self.currency_symbol}"
        else:
            return f"{self.currency_symbol}{formatted}"

def calculate_quote_financials(result: Dict[str, Any], currency_code: str = 'USD') -> Dict[str, Any]:
    """
    Convenience function to calculate financial summary for a quote result.
    """
    calculator = FinancialCalculator(currency_code)
    return calculator.calculate_financial_summary(result)
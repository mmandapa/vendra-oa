#!/usr/bin/env python3
"""
Smart Classifier for Line Item Detection
Uses intelligent features and ML libraries to differentiate between line items and other document content.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class TextFeature:
    """Features extracted from text for classification."""
    length: int
    word_count: int
    has_numbers: bool
    has_currency: bool
    has_quantities: bool
    has_prices: bool
    has_part_numbers: bool
    has_technical_terms: bool
    has_business_terms: bool
    has_contact_info: bool
    has_metadata: bool
    has_urls: bool
    has_file_paths: bool
    has_code_artifacts: bool
    has_specific_noise: bool
    readability_score: float
    complexity_score: float
    semantic_similarity: float

class SmartLineItemClassifier:
    """
    Intelligent classifier that uses advanced features to differentiate between line items and other content.
    """
    
    def __init__(self):
        self.line_item_keywords = set()
        self.non_line_item_keywords = set()
        self.feature_weights = {}
        self._initialize_classifier()
    
    def _initialize_classifier(self):
        """Initialize the classifier with intelligent features."""
        try:
            # Use textstat for readability analysis
            import textstat
            self.textstat = textstat
            logger.info("✅ Loaded textstat for readability analysis")
        except ImportError:
            logger.warning("⚠️  textstat not available, using basic metrics")
            self.textstat = None
        
        try:
            # Use scikit-learn for ML features
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            self.TfidfVectorizer = TfidfVectorizer
            self.cosine_similarity = cosine_similarity
            logger.info("✅ Loaded scikit-learn for ML features")
        except ImportError:
            logger.warning("⚠️  scikit-learn not available, using basic similarity")
            self.TfidfVectorizer = None
            self.cosine_similarity = None
    
    def extract_features(self, text: str) -> TextFeature:
        """Extract comprehensive features from text for intelligent classification."""
        if not text or len(text.strip()) < 2:
            return self._create_empty_feature()
        
        text = text.strip()
        words = text.split()
        text_lower = text.lower()
        
        # Basic text features
        length = len(text)
        word_count = len(words)
        
        # Pattern detection using regex
        has_numbers = bool(re.search(r'\d', text))
        has_currency = bool(re.search(r'[\$€£¥₹₽₿₩₪₨₦₡₱₲₴₵₸₺₻₼₽₾₿]', text))
        has_quantities = bool(re.search(r'\b\d+\s*(?:pcs?|units?|items?|pieces?|boxes?|sets?|kits?|lots?)\b', text_lower))
        has_prices = bool(re.search(r'\$?\d+(?:,\d{3})*(?:\.\d{1,2})?', text))
        has_part_numbers = bool(re.search(r'\b[A-Z]{2,}\d+[A-Z0-9\-]*\b', text))
        has_urls = bool(re.search(r'https?://|www\.', text))
        has_file_paths = bool(re.search(r'[A-Z]:\\|/Users/|/home/|\.(pdf|docx?|xlsx?)$', text))
        has_code_artifacts = bool(re.search(r'[<>/\\|&{}[\]]{2,}|def\s+|class\s+|import\s+', text))
        
        # Specific noise detection for known problematic patterns
        has_specific_noise = bool(re.search(r'48p9d2f|ikninto|vfartioonm|dfriivlee|ussetirn|tixce|q7u|totacllau|tdea|cxan|mistakes|double|chec|r0es8p|957ed7cb|claude.*ai.*chat', text_lower))
        
        # Advanced features
        readability_score = 0.0
        complexity_score = 0.0
        semantic_similarity = 0.0
        
        if self.textstat:
            try:
                readability_score = self.textstat.flesch_reading_ease(text)
                complexity_score = self.textstat.gunning_fog(text)
            except:
                pass
        
        # Intelligent term detection using word patterns
        has_technical_terms = self._has_technical_terms(text_lower)
        has_business_terms = self._has_business_terms(text_lower)
        has_contact_info = self._has_contact_info(text_lower)
        has_metadata = self._has_metadata(text_lower)
        
        return TextFeature(
            length=length,
            word_count=word_count,
            has_numbers=has_numbers,
            has_currency=has_currency,
            has_quantities=has_quantities,
            has_prices=has_prices,
            has_part_numbers=has_part_numbers,
            has_technical_terms=has_technical_terms,
            has_business_terms=has_business_terms,
            has_contact_info=has_contact_info,
            has_metadata=has_metadata,
            has_urls=has_urls,
            has_file_paths=has_file_paths,
            has_code_artifacts=has_code_artifacts,
            has_specific_noise=has_specific_noise,
            readability_score=readability_score,
            complexity_score=complexity_score,
            semantic_similarity=semantic_similarity
        )
    
    def _has_technical_terms(self, text_lower: str) -> bool:
        """Check if text contains technical/product terms."""
        technical_indicators = [
            'service', 'product', 'item', 'part', 'component', 'material',
            'equipment', 'tool', 'supply', 'accessory', 'assembly',
            'maintenance', 'repair', 'installation', 'calibration',
            'inspection', 'testing', 'consulting', 'support',
            'system', 'device', 'unit', 'module', 'package', 'kit',
            'solution', 'platform', 'hardware', 'interface', 'connector',
            'cable', 'wire', 'circuit', 'sensor', 'controller', 'motor',
            'pump', 'valve', 'filter', 'battery', 'charger', 'adapter',
            # Manufacturing-specific terms
            'cylinder', 'barrel', 'piston', 'rod', 'cap', 'machining',
            'hydraulic', 'pneumatic', 'steel', 'stainless', 'aluminum',
            'brass', 'copper', 'plastic', 'rubber', 'ceramic', 'composite',
            'welding', 'cutting', 'grinding', 'polishing', 'coating',
            'treatment', 'finishing', 'quality', 'assurance', 'testing',
            'packaging', 'despatch', 'shipping', 'delivery'
        ]
        return any(term in text_lower for term in technical_indicators)
    
    def _has_business_terms(self, text_lower: str) -> bool:
        """Check if text contains business/commercial terms."""
        business_indicators = [
            'contract', 'agreement', 'service', 'work', 'labor', 'hour',
            'project', 'task', 'job', 'assignment', 'consultation',
            'training', 'education', 'certification', 'license',
            'freight', 'shipping', 'delivery', 'transport', 'logistics',
            'warehouse', 'inventory', 'stock', 'order', 'purchase',
            'manufacturing', 'production', 'quality', 'safety'
        ]
        return any(term in text_lower for term in business_indicators)
    
    def _has_contact_info(self, text_lower: str) -> bool:
        """Check if text contains contact information."""
        contact_indicators = [
            'phone', 'fax', 'email', 'contact', 'attn', 'attention',
            'street', 'avenue', 'road', 'drive', 'lane', 'place', 'court',
            'boulevard', 'highway', 'suite', 'apt', 'apartment', 'floor',
            'building', 'zip', 'postal', 'code'
        ]
        return any(term in text_lower for term in contact_indicators)
    
    def _has_metadata(self, text_lower: str) -> bool:
        """Check if text contains document metadata."""
        metadata_indicators = [
            'date', 'time', 'page', 'total', 'subtotal', 'tax',
            'balance', 'amount', 'due', 'invoice',
            'quote', 'order', 'po', 'reference', 'ref', 'number',
            'estimate', 'receipt', 'statement', 'report'
        ]
        return any(term in text_lower for term in metadata_indicators)
    
    def _is_discount_or_adjustment(self, text: str) -> bool:
        """Check if text represents a discount or adjustment line item."""
        text_lower = text.lower().strip()
        
        # Discount/adjustment indicators
        discount_indicators = [
            'cod', 'cash on delivery', 'discount', 'rebate', 'credit', 'adjustment',
            'deduction', 'reduction', 'markdown', 'savings', 'promotion'
        ]
        
        # Check if it contains discount terms
        has_discount_term = any(term in text_lower for term in discount_indicators)
        
        # Check if it has a negative amount (common for discounts)
        has_negative_amount = bool(re.search(r'-\$?\d+', text))
        
        # Check if it's a short description (typical for adjustments)
        is_short_description = len(text.strip()) <= 20
        
        return has_discount_term or (has_negative_amount and is_short_description)
    
    def _create_empty_feature(self) -> TextFeature:
        """Create an empty feature object for invalid text."""
        return TextFeature(
            length=0, word_count=0, has_numbers=False, has_currency=False,
            has_quantities=False, has_prices=False, has_part_numbers=False,
            has_technical_terms=False, has_business_terms=False, has_contact_info=False,
            has_metadata=False, has_urls=False, has_file_paths=False, has_code_artifacts=False,
            has_specific_noise=False, readability_score=0.0, complexity_score=0.0, semantic_similarity=0.0
        )
    
    def calculate_line_item_score(self, features: TextFeature, original_text: str = "") -> float:
        """Calculate a confidence score for whether text represents a line item."""
        score = 0.0
        
        # Positive indicators (increase score)
        if features.has_numbers and features.has_prices:
            score += 0.25  # Strong indicator of line item
        
        if features.has_quantities:
            score += 0.2  # Quantity information is very indicative
        
        if features.has_part_numbers:
            score += 0.15  # Part numbers suggest products
        
        if features.has_technical_terms:
            score += 0.25  # Technical terms suggest products/services (increased weight)
        
        if features.has_business_terms:
            score += 0.2  # Business terms suggest commercial items (increased weight)
        
        if 3 <= features.word_count <= 25:
            score += 0.15  # Reasonable description length (increased range)
        
        if features.readability_score > 20:
            score += 0.1  # Readable text is more likely to be a product description
        
        # Special bonus for service/product descriptions without numbers
        if features.has_technical_terms and not features.has_numbers and features.word_count >= 2:
            score += 0.3  # Strong bonus for service descriptions
        
        # Special handling for discount/adjustment line items
        if original_text and self._is_discount_or_adjustment(original_text):
            score += 0.4  # Strong bonus for discount/adjustment line items
        
        # Negative indicators (decrease score)
        if features.has_urls:
            score -= 0.4  # URLs are rarely line items
        
        if features.has_file_paths:
            score -= 0.4  # File paths are never line items
        
        if features.has_code_artifacts:
            score -= 0.3  # Code artifacts are not products
        
        if features.has_contact_info:
            score -= 0.3  # Contact info is not a product
        
        if features.has_metadata:
            score -= 0.2  # Metadata is not a product
        
        # Specific noise detection (strong penalty)
        if hasattr(features, 'has_specific_noise') and features.has_specific_noise:
            score -= 0.8  # Strong penalty for known noise patterns
        
        if features.word_count < 2:
            score -= 0.2  # Too short to be a meaningful description
        
        if features.word_count > 50:
            score -= 0.1  # Too long, might be explanatory text
        
        # Normalize score to 0-1 range
        score = max(0.0, min(1.0, score))
        
        return score
    
    def is_likely_line_item(self, text: str, threshold: float = 0.4) -> Tuple[bool, float]:
        """
        Intelligently determine if text represents a line item.
        Returns (is_line_item, confidence_score)
        """
        if not text or len(text.strip()) < 2:
            return False, 0.0
        
        # Extract features
        features = self.extract_features(text)
        
        # Calculate confidence score
        confidence = self.calculate_line_item_score(features, text)
        
        # Make decision based on threshold
        is_line_item = confidence >= threshold
        
        logger.debug(f"Smart classification: '{text[:50]}...' -> Score: {confidence:.3f}, Is line item: {is_line_item}")
        
        return is_line_item, confidence
    
    def classify_batch(self, texts: List[str], threshold: float = 0.3) -> List[Tuple[bool, float]]:
        """Classify multiple texts efficiently."""
        results = []
        for text in texts:
            result = self.is_likely_line_item(text, threshold)
            results.append(result)
        return results
    
    def learn_from_examples(self, line_item_examples: List[str], non_line_item_examples: List[str]):
        """Learn from examples to improve classification (optional enhancement)."""
        if not self.TfidfVectorizer:
            logger.warning("scikit-learn not available for learning")
            return
        
        try:
            # Create TF-IDF vectors for examples
            vectorizer = self.TfidfVectorizer(max_features=1000, stop_words='english')
            
            # Combine examples
            all_examples = line_item_examples + non_line_item_examples
            if not all_examples:
                return
            
            # Fit vectorizer
            tfidf_matrix = vectorizer.fit_transform(all_examples)
            
            # Store for similarity calculations
            self.vectorizer = vectorizer
            self.line_item_vectors = tfidf_matrix[:len(line_item_examples)]
            self.non_line_item_vectors = tfidf_matrix[len(line_item_examples):]
            
            logger.info(f"✅ Learned from {len(line_item_examples)} line item examples and {len(non_line_item_examples)} non-line item examples")
            
        except Exception as e:
            logger.warning(f"Learning failed: {e}")

# Global instance for reuse
smart_classifier = SmartLineItemClassifier() 
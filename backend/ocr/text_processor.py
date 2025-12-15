"""
Text processing and classification for OCR output.
"""

import re
from typing import Optional

from backend.shared.models import Annotation, BoundingBox, Dimension


class TextProcessor:
    """
    Processes and classifies OCR text output.
    
    Identifies:
    - Dimensions (measurements)
    - Part labels
    - Material specifications
    - Notes and instructions
    """
    
    # Patterns for dimension parsing
    DIMENSION_PATTERNS = [
        # Fractional inches: 1/8, 3/16, 1 1/2
        r"(\d+\s*)?([\d]+/[\d]+)\s*(in|inch|inches|\")?",
        # Decimal inches: 0.125, 1.5
        r"(\d+\.?\d*)\s*(in|inch|inches|\")",
        # Millimeters: 3mm, 3.5 mm
        r"(\d+\.?\d*)\s*(mm|millimeter|millimeters)",
        # Centimeters: 2cm, 2.5 cm
        r"(\d+\.?\d*)\s*(cm|centimeter|centimeters)",
    ]
    
    # Patterns for part labels
    PART_LABEL_PATTERNS = [
        r"^[A-Z]\d+$",  # F1, R3, W2
        r"^(RIB|FORMER|SPAR|BULK|BH)\s*\d+$",  # RIB 1, FORMER 3
        r"^[A-Z]{1,3}-\d+$",  # F-1, RIB-3
    ]
    
    # Material keywords
    MATERIAL_KEYWORDS = {
        "balsa": ["balsa", "bal"],
        "plywood": ["ply", "plywood", "birch"],
        "hardwood": ["hardwood", "spruce", "bass", "maple"],
        "carbon": ["carbon", "cf", "carbon fiber"],
        "fiberglass": ["fiberglass", "fg", "glass"],
        "foam": ["foam", "epp", "eps", "depron"],
    }
    
    def process_text(
        self,
        text: str,
        bounds: BoundingBox,
        confidence: float = 1.0,
    ) -> Annotation:
        """
        Process a single text item.
        
        Args:
            text: Raw text
            bounds: Bounding box
            confidence: OCR confidence
            
        Returns:
            Processed annotation
        """
        # Clean text
        cleaned = self._clean_text(text)
        
        # Classify text type
        annotation_type = self._classify_text(cleaned)
        
        # Parse dimension if applicable
        dimension_value = None
        dimension_unit = None
        
        if annotation_type == "dimension":
            parsed = self._parse_dimension(cleaned)
            if parsed:
                dimension_value = parsed.value
                dimension_unit = parsed.unit
        
        return Annotation(
            text=cleaned,
            bounds=bounds,
            confidence=confidence,
            annotation_type=annotation_type,
            dimension_value=dimension_value,
            dimension_unit=dimension_unit,
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean OCR text output."""
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Fix common OCR errors
        replacements = {
            "0": "O",  # Sometimes O is read as 0 in labels
            "l": "1",  # Sometimes 1 is read as l
            "I": "1",  # Sometimes 1 is read as I
        }
        
        # Only apply to likely numeric contexts
        # ... (simplified for now)
        
        return text.strip()
    
    def _classify_text(self, text: str) -> str:
        """Classify text type."""
        text_upper = text.upper()
        
        # Check for dimension patterns
        for pattern in self.DIMENSION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "dimension"
        
        # Check for part labels
        for pattern in self.PART_LABEL_PATTERNS:
            if re.match(pattern, text_upper):
                return "label"
        
        # Check for material keywords
        text_lower = text.lower()
        for material, keywords in self.MATERIAL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return "material_note"
        
        # Check for scale indicators
        if re.search(r"(scale|1:|full\s*size)", text, re.IGNORECASE):
            return "scale"
        
        # Default to text/note
        return "text"
    
    def _parse_dimension(self, text: str) -> Optional[Dimension]:
        """Parse dimension from text."""
        # Try fractional inches
        match = re.search(r"(\d+\s*)?([\d]+)/([\d]+)\s*(in|inch|inches|\")?", text, re.IGNORECASE)
        if match:
            whole = int(match.group(1).strip()) if match.group(1) else 0
            numerator = int(match.group(2))
            denominator = int(match.group(3))
            value = whole + (numerator / denominator)
            return Dimension(value=value, unit="in", text=text)
        
        # Try decimal with unit
        match = re.search(r"(\d+\.?\d*)\s*(mm|cm|in|inch|inches|\")", text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit_text = match.group(2).lower()
            
            unit_map = {
                "mm": "mm",
                "cm": "cm",
                "in": "in",
                "inch": "in",
                "inches": "in",
                '"': "in",
            }
            unit = unit_map.get(unit_text, "in")
            
            return Dimension(value=value, unit=unit, text=text)
        
        return None
    
    def extract_dimensions(self, text: str) -> list[Dimension]:
        """Extract all dimensions from text."""
        dimensions = []
        
        # Find all dimension patterns
        for pattern in self.DIMENSION_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                dim = self._parse_dimension(match.group(0))
                if dim:
                    dimensions.append(dim)
        
        return dimensions



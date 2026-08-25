import re
import unicodedata

class PlateService:
    # Translation table mapping Eastern Arabic-Indic digits to Western digits
    _DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

    def normalize(self, plate: str) -> str:
        """Strips whitespace, converts Eastern digits to Western, and collapses spaces.
        
        Does not raise on empty string.
        """
        if not plate:
            return ""
        # Strip leading/trailing whitespace
        s = plate.strip()
        # Translate Eastern Arabic-Indic digits
        s = s.translate(self._DIGIT_MAP)
        # Collapse multiple spaces to single space
        s = re.sub(r"\s+", " ", s)
        return s

    def validate(self, plate: str) -> bool:
        """Normalizes the plate and validates it against the Egyptian format.
        
        Egyptian format: 1-3 Arabic letters followed by 1-4 Western digits, space-separated.
        """
        normalized = self.normalize(plate)
        # Pattern: 1 to 3 Arabic letters, a single space, and 1 to 4 Western digits
        pattern = r"^[\u0600-\u06FF]{1,3} \d{1,4}$"
        return bool(re.match(pattern, normalized))

    def search_normalized(self, plate: str) -> str:
        """Normalizes the plate and strips all diacritics/combining marks.
        
        Used for DB search comparison only.
        """
        normalized = self.normalize(plate)
        # Decompose using NFKD normalization
        decomposed = unicodedata.normalize("NFKD", normalized)
        # Filter out combining marks (category 'Mn')
        stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
        return stripped

__all__ = ["PlateService"]

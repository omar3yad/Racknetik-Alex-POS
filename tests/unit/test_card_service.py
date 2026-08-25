import pytest
from services.card_service import CardService
from services.exceptions import InvalidBarcodeFormatError

def test_strips_whitespace():
    service = CardService(db=None)
    assert service.normalize_code("  CARD-001  ") == "CARD-001"

def test_uppercases():
    service = CardService(db=None)
    assert service.normalize_code("card-001") == "CARD-001"

def test_empty_raises():
    service = CardService(db=None)
    with pytest.raises(InvalidBarcodeFormatError):
        service.normalize_code("")

def test_invalid_chars_raises():
    service = CardService(db=None)
    with pytest.raises(InvalidBarcodeFormatError):
        service.normalize_code("CARD@001")

def test_arabic_raises():
    service = CardService(db=None)
    with pytest.raises(InvalidBarcodeFormatError):
        service.normalize_code("كرت-001")

def test_too_long_raises():
    service = CardService(db=None)
    with pytest.raises(InvalidBarcodeFormatError):
        service.normalize_code("A" * 51)

def test_valid_with_underscore():
    service = CardService(db=None)
    assert service.normalize_code("CARD_001") == "CARD_001"

def test_valid_with_dash():
    service = CardService(db=None)
    assert service.normalize_code("CARD-0042") == "CARD-0042"

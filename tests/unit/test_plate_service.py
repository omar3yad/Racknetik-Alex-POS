import unicodedata
from services.plate_service import PlateService

def test_strips_whitespace():
    plate = PlateService()
    assert plate.normalize("  أ ب ج 123  ") == "أ ب ج 123"

def test_eastern_to_western_numerals():
    plate = PlateService()
    assert plate.normalize("أ ب ج ١٢٣") == "أ ب ج 123"

def test_collapses_spaces():
    plate = PlateService()
    assert plate.normalize("أ  ب   ج 1") == "أ ب ج 1"

def test_empty_string():
    plate = PlateService()
    assert plate.normalize("") == ""

def test_mixed_numerals():
    plate = PlateService()
    assert plate.normalize("ن ي ش ١٥٩") == "ن ي ش 159"

def test_valid_plate():
    plate = PlateService()
    assert plate.validate("ن ي ش 159") is True

def test_one_letter():
    plate = PlateService()
    assert plate.validate("أ 1") is True

def test_three_letters_four_digits():
    plate = PlateService()
    assert plate.validate("أ ب ج 1234") is True

def test_no_space():
    plate = PlateService()
    assert plate.validate("أبج123") is False

def test_latin_letters():
    plate = PlateService()
    assert plate.validate("ABC 123") is False

def test_empty():
    plate = PlateService()
    assert plate.validate("") is False

def test_removes_diacritics():
    plate = PlateService()
    norm = plate.search_normalized("أَحْمَد")
    # Assert no character has unicode category Mn (Mark, Nonspacing) which corresponds to diacritics/tashkeel
    for char in norm:
        assert unicodedata.category(char) != "Mn"

def test_normalizes_first():
    plate = PlateService()
    assert plate.search_normalized("ن ي ش ١٥٩") == plate.search_normalized("ن ي ش 159")

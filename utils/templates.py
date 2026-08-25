import functools
import json
from config import get_settings

@functools.lru_cache
def load_translations(path: str = "translations/ar.json") -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def translate_filter(key: str, translations: dict) -> str:
    if key in translations:
        return translations[key]
    
    settings = get_settings()
    if settings.ENVIRONMENT == "development":
        return f"[[{key}]]"
    else:
        raise KeyError(f"Translation key '{key}' not found in production environment.")

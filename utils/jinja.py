from datetime import datetime, timedelta
from functools import partial
from fastapi.templating import Jinja2Templates
from config import Settings
from utils.templates import load_translations, translate_filter
from services.pricing_helpers import format_duration, format_egp

def format_egp_filter(piastres: int | None) -> str:
    """Format piastres to localized Arabic EGP separator, returning '—' if None."""
    if piastres is None:
        return "—"
    return format_egp(piastres)

def format_duration_filter(minutes: int | None) -> str:
    """Format minutes to localized Arabic duration description, returning '—' if None."""
    if minutes is None:
        return "—"
    return format_duration(minutes)

def format_datetime_filter(dt: datetime | None) -> str:
    """Format datetime converted to Cairo local time (UTC+2) to localized Arabic format."""
    if dt is None:
        return "—"
    # Cairo is UTC+2
    dt_local = dt + timedelta(hours=2)
    formatted = dt_local.strftime("%d/%m/%Y %H:%M")
    # Translate digits to Arabic-Indic
    trans = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    return formatted.translate(trans)

def create_jinja2_environment(settings: Settings) -> Jinja2Templates:
    templates = Jinja2Templates(directory="templates")
    translations = load_translations()
    t_func = partial(translate_filter, translations=translations)
    templates.env.globals["t"] = t_func

    # Register filters
    templates.env.filters["format_egp"] = format_egp_filter
    templates.env.filters["format_duration"] = format_duration_filter
    templates.env.filters["format_datetime"] = format_datetime_filter
    templates.env.filters["zfill"] = lambda s, w: str(s).zfill(w)

    # Register globals
    templates.env.globals["format_duration"] = format_duration
    templates.env.globals["format_egp"] = format_egp

    return templates

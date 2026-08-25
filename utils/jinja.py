from functools import partial
from fastapi.templating import Jinja2Templates
from config import Settings
from utils.templates import load_translations, translate_filter

def create_jinja2_environment(settings: Settings) -> Jinja2Templates:
    templates = Jinja2Templates(directory="templates")
    translations = load_translations()
    t_func = partial(translate_filter, translations=translations)
    templates.env.globals["t"] = t_func
    return templates

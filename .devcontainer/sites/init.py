# sites/__init__.py
from urllib.parse import urlparse
from typing import Callable, Dict, Tuple

from . import alonhadat, batdongsan

# domain -> (parser_func, default_strategy)
SITE_REGISTRY: Dict[str, Tuple[Callable, str]] = {
    "alonhadat.com.vn": (alonhadat.parse, alonhadat.DEFAULT_STRATEGY),
    "batdongsan.com.vn": (batdongsan.parse, batdongsan.DEFAULT_STRATEGY),
}

def pick_site(link: str):
    host = (urlparse(link).netloc or "").lower()
    for dom, value in SITE_REGISTRY.items():
        if dom in host:
            return value
    return None

# sites/__init__.py
from urllib.parse import urlparse
from typing import Callable, Tuple, Dict

# Import các parser theo site.
# YÊU CẦU: mỗi file sites/<site>.py phải có hàm parse(link: str, html_text: str) -> dict
# và (không bắt buộc) hằng DEFAULT_STRATEGY = "requests" | "cloudscraper" | "playwright"
from . import alonhadat
from . import batdongsan
from . import nhatot
from . import muaban

# i-batdongsan: file phải đặt tên i_batdongsan.py (KHÔNG dùng dấu '-')
try:
    from . import i_batdongsan as _i_batdongsan
except Exception:
    _i_batdongsan = None  # chưa có file hoặc lỗi import -> bỏ qua domain này

SITE_REGISTRY: Dict[str, Tuple[Callable, str]] = {
    "alonhadat.com.vn": (
        getattr(alonhadat, "parse"),
        getattr(alonhadat, "DEFAULT_STRATEGY", "requests"),
    ),
    "batdongsan.com.vn": (
        getattr(batdongsan, "parse"),
        getattr(batdongsan, "DEFAULT_STRATEGY", "playwright"),
    ),
    "nhatot.com": (
        getattr(nhatot, "parse"),
        getattr(nhatot, "DEFAULT_STRATEGY", "playwright"),
    ),
    "muaban.net": (
        getattr(muaban, "parse"),
        getattr(muaban, "DEFAULT_STRATEGY", "playwright"),
    ),
}

# Chỉ đăng ký i-batdongsan nếu import thành công
if _i_batdongsan:
    SITE_REGISTRY["i-batdongsan.com"] = (
        getattr(_i_batdongsan, "parse"),
        getattr(_i_batdongsan, "DEFAULT_STRATEGY", "requests"),
    )

def pick_site(link: str):
    """
    Trả về tuple (parser_func, default_strategy) theo domain của link,
    hoặc None nếu domain chưa hỗ trợ.
    """
    host = (urlparse(link).netloc or "").lower()
    for dom, val in SITE_REGISTRY.items():
        if dom in host:
            return val
    return None

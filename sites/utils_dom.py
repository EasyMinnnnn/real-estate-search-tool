# sites/utils_dom.py
from __future__ import annotations
import re
from typing import List, Optional
from bs4 import BeautifulSoup, Tag

_LEADING_COMBINATORS = re.compile(r"^\s*([>+~,]+)\s*")

def _sanitize_selector(sel: str) -> str:
    # Bỏ các combinator đứng đầu như ">", "+", "~", "," nếu lỡ viết sai
    s = sel.strip()
    s = _LEADING_COMBINATORS.sub("", s)
    # Bỏ dấu combinator thừa khi bắt đầu bằng ">" sau dấu phẩy
    s = re.sub(r",\s*[>+~]\s*", ", ", s)
    return s

def sel(root: BeautifulSoup | Tag, selector: str):
    try:
        return root.select(_sanitize_selector(selector))
    except Exception:
        return []  # an toàn

def sel1(root: BeautifulSoup | Tag, selector: str) -> Optional[Tag]:
    try:
        return root.select_one(_sanitize_selector(selector))
    except Exception:
        return None

def text_or_empty(node: Tag, strip: bool = True) -> str:
    if not node:
        return ""
    return node.get_text(strip=strip)

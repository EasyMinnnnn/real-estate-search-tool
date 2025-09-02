# tests/test_one_url.py
import os, json, sys
from fetchers import get_html
from sites import pick_site

"""
Usage:
  python tests/test_one_url.py <URL> [strategy]
strategy: requests | cloudscraper | playwright (override default of site)
"""

def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/test_one_url.py <URL> [strategy]"); sys.exit(1)
    url = sys.argv[1].strip()
    strategy = sys.argv[2].strip() if len(sys.argv) > 2 else None

    picked = pick_site(url)
    if not picked:
        print("❌ Chưa hỗ trợ domain này"); sys.exit(1)
    parser, default_strategy = picked
    strategy = strategy or default_strategy

    html = get_html(url, strategy)
    data = parser(url, html)
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    # gợi ý env:
    # export PLAYWRIGHT_HEADLESS=1
    # pip install -r requirements.txt && playwright install chromium
    main()

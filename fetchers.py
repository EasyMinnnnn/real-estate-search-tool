# fetchers.py
from __future__ import annotations
import os, time
import requests

REQ_HEADERS = {
    "User-Agent": os.getenv("UA", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36"),
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer": "https://www.google.com/",
}

def fetch_requests(url: str, timeout: int = 25) -> str:
    r = requests.get(url, headers=REQ_HEADERS, timeout=timeout)
    if r.status_code in (403, 410, 451):
        raise requests.HTTPError(f"Blocked: {r.status_code}")
    r.raise_for_status()
    return r.text

def fetch_cloudscraper(url: str, timeout: int = 25) -> str:
    # pip install cloudscraper
    import cloudscraper
    s = cloudscraper.create_scraper()
    r = s.get(url, timeout=timeout)
    if r.status_code >= 400:
        raise requests.HTTPError(f"HTTP {r.status_code}")
    return r.text

def fetch_playwright(url: str, timeout_ms: int = 60000, headless: bool = True) -> str:
    # pip install playwright && playwright install chromium
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(user_agent=REQ_HEADERS["User-Agent"],
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            html = page.content()
            return html
        finally:
            ctx.close(); browser.close()

# strategy = "requests" | "cloudscraper" | "playwright"
def get_html(url: str, strategy: str) -> str:
    if strategy == "playwright":
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "1") == "1"
        return fetch_playwright(url, headless=headless)
    if strategy == "cloudscraper":
        return fetch_cloudscraper(url)
    return fetch_requests(url)

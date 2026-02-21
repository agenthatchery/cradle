"""
Headless Browser Tool for Cradle
=================================
Uses Playwright to render dynamic (JavaScript-heavy) pages.
Falls back to simple urllib if Playwright is not installed.

Install: pip install playwright && playwright install chromium
"""

import logging
import urllib.request

logger = logging.getLogger(__name__)

# Try to import Playwright, fall back gracefully
_HAS_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright
    _HAS_PLAYWRIGHT = True
except ImportError:
    logger.info("Playwright not installed. headless_browse will use simple HTTP fallback.")


def headless_browse(url: str, wait_seconds: int = 3) -> str:
    """
    Open a URL in a headless browser (Playwright/Chromium) and return the rendered text.
    This handles JavaScript-heavy sites (SPAs, dynamic content, auth walls).
    Falls back to simple HTTP if Playwright is not installed.

    Args:
        url: The webpage URL to render
        wait_seconds: How long to wait for JS to render (default 3s)
    Returns:
        The visible text content of the rendered page (max 8000 chars).
    """
    if _HAS_PLAYWRIGHT:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-gpu'])
                page = browser.new_page()
                page.set_default_timeout(30000)
                page.goto(url, wait_until='networkidle', timeout=30000)
                if wait_seconds > 0:
                    page.wait_for_timeout(wait_seconds * 1000)
                text = page.inner_text('body')
                browser.close()
                result = text[:8000] if text else "Page rendered but no text found."
                logger.info(f"[Playwright] Rendered {url}: {len(result)} chars")
                return result
        except Exception as e:
            logger.warning(f"Playwright failed: {e}. Falling back to HTTP.")

    # Simple HTTP fallback
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        # Basic HTML to text
        import re
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        result = text[:8000]
        logger.info(f"[HTTP] Fetched {url}: {len(result)} chars")
        return result
    except Exception as e:
        return f"Failed to load {url}: {e}"

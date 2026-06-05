"""
news.py — News ingestion from two sources:

  1. CSE (Colombo Stock Exchange) — unofficial POST API at cse.lk/api/
     Returns structured JSON for company announcements, financial filings,
     and exchange notices. No authentication required.

  2. Almas Equities — one.almasequities.com/dl/Home
     A JavaScript SPA requiring login. Scraped via Playwright (headless
     browser) with credentials stored in .env (ALMAS_EMAIL, ALMAS_PASSWORD).

Output schema (both sources normalised to same parquet):
  date        : datetime  — publication date (UTC)
  source      : str       — "cse" or "almas"
  ticker      : str|None  — SL20 ticker if identified, else None
  headline    : str       — title / subject of the announcement
  body        : str       — full text (empty string if unavailable)
  url         : str       — direct link (PDF or page URL)
  url_hash    : str       — sha256(url) — dedup key
  annct_type  : str       — e.g. "financial", "approved", "general", "news"

Usage
-----
  from sl20_ml.ingestion.news import CSEFetcher, AlmasFetcher
  rows = CSEFetcher().fetch()
  rows += AlmasFetcher().fetch()
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── Ticker → CSE symbol mapping (ordinary shares, .N0000 suffix) ─────────────
# Verify these by running: POST https://www.cse.lk/api/companyInfoSummery
# with body symbol=JKH.N0000  — should return the company name.
# Some tickers may need different suffixes (.X0000 for prefs, etc.).
CSE_SYMBOL_MAP: dict[str, str] = {
    "JKH":  "JKH.N0000",
    "COMB": "COMB.N0000",
    "DIAL": "DIAL.N0000",
    "SAMP": "SAMP.N0000",
    "HAYL": "HAYL.N0000",
    "CTC":  "CTC.N0000",
    "HNB":  "HNB.N0000",
    "LIOC": "LIOC.N0000",
    "SPEN": "SPEN.N0000",
    "DFCC": "DFCC.N0000",
    "NTB":  "NTB.N0000",
    "BUKI": "BUKI.N0000",
    "CARG": "CARG.N0000",
    "CCS":  "CCS.N0000",
    "HHL":  "HHL.N0000",
    "LION": "LION.N0000",
    "MELS": "MELS.N0000",
    "TKYO": "TKYO.N0000",
    "VONE": "VONE.N0000",
    "AEL":  "AEL.N0000",
}

# Reverse map: CSE symbol prefix → our ticker (for tagging scraped results)
_SYMBOL_TO_TICKER: dict[str, str] = {
    v.split(".")[0]: k for k, v in CSE_SYMBOL_MAP.items()
}

# Company name fragments → ticker (for text-based tagging in Almas)
COMPANY_NAME_MAP: dict[str, str] = {
    "john keells":          "JKH",
    "commercial bank":      "COMB",
    "dialog":               "DIAL",
    "sampath":              "SAMP",
    "hayleys":              "HAYL",
    "ceylon tobacco":       "CTC",
    "hatton national":      "HNB",
    "lanka ioc":            "LIOC",
    "lioc":                 "LIOC",
    "spen":                 "SPEN",
    "dfcc":                 "DFCC",
    "nations trust":        "NTB",
    "ntb":                  "NTB",
    "bukit":                "BUKI",
    "cargo":                "CARG",
    "cargills":             "CARG",
    "ccs":                  "CCS",
    "hela":                 "HHL",
    "lion brewery":         "LION",
    "melstacorp":           "MELS",
    "tokyo cement":         "TKYO",
    "vallibel one":         "VONE",
    "ael":                  "AEL",
    "access engineering":   "AEL",
}


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _tag_ticker(text: str) -> str | None:
    """
    Try to identify which SL20 ticker a piece of text is about.
    Checks ticker symbols first (exact), then company name fragments.
    Returns the ticker string or None.
    """
    text_lower = text.lower()

    # Check exact ticker mention (e.g. "JKH", "JKH.N0000")
    for ticker in CSE_SYMBOL_MAP:
        if ticker.lower() in text_lower.split():
            return ticker
    for sym_prefix, ticker in _SYMBOL_TO_TICKER.items():
        if sym_prefix.lower() in text_lower:
            return ticker

    # Check company name fragments
    for fragment, ticker in COMPANY_NAME_MAP.items():
        if fragment in text_lower:
            return ticker

    return None


# ── CSE Fetcher ───────────────────────────────────────────────────────────────

class CSEFetcher:
    """
    Fetches company announcements from the unofficial CSE POST API.
    No authentication required.

    Hits four announcement endpoints:
      - approvedAnnouncement        : corporate decisions (AGM, dividends, rights)
      - getFinancialAnnouncement    : annual/interim reports
      - getNewListingsRelatedNoticesAnnouncements : IPOs, new listings
      - getNonComplianceAnnouncements : regulatory notices

    Also fetches per-ticker data via companyInfoSummery for the 20 SL20 stocks.
    """

    BASE_URL = "https://www.cse.lk/api"

    # Announcement endpoints (POST, no body required)
    ANNOUNCEMENT_ENDPOINTS: list[tuple[str, str]] = [
        ("approvedAnnouncement",                       "approved"),
        ("getFinancialAnnouncement",                   "financial"),
        ("getNewListingsRelatedNoticesAnnouncements",  "listing"),
        ("getNonComplianceAnnouncements",              "noncompliance"),
    ]

    def __init__(self, delay_sec: float = 0.5):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "stoX/1.0 (research project)",
            "Accept":     "application/json",
        })
        self.delay = delay_sec

    def _post(self, endpoint: str, data: dict | None = None) -> Any:
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            resp = self.session.post(
                url,
                data=data or {},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning(f"CSE API error [{endpoint}]: {exc}")
            return None

    def _parse_announcement_response(
        self,
        payload: Any,
        annct_type: str,
    ) -> list[dict]:
        """
        Extract rows from a CSE announcement JSON response.
        Field names vary by endpoint — we capture everything defensively.
        """
        if payload is None:
            return []

        # The response is a dict with one top-level list key
        # e.g. {"approvedAnnouncements": [...]}  or  {"reqFinancialAnnouncemnets": [...]}
        rows_raw: list[dict] = []
        if isinstance(payload, dict):
            for v in payload.values():
                if isinstance(v, list):
                    rows_raw = v
                    break
        elif isinstance(payload, list):
            rows_raw = payload

        rows = []
        for item in rows_raw:
            if not isinstance(item, dict):
                continue

            # Try to extract date from common field names
            raw_date = (
                item.get("announcementDate")
                or item.get("date")
                or item.get("publishedDate")
                or item.get("createdDate")
                or ""
            )
            try:
                date = pd.to_datetime(raw_date, utc=True)
            except Exception:
                date = pd.Timestamp.now(tz="UTC")

            # Headline / subject
            headline = (
                item.get("subject")
                or item.get("fileText")
                or item.get("title")
                or item.get("companyName", "")
                or item.get("company", "")
            )

            # URL to the announcement (often a PDF)
            url = (
                item.get("pdfLink")
                or item.get("url")
                or item.get("link")
                or f"{self.BASE_URL}/{annct_type}/{item.get('id', '')}"
            )

            # Body text (often empty for CSE — headline is sufficient)
            body = item.get("body") or item.get("content") or ""

            # Try to figure out which ticker this is for
            symbol_field = (
                item.get("symbol")
                or item.get("companySymbol")
                or item.get("ticker")
                or ""
            )
            symbol_prefix = symbol_field.split(".")[0].upper() if symbol_field else ""
            ticker = (
                _SYMBOL_TO_TICKER.get(symbol_prefix)
                or _tag_ticker(headline)
                or _tag_ticker(str(item.get("company") or item.get("companyName") or ""))
            )

            rows.append({
                "date":       date,
                "source":     "cse",
                "ticker":     ticker,
                "headline":   str(headline).strip(),
                "body":       str(body).strip(),
                "url":        str(url),
                "url_hash":   _url_hash(str(url)),
                "annct_type": annct_type,
            })

        return rows

    def fetch(self) -> list[dict]:
        """Fetch all announcement types. Returns a flat list of normalised rows."""
        all_rows: list[dict] = []

        for endpoint, annct_type in self.ANNOUNCEMENT_ENDPOINTS:
            logger.info(f"  CSE → {endpoint} ...")
            payload = self._post(endpoint)
            rows = self._parse_announcement_response(payload, annct_type)
            logger.info(f"    Got {len(rows)} rows")
            all_rows.extend(rows)
            time.sleep(self.delay)

        logger.info(f"CSE fetch complete: {len(all_rows)} total announcements")
        return all_rows


# ── Almas Fetcher ─────────────────────────────────────────────────────────────

class AlmasFetcher:
    """
    Scrapes news headlines from one.almasequities.com/dl/Home using Playwright.

    Requires a paid Almas Equities account. Store credentials in .env:
        ALMAS_EMAIL=your@email.com
        ALMAS_PASSWORD=yourpassword

    The site is a React SPA — static HTTP requests won't see any content.
    Playwright launches a headless Chromium browser, logs in, waits for
    the news feed to render, then extracts headlines and links.

    Install: pip install playwright && playwright install chromium
    """

    LOGIN_URL = "https://one.almasequities.com/dl/Login"
    HOME_URL  = "https://one.almasequities.com/dl/Home"

    # CSS selectors — UPDATE THESE after inspecting the live DOM.
    # In Chrome DevTools: open Home, right-click a news item → Inspect.
    # These are best-guess patterns for a typical React news list.
    SELECTORS = {
        "email_input":    'input[type="email"], input[name="email"], input[placeholder*="mail" i]',
        "password_input": 'input[type="password"]',
        "login_button":   'button[type="submit"], button:has-text("Login"), button:has-text("Sign In")',
        # After login, news items — inspect the DOM to confirm these:
        "news_list":      '.news-item, .news-row, [class*="news"], [class*="News"], tr.news, li.news',
        "headline":       'a, .headline, .title, [class*="title" i], [class*="subject" i]',
        "date":           '.date, [class*="date" i], time',
        "link":           'a[href]',
    }

    def __init__(self, headless: bool = True, max_articles: int = 200):
        self.headless     = headless
        self.max_articles = max_articles
        self.email        = os.getenv("ALMAS_EMAIL", "")
        self.password     = os.getenv("ALMAS_PASSWORD", "")

    def fetch(self) -> list[dict]:
        """
        Launch Playwright, log in, scrape news feed, return normalised rows.

        Raises RuntimeError if credentials are missing or login fails.
        """
        if not self.email or not self.password:
            raise RuntimeError(
                "ALMAS_EMAIL and ALMAS_PASSWORD must be set in .env — "
                "see ml/.env.example"
            )

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
        except ImportError:
            raise RuntimeError(
                "playwright not installed. Run:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        rows: list[dict] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            ctx     = browser.new_context()
            page    = ctx.new_page()

            # ── Step 1: Log in ─────────────────────────────────────────────
            logger.info("Almas → navigating to login page ...")
            page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30_000)

            try:
                page.fill(self.SELECTORS["email_input"],    self.email)
                page.fill(self.SELECTORS["password_input"], self.password)
                page.click(self.SELECTORS["login_button"])
                # Wait for navigation to the home page after login
                page.wait_for_url("**/Home**", timeout=15_000)
                logger.info("Almas → login successful")
            except PwTimeout:
                # Try a fallback: maybe we're already on Home
                if "Home" not in page.url:
                    # Save a debug screenshot so you can see what went wrong
                    page.screenshot(path="almas_login_debug.png")
                    raise RuntimeError(
                        "Almas login timed out. Check credentials in .env. "
                        "Screenshot saved to almas_login_debug.png"
                    )

            # ── Step 2: Wait for news content to render ─────────────────
            logger.info("Almas → waiting for news feed ...")
            try:
                # Wait for any element matching the news selector
                page.wait_for_selector(
                    self.SELECTORS["news_list"],
                    timeout=20_000,
                    state="visible",
                )
            except PwTimeout:
                page.screenshot(path="almas_home_debug.png")
                logger.warning(
                    "Almas → news selector not found. "
                    "DOM screenshot saved to almas_home_debug.png. "
                    "Update SELECTORS in news.py after inspecting the screenshot."
                )
                browser.close()
                return []

            # ── Step 3: Extract news items ───────────────────────────────
            news_elements = page.query_selector_all(self.SELECTORS["news_list"])
            logger.info(f"Almas → found {len(news_elements)} news elements")

            for el in news_elements[: self.max_articles]:
                try:
                    # Headline text
                    headline_el = el.query_selector(self.SELECTORS["headline"])
                    headline    = headline_el.inner_text().strip() if headline_el else ""

                    # Link href
                    link_el = el.query_selector(self.SELECTORS["link"])
                    href    = link_el.get_attribute("href") or "" if link_el else ""
                    if href and not href.startswith("http"):
                        href = "https://one.almasequities.com" + href

                    # Date text
                    date_el  = el.query_selector(self.SELECTORS["date"])
                    date_str = date_el.inner_text().strip() if date_el else ""
                    try:
                        date = pd.to_datetime(date_str, utc=True)
                    except Exception:
                        date = pd.Timestamp.now(tz="UTC")

                    if not headline:
                        continue

                    ticker = _tag_ticker(headline)

                    rows.append({
                        "date":       date,
                        "source":     "almas",
                        "ticker":     ticker,
                        "headline":   headline,
                        "body":       "",       # body requires clicking into article
                        "url":        href,
                        "url_hash":   _url_hash(href or headline),
                        "annct_type": "news",
                    })
                except Exception as exc:
                    logger.debug(f"  Skipping element: {exc}")
                    continue

            browser.close()

        logger.info(f"Almas fetch complete: {len(rows)} articles")
        return rows


# ── Shared helper ─────────────────────────────────────────────────────────────

def save_raw(rows: list[dict], output_path: Path) -> pd.DataFrame:
    """
    Merge new rows with existing parquet (if any), deduplicate by url_hash,
    sort by date, and save.
    """
    if not rows:
        logger.warning("No rows to save.")
        if output_path.exists():
            return pd.read_parquet(output_path)
        return pd.DataFrame()

    new_df = pd.DataFrame(rows)

    if output_path.exists():
        existing = pd.read_parquet(output_path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    before = len(combined)
    combined = combined.drop_duplicates(subset="url_hash", keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)

    logger.info(
        f"Saved {len(combined)} rows to {output_path} "
        f"(+{len(combined) - (before - len(new_df))} new after dedup)"
    )
    return combined

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

# Company name fragments → ticker (for text-based tagging).
# Ordered longest-first to avoid short matches shadowing long ones.
# CSE returns full legal names like "HATTON NATIONAL BANK PLC" —
# fragments are checked as substrings of lowercased text.
COMPANY_NAME_MAP: dict[str, str] = {
    # JKH
    "john keells holdings":     "JKH",
    "john keells":              "JKH",
    # COMB
    "commercial bank of ceylon": "COMB",
    "commercial bank":          "COMB",
    # DIAL
    "dialog axiata":            "DIAL",
    "dialog":                   "DIAL",
    # SAMP
    "sampath bank":             "SAMP",
    "sampath":                  "SAMP",
    # HAYL
    "hayleys":                  "HAYL",
    # CTC
    "ceylon tobacco":           "CTC",
    # HNB
    "hatton national bank":     "HNB",
    "hnb finance":              "HNB",
    "hnb":                      "HNB",
    # LIOC
    "lanka ioc":                "LIOC",
    "lioc":                     "LIOC",
    # SPEN
    "softlogic life":           "SPEN",
    "spen":                     "SPEN",
    # DFCC
    "dfcc bank":                "DFCC",
    "dfcc":                     "DFCC",
    # NTB
    "nations trust bank":       "NTB",
    "nations trust":            "NTB",
    "ntb":                      "NTB",
    # BUKI
    "bukit darah":              "BUKI",
    "buki":                     "BUKI",
    # CARG
    "cargills (ceylon)":        "CARG",
    "cargills ceylon":          "CARG",
    "cargills":                 "CARG",
    # CCS
    "ccs":                      "CCS",
    # HHL
    "hela apparel":             "HHL",
    "hhl":                      "HHL",
    # LION
    "lion brewery":             "LION",
    # MELS
    "melstacorp":               "MELS",
    # TKYO
    "tokyo cement":             "TKYO",
    # VONE
    "vallibel one":             "VONE",
    # AEL
    "access engineering":       "AEL",
    "ael":                      "AEL",
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

    @staticmethod
    def _parse_date(item: dict) -> pd.Timestamp:
        """
        Parse date from a CSE API item. Field names and formats vary:
          - createdDate       : Unix ms integer  e.g. 1780675552000
                                OR string         e.g. "08 May 2026 05:02:54 PM"
          - dateOfAnnouncement: string            e.g. "05 Jun 2026"
          - uploadedDate      : string            e.g. "05 Jun 2026 09:23:12 PM"
          - manualDate        : Unix ms integer
        Priority: dateOfAnnouncement > uploadedDate > createdDate > manualDate
        """
        for field in ("dateOfAnnouncement", "uploadedDate", "createdDate", "manualDate"):
            val = item.get(field)
            if val is None:
                continue
            try:
                if isinstance(val, (int, float)) and val > 1e10:
                    # Unix timestamp in milliseconds
                    return pd.Timestamp(val, unit="ms", tz="UTC")
                return pd.to_datetime(str(val), utc=True)
            except Exception:
                continue
        return pd.Timestamp.now(tz="UTC")

    def _parse_announcement_response(
        self,
        payload: Any,
        annct_type: str,
    ) -> list[dict]:
        """
        Extract rows from a CSE announcement JSON response.
        Each endpoint has different field names — handled explicitly below.

        Confirmed field shapes (from live API inspection):
          approved   : {id, createdDate(ms), dateOfAnnouncement, announcementCategory,
                        company, symbol(null), remarks, logoUrl}
          financial  : {id, path(PDF), manualDate(ms), uploadedDate, fileText,
                        name, symbol(str), logoUrl}
          listing    : {id, createdDate(str), announcementCategory, company, remarks}
          noncompliance: similar to approved
        """
        if payload is None:
            return []

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

            date = self._parse_date(item)

            # ── Headline: endpoint-specific ───────────────────────────────
            if annct_type == "financial":
                # fileText = "Annual Report as at 31st March 2026"
                # name     = company name
                file_text = item.get("fileText") or ""
                company   = item.get("name") or ""
                headline  = f"{file_text} — {company}" if file_text else company

            elif annct_type in ("approved", "noncompliance"):
                # announcementCategory = "ANNUAL GENERAL MEETING - INITIAL"
                # company = company name
                category = item.get("announcementCategory") or ""
                company  = item.get("company") or ""
                headline = f"{category} — {company}" if category else company
                # remarks may have extra context
                remarks  = item.get("remarks") or ""

            elif annct_type == "listing":
                # remarks has the real content
                remarks  = item.get("remarks") or ""
                category = item.get("announcementCategory") or ""
                company  = item.get("company") or ""
                headline = remarks or f"{category} — {company}"

            else:
                headline = (
                    item.get("fileText") or item.get("subject")
                    or item.get("title") or item.get("remarks")
                    or item.get("company") or ""
                )

            # ── Body: remarks field where available ───────────────────────
            body = item.get("remarks") or item.get("content") or ""
            if annct_type == "listing":
                body = ""  # remarks already used as headline for listings

            # ── URL: financial has a PDF path ─────────────────────────────
            if annct_type == "financial" and item.get("path"):
                url = f"https://www.cse.lk/{item['path']}"
            else:
                url = (
                    item.get("pdfLink") or item.get("url") or item.get("link")
                    or f"https://www.cse.lk/api/{annct_type}/{item.get('id', '')}"
                )

            # ── Ticker: symbol field (no suffix) takes priority ───────────
            symbol_raw = (
                item.get("symbol") or item.get("companySymbol") or ""
            )
            symbol_prefix = symbol_raw.split(".")[0].upper() if symbol_raw else ""
            ticker = (
                _SYMBOL_TO_TICKER.get(symbol_prefix)
                or _tag_ticker(headline)
                or _tag_ticker(str(item.get("company") or item.get("name") or ""))
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

    LOGIN_URL    = "https://one.almasequities.com/dl/Login"
    HOME_URL     = "https://one.almasequities.com/dl/Home"
    SESSION_FILE = Path(__file__).parents[4] / "data" / "raw" / "news" / "almas_session.json"

    # CSS selectors for the news feed (update after inspecting live DOM)
    SELECTORS = {
        "email_input": 'input[type="email"], input[name="email"], input[placeholder*="mail" i]',
        "news_list":   '.news-item, .news-row, [class*="news"], [class*="News"], tr, li',
        "headline":    'a, .headline, .title, [class*="title" i], [class*="subject" i]',
        "date":        '.date, [class*="date" i], time',
        "link":        'a[href]',
    }

    def __init__(self, headless: bool = True, max_articles: int = 200):
        self.headless     = headless
        self.max_articles = max_articles
        self.email        = os.getenv("ALMAS_EMAIL", "")

    def setup_session(self) -> None:
        """
        Open a VISIBLE browser so you can log in manually.
        Almas uses OTP/PIN login — it emails a PIN after you submit your email.

        Steps:
          1. This opens a Chrome window at the Almas login page
          2. Enter your email and click Continue
          3. Check your email inbox for the PIN
          4. Enter the PIN in the browser
          5. Once you reach the Home page, press Enter in this terminal
          6. Session cookies are saved to almas_session.json for future headless runs

        Run once:
          python build_news_ingest.py --setup-almas-session
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("playwright not installed. Run: pip install playwright && python -m playwright install chromium")

        print("\n" + "="*60)
        print("ALMAS SESSION SETUP")
        print("="*60)
        print("A browser window will open. Please:")
        print("  1. Enter your email and click Continue")
        print("  2. Check your inbox for the PIN/OTP code")
        print("  3. Enter the PIN in the browser")
        print("  4. Wait until you see the Home page (charts, news)")
        print("  5. Come back here and press Enter")
        print("="*60 + "\n")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            ctx     = browser.new_context()
            page    = ctx.new_page()

            # Pre-fill email to save the user a step
            page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.fill(self.SELECTORS["email_input"], self.email)
            except Exception:
                pass  # fine — user can type it manually

            input("\nPress Enter once you are logged in and can see the Home page... ")

            # Save full browser storage state (cookies + localStorage)
            self.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(self.SESSION_FILE))
            print(f"Session saved to {self.SESSION_FILE}")
            browser.close()

    def fetch(self) -> list[dict]:
        """
        Scrape Almas news feed using a saved session.
        Run setup_session() first (once) to create the session file.
        """
        if not self.SESSION_FILE.exists():
            raise RuntimeError(
                f"No Almas session found at {self.SESSION_FILE}.\n"
                "Run this once to log in and save the session:\n"
                "  python build_news_ingest.py --setup-almas-session"
            )

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
        except ImportError:
            raise RuntimeError("playwright not installed. Run: pip install playwright && python -m playwright install chromium")

        rows: list[dict] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            # Restore the saved login session
            ctx  = browser.new_context(storage_state=str(self.SESSION_FILE))
            page = ctx.new_page()

            logger.info("Almas → loading Home with saved session ...")
            page.goto(self.HOME_URL, wait_until="networkidle", timeout=30_000)

            # If we got redirected to Login, session has expired
            if "Login" in page.url or "login" in page.url:
                page.screenshot(path="almas_session_expired.png")
                browser.close()
                raise RuntimeError(
                    "Almas session has expired. Re-run setup:\n"
                    "  python build_news_ingest.py --setup-almas-session"
                )

            # Wait for news content to render
            try:
                page.wait_for_selector(self.SELECTORS["news_list"], timeout=20_000, state="visible")
            except PwTimeout:
                page.screenshot(path="almas_home_debug.png")
                logger.warning(
                    "Almas → news selector not found. Screenshot saved to almas_home_debug.png. "
                    "Update SELECTORS['news_list'] in news.py after inspecting the DOM."
                )
                browser.close()
                return []

            news_elements = page.query_selector_all(self.SELECTORS["news_list"])
            logger.info(f"Almas → found {len(news_elements)} elements, extracting news ...")

            for el in news_elements[: self.max_articles]:
                try:
                    headline_el = el.query_selector(self.SELECTORS["headline"])
                    headline    = headline_el.inner_text().strip() if headline_el else ""

                    link_el = el.query_selector(self.SELECTORS["link"])
                    href    = link_el.get_attribute("href") or "" if link_el else ""
                    if href and not href.startswith("http"):
                        href = "https://one.almasequities.com" + href

                    date_el  = el.query_selector(self.SELECTORS["date"])
                    date_str = date_el.inner_text().strip() if date_el else ""
                    try:
                        date = pd.to_datetime(date_str, utc=True)
                    except Exception:
                        date = pd.Timestamp.now(tz="UTC")

                    if not headline:
                        continue

                    rows.append({
                        "date":       date,
                        "source":     "almas",
                        "ticker":     _tag_ticker(headline),
                        "headline":   headline,
                        "body":       "",
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

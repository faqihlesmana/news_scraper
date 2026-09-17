"""
base_parser.py
Shared utilities for all parsers: HTTP fetching, text cleaning,
date normalization to WITA (YYYY-MM-DD HH:mm:ss), pagination detection.

Pagination support:
  - Listing page  : find_next_page()            → URL halaman daftar berikutnya
  - Article detail: find_article_next_page()    → URL halaman artikel berikutnya
                    fetch_full_article_content() → fetch & gabung semua halaman artikel
"""

import re
import time
import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_TIMEOUT, REQUEST_DELAY

logger = logging.getLogger(__name__)

WITA = timezone(timedelta(hours=8))   # UTC+8

# ─────────────────────────────────────────────────────────────────────────────
#  Boilerplate patterns to strip from article body
# ─────────────────────────────────────────────────────────────────────────────
BOILERPLATE_PATTERNS = [
    r"baca\s*juga\s*:.*",
    r"ikuti\s*(kami|berita)\s*(di|kami).*",
    r"follow\s*(kami|us)\s*(di|on).*",
    r"artikel\s*ini\s*telah.*",
    r"konten\s*premium.*",
    r"subscribe\s*(sekarang|now).*",
    r"bergabunglah\s*dengan.*",
    r"share\s*artikel\s*ini.*",
    r"klik\s*di\s*sini.*",
    r"editor\s*:\s*\w+.*",
    r"reporter\s*:\s*\w+.*",
    r"sumber\s*:\s*\w+.*",
    r"untuk\s*berlangganan.*",
    r"simak\s*berita\s*terkini.*",
    r"dapatkan\s*berita\s*terbaru.*",
    r"©.*reserved.*",
    r"all rights reserved.*",
    r"bagikan\s*artikel.*",
    r"lihat\s*juga\s*:.*",
    r"advertisement",
    r"iklan",
]
_BOILERPLATE_RE = re.compile(
    "|".join(BOILERPLATE_PATTERNS), re.IGNORECASE | re.DOTALL
)

# Indonesian month names → number
ID_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4,
    "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
    "september": 9, "oktober": 10, "november": 11, "desember": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# ─────────────────────────────────────────────────────────────────────────────
#  HTTP
# ─────────────────────────────────────────────────────────────────────────────
_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(REQUEST_HEADERS)
    return _session


def fetch(url: str, retries: int = 2) -> Optional[BeautifulSoup]:
    """Fetch URL and return BeautifulSoup, or None on failure."""
    for attempt in range(retries + 1):
        try:
            resp = get_session().get(url, timeout=REQUEST_TIMEOUT, verify=False)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            time.sleep(REQUEST_DELAY)
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.warning(f"[fetch] Attempt {attempt+1} failed for {url}: {e}")
            if attempt < retries:
                time.sleep(2)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Text cleaning
# ─────────────────────────────────────────────────────────────────────────────
def clean_content(raw: str) -> str:
    """Remove boilerplate, excess whitespace, and deduplicate sentences."""
    if not raw:
        return ""
    # Line-by-line filter
    lines = raw.splitlines()
    cleaned = []
    seen = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove boilerplate lines
        if _BOILERPLATE_RE.fullmatch(line.lower()):
            continue
        if _BOILERPLATE_RE.search(line):
            # Only strip if line IS mostly boilerplate (short)
            if len(line) < 120:
                continue
        if line.lower() in seen:
            continue
        seen.add(line.lower())
        cleaned.append(line)
    return "\n\n".join(cleaned)


def extract_paragraphs(soup_el) -> str:
    """Extract <p> text from a BeautifulSoup element and clean it."""
    if soup_el is None:
        return ""
    # Remove unwanted tags first
    for tag in soup_el.find_all(["script", "style", "iframe", "figure",
                                  "aside", "nav", "footer", ".related",
                                  "[class*='related']", "[class*='widget']"]):
        tag.decompose()
    paras = [p.get_text(strip=True) for p in soup_el.find_all("p")]
    if not paras:
        paras = [soup_el.get_text(separator="\n", strip=True)]
    raw = "\n\n".join(p for p in paras if len(p) > 30)
    return clean_content(raw)


# ─────────────────────────────────────────────────────────────────────────────
#  Date normalization → WITA (YYYY-MM-DD HH:mm:ss)
# ─────────────────────────────────────────────────────────────────────────────
def normalize_date(raw: str) -> Optional[str]:
    """
    Convert any date string to 'YYYY-MM-DD HH:mm:ss' in WITA (UTC+8).
    Returns None if parsing fails.
    """
    if not raw:
        return None
    raw = raw.strip()

    # 1. ISO 8601 with timezone offset  e.g. 2026-07-26T15:44:51+08:00
    m = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})([\+\-]\d{2}:\d{2}|Z)?", raw)
    if m:
        dt_str = m.group(1)
        tz_str = m.group(2) or "+08:00"
        try:
            dt = datetime.fromisoformat(dt_str + tz_str.replace("Z", "+00:00"))
            dt_wita = dt.astimezone(WITA)
            return dt_wita.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    # 2. Standard date e.g. 2026-07-26 16:55:00
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(:\d{2})?)", raw)
    if m:
        try:
            dt = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S"
                                   if ":" in m.group(2)[5:] else "%Y-%m-%d %H:%M")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    # 3. Indonesian: "25 July 2026" or "25 Juli 2026" or "Sabtu, 25 Juli 2026"
    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?",
        raw, re.IGNORECASE
    )
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = int(m.group(3))
        time_str = m.group(4) or "00:00:00"
        month = ID_MONTHS.get(month_str)
        if month:
            try:
                ts = f"{year:04d}-{month:02d}-{day:02d} {time_str}"
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"
                                       if len(time_str) == 8 else "%Y-%m-%d %H:%M")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    # 3b. Indonesian/English "Juli 20, 2026" or "July 20, 2026"
    m = re.search(
        r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?",
        raw, re.IGNORECASE
    )
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3))
        time_str = m.group(4) or "00:00:00"
        month = ID_MONTHS.get(month_str)
        if month:
            try:
                ts = f"{year:04d}-{month:02d}-{day:02d} {time_str}"
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S"
                                       if len(time_str) == 8 else "%Y-%m-%d %H:%M")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    # 4. Tribunnews style "Senin, 10 April 2023 13:14 WITA"
    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s+(\d{2}:\d{2})",
        raw, re.IGNORECASE
    )
    if m:
        day, month_s, year, t = int(m.group(1)), m.group(2).lower(), int(m.group(3)), m.group(4)
        month = ID_MONTHS.get(month_s)
        if month:
            try:
                dt = datetime.strptime(f"{year}-{month:02d}-{day:02d} {t}", "%Y-%m-%d %H:%M")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    # 5. "Monday, 22 December 2025"
    for fmt in ["%A, %d %B %Y", "%d %B %Y", "%B %d, %Y"]:
        try:
            dt = datetime.strptime(re.sub(r"\s+", " ", raw.strip()), fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    logger.debug(f"[normalize_date] Could not parse: {raw!r}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Pagination
# ─────────────────────────────────────────────────────────────────────────────
def find_next_page(soup: BeautifulSoup, current_url: str) -> Optional[str]:
    """Return the URL of the next page, or None."""
    # Priority 1: rel="next"
    link = soup.find("link", rel="next") or soup.find("a", rel="next")
    if link and link.get("href"):
        return urllib.parse.urljoin(current_url, link["href"])

    # Priority 2: common CSS selectors
    for sel in [
        "a.next", "a.next-page", "[class*='next-page']", "[class*='nav-next']",
        "[class*='pagination'] a[aria-label*='Next']",
        "[class*='pagination'] a[class*='next']",
        ".page-navigation a.next", ".page-numbers.next",
        "a[class*='pagination-next']",
    ]:
        el = soup.select_one(sel)
        if el and el.get("href"):
            return urllib.parse.urljoin(current_url, el["href"])

    # Priority 3: text heuristic
    for a in soup.find_all("a", href=True):
        txt = a.get_text(strip=True).lower()
        if txt in ("next", "selanjutnya", "berikutnya", "›", "»", ">"):
            href = a["href"]
            if href and not href.startswith("#"):
                return urllib.parse.urljoin(current_url, href)

    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Article detail pagination
# ─────────────────────────────────────────────────────────────────────────────
def find_article_next_page(soup: BeautifulSoup, current_url: str,
                            content_selector: str) -> Optional[str]:
    """
    Detect if an article's body is split across multiple pages and return
    the URL of the next page, or None if it's a single page.

    This is STRICTER than find_next_page() to avoid accidentally following
    the listing page's "next" instead of the article's "next page" link.
    It only matches links that are INSIDE the article content area, or
    standard pagination elements that contain a page number indicator.
    """
    # Strategy 1: canonical <link rel="next"> in <head>
    link = soup.find("link", rel="next")
    if link and link.get("href"):
        next_url = urllib.parse.urljoin(current_url, link["href"])
        # Verify it's not just the listing next page (same path base)
        if next_url != current_url:
            return next_url

    # Strategy 2: pagination inside the article content area itself
    content_el = soup.select_one(content_selector) if content_selector else None
    if content_el:
        # Look for page navigation inside article body
        for sel in [
            "a.next", "[class*='next-page']", "a[rel='next']",
            ".page-numbers.next", "[class*='pagination-next']",
            "a[aria-label*='next']", ".page-nav a[aria-label*='next']",
        ]:
            el = content_el.select_one(sel)
            if el and el.get("href"):
                href = el["href"]
                if not href.startswith("#"):
                    return urllib.parse.urljoin(current_url, href)

        # Numbered pagination links INSIDE the content (e.g. "1 2 3" at bottom)
        for a in content_el.find_all("a", href=True):
            txt = a.get_text(strip=True).lower()
            if txt in ("next", "selanjutnya", "berikutnya", "›", "»", ">"):
                href = a["href"]
                if href and not href.startswith("#"):
                    return urllib.parse.urljoin(current_url, href)

    # Strategy 3: Check if there's a "Page X of Y" indicator and numbered links
    # Pattern: look for .page-numbers or .wp-pagenavi OUTSIDE content but
    # only if the page indicator clearly says we're not on the last page
    for page_container in soup.select(".page-numbers, .wp-pagenavi, [class*='pagenavi'], [class*='page-links'], .page-nav"):
        # Find the currently-active page number
        current_pg_el = page_container.select_one(".current, [aria-current='page']")
        if current_pg_el:
            # Find the next sibling <a> after the current page
            nxt = current_pg_el.find_next_sibling("a")
            if nxt and nxt.get("href") and not nxt.get_text(strip=True).lower() in ("»", "»»", "last"):
                return urllib.parse.urljoin(current_url, nxt["href"])

    # Strategy 4: URL-based pagination (add ?page=N or /page/N)
    # Only activate when soup explicitly contains "halaman 1 dari" or "page 1 of"
    page_text = soup.get_text()
    m = re.search(r"(?:halaman|page)\s+(\d+)\s+(?:dari|of)\s+(\d+)",
                  page_text, re.IGNORECASE)
    if m:
        current_pg = int(m.group(1))
        total_pgs  = int(m.group(2))
        if current_pg < total_pgs:
            # Try appending /page/N+1 style
            parsed = urllib.parse.urlparse(current_url)
            # Remove trailing slash, add /page/N
            base_path = parsed.path.rstrip("/")
            next_path = f"{base_path}/{current_pg + 1}"
            candidate = urllib.parse.urlunparse(parsed._replace(path=next_path))
            return candidate

    return None


def fetch_full_article_content(first_soup: BeautifulSoup, first_url: str,
                                content_selector: str,
                                max_pages: int = 10) -> str:
    """
    Fetch and concatenate content from ALL pages of a multi-page article.

    Args:
        first_soup:        BeautifulSoup of the first (already fetched) page.
        first_url:         URL of the first page.
        content_selector:  CSS selector for the article body element.
        max_pages:         Safety cap (default 10) to prevent infinite loops.

    Returns:
        Combined cleaned content string from all pages.
    """
    all_parts: list[str] = []
    visited: set[str] = {first_url}
    soup = first_soup
    url  = first_url

    for page_num in range(1, max_pages + 1):
        # Extract content from current page
        content_el = soup.select_one(content_selector) if content_selector else None
        part = extract_paragraphs(content_el)
        if part:
            all_parts.append(part)
            logger.debug(f"[pagination] Page {page_num}: {len(part)} chars from {url}")

        # Find next article page
        next_url = find_article_next_page(soup, url, content_selector)
        if not next_url or next_url in visited:
            if page_num > 1:
                logger.info(f"[pagination] Article has {page_num} page(s), total chars: {sum(len(p) for p in all_parts)}")
            break

        visited.add(next_url)
        logger.info(f"[pagination] Fetching article page {page_num + 1}: {next_url}")
        next_soup = fetch(next_url)
        if not next_soup:
            logger.warning(f"[pagination] Failed to fetch article page {page_num + 1}: {next_url}")
            break

        soup = next_soup
        url  = next_url

    return "\n\n--- (halaman selanjutnya) ---\n\n".join(all_parts)


# ─────────────────────────────────────────────────────────────────────────────
def extract_article_links(soup: BeautifulSoup, base_url: str,
                           link_selector: str, domain_hint: str = "") -> list[str]:
    """
    Extract article URLs from a listing page using a CSS selector.
    Returns a de-duped ordered list.
    """
    seen = set()
    links = []
    base_domain = urllib.parse.urlparse(base_url).netloc

    for el in soup.select(link_selector):
        href = el.get("href") or ""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(full)
        # same domain (or allow subdomain of base)
        if base_domain not in parsed.netloc and parsed.netloc not in base_domain:
            if domain_hint and domain_hint not in parsed.netloc:
                continue
        if full in seen:
            continue
        seen.add(full)
        links.append(full)

    return links

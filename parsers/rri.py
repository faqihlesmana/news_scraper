"""
parsers/rri.py
Source  : https://rri.co.id/search?q=pohuwato
Listing : search results with a.title links, pagination via ?page=N
Article : h1, .post-content / .detail-berita, date text in header, Oleh - <name>

RRI.co.id uses a custom CMS. Article URLs have format:
  https://rri.co.id/{region}/{category}/{id}/{slug}
  e.g. https://rri.co.id/gorontalo/regional/2702011/buka-konferensi-pgri-...
"""
import json
import re
import urllib.parse
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date

SOURCE_SLUG = "rri"
SOURCE_NAME = "RRI Pohuwato"

# Article URL pattern: rri.co.id/<region>/<category>/<numeric-id>/<slug>
_ARTICLE_URL_RE = re.compile(
    r"https?://rri\.co\.id/[^/]+/[^/]+/\d+/[^/?#]+"
)

CONTENT_SELECTOR = "#news-content, .post_details_block, .post-content, .detail-berita"

# Date format from RRI: "02 Sep 2026, 14:22 WIB" or "2 September 2026 14:22"
_RRI_MONTHS = {
    "jan": "januari", "feb": "februari", "mar": "maret", "apr": "april",
    "may": "mei", "mei": "mei", "jun": "juni", "jul": "juli",
    "aug": "agustus", "agu": "agustus", "sep": "september", "okt": "oktober",
    "nov": "november", "dec": "desember", "des": "desember",
}


def _normalize_rri_date(raw: str) -> str | None:
    """
    Handle RRI-specific date formats:
      - "02 Sep 2026, 14:22 WIB"
      - "Rabu, 02 September 2026 14:22 WIB"
      - "2 September 2026"
    Converts abbreviated month to Indonesian full form for normalize_date().
    """
    if not raw:
        return None
    raw = raw.strip()
    # Expand 3-letter month abbreviations → full Indonesian name
    def expand_month(m: re.Match) -> str:
        abbr = m.group(0).lower()
        return _RRI_MONTHS.get(abbr, m.group(0))
    expanded = re.sub(
        r"\b(Jan|Feb|Mar|Apr|May|Mei|Jun|Jul|Aug|Agu|Sep|Okt|Nov|Dec|Des)\b",
        expand_month, raw, flags=re.IGNORECASE
    )
    # Remove "WIB" suffix and comma
    expanded = re.sub(r"\bWIB\b", "", expanded)
    expanded = expanded.replace(",", " ")
    expanded = re.sub(r"\s+", " ", expanded).strip()
    return normalize_date(expanded)


def _build_next_url(base_url: str, current_page: int) -> str:
    """Increment ?page= param on search URL."""
    parsed = urllib.parse.urlparse(base_url)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    # Remove existing page param and set new one
    params.pop("page", None)
    new_query = urllib.parse.urlencode({k: v[0] for k, v in params.items()})
    if new_query:
        new_query += f"&page={current_page + 1}"
    else:
        new_query = f"page={current_page + 1}"
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


def get_article_links(listing_url: str) -> tuple[list[dict], str | None]:
    """
    Scrape RRI search results. Each result card has:
      - a.title  → link + title text
      - span.date or nearby text → date

    Pagination: ?page=N appended to the search URL.
    """
    soup = fetch(listing_url)
    if not soup:
        return [], None

    results = []
    seen = set()

    # Primary: look for links matching article URL pattern
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        # Resolve relative URLs
        full = urllib.parse.urljoin("https://rri.co.id", href)
        if not _ARTICLE_URL_RE.fullmatch(full):
            continue
        if full in seen:
            continue
        seen.add(full)

        # Try to get date from nearest sibling/parent date element
        date_raw = ""
        parent = a.parent
        if parent:
            # Look for date text in nearby elements
            for date_sel in ["[class*='date']", "[class*='time']", "small", "span"]:
                date_el = parent.select_one(date_sel)
                if date_el:
                    txt = date_el.get_text(strip=True)
                    if re.search(r"\d{4}", txt):
                        date_raw = txt
                        break
            if not date_raw:
                # Walk up one level and try again
                grandparent = parent.parent
                if grandparent:
                    for date_sel in ["[class*='date']", "[class*='time']", "small"]:
                        date_el = grandparent.select_one(date_sel)
                        if date_el:
                            txt = date_el.get_text(strip=True)
                            if re.search(r"\d{4}", txt):
                                date_raw = txt
                                break

        pub_at = _normalize_rri_date(date_raw) if date_raw else None
        results.append({"url": full, "published_at": pub_at})

    # Determine current page and build next page URL
    # Parse current page from URL
    parsed = urllib.parse.urlparse(listing_url)
    params = urllib.parse.parse_qs(parsed.query)
    current_page = int(params.get("page", ["1"])[0])

    # If we found results, offer next page; otherwise stop
    next_pg = None
    if results:
        next_pg = _build_next_url(listing_url, current_page)

    return results, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Date — RRI shows date in <li class="date">02 Sep 2026 14:22 WIB</li>
    date_raw = ""
    date_el = soup.select_one("li.date")
    if date_el:
        date_raw = date_el.get_text(separator=" ", strip=True)
    if not date_raw:
        # Fallback: generic selectors
        for sel in ["[class*='date-text']", "time[datetime]", "time"]:
            el = soup.select_one(sel)
            if el:
                date_raw = el.get("datetime", "") or el.get_text(strip=True)
                if date_raw and re.search(r"\d{4}", date_raw):
                    break
    if not date_raw:
        full_text = soup.get_text()
        m = re.search(
            r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des|"
            r"Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)"
            r"\s+\d{4}(?:[\s,]+\d{2}:\d{2})?",
            full_text, re.IGNORECASE
        )
        if m:
            date_raw = m.group(0)

    published_at = _normalize_rri_date(date_raw)

    # Author — RRI uses <li class="author">Oleh - Name,</li>
    author = ""
    for author_el in soup.select("li.author"):
        txt = author_el.get_text(strip=True)
        # Take first author (Oleh/reporter), skip Editor
        if re.search(r"^(oleh|reporter|pewarta)", txt, re.IGNORECASE):
            author = re.sub(r"^(oleh|reporter|pewarta)\s*[-–:]\s*", "",
                            txt, flags=re.I).strip().rstrip(",").strip()
            if author:
                break
    if not author:
        full_text = soup.get_text()
        for pattern in [
            r"Oleh\s*[-–]\s*([^,\n\r]+)",
            r"Reporter\s*:\s*([^\n\r,]+)",
            r"Pewarta\s*:\s*([^\n\r,]+)",
        ]:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                author = m.group(1).strip()
                if author:
                    break

    # Content — RRI puts article body in #news-content
    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    # Tags / categories from breadcrumb or tag links
    tags_els = soup.select(
        "a[href*='/tags/'], a[href*='/tag/'], a.btn-outline-primary, [class*='category'] a"
    )
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    # Image
    image = ""
    img = soup.select_one(
        ".post-content img, .detail-berita img, article img, [class*='featured'] img, [class*='thumb'] img"
    )
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

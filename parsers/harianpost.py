"""
parsers/harianpost.py
Source  : https://harianpost.id/topik/pohuwato/
Listing : article.hentry h2.entry-title a
Article : h1, .entry-content-single / .entry-content, time.entry-date[datetime], .posted-by a

Note: Harianpost.id uses WPMedia theme (same as Hibata.id). Listing is a WordPress
      tag archive (/topik/pohuwato/) so article URLs are at root level: harianpost.id/<slug>/
"""
import json
import re
from parsers.base_parser import (
    fetch, fetch_full_article_content, normalize_date,
    find_next_page, extract_article_links,
)

SOURCE_SLUG = "harianpost"
SOURCE_NAME = "Harianpost.id Pohuwato"

CONTENT_SELECTOR = ".entry-content-single, .entry-content"

_SKIP_PATHS = {
    "/tentang-kami/", "/redaksi/", "/privacy-policy/", "/pedoman-media-siber/",
    "/disclaimer/", "/kontak/", "/indeks-berita/", "/cat/",
}


def get_article_links(listing_url: str) -> tuple[list[dict], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None

    results = []
    seen = set()

    for article in soup.select("article.hentry"):
        a = article.select_one("h2.entry-title a[href]")
        if not a:
            continue
        href = a.get("href", "").strip()
        if not href or href in seen:
            continue
        if any(skip in href for skip in _SKIP_PATHS):
            continue
        seen.add(href)

        time_el = article.select_one("time.entry-date[datetime]")
        date_raw = ""
        if time_el:
            date_raw = time_el.get("datetime", "") or time_el.get_text(strip=True)

        pub_at = normalize_date(date_raw) if date_raw else None
        results.append({"url": href, "published_at": pub_at})

    # Fallback
    if not results:
        raw = extract_article_links(
            soup, listing_url, "h2.entry-title a", domain_hint="harianpost.id"
        )
        for l in raw:
            if l not in seen and not any(skip in l for skip in _SKIP_PATHS):
                seen.add(l)
                results.append({"url": l, "published_at": None})

    next_pg = find_next_page(soup, listing_url)
    return results, next_pg


def parse_article(url: str) -> dict | None:
    if any(skip in url for skip in _SKIP_PATHS):
        return None

    soup = fetch(url)
    if not soup:
        return None

    # Title
    h1 = soup.select_one("h1.entry-title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Author
    author = ""
    for sel in [".posted-by .author a", "[rel='author']", "[class*='author'] a"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            author = re.sub(r"^(oleh|by)\s*:?\s*", "", el.get_text(strip=True), flags=re.I).strip()
            if author:
                break

    # Date
    date_raw = ""
    for sel in ["time.entry-date.published[datetime]", "time.entry-date[datetime]",
                "time[datetime]", "time"]:
        el = soup.select_one(sel)
        if el:
            date_raw = el.get("datetime", "") or el.get_text(strip=True)
            if date_raw:
                break
    published_at = normalize_date(date_raw) if date_raw else None

    # Content
    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    # Tags
    tags_els = soup.select("[rel='tag'], a[href*='/tag/'], a[href*='/topik/']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    # Image
    image = ""
    img = soup.select_one(".wp-post-image, [class*='featured'] img, .entry-content img")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

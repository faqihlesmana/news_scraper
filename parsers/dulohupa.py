"""
parsers/dulohupa.py
Source: https://dulohupa.id/berita/berita-daerah/berita-gorontalo/kabupaten-pohuwato/
Listing:  h2.entry-title a
Article:  h1.entry-title, [class*='entry-content'], time[datetime], [class*='author']
"""
import json, re
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date, find_next_page, extract_article_links

SOURCE_SLUG = "dulohupa"
SOURCE_NAME = "Dulohupa"

CONTENT_SELECTOR = "[class*='entry-content']"

# Paths to skip – they're not articles
_SKIP_PATHS = {"/tentang-kami/", "/indeks-berita/", "/privacy-policy/", "/disclaimer/"}


def get_article_links(listing_url: str) -> tuple[list[str], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None
    raw = extract_article_links(soup, listing_url,
                                 "h2.entry-title a",
                                 domain_hint="dulohupa.id")
    links = [l for l in raw if not any(skip in l for skip in _SKIP_PATHS)]
    next_pg = find_next_page(soup, listing_url)
    return links, next_pg


def parse_article(url: str) -> dict | None:
    if any(skip in url for skip in _SKIP_PATHS):
        return None
    soup = fetch(url)
    if not soup:
        return None

    h1 = soup.select_one("h1.entry-title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    author = ""
    for sel in ["[class*='author']", "[rel='author']"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            author = re.sub(r"^(oleh|by)\s*:?\s*", "",
                            el.get_text(strip=True), flags=re.I).strip()
            break

    date_raw = ""
    el = soup.select_one("time[datetime]") or soup.select_one("time")
    if el:
        date_raw = el.get("datetime") or el.get_text(strip=True)
    published_at = normalize_date(date_raw)

    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    tags_els = soup.select("[rel='tag']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    image = ""
    img = soup.select_one("[class*='featured'] img, .entry-content img")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

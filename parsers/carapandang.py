"""
parsers/carapandang.py
Source: https://gorontalo.carapandang.com/news/category/kabupaten-pohuwato
Listing:  h3.entry-title.td-module-title a
Article:  h1 (first), [class*='td-post-content'], time[datetime], [class*='author']
"""
import json, re
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date, find_next_page, extract_article_links

SOURCE_SLUG = "carapandang"
SOURCE_NAME = "Cara Pandang Pohuwato"

CONTENT_SELECTOR = "[class*='td-post-content']"


def get_article_links(listing_url: str) -> tuple[list[str], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None
    links = extract_article_links(soup, listing_url,
                                   "h3.td-module-title a, h3.entry-title a",
                                   domain_hint="carapandang.com")
    links = [l for l in links if "/news/read/" in l or re.search(r"-\d+$", l.rstrip("/"))]
    next_pg = find_next_page(soup, listing_url)
    return links, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    # carapandang article title is in h1.entry-title inside header.td-post-title
    h1 = soup.select_one("h1.entry-title, .td-post-title h1, header.td-post-title h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = re.sub(r"^(?:Carapandang|CaraPandang)\s*\|\s*", "", og["content"]).strip()
    if not title and soup.title:
        title = re.sub(r"^(?:Carapandang|CaraPandang)\s*\|\s*", "", soup.title.get_text(strip=True)).strip()

    author = ""
    for sel in ["[class*='author']", ".td-post-author-name", "[rel='author']"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            author = re.sub(r"^(penulis|oleh|by)\s*:?\s*", "",
                            el.get_text(strip=True), flags=re.I).strip()
            author = author.rstrip("-").strip()
            break

    date_raw = ""
    el = soup.select_one("time[datetime]") or soup.select_one("time") or soup.select_one("[class*='date']")
    if el:
        date_raw = el.get("datetime") or el.get_text(strip=True)
    published_at = normalize_date(date_raw)

    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    tags_els = soup.select("[class*='td-tags'] a, [rel='tag']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    image = ""
    img = soup.select_one("[class*='td-post-featured'] img, article img")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

"""
parsers/gopos.py
Source: https://gopos.id/category/daerah/pohuwato-daerah/
Listing:  h2.jeg_post_title a
Article:  h1.jeg_post_title, [class*='entry-content'] p, [class*='date'], [class*='author']
Tags:     [rel='tag']
"""
import json, re
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date, find_next_page, extract_article_links

SOURCE_SLUG = "gopos"
SOURCE_NAME = "GoPos"

CONTENT_SELECTOR = "[class*='entry-content']"


def get_article_links(listing_url: str) -> tuple[list[str], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None
    links = extract_article_links(soup, listing_url,
                                   "h2.jeg_post_title a, h3.jeg_post_title a",
                                   domain_hint="gopos.id")
    next_pg = find_next_page(soup, listing_url)
    return links, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    h1 = soup.select_one("h1.jeg_post_title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    author = ""
    el = soup.select_one("[class*='author']")
    if el:
        author = re.sub(r"^by\s*", "", el.get_text(strip=True), flags=re.I).strip()

    date_raw = ""
    el = soup.select_one("[class*='date']") or soup.select_one("time")
    if el:
        date_raw = el.get("datetime") or el.get_text(strip=True)
    published_at = normalize_date(date_raw)

    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    tags_els = soup.select("[rel='tag']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    image = ""
    img = soup.select_one("[class*='featured'] img, article img, .jeg_post img")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

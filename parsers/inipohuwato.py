"""
parsers/inipohuwato.py
Source: https://inipohuwato.id/
Target Container: "Berita Terbaru"
Pagination: /page/N/
"""
import json
import re
from parsers.base_parser import (
    fetch, fetch_full_article_content, normalize_date
)

SOURCE_SLUG = "inipohuwato"
SOURCE_NAME = "Ini Pohuwato"

CONTENT_SELECTOR = "[class*='entry-content']"


def get_article_links(listing_url: str) -> tuple[list[dict], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None

    # Focus strictly on 'Berita Terbaru' section
    heading = soup.find(lambda el: el.name in ["h3", "h2", "span"] and "Berita Terbaru" in el.get_text())
    container = None
    if heading:
        container = heading.find_parent(class_=re.compile(r"jeg_postblock|jeg_block_container|jeg_posts"))
        if not container:
            container = heading.find_parent("div", class_=re.compile(r"jeg_"))

    if not container:
        container = soup

    articles = container.select("article.jeg_post")

    results = []
    seen = set()

    for art in articles:
        a = art.select_one("h3.jeg_post_title a, h2.jeg_post_title a, a[href]")
        if not a:
            continue
        href = a.get("href", "").strip()
        if not href or href in seen or not re.search(r"inipohuwato\.id/[^/]+/", href):
            continue
        seen.add(href)

        # Date from meta (e.g. Juli 20, 2026)
        date_el = art.select_one(".jeg_meta_date a, .jeg_meta_date, time")
        date_raw = date_el.get_text(strip=True) if date_el else ""
        pub_at = normalize_date(date_raw) if date_raw else None

        # Author from meta (e.g. redaksi)
        author_el = art.select_one(".jeg_meta_author a, .jeg_meta_author")
        author = author_el.get_text(strip=True) if author_el else ""
        author = re.sub(r"^(by|oleh)\s*", "", author, flags=re.I).strip()

        # Featured Image (ignore gravatars)
        img_el = art.select_one(".jeg_thumb img")
        img_url = ""
        if img_el:
            img_url = img_el.get("data-src") or img_el.get("src") or ""
            if "gravatar.com" in img_url or "data:image" in img_url:
                img_url = img_el.get("data-src") or ""

        results.append({
            "url": href,
            "published_at": pub_at,
            "author": author,
            "image_url": img_url
        })

    # Determine next page URL (/page/2/, /page/3/, etc.)
    next_a = soup.select_one("a.page_nav.next, a[class*='next']")
    next_pg = None
    if next_a and next_a.get("href") and next_a.get("href") != "#":
        next_pg = next_a.get("href")
    else:
        # Construct /page/N/ URL
        m = re.search(r"/page/(\d+)", listing_url)
        if m:
            curr_pg_num = int(m.group(1))
            next_pg = re.sub(r"/page/\d+/?", f"/page/{curr_pg_num + 1}/", listing_url)
        else:
            base = listing_url.rstrip("/")
            next_pg = f"{base}/page/2/"

    return results, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    h1 = soup.select_one("h1.jeg_post_title") or soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""

    author = ""
    el = soup.select_one(".jeg_meta_author a, .jeg_meta_author, [class*='author']")
    if el:
        author = re.sub(r"^(by|oleh)\s*", "", el.get_text(strip=True), flags=re.I).strip()

    date_raw = ""
    # 1. Try OpenGraph / Schema meta tag in detail HTML
    meta_el = soup.find("meta", property=re.compile(r"published_time|date", re.I)) or soup.find("meta", attrs={"name": re.compile(r"date|publish", re.I)})
    if meta_el and meta_el.get("content"):
        date_raw = meta_el.get("content")

    # 2. Fallback to visible elements
    if not date_raw:
        el = soup.select_one(".jeg_meta_date a, .jeg_meta_date, [class*='date'], time")
        if el:
            date_raw = el.get("datetime") or el.get_text(strip=True)

    published_at = normalize_date(date_raw) if date_raw else None

    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    tags_els = soup.select("[rel='tag'], a[href*='/tag/']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    image = ""
    img = soup.select_one("article img.wp-post-image, [class*='featured'] img, article img")
    if img:
        image = img.get("data-src") or img.get("src") or ""
        if "gravatar.com" in image or "data:image" in image:
            image = img.get("data-src") or ""

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

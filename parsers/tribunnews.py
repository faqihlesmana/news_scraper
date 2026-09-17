"""
parsers/tribunnews.py
Source: https://gorontalo.tribunnews.com/index-news/pohuwato
"""
import json
import re
from parsers.base_parser import (
    fetch, fetch_full_article_content, normalize_date,
    find_next_page, extract_article_links
)

SOURCE_SLUG = "tribunnews"
SOURCE_NAME = "Tribunnews Pohuwato"

CONTENT_SELECTOR = "div.side-article"


def get_article_links(listing_url: str) -> tuple[list[dict], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None

    results = []
    seen = set()

    # Find listicle items on homepage & index-news listing pages
    items = soup.select(".listicle, #latestsection > div, ul.l2 > li, .p1520, [class*='listicle'], div.pt10, li.lsi")

    for item in items:
        a = item.select_one("h3 a[href], h2 a[href], a[href*='gorontalo.tribunnews.com']")
        if not a:
            continue
        href = a.get("href", "").strip()
        if not href or href in seen:
            continue

        # Filter valid news article links
        if not (re.search(r"/\d{4}/\d{2}/\d{2}/", href) or re.search(r"/pohuwato/\d+/", href) or re.search(r"/nasional/\d+/", href)):
            continue

        seen.add(href)

        # Extract date directly from timeago title or text on listing
        time_el = item.select_one("time.timeago, time, [class*='time']")
        date_raw = ""
        if time_el:
            date_raw = time_el.get("title") or time_el.get("datetime") or time_el.get_text(strip=True)

        pub_at = normalize_date(date_raw) if date_raw else None

        results.append({
            "url": href,
            "published_at": pub_at
        })

    # Fallback to standard link extraction if no listicles found
    if not results:
        raw_links = extract_article_links(soup, listing_url,
                                         "[class*='hlover'] h2 a, h2.hlover_title a, li.lsi a, h3 a",
                                         domain_hint="gorontalo.tribunnews.com")
        for l in raw_links:
            if l not in seen and (re.search(r"/\d{4}/\d{2}/\d{2}/", l) or re.search(r"/pohuwato/\d+/", l)):
                seen.add(l)
                results.append({"url": l, "published_at": None})

    next_pg = find_next_page(soup, listing_url)

    # Fallback pagination for Tribunnews root category page
    if not next_pg and "pohuwato" in listing_url and "index-news" not in listing_url:
        next_pg = "https://gorontalo.tribunnews.com/index-news/pohuwato?page=2"

    return results, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    # Title: h1
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else ""
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # Author (Penulis / Editor from credit div)
    author = ""
    for sel in ["div.credit", "div.credit_share", "#penulis", "[class*='reporter']", "[class*='author']"]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            txt = el.get_text(strip=True)
            author = re.sub(r"^(editor|penulis|reporter|oleh)\s*:?\s*", "", txt, flags=re.I).strip()
            if author:
                break

    # Date fallback
    date_raw = ""
    for sel in ["time.timeago", "time[datetime]", "time", "[class*='time']"]:
        el = soup.select_one(sel)
        if el:
            date_raw = el.get("datetime") or el.get("title") or el.get_text(strip=True)
            if date_raw:
                break
    published_at = normalize_date(date_raw) if date_raw else None

    # Content: div.side-article
    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    # Tags
    tags_els = soup.select("a[href*='/tag/'], [class*='tags'] a")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    # Image
    image = ""
    img = soup.select_one(".side-article img, [class*='featured'] img, article img, img[src*='asset.tribunnews.com']")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

"""
parsers/pemerintah_daerah.py
Source: https://prokopim.pohuwatokab.go.id/
Listing: h3.grve-post-title a → /berita/bacaberita/NNNN/slug
Article: h1, [class*='post-content'], date in grve-post-date
"""
import json
import re
import urllib.parse
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date, find_next_page, extract_article_links

SOURCE_SLUG = "pemerintah-daerah"
SOURCE_NAME = "Pemerintah Daerah"

CONTENT_SELECTOR = "[class*='post-content']"


def get_article_links(listing_url: str) -> tuple[list[str], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None
    raw = extract_article_links(soup, listing_url,
                                 "article.grve-isotope-item h3.grve-post-title a, h3.grve-post-title a, h2.grve-post-title a",
                                 domain_hint="pohuwatokab.go.id")
    links = [l for l in raw if "/bacaberita/" in l]
    next_pg = find_next_page(soup, listing_url)
    return links, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    # Title: first h1 with real text content
    title = ""
    for h1 in soup.find_all("h1"):
        txt = h1.get_text(strip=True)
        if len(txt) > 15:
            title = txt
            break

    if not title:
        h3 = soup.select_one("h3.grve-post-title")
        if h3:
            title = h3.get_text(strip=True)

    # Author / Agenda
    author = "Redaksi Prokopim"
    agenda_el = soup.select_one("[class*='date']")
    if agenda_el:
        txt = agenda_el.get_text(strip=True)
        if "Agenda:" in txt:
            agenda_part = txt.split("Agenda:")[-1].split("|")[0].split("-")[0].strip()
            if agenda_part:
                author = f"Prokopim ({agenda_part})"

    # Published date extraction
    published_at = None
    date_el = soup.select_one("[class*='date']") or soup.select_one("time")
    if date_el:
        raw_text = date_el.get_text(strip=True)
        m = re.search(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})|(\d{4}-\d{2}-\d{2})", raw_text)
        if m:
            published_at = normalize_date(m.group(0))
        else:
            published_at = normalize_date(raw_text)

    # Article content
    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    # Tags
    tags_els = soup.select("[rel='tag'], [class*='tag'] a")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    # Featured Image
    image = ""
    img = soup.select_one("img[src*='foto_berita'], .grve-media img, [class*='post-content'] img, [class*='featured'] img")
    if img and img.get("src"):
        image = urllib.parse.urljoin(url, img["src"])

    return {
        "url": url,
        "source_slug": SOURCE_SLUG,
        "source_media": SOURCE_NAME,
        "title": title,
        "author": author,
        "published_at": published_at,
        "content": content,
        "tags": tags,
        "image_url": image,
        "category": None,
        "subcategory": None,
        "confidence": None,
        "reasoning": None,
    }

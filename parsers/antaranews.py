"""
parsers/antaranews.py
Source: https://gorontalo.antaranews.com/kabar-gorontalo/pohuwato
"""
import json
import re
from parsers.base_parser import fetch, fetch_full_article_content, normalize_date, find_next_page, extract_article_links

SOURCE_SLUG  = "antaranews"
SOURCE_NAME  = "Antaranews Pohuwato"

CONTENT_SELECTOR = "[class*='post-content']"


def get_article_links(listing_url: str) -> tuple[list[str], str | None]:
    soup = fetch(listing_url)
    if not soup:
        return [], None
    links = extract_article_links(soup, listing_url,
                                   "h2 a[href], .post-title a[href]", domain_hint="antaranews.com")
    links = [l for l in links if re.search(r"/berita/\d+/", l)]
    next_pg = find_next_page(soup, listing_url)
    return links, next_pg


def parse_article(url: str) -> dict | None:
    soup = fetch(url)
    if not soup:
        return None

    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # --- Date Extraction ---
    date_raw = ""
    for el in soup.find_all(["span", "p", "div", "time"]):
        txt = el.get_text(strip=True)
        if re.search(r"\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}", txt, re.I):
            m = re.search(r"\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}(?:\s+\d{2}:\d{2})?", txt, re.I)
            if m:
                date_raw = m.group(0)
                break

    published_at = normalize_date(date_raw)

    # --- Author Extraction (Pewarta / Editor) ---
    author = ""
    full_text = soup.get_text()
    m_pewarta = re.search(r"Pewarta\s*:\s*([^E\n\r\t]+?)(?:Editor|COPYRIGHT|©|\n|$)", full_text, re.I)
    if m_pewarta:
        author = m_pewarta.group(1).strip()
    else:
        m_editor = re.search(r"Editor\s*:\s*([^\n\r\t]+?)(?:COPYRIGHT|©|\n|$)", full_text, re.I)
        if m_editor:
            author = m_editor.group(1).strip()

    content = fetch_full_article_content(soup, url, CONTENT_SELECTOR)

    tags_els = soup.select("[rel='tag'], a[href*='/tag/']")
    tags = json.dumps([t.get_text(strip=True) for t in tags_els if t.get_text(strip=True)])

    image = ""
    img = soup.select_one("article img, .post-content img, [class*='featured'] img")
    if img:
        image = img.get("src", "")

    return {
        "url": url, "source_slug": SOURCE_SLUG, "source_media": SOURCE_NAME,
        "title": title, "author": author, "published_at": published_at,
        "content": content, "tags": tags, "image_url": image,
        "category": None, "subcategory": None, "confidence": None, "reasoning": None,
    }

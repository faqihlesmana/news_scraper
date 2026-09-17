#!/usr/bin/env python3
"""
scrape_range.py  –  CLI tool to scrape historical news within a date range
Usage:
    python scrape_range.py                                    # Default: April 1 - June 30, 2026
    python scrape_range.py --year 2026                       # April 1 - June 30 of specified year
    python scrape_range.py -s 2026-04-01 -e 2026-06-30        # Specific start and end dates
    python scrape_range.py --source tribunnews                # Scrape only one source slug
    python scrape_range.py --pages 30                         # Max listing pages per source
    python scrape_range.py --no-ai                            # Skip AI categorization & summary
    python scrape_range.py --no-gemini                        # Skip Gemini API
"""

import argparse
import logging
import os
import sys

# Allow running from project root or inside news_scraper
sys.path.insert(0, os.path.dirname(__file__))

from config import LOG_FILE, SOURCES, AI_BACKEND
from database.db import init_db, insert_news, log_scrape, seed_sources, url_exists, update_category
from parsers import get_parser
from services.scraper_engine import _get_ai_processor

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("range_scraper")


def parse_date_str(d_str: str, default_time: str = "00:00:00") -> str:
    """Normalize YYYY-MM-DD input string to 'YYYY-MM-DD HH:MM:SS'."""
    d_str = d_str.strip()
    if len(d_str) == 10:  # YYYY-MM-DD
        return f"{d_str} {default_time}"
    return d_str


def scrape_range_source(
    source: dict,
    start_date_str: str,
    end_date_str: str,
    max_pages: int = 30,
    max_consecutive_older: int = 10,
) -> tuple[list[dict], dict]:
    """
    Scrape single source for articles published between start_date_str and end_date_str.
    Returns (new_articles_list, stats_dict).
    """
    slug = source["slug"]
    name = source["name"]
    url = source["url"]
    parser_slug = source.get("parser", slug)

    parser = get_parser(parser_slug)
    if not parser:
        logger.error(f"[{name}] Parser '{parser_slug}' tidak ditemukan")
        log_scrape(slug, "error", 0, 0, f"No parser for {parser_slug}")
        return [], {"new": 0, "skip": 0, "errors": 0}

    stats = {"new": 0, "skip": 0, "errors": 0}
    new_articles = []
    current_url = url
    page = 0
    consecutive_older = 0
    stop_source = False

    logger.info(f"[{name}] Memulai range scan: {start_date_str} s/d {end_date_str}")

    while current_url and page < max_pages and not stop_source:
        page += 1
        logger.info(f"[{name}] Listing page {page}/{max_pages}: {current_url}")

        try:
            article_links, next_url = parser.get_article_links(current_url)
        except Exception as e:
            logger.error(f"[{name}] Gagal ambil links dari {current_url}: {e}")
            stats["errors"] += 1
            break

        if not article_links:
            logger.info(f"[{name}] Tidak ada link di halaman {page}, stop listing")
            break

        logger.info(f"[{name}] Ditemukan {len(article_links)} link artikel di halaman {page}")

        for item in article_links:
            if isinstance(item, dict):
                art_url = item["url"]
                extra_date = item.get("published_at")
            else:
                art_url = item
                extra_date = None

            # Skip if already exists in DB (continue searching older pages!)
            if url_exists(art_url):
                stats["skip"] += 1
                logger.debug(f"[{name}] Skip (sudah di DB): {art_url[:60]}...")
                continue

            try:
                article = parser.parse_article(art_url)
            except Exception as e:
                logger.error(f"[{name}] Parse error {art_url}: {e}")
                stats["errors"] += 1
                continue

            if not article or not article.get("title"):
                logger.warning(f"[{name}] Artikel kosong/no title: {art_url}")
                stats["errors"] += 1
                continue

            if extra_date and not article.get("published_at"):
                article["published_at"] = extra_date

            pub_at = article.get("published_at")

            # Date Range Check
            if pub_at:
                if pub_at < start_date_str:
                    consecutive_older += 1
                    logger.info(
                        f"[{name}] ⏳ Berita lebih tua dari {start_date_str} ({pub_at}) -> "
                        f"consecutive={consecutive_older}/{max_consecutive_older}"
                    )
                    if consecutive_older >= max_consecutive_older:
                        logger.info(
                            f"[{name}] 🛑 Mencapai {consecutive_older} artikel lebih tua secara berturut-turut. "
                            f"Menghentikan scan untuk {name}."
                        )
                        stop_source = True
                        break
                    continue
                elif pub_at > end_date_str:
                    stats["skip"] += 1
                    logger.info(f"[{name}] ⏩ Skip berita lebih baru dari {end_date_str} ({pub_at})")
                    consecutive_older = 0
                    continue
                else:
                    # Inside target range!
                    consecutive_older = 0
            else:
                logger.warning(f"[{name}] Tanggal terbit tidak terdeteksi untuk: {art_url}")

            # Save to DB
            try:
                saved = insert_news(article)
                if saved:
                    stats["new"] += 1
                    new_articles.append(article)
                    pub_info = pub_at if pub_at else "No Date"
                    logger.info(f"[{name}] ✓ Simpan [{pub_info}]: {article['title'][:60]}")
                else:
                    stats["skip"] += 1
            except Exception as e:
                logger.error(f"[{name}] DB error {art_url}: {e}")
                stats["errors"] += 1

        current_url = next_url

    log_scrape(slug, "success", stats["new"], stats["skip"])
    return new_articles, stats


def main():
    parser = argparse.ArgumentParser(description="Pohuwato Historical Date-Range News Scraper")
    parser.add_argument("--start-date", "-s", type=str, default=None,
                        help="Start date YYYY-MM-DD (default: 2026-04-01)")
    parser.add_argument("--end-date", "-e", type=str, default=None,
                        help="End date YYYY-MM-DD (default: 2026-06-30)")
    parser.add_argument("--year", "-y", type=int, default=None,
                        help="Year shortcut (e.g. 2026 sets 2026-04-01 to 2026-06-30)")
    parser.add_argument("--source", type=str, default=None,
                        help="Scrape only this source slug (e.g. tribunnews)")
    parser.add_argument("--pages", type=int, default=30,
                        help="Max listing pages per source (default: 30)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI categorization & summarization")
    parser.add_argument("--no-gemini", action="store_true",
                        help="Skip Gemini API categorization")

    args = parser.parse_args()

    # Determine year & dates
    year = args.year if args.year else 2026
    start_date = args.start_date if args.start_date else f"{year}-04-01"
    end_date = args.end_date if args.end_date else f"{year}-06-30"

    start_date_str = parse_date_str(start_date, "00:00:00")
    end_date_str = parse_date_str(end_date, "23:59:59")

    # Init DB
    init_db()
    seed_sources(SOURCES)

    source_slugs = [args.source] if args.source else None
    use_ai = not args.no_ai
    use_gemini = not args.no_gemini

    logger.info("=" * 70)
    logger.info(f"START HISTORICAL SCRAPER")
    logger.info(f"Target Range : {start_date_str} s/d {end_date_str}")
    logger.info(f"Max Pages    : {args.pages}")
    logger.info(f"AI Processing: {'Enabled' if use_ai else 'Disabled'}")
    logger.info("=" * 70)

    total = {"new": 0, "skip": 0, "errors": 0, "processed": 0}
    all_new_arts = []

    # Phase 1: Range Scraping
    for source in SOURCES:
        if not source.get("active", True):
            continue
        if source_slugs and source["slug"] not in source_slugs:
            continue

        try:
            new_arts, stats = scrape_range_source(
                source,
                start_date_str=start_date_str,
                end_date_str=end_date_str,
                max_pages=args.pages,
            )
            all_new_arts.extend(new_arts)
            for k in ("new", "skip", "errors"):
                total[k] += stats.get(k, 0)
            logger.info(
                f"[{source['name']}] RANGE FINISHED → baru={stats['new']}, "
                f"skip={stats['skip']}, error={stats['errors']}"
            )
        except Exception as e:
            logger.error(f"[{source['name']}] Fatal: {e}", exc_info=True)
            total["errors"] += 1

    logger.info(
        f"\nPhase 1 Range Scraping Selesai: {total['new']} artikel baru tersimpan dalam rentang, "
        f"{total['skip']} di-skip, {total['errors']} error."
    )

    # Phase 2: AI Processing
    if not use_ai or not all_new_arts:
        if use_ai and not all_new_arts:
            logger.info("Tidak ada artikel baru dalam rentang — AI tidak dipanggil.")
        print(f"\n✅ Finished: {total['new']} new | {total['skip']} skipped | {total['errors']} errors | 0 AI processed")
        return total

    if not use_gemini:
        from services.ollama_processor import process_article
        backend_name = "ollama (qwen)"
    else:
        process_article = _get_ai_processor()
        backend_name = AI_BACKEND

    logger.info(f"\n{'='*70}")
    logger.info(f"PHASE 2: AI Processing {len(all_new_arts)} artikel baru dalam rentang")
    logger.info(f"  Backend: {backend_name}")
    logger.info(f"{'='*70}")

    for i, art in enumerate(all_new_arts, 1):
        title = art.get("title", "")
        content = art.get("content", "")
        url = art.get("url", "")

        logger.info(f"[AI {i}/{len(all_new_arts)}] {title[:55]}")

        try:
            result = process_article(title, content)
            update_category(url, result)
            total["processed"] += 1
            logger.info(
                f"  → {result['category']} / {result['subcategory']} "
                f"({result['confidence']:.0%}) | summary={len(result.get('summary',''))} chars"
            )
        except Exception as e:
            logger.error(f"  → Gagal proses AI: {e}")

    print(
        f"\n✅ Range Scraping completed: {total['new']} new | {total['skip']} skipped | "
        f"{total['errors']} errors | {total['processed']} AI processed"
    )

    return total


if __name__ == "__main__":
    main()

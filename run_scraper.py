#!/usr/bin/env python3
"""
run_scraper.py  –  CLI entry point for cron / manual execution
Usage:
    python run_scraper.py                     # Scrape all sources
    python run_scraper.py --source antaranews # Scrape one source
    python run_scraper.py --no-gemini         # Skip AI categorization
    python run_scraper.py --pages 10          # Max pages per source
"""
import argparse
import logging
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from config import LOG_FILE
from database.db import init_db
from services.scraper_engine import scrape_all

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def main():
    parser = argparse.ArgumentParser(description="Pohuwato News Scraper")
    parser.add_argument("--source", type=str, default=None,
                        help="Scrape only this source slug (e.g. pemerintah-daerah)")
    parser.add_argument("--no-gemini", action="store_true",
                        help="Skip Gemini API categorization")
    parser.add_argument("--pages", type=int, default=3,
                        help="Max listing pages per source (default: 3)")
    parser.add_argument("--start-date", "-s", type=str, default=None,
                        help="Start date YYYY-MM-DD for date filtering")
    parser.add_argument("--end-date", "-e", type=str, default=None,
                        help="End date YYYY-MM-DD for date filtering")
    args = parser.parse_args()

    # Init DB
    init_db()

    source_slugs = [args.source] if args.source else None
    use_gemini   = not args.no_gemini

    if args.start_date or args.end_date:
        from scrape_range import scrape_range_source, parse_date_str
        from config import SOURCES
        from database.db import seed_sources

        seed_sources(SOURCES)
        start_date_str = parse_date_str(args.start_date or "2026-04-01", "00:00:00")
        end_date_str = parse_date_str(args.end_date or "2026-06-30", "23:59:59")
        max_pages = args.pages if args.pages != 3 else 30

        stats = {"new": 0, "skip": 0, "errors": 0, "processed": 0}
        all_new = []
        for source in SOURCES:
            if not source.get("active", True):
                continue
            if source_slugs and source["slug"] not in source_slugs:
                continue
            new_arts, s_stats = scrape_range_source(source, start_date_str, end_date_str, max_pages=max_pages)
            all_new.extend(new_arts)
            for k in ("new", "skip", "errors"):
                stats[k] += s_stats.get(k, 0)

        if not args.no_gemini:
            from services.scraper_engine import _get_ai_processor, update_category
            proc = _get_ai_processor()
            for art in all_new:
                try:
                    res = proc(art["title"], art["content"])
                    update_category(art["url"], res)
                    stats["processed"] += 1
                except Exception:
                    pass
        else:
            from services.ollama_processor import process_article
            from database.db import update_category
            for art in all_new:
                try:
                    res = process_article(art["title"], art["content"])
                    update_category(art["url"], res)
                    stats["processed"] += 1
                except Exception:
                    pass

        print(f"\n✅ Range Scraping completed: {stats['new']} new | {stats['skip']} skipped | {stats['errors']} errors | {stats['processed']} AI processed")
    else:
        stats = scrape_all(
            max_pages=args.pages,
            use_gemini=use_gemini,
            source_slugs=source_slugs,
        )
        print(f"\n✅ Scraping completed: {stats['new']} new | {stats['skip']} skipped | {stats['errors']} errors")


if __name__ == "__main__":
    main()

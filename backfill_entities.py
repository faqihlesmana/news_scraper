#!/usr/bin/env python3
"""
backfill_entities.py

Script untuk mengekstrak Event Masal & Lembaga/Perusahaan dari seluruh berita
yang sudah tersimpan di database (Backfill data lama).

Usage:
    python backfill_entities.py
    python backfill_entities.py --limit 50
    python backfill_entities.py --backend ollama
    python backfill_entities.py --backend gemini
"""
import argparse
import logging
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))

from database.db import get_db, init_db, save_extracted_entities_with_dedup
from services.entity_extractor import extract_entities_from_article

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("backfill")


def run_backfill(limit: int = None, backend: str = None):
    init_db()

    with get_db() as conn:
        query = "SELECT id, title, content, published_at, scraped_at FROM news ORDER BY id ASC"
        if limit:
            query += f" LIMIT {limit}"
        articles = conn.execute(query).fetchall()

    total = len(articles)
    logger.info(f"🚀 Memulai backfill untuk {total} berita...")

    success_count = 0
    total_events = 0
    total_companies = 0

    for idx, art in enumerate(articles, 1):
        news_id = art["id"]
        title = art["title"] or ""
        content = art["content"] or ""
        pub_date = art["published_at"] or art["scraped_at"]

        if not title:
            continue

        logger.info(f"[{idx}/{total}] Memproses: {title[:60]}...")
        try:
            res = extract_entities_from_article(title, content, backend=backend)
            events = res.get("events", [])
            companies = res.get("companies", [])

            save_extracted_entities_with_dedup(
                news_id=news_id,
                events=events,
                companies=companies,
                published_at=pub_date
            )

            total_events += len(events)
            total_companies += len(companies)
            success_count += 1
            logger.info(f"  ✓ {len(events)} event, {len(companies)} lembaga ditemukan")
        except Exception as e:
            logger.error(f"  ✗ Error memproses berita ID {news_id}: {e}")

        time.sleep(0.1)

    logger.info(f"\n{'='*50}")
    logger.info(f"✅ Backfill Selesai! Berhasil memproses {success_count}/{total} berita.")
    logger.info(f"   Total Event diekstrak: {total_events}")
    logger.info(f"   Total Lembaga diekstrak: {total_companies}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill extraction for events and companies")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of articles to process")
    parser.add_argument("--backend", type=str, default=None, choices=["gemini", "ollama", "hybrid"], help="AI backend")
    args = parser.parse_args()

    run_backfill(limit=args.limit, backend=args.backend)

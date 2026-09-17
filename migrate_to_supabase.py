#!/usr/bin/env python3
"""
migrate_to_supabase.py
Memindahkan seluruh data lokal SQLite (news_scraper.db) ke Supabase PostgreSQL.

Penggunaan:
  python3 migrate_to_supabase.py --url "postgresql://postgres.[ref]:[pass]@[host]:6543/postgres?sslmode=require"
atau cukup:
  python3 migrate_to_supabase.py (jika DATABASE_URL sudah diisi di .env)
"""

import sys
import os
import argparse
import sqlite3
from pathlib import Path

# Load config jika ada
try:
    from config import DB_PATH, DATABASE_URL
except ImportError:
    DB_PATH = Path("data/news_scraper.db")
    DATABASE_URL = os.getenv("DATABASE_URL", "")


def get_pg_connection(db_url: str):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return conn


def migrate(sqlite_path: Path, pg_url: str, dry_run: bool = False):
    if not sqlite_path.exists():
        print(f"[ERROR] File SQLite tidak ditemukan di: {sqlite_path}")
        sys.exit(1)

    print(f"[1/4] Membaca database lokal: {sqlite_path}")
    sq_conn = sqlite3.connect(str(sqlite_path))
    sq_conn.row_factory = sqlite3.Row

    # Hitung total data lokal
    tables = [
        "sources", "news", "scrape_logs", "article_feedback",
        "events", "event_news_references", "companies", "company_news_references"
    ]
    counts = {}
    for t in tables:
        try:
            cnt = sq_conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            counts[t] = cnt
        except Exception:
            counts[t] = 0

    print("\n--- RINGKASAN DATA LOKAL (SQLite) ---")
    for t, cnt in counts.items():
        print(f"  • {t:<24}: {cnt:>5} baris")
    print("--------------------------------------\n")

    if dry_run:
        print("[DRY-RUN] Selesai membaca data. Tidak ada data yang dikirim ke Supabase.")
        sq_conn.close()
        return

    print(f"[2/4] Menghubungkan ke Supabase PostgreSQL...")
    try:
        pg_conn = get_pg_connection(pg_url)
        print("  ✓ Berhasil terhubung ke Supabase!")
    except Exception as e:
        print(f"[ERROR] Gagal koneksi ke Supabase: {e}")
        sys.exit(1)

    pg_cursor = pg_conn.cursor()

    print("\n[3/4] Mentransfer data ke Supabase...")

    # 1. SOURCES
    sources = sq_conn.execute("SELECT * FROM sources").fetchall()
    if sources:
        for s in sources:
            pg_cursor.execute("""
                INSERT INTO sources (id, slug, name, url, active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    url = EXCLUDED.url,
                    active = EXCLUDED.active
            """, (s["id"], s["slug"], s["name"], s["url"], s["active"], s["created_at"]))
        print(f"  ✓ Sources: {len(sources)} baris tersinkron")

    # 2. NEWS
    news_rows = sq_conn.execute("SELECT * FROM news").fetchall()
    if news_rows:
        batch_size = 200
        inserted_news = 0
        for i in range(0, len(news_rows), batch_size):
            batch = news_rows[i:i + batch_size]
            for n in batch:
                pg_cursor.execute("""
                    INSERT INTO news (
                        id, url, source_slug, source_media, title, author,
                        published_at, content, summary, tags, image_url,
                        category, subcategory, exp_category, exp_subcategory,
                        confidence, reasoning, is_relevant, scraped_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (url) DO UPDATE SET
                        title = EXCLUDED.title,
                        category = EXCLUDED.category,
                        subcategory = EXCLUDED.subcategory,
                        exp_category = EXCLUDED.exp_category,
                        exp_subcategory = EXCLUDED.exp_subcategory,
                        confidence = EXCLUDED.confidence,
                        reasoning = EXCLUDED.reasoning,
                        summary = EXCLUDED.summary,
                        is_relevant = EXCLUDED.is_relevant
                """, (
                    n["id"], n["url"], n["source_slug"], n["source_media"], n["title"], n["author"],
                    n["published_at"], n["content"], n["summary"], n["tags"], n["image_url"],
                    n["category"], n["subcategory"], n["exp_category"], n["exp_subcategory"],
                    n["confidence"], n["reasoning"], n["is_relevant"], n["scraped_at"]
                ))
            inserted_news += len(batch)
            print(f"    ... Mengunggah berita: {inserted_news}/{len(news_rows)}", end="\r")
        print(f"  ✓ News: {len(news_rows)} baris tersinkron        ")

    # 3. SCRAPE LOGS
    logs = sq_conn.execute("SELECT * FROM scrape_logs").fetchall()
    if logs:
        for l in logs:
            pg_cursor.execute("""
                INSERT INTO scrape_logs (id, source_slug, run_at, status, articles_new, articles_skip, error_msg)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (l["id"], l["source_slug"], l["run_at"], l["status"], l["articles_new"], l["articles_skip"], l["error_msg"]))
        print(f"  ✓ Scrape Logs: {len(logs)} baris tersinkron")

    # 4. ARTICLE FEEDBACK
    feedbacks = sq_conn.execute("SELECT * FROM article_feedback").fetchall()
    if feedbacks:
        for fb in feedbacks:
            pg_cursor.execute("""
                INSERT INTO article_feedback (
                    id, article_id, user_identifier, user_ip, flag,
                    rec_category, rec_subcategory, rec_exp_category, rec_exp_subcategory, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                fb["id"], fb["article_id"], fb["user_identifier"], fb["user_ip"], fb["flag"],
                fb["rec_category"], fb["rec_subcategory"], fb["rec_exp_category"], fb["rec_exp_subcategory"],
                fb["created_at"]
            ))
        print(f"  ✓ Article Feedback: {len(feedbacks)} baris tersinkron")

    # 5. EVENTS
    events = sq_conn.execute("SELECT * FROM events").fetchall()
    if events:
        for ev in events:
            pg_cursor.execute("""
                INSERT INTO events (id, nama_event, triwulan, tahun, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nama_event, triwulan, tahun) DO UPDATE SET
                    id = EXCLUDED.id
            """, (ev["id"], ev["nama_event"], ev["triwulan"], ev["tahun"], ev["created_at"]))
        print(f"  ✓ Events: {len(events)} baris tersinkron")

    # 6. EVENT REFERENCES
    ev_refs = sq_conn.execute("SELECT * FROM event_news_references").fetchall()
    if ev_refs:
        for r in ev_refs:
            pg_cursor.execute("""
                INSERT INTO event_news_references (id, event_id, news_id, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (event_id, news_id) DO NOTHING
            """, (r["id"], r["event_id"], r["news_id"], r["created_at"]))
        print(f"  ✓ Event References: {len(ev_refs)} baris tersinkron")

    # 7. COMPANIES
    comps = sq_conn.execute("SELECT * FROM companies").fetchall()
    if comps:
        for c in comps:
            pg_cursor.execute("""
                INSERT INTO companies (id, nama_lembaga, triwulan, tahun, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (nama_lembaga, triwulan, tahun) DO UPDATE SET
                    id = EXCLUDED.id
            """, (c["id"], c["nama_lembaga"], c["triwulan"], c["tahun"], c["created_at"]))
        print(f"  ✓ Companies: {len(comps)} baris tersinkron")

    # 8. COMPANY REFERENCES
    comp_refs = sq_conn.execute("SELECT * FROM company_news_references").fetchall()
    if comp_refs:
        for r in comp_refs:
            pg_cursor.execute("""
                INSERT INTO company_news_references (id, company_id, news_id, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (company_id, news_id) DO NOTHING
            """, (r["id"], r["company_id"], r["news_id"], r["created_at"]))
        print(f"  ✓ Company References: {len(comp_refs)} baris tersinkron")

    # Commit semua transaksi
    pg_conn.commit()

    print("\n[4/4] Memperbarui Sequence ID PostgreSQL...")
    seq_tables = [
        ("sources", "id"), ("news", "id"), ("scrape_logs", "id"),
        ("article_feedback", "id"), ("events", "id"), ("event_news_references", "id"),
        ("companies", "id"), ("company_news_references", "id")
    ]
    for tbl, col in seq_tables:
        pg_cursor.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{tbl}', '{col}'),
                COALESCE((SELECT MAX({col}) FROM {tbl}), 1)
            );
        """)
    pg_conn.commit()

    pg_cursor.close()
    pg_conn.close()
    sq_conn.close()

    print("\n🎉 MIGRASI SUKSES! Seluruh data lokal telah tersimpan rapi di Supabase.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrasi database SQLite news_scraper ke Supabase PostgreSQL")
    parser.add_argument("--url", default=DATABASE_URL, help="Supabase PostgreSQL Connection URI")
    parser.add_argument("--db-path", default=str(DB_PATH), help="Path file SQLite lokal")
    parser.add_argument("--dry-run", action="store_true", help="Hanya baca data tanpa menulis ke Supabase")

    args = parser.parse_args()

    if not args.dry_run and not args.url:
        print("[ERROR] DATABASE_URL belum ditentukan!")
        print("Gunakan parameter --url atau isi DATABASE_URL di file .env")
        print('Contoh: python3 migrate_to_supabase.py --url "postgresql://postgres:password@...pooler.supabase.com:6543/postgres"')
        sys.exit(1)

    migrate(Path(args.db_path), args.url, dry_run=args.dry_run)

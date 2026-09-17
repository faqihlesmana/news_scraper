import re
import logging
import sqlite3
from contextlib import contextmanager
from config import DB_PATH, DATABASE_URL

logger = logging.getLogger(__name__)

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

IS_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith(("postgres://", "postgresql://")))

if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import DictCursor

    _PG_URL = DATABASE_URL
    if _PG_URL.startswith("postgres://"):
        _PG_URL = "postgresql://" + _PG_URL[len("postgres://"):]


class PostgresConnectionWrapper:
    """Wrapper di atas koneksi psycopg2 agar kompatibel dengan sintaks query SQLite."""

    def __init__(self, pg_conn):
        self._conn = pg_conn
        self._cur = pg_conn.cursor(cursor_factory=DictCursor)

    def _adapt_sql(self, sql: str, params=None) -> str:
        if params is not None and isinstance(params, dict):
            # Ubah :slug -> %(slug)s
            sql = re.sub(r':([a-zA-Z_][a-zA-Z0-9_]*)', r'%(\1)s', sql)
        elif params is not None and isinstance(params, (list, tuple)):
            # Ubah ? -> %s
            sql = sql.replace("?", "%s")
        return sql

    def execute(self, sql: str, params=None):
        if "BEGIN IMMEDIATE" in sql.upper():
            return self._cur
        sql = self._adapt_sql(sql, params)
        if params is not None:
            self._cur.execute(sql, params)
        else:
            self._cur.execute(sql)
        return self._cur

    def executescript(self, sql: str):
        self._cur.execute(sql)
        return self._cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            pass


def get_connection():
    if IS_POSTGRES:
        conn = psycopg2.connect(_PG_URL)
        return PostgresConnectionWrapper(conn)
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    if IS_POSTGRES:
        logger.info("[DB] Supabase PostgreSQL active. Skema dikelola via database/supabase_schema.sql.")
        return

    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            slug       TEXT UNIQUE NOT NULL,
            name       TEXT NOT NULL,
            url        TEXT NOT NULL,
            active     INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS news (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            url           TEXT UNIQUE NOT NULL,
            source_slug   TEXT NOT NULL REFERENCES sources(slug),
            source_media  TEXT NOT NULL,
            title         TEXT,
            author        TEXT,
            published_at  TEXT,
            content       TEXT,
            summary       TEXT,          -- Ringkasan 2-3 kalimat dari Ollama
            tags          TEXT,          -- JSON array as string
            image_url     TEXT,
            category      TEXT,          -- PDRB Lapangan Usaha Main Category
            subcategory   TEXT,          -- PDRB Lapangan Usaha Sub Category
            exp_category  TEXT,          -- PDRB Pengeluaran Main Category
            exp_subcategory TEXT,        -- PDRB Pengeluaran Sub Category
            confidence    REAL,
            reasoning     TEXT,
            is_relevant   INTEGER DEFAULT 0,
            scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scrape_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source_slug TEXT NOT NULL,
            run_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            status      TEXT,            -- 'success' | 'error'
            articles_new INTEGER DEFAULT 0,
            articles_skip INTEGER DEFAULT 0,
            error_msg   TEXT
        );

        CREATE TABLE IF NOT EXISTS article_feedback (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id          INTEGER NOT NULL REFERENCES news(id),
            user_identifier     TEXT NOT NULL,
            user_ip             TEXT,
            flag                INTEGER NOT NULL, -- 0 = Sip (Benar), 1 = Ga Sip (Salah)
            rec_category        TEXT,
            rec_subcategory     TEXT,
            rec_exp_category    TEXT,
            rec_exp_subcategory TEXT,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- ══ TABEL EVENT & LEMBAGA (TRIWULANAN) ══
        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_event  TEXT NOT NULL,
            triwulan    TEXT NOT NULL, -- Q1, Q2, Q3, Q4
            tahun       INTEGER NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nama_event, triwulan, tahun)
        );

        CREATE TABLE IF NOT EXISTS event_news_references (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id   INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            news_id    INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(event_id, news_id)
        );

        CREATE TABLE IF NOT EXISTS companies (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_lembaga TEXT NOT NULL,
            triwulan     TEXT NOT NULL, -- Q1, Q2, Q3, Q4
            tahun        INTEGER NOT NULL,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nama_lembaga, triwulan, tahun)
        );

        CREATE TABLE IF NOT EXISTS company_news_references (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            news_id    INTEGER NOT NULL REFERENCES news(id) ON DELETE CASCADE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id, news_id)
        );

        CREATE INDEX IF NOT EXISTS idx_news_url         ON news(url);
        CREATE INDEX IF NOT EXISTS idx_news_source      ON news(source_slug);
        CREATE INDEX IF NOT EXISTS idx_news_published   ON news(published_at);
        CREATE INDEX IF NOT EXISTS idx_news_category    ON news(category);
        CREATE INDEX IF NOT EXISTS idx_logs_source      ON scrape_logs(source_slug);
        CREATE INDEX IF NOT EXISTS idx_fb_article       ON article_feedback(article_id);
        CREATE INDEX IF NOT EXISTS idx_fb_user          ON article_feedback(user_identifier);
        CREATE INDEX IF NOT EXISTS idx_events_q_y       ON events(tahun, triwulan);
        CREATE INDEX IF NOT EXISTS idx_companies_q_y    ON companies(tahun, triwulan);
        """
        )
        # Migration: tambah kolom jika DB lama belum punya
        for col_def in ["summary TEXT", "exp_category TEXT", "exp_subcategory TEXT", "is_relevant INTEGER DEFAULT 0"]:
            try:
                conn.execute(f"ALTER TABLE news ADD COLUMN {col_def}")
                conn.commit()
            except Exception:
                pass  # Kolom sudah ada
    print(f"[DB] Database initialized at {DB_PATH}")




def url_exists(url: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone()
        return row is not None


def insert_news(article: dict) -> bool:
    """Insert article. Returns True if new, False if duplicate."""
    if url_exists(article["url"]):
        return False
    with get_db() as conn:
        conn.execute("""
            INSERT INTO news (url, source_slug, source_media, title, author,
                              published_at, content, summary, tags, image_url,
                              category, subcategory, exp_category, exp_subcategory,
                              confidence, reasoning)
            VALUES (:url, :source_slug, :source_media, :title, :author,
                    :published_at, :content, :summary, :tags, :image_url,
                    :category, :subcategory, :exp_category, :exp_subcategory,
                    :confidence, :reasoning)
        """, {
            "url":             article["url"],
            "source_slug":     article["source_slug"],
            "source_media":    article["source_media"],
            "title":           article.get("title"),
            "author":          article.get("author"),
            "published_at":    article.get("published_at"),
            "content":         article.get("content"),
            "summary":         article.get("summary"),
            "tags":            article.get("tags"),
            "image_url":       article.get("image_url"),
            "category":        article.get("category"),
            "subcategory":     article.get("subcategory"),
            "exp_category":    article.get("exp_category"),
            "exp_subcategory": article.get("exp_subcategory"),
            "confidence":      article.get("confidence"),
            "reasoning":       article.get("reasoning"),
        })
    return True


def log_scrape(source_slug: str, status: str, new: int, skip: int, error: str = None):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO scrape_logs (source_slug, status, articles_new, articles_skip, error_msg)
            VALUES (?, ?, ?, ?, ?)
        """, (source_slug, status, new, skip, error))


def seed_sources(sources: list):
    """Upsert source metadata."""
    with get_db() as conn:
        for s in sources:
            conn.execute("""
                INSERT INTO sources (slug, name, url, active)
                VALUES (:slug, :name, :url, :active)
                ON CONFLICT(slug) DO UPDATE SET
                    name=excluded.name,
                    url=excluded.url,
                    active=excluded.active
            """, {"slug": s["slug"], "name": s["name"],
                  "url": s["url"], "active": 1 if s.get("active", True) else 0})


def update_category(url: str, cat_info: dict) -> None:
    """Update category and summary fields for a single article identified by URL."""
    with get_db() as conn:
        conn.execute("""
            UPDATE news
            SET category=?, subcategory=?, exp_category=?, exp_subcategory=?, confidence=?, reasoning=?, summary=?
            WHERE url=?
        """, (
            cat_info.get("category"),
            cat_info.get("subcategory"),
            cat_info.get("exp_category"),
            cat_info.get("exp_subcategory"),
            cat_info.get("confidence"),
            cat_info.get("reasoning", ""),
            cat_info.get("summary"),
            url,
        ))


def save_article_feedback(article_id: int, user_identifier: str, user_ip: str, flag: int,
                          rec_cat: str = None, rec_subcat: str = None,
                          rec_exp_cat: str = None, rec_exp_subcat: str = None,
                          max_limit: int = 3) -> dict:
    """
    Save feedback for an article with concurrency protection and max limit check (per user).
    flag: 0 = Sip (Benar), 1 = Ga Sip (Salah)
    """
    with get_db() as conn:
        # Acquire write lock immediately to prevent race conditions during rate-limit check
        conn.execute("BEGIN IMMEDIATE")
        
        # Check current submission count for this user on this article
        count_row = conn.execute("""
            SELECT COUNT(*) FROM article_feedback
            WHERE article_id = ? AND user_identifier = ?
        """, (article_id, user_identifier)).fetchone()
        user_count = count_row[0] if count_row else 0
        
        if user_count >= max_limit:
            return {
                "success": False,
                "error": f"Batas maksimal feedback ({max_limit}x) untuk berita ini sudah tercapai.",
                "user_count": user_count
            }
            
        conn.execute("""
            INSERT INTO article_feedback (
                article_id, user_identifier, user_ip, flag,
                rec_category, rec_subcategory, rec_exp_category, rec_exp_subcategory
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article_id, user_identifier, user_ip, flag,
            rec_cat, rec_subcat, rec_exp_cat, rec_exp_subcat
        ))
        
        # Update news category in main database if recommendation is provided for Ga Sip (flag == 1)
        if flag == 1:
            updates = []
            params = []
            if rec_cat:
                updates.append("category = ?")
                params.append(rec_cat)
                updates.append("subcategory = ?")
                params.append(rec_subcat or "Umum")
            if rec_exp_cat:
                updates.append("exp_category = ?")
                params.append(rec_exp_cat)
                updates.append("exp_subcategory = ?")
                params.append(rec_exp_subcat or "Umum")
            
            if updates:
                params.append(article_id)
                conn.execute(f"UPDATE news SET {', '.join(updates)} WHERE id = ?", params)

        # Get updated feedback summary for this article
        stats = conn.execute("""
            SELECT 
                SUM(CASE WHEN flag = 0 THEN 1 ELSE 0 END) as sip,
                SUM(CASE WHEN flag = 1 THEN 1 ELSE 0 END) as gasip
            FROM article_feedback
            WHERE article_id = ?
        """, (article_id,)).fetchone()

        
        # Get latest user flag
        last_flag = conn.execute("""
            SELECT flag FROM article_feedback
            WHERE article_id = ? AND user_identifier = ?
            ORDER BY id DESC LIMIT 1
        """, (article_id, user_identifier)).fetchone()

    return {
        "success": True,
        "sip": stats["sip"] or 0 if stats else 0,
        "gasip": stats["gasip"] or 0 if stats else 0,
        "user_flag": last_flag["flag"] if last_flag else None,
        "user_count": user_count + 1
    }


def get_feedback_by_article_ids(article_ids: list[int], user_identifier: str = None) -> dict:
    """Return feedback summary map {article_id: {sip: X, gasip: Y, user_flag: 0|1|None, user_count: N}}."""
    if not article_ids:
        return {}
    
    placeholders = ",".join("?" for _ in article_ids)
    result = {}
    with get_db() as conn:
        # Get count stats
        rows = conn.execute(f"""
            SELECT 
                article_id,
                SUM(CASE WHEN flag = 0 THEN 1 ELSE 0 END) as sip,
                SUM(CASE WHEN flag = 1 THEN 1 ELSE 0 END) as gasip
            FROM article_feedback
            WHERE article_id IN ({placeholders})
            GROUP BY article_id
        """, article_ids).fetchall()
        
        for r in rows:
            result[r["article_id"]] = {
                "sip": r["sip"] or 0,
                "gasip": r["gasip"] or 0,
                "user_flag": None,
                "user_count": 0
            }
            
        # Get latest global feedback flag per article so all devices see the latest active state
        latest_rows = conn.execute(f"""
            SELECT article_id, flag
            FROM article_feedback
            WHERE id IN (
                SELECT MAX(id) FROM article_feedback
                WHERE article_id IN ({placeholders})
                GROUP BY article_id
            )
        """, article_ids).fetchall()
        
        for l in latest_rows:
            aid = l["article_id"]
            if aid not in result:
                result[aid] = {"sip": 0, "gasip": 0, "user_flag": None, "user_count": 0}
            result[aid]["user_flag"] = l["flag"]
                
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Quarterly Events & Companies (Deduplikasi & Referensi Berita)
# ─────────────────────────────────────────────────────────────────────────────
def save_extracted_entities_with_dedup(news_id: int, events: list[str], companies: list[str], published_at: str):
    """
    Menyimpan Event & Perusahaan dengan deduplikasi otomatis:
    - Jika nama sudah ada di Triwulan & Tahun yang sama, hubungkan news_id ke entitas tersebut.
    - Jika belum ada, buat entitas master baru lalu hubungkan news_id.
    """
    from services.entity_extractor import parse_quarter_and_year
    year, quarter = parse_quarter_and_year(published_at)

    with get_db() as conn:
        # 1. Simpan Events
        for ev in events:
            clean_name = " ".join(ev.split()).strip()
            if not clean_name:
                continue

            conn.execute("""
                INSERT INTO events (nama_event, triwulan, tahun)
                VALUES (?, ?, ?)
                ON CONFLICT(nama_event, triwulan, tahun) DO NOTHING
            """, (clean_name, quarter, year))

            row = conn.execute("""
                SELECT id FROM events WHERE nama_event = ? AND triwulan = ? AND tahun = ?
            """, (clean_name, quarter, year)).fetchone()

            if row:
                conn.execute("""
                    INSERT INTO event_news_references (event_id, news_id)
                    VALUES (?, ?)
                    ON CONFLICT(event_id, news_id) DO NOTHING
                """, (row["id"], news_id))

        # 2. Simpan Companies / Institutions
        for comp in companies:
            clean_name = " ".join(comp.split()).strip()
            if not clean_name:
                continue

            conn.execute("""
                INSERT INTO companies (nama_lembaga, triwulan, tahun)
                VALUES (?, ?, ?)
                ON CONFLICT(nama_lembaga, triwulan, tahun) DO NOTHING
            """, (clean_name, quarter, year))

            row = conn.execute("""
                SELECT id FROM companies WHERE nama_lembaga = ? AND triwulan = ? AND tahun = ?
            """, (clean_name, quarter, year)).fetchone()

            if row:
                conn.execute("""
                    INSERT INTO company_news_references (company_id, news_id)
                    VALUES (?, ?)
                    ON CONFLICT(company_id, news_id) DO NOTHING
                """, (row["id"], news_id))


def get_quarterly_entities(year: int = None, quarter: str = None) -> dict:
    """
    Mengambil data Event dan Perusahaan berdasarkan filter Tahun dan Triwulan,
    termasuk agregasi total referensi berita.
    """
    params = []
    where_clauses = []
    if year:
        where_clauses.append("tahun = ?")
        params.append(year)
    if quarter:
        where_clauses.append("triwulan = ?")
        params.append(quarter)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with get_db() as conn:
        # Events
        ev_query = f"""
            SELECT e.id, e.nama_event, e.triwulan, e.tahun,
                   COUNT(enr.news_id) AS total_references
            FROM events e
            LEFT JOIN event_news_references enr ON e.id = enr.event_id
            {where_sql}
            GROUP BY e.id
            ORDER BY e.tahun DESC, e.triwulan DESC, total_references DESC, e.nama_event ASC
        """
        events = [dict(r) for r in conn.execute(ev_query, params).fetchall()]

        # Companies
        comp_query = f"""
            SELECT c.id, c.nama_lembaga, c.triwulan, c.tahun,
                   COUNT(cnr.news_id) AS total_references
            FROM companies c
            LEFT JOIN company_news_references cnr ON c.id = cnr.company_id
            {where_sql}
            GROUP BY c.id
            ORDER BY c.tahun DESC, c.triwulan DESC, total_references DESC, c.nama_lembaga ASC
        """
        companies = [dict(r) for r in conn.execute(comp_query, params).fetchall()]

    return {"events": events, "companies": companies}


def get_entity_references(entity_type: str, entity_id: int) -> dict:
    """
    Mengambil daftar berita sumber untuk Pop-Up modal referensi.
    """
    with get_db() as conn:
        if entity_type == "event":
            ent_row = conn.execute("SELECT nama_event AS name, triwulan, tahun FROM events WHERE id = ?", (entity_id,)).fetchone()
            if not ent_row:
                return {"entity_name": "", "period": "", "articles": []}

            news_rows = conn.execute("""
                SELECT n.id, n.title, n.published_at, n.source_media, n.url, n.summary, n.category, n.exp_category
                FROM news n
                JOIN event_news_references enr ON n.id = enr.news_id
                WHERE enr.event_id = ?
                ORDER BY n.published_at DESC NULLS LAST
            """, (entity_id,)).fetchall()
        else:
            ent_row = conn.execute("SELECT nama_lembaga AS name, triwulan, tahun FROM companies WHERE id = ?", (entity_id,)).fetchone()
            if not ent_row:
                return {"entity_name": "", "period": "", "articles": []}

            news_rows = conn.execute("""
                SELECT n.id, n.title, n.published_at, n.source_media, n.url, n.summary, n.category, n.exp_category
                FROM news n
                JOIN company_news_references cnr ON n.id = cnr.news_id
                WHERE cnr.company_id = ?
                ORDER BY n.published_at DESC NULLS LAST
            """, (entity_id,)).fetchall()

    return {
        "entity_name": ent_row["name"],
        "period": f"{ent_row['triwulan']} {ent_row['tahun']}",
        "articles": [dict(r) for r in news_rows]
    }

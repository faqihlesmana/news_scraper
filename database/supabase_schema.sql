-- =============================================================================
-- SUPABASE POSTGRESQL SCHEMA FOR POHUWATO NEWS SCRAPER
-- Jalankan skrip ini di Supabase Dashboard -> SQL Editor -> New Query -> Run
-- =============================================================================

-- 1. Tabel Sumber Media (Sources)
CREATE TABLE IF NOT EXISTS sources (
    id         BIGSERIAL PRIMARY KEY,
    slug       TEXT UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    url        TEXT NOT NULL,
    active     INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabel Berita (News)
CREATE TABLE IF NOT EXISTS news (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT UNIQUE NOT NULL,
    source_slug     TEXT NOT NULL REFERENCES sources(slug) ON UPDATE CASCADE,
    source_media    TEXT NOT NULL,
    title           TEXT,
    author          TEXT,
    published_at    TEXT,
    content         TEXT,
    summary         TEXT,          -- Ringkasan 2-3 kalimat dari AI
    tags            TEXT,          -- JSON array as text
    image_url       TEXT,
    category        TEXT,          -- PDRB Lapangan Usaha Main Category
    subcategory     TEXT,          -- PDRB Lapangan Usaha Sub Category
    exp_category    TEXT,          -- PDRB Pengeluaran Main Category
    exp_subcategory TEXT,        -- PDRB Pengeluaran Sub Category
    confidence      REAL,
    reasoning       TEXT,
    is_relevant     INTEGER DEFAULT 0,
    scraped_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indeks Berita
CREATE INDEX IF NOT EXISTS idx_news_url         ON news(url);
CREATE INDEX IF NOT EXISTS idx_news_source      ON news(source_slug);
CREATE INDEX IF NOT EXISTS idx_news_published   ON news(published_at);
CREATE INDEX IF NOT EXISTS idx_news_category    ON news(category);
CREATE INDEX IF NOT EXISTS idx_news_exp_cat     ON news(exp_category);

-- 3. Tabel Log Scraping (Scrape Logs)
CREATE TABLE IF NOT EXISTS scrape_logs (
    id            BIGSERIAL PRIMARY KEY,
    source_slug   TEXT NOT NULL,
    run_at        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status        TEXT,            -- 'success' | 'error'
    articles_new  INTEGER DEFAULT 0,
    articles_skip INTEGER DEFAULT 0,
    error_msg     TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_source ON scrape_logs(source_slug);

-- 4. Tabel Feedback Koreksi Berita (Article Feedback)
CREATE TABLE IF NOT EXISTS article_feedback (
    id                  BIGSERIAL PRIMARY KEY,
    article_id          BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    user_identifier     TEXT NOT NULL,
    user_ip             TEXT,
    flag                INTEGER NOT NULL, -- 0 = Sip (Benar), 1 = Ga Sip (Salah)
    rec_category        TEXT,
    rec_subcategory     TEXT,
    rec_exp_category    TEXT,
    rec_exp_subcategory TEXT,
    created_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fb_article ON article_feedback(article_id);
CREATE INDEX IF NOT EXISTS idx_fb_user    ON article_feedback(user_identifier);

-- 5. Tabel Event Triwulanan (Events)
CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    nama_event  TEXT NOT NULL,
    triwulan    TEXT NOT NULL, -- Q1, Q2, Q3, Q4
    tahun       INTEGER NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nama_event, triwulan, tahun)
);

-- 6. Relasi Referensi Event & Berita
CREATE TABLE IF NOT EXISTS event_news_references (
    id         BIGSERIAL PRIMARY KEY,
    event_id   BIGINT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    news_id    BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_id, news_id)
);

-- 7. Tabel Lembaga / Perusahaan Triwulanan (Companies)
CREATE TABLE IF NOT EXISTS companies (
    id           BIGSERIAL PRIMARY KEY,
    nama_lembaga TEXT NOT NULL,
    triwulan     TEXT NOT NULL, -- Q1, Q2, Q3, Q4
    tahun        INTEGER NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(nama_lembaga, triwulan, tahun)
);

-- 8. Relasi Referensi Lembaga & Berita
CREATE TABLE IF NOT EXISTS company_news_references (
    id         BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    news_id    BIGINT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, news_id)
);

-- Indeks Triwulanan
CREATE INDEX IF NOT EXISTS idx_events_q_y    ON events(tahun, triwulan);
CREATE INDEX IF NOT EXISTS idx_companies_q_y ON companies(tahun, triwulan);

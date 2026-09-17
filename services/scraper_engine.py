"""
services/scraper_engine.py
Orchestrates scraping for all (or selected) sources.

Alur per run:
  Phase 1 — Scraping:
    • Buka halaman listing tiap sumber (maks max_pages halaman)
    • Cek tiap URL: sudah di DB → skip, belum → parse & simpan
    • Artikel yang sudah ada di DB tidak pernah di-scrape ulang

  Phase 2 — AI Processing (Ollama lokal, unlimited):
    • Per artikel baru: 1 call ke Ollama qwen2.5:3b
    • Output: kategori + subkategori + confidence + ringkasan 2-3 kalimat
    • Update DB
"""
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import SOURCES, AI_BACKEND
from parsers import get_parser
from database.db import insert_news, log_scrape, seed_sources, url_exists, update_category

logger = logging.getLogger(__name__)


def process_single_article_hybrid(title: str, content: str) -> dict:
    """
    Pipeline Hibrida per Artikel (Dual PDRB: Lapangan Usaha + Pengeluaran):
      1. Pembersihan & Vectorization otomatis.
      2. Kategorisasi Dual PDRB via Gemini.
      3. Cek relevansi (is_relevant & (category != 'Tidak Relevan' or exp_category != 'Tidak Relevan')).
      4. Jika RELEVAN: Panggil Qwen (Ollama) untuk meringkas 2-3 kalimat.
      5. Jika TIDAK RELEVAN: Skip Qwen, summary = "".
    """
    from services.gemini_categorizer import categorize as gemini_categorize
    from services.ollama_processor import summarize_article as qwen_summarize

    cat_result = gemini_categorize(title, content)

    category        = cat_result.get("category", "Tidak Relevan")
    subcategory     = cat_result.get("subcategory", "Tidak Relevan")
    exp_category    = cat_result.get("exp_category", "Tidak Relevan")
    exp_subcategory = cat_result.get("exp_subcategory", "Tidak Relevan")
    confidence      = cat_result.get("confidence", 0.0)
    is_relevant     = cat_result.get("is_relevant", False)

    summary = ""
    if is_relevant and (category != "Tidak Relevan" or exp_category != "Tidak Relevan"):
        logger.info(f"  [Hybrid] Artikel RELEVAN (Usaha: {category} | Pengeluaran: {exp_category}) → Ringkasan Qwen...")
        try:
            summary = qwen_summarize(title, content)
        except Exception as e:
            logger.error(f"  [Hybrid] Gagal membuat ringkasan Qwen: {e}")
    else:
        logger.info(f"  [Hybrid] Artikel TIDAK RELEVAN → Skip ringkasan Qwen.")

    return {
        "category":        category,
        "subcategory":     subcategory,
        "exp_category":    exp_category,
        "exp_subcategory": exp_subcategory,
        "confidence":      confidence,
        "reasoning":       cat_result.get("reasoning", ""),
        "summary":         summary,
        "is_relevant":     is_relevant,
    }


def _get_ai_processor():
    """Return fungsi process_article yang sesuai backend."""
    if AI_BACKEND in ("hybrid", "gemini"):
        return process_single_article_hybrid
    else:
        from services.ollama_processor import process_article
        return process_article


def scrape_source(source: dict, max_pages: int = 5) -> tuple[list[dict], dict]:
    """
    Scrape satu sumber.
    Returns (new_articles_list, stats_dict).

    Artikel disimpan ke DB tanpa kategori/ringkasan.
    Kategorisasi & ringkasan dilakukan setelah scraping selesai (Phase 2).
    """
    slug        = source["slug"]
    name        = source["name"]
    url         = source["url"]
    parser_slug = source.get("parser", slug)

    parser = get_parser(parser_slug)
    if not parser:
        logger.error(f"[{name}] Parser '{parser_slug}' tidak ditemukan")
        log_scrape(slug, "error", 0, 0, f"No parser for {parser_slug}")
        return [], {"new": 0, "skip": 0, "errors": 1}

    stats        = {"new": 0, "skip": 0, "errors": 0}
    new_articles = []
    current_url  = url
    page         = 0
    found_existing = False

    while current_url and page < max_pages:
        page += 1
        logger.info(f"[{name}] Listing page {page}: {current_url}")

        try:
            article_links, next_url = parser.get_article_links(current_url)
        except Exception as e:
            logger.error(f"[{name}] Gagal ambil links dari {current_url}: {e}")
            stats["errors"] += 1
            break

        if not article_links:
            logger.info(f"[{name}] Tidak ada link di halaman {page}, stop")
            break

        logger.info(f"[{name}] Ditemukan {len(article_links)} link artikel")

        for item in article_links:
            if isinstance(item, dict):
                art_url    = item["url"]
                extra_date = item.get("published_at")
            else:
                art_url    = item
                extra_date = None

            if url_exists(art_url):
                stats["skip"] += 1
                logger.info(f"[{name}] 🛑 Menemukan berita yang sudah terscrape → Stop ({art_url[:60]}...)")
                found_existing = True
                break

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

            try:
                saved = insert_news(article)
                if saved:
                    stats["new"] += 1
                    new_articles.append(article)
                    logger.info(f"[{name}] ✓ Simpan: {article['title'][:60]}")
                else:
                    stats["skip"] += 1  # Race condition
                    logger.info(f"[{name}] 🛑 Berita sudah ada di DB → Stop ({art_url[:60]}...)")
                    found_existing = True
                    break
            except Exception as e:
                logger.error(f"[{name}] DB error {art_url}: {e}")
                stats["errors"] += 1

        if found_existing:
            break

        current_url = next_url

    log_scrape(slug, "success", stats["new"], stats["skip"])
    return new_articles, stats


def scrape_all(max_pages: int = 3, use_ai: bool = True,
               use_gemini: bool = False,
               source_slugs: list[str] | None = None) -> dict:
    """
    Scrape semua sumber aktif, lalu proses AI (kategorisasi + ringkasan).

    Args:
        max_pages:    Maks halaman listing per sumber (default 3)
        use_ai:       Jalankan Ollama setelah scraping (default True)
        use_gemini:   Pakai Gemini API sebagai backend (override config)
        source_slugs: Hanya scrape sumber tertentu (None = semua)

    Returns:
        dict {new, skip, errors, processed}
    """
    seed_sources(SOURCES)

    total        = {"new": 0, "skip": 0, "errors": 0, "processed": 0}
    all_new_arts = []

    # ── Phase 1: Scraping ──────────────────────────────────────────────────────
    logger.info(f"\n{'='*60}")
    logger.info(f"PHASE 1: Scraping {len(SOURCES)} sumber (max {max_pages} halaman)")
    logger.info(f"{'='*60}")

    for source in SOURCES:
        if not source.get("active", True):
            continue
        if source_slugs and source["slug"] not in source_slugs:
            continue

        try:
            new_arts, stats = scrape_source(source, max_pages=max_pages)
            all_new_arts.extend(new_arts)
            for k in ("new", "skip", "errors"):
                total[k] += stats.get(k, 0)
            logger.info(
                f"[{source['name']}] → baru={stats['new']}, "
                f"skip={stats['skip']}, error={stats['errors']}"
            )
        except Exception as e:
            logger.error(f"[{source['name']}] Fatal: {e}", exc_info=True)
            total["errors"] += 1

    logger.info(
        f"\nPhase 1 selesai: {total['new']} artikel baru, "
        f"{total['skip']} di-skip, {total['errors']} error"
    )

    # ── Phase 2: AI Processing ─────────────────────────────────────────────────
    if not use_ai or not all_new_arts:
        if use_ai and not all_new_arts:
            logger.info("Tidak ada artikel baru — AI tidak dipanggil")
        return total

    logger.info(f"\n{'='*60}")
    logger.info(f"PHASE 2: AI Processing {len(all_new_arts)} artikel baru")
    logger.info(f"  Backend: {AI_BACKEND if not use_gemini else 'gemini'}")
    logger.info(f"{'='*60}")

    process_article = _get_ai_processor()

    for i, art in enumerate(all_new_arts, 1):
        title   = art.get("title", "")
        content = art.get("content", "")
        url     = art.get("url", "")

        logger.info(f"[AI {i}/{len(all_new_arts)}] {title[:55]}")

        try:
            result = process_article(title, content)
            update_category(url, result)
            total["processed"] += 1
            logger.info(
                f"  → {result['category']} / {result['subcategory']} "
                f"({result['confidence']:.0%}) | "
                f"summary={len(result.get('summary',''))} chars"
            )

            # ── Ekstraksi Event & Lembaga Triwulanan ──
            try:
                from database.db import get_db, save_extracted_entities_with_dedup
                from services.entity_extractor import extract_entities_from_article

                with get_db() as conn:
                    news_row = conn.execute("SELECT id, published_at FROM news WHERE url = ?", (url,)).fetchone()

                if news_row:
                    news_id = news_row["id"]
                    pub_date = news_row["published_at"] or art.get("published_at")
                    ent_res = extract_entities_from_article(title, content, backend="gemini" if use_gemini else None)
                    save_extracted_entities_with_dedup(
                        news_id=news_id,
                        events=ent_res.get("events", []),
                        companies=ent_res.get("companies", []),
                        published_at=pub_date
                    )
                    logger.info(f"  → Extracted: {len(ent_res.get('events', []))} events, {len(ent_res.get('companies', []))} companies")
            except Exception as ent_err:
                logger.warning(f"  → Ekstraksi Event/Lembaga error: {ent_err}")

        except Exception as e:
            logger.error(f"  → Gagal proses AI: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(
        f"SELESAI → new={total['new']}, skip={total['skip']}, "
        f"errors={total['errors']}, processed={total['processed']}"
    )
    return total

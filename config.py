import os
from pathlib import Path

# ── Auto-load .env file ───────────────────────────────────────
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

BASE_DIR = Path(__file__).parent

# ── Database ──────────────────────────────────────────────
DB_PATH = BASE_DIR / "data" / "news_scraper.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ── Gemini API (fallback / optional) ────────────────────
# Set via environment variable:  export GEMINI_API_KEY="your-key"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-flash-lite-latest"

# ── AI Backend ────────────────────────────────────────────
# "hybrid" = Gemini for categorization + Qwen (Ollama) for summarization
# "ollama" = Qwen for both
# "gemini" = Gemini for both
AI_BACKEND      = os.environ.get("AI_BACKEND", "hybrid")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
_default_cat = BASE_DIR / "data" / "Kamus_Kategori_Berita_PDRB.xlsx"
if not _default_cat.exists():
    _default_cat = BASE_DIR.parent / "Kamus_Kategori_Berita_PDRB.xlsx"

_default_exp = BASE_DIR / "data" / "Kategorisasi Pengeluaran.xlsx"
if not _default_exp.exists():
    _default_exp = BASE_DIR.parent / "Kategorisasi Pengeluaran.xlsx"

EXCEL_CATEGORIES_PATH = os.environ.get("EXCEL_PATH", str(_default_cat))
EXCEL_PENGELUARAN_PATH = os.environ.get("EXCEL_PENGELUARAN_PATH", str(_default_exp))


# ── Request Settings ──────────────────────────────────────
REQUEST_TIMEOUT   = 15   # seconds
REQUEST_DELAY     = 1.5  # seconds between requests (be polite)
REQUEST_HEADERS   = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

# ── News Sources ──────────────────────────────────────────
SOURCES = [
    {
        "name":   "Pemerintah Daerah",
        "slug":   "pemerintah-daerah",
        "url":    "https://prokopim.pohuwatokab.go.id/",
        "parser": "pemerintah_daerah",
        "active": True,
    },
    {
        "name":   "Tribunnews Pohuwato",
        "slug":   "tribunnews",
        "url":    "https://gorontalo.tribunnews.com/index-news/pohuwato",
        "parser": "tribunnews",
        "active": True,
    },
    {
        "name":   "Cara Pandang Pohuwato",
        "slug":   "carapandang",
        "url":    "https://gorontalo.carapandang.com/news/category/kabupaten-pohuwato",
        "parser": "carapandang",
        "active": True,
    },
    {
        "name":   "GoPos",
        "slug":   "gopos",
        "url":    "https://gopos.id/category/daerah/pohuwato-daerah/",
        "parser": "gopos",
        "active": True,
    },
    {
        "name":   "Beritabaru Pohuwato",
        "slug":   "beritabaru",
        "url":    "https://pohuwato.beritabaru.co/daerah/pohuwato/",
        "parser": "beritabaru",
        "active": True,
    },
    {
        "name":   "Dari Pohuwato",
        "slug":   "daripohuwato",
        "url":    "https://daripohuwato.id/",
        "parser": "daripohuwato",
        "active": True,
    },
    {
        "name":   "Gorontalo Post",
        "slug":   "gorontalopost",
        "url":    "https://gorontalopost.co.id/category/pohuwato-madani/",
        "parser": "gorontalopost",
        "active": True,
    },
    {
        "name":   "Ini Pohuwato",
        "slug":   "inipohuwato",
        "url":    "https://inipohuwato.id/",
        "parser": "inipohuwato",
        "active": True,
    },
    {
        "name":   "Wartanesia",
        "slug":   "wartanesia",
        "url":    "https://wartanesia.id/",
        "parser": "wartanesia",
        "active": True,
    },
    {
        "name":   "Antaranews Pohuwato",
        "slug":   "antaranews",
        "url":    "https://gorontalo.antaranews.com/kabar-gorontalo/pohuwato",
        "parser": "antaranews",
        "active": True,
    },
    {
        "name":   "Dulohupa",
        "slug":   "dulohupa",
        "url":    "https://dulohupa.id/berita/berita-daerah/berita-gorontalo/kabupaten-pohuwato/",
        "parser": "dulohupa",
        "active": True,
    },
    {
        "name":   "Seputar Pohuwato",
        "slug":   "seputarpohuwato",
        "url":    "https://seputarpohuwato.com/",
        "parser": "seputarpohuwato",
        "active": True,
    },
    {
        "name":   "Hibata.id Pohuwato",
        "slug":   "hibata",
        "url":    "https://hibata.id/daerah/pohuwato/",
        "parser": "hibata",
        "active": True,
    },
    {
        "name":   "Harianpost.id Pohuwato",
        "slug":   "harianpost",
        "url":    "https://harianpost.id/topik/pohuwato/",
        "parser": "harianpost",
        "active": True,
    },
    {
        "name":   "RRI Pohuwato",
        "slug":   "rri",
        "url":    "https://rri.co.id/search?q=pohuwato",
        "parser": "rri",
        "active": True,
    },
]

# ── Logging ───────────────────────────────────────────────
LOG_FILE = BASE_DIR / "logs" / "scraper.log"

# ── Flask ─────────────────────────────────────────────────
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "pohuwato-news-2026-secret")
_port_env = os.environ.get("PORT", "").strip()
FLASK_PORT = int(_port_env) if _port_env.isdigit() else 5555
FLASK_DEBUG      = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

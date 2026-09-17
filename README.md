# Pohuwato News Scraper & AI Categorization System

Sistem scraping dan kategorisasi berita daerah Kabupaten Pohuwato menggunakan AI (Dual-PDRB Lapangan Usaha & Pengeluaran) berbasis **Gemini API** dan **Ollama (Qwen2.5:3b)**.

---

## 📂 Struktur Proyek

```
news_scraper/
├── app.py                   # Web Dashboard (Flask) untuk melihat & memfilter berita
├── config.py                # Konfigurasi aplikasi, sumber berita, & AI backend
├── scrape_range.py          # Script CLI scraping rentang tanggal tertentu (misal: April–Juni)
├── run_scraper.py           # Script CLI scraping harian (cronjob)
├── CRONJOB_SETUP.md         # Panduan konfigurasi cronjob otomatis
├── database/                # Pengelolaan SQLite Database (db.py)
│   └── db.py
├── parsers/                 # Parser modular untuk 12 media berita lokal Pohuwato
│   ├── antaranews.py
│   ├── beritabaru.py
│   ├── carapandang.py
│   ├── daripohuwato.py
│   ├── dulohupa.py
│   ├── gopos.py
│   ├── gorontalopost.py
│   ├── inipohuwato.py
│   ├── pemerintah_daerah.py
│   ├── seputarpohuwato.py
│   ├── tribunnews.py
│   └── wartanesia.py
├── services/                # Pipeline AI & Scraper Engine
│   ├── gemini_categorizer.py # Categorizer PDRB via Gemini API
│   ├── ollama_processor.py   # Categorizer & Summarizer via Ollama (Qwen)
│   └── scraper_engine.py     # Orchestrator scraping & AI processing
├── static/ & templates/     # Aset UI Web Dashboard
└── data/
    └── news_scraper.db      # SQLite Database
```

---

## 🛠️ Instalasi

1. **Pastikan Python 3.10+ & Ollama terinstal.**
2. **Install Dependensi:**
   ```bash
   cd news_scraper
   pip install -r requirements.txt
   ```
3. **(Opsional) Pastikan Ollama berjalan:**
   ```bash
   ollama run qwen2.5:3b
   ```

---

## 🚀 Penggunaan Program

### 1. Scraping Berita Berdasarkan Rentang Tanggal (`scrape_range.py`)

Script ini khusus digunakan untuk menarik berita lama dalam rentang tanggal tertentu (misalnya bulan **April hingga Juni**). Berbeda dari scraping harian, script ini menelusuri halaman-halaman lama tanpa langsung berhenti jika menemukan artikel yang sudah tersimpan di database.

- **Scrape Berita April–Juni 2026 (Default) Menggunakan Ollama:**
  ```bash
  python scrape_range.py --no-gemini
  ```

- **Scrape Berita April–Juni untuk Tahun Tertentu (contoh: 2025):**
  ```bash
  python scrape_range.py --year 2025 --no-gemini
  ```

- **Scrape Rentang Tanggal Spesifik:**
  ```bash
  python scrape_range.py --start-date 2026-04-01 --end-date 2026-06-30 --no-gemini
  ```

- **Scrape Hanya 1 Sumber Berita (misal: Tribunnews):**
  ```bash
- **Scrape Hanya Sumber Pemerintah Daerah (`pemerintah-daerah`) untuk Rentang April–Juni:**
  ```bash
  python scrape_range.py --source pemerintah-daerah --start-date 2026-04-01 --end-date 2026-06-30 --no-gemini
  ```

#### Opsi Argumen CLI `scrape_range.py`:
- `--start-date` / `-s`: Tanggal mulai `YYYY-MM-DD` (default: `2026-04-01`).
- `--end-date` / `-e`: Tanggal selesai `YYYY-MM-DD` (default: `2026-06-30`).
- `--year` / `-y`: Tahun target (otomatis set 1 April – 30 Juni tahun tersebut).
- `--source`: Slug sumber berita (misal: `pemerintah-daerah`, `tribunnews`, `antaranews`, `gopos`). Jika kosong, semua sumber aktif di-scrape.
- `--pages`: Batas maksimal halaman listing yang ditelusuri per sumber (default: 30).
- `--no-gemini`: Menggunakan backend Ollama (Qwen) alih-alih Gemini.
- `--no-ai`: Melewati proses kategorisasi dan ringkasan AI.

---

### 2. Scraping Harian / Teratur (`run_scraper.py`)

Gunakan script ini untuk jadwal cronjob harian. Script akan berhenti jika menemukan artikel yang sudah pernah di-scrape.

```bash
# Scrape semua sumber menggunakan Ollama
python run_scraper.py --no-gemini --pages 3

# Scrape sumber spesifik (contoh: pemerintah-daerah)
python run_scraper.py --source pemerintah-daerah --no-gemini

# Scrape sumber spesifik dengan rentang tanggal
python run_scraper.py --source pemerintah-daerah --start-date 2026-04-01 --end-date 2026-06-30 --no-gemini
```

---

### 3. Web Dashboard Flask (`app.py`)

Untuk membuka antarmuka web pencarian & filter berita:

```bash
python app.py
```
Akses di browser: `http://localhost:5555`

---

## 📊 Cek Data di Database

Untuk mengecek jumlah berita di database SQLite (misal berita April–Juni 2026):

```bash
python3 -c "import sqlite3; conn=sqlite3.connect('data/news_scraper.db'); print('Total Berita April-Juni:', conn.execute(\"SELECT count(*) FROM news WHERE published_at >= '2026-04-01' AND published_at <= '2026-06-30 23:59:59'\").fetchone()[0])"
```

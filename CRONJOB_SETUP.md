# Panduan Setup Cronjob – Pohuwato News Scraper

## 1. Jalankan Scraper Manual (Test)

```bash
cd /Users/user/Programs/scraping/news_scraper
python3 run_scraper.py --no-gemini --pages 3
```

## 2. Setup Cronjob (macOS/Linux) – Jam 10:00 WITA setiap hari

### 2a. Cari path Python yang digunakan:
```bash
which python3
# Contoh output: /Library/Frameworks/Python.framework/Versions/3.14/bin/python3
```

### 2b. Edit crontab:
```bash
crontab -e
```

### 2c. Tambahkan baris berikut (ganti path Python sesuai output 2a):
```
# Pohuwato News Scraper – jam 10:00 WITA (02:00 UTC)
0 2 * * * cd /Users/user/Programs/scraping/news_scraper && /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 run_scraper.py --pages 3 >> logs/cron.log 2>&1
```

> ⚠️ Jam 10:00 WITA = 09:00 WIB = 02:00 UTC. Crontab selalu menggunakan UTC.

### 2d. Verifikasi crontab sudah tersimpan:
```bash
crontab -l
```

## 3. Setup Environment Variable GEMINI_API_KEY

### Option A – Tambahkan ke `.zshrc` / `.bashrc` (Permanent):
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### Option B – Tambahkan ke crontab langsung:
```
0 2 * * * GEMINI_API_KEY="your-api-key" cd /Users/user/Programs/scraping/news_scraper && python3 run_scraper.py --pages 3 >> logs/cron.log 2>&1
```

## 4. Opsi CLI run_scraper.py

```
python3 run_scraper.py                          # Scrape semua sumber
python3 run_scraper.py --source antaranews      # Hanya 1 sumber
python3 run_scraper.py --no-gemini             # Tanpa kategorisasi Gemini
python3 run_scraper.py --pages 5               # Max 5 halaman per sumber
```

## 5. Melihat Log
```bash
tail -f logs/scraper.log    # Real-time scraper log
tail -f logs/cron.log       # Log dari cronjob
```

## 6. Cek Database
```bash
cd news_scraper
python3 -c "
import sqlite3
conn = sqlite3.connect('data/news_scraper.db')
rows = conn.execute('SELECT source_media, COUNT(*) c FROM news GROUP BY source_media').fetchall()
for r in rows: print(r[0], r[1])
print('Total:', conn.execute('SELECT COUNT(*) FROM news').fetchone()[0])
"
```

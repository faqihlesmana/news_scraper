# Panduan Lengkap Deploy ke Supabase & Vercel

Panduan ini berisi langkah demi langkah untuk mengaktifkan database cloud di **Supabase** dan mendeploy web dashboard ke **Vercel**.

---

## Bagian 1: Setup Database di Supabase

### 1. Buat Proyek Supabase
1. Masuk ke [supabase.com](https://supabase.com).
2. Klik **New Project**, pilih nama proyek (misal: `pohuwato-news-scraper`) dan tentukan Database Password yang kuat.
3. Pilih region terdekat: **Singapore (ap-southeast-1)**.

### 2. Jalankan Skema Tabel (DDL)
1. Di dashboard Supabase, buka menu **SQL Editor** di bilah kiri.
2. Klik **New Query**.
3. Buka file [database/supabase_schema.sql](file:///Users/user/Programs/scraping/news_scraper/database/supabase_schema.sql) di proyek ini, lalu salin seluruh kodenya dan tempel di editor Supabase.
4. Klik tombol **Run** (Ctrl + Enter / Cmd + Enter).
5. Pastikan muncul status `Success. No rows returned`. Seluruh tabel (`sources`, `news`, `events`, `companies`, `article_feedback`, dll.) kini telah siap.

### 3. Ambil Connection String (URI)
1. Buka menu **Project Settings** (ikon gerigi kiri bawah) ➜ **Database**.
2. Scroll ke bagian **Connection String** ➜ pilih tab **URI**.
3. Pilih mode **Transaction** atau **Session** (Port 6543 / 5432).
4. Salin URL tersebut, contohnya:
   ```
   postgresql://postgres.xxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
   ```
   *(Ganti `[YOUR-PASSWORD]` dengan password yang Anda buat di awal)*.

---

## Bagian 2: Migrasi Data Lokal (SQLite ➜ Supabase)

Untuk mengunggah seluruh **1.949 berita, event, lembaga, dan feedback** yang ada di laptop ke Supabase:

Jalankan perintah berikut di terminal:
```bash
python3 migrate_to_supabase.py --url "postgresql://postgres.xxx:password@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require"
```
*(Atau simpan `DATABASE_URL` tersebut ke file `.env` di laptop Anda, lalu cukup jalankan `python3 migrate_to_supabase.py`)*.

Skrip akan menampilkan progres dan dalam hitungan detik seluruh data lokal telah aman di Supabase!

---

## Bagian 3: Deploy Dashboard ke Vercel

### 1. Push Perubahan Terbaru ke GitHub
Pastikan seluruh file persiapan sudah ter-push ke GitHub:
```bash
git add .
git commit -m "feat: prepare vercel deployment and supabase postgresql migration"
git push origin main
```

### 2. Import Repository di Vercel
1. Masuk ke [vercel.com](https://vercel.com) menggunakan akun GitHub Anda.
2. Klik **Add New...** ➜ **Project**.
3. Pilih repository `faqihlesmana/news_scraper` lalu klik **Import**.

### 3. Konfigurasi Environment Variables di Vercel
Sebelum klik Deploy, buka accordion **Environment Variables** dan tambahkan:
- `DATABASE_URL`: Connection string Supabase Anda (dari Langkah 1).
- `GEMINI_API_KEY`: API Key Gemini Anda.
- `AI_BACKEND`: `hybrid`
- `FLASK_SECRET_KEY`: string acak apa saja untuk sesi Flask.

### 4. Klik Deploy!
Tunggu sekitar 1–2 menit hingga Vercel selesai melakukan build.  
Setelah selesai, web dashboard Anda sudah aktif 24/7 di domain Vercel (misal: `https://news-scraper-xxx.vercel.app`)!

---

## Bagian 4: Menjalankan Scraping Harian (Mac / Laptop)

Karena laptop Anda sudah memiliki `DATABASE_URL` di file `.env`:
- Setiap kali cronjob jam 10:00 WITA berjalan di Mac Anda:
  - Berita discrape dari portal Pohuwato.
  - Diklasifikasikan menggunakan **Gemini API**.
  - Diringkas dan diekstrak event/lembaganya menggunakan **Ollama lokal**.
  - **Hasilnya langsung otomatis tersimpan ke Supabase di cloud!**
- Sehingga siapa pun yang membuka web Anda di Vercel akan langsung melihat data terbaru secara otomatis.

"""
services/ollama_processor.py

Menggunakan Ollama (LLM lokal) untuk:
1. Mengkategorikan berita berdasarkan Kamus Kategori Berita PDRB (BPS)
2. Meringkas isi berita menjadi 2-3 kalimat singkat
...dalam SATU API call per artikel.

Ollama running di http://localhost:11434 (qwen2.5:3b)
"""
import json
import logging
import os
import re
import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, EXCEL_CATEGORIES_PATH

logger = logging.getLogger(__name__)

# ── Pemetaan Sektor PDRB (Pendapatan Domestik Regional Bruto) ─────────────────
PDRB_SECTOR_MAP = {
    'A':    'Pertanian, Kehutanan & Perikanan',
    'B':    'Pertambangan & Penggalian',
    'C':    'Industri Pengolahan',
    'D':    'Pengadaan Listrik & Gas',
    'E':    'Pengadaan Air, Pengelolaan Sampah & Daur Ulang',
    'F':    'Konstruksi',
    'G':    'Perdagangan Besar, Eceran & Reparasi',
    'H':    'Transportasi & Pergudangan',
    'I':    'Penyediaan Akomodasi & Makan Minum',
    'J':    'Informasi & Komunikasi',
    'K':    'Jasa Keuangan & Asuransi',
    'L':    'Real Estate',
    'MN':   'Jasa Perusahaan',
    'M':    'Jasa Perusahaan',
    'N':    'Jasa Perusahaan',
    'O':    'Administrasi Pemerintahan, Pertahanan & Sosial Wajib',
    'P':    'Jasa Pendidikan',
    'Q':    'Jasa Kesehatan & Kegiatan Sosial',
    'RSTU': 'Jasa Lainnya',
    'R':    'Jasa Lainnya',
    'S':    'Jasa Lainnya',
    'T':    'Jasa Lainnya',
    'U':    'Jasa Lainnya',
}

# Default Categories (akan ditimpa oleh load_categories_from_excel)
CATEGORIES: list[tuple[str, list[str]]] = []
CATEGORY_METADATA: dict[str, dict] = {}


def load_categories_from_excel(excel_path: str = None) -> None:
    """
    Membaca Kamus_Kategori_Berita_PDRB.xlsx dan menyusun hirarki
    Kategori Utama (Sektor PDRB) dan Subkategori (Sub-sektor PDRB + Kata Kunci).
    """
    global CATEGORIES, CATEGORY_METADATA
    path_to_use = excel_path or EXCEL_CATEGORIES_PATH

    if not os.path.exists(path_to_use):
        logger.warning(f"[Ollama] File Excel PDRB tidak ditemukan di {path_to_use}. Menggunakan default.")
        _load_default_categories()
        return

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path_to_use, data_only=True)
        ws = wb.active

        sector_dict: dict[str, list[str]] = {}
        metadata: dict[str, dict] = {}

        for i in range(2, ws.max_row + 1):
            kode     = str(ws.cell(row=i, column=1).value or '').strip()
            name     = str(ws.cell(row=i, column=2).value or '').strip()
            keywords = str(ws.cell(row=i, column=3).value or '').strip()
            desc     = str(ws.cell(row=i, column=4).value or '').strip()

            if not kode or not name:
                continue

            # Tentukan sektor utama berdasarkan prefix kode (A, B, C, D, dst)
            prefix = ''.join([c for c in kode if c.isalpha()])
            main_cat = PDRB_SECTOR_MAP.get(
                prefix,
                PDRB_SECTOR_MAP.get(prefix[0] if prefix else '', 'Tidak Relevan')
            )

            sub_cat_display = f"[{kode}] {name}"
            sector_dict.setdefault(main_cat, []).append(sub_cat_display)

            metadata[sub_cat_display] = {
                "kode":     kode,
                "nama":     name,
                "sektor":   main_cat,
                "keywords": keywords,
                "desc":     desc,
            }

        if sector_dict:
            CATEGORIES = [(cat, subs) for cat, subs in sector_dict.items()]
            CATEGORY_METADATA = metadata
            logger.info(f"[Ollama] Berhasil memuat Kamus PDRB Excel dari {path_to_use} ({len(metadata)} sub-sektor)")
        else:
            logger.warning(f"[Ollama] Excel PDRB kosong di {path_to_use}. Menggunakan default.")
            _load_default_categories()

    except Exception as e:
        logger.error(f"[Ollama] Gagal membaca Excel PDRB ({path_to_use}): {e}")
        _load_default_categories()


EXP_CATEGORIES: list[tuple[str, list[str]]] = []
EXP_METADATA: dict[str, dict] = {}

def load_exp_categories_from_excel(excel_path: str = None) -> None:
    global EXP_CATEGORIES, EXP_METADATA
    from config import EXCEL_PENGELUARAN_PATH
    path_to_use = excel_path or EXCEL_PENGELUARAN_PATH
    if not os.path.exists(path_to_use):
        return

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path_to_use, data_only=True)
        ws = wb.active
        exp_dict: dict[str, list[str]] = {}
        EXP_METADATA.clear()

        for i in range(2, ws.max_row + 1):
            cat  = str(ws.cell(row=i, column=2).value or '').strip()
            sub  = str(ws.cell(row=i, column=3).value or '').strip()
            desc = str(ws.cell(row=i, column=5).value or '').strip()
            kw   = str(ws.cell(row=i, column=6).value or '').strip()

            if cat and sub:
                if sub not in exp_dict.setdefault(cat, []):
                    exp_dict[cat].append(sub)
                EXP_METADATA[sub] = {"desc": desc, "keywords": kw}

        if exp_dict:
            exp_dict["Tidak Relevan"] = ["Tidak Relevan"]
            EXP_CATEGORIES = [(c, subs) for c, subs in exp_dict.items()]
            logger.info(f"[Ollama] Loaded {len(EXP_CATEGORIES)} PDRB Pengeluaran categories (with descriptions & keywords)")

    except Exception as e:
        logger.error(f"[Ollama] Error loading Pengeluaran Excel: {e}")


def _load_default_categories():
    global CATEGORIES
    CATEGORIES = [
        ("Pertanian, Kehutanan & Perikanan", ["Tanaman Pangan", "Peternakan", "Perikanan", "Kehutanan"]),
        ("Pertambangan & Penggalian", ["Pertambangan Bijih Logam", "Penggalian Lainnya"]),
        ("Industri Pengolahan", ["Industri Makanan dan Minuman", "Pengolahan Hasil Bumi"]),
        ("Konstruksi", ["Konstruksi Jalan & Bangunan"]),
        ("Perdagangan Besar, Eceran & Reparasi", ["Perdagangan Eceran", "Pasar"]),
        ("Transportasi & Pergudangan", ["Angkutan Darat", "Angkutan Laut"]),
        ("Informasi & Komunikasi", ["Telekomunikasi", "Internet"]),
        ("Administrasi Pemerintahan, Pertahanan & Sosial Wajib", ["Kebijakan Pemda", "Pelayanan Publik", "Ketertiban"]),
        ("Jasa Pendidikan", ["Sekolah", "Perguruan Tinggi"]),
        ("Jasa Kesehatan & Kegiatan Sosial", ["Rumah Sakit", "Layanan Kesehatan"]),
        ("Jasa Lainnya", ["Umum"]),
    ]


# Auto-load saat module di-import
load_categories_from_excel()
load_exp_categories_from_excel()


# ── Health check ──────────────────────────────────────────────────────────────
def is_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_available_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ── Validation helpers ─────────────────────────────────────────────────────────
def _validate_exp(cat: str, sub: str) -> tuple[str, str]:
    if not cat or cat.strip().lower() in ["lainnya", "non-pdrb", "umum", "lain-lain", "tidak relevan"]:
        return "Tidak Relevan", "Tidak Relevan"
    all_exp_cats = [c for c, _ in EXP_CATEGORIES] if EXP_CATEGORIES else []
    if not all_exp_cats:
        return cat, sub
    if cat not in all_exp_cats:
        cl = cat.lower()
        cat = next((c for c in all_exp_cats if cl in c.lower() or c.lower() in cl), "Tidak Relevan")
    valid_subs = dict(EXP_CATEGORIES).get(cat, ["Tidak Relevan"])
    if sub not in valid_subs:
        sl = sub.lower()
        sub = next((s for s in valid_subs if sl in s.lower() or s.lower() in sl), valid_subs[0])
    return cat, sub


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_prompt(title: str, content: str) -> str:
    """
    Bangun prompt Dual PDRB (Lapangan Usaha + Pengeluaran) + ringkasan dalam 1 call.
    """
    lines_lu = []
    for cat, subs in CATEGORIES:
        lines_lu.append(f"• Sektor LU: {cat}")
        for s in subs[:4]:
            kw = CATEGORY_METADATA.get(s, {}).get("keywords", "")
            kw_str = f" ({kw[:30]})" if kw else ""
            lines_lu.append(f"   - Sub: {s}{kw_str}")

    cats_lu_str = "\n".join(lines_lu[:40])

    lines_exp = []
    for cat, subs in EXP_CATEGORIES:
        lines_exp.append(f"• Kategori Pengeluaran: {cat}")
        for s in subs[:4]:
            lines_exp.append(f"   - Sub: {s}")

    cats_exp_str = "\n".join(lines_exp[:30])
    excerpt = (content or "").strip()[:3000]

    return f"""Kamu adalah ahli ekonomi regional BPS. Klasifikasikan berita Pohuwato ke dalam Dual PDRB: Lapangan Usaha (LU) dan Pengeluaran (PE).

1. LAPANGAN USAHA (LU):
{cats_lu_str}
• Sektor Tambahan: Tidak Relevan (jika tidak berdampak ekonomi)

2. PENGELUARAN (PE):
{cats_exp_str}
• Kategori Tambahan: Tidak Relevan (jika tidak berdampak ekonomi)

ATURAN RELEVANSI — SKALA DAMPAK EKONOMI:
Yang kami cari adalah berita yang BERDAMPAK SIGNIFIKAN terhadap perekonomian daerah. Gunakan prinsip berikut:

MASUK KATEGORI PDRB (relevan = true) jika:
- Menyebut ANGKA PRODUKSI, NILAI EKONOMI, atau VOLUME yang jelas (contoh: "produksi jagung 10.000 ton", "investasi Rp 5 miliar")
- PROGRAM/KEBIJAKAN PEMERINTAH berskala besar (bantuan sosial massal, APBD, program pembangunan infrastruktur, subsidi)
- BENCANA/KECELAKAAN BERSKALA BESAR yang berdampak luas pada ekonomi (banjir merusak ratusan hektar sawah, longsor menutup jalan utama perdagangan)
- KORUPSI/KASUS HUKUM BERSKALA BESAR yang melibatkan anggaran publik signifikan (korupsi dana desa miliaran, kasus penggelapan APBD)
- AKTIVITAS EKONOMI yang melibatkan BANYAK ORANG atau SEKTOR (panen raya, pasar tradisional, ekspor komoditas, festival ekonomi kreatif)
- INVESTASI, PEMBUKAAN/PENUTUPAN USAHA yang berdampak pada lapangan kerja banyak orang

TIDAK RELEVAN / "Tidak Relevan" (relevan = false) jika:
- Kecelakaan/kematian INDIVIDU tanpa dampak ekonomi luas (1 orang terjatuh, 1 orang tenggelam, kecelakaan tunggal)
- Kriminal SKALA KECIL (pencurian ayam, perkelahian individu, penipuan perorangan)
- Berita seremonial/protokoler tanpa substansi ekonomi (kunjungan pejabat tanpa program konkret, pelantikan tanpa kebijakan baru)
- Berita hiburan, gosip, olahraga, agama murni tanpa kaitan ekonomi
- Berita sosial individu (pernikahan, kelahiran, kematian biasa)

CONTOH KLASIFIKASI:
Judul: "Penambang di DAM Tewas usai Diduga Terjatuh dari Talang"
→ Tidak Relevan (kecelakaan individu, tidak berdampak ekonomi luas)

Judul: "Banjir Bandang Rendam 500 Hektar Sawah di Pohuwato, Petani Rugi Miliaran"
→ Pertanian, Kehutanan & Perikanan (bencana skala besar, dampak ekonomi signifikan pada sektor pertanian)

Judul: "Pemuda Ditangkap Karena Mencuri Motor"
→ Tidak Relevan (kriminal kecil, tidak berdampak ekonomi)

Judul: "KPK Usut Korupsi Dana Desa Rp 3,2 Miliar di Pohuwato"
→ Administrasi Pemerintahan (korupsi besar, melibatkan anggaran publik signifikan)

Judul: "Bupati Resmikan Pasar Rakyat Baru Senilai Rp 8 Miliar"
→ Perdagangan Besar, Eceran & Reparasi (investasi infrastruktur perdagangan skala besar)

Judul: "Satu Unit Rumah Terbakar di Desa Taluditi"
→ Tidak Relevan (insiden kecil individual)

Judul: "Pemerintah Salurkan 10.000 Paket Sembako untuk Warga Terdampak"
→ Konsumsi Pemerintah / Administrasi Pemerintahan (bantuan sosial massal, berdampak pada konsumsi masyarakat)

Judul berita: {title}
Isi berita (cuplikan):
{excerpt}

Tugas kamu:
1. Tentukan Sektor & Sub Lapangan Usaha (LU).
2. Tentukan Kategori & Sub Pengeluaran (PE).
3. Buat ringkasan berita 4-6 kalimat Bahasa Indonesia.
4. Tentukan apakah berita ini RELEVAN secara ekonomi berdasarkan aturan skala dampak di atas.

Balas HANYA JSON valid:
{{"category": "<Sektor LU atau Tidak Relevan>", "subcategory": "<Sub LU>", "exp_category": "<Kategori PE atau Tidak Relevan>", "exp_subcategory": "<Sub PE>", "confidence": <1-10>, "summary": "<ringkasan 2-3 kalimat>"}}"""


# ── Core Ollama call ──────────────────────────────────────────────────────────
def _call_ollama(prompt: str) -> str | None:
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 450,
        },
    }
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except requests.exceptions.ConnectionError:
        logger.error("[Ollama] Tidak bisa konek ke Ollama. Pastikan `ollama serve` berjalan.")
        return None
    except Exception as e:
        logger.error(f"[Ollama] API error: {e}")
        return None


# ── Response parser ───────────────────────────────────────────────────────────
def _parse_response(raw: str) -> dict | None:
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning(f"[Ollama] Tidak bisa parse JSON: {raw[:200]}")
    return None


# ── Validation helper ─────────────────────────────────────────────────────────
def _validate(cat: str, sub: str) -> tuple[str, str]:
    if not cat or cat.strip().lower() in ["lainnya", "non-pdrb", "umum", "lain-lain", "tidak relevan"]:
        return "Tidak Relevan", "Tidak Relevan"

    all_cats = [c for c, _ in CATEGORIES]
    if not all_cats:
        return cat, sub

    cat_strip = cat.strip().upper()
    prefix = ''.join([c for c in cat_strip if c.isalpha()])
    if prefix in PDRB_SECTOR_MAP:
        mapped_cat = PDRB_SECTOR_MAP[prefix]
        if mapped_cat in all_cats:
            cat = mapped_cat

    if cat not in all_cats:
        cl = cat.lower()
        cat = next((c for c in all_cats if cl in c.lower() or c.lower() in cl), all_cats[0])

    valid_subs = dict(CATEGORIES).get(cat, [])
    if valid_subs and sub not in valid_subs:
        sl = sub.lower()
        sub = next((s for s in valid_subs if sl in s.lower() or s.lower() in sl), valid_subs[0])

    return cat, sub


# ── Public interface ──────────────────────────────────────────────────────────
def process_article(title: str, content: str) -> dict:
    """
    Proses 1 artikel: Dual PDRB (Lapangan Usaha + Pengeluaran) + ringkasan via Ollama.
    """
    prompt = _build_prompt(title or "", content or "")
    raw    = _call_ollama(prompt)
    result = _parse_response(raw) if raw else None

    if result:
        cat_raw  = result.get("category") or result.get("sektor") or result.get("c_lu") or "Tidak Relevan"
        sub_raw  = result.get("subcategory") or result.get("subsektor") or result.get("s_lu") or "Tidak Relevan"
        exp_c_raw = result.get("exp_category") or result.get("c_pe") or result.get("kategori_pengeluaran") or "Tidak Relevan"
        exp_s_raw = result.get("exp_subcategory") or result.get("s_pe") or result.get("sub_pengeluaran") or "Tidak Relevan"
        conf_raw = result.get("confidence") or result.get("n") or 5
        summary_raw = result.get("summary") or result.get("ringkasan") or ""

        cat, sub = _validate(str(cat_raw), str(sub_raw))
        exp_cat, exp_sub = _validate_exp(str(exp_c_raw), str(exp_s_raw))

        try:
            conf = min(1.0, float(conf_raw) / (10.0 if float(conf_raw) > 1.0 else 1.0))
        except Exception:
            conf = 0.8

        return {
            "category":        cat,
            "subcategory":     sub,
            "exp_category":    exp_cat,
            "exp_subcategory": exp_sub,
            "confidence":      conf,
            "summary":         str(summary_raw).strip(),
        }

    return {
        "category":        "Tidak Relevan",
        "subcategory":     "Tidak Relevan",
        "exp_category":    "Tidak Relevan",
        "exp_subcategory": "Tidak Relevan",
        "confidence":      0.0,
        "summary":         "",
    }


def summarize_article(title: str, content: str) -> str:
    """
    Ringkas isi berita menjadi 2-3 kalimat singkat menggunakan Qwen via Ollama.
    Dipanggil HANYA jika Gemini telah mengategorikan berita sebagai relevan.
    """
    excerpt = (content or "").strip()[:3000]
    prompt = f"""Kamu adalah asisten jurnalis. Buat ringkasan berita berikut dalam 2-3 kalimat singkat, padat, dan informatif menggunakan Bahasa Indonesia baku.

Judul berita: {title}
Isi berita:
{excerpt}

Tulis HANYA ringkasan 2-3 kalimat tanpa teks tambahan lain:"""

    raw = _call_ollama(prompt)
    if raw:
        clean_summary = raw.strip().strip('"').strip("'")
        clean_summary = re.sub(r"^(ringkasan:\s*|summary:\s*)", "", clean_summary, flags=re.IGNORECASE)
        return clean_summary.strip()
    return ""



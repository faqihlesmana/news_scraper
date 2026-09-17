"""
services/entity_extractor.py

Ekstraksi Event Masal & Lembaga/Perusahaan dari berita:
- Event: Pertunjukan, konser, pameran, pasar malam, jalan sehat, festival, perayaan, dll. (berdampak ekonomi kab.)
- Lembaga/Perusahaan: PT, CV, BUMN, Dinas, Lembaga, Bank, dll.
- Penentuan Triwulan (Q1-Q4) dan Tahun berdasarkan tanggal publikasi berita.
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from config import GEMINI_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL, AI_BACKEND

logger = logging.getLogger(__name__)


def parse_quarter_and_year(published_date_str: Optional[str]) -> tuple[int, str]:
    """
    Ekstrak Tahun (YYYY) dan Triwulan (Q1, Q2, Q3, Q4) dari string tanggal publikasi.
    """
    if not published_date_str:
        now = datetime.now()
        quarter = f"Q{(now.month - 1) // 3 + 1}"
        return now.year, quarter

    # Coba format ISO atau YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{1,2})", str(published_date_str))
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
    else:
        # Fallback jika ada format tanggal Indonesia seperti "12 Agustus 2024"
        bulan_map = {
            "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
            "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6,
            "jul": 7, "agu": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12
        }
        text_lower = str(published_date_str).lower()
        year_match = re.search(r"\b(20\d{2})\b", text_lower)
        year = int(year_match.group(1)) if year_match else datetime.now().year

        month = 1
        for b_name, b_num in bulan_map.items():
            if b_name in text_lower:
                month = b_num
                break

    if 1 <= month <= 3:
        quarter = "Q1"
    elif 4 <= month <= 6:
        quarter = "Q2"
    elif 7 <= month <= 9:
        quarter = "Q3"
    else:
        quarter = "Q4"

    return year, quarter


def extract_entities_gemini(title: str, content: str) -> dict:
    """
    Ekstraksi menggunakan Google Gemini API.
    """
    if not GEMINI_API_KEY:
        logger.warning("[EntityExtractor] GEMINI_API_KEY kosong, beralih ke Ollama")
        return extract_entities_ollama(title, content)

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
Anda adalah analis berita ekonomi daerah. Analisis berita berikut dan ekstrak:
1. "events": Nama kegiatan masal atau pertunjukan (misal: festival, pameran UMKM, konser, pasar malam, jalan sehat, expo, perayaan hari besar/daerah) yang diperkirakan memiliki dampak ekonomi di tingkat kabupaten. Ambil HANYA nama spesifik event tersebut. Jika tidak ada, kembalikan array kosong [].
2. "companies": Nama perusahaan swasta, BUMN/BUMD, dinas/instansi pemerintah, atau lembaga/organisasi yang disebutkan atau terlibat dalam berita. Ambil HANYA nama lembaga/perusahaan resminya.

Berita:
Judul: {title}
Isi: {content[:3000]}

Kembalikan HANYA JSON murni dengan format:
{{
  "events": ["Nama Event 1", "Nama Event 2"],
  "companies": ["Nama Perusahaan/Lembaga 1", "Nama Perusahaan/Lembaga 2"]
}}
"""
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text.strip())
        return _clean_extracted_data(data)
    except Exception as e:
        logger.error(f"[EntityExtractor] Gemini error: {e}, mencoba fallback Ollama")
        return extract_entities_ollama(title, content)


def extract_entities_ollama(title: str, content: str) -> dict:
    """
    Ekstraksi menggunakan Ollama lokal (JSON Mode).
    """
    import urllib.request

    prompt = f"""Kamu adalah asisten analisis data berita ekonomi daerah.
Tugas: Ekstrak HANYA nama event masal dan nama perusahaan/lembaga dari teks berita berikut.

Aturan Penting:
1. "events": HANYA kegiatan masal/pertunjukan/perkumpulan besar berdampak ekonomi di kabupaten (misal: festival, pameran UMKM, pasar malam, konser musik, jalan sehat, expo, perayaan daerah, turnamen). JANGAN masukkan program kerja biasa atau nama program umum kecuali ada event perayaannya. Jika tidak ada event masal, isi [].
2. "companies": HANYA perusahaan swasta, BUMN/BUMD, dinas/instansi pemerintah, perbankan, atau organisasi resmi (misal: PT Bank Mandiri, Dinas Pertanian, PT Gorontalo Sejahtera Mining, BPJN). JANGAN masukkan nama media berita (seperti GOPOS.ID, Tribun, Kompas) dan JANGAN masukkan nama kota/daerah (seperti LIMBOTO, MARISA, GORONTALO, POHUWATO) sebagai nama perusahaan.

Judul: {title}
Isi: {content[:2500]}

Kembalikan HANYA JSON persis format ini:
{{"events": ["Nama Event"], "companies": ["Nama Perusahaan/Lembaga"]}}"""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_data = json.loads(resp.read().decode())
            data = json.loads(res_data.get("response", "{}"))
            return _clean_extracted_data(data)
    except Exception as e:
        logger.error(f"[EntityExtractor] Ollama error: {e}")
        return {"events": [], "companies": []}


# Blacklist nama media, lokasi, atau kata umum yang tidak valid
_IGNORE_WORDS = {
    "gopos.id", "tribunnews", "tribun", "detik", "detik.com", "kompas", "antara", "antaranews",
    "kilasgorontalo", "kronologi.id", "hulondalo.id", "hargo.co.id", "barakati.id", "read.id",
    "marisa", "limboto", "gorontalo", "pohuwato", "tilamuta", "suwawa", "kwandang",
    "indonesia", "pemerintah pusat", "tidak ada", "none", "null", "-", "n/a"
}

def _clean_extracted_data(data: dict) -> dict:
    """Normalisasi & sanitasi list string hasil ekstraksi."""
    events = []
    for item in data.get("events", []):
        if isinstance(item, str) and item.strip():
            clean = " ".join(item.strip().split())
            if len(clean) > 3 and clean.lower() not in _IGNORE_WORDS:
                events.append(clean)

    companies = []
    for item in data.get("companies", []):
        if isinstance(item, str) and item.strip():
            clean = " ".join(item.strip().split())
            if len(clean) > 3 and clean.lower() not in _IGNORE_WORDS:
                companies.append(clean)

    return {
        "events": list(dict.fromkeys(events)),      # Deduplikasi di level artikel
        "companies": list(dict.fromkeys(companies))
    }


def extract_entities_from_article(title: str, content: str, backend: Optional[str] = None) -> dict:
    """
    Fungsi entry point untuk ekstraksi entitas sesuai backend aktif.
    """
    used_backend = backend or AI_BACKEND
    if used_backend in ("gemini", "hybrid") and GEMINI_API_KEY:
        return extract_entities_gemini(title, content)
    else:
        return extract_entities_ollama(title, content)

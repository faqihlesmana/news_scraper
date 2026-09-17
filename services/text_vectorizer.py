"""
services/text_vectorizer.py
Mengubah artikel berita menjadi representasi teks ringkas (pseudo-vector)
sebelum dikirim ke Gemini, untuk menghemat token dan API call.

Alur:
  raw_article  →  extract_keywords()  →  compact string ~80-120 karakter
  ex: "Polres Pohuwato PETI tambang emas ilegal penertiban operasi"
"""
import re

# ── Indonesian stopwords (common, high-frequency, low-information words) ──────
_STOPWORDS = {
    # Conjunctions / prepositions
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "ini", "itu",
    "atau", "juga", "namun", "tetapi", "tapi", "karena", "sehingga",
    "agar", "supaya", "meski", "meskipun", "walaupun", "bahwa", "oleh",
    "pada", "dalam", "antara", "sebagai", "saat", "ketika", "sejak",
    "hingga", "sampai", "setelah", "sebelum", "selama", "tentang",
    "mengenai", "terhadap", "bagi", "para", "pun", "pula", "lalu",
    "kemudian", "sudah", "telah", "akan", "sedang", "masih",
    "belum", "bisa", "dapat", "harus", "perlu", "ada", "tidak", "tak",
    "bukan", "tanpa", "hal", "cara", "saja", "lebih", "sangat", "cukup",
    # Articles/determiners
    "se", "si", "sang",
    # Common verbs that carry little domain info
    "adalah", "merupakan", "menjadi", "memiliki", "mempunyai", "berupa",
    "melakukan", "mengatakan", "menyatakan", "mengungkapkan", "menuturkan",
    "mengaku", "mengakui", "menyebutkan",
    # Filler words in news
    "tersebut", "terkait",
    # Numbers as words
    "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
    "sembilan", "sepuluh",
}

# ── Boilerplate patterns that add no meaning ──────────────────────────────────
_BOILERPLATE_RE = re.compile(
    r"(baca juga|ikuti kami|follow|subscribe|editor|reporter|sumber|"
    r"advertisement|iklan|bagikan|lihat juga|bergabung|klik di sini|"
    r"dapatkan berita|simak berita|untuk berlangganan).*",
    re.IGNORECASE,
)

# Keep only alphanumeric + Indonesian chars
_CLEAN_RE  = re.compile(r"[^a-zA-Z0-9àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅ\s]")
_SPACE_RE  = re.compile(r"\s+")


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    text = _CLEAN_RE.sub(" ", text.lower())
    return _SPACE_RE.sub(" ", text).strip().split()


def _is_meaningful(word: str) -> bool:
    """Return True if word carries domain information."""
    if word in _STOPWORDS:
        return False
    if len(word) < 4:  # Skip very short words (di, ke, dan, etc.)
        return False
    if word.isdigit():  # Skip pure numbers
        return False
    return True


def vectorize_article(title: str, content: str,
                      max_tokens: int = 15) -> str:
    """
    Extract the most informative keyword tokens from an article.

    Strategy:
    1. Title is most important → take all meaningful words from title
    2. Fill remaining slots from the first 2-3 sentences of content
    3. Deduplicate (preserving order)
    4. Return as space-separated string

    Args:
        title:      Article headline
        content:    Article body text
        max_tokens: Maximum number of keyword tokens (default 15)

    Returns:
        Space-separated keyword string, e.g.:
        "pohuwato bupati bantuan sosial sembako masyarakat pelayanan"
    """
    if not title and not content:
        return ""

    # ── Step 1: extract from title ────────────────────────────────────────────
    title_clean = _BOILERPLATE_RE.sub("", title or "")
    title_tokens = [w for w in _tokenize(title_clean) if _is_meaningful(w)]

    # ── Step 2: extract from first ~300 chars of content ─────────────────────
    snippet = (content or "")[:400]
    snippet = _BOILERPLATE_RE.sub("", snippet)
    content_tokens = [w for w in _tokenize(snippet) if _is_meaningful(w)]

    # ── Step 3: merge, deduplicate, preserve order ────────────────────────────
    seen: set[str] = set()
    merged: list[str] = []
    for tok in title_tokens + content_tokens:
        if tok not in seen:
            seen.add(tok)
            merged.append(tok)
        if len(merged) >= max_tokens:
            break

    return " ".join(merged)

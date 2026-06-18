import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np



BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"
METADATA_FILE = DATA_DIR / "embeddings_meta.json"

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

CATEGORY_KEYWORDS = {
    "phone": [
        "telefon", "телефон", "mobilen", "мобилен", "smartphone",
        "iphone", "samsung", "xiaomi", "huawei", "oneplus", "realme"
    ],
    "housing": [
        "stan", "стан", "apartman", "апартман", "garsonjera", "гарсоњера",
        "kuka", "куќа", "kirija", "кирија", "izdavam", "издавам",
        "centar", "центар", "aerodrom", "karpos", "kisela voda"
    ],
    "car": [
        "kola", "кола", "avtomobil", "автомобил", "vozilo", "возило",
        "golf", "bmw", "audi", "mercedes", "opel", "renault", "peugeot"
    ]
}

_model = None
_embeddings: Optional[np.ndarray] = None
_indexed_ads: List[Dict[str, Any]] = []


def detect_category(text: str):
    text = (text or "").lower()

    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in text for word in words):
            return category

    return None


def passes_category_filter(query: str, ad_text: str) -> bool:
    category = detect_category(query)

    if not category:
        return True

    return any(word in ad_text.lower() for word in CATEGORY_KEYWORDS[category])

def _get_model():
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        print(f"[Semantic] Loading model {MODEL_NAME}...")
        t0 = time.time()

        _model = SentenceTransformer(MODEL_NAME)

        print(f"[Semantic] Model loaded in {time.time() - t0:.1f}s")

    return _model


def _ad_to_text(ad: Dict[str, Any]) -> str:
    parts = [
        str(ad.get("title") or ""),
        str(ad.get("description") or ""),
        str(ad.get("price") or ""),
        str(ad.get("source") or ""),
    ]

    return " ".join(p for p in parts if p).strip()


def _ads_signature(ads: List[Dict[str, Any]]) -> Dict[str, Any]:
    links = [str(ad.get("link") or "") for ad in ads]

    return {
        "count": len(ads),
        "first_link": links[0] if links else "",
        "last_link": links[-1] if links else "",
        "model": MODEL_NAME,
    }


def _cache_is_valid(ads: List[Dict[str, Any]]) -> bool:
    if not EMBEDDINGS_FILE.exists() or not METADATA_FILE.exists():
        return False

    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)

        return meta == _ads_signature(ads)

    except Exception:
        return False


def load_semantic_index(ads: List[Dict[str, Any]]) -> None:
    global _embeddings, _indexed_ads

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    _indexed_ads = ads

    if not ads:
        _embeddings = None
        print("[Semantic] No ads available for semantic index")
        return

    if _cache_is_valid(ads):
        print("[Semantic] Loading cached embeddings...")

        _embeddings = np.load(str(EMBEDDINGS_FILE))

        if _embeddings.shape[0] == len(ads):
            print(f"[Semantic] Loaded {_embeddings.shape[0]} embeddings from cache")
            _get_model()
            return

        print("[Semantic] Cache size mismatch, rebuilding...")

    model = _get_model()

    texts = [_ad_to_text(ad) for ad in ads]

    print(f"[Semantic] Encoding {len(texts)} ads...")
    t0 = time.time()

    _embeddings = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    print(f"[Semantic] Encoded in {time.time() - t0:.1f}s")

    np.save(str(EMBEDDINGS_FILE), _embeddings)

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(_ads_signature(ads), f, ensure_ascii=False, indent=2)

    print("[Semantic] Embeddings cached to disk")

def semantic_search(
        query: str,
        limit: int = 20,
        threshold: float = 0.68,   # <-- 0.40 bese prenizok
) -> List[Dict[str, Any]]:

    if _embeddings is None or not _indexed_ads:
        return []

    model = _get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    scores = _embeddings @ q_emb
    top_indices = np.argsort(scores)[::-1]

    results = []
    for idx in top_indices:
        score = float(scores[idx])

        if score < threshold:
            break

        ad = dict(_indexed_ads[idx])
        ad_text = _ad_to_text(ad).lower()


        ad["_semantic_score"] = round(score, 4)
        results.append(ad)

        if len(results) >= limit:
            break



    return results

def is_ready() -> bool:
    return _embeddings is not None and len(_indexed_ads) > 0
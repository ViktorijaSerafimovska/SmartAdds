import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "ads.json"
EMBEDDINGS_FILE = BASE_DIR / "data" / "embeddings.npy"
METADATA_FILE = BASE_DIR / "data" / "embeddings_meta.json"

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_embeddings: Optional[np.ndarray] = None
_indexed_ads: List[Dict[str, Any]] = []


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


def _cache_is_valid() -> bool:
    if not EMBEDDINGS_FILE.exists() or not METADATA_FILE.exists():
        return False
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        data_mtime = DATA_FILE.stat().st_mtime
        return meta.get("data_mtime") == data_mtime and meta.get("model") == MODEL_NAME
    except Exception:
        return False


def load_semantic_index(ads: List[Dict[str, Any]]) -> None:
    global _embeddings, _indexed_ads

    _indexed_ads = ads

    if _cache_is_valid():
        print("[Semantic] Loading cached embeddings...")
        _embeddings = np.load(str(EMBEDDINGS_FILE))
        if _embeddings.shape[0] == len(ads):
            print(f"[Semantic] Loaded {_embeddings.shape[0]} embeddings from cache")
            _get_model()  # pre-warm so first query is fast
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
        json.dump({"data_mtime": DATA_FILE.stat().st_mtime, "model": MODEL_NAME}, f)
    print("[Semantic] Embeddings cached to disk")


def semantic_search(
    query: str,
    limit: int = 20,
    threshold: float = 0.40,
) -> List[Dict[str, Any]]:
    if _embeddings is None or not _indexed_ads:
        return []

    model = _get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]

    # Cosine similarity — embeddings are L2-normalised so dot product == cosine
    scores = _embeddings @ q_emb

    top_indices = np.argsort(scores)[::-1]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score < threshold:
            break
        ad = dict(_indexed_ads[idx])
        ad["_semantic_score"] = round(score, 4)
        results.append(ad)
        if len(results) >= limit:
            break

    return results


def is_ready() -> bool:
    return _embeddings is not None and len(_indexed_ads) > 0

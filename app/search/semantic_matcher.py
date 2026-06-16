from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from app.database.db import SessionLocal
from app.database.models import Ad
from app.database.repository import (
    create_notification,
    get_all_saved_searches,
    get_user_by_id,
)
from app.notifications.email_service import send_email_notification

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Tuning
# -------------------------------------------------------------------
# 0.45 is a good starting point for paraphrase-multilingual-MiniLM-L12-v2.
# Raise it (e.g. 0.55) if you get too many false positives.
# Lower it (e.g. 0.38) if valid matches are being missed.
MATCH_THRESHOLD: float = 0.45

# -------------------------------------------------------------------
# In-memory cache: search.id → unit-norm embedding (np.ndarray shape [D])
# -------------------------------------------------------------------
_query_cache: Dict[int, np.ndarray] = {}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _get_model():
    """Reuse the already-loaded SentenceTransformer from semantic_engine."""
    from app.search.semantic_engine import _get_model as engine_get_model
    return engine_get_model()


def _ad_to_text(ad: Ad) -> str:
    """Combine the most descriptive fields into a single string for encoding."""
    parts = [
        str(ad.title or ""),
        str(ad.description or ""),
        str(ad.price or ""),
        str(ad.source or ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _encode(texts: List[str]) -> np.ndarray:
    """Encode a list of strings → L2-normalised embedding matrix."""
    model = _get_model()
    return model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def _get_query_embedding(search_id: int, query: str) -> np.ndarray:
    """Return cached embedding for this search, encoding on first call."""
    if search_id not in _query_cache:
        emb = _encode([query])[0]
        _query_cache[search_id] = emb
        logger.debug("[SemanticMatcher] Encoded query id=%d: '%s'", search_id, query)
    return _query_cache[search_id]


def invalidate_query_cache(search_id: Optional[int] = None) -> None:
    """
    Call this when a saved search is created or deleted so the cache stays fresh.
    Pass search_id to remove a single entry, or None to clear everything.
    """
    if search_id is None:
        _query_cache.clear()
        logger.info("[SemanticMatcher] Full query cache cleared")
    else:
        _query_cache.pop(search_id, None)
        logger.info("[SemanticMatcher] Query cache cleared for search_id=%d", search_id)


# -------------------------------------------------------------------
# Main entry point — drop-in replacement for old match_new_ads()
# -------------------------------------------------------------------

def match_new_ads(ads: List[Ad]) -> None:
    """
    Semantically match a list of newly scraped Ad ORM objects against all
    saved searches.  Sends in-app + email notifications on matches.

    Parameters
    ----------
    ads : list of Ad ORM instances (as returned by save_ads_to_db)
    """
    if not ads:
        return

    db = SessionLocal()
    try:
        saved_searches = get_all_saved_searches(db)
        if not saved_searches:
            logger.debug("[SemanticMatcher] No saved searches — nothing to match")
            return

        # ------------------------------------------------------------------
        # 1. Encode all new ads in one batch (fast GPU/CPU vectorisation)
        # ------------------------------------------------------------------
        ad_texts = [_ad_to_text(ad) for ad in ads]
        try:
            ad_embeddings = _encode(ad_texts)  # shape: [num_ads, D]
        except Exception as exc:
            logger.error("[SemanticMatcher] Failed to encode ads: %s", exc)
            _fallback_keyword_match(ads, saved_searches, db)
            return

        # ------------------------------------------------------------------
        # 2. Build query embedding matrix
        # ------------------------------------------------------------------
        search_ids: List[int] = []
        query_embeddings: List[np.ndarray] = []

        for search in saved_searches:
            try:
                emb = _get_query_embedding(search.id, search.query)
                search_ids.append(search.id)
                query_embeddings.append(emb)
            except Exception as exc:
                logger.warning(
                    "[SemanticMatcher] Could not encode search id=%d '%s': %s",
                    search.id, search.query, exc
                )

        if not query_embeddings:
            return

        q_matrix = np.stack(query_embeddings)  # shape: [num_searches, D]

        # ------------------------------------------------------------------
        # 3. Score matrix: cosine similarity (both sides are L2-normalised)
        #    scores[i, j] = similarity between ad i and search j
        # ------------------------------------------------------------------
        scores = ad_embeddings @ q_matrix.T  # shape: [num_ads, num_searches]

        # ------------------------------------------------------------------
        # 4. Notify on threshold hits
        # ------------------------------------------------------------------
        for ad_idx, ad in enumerate(ads):
            for q_idx, search_id in enumerate(search_ids):
                score = float(scores[ad_idx, q_idx])

                if score < MATCH_THRESHOLD:
                    continue

                # Find the original search object
                search = next(s for s in saved_searches if s.id == search_id)

                logger.info(
                    "[SemanticMatcher] MATCH score=%.3f  user=%d  ad='%s'  query='%s'",
                    score, search.user_id, ad.title, search.query,
                )

                try:
                    create_notification(
                        db=db,
                        user_id=search.user_id,
                        ad_id=ad.id,
                        message=(
                            f"New ad found for '{search.query}' "
                            f"(similarity: {score:.0%})"
                        ),
                    )
                except Exception as exc:
                    logger.error("[SemanticMatcher] create_notification failed: %s", exc)
                    continue

                user = get_user_by_id(db, search.user_id)
                if user and user.email:
                    try:
                        send_email_notification(
                            to_email=user.email,
                            ad_title=ad.title,
                            ad_link=ad.link,
                            query=search.query,
                        )
                    except Exception as exc:
                        logger.warning("[SemanticMatcher] Email failed for user %d: %s", user.id, exc)

    finally:
        db.close()


# -------------------------------------------------------------------
# Fallback: keyword matching (used if model is not yet loaded)
# -------------------------------------------------------------------

def _fallback_keyword_match(ads: List[Ad], saved_searches, db) -> None:
    """Simple substring fallback so notifications still fire even without the model."""
    logger.warning("[SemanticMatcher] Using keyword fallback")
    for ad in ads:
        title = (ad.title or "").lower()
        desc = (ad.description or "").lower()
        for search in saved_searches:
            query = (search.query or "").lower()
            if query in title or query in desc:
                try:
                    create_notification(
                        db=db,
                        user_id=search.user_id,
                        ad_id=ad.id,
                        message=f"New ad found for '{search.query}' (keyword match)",
                    )
                    user = get_user_by_id(db, search.user_id)
                    if user and user.email:
                        send_email_notification(
                            to_email=user.email,
                            ad_title=ad.title,
                            ad_link=ad.link,
                            query=search.query,
                        )
                except Exception as exc:
                    logger.error("[SemanticMatcher] Fallback notification failed: %s", exc)

# from app.database.db import SessionLocal
#
# from app.database.repository import (
#     get_all_saved_searches,
#     create_notification,
#     get_user_by_id
# )
#
# from app.notifications.email_service import send_email_notification
#
#
# def match_new_ads(ads):
#     db = SessionLocal()
#
#     try:
#         saved_searches = get_all_saved_searches(db)
#
#         for ad in ads:
#             title = (ad.title or "").lower()
#             description = (ad.description or "").lower()
#
#             for search in saved_searches:
#                 query = (search.query or "").lower()
#
#                 if query in title or query in description:
#                     notification = create_notification(
#                         db=db,
#                         user_id=search.user_id,
#                         ad_id=ad.id,
#                         message=f"New ad found for '{search.query}'"
#                     )
#
#                     print(f"[MATCH] User {search.user_id} matched ad '{ad.title}'")
#
#                     user = get_user_by_id(db, search.user_id)
#
#                     if user and user.email:
#                         send_email_notification(
#                             to_email=user.email,
#                             ad_title=ad.title,
#                             ad_link=ad.link,
#                             query=search.query
#                         )
#
#     finally:
#         db.close()
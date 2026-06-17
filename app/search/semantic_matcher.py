from __future__ import annotations

import re
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
from app.search.search_service import keyword_evidence_score, passes_price, passes_location

logger = logging.getLogger(__name__)


MATCH_THRESHOLD: float = 0.65


_query_cache: Dict[int, np.ndarray] = {}




def _get_model():

    from app.search.semantic_engine import _get_model as engine_get_model
    return engine_get_model()


def _ad_to_text(ad: Ad) -> str:

    parts = [
        str(ad.title or ""),
        str(ad.description or ""),
        str(ad.price or ""),
        str(ad.source or ""),
    ]
    return " ".join(p for p in parts if p).strip()


def _encode(texts: List[str]) -> np.ndarray:

    model = _get_model()
    return model.encode(
        texts,
        batch_size=64,
        normalize_embeddings=True,
        show_progress_bar=False,
    )


def _get_query_embedding(search_id: int, query: str) -> np.ndarray:

    if search_id not in _query_cache:
        emb = _encode([query])[0]
        _query_cache[search_id] = emb
        logger.debug("[SemanticMatcher] Encoded query id=%d: '%s'", search_id, query)
    return _query_cache[search_id]


def invalidate_query_cache(search_id: Optional[int] = None) -> None:

    if search_id is None:
        _query_cache.clear()
        logger.info("[SemanticMatcher] Full query cache cleared")
    else:
        _query_cache.pop(search_id, None)
        logger.info("[SemanticMatcher] Query cache cleared for search_id=%d", search_id)



def numbers_in_text(text: str):
    return re.findall(r"\d+", (text or "").lower())


def passes_strict_number_guard(query: str, ad_text: str) -> bool:
    query_numbers = numbers_in_text(query)

    if not query_numbers:
        return True

    ad_numbers = numbers_in_text(ad_text)

    for number in query_numbers:
        if number not in ad_numbers:
            return False

    return True

def match_new_ads(ads: List[Ad]) -> None:

    if not ads:
        return

    db = SessionLocal()
    try:
        saved_searches = get_all_saved_searches(db)
        if not saved_searches:
            logger.debug("[SemanticMatcher] No saved searches — nothing to match")
            return


        ad_texts = [_ad_to_text(ad) for ad in ads]
        try:
            ad_embeddings = _encode(ad_texts)  # shape: [num_ads, D]
        except Exception as exc:
            logger.error("[SemanticMatcher] Failed to encode ads: %s", exc)
            _fallback_keyword_match(ads, saved_searches, db)
            return


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

        q_matrix = np.stack(query_embeddings)

        scores = ad_embeddings @ q_matrix.T


        for ad_idx, ad in enumerate(ads):
            for q_idx, search_id in enumerate(search_ids):
                score = float(scores[ad_idx, q_idx])

                if score < MATCH_THRESHOLD:
                    continue


                search = next(s for s in saved_searches if s.id == search_id)

                ad_text = _ad_to_text(ad).lower()

                if not passes_strict_number_guard(search.query, ad_text):
                    continue

                ad_dict = {
                    "title": ad.title,
                    "description": ad.description,
                    "price": ad.price,
                    "link": ad.link,
                    "source": ad.source,
                }

                evidence_score = keyword_evidence_score(search.query, ad_dict)

                if score < 0.78 and evidence_score <= 0:
                    continue

                if not passes_price(search.query, ad_dict):
                    continue

                if not passes_location(search.query, ad_dict):
                    continue

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



def _fallback_keyword_match(ads: List[Ad], saved_searches, db) -> None:

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

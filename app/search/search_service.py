from sqlalchemy import or_

from app.database.db import SessionLocal
from app.database.models import Ad

from app.search.semantic_engine import semantic_search, is_ready




def keyword_search_db(query: str, limit: int = 20):

    db = SessionLocal()

    try:

        results = db.query(Ad).filter(
            or_(
                Ad.title.ilike(f"%{query}%"),
                Ad.description.ilike(f"%{query}%"),
                Ad.price.ilike(f"%{query}%"),
            )
        ).limit(limit).all()

        ads = []

        for ad in results:

            ads.append({
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "link": ad.link,
                "source": ad.source,
            })

        return ads

    finally:

        db.close()


def search_ads(query: str, limit: int = 20):

    keyword_results = keyword_search_db(
        query=query,
        limit=limit
    )

    semantic_results = []

    try:

        if is_ready():

            semantic_results = semantic_search(
                query=query,
                limit=limit
            )

    except Exception as e:

        print(f"[Semantic Error] {e}")

    merged = []
    seen = set()

    for item in keyword_results + semantic_results:

        link = item.get("link")

        if link in seen:
            continue

        seen.add(link)

        merged.append(item)

    return merged[:limit]
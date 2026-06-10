from app.database.db import SessionLocal

from app.database.repository import (
    get_all_saved_searches,
    create_notification
)

def match_new_ads(ads):

    db = SessionLocal()

    try:

        saved_searches = get_all_saved_searches(db)

        for ad in ads:

            title = (ad.title or "").lower()
            description = (ad.description or "").lower()

            for search in saved_searches:

                query = search.query.lower()

                if query in title or query in description:

                    create_notification(
                        db=db,
                        user_id=search.user_id,
                        ad_id=ad.id,
                        message=f"New ad found for '{search.query}'"
                    )

                    print(
                        f"[MATCH] User {search.user_id} matched ad '{ad.title}'"
                    )

    finally:
        db.close()
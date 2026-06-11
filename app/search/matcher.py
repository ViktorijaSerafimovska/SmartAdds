from app.database.db import SessionLocal

from app.database.repository import (
    get_all_saved_searches,
    create_notification,
    get_user_by_id
)

from app.notifications.email_service import send_email_notification


def match_new_ads(ads):
    db = SessionLocal()

    try:
        saved_searches = get_all_saved_searches(db)

        for ad in ads:
            title = (ad.title or "").lower()
            description = (ad.description or "").lower()

            for search in saved_searches:
                query = (search.query or "").lower()

                if query in title or query in description:
                    notification = create_notification(
                        db=db,
                        user_id=search.user_id,
                        ad_id=ad.id,
                        message=f"New ad found for '{search.query}'"
                    )

                    print(f"[MATCH] User {search.user_id} matched ad '{ad.title}'")

                    user = get_user_by_id(db, search.user_id)

                    if user and user.email:
                        send_email_notification(
                            to_email=user.email,
                            ad_title=ad.title,
                            ad_link=ad.link,
                            query=search.query
                        )

    finally:
        db.close()
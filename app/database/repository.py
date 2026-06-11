#
# from sqlalchemy.exc import IntegrityError
#
# from app.database.db import SessionLocal
# from app.database.models import Ad, SavedSearch, Notification, User
#
#
# def save_ads_to_db(ads):
#     db = SessionLocal()
#     new_ads = []
#
#     try:
#         for item in ads:
#             link = item.get("link", "")
#
#             if not link:
#                 continue
#
#             exists = db.query(Ad).filter(Ad.link == link).first()
#
#             if exists:
#                 continue
#
#             ad = Ad(
#                 title=item.get("title", ""),
#                 description=item.get("description", ""),
#                 price=item.get("price", ""),
#                 link=link,
#                 source=item.get("source", ""),
#             )
#
#             db.add(ad)
#             new_ads.append(ad)
#
#         db.commit()
#
#         for ad in new_ads:
#             db.refresh(ad)
#
#         return new_ads
#
#     except IntegrityError as e:
#         db.rollback()
#         print(f"[DB ERROR] IntegrityError: {e}")
#         return []
#
#     except Exception as e:
#         db.rollback()
#         print(f"[DB ERROR] {e}")
#         return []
#
#     finally:
#         db.close()
#
#
# def get_all_ads():
#     db = SessionLocal()
#
#     try:
#         ads = db.query(Ad).all()
#
#         result = []
#
#         for ad in ads:
#             result.append({
#                 "id": ad.id,
#                 "title": ad.title,
#                 "description": ad.description,
#                 "price": ad.price,
#                 "link": ad.link,
#                 "source": ad.source,
#             })
#
#         return result
#
#     finally:
#         db.close()
#
#
# def save_search(user_id: int, query: str):
#     db = SessionLocal()
#
#     try:
#         saved_search = SavedSearch(
#             user_id=user_id,
#             query=query
#         )
#
#         db.add(saved_search)
#         db.commit()
#         db.refresh(saved_search)
#
#         return saved_search
#
#     finally:
#         db.close()
#
#
# def get_all_saved_searches(db):
#     return db.query(SavedSearch).all()
#
#
# def create_notification(db, user_id: int, ad_id: int, message: str):
#     notification = Notification(
#         user_id=user_id,
#         ad_id=ad_id,
#         message=message
#     )
#
#     db.add(notification)
#     db.commit()
#     db.refresh(notification)
#
#     return notification
#
#
#
#
# def get_user_notifications(user_id: int):
#     db = SessionLocal()
#
#     try:
#         notifications = (
#             db.query(Notification)
#             .filter(Notification.user_id == user_id)
#             .order_by(Notification.created_at.desc())
#             .all()
#         )
#
#         result = []
#
#         for n in notifications:
#             result.append({
#                 "id": n.id,
#                 "user_id": n.user_id,
#                 "ad_id": n.ad_id,
#                 "message": n.message,
#                 "is_read": n.is_read,
#                 "created_at": n.created_at,
#             })
#
#         return result
#
#     finally:
#         db.close()
from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.database.models import Ad, SavedSearch, Notification, User


def save_ads_to_db(ads):
    db = SessionLocal()
    new_ads = []

    try:
        for item in ads:
            link = item.get("link", "")

            if not link:
                continue

            exists = db.query(Ad).filter(Ad.link == link).first()

            if exists:
                continue

            ad = Ad(
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=item.get("price", ""),
                link=link,
                source=item.get("source", ""),
            )

            db.add(ad)
            new_ads.append(ad)

        db.commit()

        for ad in new_ads:
            db.refresh(ad)

        return new_ads

    except IntegrityError as e:
        db.rollback()
        print(f"[DB ERROR] IntegrityError: {e}")
        return []

    except Exception as e:
        db.rollback()
        print(f"[DB ERROR] {e}")
        return []

    finally:
        db.close()


def get_all_ads():
    db = SessionLocal()

    try:
        ads = db.query(Ad).all()

        result = []

        for ad in ads:
            result.append({
                "id": ad.id,
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "link": ad.link,
                "source": ad.source,
            })

        return result

    finally:
        db.close()


def save_search(user_id: int, query: str):
    db = SessionLocal()

    try:
        saved_search = SavedSearch(
            user_id=user_id,
            query=query
        )

        db.add(saved_search)
        db.commit()
        db.refresh(saved_search)

        return saved_search

    finally:
        db.close()


def get_all_saved_searches(db):
    return db.query(SavedSearch).all()


def get_user_by_id(db, user_id: int):
    return (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )


def create_notification(db, user_id: int, ad_id: int, message: str):
    existing = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.ad_id == ad_id
        )
        .first()
    )

    if existing:
        return existing

    notification = Notification(
        user_id=user_id,
        ad_id=ad_id,
        message=message,
        is_read=False
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def get_user_notifications(user_id: int):
    db = SessionLocal()

    try:
        notifications = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .all()
        )

        result = []

        for n in notifications:
            result.append({
                "id": n.id,
                "user_id": n.user_id,
                "ad_id": n.ad_id,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at,
            })

        return result

    finally:
        db.close()
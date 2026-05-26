from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.database.models import Ad


def save_ads_to_db(ads):

    db = SessionLocal()

    try:
        for item in ads:

            exists = db.query(Ad).filter(
                Ad.link == item["link"]
            ).first()

            if exists:
                continue

            ad = Ad(
                title=item.get("title", ""),
                description=item.get("description", ""),
                price=item.get("price", ""),
                link=item.get("link", ""),
                source=item.get("source", ""),
            )

            db.add(ad)

        db.commit()

    except IntegrityError:
        db.rollback()

    finally:
        db.close()


def get_all_ads():

    db = SessionLocal()

    try:
        ads = db.query(Ad).all()

        result = []

        for ad in ads:
            result.append({
                "title": ad.title,
                "description": ad.description,
                "price": ad.price,
                "link": ad.link,
                "source": ad.source,
            })

        return result

    finally:
        db.close()
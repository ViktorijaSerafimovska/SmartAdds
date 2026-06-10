# from app.mcp.mcp_client import search_ads
#
# results = search_ads("golf 7", 5)
#
# print(results)

from app.database.db import SessionLocal
from app.database.models import User, SavedSearch

db = SessionLocal()

try:
    user = db.query(User).filter(User.email == "test@test.com").first()

    if not user:
        user = User(
            username="testuser",
            email="test@test.com",
            password_hash="test123"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    saved_search = SavedSearch(
        user_id=user.id,
        query="стан"
    )

    db.add(saved_search)
    db.commit()

    print("User created/found:", user.id)
    print("Saved search created:", saved_search.query)

finally:
    db.close()
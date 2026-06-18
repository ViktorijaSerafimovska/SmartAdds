from app.database.db import engine, Base

import app.database.models

Base.metadata.create_all(bind=engine)

print("Tables created")
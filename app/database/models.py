from sqlalchemy import Column, Integer, String, Text

from app.database.db import Base


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)
    description = Column(Text, default="")
    price = Column(String, default="")
    link = Column(String, unique=True, nullable=False)
    source = Column(String, nullable=False)
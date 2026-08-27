from sqlalchemy import Column, Integer, String, Float
from app.database.connection import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(
        String(100),
        nullable=False
    )

    address = Column(
        String(255),
        nullable=True
    )

    latitude = Column(
        Float,
        nullable=True
    )

    longitude = Column(
        Float,
        nullable=True
    )

    contact_number = Column(
        String(20),
        nullable=True
    )
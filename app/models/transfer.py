from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

from app.database.connection import Base


class TransferRecommendation(Base):
    __tablename__ = "transfer_recommendations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    source_hospital_id = Column(
        Integer,
        nullable=False
    )

    destination_hospital_id = Column(
        Integer,
        nullable=False
    )

    item_name = Column(
        String(100),
        nullable=False
    )

    recommended_units = Column(
        Integer,
        nullable=False
    )

    priority = Column(
        String(50),
        nullable=True
    )

    distance = Column(
        Float,
        nullable=True
    )

    transfer_time = Column(
        Float,
        nullable=True
    )

    expiry_risk = Column(
        Float,
        nullable=True
    )

    status = Column(
        String(50),
        default="recommended"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class TransferTransaction(Base):
    __tablename__ = "transfer_transactions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    recommendation_id = Column(
        Integer,
        nullable=True
    )

    source_hospital_id = Column(
        Integer,
        nullable=False
    )

    destination_hospital_id = Column(
        Integer,
        nullable=False
    )

    item_name = Column(
        String(100),
        nullable=False
    )

    units = Column(
        Integer,
        nullable=False
    )

    status = Column(
        String(50),
        default="pending"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
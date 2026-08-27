from sqlalchemy import Column, Integer, String, Float, Date
from app.database.connection import Base


class DemandHistory(Base):
    __tablename__ = "demand_history"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_id = Column(
        Integer,
        nullable=False
    )

    item_name = Column(
        String(100),
        nullable=False
    )

    demand_date = Column(
        Date,
        nullable=False
    )

    quantity_demanded = Column(
        Integer,
        nullable=False
    )


class DemandPrediction(Base):
    __tablename__ = "demand_predictions"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    hospital_id = Column(
        Integer,
        nullable=False
    )

    item_name = Column(
        String(100),
        nullable=False
    )

    prediction_date = Column(
        Date,
        nullable=False
    )

    predicted_quantity = Column(
        Integer,
        nullable=False
    )

    confidence = Column(
        Float,
        nullable=True
    )
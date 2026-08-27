from sqlalchemy import Column, Integer, String, Float, Date
from app.database.connection import Base


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

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

    batch_number = Column(
        String(100),
        nullable=False
    )

    quantity = Column(
        Integer,
        nullable=False
    )

    expiry_date = Column(
        Date,
        nullable=True
    )

    unit_cost = Column(
        Float,
        nullable=True
    )
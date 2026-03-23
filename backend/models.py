from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(20), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # CALL or PUT
    amount = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False)
    expiry_seconds = Column(Integer, nullable=False)
    result = Column(String(10), default="PENDING")  # WIN, LOSS, PENDING
    pnl = Column(Float, default=0.0)
    mode = Column(String(10), default="demo")  # demo or live
    order_id = Column(String(100), nullable=True)
    entry_price = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "asset": self.asset,
            "direction": self.direction,
            "amount": self.amount,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "expiry_seconds": self.expiry_seconds,
            "result": self.result,
            "pnl": self.pnl,
            "mode": self.mode,
            "order_id": self.order_id,
            "entry_price": self.entry_price,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(20), nullable=False, index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "asset": self.asset,
            "price": self.price,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

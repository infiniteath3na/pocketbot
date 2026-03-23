from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./pocketbot.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import Trade, Settings, PriceSnapshot  # noqa: F401
    Base.metadata.create_all(bind=engine)


def init_default_settings(db):
    from models import Settings
    defaults = {
        "mode": "demo",
        "trade_size": "10",
        "confidence_threshold": "70",
        "daily_loss_limit": "100",
        "max_concurrent_trades": "3",
        "min_trade_interval": "5",
        "auto_trade": "false",
        "refresh_interval": "30",
        "enabled_assets": "EURUSD,GBPUSD,USDJPY,AUDUSD,XAUUSD,BTCUSD,ETHUSD",
        "ssid_demo": "",
        "ssid_live": "",
        "bot_running": "false",
    }
    for key, value in defaults.items():
        existing = db.query(Settings).filter(Settings.key == key).first()
        if not existing:
            setting = Settings(key=key, value=value)
            db.add(setting)
    db.commit()

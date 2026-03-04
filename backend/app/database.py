from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Ensure SSL mode is set for production PostgreSQL
database_url = settings.DATABASE_URL

# Render PostgreSQL requires sslmode=require
if database_url and "render.com" in database_url and "sslmode" not in database_url:
    separator = "&" if "?" in database_url else "?"
    database_url = f"{database_url}{separator}sslmode=require"

# Also handle the postgres:// vs postgresql:// issue (Render uses postgres://)
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    database_url,
    pool_pre_ping=True,           # Test connections before using them
    pool_recycle=300,              # Recycle connections every 5 minutes
    pool_size=5,                   # Keep 5 connections in pool
    max_overflow=10,               # Allow 10 extra connections under load
    connect_args={
        "connect_timeout": 10,     # 10 second connection timeout
        "keepalives": 1,           # Enable TCP keepalives
        "keepalives_idle": 30,     # Send keepalive after 30s idle
        "keepalives_interval": 10, # Retry keepalive every 10s
        "keepalives_count": 5,     # Give up after 5 failed keepalives
    } if "postgresql" in (database_url or "") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables with retry logic."""
    import time
    max_retries = 5
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                logger.warning(f"DB connection attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
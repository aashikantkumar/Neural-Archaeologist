from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Fix DATABASE_URL if it uses postgres:// (Render gives old format)
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},  # ✅ SSL fix
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
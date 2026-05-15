"""Database initialization and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLSession
from sqlalchemy.ext.declarative import declarative_base

# Database URL - SQLite for local development, can be updated for production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cloud_analytics.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db() -> SQLSession:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=engine)

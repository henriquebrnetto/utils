"""Database connection utilities for GreenThumb."""
import os
from contextlib import asynccontextmanager
from typing import Any, Generator

from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy import Engine

# Default to PostgreSQL, fallback to SQLite for local development
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///./database.db"
)

_engine: Engine | None = None


def get_engine(echo: bool = False) -> Engine:
    """Get or create the database engine.
    
    Args:
        echo: Whether to echo SQL statements (for debugging)
        
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    if _engine is None:
        connect_args = {}
        if DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(DATABASE_URL, echo=echo, connect_args=connect_args)
    return _engine


def get_session() -> Generator[Session, None, None]:
    """Get a database session.
    
    Yields:
        SQLModel Session
    """
    engine = get_engine()
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    """Create all database tables defined in SQLModel metadata."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app: Any):
    """FastAPI lifespan context manager for database setup/teardown.
    
    Args:
        app: FastAPI application instance
    """
    create_db_and_tables()
    yield
    print("Shutting down...")
    engine = get_engine()
    engine.dispose()
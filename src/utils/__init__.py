"""Utilities library.

Provides database connection management and CRUD operations for SQLModel objects.
The FastAPI router lives in utils.api and is optional.
"""

# Connection utilities
from .db import (
    DATABASE_URL,
    get_engine,
    get_session,
    create_db_and_tables,
    lifespan,
)

# Exceptions
from .db_utils import (
    DatabaseError,
    NotFoundError,
    ValidationError,
)

# Decorators
from .db_utils import (
    db_error,
    db_commit,
)

# CRUD operations
from .db_utils import (
    get,
    get_by_id,
    save,
    save_all,
    delete,
    update,
    get_or_create,
    get_or_convert,
)

__all__ = [
    # Connection
    "DATABASE_URL",
    "get_engine",
    "get_session",
    "create_db_and_tables",
    "lifespan",
    # Exceptions
    "DatabaseError",
    "NotFoundError",
    "ValidationError",
    # Decorators
    "db_error",
    "db_commit",
    # CRUD
    "get",
    "get_by_id",
    "save",
    "save_all",
    "delete",
    "update",
    "get_or_create",
    "get_or_convert",
]

# utils

Lightweight utilities for working with SQLModel/SQLAlchemy sessions plus an optional FastAPI CRUD router. Core helpers stay framework-agnostic; the API layer is opt-in via the `api` extra.

## What's inside
- Database engine/session helpers (create engine, yield `Session`, create tables)
- CRUD helpers (`get`, `get_by_id`, `save`, `save_all`, `update`, `delete`, `get_or_create`, `get_or_convert`)
- Error and commit decorators (`db_error`, `db_commit`)
- Optional FastAPI router factory (`make_crud_router` in `utils.api`) that wires standard CRUD endpoints for a SQLModel.

## Requirements
- Python >= 3.11
- Core deps: `sqlmodel`, `sqlalchemy`, `psycopg2-binary`
- Optional API extra adds: `fastapi`

## Installation

### Core only
```bash
pip install .
```

### With FastAPI CRUD router
```bash
pip install .[api]
```

## Usage

### Configure and create the database
```python
from utils import DATABASE_URL, create_db_and_tables, get_engine

# DATABASE_URL is read from the environment (falls back to sqlite:///./database.db)
engine = get_engine(echo=False)
create_db_and_tables()
```

### Basic CRUD helpers
```python
from typing import Optional
from sqlmodel import SQLModel, Field
from utils import get_session, save, get, get_by_id, update, delete

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

# Create
with next(get_session()) as session:
    item = save(session, Item(name="hello"))

# Read
with next(get_session()) as session:
    all_items = get(session, Item)
    first = get_by_id(session, Item, item.id)

# Update (using another SQLModel/Pydantic object with updates)
class ItemUpdate(SQLModel):
    name: str

with next(get_session()) as session:
    updated = update(session, Item, item.id, ItemUpdate(name="updated"))

# Delete
with next(get_session()) as session:
    delete(session, Item, item.id)
```

### Using the FastAPI CRUD router (optional extra)
```python
from fastapi import FastAPI
from sqlmodel import SQLModel, Field
from utils.api import make_crud_router
from utils import get_session

class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str

class BookCreate(SQLModel):
    title: str

class BookRead(SQLModel):
    id: int
    title: str

class BookUpdate(SQLModel):
    title: str

app = FastAPI()
book_router = make_crud_router(
    model=Book,
    create_schema=BookCreate,
    read_schema=BookRead,
    update_schema=BookUpdate,
    prefix="/books",
    tags=["books"],
)
app.include_router(book_router)
```

### Lifespan helper for FastAPI (core)
```python
from fastapi import FastAPI
from utils import lifespan

app = FastAPI(lifespan=lifespan)
```

## Notes
- Imports are designed so `import utils` works without FastAPI; only the `utils.api` module requires the `api` extra.
- Default DB URL is `DATABASE_URL` env var (PostgreSQL expected); otherwise falls back to SQLite for local use.
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from .db import get_session
from .db_utils import db_commit, delete, get, get_by_id, save, update

def make_crud_router(
    model: Any,
    create_schema: Any,
    read_schema: Any,
    update_schema: Any,
    prefix: str,
    tags: Optional[List[str]] = None
) -> APIRouter:
    """
    Create a CRUD router for a given SQLModel.
    Commits changes using @db_commit decorator.
    Inherits error handling from @db_error decorator.

    Args:
        model (Any): The SQLModel class to create the router for.
        create_schema (Any): The Pydantic schema for creating new instances.
        read_schema (Any): The Pydantic schema for reading instances.

    Returns:
        APIRouter: The FastAPI router with CRUD endpoints.
    """
    router = APIRouter(prefix=prefix, tags=tags)

    # GET ALL
    @router.get("/", response_model=List[read_schema])
    def list_items(session: Session = Depends(get_session)):
        return get(session, model)

    # GET BY ID
    @router.get("/{id}/{id2}", response_model=read_schema)
    def read_item(id: int, id2: Optional[int] = None, session: Session = Depends(get_session)):
        if id2 is not None:
            return get_by_id(session, model, (id, id2))
        return get_by_id(session, model, id)

    # CREATE
    @router.post("/", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    @db_commit
    def create_item(payload: create_schema, session: Session = Depends(get_session)):
        return save(session, model(**payload.model_dump()))

    # UPDATE
    @router.put("/{id}", response_model=read_schema)
    @db_commit
    def update_item(id: int, payload: update_schema, session: Session = Depends(get_session)):
        return update(session, model, id, payload)

    # DELETE
    @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
    @db_commit
    def delete_item(id: int, session: Session = Depends(get_session)):
        return delete(session, model, id)
    
    return router
from typing import Any, List, Optional, Union, get_args, get_origin

from fastapi import APIRouter, Depends, Query, Request, status
from sqlmodel import Session

from .db import get_session
from .db_utils import db_commit, delete, get, get_by_id, save, update


def _coerce(annotation: Any, value: str) -> Any:
    """Cast a string query-param value to the field's Python type."""
    origin = get_origin(annotation)
    if origin is Union:
        inner = [a for a in get_args(annotation) if a is not type(None)]
        annotation = inner[0] if inner else str
    try:
        if annotation is int:
            return int(value)
        if annotation is float:
            return float(value)
        if annotation is bool:
            return value.lower() in ('true', '1', 'yes')
    except (ValueError, TypeError):
        pass
    return value


def make_crud_router(
    model: Any,
    create_schema: Any,
    read_schema: Any,
    update_schema: Any,
    prefix: str,
    tags: Optional[List[str]] = None,
    pk_fields: Optional[List[str]] = None,
) -> APIRouter:
    """
    Create a CRUD router for a given SQLModel.
    Commits changes using @db_commit decorator.
    Inherits error handling from @db_error decorator.

    The list endpoint (GET /) supports optional query parameters:
      - Any model field name → equality filter (e.g. ?id_device=1)
      - order_by → comma-separated field names, prefix with '-' for DESC
      - limit → maximum number of rows returned

    Args:
        model: The SQLModel class to create the router for.
        create_schema: The Pydantic schema for creating new instances.
        read_schema: The Pydantic schema for reading instances.
        update_schema: The Pydantic schema for updating instances.
        prefix: URL prefix for all routes.
        tags: Optional OpenAPI tags.
        pk_fields: Optional list of composite PK field names.

    Returns:
        APIRouter: The FastAPI router with CRUD endpoints.
    """
    router = APIRouter(prefix=prefix, tags=tags)

    _model_fields = model.model_fields  # Pydantic v2 field map
    _reserved = frozenset(('order_by', 'limit'))

    # GET ALL
    @router.get("", response_model=List[read_schema])
    def list_items(
        request: Request,
        order_by: Optional[str] = Query(None, description="Comma-separated field names; prefix with '-' for DESC"),
        limit: Optional[int] = Query(None, ge=1, le=10000),
        session: Session = Depends(get_session),
    ):
        filters: dict = {}
        for key, value in request.query_params.items():
            if key in _reserved or key not in _model_fields:
                continue
            filters[key] = _coerce(_model_fields[key].annotation, value)
        return get(
            session, model,
            filters=filters or None,
            order_by=order_by.split(',') if order_by else None,
            limit=limit,
        )

    # GET BY ID — composite PK if pk_fields has 2 entries, otherwise single int PK
    if pk_fields and len(pk_fields) == 2:
        _pk1, _pk2 = pk_fields

        @router.get(f"/{{{_pk1}}}/{{{_pk2}}}", response_model=read_schema)
        def read_item_composite(request: Request, session: Session = Depends(get_session)):
            return get_by_id(session, model, (int(request.path_params[_pk1]), int(request.path_params[_pk2])))
    else:
        @router.get("/{id}", response_model=read_schema)
        def read_item(id: int, session: Session = Depends(get_session)):
            return get_by_id(session, model, id)

    # CREATE
    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    @db_commit
    def create_item(payload: create_schema, session: Session = Depends(get_session)):
        return save(session, model(**payload.model_dump()))

    # UPDATE
    @router.put("/{id}", response_model=read_schema)
    @db_commit
    def update_item(id: int, payload: update_schema, session: Session = Depends(get_session)):
        return update(session, model, id, payload)

    # DELETE — composite PK or single PK
    if pk_fields and len(pk_fields) == 2:
        pk1, pk2 = pk_fields
        _globs: dict = {
            "Session": Session,
            "Depends": Depends,
            "get_session": get_session,
            "db_commit": db_commit,
            "delete": delete,
            "_model": model,
        }
        exec(
            textwrap.dedent(f"""
                @db_commit
                def _delete_composite(
                    {pk1}: int,
                    {pk2}: int,
                    session: Session = Depends(get_session),
                ):
                    return delete(session, _model, ({pk1}, {pk2}))
            """),
            _globs,
        )
        router.delete(
            f"/{{{pk1}}}/{{{pk2}}}",
            status_code=status.HTTP_204_NO_CONTENT,
        )(_globs["_delete_composite"])
    else:
        @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
        @db_commit
        def delete_item(id: int, session: Session = Depends(get_session)):
            return delete(session, model, id)

    return router

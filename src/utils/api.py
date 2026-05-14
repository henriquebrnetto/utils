"""FastAPI CRUD router factory."""
import textwrap
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Request, status
from sqlmodel import Session

from .db import get_session
from .db_utils import db_commit, delete, get, get_by_id, save, update


def make_crud_router(
    model: Any,
    create_schema: Any,
    read_schema: Any,
    update_schema: Any,
    prefix: str,
    tags: Optional[List[str]] = None,
    pk_fields: Optional[List[str]] = None,
) -> APIRouter:
    """Create a CRUD router for a given SQLModel.

    Args:
        pk_fields: When provided with 2 field names (e.g. ["id_sensor_model",
                   "id_variable"]), the DELETE route accepts both as path params
                   and passes a tuple to db_utils.delete(). Omit for the default
                   single-integer PK behaviour.
    """
    router = APIRouter(prefix=prefix, tags=tags)

    # GET ALL
    @router.get("", response_model=List[read_schema])
    def list_items(request: Request, session: Session = Depends(get_session)):
        _meta = {"limit", "offset", "order_by"}
        filters = {k: v for k, v in request.query_params.items()
                   if k not in _meta and hasattr(model, k)} or None
        return get(session, model, filters=filters)

    # GET BY ID
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

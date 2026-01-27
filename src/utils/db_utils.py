"""Database utility functions for GreenThumb.

This module provides CRUD operations and query helpers for SQLModel objects.
These are framework-agnostic utilities that can be used with FastAPI, Flask, or standalone.
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import functools

from sqlmodel import Session, select


class DatabaseError(Exception):
    """Base exception for database operations."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(DatabaseError):
    """Raised when a requested resource is not found."""
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class ValidationError(DatabaseError):
    """Raised when validation fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


def _build_clauses(model: Any, filters: Dict[str, Any]) -> list:
    """Build SQLAlchemy WHERE clauses from a filter dictionary.
    
    Supports operators via double-underscore notation:
    - field__eq: equals (default)
    - field__ne: not equals
    - field__lt, field__lte: less than (or equal)
    - field__gt, field__gte: greater than (or equal)
    - field__in: in list
    - field__contains: LIKE '%value%'
    - field__like: custom LIKE pattern
    
    Args:
        model: SQLModel class
        filters: Dictionary of field__operator -> value
        
    Returns:
        List of SQLAlchemy clause objects
    """
    clauses = []
    for raw_key, value in filters.items():
        if "__" in raw_key:
            field, op = raw_key.split("__", 1)
        else:
            field, op = raw_key, "eq"

        if not hasattr(model, field):
            raise ValidationError(f"Field '{field}' not found on {model.__name__}")

        col = getattr(model, field)

        if op == "eq":
            clauses.append(col == value)
        elif op == "ne":
            clauses.append(col != value)
        elif op == "lt":
            clauses.append(col < value)
        elif op == "lte":
            clauses.append(col <= value)
        elif op == "gt":
            clauses.append(col > value)
        elif op == "gte":
            clauses.append(col >= value)
        elif op == "in":
            if not isinstance(value, (list, tuple, set)):
                raise ValidationError(f"Value for '{raw_key}' must be a list/tuple for __in")
            clauses.append(col.in_(value))
        elif op == "contains":
            clauses.append(col.contains(value))
        elif op == "like":
            clauses.append(col.like(value))
        else:
            raise ValidationError(f"Unsupported filter operation: {op}")
    return clauses


def _order_by(order_by: List[str], obj: Any, query) -> Any:
    """Apply ordering to a query.
    
    Args:
        order_by: List of field names (prefix with '-' for descending)
        obj: SQLModel class
        query: SQLAlchemy query object
        
    Returns:
        Query with ordering applied
    """
    order_cols = []
    for o in order_by:
        if o.startswith("-"):
            fname = o[1:]
            if not hasattr(obj, fname):
                raise ValidationError(f"Order field '{fname}' not found")
            order_cols.append(getattr(obj, fname).desc())
        else:
            fname = o
            if not hasattr(obj, fname):
                raise ValidationError(f"Order field '{fname}' not found")
            order_cols.append(getattr(obj, fname))

    return query.order_by(*order_cols)


def db_error(func):
    """Decorator to wrap database errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(str(e))
    return wrapper


def _extract_session(args, kwargs):
    """Extract session from function arguments."""
    if "session" in kwargs and isinstance(kwargs["session"], Session):
        return kwargs["session"]
    if "db" in kwargs and isinstance(kwargs["db"], Session):
        return kwargs["db"]
    for a in args:
        if isinstance(a, Session):
            return a
    return None


def db_commit(func):
    """Decorator to auto-commit database operations.
    
    Automatically commits the session after the function executes,
    and rolls back on error.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = _extract_session(args, kwargs)
        try:
            result = func(*args, **kwargs)
            if session:
                session.commit()
            return result
        except Exception:
            if session:
                try:
                    session.rollback()
                except Exception:
                    pass
            raise
    return wrapper


@db_error
def get(
    session: Session,
    obj: Any,
    filters: Optional[Dict[str, Any]] = None,
    order_by: Optional[List[str]] = None,
    one_or_none: bool = False
) -> Optional[Any]:
    """Get objects from database.
    
    Args:
        session: Database session
        obj: SQLModel class to query
        filters: Optional filter dictionary
        order_by: Optional list of fields to order by
        one_or_none: If True, return single result or None
        
    Returns:
        List of objects, single object, or None
    """
    if isinstance(obj, list):
        stmt = select(*obj)
    else:
        stmt = select(obj)

    if filters:
        clauses = _build_clauses(obj, filters)
        if clauses:
            stmt = stmt.where(*clauses)

    if order_by:
        stmt = _order_by(order_by, obj, stmt)
    
    return session.exec(stmt).one_or_none() if one_or_none else session.exec(stmt).all()


@db_error
def get_by_id(session: Session, obj: Any, id: Union[int, Tuple[int, int]]) -> Optional[Any]:
    """Get object by primary key.
    
    Args:
        session: Database session
        obj: SQLModel class
        id: Primary key value (or tuple for composite keys)
        
    Returns:
        Object or None if not found
    """
    return session.get(obj, id)


@db_error
def save(session: Session, new_obj: Any | List[Any]) -> Any | List[Any]:
    """Save one or more objects to the database.
    
    Args:
        session: Database session
        new_obj: Object(s) to save
        
    Returns:
        Saved object(s) with ID populated
    """
    if not isinstance(new_obj, list):
        new_obj = [new_obj]

    session.add_all(new_obj)
    for obj in new_obj:
        session.flush()
        session.refresh(obj)
        
    return new_obj if len(new_obj) > 1 else new_obj[0]


@db_error
def delete(session: Session, obj: Any, id: Union[int, Tuple[int, int]]) -> bool:
    """Delete object by ID.
    
    Args:
        session: Database session
        obj: SQLModel class
        id: Primary key value
        
    Returns:
        True if deleted
        
    Raises:
        NotFoundError: If object not found
    """
    db_obj = session.get(obj, id)
    if not db_obj:
        raise NotFoundError(f"{obj.__name__} not found")
    session.delete(db_obj)
    return True


@db_error
def update(session: Session, obj: Any, id: Union[int, Tuple[int, int]], vals: Any) -> Any:
    """Update object by ID.
    
    Args:
        session: Database session
        obj: SQLModel class
        id: Primary key value
        vals: Pydantic/SQLModel object with new values
        
    Returns:
        Updated object
        
    Raises:
        NotFoundError: If object not found
    """
    db_result = session.get(obj, id)
    if not db_result:
        raise NotFoundError(f"{obj.__name__} not found")
    
    db_result_dict = db_result.model_dump()
    db_result_dict.update(vals.model_dump(exclude_unset=True))
    if "id" in db_result_dict:
        del db_result_dict["id"]

    for key, value in db_result_dict.items():
        setattr(db_result, key, value)

    session.add(db_result)
    session.refresh(db_result)
    return db_result


def get_or_create(session: Session, obj: Any, vals: Any, filters: dict) -> Any:
    """Get object from database or create if not exists.
    
    Args:
        session: Database session
        obj: SQLModel class
        vals: Values for creating new object
        filters: Filters to find existing object
        
    Returns:
        Existing or newly created object, None if filters contain None/empty values
    """
    for field, val in filters.items():
        if val in [None, ""]:
            return None
    
    if 'id' in filters:
        db_result = get_by_id(session, obj, filters['id'])
    else:
        db_result = get(session, obj, filters=filters, one_or_none=True)

    if not db_result:
        return save(session, obj(**vals))
    return db_result


def get_or_convert(session: Session, obj: Any, vals: Any, filters: dict) -> Any:
    """Get object from database or create instance (without saving).
    
    Args:
        session: Database session
        obj: SQLModel class
        vals: Values for creating new instance
        filters: Filters to find existing object
        
    Returns:
        Existing object or new unsaved instance, None if filters contain None/empty values
    """
    for field, val in filters.items():
        if val in [None, ""]:
            return None
    
    if 'id' in filters:
        db_result = get_by_id(session, obj, filters['id'])
    else:
        db_result = get(session, obj, filters=filters, one_or_none=True)

    if not db_result:
        return obj(**vals)
    return db_result
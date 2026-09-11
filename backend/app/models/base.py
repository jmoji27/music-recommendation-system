from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base — import this in every model module so
    Alembic's autogenerate can see all tables via Base.metadata."""

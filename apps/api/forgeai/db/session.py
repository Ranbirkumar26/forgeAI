from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from forgeai.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from forgeai.db import tables  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if settings.database_url.startswith("sqlite"):
        _migrate_sqlite_additive()


def _migrate_sqlite_additive() -> None:
    inspector = inspect(engine)
    if "repo_chunks" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("repo_chunks")}
    additions = {
        "symbol_path": "TEXT",
        "kind": "VARCHAR(60) DEFAULT 'file'",
        "start_line": "INTEGER DEFAULT 1",
        "end_line": "INTEGER DEFAULT 1",
        "signature": "TEXT",
        "docstring": "TEXT",
        "imports": "JSON DEFAULT '[]'",
    }
    with engine.begin() as connection:
        for name, ddl in additions.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE repo_chunks ADD COLUMN {name} {ddl}"))

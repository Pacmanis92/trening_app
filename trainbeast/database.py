import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DB_FILENAME = "trainbeast.db"


def default_db_path() -> Path:
    """Android: katalog danych aplikacji; komputer: katalog projektu."""
    storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if storage:
        Path(storage).mkdir(parents=True, exist_ok=True)
        return Path(storage) / DB_FILENAME
    return Path(__file__).resolve().parent.parent / DB_FILENAME


def make_engine(url: str | None = None) -> Engine:
    engine = create_engine(url or f"sqlite:///{default_db_path()}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)

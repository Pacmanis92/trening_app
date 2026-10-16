import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Exercise

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

    _migrate_exercise_category(engine)
    Base.metadata.create_all(engine)
    return engine


def _migrate_exercise_category(engine: Engine) -> None:
    """Jednorazowo: gdy exercise nie ma kolumny category, czyści dane i odtwarza tabelę.

    Na świeżej bazie (brak tabeli exercise) nic nie robi; po migracji warunek już nie zachodzi.
    """
    inspector = inspect(engine)
    if not inspector.has_table("exercise"):
        return
    if "category" in {c["name"] for c in inspector.get_columns("exercise")}:
        return
    with engine.begin() as conn:
        for table in ("workout_set", "workout_exercise", "workout", "exercise"):
            conn.execute(text(f"DELETE FROM {table}"))
    Exercise.__table__.drop(engine)  # create_all odtworzy ją z kolumną category


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)

import os
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Exercise, Workout, WorkoutExercise, WorkoutSet

DB_FILENAME = "trainbeast.db"


def default_db_path(env: Mapping[str, str] | None = None) -> Path:
    """Android: katalog danych aplikacji; komputer: katalog projektu."""
    storage = (os.environ if env is None else env).get("FLET_APP_STORAGE_DATA")
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
    _reset_workout_tables_for_units(engine)
    Base.metadata.create_all(engine)
    migrate_additive_columns(engine)
    normalize_exercise_positions(engine)
    return engine


# kolumny dodane po pierwszej wersji schematu: (tabela, kolumna, definicja SQL)
ADDITIVE_COLUMNS = (("workout_exercise", "note", "TEXT"),)


def migrate_additive_columns(engine: Engine) -> list[str]:
    """Dodaje brakujące kolumny (PRAGMA table_info + ALTER TABLE ADD COLUMN); idempotentne.

    Przed pierwszą zmianą robi kopię pliku bazy (.bak z datą). Zwraca nazwy dodanych kolumn."""
    with engine.connect() as conn:
        missing = []
        for table, column, ddl in ADDITIVE_COLUMNS:
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if existing and column not in existing:
                missing.append((table, column, ddl))
    if not missing:
        return []
    db_file = engine.url.database
    if db_file and db_file != ":memory:" and Path(db_file).is_file():
        engine.dispose()  # zamyka połączenia, żeby kopia była spójna
        shutil.copy2(db_file, _backup_path(Path(db_file)))
    with engine.begin() as conn:
        for table, column, ddl in missing:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    return [f"{t}.{c}" for t, c, _ in missing]


def normalize_exercise_positions(engine: Engine) -> int:
    """Porządkuje `position` ćwiczeń w każdym treningu do 0..n-1 wg dotychczasowej kolejności (position, id).

    Naprawia luki i duplikaty (po usunięciu ćwiczenia); ruszane są tylko wiersze o zmienionej pozycji, więc
    kolejne uruchomienie nic nie zmienia. Zwraca liczbę zmienionych wierszy."""
    changed = 0
    with engine.begin() as conn:
        if not inspect(conn).has_table("workout_exercise"):
            return 0
        rows = conn.exec_driver_sql(
            "SELECT id, workout_id, position FROM workout_exercise ORDER BY workout_id, position, id"
        ).all()
        current_workout, index = None, 0
        for row_id, workout_id, position in rows:
            index = index + 1 if workout_id == current_workout else 0
            current_workout = workout_id
            if position != index:
                conn.exec_driver_sql("UPDATE workout_exercise SET position = ? WHERE id = ?", (index, row_id))
                changed += 1
    return changed


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


def _backup_path(db_file: Path) -> Path:
    backup = db_file.with_name(db_file.name + ".bak")
    if backup.exists():  # nie nadpisuje wcześniejszej kopii
        backup = db_file.with_name(f"{db_file.name}.{datetime.now():%Y%m%d%H%M%S}.bak")
    return backup


def _reset_workout_tables_for_units(engine: Engine) -> None:
    """Jednorazowo: gdy workout_set nie ma kolumn jednostek, robi kopię pliku bazy (.bak obok oryginału),
    po czym usuwa i odtwarza tylko tabele treningów i serii (bez migracji). Ćwiczenia i kategorie zostają.

    Na świeżej bazie (brak tabeli workout_set) i po zmianie schematu nic nie robi.
    """
    inspector = inspect(engine)
    if not inspector.has_table("workout_set"):
        return
    if {"unit", "unit_minor"} <= {c["name"] for c in inspector.get_columns("workout_set")}:
        return
    db_file = engine.url.database
    if db_file and db_file != ":memory:" and Path(db_file).is_file():
        engine.dispose()  # zamyka połączenia, żeby kopia była spójna
        shutil.copy2(db_file, _backup_path(Path(db_file)))
    Base.metadata.drop_all(
        engine, tables=[WorkoutSet.__table__, WorkoutExercise.__table__, Workout.__table__]
    )  # create_all odtworzy je z nowym schematem


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)

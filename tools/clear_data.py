"""Jednorazowe czyszczenie bazy: usuwa wszystkie treningi i ćwiczenia własne.

Uruchom ręcznie: python tools/clear_data.py [ścieżka_do_bazy]
Ćwiczenia startowe oraz kategorie/sekcje zostają.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trainbeast.database import make_engine, make_session_factory  # noqa: E402
from trainbeast.services import TrainingService  # noqa: E402


def main() -> None:
    url = f"sqlite:///{Path(sys.argv[1]).resolve()}" if len(sys.argv) > 1 else None
    service = TrainingService(make_session_factory(make_engine(url)))
    for table, deleted in service.clear_user_data().items():
        print(f"{table}: usunięto {deleted}")


if __name__ == "__main__":
    main()

# TrainBeast

Lokalny, offline dziennik treningów siłowych (Python, Flet, SQLite/SQLAlchemy). Interfejs po polsku, jednostki w kg.

## Uruchomienie na komputerze

```
pip install -e ".[dev]"
python main.py
```

Baza `trainbeast.db` powstaje w katalogu projektu przy pierwszym uruchomieniu.
Na Androidzie używany jest katalog wskazany przez `FLET_APP_STORAGE_DATA`.

## Testy

```
python -m pytest
```

Testy używają osobnej, tymczasowej bazy SQLite.

## Budowanie na Androida

Aplikację można zbudować poleceniem `flet build apk` uruchomionym w katalogu projektu
(wymaga zainstalowanego Flutter SDK i Android SDK, które Flet może pobrać przy pierwszym budowaniu).
Zależności są brane z `pyproject.toml`. Wersja Flet jest przypięta do `1.0.4`.
Budowanie APK nie było testowane w tym repozytorium.

## Znane ograniczenia

- Brak edycji nazw ćwiczeń i brak usuwania własnych ćwiczeń z listy.
- Data treningu wpisywana ręcznie w formacie RRRR-MM-DD (bez kalendarza).
- Nie można usunąć ani edytować zakończonego treningu.
- Jednocześnie może istnieć wiele niezakończonych treningów; wznawiany jest najnowszy.
- Aplikacja nie była testowana na Androidzie ani iOS.
- Wygląd (motyw) zależy od ustawień systemu.

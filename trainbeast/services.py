import calendar
import math
import random
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, NamedTuple

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .models import Category, Exercise, Workout, WorkoutExercise, WorkoutSet

LOAD_TYPES = ("weight", "distance", "reps", "floors")
EFFORT_TYPES = ("reps", "time")

EMPTY_SUMMARY = "Brak wykonanych serii"
SEED_VERSION = 1  # PRAGMA user_version po zasianiu katalogu startowego

WR = ("weight", "reps")
WT = ("weight", "time")
DT = ("distance", "time")
FT = ("floors", "time")

STARTER_CATEGORIES = [
    "Chest (Klatka piersiowa)",
    "Back (Plecy)",
    "Shoulders (Barki)",
    "Biceps (Biceps)",
    "Triceps (Triceps)",
    "Legs (Nogi)",
    "Glutes (Pośladki)",
    "Core (Mięśnie brzucha i stabilizatorskie)",
    "Cardio (Trening kondycyjny)",
]

# kategoria -> [(nazwa EN, nazwa PL, pierwsza oś, druga oś)]
STARTER_EXERCISES: dict[str, list[tuple[str, str, str, str]]] = {
    STARTER_CATEGORIES[0]: [
        ("Barbell Bench Press", "Wyciskanie sztangi na ławce poziomej", *WR),
        ("Dumbbell Bench Press", "Wyciskanie hantli na ławce poziomej", *WR),
        ("Incline Barbell Press", "Wyciskanie sztangi na ławce skośnej dodatniej", *WR),
        ("Incline Dumbbell Press", "Wyciskanie hantli na ławce skośnej dodatniej", *WR),
        ("Decline Barbell Press", "Wyciskanie sztangi na ławce skośnej ujemnej", *WR),
        ("Decline Dumbbell Press", "Wyciskanie hantli na ławce skośnej ujemnej", *WR),
        ("Chest Press Machine", "Wyciskanie na maszynie siedząc", *WR),
        ("Pec Deck / Butterfly Machine", "Rozpiętki na maszynie", *WR),
        ("Dumbbell Flyes", "Rozpiętki z hantlami", *WR),
        ("Cable Flyes", "Rozpiętki na bramie / wyciągu", *WR),
        ("Push-ups", "Pompki klasyczne", *WR),
        ("Dips", "Pompki na poręczach", *WR),
    ],
    STARTER_CATEGORIES[1]: [
        ("Pull-ups", "Podciąganie na drążku nachwytem", *WR),
        ("Chin-ups", "Podciąganie na drążku podchwytem", *WR),
        ("Muscle-ups", "Muscle-up / Wspięcie wspierane na drążku", *WR),
        ("Barbell Row", "Wiosłowanie sztangą w opadzie tułowia", *WR),
        ("Dumbbell Row", "Wiosłowanie hantlem jednorącz o ławkę", *WR),
        ("Seated Cable Row", "Wiosłowanie na wyciągu dolnym siedząc", *WR),
        ("T-Bar Row", "Wiosłowanie na półsztandze / maszynie T-Bar", *WR),
        ("Lat Pulldown", "Ściąganie drążka wyciągu górnego do klatki", *WR),
        ("Barbell Deadlift", "Martwy ciąg ze sztangą", *WR),
        ("Dumbbell Deadlift", "Martwy ciąg z hantlami", *WR),
        ("Hyperextension", "Prostowanie tułowia na ławce rzymskiej", *WR),
    ],
    STARTER_CATEGORIES[2]: [
        ("Barbell Overhead Press / Military Press", "Wyciskanie żołnierskie sztangi stojąc", *WR),
        ("Seated Dumbbell Shoulder Press", "Wyciskanie hantli siedząc", *WR),
        ("Shoulder Press Machine", "Wyciskanie na barki na maszynie", *WR),
        ("Dumbbell Lateral Raises", "Wznosy hantli bokiem", *WR),
        ("Cable Lateral Raises", "Wznosy bokiem na wyciągu", *WR),
        ("Machine Lateral Raises", "Wznosy bokiem na maszynie", *WR),
        ("Barbell Front Raises", "Wznosy sztangi w przód", *WR),
        ("Dumbbell Front Raises", "Wznosy hantli w przód", *WR),
        ("Dumbbell Rear Delt Flyes", "Odwrotne rozpiętki z hantlami w opadzie", *WR),
        ("Face Pulls", "Face pull na wyciągu", *WR),
        ("Pike Push-ups", "Pompki w pozycji pika / na barki", *WR),
    ],
    STARTER_CATEGORIES[3]: [
        ("Barbell Bicep Curl", "Uginanie przedramion ze sztangą prostą / łamaną", *WR),
        ("Dumbbell Curl", "Uginanie hantlami z supinacją", *WR),
        ("Barbell Preacher Curl", "Uginanie ramion ze sztangą na modlitewniku", *WR),
        ("Dumbbell Preacher Curl", "Uginanie ramienia z hantlem na modlitewniku", *WR),
        ("Machine Bicep Curl", "Uginanie ramion na maszynie", *WR),
        ("Dumbbell Hammer Curl", "Uginanie ramion z hantlami w chwycie młotkowym", *WR),
        ("Cable Curl", "Uginanie ramion na wyciągu", *WR),
    ],
    STARTER_CATEGORIES[4]: [
        ("Barbell Skull Crushers", "Wyciskanie francuskie ze sztangą leżąc", *WR),
        ("Dumbbell Skull Crushers", "Wyciskanie francuskie z hantlami leżąc", *WR),
        ("Overhead Dumbbell Extension", "Wyciskanie hantla zza głowy", *WR),
        ("Triceps Pushdown", "Prostowanie ramion na wyciągu ze sznurem / drążkiem", *WR),
        ("Triceps Extension Machine", "Prostowanie ramion na maszynie", *WR),
        ("Close-Grip Barbell Bench Press", "Wyciskanie sztangi w wąskim chwycie", *WR),
        ("Bench Dips", "Pompki tyłem na ławce", *WR),
        ("Diamond Push-ups", "Pompki diamentowe", *WR),
    ],
    STARTER_CATEGORIES[5]: [
        ("Barbell Back Squat", "Przysiad ze sztangą na plecach", *WR),
        ("Barbell Front Squat", "Przysiad ze sztangą z przodu", *WR),
        ("Dumbbell Goblet Squat", "Przysiad z hantlem z przodu", *WR),
        ("Hack Squat Machine", "Przysiady na maszynie Hack Squat", *WR),
        ("Leg Press", "Wyciskanie ciężaru na suwnicy", *WR),
        ("Leg Extension", "Prostowanie nóg na maszynie siedząc", *WR),
        ("Hamstring / Leg Curl", "Uginanie nóg na maszynie leżąc / siedząc", *WR),
        ("Barbell Lunge", "Zakroki / Wykroki ze sztangą", *WR),
        ("Dumbbell Lunge", "Zakroki / Wykroki z hantlami", *WR),
        ("Standing Calf Raises", "Wspięcia na palce stojąc", *WR),
        ("Seated Calf Raises", "Wspięcia na palce siedząc na maszynie", *WR),
    ],
    STARTER_CATEGORIES[6]: [
        ("Barbell Hip Thrust", "Hip Thrust ze sztangą", *WR),
        ("Dumbbell Hip Thrust", "Hip Thrust z hantlem", *WR),
        ("Hip Thrust Machine", "Hip Thrust na maszynie", *WR),
        ("Barbell Romanian Deadlift", "Rumuński martwy ciąg ze sztangą", *WR),
        ("Dumbbell Romanian Deadlift", "Rumuński martwy ciąg z hantlami", *WR),
        ("Dumbbell Bulgarian Split Squat", "Przysiady bułgarskie z hantlami", *WR),
        ("Cable Kickbacks", "Wypychanie nogi w tył na wyciągu", *WR),
        ("Hip Abduction Machine", "Odwodzenie nóg na maszynie siedząc", *WR),
    ],
    STARTER_CATEGORIES[7]: [
        ("Cable Crunches", "Allahy / Skłony tułowia na klęcząco przy wyciągu", *WR),
        ("Ab Crunch Machine", "Spięcia brzucha na maszynie", *WR),
        ("Plank", "Deska", *WT),
        ("Side Plank", "Deska boczna", *WT),
        ("Hollow Body Hold", "Pozycja hollow body", *WT),
        ("Toes to Bar", "Unoszenie stóp do drążka w zwisie", *WR),
        ("Hanging Leg Raises", "Unoszenie nóg w zwisie na drążku", *WR),
        ("Hyperextension Side Bends", "Skłony boczne na ławce rzymskiej", *WR),
        ("Dumbbell Russian Twist", "Skręty tułowia z hantlem", *WR),
        ("Dumbbell Farmer's Walk", "Spacer farmera z hantlami", *DT),
    ],
    STARTER_CATEGORIES[8]: [
        ("Running", "Bieg na bieżni / w terenie", *DT),
        ("Cycling", "Jazda na rowerku stacjonarnym / terenowym", *DT),
        ("Elliptical", "Trening na orbitreku", *DT),
        ("Rowing Machine", "Wioślarz / Ergometr wioślarski", *DT),
        ("Stairmaster / Stair Climber", "Schody treningowe", *FT),
        ("Jump Rope", "Skakanie na skakance", *WT),
    ],
}


def exercise_display_name(en: str, pl: str) -> str:
    return f"{en} ({pl})"


class ValidationError(ValueError):
    """Błąd danych wejściowych, z komunikatem po polsku."""


def allowed_second_measures(first: str) -> tuple[str, ...]:
    """Dozwolone drugie miary dla pierwszej: po „powtórzeniach” tylko czas, po pozostałych powtórzenia i czas."""
    if first not in LOAD_TYPES:
        raise ValidationError("Nieprawidłowy typ ćwiczenia.")
    return ("time",) if first == "reps" else EFFORT_TYPES


def validate_measures(first: str, second: str) -> None:
    """Odrzuca nieznane miary i kombinację powtórzenia × powtórzenia."""
    if first not in LOAD_TYPES or second not in EFFORT_TYPES:
        raise ValidationError("Nieprawidłowy typ ćwiczenia.")
    if second not in allowed_second_measures(first):
        raise ValidationError("Powtórzenia × Powtórzenia nie są dozwolone.")


# --- wzorce dozwolonych wartości pól liczbowych (walidacja w UI po każdej zmianie) ---
_DIGITS_RE = re.compile(r"[0-9]+")
_WEIGHT_RE = re.compile(r"[0-9]*[.,]?[0-9]*")


def is_valid_minsec_input(text: str) -> bool:
    """Czy tekst pola minut/sekund jest dozwolony: puste (stan pośredni) albo 1-2 cyfry, wartość 0-59."""
    if text == "":
        return True
    return len(text) <= 2 and text.isascii() and text.isdigit() and int(text) <= 59


def is_valid_digits_input(text: str) -> bool:
    """Pole Powtórzenia/Piętra: puste (stan pośredni) albo same cyfry 0-9, bez limitu długości."""
    return text == "" or (text.isascii() and text.isdigit())


def normalize_empty_input(text: str, allow_separator: bool = False) -> str:
    """Puste pole (albo same spacje, a dla ciężaru także sam separator) -> "0"; reszta bez zmian."""
    stripped = text.strip()
    if stripped == "" or (allow_separator and stripped in (".", ",")):
        return "0"
    return text


DISTANCE_M_MAX_DIGITS = 3


def is_valid_distance_input(text: str) -> bool:
    """Czy tekst pola dystansu (metry) jest dozwolony: puste albo 1-3 cyfry, czyli 0-999."""
    return text == "" or (len(text) <= DISTANCE_M_MAX_DIGITS and text.isascii() and text.isdigit())


def is_valid_weight_input(text: str) -> bool:
    """Czy tekst pola ciężaru jest dozwolony: cyfry i najwyżej jeden separator (kropka lub przecinek)."""
    return _WEIGHT_RE.fullmatch(text) is not None


def parse_weight(value) -> float:
    text = str(value).strip()
    if not _WEIGHT_RE.fullmatch(text) or not any(c.isdigit() for c in text):
        raise ValidationError("Ciężar musi być liczbą.")
    return float(text.replace(",", "."))


def _parse_digits(value, what: str) -> int:
    text = str(value).strip()
    if not _DIGITS_RE.fullmatch(text):
        raise ValidationError(f"{what}: wpisz wartość.")
    return int(text)


def parse_reps(value) -> int:
    return _parse_digits(value, "Powtórzenia")


def parse_floors(value) -> int:
    return _parse_digits(value, "Piętra")


def _parse_part(value, what: str) -> int:
    """Człon dystansu/czasu: puste pole = 0, reszta to same cyfry."""
    text = str(value).strip()
    return _parse_digits(text, what) if text else 0


def parse_distance(km, m) -> int:
    """km + m -> metry (np. 0 km 1500 m = 1 km 500 m)."""
    return _parse_part(km, "Kilometry") * 1000 + _parse_part(m, "Metry")


def parse_duration(h, minutes, s) -> int:
    """h + min + s -> sekundy (np. 90 s = 1 min 30 s)."""
    return (
        _parse_part(h, "Godziny") * 3600
        + _parse_part(minutes, "Minuty") * 60
        + _parse_part(s, "Sekundy")
    )


def _parse_base_int(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{what} musi być liczbą całkowitą.")
    if value < 0:
        raise ValidationError(f"{what} nie może być ujemny.")
    return value


# --- formaty wyświetlania ---
def fmt_decimal(value: float | None) -> str:
    """Liczba bez zbędnych zer: 80 (nie 80.0), 2.5; zaokrąglenie do 3 miejsc usuwa błędy typu 7.500000001."""
    text = f"{round(value or 0, 3):.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def fmt_weight(value: float | None, unit: str = "kg") -> str:
    return f"{fmt_decimal(value)} {unit}"


def _join(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def fmt_distance(meters: int | None, unit: str = "km", unit_minor: str = "m") -> str:
    km, m = divmod(meters or 0, 1000)
    return _join(f"{km}{unit}" if km else "", f"{m}{unit_minor}" if m else "") or f"0{unit_minor}"


def fmt_distance_total(meters: int | None) -> str:
    km, m = divmod(meters or 0, 1000)
    return _join(f"{km} km" if km else "", f"{m} m" if m else "") or "0 m"


def fmt_time(seconds: int | None) -> str:
    h, rest = divmod(seconds or 0, 3600)
    m, s = divmod(rest, 60)
    return _join(f"{h}h" if h else "", f"{m}m" if m else "", f"{s}s" if s else "") or "0s"


def fmt_value(kind: str, value, with_unit: bool = True, units: tuple[str, ...] = ()) -> str:
    """Wspólny format wartości: kind = weight | distance | reps | floors | time; units = jednostki serii."""
    if kind == "weight":
        return fmt_weight(value, *units)
    if kind == "distance":
        return fmt_distance(value, *units)
    if kind == "time":
        return fmt_time(value)
    unit = "pięt." if kind == "floors" else "powt."
    return f"{value or 0} {unit}" if with_unit else str(value or 0)


# --- jednostki wybierane przy serii (tylko etykieta; liczby nie są przeliczane) ---
UNIT_CHOICES = {
    "weight": ("kg", "lbs"),
    "distance": ("km", "mile"),
    "distance_minor": ("m", "ys"),
}
UNIT_ATTRS = {"weight": "unit", "distance": "unit", "distance_minor": "unit_minor"}  # kolumna WorkoutSet
UNIT_LOAD_TYPE = {"weight": "weight", "distance": "distance", "distance_minor": "distance"}


def allowed_units(measure: str) -> tuple[str, ...]:
    """Dozwolone jednostki miary: weight (kg/lbs), distance (km/mile), distance_minor (m/ys)."""
    if measure not in UNIT_CHOICES:
        raise ValidationError("Ta miara nie ma wybieranej jednostki.")
    return UNIT_CHOICES[measure]


def default_unit(measure: str) -> str:
    """Jednostka bazowa miary (brak zapisanej jednostki = bazowa): kg, km, m."""
    return allowed_units(measure)[0]


def validate_unit(measure: str, unit: str | None) -> str:
    """Zwraca jednostkę pasującą do miary; None = bazowa. Inną odrzuca (ValidationError)."""
    if unit is None:
        return default_unit(measure)
    if unit not in allowed_units(measure):
        raise ValidationError(f"Jednostka „{unit}” nie pasuje do tej miary.")
    return unit


def set_unit_of(st: WorkoutSet, measure: str) -> str:
    """Jednostka serii dla miary (na pobranym obiekcie); brak wartości = bazowa."""
    validate_unit(measure, None)  # sprawdza nazwę miary
    return validate_unit(measure, getattr(st, UNIT_ATTRS[measure]))


def first_value(load_type: str, st: WorkoutSet):
    """Wartość pierwszej osi serii; Powtórzenia i Piętra są zapisywane w polu reps."""
    if load_type == "weight":
        return round(st.weight_kg or 0.0, 3)
    if load_type == "distance":
        return st.distance_m or 0
    return st.reps or 0


def fmt_set_line(exercise: Exercise, st: WorkoutSet, number: int) -> str:
    """Krótka linia serii do widoku skondensowanego, np. „1. 20 kg × 10 powt.”."""
    units = _units_of(exercise.load_type, st)  # jednostki wybrane przy serii (kg/lbs, km/mile, m/ys)
    first = fmt_value(exercise.load_type, first_value(exercise.load_type, st), units=units)
    if exercise.effort_type == "reps":
        return f"{number}. {first} × {fmt_value('reps', st.reps)}"
    return f"{number}. {first} — {fmt_value('time', st.duration_s)}"


TOTAL_LABELS = {"reps": "Łączne powtórzenia", "floors": "Łączne piętra"}


class SummaryGroup(NamedTuple):
    heading: str  # jednostki grupy (np. „lbs”, „km / m”); pusty, gdy wszystkie serie mają tę samą jednostkę
    lines: list[str]


def _fmt_weight_total(value: float, unit: str) -> str:
    return f"{fmt_decimal(value)} {unit}"


def _fmt_distance_total_units(meters: int, unit: str, unit_minor: str) -> str:
    km, m = divmod(meters or 0, 1000)
    return _join(f"{km} {unit}" if km else "", f"{m} {unit_minor}" if m else "") or f"0 {unit_minor}"


def _units_of(kind: str, st: WorkoutSet) -> tuple[str, ...]:
    """Jednostki serii istotne dla typu obciążenia (liczby nie są przeliczane, więc grupują sumy)."""
    if kind == "weight":
        return (validate_unit("weight", getattr(st, "unit", None)),)
    if kind == "distance":
        return (
            validate_unit("distance", getattr(st, "unit", None)),
            validate_unit("distance_minor", getattr(st, "unit_minor", None)),
        )
    return ()


def summarize_exercise(exercise: Exercise, sets) -> list[SummaryGroup]:
    """Wyniki łączne wykonanych serii, osobno dla każdej jednostki; brak wykonanych serii -> pusta lista."""
    kind = exercise.load_type
    by_reps = exercise.effort_type == "reps"
    by_units: dict[tuple[str, ...], list[WorkoutSet]] = {}
    for st in sets:
        if st.done:
            by_units.setdefault(_units_of(kind, st), []).append(st)

    def first(st) -> float | int:
        return first_value(kind, st)

    def second(st) -> int:
        return (st.reps or 0) if by_reps else (st.duration_s or 0)

    groups = []
    for units in sorted(by_units):
        done = by_units[units]
        total_reps = f"Łączne powtórzenia: {sum(second(st) for st in done)}"
        if kind == "weight" and by_reps:
            lines = [
                f"Suma przewalonego żelastwa: {_fmt_weight_total(sum(first(st) * second(st) for st in done), *units)}",
                total_reps,
            ]
        elif kind == "weight":
            lines = [f"Łączny czas: {fmt_time(sum(second(st) for st in done))}"]
        elif kind == "distance" and by_reps:
            lines = [
                f"Łączny dystans: {_fmt_distance_total_units(sum(first(st) * second(st) for st in done), *units)}",
                total_reps,
            ]
        else:
            if kind == "distance":
                lines = [f"Łączny dystans: {_fmt_distance_total_units(sum(first(st) for st in done), *units)}"]
            else:
                lines = [f"{TOTAL_LABELS[kind]}: {sum(first(st) for st in done)}"]
            lines.append(total_reps if by_reps else f"Łączny czas: {fmt_time(sum(second(st) for st in done))}")
        groups.append(SummaryGroup(" / ".join(units), lines))
    if len(groups) == 1:
        groups[0] = SummaryGroup("", groups[0].lines)
    return groups


# --- napis „Ostatni trening” ---
WEEKDAY_NAMES = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")


def fmt_date_dmy(day: date) -> str:
    return f"{day.day:02d}.{day.month:02d}.{day.year:04d}"


def fmt_last_workout(day: date, exercises: int, sets: int) -> str:
    """„Ostatni trening: piątek, 23.10.2026, 6 ćwicz., 20 serii” (nazwy dni własne, bez locale)."""
    return f"Ostatni trening: {WEEKDAY_NAMES[day.weekday()]}, {fmt_date_dmy(day)}, {exercises} ćwicz., {sets} serii"


# --- kalendarz ---
MONTH_NAMES = (
    "STYCZEŃ", "LUTY", "MARZEC", "KWIECIEŃ", "MAJ", "CZERWIEC",
    "LIPIEC", "SIERPIEŃ", "WRZESIEŃ", "PAŹDZIERNIK", "LISTOPAD", "GRUDZIEŃ",
)
WEEKDAY_ABBR = ("PN", "WT", "ŚR", "CZ", "PT", "SB", "ND")


def weekday_abbr(day: date) -> str:
    """Skrót dnia tygodnia daty (PN…ND), na sztywno, bez locale."""
    return WEEKDAY_ABBR[day.weekday()]


MONTH_NAMES_GENITIVE = (
    "STYCZNIA", "LUTEGO", "MARCA", "KWIETNIA", "MAJA", "CZERWCA",
    "LIPCA", "SIERPNIA", "WRZEŚNIA", "PAŹDZIERNIKA", "LISTOPADA", "GRUDNIA",
)
CALENDAR_MONTHS_BACK = 24
CALENDAR_MONTHS_FORWARD = 24


def month_grid(year: int, month: int) -> list[list[date | None]]:
    """Tygodnie miesiąca (od poniedziałku), po 7 pól; None = puste pole przed 1. lub po ostatnim dniu miesiąca."""
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    return [[d if d.month == month else None for d in week] for week in weeks]


def month_range(
    center: date, back: int = CALENDAR_MONTHS_BACK, forward: int = CALENDAR_MONTHS_FORWARD
) -> list[tuple[int, int]]:
    """Kolejne miesiące (rok, miesiąc) od `back` miesięcy przed miesiącem `center` do `forward` miesięcy po nim."""
    return [shift_month(center.year, center.month, delta) for delta in range(-back, forward + 1)]


def classify_day(day: date, today: date, workout_dates: set[date]) -> str:
    """Rodzaj dnia w kalendarzu: "today" > "workout" > "sunday" > "normal"."""
    if day == today:
        return "today"
    if day in workout_dates:
        return "workout"
    if day.weekday() == 6:
        return "sunday"
    return "normal"


SWIPE_MIN_DISTANCE = 50  # px poziomego przeciągnięcia, od którego gest liczy się jako przesunięcie


def interpret_swipe(dx: float, threshold: float = SWIPE_MIN_DISTANCE) -> int:
    """Przeciągnięcie o dx px: w lewo (dx <= -próg) -> 1 (następny), w prawo (dx >= próg) -> -1 (poprzedni), inaczej 0."""
    if dx <= -threshold:
        return 1
    if dx >= threshold:
        return -1
    return 0


def drag_progress(dx: float, width: float, base: float = 0.0) -> float:
    """Postęp przesuwania w [-1, 1]: przeciągnięcie w lewo (dx < 0) daje wartość dodatnią (w stronę następnego dnia).

    base to postęp w chwili rozpoczęcia gestu (np. przejęcie animacji w trakcie), width to szerokość obszaru widoku.
    """
    if width <= 0:
        return 0.0
    return max(-1.0, min(1.0, base - dx / width))


SWIPE_COMMIT_FRACTION = 0.15  # część szerokości ekranu, od której puszczenie palca zatwierdza zmianę dnia


def settle_target(progress: float) -> int:
    """Dzień docelowy po zwolnieniu palca: 1 / -1, gdy przesunięcie wynosi co najmniej 25% szerokości, inaczej 0."""
    if progress >= SWIPE_COMMIT_FRACTION:
        return 1
    if progress <= -SWIPE_COMMIT_FRACTION:
        return -1
    return 0


def settle_duration(progress: float, target: int, width: float, velocity: float = 0.0) -> float:
    """Czas (s) dokończenia animacji; szybki gest skraca czas, ale nie zmienia wyboru dnia (zob. settle_target)."""
    distance = abs(target - progress)
    speed = max(abs(velocity), 2 * width, 1.0)
    return max(0.06, min(0.3, distance * width / speed))


def ease_out_cubic(t: float) -> float:
    """Krzywa animacji przesuwania (dni w „Workout”, okresy w „Statystykach”): szybki start, łagodne wyhamowanie."""
    return 1 - (1 - t) ** 3


def day_tape_layout(progress: float, width: float, offsets: range | tuple[int, ...] = range(-3, 4)) -> list[tuple[int, float, float]]:
    """Układ taśmy dni w oknie o szerokości width: lista (offset dnia, lewa krawędź, szerokość).

    W spoczynku (progress = 0) widoczne są dni -2..2, wybrany jest szerszy (3 jednostki wobec 2 u pozostałych); środek
    zaznaczonego dnia leży w środku okna. Przy przesuwaniu szerokość płynnie przechodzi na sąsiada.
    """
    unit = width / 11
    widths = {o: 2 * unit + unit * max(0.0, 1 - abs(o - progress)) for o in offsets}
    first = min(offsets)
    start, acc = {}, 0.0
    for o in offsets:
        start[o] = acc
        acc += widths[o]
    neighbour = 1 if progress >= 0 else -1
    w_nb = widths.get(neighbour, 2 * unit)
    focus = start[0] + widths[0] / 2 + abs(progress) * neighbour * (widths[0] + w_nb) / 2
    return [(o, width / 2 - focus + start[o], widths[o]) for o in offsets if first <= o]


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


@dataclass(frozen=True)
class SetSnapshot:
    """Wartości serii bez znacznika „wykonana”."""

    weight_kg: float | None
    distance_m: int | None
    reps: int | None
    duration_s: int | None
    unit: str | None = None
    unit_minor: str | None = None


@dataclass(frozen=True)
class ExerciseSnapshot:
    exercise_id: int
    sets: tuple[SetSnapshot, ...]


@dataclass(frozen=True)
class WorkoutSnapshot:
    """Migawka treningu (same dane, bez referencji do bazy) - do kopiowania na inne dni."""

    name: str
    exercises: tuple[ExerciseSnapshot, ...]


def _workout_query():
    return select(Workout).options(
        selectinload(Workout.exercises).selectinload(WorkoutExercise.sets),
        selectinload(Workout.exercises).selectinload(WorkoutExercise.exercise),
    )


class TrainingService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sf = session_factory
        self._seed_exercises()

    def _seed_exercises(self) -> None:
        """Katalog startowy jest dopisywany tylko raz (PRAGMA user_version < SEED_VERSION), żeby usunięte
        ćwiczenia i sekcje nie wracały przy kolejnym starcie. Dopisuje brakujące pozycje po nazwie."""
        with self._sf.begin() as s:
            version = s.connection().exec_driver_sql("PRAGMA user_version").scalar() or 0
            if version >= SEED_VERSION:
                return
            s.connection().exec_driver_sql(f"PRAGMA user_version = {SEED_VERSION}")
            known = {c.lower() for c in s.scalars(select(Category.name))}
            position = s.scalar(select(func.count(Category.id)))
            for name in STARTER_CATEGORIES:
                if name.lower() not in known:
                    s.add(Category(name=name, position=position))
                    position += 1
            s.flush()
            existing = {n.lower() for n in s.scalars(select(Exercise.name))}
            for category, items in STARTER_EXERCISES.items():
                for en, pl, load, effort in items:
                    name = exercise_display_name(en, pl)
                    if name.lower() not in existing:
                        s.add(Exercise(name=name, category=category, load_type=load, effort_type=effort))

    def clear_user_data(self) -> dict[str, int]:
        """Jednorazowe czyszczenie: wszystkie treningi (z ćwiczeniami i seriami) oraz ćwiczenia własne.
        Zostają ćwiczenia startowe i wszystkie kategorie/sekcje. Zwraca liczby usuniętych rekordów."""
        starter = {
            exercise_display_name(en, pl).lower() for items in STARTER_EXERCISES.values() for en, pl, _, _ in items
        }
        with self._sf.begin() as s:
            sets = s.execute(delete(WorkoutSet)).rowcount
            workout_exercises = s.execute(delete(WorkoutExercise)).rowcount
            workouts = s.execute(delete(Workout)).rowcount
            custom = [e.id for e in s.scalars(select(Exercise)) if e.name.lower() not in starter]
            exercises = 0
            if custom:
                exercises = s.execute(delete(Exercise).where(Exercise.id.in_(custom))).rowcount
        return {
            "workout_set": sets,
            "workout_exercise": workout_exercises,
            "workout": workouts,
            "exercise": exercises,
        }

    # --- kategorie i sekcje ---
    def get_categories(self) -> list[Category]:
        """Kategorie startowe, potem sekcje własne - w kolejności dodania."""
        with self._sf() as s:
            return list(s.scalars(select(Category).order_by(Category.position)))

    def add_category(self, name: str) -> Category:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Podaj nazwę sekcji.")
        duplicate = ValidationError("Kategoria lub sekcja o takiej nazwie już istnieje.")
        try:
            with self._sf.begin() as s:
                if s.scalar(select(Category.id).where(func.lower(Category.name) == name.lower())):
                    raise duplicate
                last = s.scalar(select(func.max(Category.position)))
                category = Category(name=name, position=0 if last is None else last + 1)
                s.add(category)
        except IntegrityError:
            raise duplicate from None
        return category

    def get_exercises_by_category(self, category: str) -> list[Exercise]:
        with self._sf() as s:
            return list(
                s.scalars(select(Exercise).where(Exercise.category == category).order_by(Exercise.id))
            )

    # --- ćwiczenia (definicje) ---
    def list_exercises(self) -> list[Exercise]:
        with self._sf() as s:
            return list(s.scalars(select(Exercise).order_by(Exercise.id)))

    def create_exercise(
        self, name: str, category: str, load_type: str = "weight", effort_type: str = "reps"
    ) -> Exercise:
        """Dodaje własne ćwiczenie do istniejącej kategorii lub sekcji."""
        name = (name or "").strip()
        if not name:
            raise ValidationError("Podaj nazwę ćwiczenia.")
        validate_measures(load_type, effort_type)
        duplicate = ValidationError("Ćwiczenie o takiej nazwie już istnieje.")
        try:
            with self._sf.begin() as s:
                if not category or not s.scalar(select(Category.id).where(Category.name == category)):
                    raise ValidationError("Wybierz istniejącą kategorię.")
                if s.scalar(select(Exercise.id).where(func.lower(Exercise.name) == name.lower())):
                    raise duplicate
                exercise = Exercise(
                    name=name, category=category, load_type=load_type, effort_type=effort_type
                )
                s.add(exercise)
        except IntegrityError:
            raise duplicate from None
        return exercise

    # --- treningi ---
    def create_workout(self, workout_date: date, name: str = "") -> Workout:
        """Jeden trening na dzień. `started_at` tylko dla treningu założonego w dniu dzisiejszym."""
        try:
            with self._sf.begin() as s:
                w = Workout(
                    workout_date=workout_date,
                    name=(name or "").strip(),
                    started_at=datetime.now() if workout_date == date.today() else None,
                )
                s.add(w)
        except IntegrityError:
            raise ValidationError("W tym dniu jest już trening.") from None
        return self.get_workout(w.id)

    def get_workout(self, workout_id: int) -> Workout | None:
        with self._sf() as s:
            return s.scalars(_workout_query().where(Workout.id == workout_id)).first()

    def get_workout_by_date(self, workout_date: date) -> Workout | None:
        with self._sf() as s:
            return s.scalars(
                _workout_query().where(Workout.workout_date == workout_date)
            ).first()

    def get_workout_dates(self, year: int, month: int) -> set[date]:
        """Dni miesiąca z treningiem mającym co najmniej jedno ćwiczenie."""
        ny, nm = shift_month(year, month, 1)
        return self.get_workout_dates_between(date(year, month, 1), date(ny, nm, 1))

    def get_workout_dates_between(self, first: date, end: date) -> set[date]:
        """Dni z zakresu [first, end) z treningiem mającym co najmniej jedno ćwiczenie (jedno zapytanie)."""
        with self._sf() as s:
            return set(
                s.scalars(
                    select(Workout.workout_date).where(
                        Workout.workout_date >= first,
                        Workout.workout_date < end,
                        Workout.exercises.any(),
                    )
                )
            )

    # --- statystyki (tylko odczyt) ---
    def get_exercise_set_rows(self, exercise_id: int) -> list["SetRow"]:
        """Wszystkie wykonane serie ćwiczenia z datą treningu - jedno zapytanie."""
        with self._sf() as s:
            stmt = (
                select(
                    Workout.workout_date,
                    WorkoutSet.weight_kg,
                    WorkoutSet.distance_m,
                    WorkoutSet.reps,
                    WorkoutSet.duration_s,
                    WorkoutSet.unit,
                    WorkoutSet.unit_minor,
                    WorkoutSet.done,
                )
                .join(WorkoutExercise, WorkoutExercise.id == WorkoutSet.workout_exercise_id)
                .join(Workout, Workout.id == WorkoutExercise.workout_id)
                .where(WorkoutExercise.exercise_id == exercise_id, WorkoutSet.done.is_(True))
            )
            return [SetRow(*row) for row in s.execute(stmt)]

    def get_exercise_daily_stats(self, exercise: Exercise) -> dict[date, "DailyStats"]:
        rows = self.get_exercise_set_rows(exercise.id)
        return aggregate_daily(exercise.load_type, exercise.effort_type, rows)

    def get_first_workout_date(self) -> date | None:
        """Data najstarszego treningu z historii, który ma co najmniej jedno ćwiczenie; brak -> None."""
        with self._sf() as s:
            return s.scalar(select(func.min(Workout.workout_date)).where(Workout.exercises.any()))

    def get_last_done_workout_date(self) -> date | None:
        """Data najnowszego treningu, w którym jest co najmniej jedna seria oznaczona jako wykonana; brak -> None."""
        with self._sf() as s:
            return s.scalar(
                select(func.max(Workout.workout_date))
                .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
                .join(WorkoutSet, WorkoutSet.workout_exercise_id == WorkoutExercise.id)
                .where(WorkoutSet.done.is_(True))
            )

    def get_workout_days(self, sections) -> list[date]:
        """Dni z treningiem, który ma co najmniej jedno ćwiczenie z jednej z `sections` (nazw sekcji); jedno zapytanie.

        Ćwiczenie jest powiązane z sekcją przez Exercise.category (nazwa z tabeli Category); dzień jest liczony raz."""
        names = list(sections)
        if not names:
            return []
        with self._sf() as s:
            stmt = (
                select(Workout.workout_date)
                .join(WorkoutExercise, WorkoutExercise.workout_id == Workout.id)
                .join(Exercise, Exercise.id == WorkoutExercise.exercise_id)
                .where(Exercise.category.in_(names))
                .distinct()
                .order_by(Workout.workout_date)
            )
            return list(s.scalars(stmt))

    def get_last_workout(self, today: date | None = None) -> Workout | None:
        """Najnowszy trening z datą ściśle wcześniejszą niż dziś, który ma co najmniej jedno ćwiczenie."""
        with self._sf() as s:
            return s.scalars(
                _workout_query()
                .where(
                    Workout.workout_date < (today or date.today()),
                    Workout.exercises.any(),
                )
                .order_by(Workout.workout_date.desc())
            ).first()

    def rename_workout(self, workout_id: int, name: str) -> None:
        with self._sf.begin() as s:
            s.get(Workout, workout_id).name = (name or "").strip()

    def snapshot_workout(self, workout_id: int) -> WorkoutSnapshot | None:
        """Migawka treningu; None, gdy trening nie istnieje albo nie ma żadnego ćwiczenia. Nic nie zapisuje."""
        workout = self.get_workout(workout_id)
        if workout is None or not workout.exercises:
            return None
        return WorkoutSnapshot(
            name=workout.name,
            exercises=tuple(
                ExerciseSnapshot(
                    exercise_id=we.exercise_id,
                    sets=tuple(
                        SetSnapshot(
                            st.weight_kg, st.distance_m, st.reps, st.duration_s, st.unit, st.unit_minor
                        )
                        for st in we.sets
                    ),
                )
                for we in workout.exercises
            ),
        )

    def paste_snapshot(self, snapshot: WorkoutSnapshot, workout_date: date) -> Workout | None:
        """Tworzy trening z migawki (serie niewykonane). None i brak zmian, gdy dzień ma już trening."""
        if self.get_workout_by_date(workout_date) is not None:
            return None
        try:
            with self._sf.begin() as s:
                if any(s.get(Exercise, ex.exercise_id) is None for ex in snapshot.exercises):
                    return None
                w = Workout(
                    workout_date=workout_date,
                    name=snapshot.name,
                    started_at=datetime.now() if workout_date == date.today() else None,
                )
                for position, ex in enumerate(snapshot.exercises):
                    w.exercises.append(
                        WorkoutExercise(
                            exercise_id=ex.exercise_id,
                            position=position,
                            sets=[
                                WorkoutSet(
                                    position=i,
                                    weight_kg=st.weight_kg,
                                    distance_m=st.distance_m,
                                    reps=st.reps,
                                    duration_s=st.duration_s,
                                    unit=st.unit,
                                    unit_minor=st.unit_minor,
                                    done=False,
                                )
                                for i, st in enumerate(ex.sets)
                            ],
                        )
                    )
                s.add(w)
        except IntegrityError:
            return None
        return self.get_workout(w.id)

    def delete_workout(self, workout_id: int) -> None:
        with self._sf.begin() as s:
            w = s.get(Workout, workout_id)
            if w is not None:
                s.delete(w)

    # --- ćwiczenia w treningu ---
    def add_exercise_to_workout(self, workout_id: int, exercise_id: int) -> WorkoutExercise:
        with self._sf.begin() as s:
            exercise = s.get(Exercise, exercise_id)
            if exercise is None:
                raise ValidationError("Nie ma takiego ćwiczenia.")
            last = s.scalar(
                select(func.max(WorkoutExercise.position)).where(WorkoutExercise.workout_id == workout_id)
            )
            position = 0 if last is None else last + 1  # nowe ćwiczenie na końcu
            we = WorkoutExercise(
                workout_id=workout_id, exercise_id=exercise.id, position=position
            )
            s.add(we)
            s.flush()
            we.sets.append(self._blank_set(exercise, 0))
            we_id = we.id
        with self._sf() as s:
            return s.scalars(
                select(WorkoutExercise)
                .options(
                    selectinload(WorkoutExercise.sets),
                    selectinload(WorkoutExercise.exercise),
                )
                .where(WorkoutExercise.id == we_id)
            ).one()

    def remove_exercise_from_workout(self, workout_exercise_id: int) -> None:
        with self._sf.begin() as s:
            we = s.get(WorkoutExercise, workout_exercise_id)
            if we is not None:
                s.delete(we)

    def reorder_workout_exercises(self, workout_id: int, old_index: int, new_index: int) -> list[int]:
        """Przesuwa ćwiczenie z pozycji `old_index` na `new_index` i przepisuje pozycje 0..n-1.
        Zwraca id wpisów ćwiczeń w nowej kolejności."""
        with self._sf.begin() as s:
            rows = list(
                s.scalars(
                    select(WorkoutExercise)
                    .where(WorkoutExercise.workout_id == workout_id)
                    .order_by(WorkoutExercise.position, WorkoutExercise.id)
                )
            )
            order = move_item(rows, old_index, new_index)
            for position, we in enumerate(order):
                if we.position != position:
                    we.position = position
            return [we.id for we in order]

    def get_workout_exercise_ids(self, workout_id: int) -> list[int]:
        """Id wpisów ćwiczeń treningu w zapisanej kolejności."""
        with self._sf() as s:
            return list(
                s.scalars(
                    select(WorkoutExercise.id)
                    .where(WorkoutExercise.workout_id == workout_id)
                    .order_by(WorkoutExercise.position, WorkoutExercise.id)
                )
            )

    # --- notatki do ćwiczeń w treningu ---
    def set_exercise_note(self, workout_exercise_id: int, text: str | None) -> None:
        """Zapisuje notatkę ćwiczenia w konkretnym treningu; pusty tekst lub same spacje = brak notatki."""
        cleaned = (text or "").strip()
        with self._sf.begin() as s:
            we = s.get(WorkoutExercise, workout_exercise_id)
            if we is not None:
                we.note = text if cleaned else None

    def get_exercise_note(self, workout_exercise_id: int) -> str:
        """Zapisana notatka; brak = pusty tekst."""
        with self._sf() as s:
            we = s.get(WorkoutExercise, workout_exercise_id)
            return (we.note or "") if we is not None else ""

    # --- usuwanie z katalogu (razem z historią) ---
    def delete_exercises(self, exercise_ids) -> None:
        """Usuwa ćwiczenia z katalogu oraz ich historię (wpisy w treningach, serie, notatki) w jednej transakcji,
        jawnymi usunięciami. Treningi, które przez to straciły wszystkie ćwiczenia, są usuwane; pozostałe zostają."""
        ids = list(exercise_ids)
        if not ids:
            return
        with self._sf.begin() as s:
            entries = select(WorkoutExercise.id).where(WorkoutExercise.exercise_id.in_(ids))
            affected = set(
                s.scalars(select(WorkoutExercise.workout_id).where(WorkoutExercise.exercise_id.in_(ids)))
            )
            s.execute(delete(WorkoutSet).where(WorkoutSet.workout_exercise_id.in_(entries)))
            s.execute(delete(WorkoutExercise).where(WorkoutExercise.exercise_id.in_(ids)))
            s.execute(delete(Exercise).where(Exercise.id.in_(ids)))
            if affected:
                still_used = select(WorkoutExercise.workout_id).where(WorkoutExercise.workout_id.in_(affected))
                s.execute(delete(Workout).where(Workout.id.in_(affected), Workout.id.not_in(still_used)))

    def delete_exercise(self, exercise_id: int) -> None:
        """Ćwiczenie z historią (zob. delete_exercises); nieistniejące -> bez błędu."""
        self.delete_exercises([exercise_id])

    def delete_category(self, name: str) -> None:
        """Sekcję z jej ćwiczeniami i całą historią tych ćwiczeń; nieistniejąca -> bez błędu."""
        with self._sf() as s:
            ids = list(s.scalars(select(Exercise.id).where(Exercise.category == name)))
        self.delete_exercises(ids)
        with self._sf.begin() as s:
            s.execute(delete(Category).where(Category.name == name))

    # --- serie ---
    @staticmethod
    def _blank_set(exercise: Exercise, position: int) -> WorkoutSet:
        """Seria z zerami tylko w polach pasujących do typu ćwiczenia (reszta NULL)."""
        return WorkoutSet(
            position=position,
            weight_kg=0.0 if exercise.load_type == "weight" else None,
            distance_m=0 if exercise.load_type == "distance" else None,
            reps=0 if exercise.load_type in ("reps", "floors") or exercise.effort_type == "reps" else None,
            duration_s=0 if exercise.effort_type == "time" else None,
        )

    def add_set(self, workout_exercise_id: int) -> WorkoutSet:
        """Nowa seria kopiuje wartości poprzedniej (bez znacznika „wykonana”)."""
        with self._sf.begin() as s:
            we = s.get(WorkoutExercise, workout_exercise_id)
            last = s.scalars(
                select(WorkoutSet)
                .where(WorkoutSet.workout_exercise_id == workout_exercise_id)
                .order_by(WorkoutSet.position.desc())
            ).first()
            new = self._blank_set(we.exercise, (last.position + 1) if last else 0)
            new.workout_exercise_id = workout_exercise_id
            if last:
                new.weight_kg, new.distance_m = last.weight_kg, last.distance_m
                new.reps, new.duration_s = last.reps, last.duration_s
                new.unit, new.unit_minor = last.unit, last.unit_minor
            s.add(new)
        return new

    def update_set(
        self,
        set_id: int,
        weight_kg=None,
        distance_m: int | None = None,
        reps=None,
        duration_s: int | None = None,
        done: bool | None = None,
    ) -> WorkoutSet:
        """Waliduje wszystkie podane pola przed zapisem; przy błędzie nic się nie zmienia.

        `distance_m` i `duration_s` to wartości bazowe (zob. parse_distance, parse_duration).
        """
        new_weight = parse_weight(weight_kg) if weight_kg is not None else None
        new_distance = _parse_base_int(distance_m, "Dystans") if distance_m is not None else None
        new_reps = parse_reps(reps) if reps is not None else None
        new_duration = _parse_base_int(duration_s, "Czas") if duration_s is not None else None
        with self._sf.begin() as s:
            ws = s.get(WorkoutSet, set_id)
            if new_weight is not None:
                ws.weight_kg = new_weight
            if new_distance is not None:
                ws.distance_m = new_distance
            if new_reps is not None:
                ws.reps = new_reps
            if new_duration is not None:
                ws.duration_s = new_duration
            if done is not None:
                ws.done = done
        return ws

    def set_set_unit(self, set_id: int, measure: str, unit: str) -> WorkoutSet:
        """Zapisuje jednostkę serii (bez przeliczania wartości); odrzuca jednostkę niepasującą do miary."""
        unit = validate_unit(measure, unit)
        with self._sf.begin() as s:
            ws = s.get(WorkoutSet, set_id)
            if ws is None:
                raise ValidationError("Nie ma takiej serii.")
            if ws.workout_exercise.exercise.load_type != UNIT_LOAD_TYPE[measure]:
                raise ValidationError("Ta seria nie ma tej miary.")
            setattr(ws, UNIT_ATTRS[measure], unit)
        return ws

    def get_set_unit(self, set_id: int, measure: str) -> str:
        """Odczyt jednostki serii dla miary; brak zapisanej = bazowa."""
        with self._sf() as s:
            ws = s.get(WorkoutSet, set_id)
            if ws is None:
                raise ValidationError("Nie ma takiej serii.")
            return set_unit_of(ws, measure)

    def remove_set(self, set_id: int) -> None:
        with self._sf.begin() as s:
            ws = s.get(WorkoutSet, set_id)
            if ws is not None:
                s.delete(ws)


# --- statystyki ćwiczenia (czysta logika, bez UI i bazy) ---
LBS_TO_KG = 0.45359237
MILE_TO_KM = 1.609344
YARD_TO_M = 0.9144


def lbs_to_kg(value: float) -> float:
    return value * LBS_TO_KG


def distance_to_km(major: float, minor: float = 0, unit: str | None = None, unit_minor: str | None = None) -> float:
    """Pole km/mile plus pole m/ys podzielone przez 1000; brak jednostki = bazowa (km, m)."""
    km = major * (MILE_TO_KM if unit == "mile" else 1)
    metres = minor * (YARD_TO_M if unit_minor == "ys" else 1)
    return km + metres / 1000


def hms_to_minutes(h: float, minutes: float, seconds: float) -> float:
    return h * 60 + minutes + seconds / 60


class SetRow(NamedTuple):
    """Seria w postaci surowych wartości z bazy (do statystyk)."""

    day: date
    weight_kg: float | None
    distance_m: int | None
    reps: int | None
    duration_s: int | None
    unit: str | None
    unit_minor: str | None
    done: bool


class DailyStats(NamedTuple):
    w1: float  # łącznie podniesione / zrobione
    w2: float  # największa wartość pierwszej miary w jednej serii
    w3: float  # druga miara łącznie (powtórzenia lub minuty)
    w3_max: float = 0.0  # największa wartość drugiej miary w jednej serii


class StatTitles(NamedTuple):
    w1: str
    w2: str
    w3: str
    unit1: str  # jednostki rekordów W1, W2 i W3
    unit2: str
    unit3: str


# jedna tabela napisów i jednostek: pierwsza miara -> (tytuł W1, tytuł W2, jednostka W1/W2)
STAT_FIRST_TITLES = {
    "weight": ("Łączny ciężar (kg)", "Największy ciężar dnia (kg)", "kg"),
    "distance": ("Łączny dystans (km)", "Najdłuższy pojedynczy dystans dnia (km)", "km"),
    "reps": ("Łączna liczba powtórzeń", "Najwięcej powtórzeń w serii", "powt."),
    "floors": ("Łączna liczba pięter", "Najwięcej pięter w serii", "pięt."),
}
STAT_SECOND_TITLES = {"reps": ("Powtórzenia", "powt."), "time": ("Łączny czas ćwiczeń (min)", "min")}


def stat_titles(load_type: str, effort_type: str) -> StatTitles:
    w1, w2, unit = STAT_FIRST_TITLES[load_type]
    w3, unit3 = STAT_SECOND_TITLES[effort_type]
    return StatTitles(w1, w2, w3, unit, unit, unit3)


def _set_values(load_type: str, effort_type: str, row: SetRow) -> tuple[float, float]:
    """(pierwsza miara w kg / km / powt. / piętrach, druga miara w powt. / minutach) po przeliczeniu jednostek."""
    if load_type == "weight":
        first = row.weight_kg or 0.0
        if row.unit == "lbs":
            first = lbs_to_kg(first)
    elif load_type == "distance":
        km, m = divmod(row.distance_m or 0, 1000)
        first = distance_to_km(km, m, row.unit, row.unit_minor)
    else:  # powtórzenia i piętra są zapisane w polu reps
        first = float(row.reps or 0)
    if effort_type == "reps":
        second = float(row.reps or 0)
    else:
        second = (row.duration_s or 0) / 60
    return first, second


def aggregate_daily(load_type: str, effort_type: str, rows) -> dict[date, DailyStats]:
    """Wartości dzienne W1, W2, W3 z wykonanych serii (niewykonane są pomijane)."""
    # piętra × powtórzenia dzielą pole reps z drugą miarą: mnożenie dałoby kwadrat, więc W1 to suma pięter
    multiply = effort_type == "reps" and load_type in ("weight", "distance")
    days: dict[date, list[float]] = {}
    for row in rows:
        if not row.done:
            continue
        first, second = _set_values(load_type, effort_type, row)
        acc = days.setdefault(row.day, [0.0, 0.0, 0.0, 0.0])
        acc[0] += first * second if multiply else first
        acc[1] = max(acc[1], first)
        acc[2] += second
        acc[3] = max(acc[3], second)
    return {day: DailyStats(*acc) for day, acc in days.items()}


# --- okresy wykresów: bieżący tydzień (pn-nd) lub miesiąc kalendarzowy ---
def period_range(day: date, interval: str) -> tuple[date, date]:
    """Początek i koniec (włącznie) tygodnia (pn-nd) lub miesiąca kalendarzowego zawierającego `day`."""
    if interval == "week":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    return date(day.year, day.month, 1), date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def shift_period(day: date, interval: str, delta: int) -> date:
    """Początek okresu przesuniętego o `delta` okresów względem okresu zawierającego `day`."""
    start, _ = period_range(day, interval)
    if interval == "week":
        return start + timedelta(weeks=delta)
    year, month = shift_month(start.year, start.month, delta)
    return date(year, month, 1)


def navigate_period(start: date, interval: str, delta: int, today: date, first_workout: date | None) -> date:
    """Początek okresu po przesunięciu o `delta` (-1 poprzedni, 1 następny); poza granicami zwraca `start`.

    Granice: nie dalej niż bieżący okres i nie dalej do tyłu niż okres z pierwszym treningiem (brak treningów: bez cofania)."""
    start = period_range(start, interval)[0]
    target = shift_period(start, interval, delta)
    newest = period_range(today, interval)[0]
    oldest = period_range(first_workout, interval)[0] if first_workout else newest
    return target if oldest <= target <= newest else start


def period_label(start: date, interval: str) -> str:
    """Nazwa okresu obok tytułu wykresu: „Marzec 2026” (miesiąc) lub „Tydzień 12, 2026” (tydzień ISO i rok ISO)."""
    if interval == "week":
        iso_year, iso_week, _ = start.isocalendar()
        return f"Tydzień {iso_week}, {iso_year}"
    return f"{MONTH_NAMES[start.month - 1].capitalize()} {start.year}"


def period_series(
    daily: dict[date, DailyStats], start: date, interval: str, today: date
) -> list[tuple[date, DailyStats]]:
    """Dni okresu, w których była wykonana seria (do dziś włącznie), od najwcześniejszego; dni bez serii są pomijane."""
    first, last = period_range(start, interval)
    return [(day, daily[day]) for day in sorted(daily) if first <= day <= min(last, today)]


def default_selected_index(series: list[tuple[date, DailyStats]]) -> int | None:
    """Indeks ostatniego dnia z danymi w okresie; brak danych -> None."""
    return len(series) - 1 if series else None


def period_stats(series: list[tuple[date, DailyStats]]) -> tuple[float, float]:
    """(suma W1, maksimum W2) z dni okresu."""
    return sum(v.w1 for _, v in series), max((v.w2 for _, v in series), default=0.0)


def period_second_stats(series: list[tuple[date, DailyStats]]) -> tuple[float, float]:
    """(suma W3, największa wartość drugiej miary w jednej serii) z dni okresu."""
    return sum(v.w3 for _, v in series), max((v.w3_max for _, v in series), default=0.0)


def history_max(daily: dict[date, DailyStats]) -> float:
    """Największa wartość pierwszej miary w jednej serii z całej historii ćwiczenia (po przeliczeniu jednostek)."""
    return max((v.w2 for v in daily.values()), default=0.0)


def percent_change(current: float, previous: float) -> int | None:
    """Zmiana procentowa względem poprzedniego okresu, zaokrąglona do pełnych procent (od zera); poprzedni <= 0 -> None."""
    if previous <= 0:
        return None
    pct = (current - previous) / previous * 100
    return int(math.copysign(math.floor(abs(pct) + 0.5), pct))


def fmt_percent(pct: int | None) -> str:
    return "–" if pct is None else f"{pct:+d}%" if pct else "0%"


def stat_total_label(load_type: str) -> str:
    """Etykieta lewej kolumny statystyk: „Łączny tonaż” dla ciężaru, inaczej nazwa W1 bez jednostki."""
    if load_type == "weight":
        return "Łączny tonaż"
    return STAT_FIRST_TITLES[load_type][0].split(" (")[0]


# etykieta lewej kolumny pola pod wykresem 2 (osobno od tytułów wykresów, które mają dopiski „dnia”)
STAT_PEAK_LABELS = {
    "weight": "Największy ciężar",
    "distance": "Największy dystans",
    "reps": "Najwięcej powtórzeń w serii",
    "floors": "Najwięcej pięter w serii",
}
# druga miara -> (etykieta sumy w okresie, etykieta rekordu w serii)
STAT_SECOND_LABELS = {
    "reps": ("Łączna liczba powtórzeń", "Rekord powtórzeń w serii"),
    "time": ("Łączny czas", "Rekord czasu w serii"),
}


class StatColumn(NamedTuple):
    label: str
    value: float
    unit: str
    pct: int | None  # zmiana procentowa; None = brak porównania („–”)
    compare: str  # napis „vs. …”
    display: str | None = None  # gotowy napis wartości (zamiast liczby z jednostką)


class StatCard(NamedTuple):
    left: StatColumn
    right: StatColumn


def exercise_stat_cards(
    load_type: str, effort_type: str, daily: dict[date, DailyStats], start: date, interval: str, today: date
) -> tuple[StatCard, StatCard, StatCard]:
    """Wartości trzech pól statystyk pod wykresami W1, W2 i W3 dla okresu zaczynającego się w `start`."""
    previous = shift_period(start, interval, -1)
    series = period_series(daily, start, interval, today)
    prev_series = period_series(daily, previous, interval, today)
    unit1, unit3 = STAT_FIRST_TITLES[load_type][2], STAT_SECOND_TITLES[effort_type][1]
    month = interval == "month"
    vs_prev = "vs. poprzedni miesiąc" if month else "vs. poprzedni tydzień"
    vs_selected = "vs. wybrany miesiąc" if month else "vs. wybrany tydzień"
    total, best = period_stats(series)
    prev_total, prev_best = period_stats(prev_series)
    total2, best2 = period_second_stats(series)
    prev_total2, prev_best2 = period_second_stats(prev_series)
    overall = history_max(daily)
    total_label2, best_label2 = STAT_SECOND_LABELS[effort_type]
    return (
        StatCard(
            StatColumn(stat_total_label(load_type), total, unit1, percent_change(total, prev_total), vs_prev),
            StatColumn("Rekord serii", best, unit1, percent_change(best, prev_best), vs_prev),
        ),
        StatCard(
            StatColumn(STAT_PEAK_LABELS[load_type], best, unit1, percent_change(best, prev_best), vs_prev),
            StatColumn("Max od początku", overall, unit1, percent_change(overall, best), vs_selected),
        ),
        StatCard(
            StatColumn(total_label2, total2, unit3, percent_change(total2, prev_total2), vs_prev),
            StatColumn(best_label2, best2, unit3, percent_change(best2, prev_best2), vs_prev),
        ),
    )


def period_label_step(count: int, plot_width: float, min_slot: float = 13) -> int:
    """Co który dzień pokazać etykietę osi X: 1, gdy każda mieści się w `min_slot` px, inaczej 2."""
    return 1 if count * min_slot <= plot_width else 2


def nearest_day_index(x: float, left: float, width: float, count: int) -> int:
    """Indeks dnia najbliższego dotknięciu w poziomie (x względem wykresu; `left` = szerokość osi Y)."""
    if count <= 1 or width <= left:
        return 0
    return max(0, min(count - 1, int((x - left) / (width - left) * count)))


def fmt_stat_number(value: float) -> str:
    """Maksymalnie 2 miejsca po przecinku, bez zbędnych zer."""
    text = f"{round(value, 2):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


# --- wykres liczby treningów: okno 12 okresów ---
COUNT_WINDOW = 12


class CountWindow(NamedTuple):
    shift: int  # przesunięcie końca okna względem bieżącego okresu (po ograniczeniu do granic)
    end: date  # początek ostatniego okresu okna
    starts: list[date]  # początki wyświetlanych okresów (mniej niż 12, gdy historia jest krótsza)
    min_shift: int
    max_shift: int


def periods_between(first: date, last: date, interval: str) -> int:
    """Liczba okresów od okresu zawierającego `first` do okresu zawierającego `last`, włącznie (co najmniej 0)."""
    a, b = period_range(first, interval)[0], period_range(last, interval)[0]
    if interval == "week":
        return max((b - a).days // 7 + 1, 0)
    return max((b.year - a.year) * 12 + b.month - a.month + 1, 0)


def period_starts(end: date, interval: str, length: int = COUNT_WINDOW) -> list[date]:
    """Początki `length` kolejnych okresów kończących się na okresie zawierającym `end`."""
    return [shift_period(end, interval, -back) for back in range(length - 1, -1, -1)]


def count_window(
    today: date, interval: str, shift: int, first_workout: date | None, last_done: date | None
) -> CountWindow:
    """Okno 12 okresów kończące się `shift` okresów od bieżącego; `shift` jest ograniczany do granic.

    Górna granica końca okna: późniejszy z okresów - bieżący i najnowszego wykonanego treningu. Dolna: okno zaczyna się
    najwcześniej w okresie pierwszego treningu; gdy historia jest krótsza niż okno (lub jej nie ma), nie ma cofania."""
    current = period_range(today, interval)[0]
    max_end = max(current, period_range(last_done, interval)[0]) if last_done else current
    max_shift = periods_between(current, max_end, interval) - 1
    min_shift = 0
    if first_workout:
        earliest_end = shift_period(first_workout, interval, COUNT_WINDOW - 1)
        if earliest_end <= current:
            min_shift = 1 - periods_between(earliest_end, current, interval)
    shift = max(min_shift, min(max_shift, shift))
    end = shift_period(current, interval, shift)
    starts = period_starts(end, interval)
    if first_workout:
        oldest = period_range(first_workout, interval)[0]
        starts = [d for d in starts if d >= oldest] or starts[-1:]
    return CountWindow(shift, end, starts, min_shift, max_shift)


def navigate_count_window(
    today: date, interval: str, shift: int, delta: int, first_workout: date | None, last_done: date | None
) -> int:
    """Nowe przesunięcie okna po kroku `delta` (-1 starsze, 1 nowsze); poza granicami zwraca dotychczasowe."""
    window = count_window(today, interval, shift, first_workout, last_done)
    target = window.shift + delta
    return target if window.min_shift <= target <= window.max_shift else window.shift


COUNT_SWIPE_FRACTION = 0.15  # część szerokości obszaru wykresu odpowiadająca jednemu okresowi przesunięcia


def swipe_periods(dx: float, width: float, fraction: float = COUNT_SWIPE_FRACTION) -> int:
    """Liczba okresów (ze znakiem) dla przeciągnięcia o dx px w obszarze o szerokości width: odległość / (fraction * width)
    w dół do całości; w lewo (dx < 0) dodatnia (nowsze dane), w prawo ujemna (starsze), poniżej progu 0."""
    unit = fraction * width
    if unit <= 0:
        return 0
    direction = interpret_swipe(dx, threshold=unit * (1 - 1e-9))  # tolerancja na błąd zmiennoprzecinkowy dokładnie na progu
    if not direction:
        return 0
    return direction * int(abs(dx) / unit + 1e-9)


def limit_swipe_periods(periods: int, shift: int, min_shift: int, max_shift: int) -> int:
    """Ogranicza przesunięcie o `periods` tak, by `shift + wynik` leżał w [min_shift, max_shift] (stoi na granicy -> 0)."""
    return max(min_shift - shift, min(max_shift - shift, periods))


def count_period_label(start: date, interval: str) -> str:
    """Etykieta okresu na osi X: „MM.RRRR” (miesiąc) lub „WW RRRR” (tydzień ISO i rok ISO)."""
    if interval == "week":
        iso_year, iso_week, _ = start.isocalendar()
        return f"{iso_week:02d} {iso_year}"
    return f"{start.month:02d}.{start.year}"


def count_by_period(days, starts: list[date], interval: str) -> list[int]:
    """Liczba (różnych) dni z `days` w każdym okresie zaczynającym się w `starts` (grupowanie bez zapytań)."""
    counts = dict.fromkeys(starts, 0)
    for day in set(days):
        start = period_range(day, interval)[0]
        if start in counts:
            counts[start] += 1
    return [counts[start] for start in starts]


def workouts_total_and_average(days, today: date, interval: str, first_workout: date | None) -> tuple[int, float]:
    """(treningi od pierwszego do dziś, średnia na okres od okresu pierwszego treningu do bieżącego włącznie)."""
    if first_workout is None:
        return 0, 0.0
    total = len({d for d in days if first_workout <= d <= today})
    return total, total / max(periods_between(first_workout, today, interval), 1)


def fmt_average(value: float) -> str:
    """Jedno miejsce po przecinku (przecinek dziesiętny), bez zbędnego zera: „3”, „2,6”, „0”."""
    return (f"{round(value, 1):.1f}".rstrip("0").rstrip(".") or "0").replace(".", ",")


def workouts_word(n: int) -> str:
    """Odmiana: 1 trening, 2-4 treningi, 5 i więcej treningów (12-14: treningów)."""
    if n == 1:
        return "trening"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "treningi"
    return "treningów"


def fmt_workouts(n: int) -> str:
    return f"{n} {workouts_word(n)}"


class WindowComparison(NamedTuple):
    total: int
    previous_total: int
    average: float
    previous_average: float
    total_pct: int | None
    average_pct: int | None


def compare_windows(days, end: date, interval: str, first_workout: date | None) -> WindowComparison:
    """Porównanie okna 12 okresów kończącego się w `end` z 12 okresami bezpośrednio przed nim.

    Średnia = treningi w oknie / 12 (okresy sprzed pierwszego treningu to 0, dzielnik stały). Poprzednie okno leżące
    w całości przed pierwszym treningiem (lub zerowe) nie daje porównania (None)."""
    current = count_by_period(days, period_starts(end, interval), interval)
    previous_end = shift_period(end, interval, -COUNT_WINDOW)
    previous = count_by_period(days, period_starts(previous_end, interval), interval)
    total, prev_total = sum(current), sum(previous)
    average, prev_average = total / COUNT_WINDOW, prev_total / COUNT_WINDOW
    before_first = first_workout is None or previous_end < period_range(first_workout, interval)[0]
    return WindowComparison(
        total,
        prev_total,
        average,
        prev_average,
        None if before_first else percent_change(total, prev_total),
        None if before_first else percent_change(average, prev_average),
    )


# --- zawężona skala osi Y wykresów ćwiczenia ---
class AxisScale(NamedTuple):
    lower: float
    upper: float
    ticks: list[float]


AXIS_PADDING = 0.12  # zapas z góry i z dołu jako część rozpiętości danych
AXIS_SINGLE_PADDING = 0.1  # jedna wartość lub wszystkie równe: zapas jako część wartości
AXIS_MAX_INTERVALS = 4  # co najwyżej 5 etykiet (4 odstępy)


def nice_axis_scale(values) -> AxisScale:
    """Skala osi Y dopasowana do `values`: równy zapas (ok. 12% rozpiętości) z góry i z dołu, „ładny” krok
    (1, 2, 2,5, 5 × 10^k), 4-5 etykiet, dolna granica >= 0. Jedna wartość lub równe: zapas 10% wartości;
    same zera i brak danych: 0-1."""
    values = list(values)
    if not values or max(values) <= 0:
        return AxisScale(0, 1, [0, 1])
    low, high = min(values), max(values)
    pad = high * AXIS_SINGLE_PADDING if high == low else (high - low) * AXIS_PADDING
    low, high = max(0.0, low - pad), high + pad
    raw = (high - low) / AXIS_MAX_INTERVALS
    base = 10 ** math.floor(math.log10(raw))
    first = last = 0
    for step in (m * base * 10**e for e in (0, 1) for m in (1, 2, 2.5, 5)):
        first = math.floor(round(low / step, 9))
        last = math.ceil(round(high / step, 9))
        if last - first <= AXIS_MAX_INTERVALS:
            break
    ticks = [round(i * step, 9) for i in range(first, last + 1)]
    return AxisScale(ticks[0], ticks[-1], ticks)


def move_item(items, old_index: int, new_index: int) -> list:
    """Kopia listy z elementem z `old_index` przeniesionym na `new_index` (pozycja po przesunięciu)."""
    n = len(items)
    if not (0 <= old_index < n and 0 <= new_index < n):
        raise ValidationError("Nieprawidłowa pozycja ćwiczenia.")
    result = list(items)
    result.insert(new_index, result.pop(old_index))
    return result


# --- stan nawigacji: zakładki i stos otwartych warstw (bez Flet) ---
TAB_WORKOUT, TAB_STATS = "workout", "stats"
LAYER_CALENDAR = "calendar"
BACK_LAYER, BACK_TAB, BACK_EXIT = "layer", "tab", "exit"


@dataclass(eq=False)
class Layer:
    name: str
    on_back: Callable[[], None] | None = None


class NavState:
    """Zakładka, zakładka sprzed otwarcia kalendarza i stos otwartych warstw (kalendarz, okna, listy).

    Warstwa rejestruje się przy otwarciu (`open_layer`) i wyrejestrowuje przy zamknięciu dowolnym sposobem
    (`close_layer`, idempotentne). Cofnięcie (`back`) zdejmuje szczyt stosu i wywołuje jego `on_back`."""

    def __init__(self) -> None:
        self.tab = TAB_WORKOUT
        self.layers: list[Layer] = []
        self._calendar_return_tab: str | None = None

    def switch_tab(self, tab: str) -> None:
        self.tab = tab

    def open_layer(self, name: str, on_back: Callable[[], None] | None = None) -> Layer:
        layer = Layer(name, on_back)
        self.layers.append(layer)
        return layer

    def close_layer(self, layer: Layer) -> bool:
        """Wyrejestrowuje warstwę (np. po zamknięciu przyciskiem); False, gdy już jej nie ma. Zamknięcie kalendarza
        przywraca zakładkę sprzed jego otwarcia."""
        if layer not in self.layers:
            return False
        self.layers.remove(layer)
        if layer.name == LAYER_CALENDAR:
            self._leave_calendar()
        return True

    def open_calendar(self, on_back: Callable[[], None] | None = None) -> Layer:
        """Otwiera kalendarz bez zmiany zakładki; zapamiętuje aktywną."""
        self._calendar_return_tab = self.tab
        return self.open_layer(LAYER_CALENDAR, on_back)

    def _leave_calendar(self) -> None:
        if self._calendar_return_tab is not None:
            self.tab, self._calendar_return_tab = self._calendar_return_tab, None

    def select_day_from_calendar(self, layer: Layer) -> None:
        """Wybór dnia w kalendarzu: zamyka go i przechodzi do „Workout”."""
        self.close_layer(layer)
        self.tab = TAB_WORKOUT

    def back(self) -> str:
        """Systemowe cofnięcie: zamyka najwyżej otwartą warstwę (BACK_LAYER); bez warstw na „Statystykach” wraca do
        „Workout” (BACK_TAB); bez warstw na „Workout” zwraca BACK_EXIT (zamknięcie aplikacji)."""
        if self.layers:
            layer = self.layers[-1]
            self.close_layer(layer)
            if layer.on_back is not None:
                layer.on_back()
            return BACK_LAYER
        if self.tab != TAB_WORKOUT:
            self.tab = TAB_WORKOUT
            return BACK_TAB
        return BACK_EXIT


# --- pomocnicze (na pobranych, odłączonych obiektach) ---
def has_snapshot_to_paste(snapshot: WorkoutSnapshot | None) -> bool:
    """Czy w pamięci jest skopiowany trening, który można wkleić."""
    return snapshot is not None


def done_sets_count(workout: Workout) -> int:
    return sum(1 for we in workout.exercises for st in we.sets if st.done)


def y_axis_ticks(max_value: float, integer: bool = False, target: int = 4) -> tuple[float, list[float]]:
    """Skala osi Y od 0: (górna granica, wartości etykiet). Krok „ładny” (1, 2, 2,5, 5 × 10^k); dla liczb całkowitych krok >= 1."""
    if max_value <= 0:
        return 1, [0, 1]
    raw = max_value / target
    base = 10 ** math.floor(math.log10(raw))
    step = next(m * base for m in (1, 2, 2.5, 5, 10) if m * base >= raw)
    if integer:
        step = max(1, math.ceil(step))
    count = math.ceil(round(max_value / step, 9))
    ticks = [round(i * step, 6) for i in range(count + 1)]
    return ticks[-1], ticks


# --- dane testowe (czysta logika, bez bazy) ---
DEMO_EXERCISES = ("Barbell Bench Press", "Stairmaster / Stair Climber", "Cycling")
DEMO_WEEKDAYS = (0, 2, 4)  # poniedziałek, środa, piątek
DEMO_MONTHS = 3


class DemoSet(NamedTuple):
    weight_kg: float | None = None
    distance_m: int | None = None
    reps: int | None = None
    duration_s: int | None = None
    done: bool = True


class DemoExercise(NamedTuple):
    name: str  # nazwa angielska z katalogu; pełną nazwę w bazie tworzy exercise_display_name
    sets: tuple[DemoSet, ...]


class DemoWorkout(NamedTuple):
    day: date
    exercises: tuple[DemoExercise, ...]


def demo_catalog_measures(name: str) -> tuple[str, str]:
    """(pierwsza, druga miara) ćwiczenia startowego o nazwie angielskiej `name`."""
    for items in STARTER_EXERCISES.values():
        for en, _pl, load, effort in items:
            if en == name:
                return load, effort
    raise KeyError(name)


def demo_start_date(today: date) -> date:
    year, month = shift_month(today.year, today.month, -DEMO_MONTHS)
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def generate_demo_workouts(today: date, seed: int = 42) -> list[DemoWorkout]:
    """Treningi pn/śr/pt z ostatnich 3 miesięcy do `today` włącznie; każdy z trzema ćwiczeniami demo.

    Wartości w jednostkach bazowych (kg, m, s), z lekkim wzrostem w czasie i losowością o stałym ziarnie."""
    rng = random.Random(seed)
    start = demo_start_date(today)
    days = [start + timedelta(days=i) for i in range((today - start).days + 1)]
    days = [d for d in days if d.weekday() in DEMO_WEEKDAYS]
    workouts = []
    for index, day in enumerate(days):
        progress = index / max(len(days) - 1, 1)  # 0..1: lekki wzrost w czasie
        bench = tuple(
            DemoSet(
                weight_kg=min(80.0, max(60.0, round((60 + 15 * progress + rng.uniform(-3, 3)) / 2.5) * 2.5)),
                reps=rng.randint(6, 10),
            )
            for _ in range(rng.randint(3, 4))
        )
        stairs = tuple(
            DemoSet(reps=int(minutes * rng.uniform(3.5, 4.5)), duration_s=minutes * 60)
            for minutes in (rng.randint(10 + round(5 * progress), 15 + round(10 * progress)) for _ in range(rng.randint(1, 2)))
        )
        cycling = []
        for _ in range(rng.randint(1, 2)):
            km = round(10 + 10 * progress + rng.uniform(0, 5), 1)
            speed = rng.uniform(22, 28) + 2 * progress  # km/h
            cycling.append(DemoSet(distance_m=int(km * 1000), duration_s=int(km / speed * 3600)))
        workouts.append(
            DemoWorkout(
                day,
                (
                    DemoExercise(DEMO_EXERCISES[0], bench),
                    DemoExercise(DEMO_EXERCISES[1], stairs),
                    DemoExercise(DEMO_EXERCISES[2], tuple(cycling)),
                ),
            )
        )
    return workouts

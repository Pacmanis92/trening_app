import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import NamedTuple

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .models import Category, Exercise, Workout, WorkoutExercise, WorkoutSet

LOAD_TYPES = ("weight", "distance", "reps", "floors")
EFFORT_TYPES = ("reps", "time")

EMPTY_SUMMARY = "Brak wykonanych serii"

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
        if kind == "weight" and by_reps:
            lines = [f"Suma przewalonego żelastwa: {_fmt_weight_total(sum(first(st) * second(st) for st in done), *units)}"]
        elif kind == "weight":
            lines = [f"Łączny czas: {fmt_time(sum(second(st) for st in done))}"]
        elif kind == "distance" and by_reps:
            lines = [f"Łączny dystans: {_fmt_distance_total_units(sum(first(st) * second(st) for st in done), *units)}"]
        else:
            if kind == "distance":
                lines = [f"Łączny dystans: {_fmt_distance_total_units(sum(first(st) for st in done), *units)}"]
            else:
                lines = [f"{TOTAL_LABELS[kind]}: {sum(first(st) for st in done)}"]
            lines.append(f"Łączny czas: {fmt_time(sum(second(st) for st in done))}")
        groups.append(SummaryGroup(" / ".join(units), lines))
    if len(groups) == 1:
        groups[0] = SummaryGroup("", groups[0].lines)
    return groups


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
        """Idempotentnie: dopisuje brakujące kategorie i ćwiczenia startowe (po nazwie)."""
        with self._sf.begin() as s:
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
        if load_type not in LOAD_TYPES or effort_type not in EFFORT_TYPES:
            raise ValidationError("Nieprawidłowy typ ćwiczenia.")
        if load_type == "reps" and effort_type == "reps":
            raise ValidationError("Powtórzenia × Powtórzenia nie są dozwolone.")
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
            position = s.scalar(
                select(func.count(WorkoutExercise.id)).where(
                    WorkoutExercise.workout_id == workout_id
                )
            )
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


# --- pomocnicze (na pobranych, odłączonych obiektach) ---
def has_snapshot_to_paste(snapshot: WorkoutSnapshot | None) -> bool:
    """Czy w pamięci jest skopiowany trening, który można wkleić."""
    return snapshot is not None


def done_sets_count(workout: Workout) -> int:
    return sum(1 for we in workout.exercises for st in we.sets if st.done)

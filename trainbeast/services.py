import math
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .models import Exercise, Workout, WorkoutExercise, WorkoutSet

LOAD_TYPES = ("weight", "distance")
EFFORT_TYPES = ("reps", "time")

EMPTY_SUMMARY = "Brak wykonanych serii"
SUMMARY_SEP = "    "

# (nazwa, load_type, effort_type)
STARTER_EXERCISES = [
    ("Wyciskanie sztangi leżąc", "weight", "reps"),
    ("Przysiad ze sztangą", "weight", "reps"),
    ("Martwy ciąg", "weight", "reps"),
    ("Wiosłowanie sztangą", "weight", "reps"),
    ("Wyciskanie nad głowę", "weight", "reps"),
    ("Podciąganie", "weight", "reps"),
    ("Uginanie ramion", "weight", "reps"),
    ("Prostowanie ramion na wyciągu", "weight", "reps"),
    ("Wspięcia na palce", "weight", "reps"),
    ("Pull-up hold", "weight", "time"),
]


class ValidationError(ValueError):
    """Błąd danych wejściowych, z komunikatem po polsku."""


def parse_weight(value) -> float:
    try:
        weight = float(str(value).strip().replace(",", "."))
    except ValueError:
        raise ValidationError("Ciężar musi być liczbą.") from None
    if not math.isfinite(weight):
        raise ValidationError("Ciężar musi być liczbą.")
    if weight < 0:
        raise ValidationError("Ciężar nie może być ujemny.")
    return weight


def parse_reps(value) -> int:
    try:
        reps = int(str(value).strip())
    except ValueError:
        raise ValidationError("Powtórzenia muszą być liczbą całkowitą.") from None
    if reps < 0:
        raise ValidationError("Powtórzenia nie mogą być ujemne.")
    return reps


def _parse_part(value, what: str) -> int:
    """Człon dystansu/czasu: puste pole = 0, reszta musi być nieujemną liczbą całkowitą."""
    text = str(value).strip()
    if not text:
        return 0
    try:
        number = int(text)
    except ValueError:
        raise ValidationError(f"{what}: wpisz liczbę całkowitą.") from None
    if number < 0:
        raise ValidationError(f"{what}: wartość nie może być ujemna.")
    return number


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
def fmt_weight(value: float | None) -> str:
    return f"{round(value or 0, 3):g} kg"


def _join(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def fmt_distance(meters: int | None) -> str:
    km, m = divmod(meters or 0, 1000)
    return _join(f"{km}km" if km else "", f"{m}m" if m else "") or "0m"


def fmt_distance_total(meters: int | None) -> str:
    km, m = divmod(meters or 0, 1000)
    return _join(f"{km} km" if km else "", f"{m} m" if m else "") or "0 m"


def fmt_time(seconds: int | None) -> str:
    h, rest = divmod(seconds or 0, 3600)
    m, s = divmod(rest, 60)
    return _join(f"{h}h" if h else "", f"{m}m" if m else "", f"{s}s" if s else "") or "0s"


def fmt_value(kind: str, value, with_unit: bool = True) -> str:
    """Wspólny format wartości: kind = weight | distance | reps | time."""
    if kind == "weight":
        return fmt_weight(value)
    if kind == "distance":
        return fmt_distance(value)
    if kind == "time":
        return fmt_time(value)
    return f"{value or 0} powt." if with_unit else str(value or 0)


def fmt_set_line(exercise: Exercise, st: WorkoutSet, number: int) -> str:
    """Krótka linia serii do widoku skondensowanego, np. „1. 20 kg × 10 powt.”."""
    if exercise.load_type == "weight":
        first = fmt_value("weight", st.weight_kg)
    else:
        first = fmt_value("distance", st.distance_m)
    if exercise.effort_type == "reps":
        return f"{number}. {first} × {fmt_value('reps', st.reps)}"
    return f"{number}. {first} — {fmt_value('time', st.duration_s)}"


def summarize_exercise(exercise: Exercise, sets) -> list[str]:
    """Podsumowanie wykonanych serii (linie tekstu); serie niewykonane są pomijane."""
    done = [st for st in sets if st.done]
    if not done:
        return [EMPTY_SUMMARY]
    by_weight = exercise.load_type == "weight"
    by_reps = exercise.effort_type == "reps"

    def first(st) -> float | int:
        return (st.weight_kg or 0.0) if by_weight else (st.distance_m or 0)

    def second(st) -> int:
        return (st.reps or 0) if by_reps else (st.duration_s or 0)

    groups: dict[float | int, int] = {}
    for st in done:
        groups[first(st)] = groups.get(first(st), 0) + second(st)

    lines = []
    for key in sorted(groups):
        head = f"Ciężar: {fmt_value('weight', key)}" if by_weight else f"Dystans: {fmt_value('distance', key)}"
        tail = (
            f"Powtórzenia: {fmt_value('reps', groups[key], with_unit=False)}"
            if by_reps
            else f"Czas: {fmt_value('time', groups[key])}"
        )
        lines.append(f"{head}{SUMMARY_SEP}{tail}")

    if by_weight and by_reps:
        lines.append(f"Suma przewalonego żelastwa: {fmt_weight(sum(first(st) * second(st) for st in done))}")
    elif by_weight:
        lines.append(f"Łączny czas: {fmt_time(sum(second(st) for st in done))}")
    elif by_reps:
        lines.append(f"Łączny dystans: {fmt_distance_total(sum(first(st) * second(st) for st in done))}")
    else:
        lines.append(f"Łączny dystans: {fmt_distance_total(sum(first(st) for st in done))}")
        lines.append(f"Łączny czas: {fmt_time(sum(second(st) for st in done))}")
    return lines


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
        """Idempotentnie: dopisuje brakujące ćwiczenia startowe (po nazwie)."""
        with self._sf.begin() as s:
            existing = {n.lower() for n in s.scalars(select(Exercise.name))}
            s.add_all(
                Exercise(name=name, load_type=load, effort_type=effort)
                for name, load, effort in STARTER_EXERCISES
                if name.lower() not in existing
            )

    # --- ćwiczenia (definicje) ---
    def list_exercises(self) -> list[Exercise]:
        with self._sf() as s:
            return list(s.scalars(select(Exercise).order_by(Exercise.id)))

    def create_exercise(
        self, name: str, load_type: str = "weight", effort_type: str = "reps"
    ) -> Exercise:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Podaj nazwę ćwiczenia.")
        if load_type not in LOAD_TYPES or effort_type not in EFFORT_TYPES:
            raise ValidationError("Nieprawidłowy typ ćwiczenia.")
        duplicate = ValidationError("Ćwiczenie o takiej nazwie już istnieje.")
        try:
            with self._sf.begin() as s:
                if s.scalar(select(Exercise.id).where(func.lower(Exercise.name) == name.lower())):
                    raise duplicate
                exercise = Exercise(name=name, load_type=load_type, effort_type=effort_type)
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

    def get_last_workout(self, today: date | None = None) -> Workout | None:
        """Najnowszy trening z datą nie późniejszą niż dziś, który ma co najmniej jedno ćwiczenie."""
        with self._sf() as s:
            return s.scalars(
                _workout_query()
                .where(
                    Workout.workout_date <= (today or date.today()),
                    Workout.exercises.any(),
                )
                .order_by(Workout.workout_date.desc())
            ).first()

    def rename_workout(self, workout_id: int, name: str) -> None:
        with self._sf.begin() as s:
            s.get(Workout, workout_id).name = (name or "").strip()

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
            reps=0 if exercise.effort_type == "reps" else None,
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

    def remove_set(self, set_id: int) -> None:
        with self._sf.begin() as s:
            ws = s.get(WorkoutSet, set_id)
            if ws is not None:
                s.delete(ws)


# --- pomocnicze (na pobranych, odłączonych obiektach) ---
def done_sets_count(workout: Workout) -> int:
    return sum(1 for we in workout.exercises for st in we.sets if st.done)

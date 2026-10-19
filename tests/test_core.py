from datetime import date, timedelta

import pytest

from sqlalchemy import inspect, text

from trainbeast.database import make_engine, make_session_factory
from trainbeast.models import Category, Exercise, Workout, WorkoutExercise, WorkoutSet
from trainbeast.services import (
    STARTER_CATEGORIES,
    STARTER_EXERCISES,
    TrainingService,
    ValidationError,
    done_sets_count,
    fmt_value,
    parse_distance,
    parse_duration,
    fmt_set_line,
    summarize_exercise,
)


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def svc(db_url):
    engine = make_engine(db_url)
    return TrainingService(make_session_factory(engine))


TODAY = date.today()
CAT = STARTER_CATEGORIES[0]
STARTER_COUNT = sum(len(v) for v in STARTER_EXERCISES.values())


def count(svc, model):
    with svc._sf() as s:
        return len(s.query(model).all())


def test_create_workout_today_sets_started_at(svc):
    w = svc.create_workout(TODAY, "Push")
    assert w.name == "Push" and w.workout_date == TODAY
    assert w.started_at is not None and w.ended_at is None
    assert svc.get_workout_by_date(TODAY).id == w.id


@pytest.mark.parametrize("offset", [-5, 3])
def test_create_workout_past_and_future_has_no_started_at(svc, offset):
    day = TODAY + timedelta(days=offset)
    w = svc.create_workout(day)
    assert w.workout_date == day and w.started_at is None


def test_one_workout_per_day(svc):
    svc.create_workout(TODAY)
    with pytest.raises(ValidationError):
        svc.create_workout(TODAY)
    assert count(svc, Workout) == 1


def test_get_workout_by_date(svc):
    w = svc.create_workout(TODAY + timedelta(days=2), "Za dwa dni")
    assert svc.get_workout_by_date(TODAY + timedelta(days=2)).id == w.id
    assert svc.get_workout_by_date(TODAY + timedelta(days=1)) is None


def test_add_exercise_and_sets(svc):
    w = svc.create_workout(TODAY)
    ex = svc.list_exercises()[0]
    we = svc.add_exercise_to_workout(w.id, ex.id)
    assert len(we.sets) == 1
    svc.update_set(we.sets[0].id, weight_kg="82,5", reps="8", done=True)
    new = svc.add_set(we.id)
    assert (new.weight_kg, new.reps, new.done) == (82.5, 8, False)
    assert (new.distance_m, new.duration_s) == (None, None)
    custom = svc.add_exercise_to_workout(w.id, svc.create_exercise("Dipy", CAT).id)
    assert custom.exercise.name == "Dipy"
    assert len(svc.get_workout(w.id).exercises) == 2


@pytest.mark.parametrize("load", ["weight", "distance", "reps", "floors"])
@pytest.mark.parametrize("effort", ["reps", "time"])
def test_create_exercise_all_type_combinations(svc, load, effort):
    if (load, effort) == ("reps", "reps"):
        with pytest.raises(ValidationError):
            svc.create_exercise("Własne", CAT, load, effort)
        return
    ex = svc.create_exercise("  Własne  ", CAT, load, effort)
    assert (ex.name, ex.load_type, ex.effort_type) == ("Własne", load, effort)
    saved = next(e for e in svc.list_exercises() if e.name == "Własne")
    assert (saved.load_type, saved.effort_type) == (load, effort)
    we = svc.add_exercise_to_workout(svc.create_workout(TODAY).id, ex.id)
    st = we.sets[0]
    assert (st.weight_kg is not None, st.distance_m is not None) == (load == "weight", load == "distance")
    assert (st.reps is not None) == (load in ("reps", "floors") or effort == "reps")
    assert (st.duration_s is not None) == (effort == "time")


@pytest.mark.parametrize("name", ["", "   ", "dIPY", "Dipy"])
def test_create_exercise_rejects_empty_and_duplicate(svc, name):
    svc.create_exercise("Dipy", CAT)
    before = len(svc.list_exercises())
    with pytest.raises(ValidationError):
        svc.create_exercise(name, CAT)
    assert len(svc.list_exercises()) == before


def test_distance_and_time_set_roundtrip(svc):
    ex = svc.create_exercise("Bieg", CAT, "distance", "time")
    we = svc.add_exercise_to_workout(svc.create_workout(TODAY).id, ex.id)
    svc.update_set(
        we.sets[0].id,
        distance_m=parse_distance("5", "400"),
        duration_s=parse_duration("0", "0", "90"),
        done=True,
    )
    st = svc.get_workout_by_date(TODAY).exercises[0].sets[0]
    assert (st.distance_m, st.duration_s, st.weight_kg, st.reps) == (5400, 90, None, None)
    copy = svc.add_set(we.id)
    assert (copy.distance_m, copy.duration_s, copy.done) == (5400, 90, False)
    assert parse_duration("1", "90", "") == 3600 + 5400
    assert parse_distance("", "1500") == 1500


@pytest.mark.parametrize(
    "call",
    [
        lambda: parse_distance("-1", "0"),
        lambda: parse_duration("0", "-5", "0"),
        lambda: parse_duration("0", "0", "abc"),
    ],
)
def test_negative_or_bad_parts_rejected(call):
    with pytest.raises(ValidationError):
        call()


def test_negative_base_values_rejected(svc):
    ex = svc.create_exercise("Bieg", CAT, "distance", "time")
    we = svc.add_exercise_to_workout(svc.create_workout(TODAY).id, ex.id)
    for kwargs in ({"distance_m": -1}, {"duration_s": -1}):
        with pytest.raises(ValidationError):
            svc.update_set(we.sets[0].id, **kwargs)
    st = svc.get_workout_by_date(TODAY).exercises[0].sets[0]
    assert (st.distance_m, st.duration_s) == (0, 0)


class _Ex:
    def __init__(self, load, effort):
        self.load_type, self.effort_type = load, effort


class _St:
    def __init__(self, first=0, second=0, done=True, load="weight", effort="reps"):
        self.weight_kg = first if load == "weight" else None
        self.distance_m = first if load == "distance" else None
        self.reps = second if effort == "reps" else None
        self.duration_s = second if effort == "time" else None
        self.done = done


def test_summary_weight_reps_example():
    sets = [_St(20, 10), _St(30, 10), _St(30, 10), _St(40, 10), _St(100, 10, done=False)]
    assert summarize_exercise(_Ex("weight", "reps"), sets) == [
        "Ciężar: 20 kg    Powtórzenia: 10",
        "Ciężar: 30 kg    Powtórzenia: 20",
        "Ciężar: 40 kg    Powtórzenia: 10",
        "Suma przewalonego żelastwa: 1200 kg",
    ]


def test_summary_weight_time():
    sets = [_St(20, 90, effort="time"), _St(20, 3600 + 35 * 60 + 15, effort="time"), _St(5, 7, effort="time", done=False)]
    assert summarize_exercise(_Ex("weight", "time"), sets) == [
        "Ciężar: 20 kg    Czas: 1h 36m 45s",
        "Łączny czas: 1h 36m 45s",
    ]


def test_summary_distance_reps():
    sets = [_St(400, 10, load="distance"), _St(400, 1, load="distance"), _St(1000, 5, load="distance")]
    assert summarize_exercise(_Ex("distance", "reps"), sets) == [
        "Dystans: 400m    Powtórzenia: 11",
        "Dystans: 1km    Powtórzenia: 5",
        "Łączny dystans: 9 km 400 m",
    ]


def test_summary_distance_time():
    sets = [
        _St(5400, 35 * 60 + 10, load="distance", effort="time"),
        _St(5400, 60, load="distance", effort="time"),
        _St(100, 1, load="distance", effort="time", done=False),
    ]
    assert summarize_exercise(_Ex("distance", "time"), sets) == [
        "Dystans: 5km 400m    Czas: 36m 10s",
        "Łączny dystans: 10 km 800 m",
        "Łączny czas: 36m 10s",
    ]


def test_summary_ignores_undone_sets():
    assert summarize_exercise(_Ex("weight", "reps"), [_St(20, 10, done=False)]) == ["Brak wykonanych serii"]
    assert summarize_exercise(_Ex("weight", "reps"), []) == ["Brak wykonanych serii"]


def test_fmt_value_units_and_zero_parts():
    assert fmt_value("weight", 20) == "20 kg"
    assert fmt_value("distance", 5400) == "5km 400m"
    assert fmt_value("distance", 400) == "400m"
    assert fmt_value("distance", 5000) == "5km"
    assert fmt_value("distance", 0) == "0m"
    assert fmt_value("reps", 10) == "10 powt."
    assert fmt_value("reps", 10, with_unit=False) == "10"
    assert fmt_value("time", 2 * 3600 + 35 * 60 + 45) == "2h 35m 45s"
    assert fmt_value("time", 3600) == "1h"
    assert fmt_value("time", 0) == "0s"


def test_summary_distance_time_row_format():
    sets = [_St(2200, 325, load="distance", effort="time")]
    assert summarize_exercise(_Ex("distance", "time"), sets)[0] == "Dystans: 2km 200m    Czas: 5m 25s"


def test_summary_weight_time_and_distance_reps_row_format():
    assert summarize_exercise(_Ex("weight", "time"), [_St(20, 90, effort="time")])[0] == "Ciężar: 20 kg    Czas: 1m 30s"
    assert summarize_exercise(_Ex("distance", "reps"), [_St(400, 10, load="distance")])[0] == "Dystans: 400m    Powtórzenia: 10"


def test_toggle_done_changes_only_one_set_and_persists(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    w = svc.create_workout(TODAY)
    we = svc.add_exercise_to_workout(w.id, svc.list_exercises()[0].id)
    svc.add_set(we.id)
    svc.add_set(we.id)
    ids = [st.id for st in svc.get_workout(w.id).exercises[0].sets]
    svc.update_set(ids[1], done=True)
    reopened = TrainingService(make_session_factory(make_engine(db_url)))
    assert [st.done for st in reopened.get_workout(w.id).exercises[0].sets] == [False, True, False]
    reopened.update_set(ids[1], done=False)
    assert [st.done for st in reopened.get_workout(w.id).exercises[0].sets] == [False, False, False]


def test_edit_and_remove_set(svc):
    w = svc.create_workout(TODAY)
    we = svc.add_exercise_to_workout(w.id, svc.list_exercises()[0].id)
    set_id = we.sets[0].id
    svc.update_set(set_id, weight_kg=60, reps=10)
    st = svc.get_workout(w.id).exercises[0].sets[0]
    assert (st.weight_kg, st.reps) == (60.0, 10)
    svc.remove_set(set_id)
    assert svc.get_workout(w.id).exercises[0].sets == []


def test_cascade_delete_exercise_removes_sets(svc):
    w = svc.create_workout(TODAY)
    we = svc.add_exercise_to_workout(w.id, svc.list_exercises()[0].id)
    svc.add_set(we.id)
    assert count(svc, WorkoutSet) == 2
    svc.remove_exercise_from_workout(we.id)
    assert count(svc, WorkoutSet) == 0
    assert count(svc, WorkoutExercise) == 0
    assert count(svc, Exercise) == STARTER_COUNT  # definicja zostaje


@pytest.mark.parametrize(
    "weight,reps", [("-1", "5"), ("50", "-3"), ("abc", "5"), ("50", ""), ("", "5"), ("50", "2.5")]
)
def test_validation_rejects_bad_values(svc, weight, reps):
    w = svc.create_workout(TODAY)
    we = svc.add_exercise_to_workout(w.id, svc.list_exercises()[0].id)
    with pytest.raises(ValidationError):
        svc.update_set(we.sets[0].id, weight_kg=weight, reps=reps)
    st = svc.get_workout(w.id).exercises[0].sets[0]
    assert (st.weight_kg, st.reps) == (0.0, 0)


def test_workout_survives_reopen(db_url):
    first = TrainingService(make_session_factory(make_engine(db_url)))
    w = first.create_workout(TODAY, "Nogi")
    we = first.add_exercise_to_workout(w.id, first.list_exercises()[1].id)
    first.update_set(we.sets[0].id, weight_kg=100, reps=5, done=True)

    second = TrainingService(make_session_factory(make_engine(db_url)))
    resumed = second.get_workout_by_date(TODAY)
    assert resumed.id == w.id and resumed.name == "Nogi" and resumed.ended_at is None
    st = resumed.exercises[0].sets[0]
    assert (st.weight_kg, st.reps, st.done) == (100.0, 5, True)


def test_last_workout_ignores_future_dates_and_empty_workouts(svc):
    ex_id = svc.list_exercises()[0].id
    past = svc.create_workout(TODAY - timedelta(days=3))
    svc.add_exercise_to_workout(past.id, ex_id)
    future = svc.create_workout(TODAY + timedelta(days=2))
    svc.add_exercise_to_workout(future.id, ex_id)
    svc.create_workout(TODAY)  # bez ćwiczeń
    assert svc.get_last_workout().id == past.id


def test_last_workout_none_when_nothing_qualifies(svc):
    svc.create_workout(TODAY - timedelta(days=1))
    assert svc.get_last_workout() is None


def test_delete_workout_cascades(svc):
    w = svc.create_workout(TODAY)
    we = svc.add_exercise_to_workout(w.id, svc.list_exercises()[0].id)
    svc.add_set(we.id)
    svc.delete_workout(w.id)
    assert count(svc, Workout) == count(svc, WorkoutExercise) == count(svc, WorkoutSet) == 0


# --- kategorie, sekcje, seed, migracja ---
def find(svc, en):
    return next(e for e in svc.list_exercises() if e.name.startswith(en + " ("))


def test_nine_categories_in_order(svc):
    assert [c.name for c in svc.get_categories()] == STARTER_CATEGORIES
    assert len(STARTER_CATEGORIES) == 9
    assert STARTER_CATEGORIES[0] == "Chest (Klatka piersiowa)"
    assert STARTER_CATEGORIES[-1] == "Cardio (Trening kondycyjny)"


def test_exercise_names_and_units(svc):
    bench = find(svc, "Barbell Bench Press")
    assert bench.name == "Barbell Bench Press (Wyciskanie sztangi na ławce poziomej)"
    assert (bench.category, bench.load_type, bench.effort_type) == (CAT, "weight", "reps")
    stair = find(svc, "Stairmaster / Stair Climber")
    assert (stair.load_type, stair.effort_type) == ("floors", "time")
    assert (find(svc, "Bench Dips").load_type, find(svc, "Bench Dips").effort_type) == ("weight", "reps")
    twist = find(svc, "Dumbbell Russian Twist")
    assert (twist.load_type, twist.effort_type) == ("weight", "reps")
    assert (find(svc, "Plank").load_type, find(svc, "Plank").effort_type) == ("weight", "time")
    farmer = find(svc, "Dumbbell Farmer's Walk")
    assert (farmer.load_type, farmer.effort_type) == ("distance", "time")
    rope = find(svc, "Jump Rope")
    assert (rope.load_type, rope.effort_type) == ("weight", "time")
    assert (find(svc, "Running").load_type, find(svc, "Running").effort_type) == ("distance", "time")


def test_every_exercise_has_existing_category(svc):
    names = {c.name for c in svc.get_categories()}
    assert len(svc.list_exercises()) == STARTER_COUNT == 84
    assert all(e.category in names for e in svc.list_exercises())
    for category in STARTER_CATEGORIES:
        assert svc.get_exercises_by_category(category)


@pytest.mark.parametrize("category", ["", None, "Nie ma takiej"])
def test_create_exercise_rejects_missing_category(svc, category):
    before = len(svc.list_exercises())
    with pytest.raises(ValidationError):
        svc.create_exercise("Nowe", category)
    assert len(svc.list_exercises()) == before


def test_seed_is_idempotent(db_url):
    for _ in range(3):
        service = TrainingService(make_session_factory(make_engine(db_url)))
    assert len(service.get_categories()) == 9
    assert len(service.list_exercises()) == STARTER_COUNT


def test_custom_exercise_goes_to_its_category(svc):
    ex = svc.create_exercise("Własne", "Legs (Nogi)", "floors", "time")
    assert ex.category == "Legs (Nogi)"
    assert ex.name in [e.name for e in svc.get_exercises_by_category("Legs (Nogi)")]
    assert ex.name not in [e.name for e in svc.get_exercises_by_category(CAT)]


def test_floors_and_reps_measures_roundtrip(svc):
    w = svc.create_workout(TODAY)
    stair = svc.add_exercise_to_workout(w.id, find(svc, "Stairmaster / Stair Climber").id)
    svc.update_set(stair.sets[0].id, reps="12", duration_s=600, done=True)
    reps_ex = svc.create_exercise("Pompki własne", CAT, "reps", "time")
    own = svc.add_exercise_to_workout(w.id, reps_ex.id)
    svc.update_set(own.sets[0].id, reps="30", duration_s=60, done=True)
    loaded = {we.exercise.name: we for we in svc.get_workout(w.id).exercises}
    st = loaded[find(svc, "Stairmaster / Stair Climber").name].sets[0]
    assert (st.reps, st.duration_s, st.weight_kg, st.distance_m) == (12, 600, None, None)
    assert fmt_set_line(stair.exercise, st, 1) == "1. 12 pięt. — 10m"
    assert svc.add_set(stair.id).reps == 12
    lines = summarize_exercise(stair.exercise, [st])
    assert lines == [f"Piętra: 12    Czas: 10m", "Łączne piętra: 12", "Łączny czas: 10m"]
    st2 = loaded["Pompki własne"].sets[0]
    assert summarize_exercise(reps_ex, [st2])[0] == "Powtórzenia: 30    Czas: 1m"
    assert fmt_set_line(reps_ex, st2, 2) == "2. 30 powt. — 1m"


def test_add_section_appended_at_end_and_persists(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    svc.add_category("  Moja sekcja ")
    svc.add_category("Druga")
    expected = STARTER_CATEGORIES + ["Moja sekcja", "Druga"]
    assert [c.name for c in svc.get_categories()] == expected
    reopened = TrainingService(make_session_factory(make_engine(db_url)))
    assert [c.name for c in reopened.get_categories()] == expected


@pytest.mark.parametrize("name", ["", "   ", "chest (klatka piersiowa)", "  BACK (PLECY) ", "Moja", " moja "])
def test_add_section_rejects_empty_and_duplicates(svc, name):
    svc.add_category("Moja")
    before = len(svc.get_categories())
    with pytest.raises(ValidationError):
        svc.add_category(name)
    assert len(svc.get_categories()) == before


def test_exercise_in_custom_section(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    svc.add_category("Moja")
    assert svc.get_exercises_by_category("Moja") == []
    svc.create_exercise("Ruch", "Moja", "distance", "reps")
    reopened = TrainingService(make_session_factory(make_engine(db_url)))
    assert [e.name for e in reopened.get_exercises_by_category("Moja")] == ["Ruch"]
    assert "Ruch" not in [e.name for c in STARTER_CATEGORIES for e in reopened.get_exercises_by_category(c)]


def _old_db(url):
    """Baza w starym schemacie: exercise bez category + dane."""
    engine = make_engine(url)
    with engine.begin() as conn:
        for table in ("workout_set", "workout_exercise", "workout", "exercise", "category"):
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        conn.execute(text(
            "CREATE TABLE exercise (id INTEGER PRIMARY KEY, name VARCHAR(100) UNIQUE, "
            "load_type VARCHAR(10), effort_type VARCHAR(10))"
        ))
        conn.execute(text("INSERT INTO exercise (id, name, load_type, effort_type) VALUES (1, 'Stare', 'weight', 'reps')"))
        conn.execute(text("CREATE TABLE workout (id INTEGER PRIMARY KEY, workout_date DATE UNIQUE, name VARCHAR(100), started_at DATETIME, ended_at DATETIME)"))
        conn.execute(text("INSERT INTO workout (id, workout_date, name) VALUES (1, '2024-01-01', 'Stary')"))
        conn.execute(text("CREATE TABLE workout_exercise (id INTEGER PRIMARY KEY, workout_id INTEGER REFERENCES workout(id) ON DELETE CASCADE, exercise_id INTEGER REFERENCES exercise(id), position INTEGER)"))
        conn.execute(text("INSERT INTO workout_exercise VALUES (1, 1, 1, 0)"))
        conn.execute(text("CREATE TABLE workout_set (id INTEGER PRIMARY KEY, workout_exercise_id INTEGER REFERENCES workout_exercise(id) ON DELETE CASCADE, position INTEGER, weight_kg FLOAT, distance_m INTEGER, reps INTEGER, duration_s INTEGER, done BOOLEAN)"))
        conn.execute(text("INSERT INTO workout_set VALUES (1, 1, 0, 10, NULL, 5, NULL, 1)"))
    engine.dispose()


def test_migration_adds_column_and_cleans_only_once(db_url):
    _old_db(db_url)
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    assert "category" in {c["name"] for c in inspect(svc._sf.kw["bind"]).get_columns("exercise")}
    assert count(svc, Workout) == count(svc, WorkoutExercise) == count(svc, WorkoutSet) == 0
    assert "Stare" not in [e.name for e in svc.list_exercises()]
    assert len(svc.list_exercises()) == STARTER_COUNT
    # dane użytkownika po migracji nie są usuwane przy kolejnym uruchomieniu
    svc.create_workout(TODAY, "Nowy")
    svc.create_exercise("Własne", CAT)
    again = TrainingService(make_session_factory(make_engine(db_url)))
    assert count(again, Workout) == 1
    assert len(again.list_exercises()) == STARTER_COUNT + 1
    assert len(again.get_categories()) == 9


def test_fresh_db_is_not_cleaned(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    svc.create_workout(TODAY)
    TrainingService(make_session_factory(make_engine(db_url)))
    assert count(svc, Workout) == 1


# --- ograniczenia pól, ciężar, kalendarz ---
from trainbeast.services import (  # noqa: E402
    DIGIT_CHAR_PATTERN,
    MONTH_NAMES,
    fmt_decimal,
    is_valid_minsec_input,
    is_valid_weight_input,
    month_grid,
    parse_floors,
    parse_reps,
    parse_weight,
    shift_month,
)
import re  # noqa: E402


@pytest.mark.parametrize("text", ["", "0", "5", "05", "59", "00"])
def test_minsec_allowed(text):
    assert is_valid_minsec_input(text)


@pytest.mark.parametrize("text", ["60", "75", "150", "123", "5a", "-1", "5.", " 5", "٣"])
def test_minsec_rejected(text):
    assert not is_valid_minsec_input(text)


@pytest.mark.parametrize("text,value", [("2.5", 2.5), ("2,5", 2.5), ("80", 80.0), (",5", 0.5), ("0.5", 0.5)])
def test_weight_accepted(text, value):
    assert is_valid_weight_input(text)
    assert parse_weight(text) == value


@pytest.mark.parametrize("text", ["2.5.3", "2,5,3", "abc", "-1", "1e5", "", ",", "inf"])
def test_weight_rejected(text):
    with pytest.raises(ValidationError):
        parse_weight(text)


def test_weight_input_allows_intermediate_states_but_not_second_separator():
    assert all(is_valid_weight_input(t) for t in ["", "2.", ".", ","])
    assert not is_valid_weight_input("2.5.") and not is_valid_weight_input("2.5,3")


def test_integer_pattern_only_digits():
    assert re.fullmatch(DIGIT_CHAR_PATTERN, "7")
    assert not any(re.fullmatch(DIGIT_CHAR_PATTERN, c) for c in ".,- a")


@pytest.mark.parametrize("call", [lambda: parse_reps("2.5"), lambda: parse_floors("-1"), lambda: parse_reps("")])
def test_int_fields_reject_without_integer_message(call):
    with pytest.raises(ValidationError) as err:
        call()
    assert "całkowit" not in str(err.value)


def test_fractional_weight_roundtrip_and_summary(svc):
    we = svc.add_exercise_to_workout(svc.create_workout(TODAY).id, svc.list_exercises()[0].id)
    sid = we.sets[0].id
    svc.update_set(sid, weight_kg=parse_weight("2,5"), reps=3, done=True)
    svc.add_set(we.id)
    st = svc.get_workout_by_date(TODAY).exercises[0].sets[0]
    assert st.weight_kg == 2.5
    ex = svc.get_workout_by_date(TODAY).exercises[0].exercise
    assert summarize_exercise(ex, [st]) == ["Ciężar: 2.5 kg    Powtórzenia: 3", "Suma przewalonego żelastwa: 7.5 kg"]


def test_fmt_decimal():
    assert (fmt_decimal(80.0), fmt_decimal(2.5), fmt_decimal(7.500000001), fmt_decimal(0.1 + 0.2)) == ("80", "2.5", "7.5", "0.3")


def test_month_grid_january_2027():
    weeks = month_grid(2027, 1)
    assert len(weeks) == 5
    assert weeks[0].days[0] == date(2026, 12, 28) and weeks[-1].days[-1] == date(2027, 1, 31)
    assert [w.iso_week for w in weeks] == [53, 1, 2, 3, 4]
    assert all(len(w.days) == 7 for w in weeks)


def test_month_grid_six_rows():
    assert len(month_grid(2026, 8)) == 6


def test_shift_month_across_years():
    assert shift_month(2026, 12, 1) == (2027, 1)
    assert shift_month(2027, 1, -1) == (2026, 12)
    assert shift_month(2027, 3, -15) == (2025, 12)
    assert len(MONTH_NAMES) == 12 and MONTH_NAMES[0] == "STYCZEŃ" and MONTH_NAMES[8] == "WRZESIEŃ"


def test_workout_dates_only_with_exercises(svc):
    ex = svc.list_exercises()[0]
    full = svc.create_workout(date(2027, 1, 5))
    svc.add_exercise_to_workout(full.id, ex.id)
    svc.create_workout(date(2027, 1, 6))
    other = svc.create_workout(date(2027, 2, 1))
    svc.add_exercise_to_workout(other.id, ex.id)
    assert svc.get_workout_dates(2027, 1) == {date(2027, 1, 5)}
    assert svc.get_workout_dates(2027, 12) == set()


@pytest.mark.parametrize("text", ["", "0", "5", "05", "99", "100", "999"])
def test_distance_input_allowed(text):
    from trainbeast.services import is_valid_distance_input

    assert is_valid_distance_input(text)


@pytest.mark.parametrize("text", ["1000", "5.5", "5,5", "-1", "5a", " 5", "٣"])
def test_distance_input_rejected(text):
    from trainbeast.services import is_valid_distance_input

    assert not is_valid_distance_input(text)


def test_digit_char_pattern_only_digits():
    import re

    from trainbeast.services import DIGIT_CHAR_PATTERN

    for ch in "0123456789":
        assert re.fullmatch(DIGIT_CHAR_PATTERN, ch)
    for bad in ["2.5", "2,5", "-3", "a", " ", "2.", ""]:
        assert not re.fullmatch(DIGIT_CHAR_PATTERN + "+", bad)


def test_calendar_today_only_in_shown_month():
    from trainbeast.services import is_calendar_today, month_grid

    today = date(2026, 10, 16)
    days = [d for w in month_grid(2026, 10) for d in w.days]
    assert [d for d in days if is_calendar_today(d, 10, today)] == [today]
    assert not any(is_calendar_today(d, 11, today) for w in month_grid(2026, 11) for d in w.days)
    # dzisiaj widoczne jako dopełnienie tygodnia sąsiedniego miesiąca nie jest zaznaczane
    edge = date(2026, 11, 1)
    assert edge in [d for w in month_grid(2026, 10) for d in w.days]
    assert not is_calendar_today(edge, 10, edge)


@pytest.mark.parametrize("text", ["", "0", "45", "007"])
def test_digits_input_allowed(text):
    from trainbeast.services import is_valid_digits_input

    assert is_valid_digits_input(text)


@pytest.mark.parametrize("text", ["45,5.5", "45.5", "4,5", "-3", "a", "4 5", " "])
def test_digits_input_rejected(text):
    from trainbeast.services import is_valid_digits_input

    assert not is_valid_digits_input(text)


@pytest.mark.parametrize("text", ["", "  ", " "])
@pytest.mark.parametrize("sep", [False, True])
def test_normalize_empty_to_zero(text, sep):
    from trainbeast.services import normalize_empty_input

    assert normalize_empty_input(text, allow_separator=sep) == "0"


@pytest.mark.parametrize("text", [".", ","])
def test_normalize_separator_only_for_weight(text):
    from trainbeast.services import normalize_empty_input

    assert normalize_empty_input(text, allow_separator=True) == "0"
    assert normalize_empty_input(text) == text


@pytest.mark.parametrize("text", ["5", "2.5", "0", "05"])
def test_normalize_keeps_nonempty(text):
    from trainbeast.services import normalize_empty_input

    assert normalize_empty_input(text, allow_separator=True) == text


def test_empty_allowed_by_all_input_validators():
    from trainbeast.services import is_valid_digits_input, is_valid_distance_input, is_valid_minsec_input, is_valid_weight_input

    for check in (is_valid_digits_input, is_valid_distance_input, is_valid_minsec_input, is_valid_weight_input):
        assert check("")


def test_clear_user_data(svc):
    custom_cat = svc.add_category("Moja sekcja")
    svc.add_category("Pusta sekcja")
    custom = svc.create_exercise("Własne ćwiczenie", custom_cat.name)
    starter = svc.list_exercises()[0]
    w = svc.create_workout(TODAY, "x")
    we = svc.add_exercise_to_workout(w.id, custom.id)
    svc.add_exercise_to_workout(w.id, starter.id)
    svc.add_set(we.id)
    assert count(svc, WorkoutSet) >= 1
    categories_before = count(svc, Category)

    result = svc.clear_user_data()

    assert count(svc, Workout) == count(svc, WorkoutExercise) == count(svc, WorkoutSet) == 0
    assert count(svc, Exercise) == STARTER_COUNT
    assert count(svc, Category) == categories_before
    assert result["workout"] == 1 and result["exercise"] == 1
    assert svc.clear_user_data() == {"workout_set": 0, "workout_exercise": 0, "workout": 0, "exercise": 0}
    assert count(svc, Exercise) == STARTER_COUNT
    assert starter.name in [e.name for e in svc.list_exercises()]


def test_default_db_path_uses_storage_dir(tmp_path):
    from trainbeast.database import DB_FILENAME, default_db_path

    target = tmp_path / "data" / "app"
    assert default_db_path({"FLET_APP_STORAGE_DATA": str(target)}) == target / DB_FILENAME
    assert target.is_dir()


@pytest.mark.parametrize("env", [{}, {"FLET_APP_STORAGE_DATA": ""}])
def test_default_db_path_without_storage_unchanged(env):
    from pathlib import Path

    import trainbeast.database as database

    expected = Path(database.__file__).resolve().parent.parent / database.DB_FILENAME
    assert database.default_db_path(env) == expected


def test_fresh_database_startup_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))
    for _ in range(2):
        svc = TrainingService(make_session_factory(make_engine()))
        assert count(svc, Category) == len(STARTER_CATEGORIES)
        assert count(svc, Exercise) == STARTER_COUNT
    assert (tmp_path / "trainbeast.db").exists()


@pytest.mark.parametrize("dx, expected", [(-80, 1), (-50, 1), (80, -1), (50, -1), (-49, 0), (49, 0), (0, 0), (3, 0)])
def test_interpret_swipe(dx, expected):
    from trainbeast.services import interpret_swipe

    assert interpret_swipe(dx) == expected


def test_set_fields_stay_empty_while_editing_and_become_zero_on_blur(svc, monkeypatch):
    """Obsługa zmiany z pustym tekstem nie dotyka wartości kontrolki; blur / zaznaczenie serii wstawia 0."""
    import flet as ft

    from trainbeast.ui import TrainBeastApp

    monkeypatch.setattr(ft.BaseControl, "update", lambda self: None)  # bez strony
    app = TrainBeastApp.__new__(TrainBeastApp)
    app.service, app.set_fields, app.set_groups, app.expanded = svc, {}, {}, set()
    app.info_text = ft.Text("")
    app._refresh_info = lambda: None
    w = svc.create_workout(TODAY)
    seen = set()
    for ex in svc.list_exercises():
        key = (ex.load_type, ex.effort_type)
        if key in seen:
            continue
        seen.add(key)
        svc.add_exercise_to_workout(w.id, ex.id)
        we = svc.get_workout(w.id).exercises[-1]
        st = we.sets[0]
        app._set_row(we.id, we.exercise, 1, st)
        for f in app.set_fields[st.id]:
            f.value = ""
            f.on_change(ft.ControlEvent(control=f, name="change", data=""))
            assert f.value == "" and f.border_color is None
            f.on_blur(None)
            assert f.value == "0"
        for f in app.set_fields[st.id]:  # zaznaczenie serii bez blur: baza dostaje 0, pole pokazuje 0
            f.value = ""
        app._toggle_done(st.id, True)
        assert all(f.value == "0" for f in app.set_fields[st.id])
    assert seen >= {("weight", "reps"), ("distance", "time"), ("floors", "time")}


# --- skróty dni tygodnia ---
from trainbeast.services import WEEKDAY_ABBR, weekday_abbr  # noqa: E402


def test_weekday_abbr_list():
    assert WEEKDAY_ABBR == ("PN", "WT", "ŚR", "CZ", "PT", "SB", "ND")


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 10, 17), "SB"),
        (date(2026, 10, 18), "ND"),
        (date(2026, 10, 19), "PN"),
        (date(2026, 10, 20), "WT"),
        (date(2026, 10, 21), "ŚR"),
        (date(2026, 10, 22), "CZ"),
        (date(2027, 1, 1), "PT"),
    ],
)
def test_weekday_abbr(day, expected):
    assert weekday_abbr(day) == expected


# --- kopiuj / wklej trening ---
def _two_exercise_workout(svc, day, name="Push"):
    ex_w = svc.get_exercises_by_category(CAT)[0]  # ciężar x powtórzenia
    cardio = svc.get_exercises_by_category(STARTER_CATEGORIES[8])
    ex_d = next(e for e in cardio if e.load_type == "distance")
    w = svc.create_workout(day, name)
    we1 = svc.add_exercise_to_workout(w.id, ex_w.id)
    svc.update_set(we1.sets[0].id, weight_kg=80, reps=5, done=True)
    s2 = svc.add_set(we1.id)
    svc.update_set(s2.id, weight_kg=82.5, reps=3)
    we2 = svc.add_exercise_to_workout(w.id, ex_d.id)
    svc.update_set(we2.sets[0].id, distance_m=1500, duration_s=600, done=True)
    return w


def _flat(workout):
    return (
        workout.name,
        [
            (we.exercise_id, [(s.weight_kg, s.distance_m, s.reps, s.duration_s) for s in we.sets])
            for we in workout.exercises
        ],
    )


def test_snapshot_has_name_exercises_sets_in_order(svc):
    w = _two_exercise_workout(svc, TODAY)
    snap = svc.snapshot_workout(w.id)
    assert snap.name == "Push"
    assert [e.exercise_id for e in snap.exercises] == [we.exercise_id for we in svc.get_workout(w.id).exercises]
    assert [(s.weight_kg, s.reps) for s in snap.exercises[0].sets] == [(80.0, 5), (82.5, 3)]
    assert (snap.exercises[1].sets[0].distance_m, snap.exercises[1].sets[0].duration_s) == (1500, 600)


def test_snapshot_none_for_empty_or_missing_workout(svc):
    w = svc.create_workout(TODAY)
    assert svc.snapshot_workout(w.id) is None
    assert svc.snapshot_workout(9999) is None


def test_paste_creates_equal_workout_with_undone_sets(svc):
    src = _two_exercise_workout(svc, TODAY)
    snap = svc.snapshot_workout(src.id)
    day = TODAY + timedelta(days=1)
    pasted = svc.paste_snapshot(snap, day)
    assert pasted.workout_date == day and pasted.id != src.id
    assert _flat(pasted) == _flat(svc.get_workout(src.id))
    assert not any(s.done for we in pasted.exercises for s in we.sets)
    assert [we.position for we in pasted.exercises] == [0, 1]


def test_paste_does_not_change_source(svc):
    src = _two_exercise_workout(svc, TODAY)
    before = (_flat(svc.get_workout(src.id)), done_sets_count(svc.get_workout(src.id)))
    svc.paste_snapshot(svc.snapshot_workout(src.id), TODAY + timedelta(days=1))
    after = svc.get_workout(src.id)
    assert (_flat(after), done_sets_count(after)) == before


def test_snapshot_is_independent_of_later_source_changes(svc):
    src = _two_exercise_workout(svc, TODAY)
    snap = svc.snapshot_workout(src.id)
    expected = _flat(svc.get_workout(src.id))
    we = svc.get_workout(src.id).exercises[0]
    svc.update_set(we.sets[0].id, weight_kg=999, reps=99)
    svc.remove_set(we.sets[1].id)
    svc.rename_workout(src.id, "Zmienione")
    svc.remove_exercise_from_workout(svc.get_workout(src.id).exercises[1].id)
    pasted = svc.paste_snapshot(snap, TODAY + timedelta(days=1))
    assert _flat(pasted) == expected


def test_paste_on_day_with_workout_changes_nothing(svc):
    src = _two_exercise_workout(svc, TODAY)
    snap = svc.snapshot_workout(src.id)
    day = TODAY + timedelta(days=1)
    existing = svc.create_workout(day, "Inny")
    counts = [count(svc, m) for m in (Workout, WorkoutExercise, WorkoutSet)]
    assert svc.paste_snapshot(snap, day) is None
    assert [count(svc, m) for m in (Workout, WorkoutExercise, WorkoutSet)] == counts
    assert svc.get_workout_by_date(day).name == "Inny" and svc.get_workout_by_date(day).id == existing.id


def test_same_snapshot_can_be_pasted_on_many_days(svc):
    src = _two_exercise_workout(svc, TODAY)
    snap = svc.snapshot_workout(src.id)
    a = svc.paste_snapshot(snap, TODAY + timedelta(days=1))
    b = svc.paste_snapshot(snap, TODAY + timedelta(days=2))
    assert a.id != b.id and _flat(a) == _flat(b) == _flat(svc.get_workout(src.id))

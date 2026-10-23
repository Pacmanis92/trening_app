from datetime import date

import pytest
from sqlalchemy import text

from trainbeast.database import make_engine, make_session_factory, normalize_exercise_positions
from trainbeast.models import Category, Exercise, Workout, WorkoutExercise, WorkoutSet
from trainbeast.services import (
    BACK_EXIT,
    BACK_LAYER,
    BACK_TAB,
    STARTER_CATEGORIES,
    NavState,
    TrainingService,
    ValidationError,
    allowed_second_measures,
    fmt_last_workout,
    summarize_exercise,
    validate_measures,
)

CAT = STARTER_CATEGORIES[0]


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'f.db'}"


@pytest.fixture
def svc(db_url):
    return TrainingService(make_session_factory(make_engine(db_url)))


def count(svc, model):
    with svc._sf() as s:
        return len(s.query(model).all())


def ex_id(svc, en):
    return next(e.id for e in svc.list_exercises() if e.name.startswith(en))


def workout_with(svc, day, names):
    w = svc.create_workout(day)
    return w, [svc.add_exercise_to_workout(w.id, ex_id(svc, n)) for n in names]


# --- 1. miary ---
def test_second_measures_per_first():
    assert allowed_second_measures("reps") == ("time",)
    for first in ("weight", "distance", "floors"):
        assert set(allowed_second_measures(first)) == {"reps", "time"}


def test_reps_times_reps_is_rejected(svc):
    with pytest.raises(ValidationError):
        validate_measures("reps", "reps")
    with pytest.raises(ValidationError):
        svc.create_exercise("Dziwne", CAT, "reps", "reps")
    validate_measures("reps", "time")
    assert svc.create_exercise("Pompki x", CAT, "reps", "time").effort_type == "time"


# --- 2. notatki ---
def test_note_save_read_overwrite_clear(svc):
    _, (we,) = workout_with(svc, date(2026, 1, 5), ["Barbell Bench Press"])
    assert svc.get_exercise_note(we.id) == ""
    svc.set_exercise_note(we.id, "Lekko na barku")
    assert svc.get_exercise_note(we.id) == "Lekko na barku"
    svc.set_exercise_note(we.id, "Inaczej\nwiersz 2")
    assert svc.get_exercise_note(we.id) == "Inaczej\nwiersz 2"
    svc.set_exercise_note(we.id, "   \n ")
    assert svc.get_exercise_note(we.id) == ""
    with svc._sf() as s:
        assert s.get(WorkoutExercise, we.id).note is None
    svc.set_exercise_note(we.id, "")
    assert svc.get_exercise_note(we.id) == ""


def test_note_is_not_copied_on_paste(svc):
    w, (we,) = workout_with(svc, date(2026, 1, 5), ["Barbell Bench Press"])
    svc.set_exercise_note(we.id, "tylko ta sesja")
    pasted = svc.paste_snapshot(svc.snapshot_workout(w.id), date(2026, 1, 6))
    assert svc.get_exercise_note(pasted.exercises[0].id) == ""
    assert svc.get_exercise_note(we.id) == "tylko ta sesja"


# --- 3. podsumowanie ---
class _Ex:
    def __init__(self, load, effort):
        self.load_type, self.effort_type = load, effort


class _St:
    def __init__(self, weight=None, reps=None, distance=None, unit=None, unit_minor=None, duration=None, done=True):
        self.weight_kg, self.reps, self.distance_m, self.duration_s = weight, reps, distance, duration
        self.unit, self.unit_minor, self.done = unit, unit_minor, done


def lines(ex, sets):
    return [(g.heading, g.lines) for g in summarize_exercise(ex, sets)]


def test_summary_has_total_reps_one_unit():
    sets = [_St(20, 10), _St(30, 8), _St(99, 9, done=False)]
    assert lines(_Ex("weight", "reps"), sets) == [("", ["Suma przewalonego żelastwa: 440 kg", "Łączne powtórzenia: 18"])]


def test_summary_total_reps_per_unit_group():
    sets = [_St(20, 10, unit="kg"), _St(10, 3, unit="lbs"), _St(10, 4, unit="lbs")]
    assert lines(_Ex("weight", "reps"), sets) == [
        ("kg", ["Suma przewalonego żelastwa: 200 kg", "Łączne powtórzenia: 10"]),
        ("lbs", ["Suma przewalonego żelastwa: 70 lbs", "Łączne powtórzenia: 7"]),
    ]


def test_summary_distance_and_floors_reps_have_total_reps():
    assert lines(_Ex("distance", "reps"), [_St(distance=500, reps=4)]) == [
        ("", ["Łączny dystans: 2 km", "Łączne powtórzenia: 4"])
    ]
    assert lines(_Ex("floors", "reps"), [_St(reps=12)]) == [("", ["Łączne piętra: 12", "Łączne powtórzenia: 12"])]


def test_summary_without_sets():
    assert summarize_exercise(_Ex("weight", "reps"), []) == []


# --- 4. napis ostatniego treningu ---
@pytest.mark.parametrize(
    "day, name",
    [
        (date(2026, 10, 19), "poniedziałek"),
        (date(2026, 10, 20), "wtorek"),
        (date(2026, 10, 21), "środa"),
        (date(2026, 10, 22), "czwartek"),
        (date(2026, 10, 23), "piątek"),
        (date(2026, 10, 24), "sobota"),
        (date(2026, 10, 25), "niedziela"),
    ],
)
def test_last_workout_weekday_names(day, name):
    assert fmt_last_workout(day, 1, 1).startswith(f"Ostatni trening: {name}, ")


def test_last_workout_format():
    assert fmt_last_workout(date(2026, 10, 23), 6, 20) == "Ostatni trening: piątek, 23.10.2026, 6 ćwicz., 20 serii"
    assert fmt_last_workout(date(2026, 2, 3), 1, 0) == "Ostatni trening: wtorek, 03.02.2026, 1 ćwicz., 0 serii"


# --- 5. usuwanie ---
def _add_set_done(svc, we):
    svc.update_set(we.sets[0].id, weight_kg=10, reps=5, done=True)


def test_delete_exercise_removes_history_only_for_it(svc):
    w1, (a1, b1) = workout_with(svc, date(2026, 1, 5), ["Barbell Bench Press", "Pull-ups"])
    w2, (a2,) = workout_with(svc, date(2026, 1, 6), ["Barbell Bench Press"])
    svc.set_exercise_note(a1.id, "n")
    _add_set_done(svc, a1), _add_set_done(svc, b1)
    bench = ex_id(svc, "Barbell Bench Press")
    svc.delete_exercise(bench)
    assert bench not in [e.id for e in svc.list_exercises()]
    with svc._sf() as s:
        assert s.query(WorkoutExercise).filter_by(exercise_id=bench).count() == 0
        remaining = s.query(WorkoutExercise).all()
        assert [we.exercise.name.startswith("Pull-ups") for we in remaining] == [True]
        assert s.query(WorkoutSet).count() == 1  # tylko seria Pull-ups
    assert svc.get_workout_by_date(date(2026, 1, 5)) is not None  # ma jeszcze inne ćwiczenie
    assert svc.get_workout_by_date(date(2026, 1, 6)) is None  # została pusta -> usunięty


def test_delete_exercise_keeps_unrelated_empty_workouts(svc):
    svc.create_workout(date(2026, 1, 9))  # pusty trening, którego to nie dotyczy
    workout_with(svc, date(2026, 1, 5), ["Barbell Bench Press"])
    svc.delete_exercise(ex_id(svc, "Barbell Bench Press"))
    assert svc.get_workout_by_date(date(2026, 1, 9)) is not None
    assert svc.get_workout_dates(2026, 1) == set()


def test_delete_missing_exercise_is_noop(svc):
    before = len(svc.list_exercises())
    svc.delete_exercise(999999)
    svc.delete_category("Nie ma takiej")
    assert len(svc.list_exercises()) == before


def test_delete_category_removes_exercises_and_history(svc):
    svc.add_category("Moja")
    own = svc.create_exercise("Ruch", "Moja")
    w = svc.create_workout(date(2026, 1, 5))
    we = svc.add_exercise_to_workout(w.id, own.id)
    other = svc.add_exercise_to_workout(w.id, ex_id(svc, "Pull-ups"))
    svc.delete_category("Moja")
    assert "Moja" not in [c.name for c in svc.get_categories()]
    assert own.id not in [e.id for e in svc.list_exercises()]
    assert [x.id for x in svc.get_workout(w.id).exercises] == [other.id]
    # sekcja startowa z ćwiczeniami
    n = len(svc.get_exercises_by_category(CAT))
    assert n > 0
    svc.delete_category(CAT)
    assert svc.get_exercises_by_category(CAT) == []
    assert CAT not in [c.name for c in svc.get_categories()]


def test_deleted_starter_catalog_is_not_reseeded(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    svc.delete_category(CAT)
    svc.delete_exercise(ex_id(svc, "Pull-ups"))
    again = TrainingService(make_session_factory(make_engine(db_url)))
    assert CAT not in [c.name for c in again.get_categories()]
    assert not [e for e in again.list_exercises() if e.name.startswith("Pull-ups")]


# --- 6. kolejność ---
NAMES = ["Barbell Bench Press", "Pull-ups", "Plank", "Running"]


def order(svc, w):
    return [we.exercise.name.split(" (")[0] for we in svc.get_workout(w.id).exercises]


@pytest.mark.parametrize(
    "old, new, expected",
    [
        (3, 1, ["Barbell Bench Press", "Running", "Pull-ups", "Plank"]),
        (0, 2, ["Pull-ups", "Plank", "Barbell Bench Press", "Running"]),
        (2, 0, ["Plank", "Barbell Bench Press", "Pull-ups", "Running"]),
        (0, 3, ["Pull-ups", "Plank", "Running", "Barbell Bench Press"]),
        (1, 1, NAMES),
    ],
)
def test_reorder(svc, old, new, expected):
    w, _ = workout_with(svc, date(2026, 1, 5), NAMES)
    ids = svc.reorder_workout_exercises(w.id, old, new)
    assert order(svc, w) == expected
    assert ids == svc.get_workout_exercise_ids(w.id)
    with svc._sf() as s:
        assert sorted(x.position for x in s.query(WorkoutExercise).filter_by(workout_id=w.id)) == [0, 1, 2, 3]


def test_reorder_persists_and_invalid_index(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    w, _ = workout_with(svc, date(2026, 1, 5), NAMES)
    svc.reorder_workout_exercises(w.id, 0, 3)
    with pytest.raises(ValidationError):
        svc.reorder_workout_exercises(w.id, 0, 9)
    reopened = TrainingService(make_session_factory(make_engine(db_url)))
    assert order(reopened, w)[-1] == "Barbell Bench Press"


def test_new_exercise_goes_last_even_after_removal(svc):
    w, wes = workout_with(svc, date(2026, 1, 5), NAMES[:3])
    svc.remove_exercise_from_workout(wes[0].id)
    svc.add_exercise_to_workout(w.id, ex_id(svc, "Running"))
    assert order(svc, w) == ["Pull-ups", "Plank", "Running"]


def test_paste_keeps_order(svc):
    w, _ = workout_with(svc, date(2026, 1, 5), NAMES)
    svc.reorder_workout_exercises(w.id, 3, 0)
    pasted = svc.paste_snapshot(svc.snapshot_workout(w.id), date(2026, 1, 6))
    assert order(svc, pasted) == order(svc, w)


def test_migration_adds_note_column_keeps_data_and_is_idempotent(tmp_path):
    db = tmp_path / "old.db"
    url = f"sqlite:///{db}"
    svc = TrainingService(make_session_factory(make_engine(url)))
    w, wes = workout_with(svc, date(2026, 1, 5), NAMES[:3])
    eng = make_engine(url)
    with eng.begin() as conn:  # stary schemat: bez note, z lukami i duplikatami pozycji
        conn.execute(text("ALTER TABLE workout_exercise DROP COLUMN note"))
        conn.execute(text("UPDATE workout_exercise SET position = 5 WHERE id = :i"), {"i": wes[0].id})
        conn.execute(text("UPDATE workout_exercise SET position = 5 WHERE id = :i"), {"i": wes[1].id})
        conn.execute(text("UPDATE workout_exercise SET position = 1 WHERE id = :i"), {"i": wes[2].id})
    eng.dispose()
    before = {p.name for p in tmp_path.iterdir()}
    svc2 = TrainingService(make_session_factory(make_engine(url)))
    assert len({p.name for p in tmp_path.iterdir()} - before) == 1  # kopia .bak
    assert svc2.get_exercise_note(wes[0].id) == ""
    # kolejność wg (position, id): wes[2] (1), potem wes[0], wes[1] (po 5, po id)
    assert svc2.get_workout_exercise_ids(w.id) == [wes[2].id, wes[0].id, wes[1].id]
    with svc2._sf() as s:
        assert sorted(x.position for x in s.query(WorkoutExercise)) == [0, 1, 2]
    files = {p.name for p in tmp_path.iterdir()}
    engine = make_engine(url)
    assert normalize_exercise_positions(engine) == 0
    assert {p.name for p in tmp_path.iterdir()} == files  # drugi start: bez nowej kopii i zmian
    assert count(svc2, Workout) == 1


# --- 9, 10. nawigacja i stos warstw ---
def test_calendar_from_workout_returns_to_workout():
    nav = NavState()
    layer = nav.open_calendar()
    assert nav.tab == "workout"
    nav.close_layer(layer)
    assert nav.tab == "workout" and not nav.layers


def test_calendar_from_stats_returns_to_stats_without_switching():
    nav = NavState()
    nav.switch_tab("stats")
    layer = nav.open_calendar()
    assert nav.tab == "stats"  # bez przełączania na Workout
    nav.close_layer(layer)
    assert nav.tab == "stats"


def test_select_day_from_stats_goes_to_workout():
    nav = NavState()
    nav.switch_tab("stats")
    layer = nav.open_calendar()
    nav.select_day_from_calendar(layer)
    assert nav.tab == "workout" and not nav.layers
    nav.back()
    assert nav.tab == "workout"


def test_back_from_calendar_opened_on_stats_returns_to_stats():
    nav = NavState()
    nav.switch_tab("stats")
    closed = []
    nav.open_calendar(lambda: closed.append("calendar"))
    assert nav.back() == BACK_LAYER and closed == ["calendar"] and nav.tab == "stats"


def test_back_pops_most_recent_layer_first():
    nav = NavState()
    closed = []
    nav.open_layer("lista", lambda: closed.append("lista"))
    nav.open_layer("potwierdzenie", lambda: closed.append("potwierdzenie"))
    assert nav.back() == BACK_LAYER and closed == ["potwierdzenie"]
    assert nav.back() == BACK_LAYER and closed == ["potwierdzenie", "lista"]
    assert nav.back() == BACK_EXIT


def test_layer_closed_another_way_is_unregistered():
    nav = NavState()
    closed = []
    layer = nav.open_layer("okno", lambda: closed.append("okno"))
    assert nav.close_layer(layer) is True
    assert nav.close_layer(layer) is False  # idempotentne
    assert nav.layers == []
    assert nav.back() == BACK_EXIT and closed == []  # brak "martwego" wpisu


def test_empty_stack_on_workout_exits_and_on_stats_goes_to_workout():
    nav = NavState()
    assert nav.back() == BACK_EXIT
    nav.switch_tab("stats")
    assert nav.back() == BACK_TAB and nav.tab == "workout"
    assert nav.back() == BACK_EXIT

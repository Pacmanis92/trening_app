from datetime import date, timedelta

import pytest

from trainbeast.database import make_engine, make_session_factory
from trainbeast.models import Exercise, Workout, WorkoutExercise, WorkoutSet
from trainbeast.services import (
    STARTER_EXERCISES,
    TrainingService,
    ValidationError,
    done_sets_count,
    fmt_value,
    parse_distance,
    parse_duration,
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


def count(svc, model):
    with svc._sf() as s:
        return len(s.query(model).all())


def test_starter_exercises_seeded_once(db_url):
    for _ in range(2):
        service = TrainingService(make_session_factory(make_engine(db_url)))
    exercises = service.list_exercises()
    assert [e.name for e in exercises] == [n for n, _, _ in STARTER_EXERCISES]
    hold = next(e for e in exercises if e.name == "Pull-up hold")
    assert (hold.load_type, hold.effort_type) == ("weight", "time")
    assert all((e.load_type, e.effort_type) == ("weight", "reps") for e in exercises if e is not hold)


def test_seed_adds_only_missing(db_url):
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    with svc._sf.begin() as s:
        s.delete(s.query(Exercise).filter_by(name="Pull-up hold").one())
    svc = TrainingService(make_session_factory(make_engine(db_url)))
    names = [e.name for e in svc.list_exercises()]
    assert names.count("Pull-up hold") == 1 and len(names) == len(STARTER_EXERCISES)


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
    custom = svc.add_exercise_to_workout(w.id, svc.create_exercise("Dipy").id)
    assert custom.exercise.name == "Dipy"
    assert len(svc.get_workout(w.id).exercises) == 2


@pytest.mark.parametrize("load", ["weight", "distance"])
@pytest.mark.parametrize("effort", ["reps", "time"])
def test_create_exercise_all_type_combinations(svc, load, effort):
    ex = svc.create_exercise("  Własne  ", load, effort)
    assert (ex.name, ex.load_type, ex.effort_type) == ("Własne", load, effort)
    saved = next(e for e in svc.list_exercises() if e.name == "Własne")
    assert (saved.load_type, saved.effort_type) == (load, effort)
    we = svc.add_exercise_to_workout(svc.create_workout(TODAY).id, ex.id)
    st = we.sets[0]
    assert (st.weight_kg is not None, st.distance_m is not None) == (load == "weight", load == "distance")
    assert (st.reps is not None, st.duration_s is not None) == (effort == "reps", effort == "time")


@pytest.mark.parametrize("name", ["", "   ", "pull-UP hold", "Dipy"])
def test_create_exercise_rejects_empty_and_duplicate(svc, name):
    svc.create_exercise("Dipy")
    before = len(svc.list_exercises())
    with pytest.raises(ValidationError):
        svc.create_exercise(name)
    assert len(svc.list_exercises()) == before


def test_distance_and_time_set_roundtrip(svc):
    ex = svc.create_exercise("Bieg", "distance", "time")
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
    ex = svc.create_exercise("Bieg", "distance", "time")
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
    assert count(svc, Exercise) == len(STARTER_EXERCISES)  # definicja zostaje


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

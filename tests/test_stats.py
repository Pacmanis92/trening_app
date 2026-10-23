from datetime import date, timedelta

import pytest

from trainbeast.services import (
    DailyStats,
    Record,
    SetRow,
    aggregate_daily,
    axis_label_indices,
    distance_to_km,
    fmt_record,
    hms_to_minutes,
    lbs_to_kg,
    monthly_workout_counts,
    stat_titles,
    stats_records,
)

D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)


def row(day=D1, weight=None, dist=None, reps=None, dur=None, unit=None, minor=None, done=True):
    return SetRow(day, weight, dist, reps, dur, unit, minor, done)


def test_conversions():
    assert lbs_to_kg(100) == pytest.approx(45.359237)
    assert distance_to_km(2, 0, "mile") == pytest.approx(3.218688)
    assert distance_to_km(0, 1000, None, "ys") == pytest.approx(0.9144)
    assert distance_to_km(3, 500) == pytest.approx(3.5)
    assert distance_to_km(1, 500, "mile", "ys") == pytest.approx(1.609344 + 0.4572)
    assert hms_to_minutes(1, 30, 30) == pytest.approx(90.5)


def test_only_done_sets_counted():
    rows = [row(weight=50, reps=10), row(weight=100, reps=10, done=False)]
    assert aggregate_daily("weight", "reps", rows)[D1] == DailyStats(500, 50, 10)


def test_weight_reps():
    rows = [row(weight=50, reps=10), row(weight=60, reps=5), row(D2, weight=20, reps=None)]
    daily = aggregate_daily("weight", "reps", rows)
    assert daily[D1] == DailyStats(50 * 10 + 60 * 5, 60, 15)
    assert daily[D2] == DailyStats(0, 20, 0)  # puste = 0


def test_distance_time():
    rows = [row(dist=2500, dur=900), row(dist=1000, dur=330)]
    daily = aggregate_daily("distance", "time", rows)
    assert daily[D1].w1 == pytest.approx(3.5)
    assert daily[D1].w2 == pytest.approx(2.5)
    assert daily[D1].w3 == pytest.approx(20.5)


def test_mixed_units_same_day():
    rows = [row(weight=100, reps=1), row(weight=100, reps=1, unit="lbs")]
    daily = aggregate_daily("weight", "reps", rows)
    assert daily[D1].w1 == pytest.approx(100 + 45.359237)
    assert daily[D1].w2 == pytest.approx(100)


def test_floors_reps_not_squared():
    daily = aggregate_daily("floors", "reps", [row(reps=10), row(reps=5)])
    assert daily[D1] == DailyStats(15, 10, 15)


def test_reps_time():
    daily = aggregate_daily("reps", "time", [row(reps=10, dur=60), row(reps=20, dur=120)])
    assert daily[D1] == DailyStats(30, 20, 3)


def test_records_whole_history_tie_and_empty():
    daily = {
        date(2020, 1, 1): DailyStats(100, 10, 5),
        date(2020, 1, 5): DailyStats(100, 20, 5),
        date(2026, 1, 1): DailyStats(50, 20, 0),
    }
    r1, r2, r3 = stats_records(daily)
    assert r1 == Record(100, date(2020, 1, 1))  # remis: najwcześniejsza data
    assert r2 == Record(20, date(2020, 1, 5))
    assert r3 == Record(5, date(2020, 1, 1))
    assert stats_records({D1: DailyStats(0, 0, 0)}) == (None, None, None)
    assert stats_records({}) == (None, None, None)


def test_fmt_record():
    assert fmt_record(Record(1250.0, date(2026, 10, 12)), "kg") == "Rekord: 1250 kg (12.10.2026)"
    assert fmt_record(Record(2.345, date(2026, 1, 2)), "km") == "Rekord: 2.35 km (02.01.2026)"
    assert fmt_record(None, "kg") == "Brak danych"


def test_titles():
    t = stat_titles("weight", "time")
    assert (t.w1, t.w2, t.w3) == ("Łączny ciężar (kg)", "Największy ciężar (kg)", "Czas (min)")


def test_axis_label_indices():
    assert axis_label_indices(7, 1) == list(range(7))
    idx = axis_label_indices(30, 5)
    assert idx[-1] == 29 and len(idx) == 6


def test_monthly_counts_year_boundary_and_current_month():
    today = date(2026, 2, 10)
    dates = {date(2026, 2, 1), date(2026, 2, 10), date(2025, 12, 31), date(2025, 1, 5), date(2024, 3, 1)}
    result = monthly_workout_counts(dates, today)
    assert len(result) == 24
    assert result[0][0] == (2024, 3) and result[-1][0] == (2026, 2)
    counts = dict(result)
    assert counts[(2026, 2)] == 2
    assert counts[(2025, 12)] == 1
    assert counts[(2026, 1)] == 0
    assert counts[(2025, 1)] == 1
    assert counts[(2024, 3)] == 1
    assert (2024, 2) not in counts


def test_service_monthly_counts_matches_calendar(tmp_path):
    from trainbeast.database import make_engine, make_session_factory
    from trainbeast.services import TrainingService

    svc = TrainingService(make_session_factory(make_engine(f"sqlite:///{tmp_path / 't.db'}")))
    today = date(2026, 10, 22)
    ex = svc.list_exercises()[0]
    w = svc.create_workout(today)
    svc.add_exercise_to_workout(w.id, ex.id)
    svc.create_workout(date(2026, 9, 3))  # pusty trening nie liczy się (jak w kalendarzu)
    counts = svc.get_monthly_workout_counts(today)
    assert counts[-1] == ((2026, 10), 1)
    assert dict(counts)[(2026, 9)] == 0


def test_service_daily_stats_one_exercise(tmp_path):
    from trainbeast.database import make_engine, make_session_factory
    from trainbeast.services import TrainingService

    svc = TrainingService(make_session_factory(make_engine(f"sqlite:///{tmp_path / 't.db'}")))
    ex = next(e for e in svc.list_exercises() if e.load_type == "weight" and e.effort_type == "reps")
    w = svc.create_workout(D1)
    we = svc.add_exercise_to_workout(w.id, ex.id)
    st = svc.get_workout(w.id).exercises[0].sets[0]
    svc.update_set(st.id, weight_kg=40.0, reps=5, done=True)
    assert svc.get_exercise_daily_stats(ex)[D1] == DailyStats(200, 40, 5)
    svc.update_set(st.id, done=False)
    assert svc.get_exercise_daily_stats(ex) == {}


def test_y_axis_ticks():
    from trainbeast.services import y_axis_ticks

    assert y_axis_ticks(0) == (1, [0, 1])
    top, ticks = y_axis_ticks(1250)
    assert ticks[0] == 0 and top >= 1250 and top == ticks[-1] and len(ticks) <= 7
    top, ticks = y_axis_ticks(3, integer=True)
    assert all(float(t).is_integer() for t in ticks) and top >= 3
    assert y_axis_ticks(0.8)[1][0] == 0

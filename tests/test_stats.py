from datetime import date, timedelta

import pytest

from trainbeast.services import (
    DailyStats,
    exercise_stat_cards,
    history_max,
    period_second_stats,
    SetRow,
    aggregate_daily,
    axis_label_indices,
    distance_to_km,
    hms_to_minutes,
    lbs_to_kg,
    monthly_workout_counts,
    stat_titles,
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
    assert aggregate_daily("weight", "reps", rows)[D1] == DailyStats(500, 50, 10, 10)


def test_weight_reps():
    rows = [row(weight=50, reps=10), row(weight=60, reps=5), row(D2, weight=20, reps=None)]
    daily = aggregate_daily("weight", "reps", rows)
    assert daily[D1] == DailyStats(50 * 10 + 60 * 5, 60, 15, 10)
    assert daily[D2] == DailyStats(0, 20, 0, 0)  # puste = 0


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
    assert daily[D1] == DailyStats(15, 10, 15, 10)


def test_reps_time():
    daily = aggregate_daily("reps", "time", [row(reps=10, dur=60), row(reps=20, dur=120)])
    assert daily[D1] == DailyStats(30, 20, 3, 2)


def test_titles():
    t = stat_titles("weight", "time")
    assert (t.w1, t.w2, t.w3) == ("Łączny ciężar (kg)", "Największy ciężar dnia (kg)", "Łączny czas ćwiczeń (min)")
    assert stat_titles("distance", "reps").w2 == "Najdłuższy pojedynczy dystans dnia (km)"
    assert stat_titles("reps", "reps").w2 == "Najwięcej powtórzeń w serii"  # bez zmian
    assert stat_titles("weight", "reps").w3 == "Powtórzenia"


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
    assert svc.get_exercise_daily_stats(ex)[D1] == DailyStats(200, 40, 5, 5)
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


# --- kwestia 6: statystyki pól pod wykresami ---
def test_second_measure_max_in_set_reps_and_time():
    reps = aggregate_daily("weight", "reps", [row(weight=50, reps=8), row(weight=50, reps=12)])
    assert reps[D1].w3 == 20 and reps[D1].w3_max == 12
    time = aggregate_daily("distance", "time", [row(dist=1000, dur=600), row(dist=1000, dur=1800)])
    assert time[D1].w3 == pytest.approx(40) and time[D1].w3_max == pytest.approx(30)  # minuty


def test_history_max_converts_kg_and_lbs():
    rows = [row(D1, weight=100, reps=1), row(D2, weight=200, reps=1, unit="lbs"), row(date(2026, 9, 1), weight=95, reps=1)]
    assert history_max(aggregate_daily("weight", "reps", rows)) == pytest.approx(100)  # 200 lbs = 90,7 kg
    rows.append(row(date(2026, 8, 1), weight=250, reps=1, unit="lbs"))
    assert history_max(aggregate_daily("weight", "reps", rows)) == pytest.approx(113.398093)
    assert history_max({}) == 0.0


def test_period_second_stats_empty_period():
    assert period_second_stats([]) == (0.0, 0.0)


TODAY = date(2026, 10, 23)
START = date(2026, 10, 1)


def _cards(daily, interval="month", start=START, load="weight", effort="reps"):
    return exercise_stat_cards(load, effort, daily, start, interval, TODAY)


def test_cards_max_from_start_vs_period_max_different_and_equal():
    daily = aggregate_daily("weight", "reps", [
        row(date(2026, 8, 5), weight=120, reps=3),
        row(date(2026, 9, 5), weight=60, reps=5),
        row(date(2026, 10, 5), weight=80, reps=5),
    ])
    peak = _cards(daily)[1]
    assert peak.left.label == "Największy ciężar" and peak.left.value == 80
    assert peak.left.pct == 33 and peak.left.compare == "vs. poprzedni miesiąc"  # 80 vs 60
    assert peak.right.label == "Max od początku" and peak.right.value == 120
    assert peak.right.pct == 50 and peak.right.compare == "vs. wybrany miesiąc"  # (120-80)/80
    equal = _cards(daily, start=date(2026, 8, 1))[1]
    assert equal.right.value == 120 and equal.right.pct == 0
    assert _cards(daily, "week", date(2026, 10, 5))[1].right.compare == "vs. wybrany tydzień"


def test_cards_period_without_data():
    daily = aggregate_daily("weight", "reps", [row(date(2026, 8, 5), weight=120, reps=3)])
    cards = _cards(daily, start=date(2026, 10, 1))
    assert cards[0].left.value == 0 and cards[0].left.pct is None
    assert cards[1].left.value == 0 and cards[1].left.pct is None
    assert cards[1].right.value == 120 and cards[1].right.pct is None  # max z okresu = 0 -> brak porównania
    assert cards[2].left.value == 0 and cards[2].right.value == 0
    empty = _cards({})
    assert empty[1].right.value == 0 and empty[1].right.pct is None


def test_cards_kg_and_lbs_in_one_period_and_percent_base_zero():
    daily = aggregate_daily("weight", "reps", [
        row(date(2026, 10, 5), weight=100, reps=2),
        row(date(2026, 10, 6), weight=200, reps=1, unit="lbs"),
    ])
    c = _cards(daily)
    assert c[0].left.value == pytest.approx(200 + 90.718474)
    assert c[0].left.pct is None  # poprzedni okres bez danych (baza 0)
    assert c[0].right.value == pytest.approx(100)


def test_cards_second_measure_reps_and_time():
    reps = aggregate_daily("weight", "reps", [
        row(date(2026, 10, 5), weight=50, reps=8), row(date(2026, 10, 5), weight=50, reps=12),
        row(date(2026, 9, 5), weight=50, reps=10),
    ])
    c = _cards(reps)[2]
    assert (c.left.label, c.left.value, c.left.unit, c.left.pct) == ("Łączna liczba powtórzeń", 20, "powt.", 100)
    assert (c.right.label, c.right.value, c.right.pct) == ("Rekord powtórzeń w serii", 12, 20)
    time = aggregate_daily("distance", "time", [row(date(2026, 10, 5), dist=1000, dur=600), row(date(2026, 10, 5), dist=1000, dur=1800)])
    c = _cards(time, load="distance", effort="time")[2]
    assert (c.left.label, c.left.unit, c.right.label) == ("Łączny czas", "min", "Rekord czasu w serii")
    assert c.left.value == pytest.approx(40) and c.right.value == pytest.approx(30)

from datetime import date, timedelta

import pytest

from trainbeast.services import (
    DEMO_EXERCISES,
    DailyStats,
    SetRow,
    aggregate_daily,
    demo_catalog_measures,
    demo_start_date,
    fmt_percent,
    generate_demo_workouts,
    percent_change,
    period_label,
    period_range,
    period_series,
    period_stats,
    shift_period,
)


# --- zakresy ---
@pytest.mark.parametrize("day", [date(2026, 10, 19), date(2026, 10, 21), date(2026, 10, 25)])
def test_week_is_monday_to_sunday(day):
    start, end = period_range(day, "week")
    assert (start, end) == (date(2026, 10, 19), date(2026, 10, 25))
    assert start.weekday() == 0 and end.weekday() == 6


@pytest.mark.parametrize(
    "day, last",
    [(date(2026, 2, 10), 28), (date(2028, 2, 10), 29), (date(2026, 4, 3), 30), (date(2026, 10, 31), 31)],
)
def test_month_lengths(day, last):
    start, end = period_range(day, "month")
    assert start == day.replace(day=1)
    assert end == day.replace(day=last)
    assert (end - start).days + 1 == last


def test_year_boundary():
    assert period_range(date(2026, 12, 31), "month") == (date(2026, 12, 1), date(2026, 12, 31))
    assert period_range(date(2026, 12, 31), "week") == (date(2026, 12, 28), date(2027, 1, 3))
    assert period_range(date(2027, 1, 1), "week") == (date(2026, 12, 28), date(2027, 1, 3))


def test_previous_and_next_period():
    assert shift_period(date(2026, 3, 15), "month", -1) == date(2026, 2, 1)
    assert shift_period(date(2026, 1, 20), "month", -1) == date(2025, 12, 1)
    assert shift_period(date(2025, 12, 5), "month", 1) == date(2026, 1, 1)
    assert shift_period(date(2026, 1, 1), "week", -1) == date(2025, 12, 22)
    assert shift_period(date(2026, 10, 21), "week", 1) == date(2026, 10, 26)


# --- nazwa okresu ---
def test_period_label_months_polish_nominative():
    assert period_label(date(2026, 3, 1), "month") == "Marzec 2026"
    assert period_label(date(2026, 10, 1), "month") == "Październik 2026"
    assert period_label(date(2026, 12, 1), "month") == "Grudzień 2026"
    assert period_label(date(2027, 1, 1), "month") == "Styczeń 2027"


def test_period_label_weeks_iso():
    assert period_label(date(2026, 3, 16), "week") == "Tydzień 12, 2026"
    assert period_label(date(2025, 12, 29), "week") == "Tydzień 1, 2026"  # przełom roku: rok ISO następny
    assert period_label(date(2020, 12, 28), "week") == "Tydzień 53, 2020"
    assert period_label(date(2021, 1, 4), "week") == "Tydzień 1, 2021"


# --- seria punktów: tylko dni z danymi ---
def test_series_skips_days_without_sets():
    today = date(2026, 10, 25)
    daily = {date(2026, 10, 20): DailyStats(5, 4, 3), date(2026, 10, 22): DailyStats(1, 1, 1)}
    series = period_series(daily, today, "week", today)
    assert series == [(date(2026, 10, 20), DailyStats(5, 4, 3)), (date(2026, 10, 22), DailyStats(1, 1, 1))]


def test_series_future_days_skipped_and_other_periods_excluded():
    today = date(2026, 10, 21)  # środa
    daily = {
        date(2026, 10, 20): DailyStats(5, 4, 3),
        date(2026, 10, 23): DailyStats(9, 9, 9),  # przyszłość
        date(2026, 10, 12): DailyStats(7, 7, 7),  # poprzedni tydzień
    }
    series = period_series(daily, today, "week", today)
    assert [d for d, _ in series] == [date(2026, 10, 20)]


def test_series_no_data_is_empty():
    today = date(2026, 10, 21)
    assert period_series({}, today, "month", today) == []


def test_series_single_day():
    today = date(2026, 10, 21)
    series = period_series({date(2026, 10, 3): DailyStats(1, 2, 3)}, today, "month", today)
    assert len(series) == 1


# --- statystyki okresu ---
def test_period_stats_sum_and_max():
    today = date(2026, 10, 25)
    daily = {date(2026, 10, 19): DailyStats(100, 20, 5), date(2026, 10, 22): DailyStats(50, 30, 2)}
    assert period_stats(period_series(daily, today, "week", today)) == (150, 30)  # dni bez treningu wnoszą 0
    assert period_stats(period_series({}, today, "week", today)) == (0, 0)  # okres bez danych


def test_percent_change():
    assert percent_change(112, 100) == 12  # wzrost
    assert percent_change(80, 100) == -20  # spadek
    assert percent_change(100, 100) == 0  # brak zmiany
    assert percent_change(5, 0) is None  # poprzedni 0
    assert percent_change(0, 0) is None  # oba 0
    assert percent_change(112.5, 100) == 13  # zaokrąglanie od zera
    assert percent_change(112.4, 100) == 12
    assert percent_change(87.5, 100) == -13
    assert percent_change(0, 100) == -100


def test_fmt_percent():
    assert fmt_percent(12) == "+12%"
    assert fmt_percent(-5) == "-5%"
    assert fmt_percent(0) == "0%"
    assert fmt_percent(None) == "–"


# --- dane testowe ---
TODAY = date(2026, 10, 23)  # piątek


def test_demo_dates_are_mon_wed_fri_in_three_months():
    workouts = generate_demo_workouts(TODAY)
    start = demo_start_date(TODAY)
    assert start == date(2026, 7, 23)
    days = [w.day for w in workouts]
    assert days == sorted(set(days))
    assert all(d.weekday() in (0, 2, 4) for d in days)
    assert all(start <= d <= TODAY for d in days)
    assert days[-1] == TODAY  # dzisiaj włącznie


def test_demo_three_workouts_per_full_week_and_three_exercises():
    workouts = generate_demo_workouts(TODAY)
    weeks: dict[date, int] = {}
    for w in workouts:
        key = period_range(w.day, "week")[0]
        weeks[key] = weeks.get(key, 0) + 1
    first_week = period_range(demo_start_date(TODAY), "week")[0]
    for week, n in weeks.items():
        if week != first_week:  # pierwszy tydzień jest przycięty początkiem zakresu
            assert n == 3, week
    for w in workouts:
        assert [e.name for e in w.exercises] == list(DEMO_EXERCISES)
        assert all(e.sets for e in w.exercises)
        assert all(s.done for e in w.exercises for s in e.sets)


def test_demo_values_match_exercise_measures():
    assert demo_catalog_measures("Barbell Bench Press") == ("weight", "reps")
    assert demo_catalog_measures("Stairmaster / Stair Climber") == ("floors", "time")
    assert demo_catalog_measures("Cycling") == ("distance", "time")
    for w in generate_demo_workouts(TODAY):
        bench, stairs, cycling = w.exercises
        assert 3 <= len(bench.sets) <= 4
        assert all(60 <= s.weight_kg <= 80 and s.weight_kg % 2.5 == 0 and 6 <= s.reps <= 10 for s in bench.sets)
        assert 1 <= len(stairs.sets) <= 2
        assert all(s.reps > 0 and s.duration_s > 0 and s.weight_kg is None for s in stairs.sets)
        assert 1 <= len(cycling.sets) <= 2
        assert all(10_000 <= s.distance_m <= 26_000 and s.duration_s > 0 for s in cycling.sets)


def test_demo_is_reproducible_for_same_seed():
    assert generate_demo_workouts(TODAY, seed=1) == generate_demo_workouts(TODAY, seed=1)
    assert generate_demo_workouts(TODAY, seed=1) != generate_demo_workouts(TODAY, seed=2)


def test_demo_sets_feed_daily_stats():
    workouts = generate_demo_workouts(TODAY)
    rows = [
        SetRow(w.day, s.weight_kg, s.distance_m, s.reps, s.duration_s, None, None, True)
        for w in workouts
        for s in w.exercises[0].sets
    ]
    assert len(aggregate_daily("weight", "reps", rows)) == len(workouts)

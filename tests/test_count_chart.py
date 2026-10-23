from datetime import date

import pytest

from trainbeast.database import make_engine, make_session_factory
from trainbeast.services import (
    STARTER_CATEGORIES,
    TrainingService,
    compare_windows,
    count_by_period,
    count_period_label,
    count_window,
    fmt_average,
    fmt_workouts,
    navigate_count_window,
    limit_swipe_periods,
    nice_axis_scale,
    swipe_periods,
    period_starts,
    workouts_total_and_average,
    workouts_word,
)

TODAY = date(2026, 10, 23)


@pytest.fixture
def svc(tmp_path):
    return TrainingService(make_session_factory(make_engine(f"sqlite:///{tmp_path / 't.db'}")))


def add_workout(svc, day, category=None, done=False, names=None):
    """Trening z jednym ćwiczeniem z `category` (lub kilkoma z `names` kategorii); opcjonalnie z wykonaną serią."""
    w = svc.create_workout(day)
    for cat in names or [category]:
        ex = svc.get_exercises_by_category(cat)[0]
        we = svc.add_exercise_to_workout(w.id, ex.id)
        if done:
            st = svc.get_workout(w.id).exercises[-1].sets[0]
            svc.update_set(st.id, done=True)
    return w


# --- etykiety ---
def test_month_label_year_boundary():
    starts = period_starts(date(2026, 2, 1), "month")
    labels = [count_period_label(d, "month") for d in starts]
    assert labels[0] == "03.2025" and labels[-1] == "02.2026"
    assert labels[9] == "12.2025" and labels[10] == "01.2026"
    assert len(set(labels)) == 12


def test_week_label_iso_year_boundary():
    assert count_period_label(date(2025, 12, 29), "week") == "01 2026"  # 29.12.2025 (pn) należy do tygodnia 1 roku 2026
    assert count_period_label(date(2020, 12, 28), "week") == "53 2020"
    assert count_period_label(date(2025, 8, 25), "week") == "35 2025"
    assert count_period_label(date(2026, 4, 6), "week") == "15 2026"


def test_week_window_across_year_boundary():
    window = count_window(date(2026, 1, 1), "week", 0, None, None)  # 1.01.2026 to czwartek tygodnia 1
    assert window.end == date(2025, 12, 29)
    assert count_period_label(window.starts[-1], "week") == "01 2026"
    assert count_period_label(window.starts[-2], "week") == "52 2025"
    assert len(window.starts) == 12


# --- okno ---
def test_window_no_workouts_is_current_without_scrolling():
    window = count_window(TODAY, "month", 0, None, None)
    assert len(window.starts) == 12 and window.end == date(2026, 10, 1)
    assert window.starts[0] == date(2025, 11, 1)
    assert (window.min_shift, window.max_shift) == (0, 0)
    assert navigate_count_window(TODAY, "month", 0, -1, None, None) == 0


def test_window_back_to_first_workout():
    first = date(2024, 1, 15)
    window = count_window(TODAY, "month", -50, first, first)
    assert window.shift == window.min_shift == -22
    assert window.starts[0] == date(2024, 1, 1) and window.end == date(2024, 12, 1)
    assert len(window.starts) == 12
    assert navigate_count_window(TODAY, "month", -22, -1, first, first) == -22
    assert navigate_count_window(TODAY, "month", -21, -1, first, first) == -22


def test_window_short_history_shows_from_first_workout_and_cannot_move():
    first = date(2026, 7, 10)
    window = count_window(TODAY, "month", 0, first, first)
    assert window.starts == [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)]
    assert (window.min_shift, window.max_shift) == (0, 0)
    assert navigate_count_window(TODAY, "month", 0, -1, first, first) == 0
    assert navigate_count_window(TODAY, "month", 0, 1, first, first) == 0


def test_window_last_workout_in_current_period_blocks_forward():
    first = date(2025, 1, 1)
    assert navigate_count_window(TODAY, "month", 0, 1, first, date(2026, 10, 2)) == 0
    assert navigate_count_window(TODAY, "week", 0, 1, first, date(2026, 10, 20)) == 0  # tydzień 19-25.10


def test_window_last_workout_earlier_than_current_keeps_current_upper_bound():
    first = date(2025, 1, 1)
    window = count_window(TODAY, "month", 5, first, date(2026, 5, 3))
    assert window.max_shift == 0 and window.shift == 0 and window.end == date(2026, 10, 1)


def test_window_last_workout_later_than_current_moves_upper_bound():
    first = date(2025, 1, 1)
    last_done = date(2026, 12, 5)
    window = count_window(TODAY, "month", 0, first, last_done)
    assert window.max_shift == 2
    assert navigate_count_window(TODAY, "month", 1, 1, first, last_done) == 2
    assert navigate_count_window(TODAY, "month", 2, 1, first, last_done) == 2  # dalej nie ma
    assert count_window(TODAY, "month", 2, first, last_done).end == date(2026, 12, 1)


def test_service_workout_without_done_sets_does_not_move_boundary(svc):
    chest = STARTER_CATEGORIES[0]
    add_workout(svc, date(2026, 10, 5), chest, done=True)
    add_workout(svc, date(2026, 12, 20), chest, done=False)  # przyszły trening bez wykonanych serii
    assert svc.get_last_done_workout_date() == date(2026, 10, 5)
    first, last = svc.get_first_workout_date(), svc.get_last_done_workout_date()
    assert navigate_count_window(TODAY, "month", 0, 1, first, last) == 0
    add_workout(svc, date(2026, 12, 22), chest, done=True)
    assert svc.get_last_done_workout_date() == date(2026, 12, 22)


def test_service_no_workouts(svc):
    assert svc.get_last_done_workout_date() is None
    assert svc.get_workout_days(STARTER_CATEGORIES) == []


# --- filtr sekcji ---
def test_section_filter_all_equals_calendar_days(svc):
    chest, back, legs = STARTER_CATEGORIES[0], STARTER_CATEGORIES[1], STARTER_CATEGORIES[5]
    add_workout(svc, date(2026, 10, 1), chest)
    add_workout(svc, date(2026, 10, 2), back)
    add_workout(svc, date(2026, 9, 3), legs)
    svc.create_workout(date(2026, 9, 10))  # pusty trening: nie liczy się
    everything = [c.name for c in svc.get_categories()]
    days = svc.get_workout_days(everything)
    assert set(days) == svc.get_workout_dates_between(date(2026, 1, 1), date(2027, 1, 1))
    assert set(svc.get_workout_days([chest])) == {date(2026, 10, 1)}
    assert set(svc.get_workout_days([chest, legs])) == {date(2026, 10, 1), date(2026, 9, 3)}
    assert svc.get_workout_days([]) == []


def test_workout_with_two_sections_counted_once(svc):
    chest, back = STARTER_CATEGORIES[0], STARTER_CATEGORIES[1]
    add_workout(svc, date(2026, 10, 1), names=[chest, back])
    days = svc.get_workout_days([chest, back])
    assert days == [date(2026, 10, 1)]
    assert count_by_period(days, period_starts(date(2026, 10, 1), "month"), "month")[-1] == 1


def test_new_custom_section_is_included_in_list(svc):
    svc.add_category("Moja sekcja")
    assert "Moja sekcja" in [c.name for c in svc.get_categories()]


def test_count_by_period_months_and_weeks():
    days = [date(2026, 10, 1), date(2026, 10, 15), date(2026, 9, 30), date(2024, 1, 1)]
    counts = count_by_period(days, period_starts(date(2026, 10, 1), "month"), "month")
    assert counts[-1] == 2 and counts[-2] == 1 and sum(counts) == 3
    weeks = count_by_period([date(2026, 10, 19), date(2026, 10, 25), date(2026, 10, 26)], period_starts(date(2026, 10, 19), "week"), "week")
    assert weeks[-1] == 2 and weeks[-2] == 0


# --- suma i średnia ---
def test_total_and_average_divisor_is_periods_since_first_workout():
    days = [date(2026, 1, 10), date(2026, 3, 1), date(2026, 3, 2), date(2026, 10, 1), date(2026, 10, 2)]
    total, average = workouts_total_and_average(days, TODAY, "month", date(2026, 1, 10))
    assert total == 5 and average == pytest.approx(0.5)  # 10 miesięcy: sty-paź
    total, average = workouts_total_and_average(days, date(2026, 1, 20), "month", date(2026, 1, 10))
    assert (total, average) == (1, 1)


def test_total_and_average_no_workouts():
    assert workouts_total_and_average([], TODAY, "week", None) == (0, 0.0)


def test_total_and_average_filtered_uses_overall_first_workout():
    # filtrowane dni zaczynają się później niż pierwszy trening w całej historii: dzielnik liczy od pierwszego treningu
    total, average = workouts_total_and_average([date(2026, 10, 1)], TODAY, "month", date(2026, 1, 5))
    assert total == 1 and average == pytest.approx(0.1)


def test_fmt_average():
    assert fmt_average(3) == "3"
    assert fmt_average(2.6) == "2,6"
    assert fmt_average(2.64) == "2,6"
    assert fmt_average(0) == "0"
    assert fmt_average(10.0) == "10"
    assert fmt_average(0.04) == "0"


@pytest.mark.parametrize(
    "n, word",
    [(0, "treningów"), (1, "trening"), (2, "treningi"), (4, "treningi"), (5, "treningów"), (11, "treningów"),
     (12, "treningów"), (14, "treningów"), (22, "treningi"), (25, "treningów"), (112, "treningów"), (102, "treningi")],
)
def test_workouts_word(n, word):
    assert workouts_word(n) == word
    assert fmt_workouts(n) == f"{n} {word}"


# --- porównanie okien ---
END = date(2026, 10, 1)  # okno: 11.2025 - 10.2026, poprzednie: 11.2024 - 10.2025


def month_days(year, month, n):
    return [date(year, month, d) for d in range(1, n + 1)]


def test_compare_growth():
    days = month_days(2025, 3, 2) + month_days(2026, 3, 3)
    c = compare_windows(days, END, "month", date(2024, 11, 1))
    assert (c.total, c.previous_total) == (3, 2)
    assert c.total_pct == 50 and c.average_pct == 50
    assert c.average == pytest.approx(3 / 12) and c.previous_average == pytest.approx(2 / 12)


def test_compare_decline():
    days = month_days(2025, 3, 4) + month_days(2026, 3, 1)
    c = compare_windows(days, END, "month", date(2024, 11, 1))
    assert c.total_pct == -75 and c.average_pct == -75


def test_compare_no_change():
    days = month_days(2025, 3, 2) + month_days(2026, 3, 2)
    c = compare_windows(days, END, "month", date(2024, 11, 1))
    assert c.total_pct == 0 and c.average_pct == 0


def test_compare_previous_window_empty():
    c = compare_windows(month_days(2026, 3, 2), END, "month", date(2024, 11, 1))
    assert c.previous_total == 0 and c.total_pct is None and c.average_pct is None


def test_compare_previous_window_before_first_workout():
    c = compare_windows(month_days(2026, 3, 2), END, "month", date(2025, 11, 5))
    assert c.total_pct is None and c.average_pct is None and c.total == 2


def test_compare_partially_covered_previous_window():
    days = [date(2025, 4, 1), date(2025, 5, 1)] + month_days(2026, 3, 4)
    c = compare_windows(days, END, "month", date(2025, 3, 20))
    assert c.previous_total == 2 and c.total_pct == 100 and c.average_pct == 100
    assert c.previous_average == pytest.approx(2 / 12)  # dzielnik zawsze 12


def test_compare_no_workouts_at_all():
    c = compare_windows([], END, "month", None)
    assert (c.total, c.total_pct, c.average_pct) == (0, None, None)


def test_compare_weeks():
    c = compare_windows([date(2026, 10, 20), date(2026, 10, 21), date(2026, 6, 1)], date(2026, 10, 19), "week", date(2026, 1, 1))
    assert c.total == 2 and c.previous_total == 1 and c.total_pct == 100  # 1.06 leży w poprzednim oknie 12 tygodni


# --- skala osi Y ---
def margins(values):
    scale = nice_axis_scale(values)
    return min(values) - scale.lower, scale.upper - max(values), scale


def test_axis_scale_narrow_data():
    lower, upper, scale = nice_axis_scale([90, 100])[0], nice_axis_scale([90, 100])[1], nice_axis_scale([90, 100])
    assert lower > 0 and upper < 120  # nie 0-100
    assert lower <= 90 and upper >= 100
    assert 4 <= len(scale.ticks) <= 5


def test_axis_scale_wide_data():
    scale = nice_axis_scale([5, 20, 180, 400])
    assert scale.lower == 0 and scale.upper >= 400
    assert 4 <= len(scale.ticks) <= 5


def test_axis_scale_single_point():
    scale = nice_axis_scale([100])
    assert scale.lower < 100 < scale.upper
    assert scale.lower == pytest.approx(90, abs=6) and scale.upper == pytest.approx(110, abs=6)
    assert 4 <= len(scale.ticks) <= 5


def test_axis_scale_equal_values():
    scale = nice_axis_scale([50, 50, 50])
    assert scale.lower < 50 < scale.upper
    assert 4 <= len(scale.ticks) <= 5


def test_axis_scale_zeros_and_empty():
    assert nice_axis_scale([0, 0]) == (0, 1, [0, 1])
    assert nice_axis_scale([]) == (0, 1, [0, 1])


def test_axis_scale_lower_never_below_zero():
    for values in ([0.5, 3], [1, 2], [0, 10], [2, 2], [0.01], [0, 0.3]):
        assert nice_axis_scale(values).lower >= 0


def test_axis_scale_margins_similar():
    for values in ([90, 100], [100, 140], [1000, 1300], [37, 52]):
        below, above, scale = margins(values)
        step = scale.ticks[1] - scale.ticks[0]
        assert abs(below - above) <= step
        assert below >= 0 and above >= 0


def test_axis_scale_ticks_evenly_spaced():
    scale = nice_axis_scale([12.5, 17.5])
    steps = {round(b - a, 6) for a, b in zip(scale.ticks, scale.ticks[1:])}
    assert len(steps) == 1
    assert scale.ticks[0] == scale.lower and scale.ticks[-1] == scale.upper


# --- przesuwanie wykresu: próg 15% szerokości na okres ---
W = 300.0


@pytest.mark.parametrize(
    "percent, expected",
    [(0, 0), (14, 0), (15, 1), (29, 1), (30, 2), (44.9, 2), (45, 3), (90, 6)],
)
def test_swipe_periods_threshold_both_directions(percent, expected):
    dx = percent / 100 * W
    assert swipe_periods(-dx, W) == expected  # w lewo: nowsze (dodatnie)
    assert swipe_periods(dx, W) == -expected  # w prawo: starsze (ujemne)


def test_swipe_periods_zero_and_invalid_width():
    assert swipe_periods(0, W) == 0
    assert swipe_periods(-100, 0) == 0


@pytest.mark.parametrize(
    "periods, shift, expected",
    [(3, -5, 3), (-3, -5, -3), (-5, -3, -5), (5, -3, 3), (-2, -3, -2), (-1, 0, -1), (1, 0, 0), (0, -2, 0), (-4, -22, 0)],
)
def test_limit_swipe_periods(periods, shift, expected):
    # okno [-22, 0]; poza granicą zatrzymanie na granicy, na granicy 0
    assert limit_swipe_periods(periods, shift, -22, 0) == expected


def test_limit_swipe_periods_stops_at_boundary_not_ignores():
    assert limit_swipe_periods(-5, -20, -22, 0) == -2
    assert limit_swipe_periods(4, -1, -22, 0) == 1

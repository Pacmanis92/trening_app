import asyncio
from datetime import date

import flet as ft
import pytest

from trainbeast.database import make_engine, make_session_factory
from trainbeast.services import (
    DailyStats,
    DayTape,
    SetRow,
    TrainingService,
    aggregate_daily,
    clamp_tape_left,
    day_tape,
    dominant_period,
    drag_tape_shift,
    exercise_day_tape,
    initial_window_first,
    last_point_in_window,
    period_label,
    snap_tape_index,
    tape_chart_data,
    tape_day,
    window_stats,
)
from trainbeast.ui import TrainBeastApp

TODAY = date(2026, 10, 23)  # piątek


def last_day(tape):
    return tape_day(tape, tape.count - 1)


# --- zakres taśmy ---
def test_month_tape_from_first_month_to_current_month_end():
    tape = day_tape(TODAY, "month", date(2026, 8, 20), date(2026, 9, 10))
    assert tape.start == date(2026, 8, 1) and last_day(tape) == date(2026, 10, 31)
    assert tape.count == 31 + 30 + 31 and tape.visible == 31
    assert tape.first == 61  # okno = cały październik


def test_week_tape_iso_weeks_year_boundary_and_week_53():
    today = date(2027, 1, 4)  # poniedziałek, tydzień 1 roku 2027
    tape = day_tape(today, "week", date(2026, 12, 30), date(2026, 12, 30))
    assert tape.start == date(2026, 12, 28) and period_label(tape.start, "week") == "Tydzień 53, 2026"
    assert last_day(tape) == date(2027, 1, 10) and tape.count == 14
    assert tape.visible == 7 and tape.first == 7


def test_february_window_clamped_to_tape_end():
    tape = day_tape(date(2026, 2, 10), "month", date(2026, 1, 5), date(2026, 2, 3))
    assert tape.start == date(2026, 1, 1) and last_day(tape) == date(2026, 2, 28) and tape.count == 59
    assert tape.first == 28  # 31 dni od 1.02 wyszłoby poza taśmę: okno 29.01-28.02
    assert dominant_period(tape, tape.first, "month") == date(2026, 2, 1)  # luty 28 dni, styczeń 3


def test_history_shorter_than_window_fits_whole():
    tape = day_tape(date(2027, 2, 10), "month", date(2027, 2, 5), date(2027, 2, 5))
    assert tape.count == 28 and tape.visible == 28 and tape.first == 0
    tape = day_tape(TODAY, "week", date(2026, 10, 21), date(2026, 10, 21))
    assert (tape.start, tape.count, tape.visible, tape.first) == (date(2026, 10, 19), 7, 7, 0)


def test_exercise_without_sets_current_period_only():
    month = day_tape(TODAY, "month", None, None)
    assert (month.start, month.count, month.visible, month.first) == (date(2026, 10, 1), 31, 31, 0)
    week = exercise_day_tape({}, TODAY, "week")
    assert (week.start, week.count, week.visible, week.first) == (date(2026, 10, 19), 7, 7, 0)


def test_upper_bound_is_later_of_current_and_latest_set_period():
    in_current = day_tape(TODAY, "month", date(2026, 10, 5), date(2026, 10, 20))
    assert last_day(in_current) == date(2026, 10, 31)
    later = day_tape(TODAY, "month", date(2026, 10, 5), date(2026, 12, 22))
    assert later.start == date(2026, 10, 1) and last_day(later) == date(2026, 12, 31)
    assert later.first == 0  # okno nadal zaczyna się w bieżącym miesiącu
    older = day_tape(TODAY, "month", date(2026, 7, 5), date(2026, 8, 2))
    assert last_day(older) == date(2026, 10, 31)  # ostatnia seria dawno: górna granica = bieżący okres


def test_initial_window_aligned_to_current_period_start():
    assert initial_window_first(date(2026, 8, 1), 92, 31, TODAY, "month") == 61
    assert initial_window_first(date(2026, 9, 28), 60, 7, TODAY, "week") == 21  # poniedziałek 19.10
    assert initial_window_first(date(2026, 10, 1), 31, 31, TODAY, "month") == 0


# --- piksele -> indeks dnia, dosunięcie, granice ---
def test_snap_to_full_day_up_and_down_and_half_rounds_up():
    assert snap_tape_index(-34, 10, 60, 31) == 3  # 3,4 dnia: w dół
    assert snap_tape_index(-36, 10, 60, 31) == 4  # 3,6 dnia: w górę
    assert snap_tape_index(-5, 10, 60, 31) == 1  # dokładnie pół dnia: w górę


def test_snap_and_clamp_to_tape_start_and_end():
    assert snap_tape_index(40, 10, 60, 31) == 0  # za początkiem
    assert snap_tape_index(-1000, 10, 60, 31) == 29  # za końcem: ostatnie okno
    assert clamp_tape_left(40, 10, 60, 31) == 0
    assert clamp_tape_left(-1000, 10, 60, 31) == -290


def test_drag_follows_finger_one_to_one():
    assert drag_tape_shift(37.5, 300, 10, None) == 37.5
    assert drag_tape_shift(-12, 300, 10, None) == -12
    assert drag_tape_shift(45, 300, 10) == 10  # okresy: 15% szerokości = jeden slot


# --- okres przeważający w oknie ---
MONTH_TAPE = DayTape(date(2026, 9, 1), 122, 31, 0)  # 1.09-31.12
WEEK_TAPE = DayTape(date(2026, 10, 5), 70, 7, 0)


def test_dominant_month_20_11_11_20_and_tie_goes_to_later():
    assert dominant_period(MONTH_TAPE, 41, "month") == date(2026, 10, 1)  # 12.10-11.11: 20 dni października
    assert dominant_period(MONTH_TAPE, 50, "month") == date(2026, 11, 1)  # 21.10-20.11: 20 dni listopada
    tie = DayTape(date(2026, 9, 1), 122, 30, 0)  # 17.10-15.11: po 15 dni
    assert dominant_period(tie, 46, "month") == date(2026, 11, 1)


def test_dominant_week_4_3_and_3_4():
    assert dominant_period(WEEK_TAPE, 3, "week") == date(2026, 10, 5)  # czw-nd + pn-śr: 4 / 3
    assert dominant_period(WEEK_TAPE, 4, "week") == date(2026, 10, 12)  # pt-nd + pn-czw: 3 / 4
    assert dominant_period(WEEK_TAPE, 0, "week") == date(2026, 10, 5)


# --- punkty, skala, pola ---
def row(day, weight=None, reps=None, unit=None, done=True):
    return SetRow(day, weight, None, reps, None, unit, None, done)


def test_chart_data_only_days_with_sets_kg_and_lbs_future_skipped():
    daily = aggregate_daily(
        "weight",
        "reps",
        [
            row(date(2026, 10, 1), 100.0, 5),
            row(date(2026, 10, 5), 100.0, 3, unit="lbs"),
            row(date(2026, 10, 7), 50.0, 5, done=False),  # niewykonana: brak dnia
            row(date(2026, 10, 30), 90.0, 5),  # przyszłość
        ],
    )
    tape = exercise_day_tape(daily, TODAY, "month")
    w1, w2, w3 = tape_chart_data(daily, tape, TODAY)
    assert [x for x, _ in w1.points] == [0, 4]  # dni 1.10 i 5.10, bez 7.10 i 30.10
    lbs_kg = 100.0 * 0.45359237
    assert w2.points[1][1] == pytest.approx(lbs_kg)
    assert w1.points[1][1] == pytest.approx(lbs_kg * 3)
    assert [v for _, v in w3.points] == [5, 3]
    # stała skala z całej taśmy: zawęża się do danych i obejmuje wszystkie punkty
    assert w2.scale.lower >= 0 and w2.scale.lower <= lbs_kg and w2.scale.upper >= 100


def test_chart_data_covers_whole_tape_not_only_window():
    daily = {date(2026, 8, 20): DailyStats(10, 5, 4), date(2026, 10, 5): DailyStats(40, 20, 4)}
    tape = exercise_day_tape(daily, TODAY, "month")
    w1, _, _ = tape_chart_data(daily, tape, TODAY)
    assert [x for x, _ in w1.points] == [19, 65]
    assert w1.scale.upper >= 40 and w1.scale.lower <= 10  # skala uwzględnia też punkt poza oknem początkowym


def test_window_stats_whole_dominant_period_not_only_visible_days():
    daily = {
        date(2026, 9, 5): DailyStats(100, 50, 5, 5),  # poza oknem (okno 12.10-11.11), ale we wrześniu
        date(2026, 10, 2): DailyStats(40, 20, 4, 4),  # poza oknem, w październiku (przeważającym)
        date(2026, 10, 15): DailyStats(60, 30, 6, 6),  # w oknie
        date(2026, 11, 3): DailyStats(500, 90, 9, 9),  # w oknie, inny miesiąc
    }
    stats = window_stats("weight", "reps", daily, MONTH_TAPE, 41, "month", date(2026, 11, 20))
    assert stats.start == date(2026, 10, 1) and stats.label == "Październik 2026"
    first, second, third = stats.cards
    assert first.left.value == 100 and first.left.sublabel == "Październik 2026"  # 40 + 60: cały miesiąc
    assert first.left.pct == 0  # wrzesień też 100
    assert first.right.value == 30 and first.right.pct == -40  # rekord serii 30 vs 50 we wrześniu
    assert second.left.value == 30 and second.right.label == "Max od początku" and second.right.value == 90
    assert second.right.sublabel is None and second.right.compare == "vs. wybrany miesiąc"
    assert third.left.value == 10 and third.left.sublabel == "Październik 2026"


def test_window_stats_week_label():
    daily = {date(2026, 10, 14): DailyStats(10, 5, 2, 2)}
    stats = window_stats("weight", "reps", daily, WEEK_TAPE, 4, "week", date(2026, 12, 1))
    assert stats.label == "Tydzień 42, 2026" and stats.cards[0].left.sublabel == "Tydzień 42, 2026"
    assert stats.cards[0].left.value == 10


def test_last_point_in_window():
    xs = [2, 5, 9, 40]
    assert last_point_in_window(xs, 0, 31) == 2  # 9 to ostatni w oknie 0-30
    assert last_point_in_window(xs, 10, 31) == 3
    assert last_point_in_window(xs, 10, 5) is None  # brak danych: brak zaznaczenia
    assert last_point_in_window([], 0, 7) is None


# --- niezależność trzech wykresów (UI na atrapie strony) ---
class FakePage:
    platform = ft.PagePlatform.ANDROID
    width = 390
    height = 844

    def add(self, *controls):
        pass

    def update(self):
        pass


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(ft.BaseControl, "update", lambda self: None)  # kontrolki nie są podpięte do strony
    service = TrainingService(make_session_factory(make_engine(f"sqlite:///{tmp_path / 'ui.db'}")))
    return TrainBeastApp(FakePage(), service)


def test_charts_move_independently_and_reset_on_exercise_and_interval_change(app):
    today = date.today()
    svc = app.service
    ex = next(e for e in svc.list_exercises() if e.load_type == "weight" and e.effort_type == "reps")
    for days_ago in (100, 40, 3):
        w = svc.create_workout(date.fromordinal(today.toordinal() - days_ago))
        svc.add_exercise_to_workout(w.id, ex.id)
        st = svc.get_workout(w.id).exercises[0].sets[0]
        svc.update_set(st.id, weight_kg=50.0 + days_ago, reps=5, done=True)
    app.stats_exercise = ex
    app._build_stats_view()
    app._refresh_stats(update=False)
    charts = app.day_charts
    assert len(charts) == 3
    initial = [c.first for c in charts]
    assert len(set(initial)) == 1 and charts[0].scrollable

    async def swipe(chart, dx):
        chart._drag_start(ft.DragStartEvent(local_position=ft.Offset(0, 0), global_position=ft.Offset(200, 0), kind=ft.PointerDeviceType.TOUCH, name="s", control=None))
        chart._drag_update(ft.DragUpdateEvent(local_position=ft.Offset(0, 0), global_position=ft.Offset(200 + dx, 0), name="u", control=None))
        await chart._drag_end(ft.DragEndEvent(local_position=ft.Offset(0, 0), global_position=ft.Offset(0, 0), velocity=ft.Offset(0, 0), primary_velocity=0, name="e", control=None))

    asyncio.run(swipe(charts[1], 10 * charts[1].slot))  # w prawo: starsze dane
    assert charts[1].first == initial[1] - 10
    assert charts[0].first == initial[0] and charts[2].first == initial[2]
    assert app.stats_first == [None, charts[1].first, None]
    asyncio.run(swipe(charts[1], 100000))  # do początku taśmy
    assert charts[1].first == 0
    asyncio.run(swipe(charts[1], -100000))  # do końca taśmy
    assert charts[1].first == charts[1].count - charts[1].visible

    app._choose_interval("Tygodniowy")
    assert app.stats_first == [None, None, None]
    assert all(c.visible == 7 for c in app.day_charts)
    app.stats_first = [3, None, 5]
    app._pick_stats_exercise(next(e for e in svc.list_exercises() if e.id != ex.id).id)
    assert app.stats_first == [None, None, None]

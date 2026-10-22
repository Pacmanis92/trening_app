import asyncio
from datetime import date, timedelta

import flet as ft
import pytest

from trainbeast.database import make_engine, make_session_factory
from trainbeast.services import (
    TrainingService,
    day_tape_layout,
    drag_progress,
    settle_duration,
    settle_target,
)
from trainbeast.ui import TrainBeastApp

WIDTH = 374.0


@pytest.mark.parametrize(
    "dx, expected",
    [(0, 0.0), (-WIDTH / 2, 0.5), (WIDTH / 2, -0.5), (-WIDTH * 3, 1.0), (WIDTH * 3, -1.0)],
)
def test_drag_progress_follows_finger(dx, expected):
    assert drag_progress(dx, WIDTH) == pytest.approx(expected)


def test_drag_progress_continues_from_base_and_handles_zero_width():
    assert drag_progress(-WIDTH / 4, WIDTH, base=0.5) == pytest.approx(0.75)
    assert drag_progress(-10, 0) == 0.0


@pytest.mark.parametrize(
    "progress, expected",
    [(0.0, 0), (0.2, 0), (0.2499, 0), (0.25, 1), (0.2501, 1), (0.9, 1), (1.0, 1),
     (-0.2499, 0), (-0.25, -1), (-0.2501, -1), (-1.0, -1)],
)
def test_settle_target_25_percent_rule(progress, expected):
    assert settle_target(progress) == expected


def test_fast_fling_shortens_animation_but_not_decision():
    slow = settle_duration(0.2, 0, WIDTH, 0)
    fast = settle_duration(0.2, 0, WIDTH, 5000)
    assert fast <= slow
    assert settle_target(0.2) == 0  # prędkość nie wpływa na wybór dnia


def test_tape_at_rest_selected_centered_and_five_days_fill_window():
    layout = {o: (left, w) for o, left, w in day_tape_layout(0.0, 550)}
    left0, w0 = layout[0]
    assert left0 + w0 / 2 == pytest.approx(275)
    assert layout[-2][0] == pytest.approx(0)  # dwa dni przed: zaczynają się na lewej krawędzi okna
    assert layout[2][0] + layout[2][1] == pytest.approx(550)  # dwa po: kończą na prawej
    assert w0 == pytest.approx(550 * 3 / 11)


@pytest.mark.parametrize("step", [1, -1])
def test_tape_end_state_equals_rest_state_shifted_by_one_day(step):
    rest = {o: (left, w) for o, left, w in day_tape_layout(0.0, 550)}
    end = {o: (left, w) for o, left, w in day_tape_layout(float(step), 550)}
    for o in range(-2, 3):
        assert end[o + step] == pytest.approx(rest[o])


def test_tape_moves_continuously_and_monotonically_with_progress():
    previous = None
    for i in range(0, 101):
        p = i / 100
        left = {o: l for o, l, w in day_tape_layout(p, 550)}[0]
        assert previous is None or left < previous  # w lewo przy dodatnim postępie
        previous = left


# --- zachowanie UI na atrapie strony ---
class FakePage:
    platform = ft.PagePlatform.ANDROID
    width = 390
    height = 844

    def __init__(self):
        self.controls = []
        self.updates = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        self.updates += 1


def drag_start(x):
    return ft.DragStartEvent(local_position=ft.Offset(x, 0), global_position=ft.Offset(x, 0), kind=ft.PointerDeviceType.TOUCH, name="start", control=None)


def drag_update(x):
    return ft.DragUpdateEvent(local_position=ft.Offset(x, 0), global_position=ft.Offset(x, 0), name="update", control=None)


def drag_end(velocity=0.0):
    return ft.DragEndEvent(local_position=ft.Offset(0, 0), global_position=ft.Offset(0, 0), velocity=ft.Offset(velocity, 0), primary_velocity=velocity, name="end", control=None)


@pytest.fixture
def app(tmp_path):
    service = TrainingService(make_session_factory(make_engine(f"sqlite:///{tmp_path / 'ui.db'}")))
    application = TrainBeastApp(FakePage(), service)
    application._panel_width = 300.0
    return application


def frame_state(app):
    """(offsety paneli, lewe krawędzie dni na taśmie) - wszystko, co ruch palca zmienia."""
    return (
        {k: p.offset.x for k, p in app._panels.items()},
        [round(c[0].left, 3) for c in app._tabs.values()],
    )


def test_swipe_left_moves_both_views_and_commits_next_day(app):
    start_day = date(2026, 10, 25)
    app.selected = start_day
    app.render()
    app._panel_width = 300.0
    tape_before = [c[0].left for c in app._tabs.values()]

    async def scenario():
        app._on_drag_start(drag_start(200))
        app._on_drag_update(drag_update(125))  # -75 px => 25% szerokości
        assert app._progress == pytest.approx(0.25)
        assert app._panels[0].offset.x == pytest.approx(-0.25)
        assert app._panels[1].offset.x == pytest.approx(0.75)
        assert app._panels[-1].offset.x == pytest.approx(-1.25)
        assert app.selected == start_day  # data zmienia się dopiero po zwolnieniu
        assert [c[0].left for c in app._tabs.values()] != tape_before
        # zatrzymanie palca: brak zdarzeń => pozycje się nie zmieniają
        frozen = frame_state(app)
        await asyncio.sleep(0.1)
        assert frame_state(app) == frozen
        # ponowny ruch kontynuuje
        app._on_drag_update(drag_update(50))  # -150 px => 50%
        assert app._progress == pytest.approx(0.5)
        app._on_drag_update(drag_update(40))  # 53% => przekroczone 25%
        await app._on_drag_end(drag_end(-100))

    asyncio.run(scenario())
    assert app.selected == date(2026, 10, 26)
    assert app._progress == 0.0 and set(app._panels) == {0}
    assert app._panels[0].offset.x == 0


def test_swipe_right_goes_back_over_year_boundary(app):
    app.selected = date(2026, 1, 1)
    app.render()
    app._panel_width = 300.0

    async def scenario():
        app._on_drag_start(drag_start(10))
        app._on_drag_update(drag_update(250))  # +240 px => -80%
        await app._on_drag_end(drag_end())

    asyncio.run(scenario())
    assert app.selected == date(2025, 12, 31)


def test_release_below_25_percent_returns_to_current_day(app):
    day = app.selected

    async def scenario():
        app._on_drag_start(drag_start(200))
        app._on_drag_update(drag_update(200 - 0.24 * app._panel_width))  # 24% => aktualny dzień
        await app._on_drag_end(drag_end(-3000))  # nawet szybki gest nie łamie reguły 25%

    asyncio.run(scenario())
    assert app.selected == day
    assert app._progress == 0.0
    assert all(p.offset.x == step for step, p in app._panels.items())
    positions = [round(c[0].left, 3) for c in app._tabs.values()]
    fresh = [round(l + 1, 3) for _, l, _ in day_tape_layout(0.0, app._tape_width)]
    assert positions == fresh


def test_cancel_tap_and_stray_events_do_not_change_day(app):
    day = app.selected

    async def scenario():
        await app._on_drag_end(drag_end())  # koniec bez startu
        app._on_drag_update(drag_update(10))  # update bez startu
        await app._on_drag_cancel(None)
        app._on_drag_start(drag_start(100))
        app._on_drag_update(drag_update(90))
        await app._on_drag_cancel(None)  # anulowanie małego ruchu
        app._on_drag_start(drag_start(100))
        await app._on_drag_end(drag_end())  # dotknięcie bez ruchu

    asyncio.run(scenario())
    assert app.selected == day and app._progress == 0.0


def test_new_drag_takes_over_running_animation_without_double_commit(app):
    day = app.selected

    async def scenario():
        app._on_drag_start(drag_start(200))
        app._on_drag_update(drag_update(20))  # ~60%
        settle = asyncio.create_task(app._on_drag_end(drag_end()))
        await asyncio.sleep(0.02)
        app._on_drag_start(drag_start(100))  # palec wraca w trakcie animacji
        await settle
        assert app.selected == day  # animacja przerwana, brak zatwierdzenia
        app._on_drag_update(drag_update(300))  # przeciąganie w prawo od bieżącej pozycji
        assert app._progress < 0.6
        await app._on_drag_end(drag_end())

    asyncio.run(scenario())
    assert app.selected in (day, day + timedelta(days=1))
    assert app._progress == 0.0


def test_neighbour_preview_does_not_touch_current_view_state(app):
    app.service.create_workout(app.selected)
    app.render()
    workout_id, cards, selected = app.workout_id, app.cards_column, app.selected
    assert workout_id is not None
    app._on_drag_start(drag_start(200))
    assert (app.workout_id, app.cards_column, app.selected) == (workout_id, cards, selected)
    assert set(app._panels) == {-1, 0, 1}


def test_date_bar_frame_is_static_and_tape_is_clipped(app):
    bar = app.page.controls[0].content.content.controls[1].content.controls[0]  # kontener paska dni
    frame = bar
    row = frame.content
    window = row.controls[1]
    assert window.clip_behavior == ft.ClipBehavior.HARD_EDGE
    assert row.controls[0].width == row.controls[2].width == 28  # strzałki stałe

    def static_props():
        return (frame.border.top.color, frame.border_radius, frame.bgcolor, row.controls[0].width, window.height, frame.padding.left)

    before = static_props()

    async def scenario():
        app._on_drag_start(drag_start(200))
        for x in (180, 120, 60):
            app._on_drag_update(drag_update(x))
            assert static_props() == before
            assert frame.offset is None and window.offset is None  # nic z ramki się nie przesuwa
        await app._on_drag_end(drag_end())

    asyncio.run(scenario())


def test_next_day_month_boundaries():
    assert date(2026, 2, 28) + timedelta(days=1) == date(2026, 3, 1)
    assert date(2028, 2, 28) + timedelta(days=1) == date(2028, 2, 29)
    assert date(2026, 12, 31) + timedelta(days=1) == date(2027, 1, 1)


@pytest.mark.parametrize("fraction, direction", [(0.25, 1), (0.30, 1), (-0.25, -1), (-0.30, -1), (0.24, 0), (-0.24, 0)])
def test_release_threshold_in_ui(app, fraction, direction):
    app.selected = date(2026, 10, 25)
    app.render()
    app._panel_width = 400.0

    async def scenario():
        app._on_drag_start(drag_start(200))
        app._on_drag_update(drag_update(200 - fraction * 400.0))
        await app._on_drag_end(drag_end())

    asyncio.run(scenario())
    assert app.selected == date(2026, 10, 25) + timedelta(days=direction)
    assert app._progress == 0.0

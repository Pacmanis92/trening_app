import asyncio
import math
import time
from datetime import date, timedelta

import flet as ft
import flet_charts as fch

from .services import (
    EMPTY_SUMMARY,
    MONTH_NAMES_GENITIVE,
    WEEKDAY_ABBR,
    TrainingService,
    ValidationError,
    SummaryGroup,
    AxisScale,
    StatCard,
    StatColumn,
    WorkoutSnapshot,
    allowed_units,
    compare_windows,
    count_by_period,
    count_period_label,
    count_window,
    default_selected_index,
    ease_out_cubic,
    exercise_stat_cards,
    fmt_average,
    fmt_percent,
    fmt_workouts,
    nearest_day_index,
    limit_swipe_periods,
    navigate_period,
    nice_axis_scale,
    period_label,
    period_label_step,
    period_range,
    period_series,
    interpret_swipe,
    done_sets_count,
    has_snapshot_to_paste,
    fmt_decimal,
    fmt_stat_number,
    fmt_set_line,
    day_tape_layout,
    drag_progress,
    classify_day,
    is_valid_digits_input,
    is_valid_distance_input,
    is_valid_minsec_input,
    is_valid_weight_input,
    month_grid,
    month_range,
    normalize_empty_input,
    parse_distance,
    parse_duration,
    parse_floors,
    parse_reps,
    parse_weight,
    set_unit_of,
    settle_duration,
    settle_target,
    shift_month,
    stat_titles,
    swipe_periods,
    workouts_total_and_average,
    summarize_exercise,
    weekday_abbr,
    y_axis_ticks,
)

BTN_HEIGHT = 60
FIELD_HEIGHT = 60
EXERCISE_NAME_SIZE = 18  # nazwa ćwiczenia: ten sam rozmiar w trybie edycji i nieedytowalnym
SET_TEXT_LINE = 24  # wysokość linii wartości (czcionka 16); odstęp tekstu od krawędzi = (wysokość pola - linia) / 2
SET_FIELD_V_GAP_OLD = (44 - SET_TEXT_LINE) / 2  # dawny odstęp (pole miało 44 px) = 10
SET_FIELD_V_GAP = SET_FIELD_V_GAP_OLD / 2  # o 50% mniejszy odstęp tekstu od górnej i dolnej krawędzi = 5
SET_FIELD_HEIGHT = int(SET_TEXT_LINE + 2 * SET_FIELD_V_GAP)  # wspólna wysokość wszystkich pól miar = 34
SET_LABEL_SIZE = 11  # etykieta jednostki na górnej krawędzi pola
LABEL_OVERHANG = 8  # tyle etykieta wystaje nad ramkę pola (jej środek leży na krawędzi)
SET_ROW_HEIGHT = SET_FIELD_HEIGHT + LABEL_OVERHANG
NAME_ROW_HEIGHT = 60 * 0.6  # pole „Nazwa treningu" i przycisk „Kopiuj": jedna wspólna wysokość
CAL_TEXT = "#222222"
CAL_ROW_HEIGHT = 48
CAL_TITLE_HEIGHT = 44
CAL_WEEKDAY_HEIGHT = 28
CAL_MONTH_GAP = 16  # odstęp nad nagłówkiem miesiąca
CAL_MONTH_FIXED = CAL_TITLE_HEIGHT + CAL_WEEKDAY_HEIGHT + CAL_MONTH_GAP  # wysokość miesiąca bez wierszy dni
CAL_SAT = ft.Colors.GREY_600
CAL_SUN = ft.Colors.RED_600
ACCENT = "#FCB808"  # żółty ramek (odczytany ze zrzutu inspiracji)
BLACK = "#000000"
FILL_DARK = "#171717"  # wypełnienie paska dni, pola nazwy i kart ćwiczeń
SCREEN_MARGIN = 8  # margines ekranu: lewy napisu TrainBeast = prawy ikony kalendarza
HEADER_ICON_OFFSET = 30 + 4  # dawny hantel (30) + odstęp (4): zachowuje pozycję „NO EXCUSES"
CAL_WORKOUT_BG = "#FFE9A0"
CAL_TODAY_BG = ACCENT
OUTLINE_BTN_RADIUS = 22
CARD_RADIUS = 12
DAY_TAB_HEIGHT = 32  # dwa wiersze (skrót dnia ok. 12 + data ok. 16) z minimalnym zapasem
DAY_BAR_V_PAD = 3  # odstęp góra/dół między ramką paska a zakładkami
DAY_ABBR_SIZE = 10
DAY_BAR_RADIUS = (DAY_TAB_HEIGHT + 2 * DAY_BAR_V_PAD + 2) / 2  # pigułka: połowa wysokości paska z ramką (40)
LINK_HEIGHT = 22  # „Wróć do dzisiaj": wysokość pola linku (dawniej ok. 48 z domyślnym polem dotyku)
CLOSE_BUTTON_COLOR = ACCENT  # napis „Zamknij" w oknach (podsumowanie ćwiczenia, filtr sekcji): jedna wspólna stała
ACTION_BLUE = ft.Colors.PRIMARY  # niebieski „Zakończ" (kolor główny motywu); też daszek
BTN_FILL = ft.Colors.with_opacity(0.25, ACCENT)  # półprzezroczyste żółte wypełnienie przycisków
ACCENT_DARK = "#584003"  # ciemny odcień żółtego ramek (ACCENT * 0,35): wypełnienie „+ Dodaj ćwiczenie" i „Kopiuj"
DONE_ICON_SIZE = 22  # wskaźnik wykonania serii: wspólny dla widoku edycji i nieedytowalnego
DONE_ICON_PAD = 6
UNIT_MENU_WIDTH = 112  # minimalna szerokość menu Material; linia rozdzielająca ma całą szerokość
EDIT_BTN_HEIGHT = 40  # „+ Dodaj serię" i „Zakończ" w karcie edycji
LIST_BTN_HEIGHT = BTN_HEIGHT - 8  # „Zwiń listę” i „+ Dodaj serię”: ten sam domyślny styl i wysokość
EDIT_BTN_GAP = 12  # dodatkowy odstęp między ostatnią serią a wierszem przycisków
HEADER_BTN_HEIGHT = 48  # wysokość ikony kalendarza (32 + 2 * 8); „Donate" ma tę samą
HEADER_BTN_RADIUS = 10  # zaokrąglenie ikony kalendarza i „Donate"
HEADER_BTN_BORDER = ft.BorderSide(1, ACCENT)  # ramka ikony kalendarza i „Donate"
TAB_BAR_HEIGHT = 48
TAB_SPACER = 16  # odstęp na dole przewijanych list nad paskiem zakładek
STATS_CARD_BG = "#272a2f"
STATS_CHART_HEIGHT = 210
STATS_CHART_LABEL_SIZE = 10
STATS_LEFT_AXIS_WIDTH = 44
CHART_GRID_COLOR = "#30343a"  # tylko odrobinę jaśniejszy niż STATS_CARD_BG (ramka i linia pól statystyk)
CHART_GRID_LINE_COLOR = "#FFFFFF"  # poziome przerywane linie siatki wszystkich wykresów
CHART_TOOLTIP_ROOM = 36  # miejsce nad wykresem na dymek najwyższego punktu
SELECTED_DOT_RADIUS = 6
STAT_LABEL_HEIGHT = 32  # dwie linie etykiety (czcionka 12): wartości obu kolumn leżą na jednej wysokości
STATS_DIVIDER_HEIGHT = 92  # pionowa linia między kolumnami statystyk
STAT_CARD_BG = FILL_DARK  # pole statystyk: ciemniejsze niż karta wykresu, z cienką ramką
CHART_TOOLTIP_BG = "#1b1d20"
CHART_TOOLTIP_BORDER = "#d9d9d9"
CHART_LABEL_BOX = (14, 48)  # (szerokość, wysokość) pola obróconej etykiety: mieści pogrubione „WW RRRR” (ok. 44 px) z zapasem
CHART_LABEL_GAP = 6  # odstęp między osią X a polem etykiety: linia zaznaczenia nie zachodzi na etykietę
CHART_BOTTOM_AXIS = CHART_LABEL_BOX[1] + CHART_LABEL_GAP  # stała rezerwa pod osią (nie zależy od zaznaczenia)
UP_COLOR = ft.Colors.GREEN_400
DOWN_COLOR = ft.Colors.RED_400
FILTER_ROW_HEIGHT = 48  # wysokość wiersza z polem wyboru w oknie sekcji (szacunek do decyzji o przewijaniu)
FILTER_MAX_HEIGHT = 0.7  # część wysokości ekranu, powyżej której lista sekcji się przewija
INTERVAL_WIDTH = 124
INTERVAL_LABELS = {"month": "Miesięczny", "week": "Tygodniowy"}
DONATE_WIDTH = 64  # trochę szerszy niż kalendarz (48), napis „Donate" mieści się w jednym wierszu


def day_color(weekday: int) -> str:
    """Kolor dnia tygodnia (0 = poniedziałek): sobota szara, niedziela czerwona."""
    return CAL_SAT if weekday == 5 else CAL_SUN if weekday == 6 else CAL_TEXT


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_short(d: date) -> str:
    return d.strftime("%d.%m")


def workout_title(w) -> str:
    return w.name or "Trening"


def outline_style(padding=None) -> ft.ButtonStyle:
    """„Podsumowanie ćwiczenia", „Dodaj trening", „Wklej trening": półprzezroczyste żółte wypełnienie, biały tekst, bez ramki."""
    return ft.ButtonStyle(
        bgcolor=BTN_FILL,
        color=ft.Colors.WHITE,
        shape=ft.RoundedRectangleBorder(radius=OUTLINE_BTN_RADIUS),
        padding=padding,
    )


def delete_style() -> ft.ButtonStyle:
    """Jak domyślny ft.Button („+ Dodaj serię”: bez ramki, domyślny kształt): wypełnienie #171717, żółty tekst."""
    return ft.ButtonStyle(bgcolor=FILL_DARK, color=ACCENT)


def add_exercise_style(padding=None) -> ft.ButtonStyle:
    """Wspólny styl „+ Dodaj ćwiczenie” i „Kopiuj”: dawny styl „Usuń trening” (ciemnożółte wypełnienie), biały tekst."""
    return ft.ButtonStyle(bgcolor=ACCENT_DARK, color=ft.Colors.WHITE, padding=padding)


def cancel_style() -> ft.ButtonStyle:
    """„Anuluj" i „Zamknij" w oknach: żółty napis (kolor tekstu „Usuń trening"), bez zmiany tła."""
    return ft.ButtonStyle(color=CLOSE_BUTTON_COLOR)


def header_btn_style(padding=None) -> ft.ButtonStyle:
    """Wspólny styl ikony kalendarza i „Donate": czarne wypełnienie, żółta ramka, to samo zaokrąglenie."""
    return ft.ButtonStyle(
        bgcolor=BLACK,
        color=ACCENT,
        side=HEADER_BTN_BORDER,
        shape=ft.RoundedRectangleBorder(radius=HEADER_BTN_RADIUS),
        padding=padding,
    )


def big_button(text: str, on_click, primary: bool = True, outlined: bool = False, **kwargs) -> ft.Control:
    cls = ft.FilledButton if primary else ft.Button
    if outlined:
        kwargs["style"] = outline_style()
    return cls(text, on_click=on_click, height=BTN_HEIGHT, expand=kwargs.pop("expand", None), **kwargs)


def done_icon(done: bool) -> ft.Icon:
    """Wskaźnik wykonania serii (żółte kółko z ptaszkiem / puste kółko): wspólny dla edycji i widoku nieedytowalnego."""
    return ft.Icon(
        ft.Icons.CHECK_CIRCLE if done else ft.Icons.RADIO_BUTTON_UNCHECKED,
        size=DONE_ICON_SIZE,
        color=ACCENT if done else ft.Colors.OUTLINE,
    )


def own_button(text: str, on_click, **kwargs) -> ft.FilledButton:
    """„Dodaj własne” i „Dodaj sekcję”: wspólny wygląd w oknie wyboru ćwiczenia (styl „+ Dodaj ćwiczenie”)."""
    return ft.FilledButton(text, height=BTN_HEIGHT - 8, style=add_exercise_style(), on_click=on_click, **kwargs)


def fmt_chart_date(d: date) -> str:
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def vertical_label(text: str, highlight: bool = False) -> ft.Control:
    """Etykieta osi X obrócona o 270 stopni (dawne 90 + 180; Text.rotate nie zmienia rozmiaru, więc leży w Stacku o stałym polu)."""
    w, h = CHART_LABEL_BOX
    return ft.Container(
        ft.Stack(
            [
                ft.Container(
                    ft.Text(
                        text,
                        size=STATS_CHART_LABEL_SIZE,
                        color=ACCENT if highlight else ft.Colors.WHITE,
                        weight=ft.FontWeight.BOLD if highlight else None,
                        no_wrap=True,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    width=h,
                    height=w,
                    alignment=ft.Alignment.CENTER,
                    left=(w - h) / 2,
                    top=(h - w) / 2 + CHART_LABEL_GAP,
                    rotate=ft.Rotate(math.pi / 2 + math.pi),
                )
            ],
            clip_behavior=ft.ClipBehavior.NONE,
        ),
        width=w,
        height=h + CHART_LABEL_GAP,
    )


class PeriodChart:
    """Wspólny wykres z zaznaczanym punktem; używany dla W1, W2 i W3 (punkt = dzień) oraz liczby treningów (punkt = okres).

    Zaznaczenie (powiększona kropka, przerywana linia w dół, dymek) jest nakładką w Stacku nad LineChart, bo wbudowane
    `selected` przy `interactive=False` psuło w Flet 1.0.4 rysowanie kolejnych kart."""

    def __init__(
        self,
        title: str,
        heading_extra: ft.Control,
        points: list[tuple[int, float]],
        tip_titles: list[str],
        axis_labels: list[str],
        value_text,
        scale: AxisScale,
        footer: ft.Control,
        page_width: float,
        highlight_label: bool = False,
        on_shift=None,
    ):
        """points: (pozycja na osi X, wartość) tylko dla slotów z danymi; tip_titles: nagłówek dymku każdego punktu;
        axis_labels: etykiety wszystkich slotów osi X; value_text: wartość -> napis w dymku; scale: skala osi Y.
        on_shift: async (wykres, liczba okresów ze znakiem); gdy podane, przeciąganie przesuwa tylko zawartość wykresu
        (linię z punktami, etykiety osi X i zaznaczenie) w obrębie obszaru wykresu, a oś Y i siatka stoją w miejscu."""
        self.title, self.points, self.tip_titles, self.axis_labels = title, points, tip_titles, axis_labels
        self.count, self.value_text, self.scale, self.highlight_label = len(axis_labels), value_text, scale, highlight_label
        self.selected = default_selected_index(points)
        self.on_shift = on_shift
        self.busy = False
        self.layer: ft.Container | None = None
        self.viewport: ft.Stack | None = None
        self._drag: list[float] = []  # [x startu, ostatnie przesunięcie]
        self.width = max(page_width - 2 * SCREEN_MARGIN - 24 - 12, 100.0)  # karta (padding 12) i prawy odstęp 12; poprawiane on_size_change
        self.chart_host = ft.Container(padding=ft.Padding.only(right=12))
        # tytuł i okres w jednym wierszu; gdy się nie mieszczą, okres przechodzi pod tytuł (nic nie jest ucinane)
        heading = ft.Row(
            [
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                heading_extra,
            ],
            wrap=True,
            spacing=12,
            run_spacing=2,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        chart_card = ft.Container(
            ft.Column(
                [heading, self._gesture()],
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            padding=12,
            bgcolor=STATS_CARD_BG,
            border_radius=CARD_RADIUS,
        )
        self.control = ft.Column([chart_card, footer], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.chart_host.on_size_change = self._on_size
        self._build()

    def _gesture(self) -> ft.GestureDetector:
        if self.on_shift is None:
            return ft.GestureDetector(self.chart_host, on_tap_down=self._on_tap)
        return ft.GestureDetector(
            self.chart_host,
            on_tap_down=self._on_tap,
            drag_interval=10,
            on_horizontal_drag_start=self._drag_start,
            on_horizontal_drag_update=self._drag_update,
            on_horizontal_drag_end=self._drag_end,
            on_horizontal_drag_cancel=self._drag_cancel,
        )

    @property
    def plot_width(self) -> float:
        return max(self.width - STATS_LEFT_AXIS_WIDTH, 1.0)

    def _drag_start(self, e: ft.DragStartEvent) -> None:
        if not self.busy and self.layer is not None:
            self._drag = [e.global_position.x, 0.0]

    def _drag_update(self, e: ft.DragUpdateEvent) -> None:
        if not self._drag or self.busy or self.layer is None:
            return
        width = self.plot_width
        self._drag[1] = max(-width, min(width, e.global_position.x - self._drag[0]))
        self.layer.offset = ft.Offset(self._drag[1] / width, 0)  # zawartość podąża za palcem
        self.layer.update()

    async def _drag_end(self, e: ft.DragEndEvent) -> None:
        if not self._drag or self.busy:
            return
        dx, self._drag = self._drag[1], []
        self.busy = True  # w trakcie animacji kolejne gesty są ignorowane
        try:
            await self.on_shift(self, swipe_periods(dx, self.plot_width))
        finally:
            self.busy = False

    async def _drag_cancel(self, e=None) -> None:
        if self._drag and not self.busy:
            self._drag = []
            self.busy = True
            try:
                await self.snap_back()
            finally:
                self.busy = False

    async def _animate(self, start: float, target: float, incoming: ft.Container | None = None, delta: int = 0) -> None:
        """Przesuwa warstwę z offsetu `start` do `target` (ułamek szerokości obszaru); `incoming` (warstwa) jedzie obok niej
        (jego offset = offset warstwy + delta)."""
        layer, viewport = self.layer, self.viewport
        duration = settle_duration(-start, -target, self.plot_width)
        began = time.perf_counter()
        while True:
            t = min(1.0, (time.perf_counter() - began) / duration)
            offset = start + (target - start) * ease_out_cubic(t)  # krzywa i czas jak w pozostałych animacjach
            layer.offset = ft.Offset(offset, 0)
            if incoming is not None:
                incoming.offset = ft.Offset(offset + delta, 0)
            viewport.update()
            if t >= 1.0:
                break
            await asyncio.sleep(0.012)

    async def snap_back(self) -> None:
        """Zawartość wraca na miejsce (przesunięcie poniżej progu lub granica okna)."""
        if self.layer is not None and self.layer.offset and self.layer.offset.x:
            await self._animate(self.layer.offset.x, 0.0)

    async def slide_in(self, incoming: "PeriodChart", delta: int) -> None:
        """Dotychczasowa zawartość wyjeżdża (delta = 1 w lewo, nowsze dane), zawartość `incoming` nadjeżdża z przeciwnej strony."""
        if self.layer is None or self.viewport is None:
            return
        incoming.width = self.width
        arriving = incoming._make_layer()  # tylko do animacji; `incoming` zachowuje własną, niepodpiętą warstwę
        start = self.layer.offset.x if self.layer.offset else 0.0
        arriving.offset = ft.Offset(start + delta, 0)
        self.viewport.controls.append(arriving)
        self.viewport.update()
        await asyncio.sleep(0.03)
        await self._animate(start, -float(delta), arriving, delta)

    def _on_size(self, e) -> None:
        width = e.width - 12
        if abs(width - self.width) > 1:
            self.width = width
            self._build()
            self.chart_host.update()

    def _on_tap(self, e: ft.TapEvent) -> None:
        if not self.points:
            return
        guess = nearest_day_index(e.local_position.x, STATS_LEFT_AXIS_WIDTH, self.width, self.count)
        chosen = min(range(len(self.points)), key=lambda n: abs(self.points[n][0] - guess))
        if chosen != self.selected:
            self.selected = chosen
            self._build()
            self.chart_host.update()

    def _overlay(self, origin: float = 0.0) -> list[ft.Control]:
        """Kropka, przerywana linia pionowa do osi X i dymek zaznaczonego dnia (współrzędne z geometrii wykresu);
        `origin` = lewa krawędź układu współrzędnych (0: cały wykres, oś Y: sam obszar wykresu)."""
        if self.selected is None:
            return []
        day_index, value = self.points[self.selected]
        plot_w = self.width - STATS_LEFT_AXIS_WIDTH
        plot_h = STATS_CHART_HEIGHT - CHART_BOTTOM_AXIS
        x = STATS_LEFT_AXIS_WIDTH + (day_index + 0.5) / self.count * plot_w - origin
        lower, upper = self.scale.lower, self.scale.upper
        y = CHART_TOOLTIP_ROOM + plot_h * (1 - (value - lower) / (upper - lower))
        dash, gap = 3, 3
        length = CHART_TOOLTIP_ROOM + plot_h - y  # od punktu do osi X
        dashes = max(math.ceil(length / (dash + gap)), 1)
        line = ft.Column(
            [
                ft.Container(width=1.5, height=min(dash, length - n * (dash + gap)), bgcolor=ACCENT)  # ostatnia kreska kończy się na osi
                for n in range(dashes)
            ],
            spacing=gap,
            left=x - 0.75,
            top=y,
        )
        dot = ft.Container(
            width=2 * SELECTED_DOT_RADIUS,
            height=2 * SELECTED_DOT_RADIUS,
            border_radius=SELECTED_DOT_RADIUS,
            bgcolor=ACCENT,
            border=ft.Border.all(2, ft.Colors.WHITE),
            left=x - SELECTED_DOT_RADIUS,
            top=y - SELECTED_DOT_RADIUS,
        )
        value_text = self.value_text(value)
        tip_w = max(96.0, 22 + 8.5 * len(value_text))
        tip_h = 46.0
        tip = ft.Container(
            ft.Column(
                [
                    ft.Text(self.tip_titles[self.selected], size=12, color=ft.Colors.WHITE),
                    ft.Text(value_text, size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, max_lines=1),
                ],
                spacing=2,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=tip_w,
            height=tip_h,
            padding=ft.Padding.symmetric(horizontal=10),
            bgcolor=CHART_TOOLTIP_BG,
            border=ft.Border.all(1, CHART_TOOLTIP_BORDER),
            border_radius=8,
            left=min(max(x - tip_w / 2, 0), max(self.width - origin - tip_w, 0)),  # nie wychodzi poza kartę (obszar)
            top=max(y - SELECTED_DOT_RADIUS - 4 - tip_h, 0),
        )
        return [line, dot, tip]

    def _is_selected_slot(self, slot: int) -> bool:
        return self.highlight_label and self.selected is not None and self.points[self.selected][0] == slot

    def _line_chart(self, *, data: bool, grid: bool, y_labels: bool, x_labels: bool, **place) -> fch.LineChart:
        """LineChart o stałej geometrii (te same osie i rezerwy), z wybranymi elementami: dane, siatka, etykiety osi."""
        count, ticks = self.count, self.scale.ticks
        step = period_label_step(count, self.width - STATS_LEFT_AXIS_WIDTH)
        points = [
            fch.LineChartDataPoint(x, v, point=fch.ChartCirclePoint(color=ACCENT, radius=3), show_tooltip=False)
            for x, v in self.points
        ]
        grid_step = ticks[1] - ticks[0] if len(ticks) > 1 else 1
        blank = ft.Container(width=1, height=1)  # pusta etykieta: oś zachowuje rezerwę miejsca, ale nic nie rysuje
        left = (
            [fch.ChartAxisLabel(value=t, label=ft.Text(fmt_stat_number(t), size=STATS_CHART_LABEL_SIZE, color=ft.Colors.WHITE, max_lines=1)) for t in ticks]
            if y_labels
            else [fch.ChartAxisLabel(value=ticks[0], label=blank)]
        )
        bottom = (
            [fch.ChartAxisLabel(value=i, label=vertical_label(self.axis_labels[i], self._is_selected_slot(i))) for i in range(0, count, step)]
            if x_labels
            else [fch.ChartAxisLabel(value=0, label=blank)]
        )
        return fch.LineChart(
            data_series=[fch.LineChartData(points=points, color=ACCENT, stroke_width=2, curved=False)] if data and points else [],
            min_x=-0.5,
            max_x=count - 0.5,
            min_y=self.scale.lower,
            max_y=self.scale.upper,
            interactive=False,
            animation=None,
            tooltip=None,
            horizontal_grid_lines=fch.ChartGridLines(
                interval=grid_step,
                color=CHART_GRID_LINE_COLOR if grid else ft.Colors.TRANSPARENT,
                width=1 if grid else 0,
                dash_pattern=[4, 4],
            ),
            left_axis=fch.ChartAxis(labels=left, label_size=STATS_LEFT_AXIS_WIDTH, label_spacing=grid_step, show_min=True, show_max=True),
            bottom_axis=fch.ChartAxis(labels=bottom, label_size=CHART_BOTTOM_AXIS, label_spacing=step, show_min=False, show_max=False),
            top_axis=fch.ChartAxis(show_labels=False),
            right_axis=fch.ChartAxis(show_labels=False),
            height=STATS_CHART_HEIGHT,
            top=CHART_TOOLTIP_ROOM,
            **place,
        )

    def _make_layer(self) -> ft.Container:
        """Przesuwana zawartość: linia z punktami, etykiety osi X i zaznaczenie (osobny egzemplarz przy każdym wywołaniu)."""
        content = self._line_chart(data=True, grid=False, y_labels=False, x_labels=True, left=-STATS_LEFT_AXIS_WIDTH, width=self.width)
        return ft.Container(
            ft.Stack([content, *self._overlay(STATS_LEFT_AXIS_WIDTH)], clip_behavior=ft.ClipBehavior.NONE),
            width=self.plot_width,
            height=CHART_TOOLTIP_ROOM + STATS_CHART_HEIGHT,
            offset=ft.Offset(0, 0),
        )

    def _build(self) -> None:
        height = CHART_TOOLTIP_ROOM + STATS_CHART_HEIGHT
        if self.on_shift is None:
            chart = self._line_chart(data=True, grid=True, y_labels=True, x_labels=True, left=0, right=0)
            self.chart_host.content = ft.Stack([chart, *self._overlay()], height=height)
            return
        # oś Y i siatka stoją w tle; dane, etykiety osi X i zaznaczenie leżą w warstwie przesuwanej w obrębie obszaru wykresu
        background = self._line_chart(data=False, grid=True, y_labels=True, x_labels=False, left=0, right=0)
        plot_w = self.plot_width
        self.layer = self._make_layer()
        self.viewport = ft.Stack([self.layer], width=plot_w, height=height)
        clip = ft.Container(self.viewport, width=plot_w, height=height, clip_behavior=ft.ClipBehavior.HARD_EDGE, left=STATS_LEFT_AXIS_WIDTH, top=0)
        self.chart_host.content = ft.Stack([background, clip], height=height)


class TrainBeastApp:
    def __init__(self, page: ft.Page, service: TrainingService):
        self.page = page
        self.service = service
        self.selected = date.today()
        self.workout_id: int | None = None
        self.set_fields: dict[int, list[ft.TextField]] = {}
        self.set_groups: dict[int, list[tuple[str, list[ft.TextField]]]] = {}
        self.expanded: set[int] = set()  # karty w trybie edycji (tylko UI)
        self.snapshot: WorkoutSnapshot | None = None  # skopiowany trening (tylko w pamięci)
        self.tab = "workout"
        self.stats_exercise = None  # wybrane ćwiczenie w zakładce Statystyki (tylko UI)
        self.stats_interval = "month"
        self.stats_period_start: date | None = None  # początek wyświetlanego okresu (None = bieżący); wspólny dla trzech wykresów
        self._period_busy = False  # trwa animacja zmiany okresu: kolejne gesty ignorowane
        self.count_shift = 0  # przesunięcie okna wykresu liczby treningów względem bieżącego okresu (tylko UI)
        self.count_deselected: set[str] = set()  # odznaczone sekcje filtra (do końca sesji; nowe sekcje są zaznaczone)
        self._info_texts: dict[str, ft.Text] = {}
        self._reset_swipe()

        page.title = "TrainBeast"
        page.padding = 0
        page.bgcolor = BLACK
        if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
            page.window.width = 390  # tylko podgląd na komputerze
            page.window.height = 844
        self.workout_host = ft.Container(expand=True)
        self.stats_host = ft.Container(expand=True, bgcolor=BLACK, visible=False)
        self._stats_built = False
        self._tab_labels: dict[str, ft.Text] = {}
        page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    [self.workout_host, self.stats_host, self._tab_bar()],
                    expand=True,
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            )
        )
        self.render()

    # --- infrastruktura ---
    def _show(self, header: list[ft.Control], swipe_top: list[ft.Control], panel: ft.Control, gesture: bool = True) -> None:
        """header: część nad paskiem dni (poza obszarem gestu); swipe_top + panel: obszar gestu od paska dni do dołu."""
        body = ft.Column(
            [*swipe_top, panel],
            expand=True,
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        if gesture:
            body = ft.GestureDetector(
                body,
                expand=True,
                drag_interval=10,
                on_horizontal_drag_start=self._on_drag_start,
                on_horizontal_drag_update=self._on_drag_update,
                on_horizontal_drag_end=self._on_drag_end,
                on_horizontal_drag_cancel=self._on_drag_cancel,
            )
        self.workout_host.content = ft.Container(
            padding=SCREEN_MARGIN,
            expand=True,
            content=ft.Column(
                [
                    ft.Container(
                        bgcolor=BLACK,
                        content=ft.Column(
                            list(header),
                            spacing=12,
                            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        ),
                    ),
                    body,
                ],
                expand=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )
        self.page.update()

    def _toast(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    def _dialog(self, title: str, content: ft.Control | None, actions: list[ft.Control], **kwargs) -> None:
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(title), content=content, actions=actions, **kwargs))

    # --- zakładki ---
    def _tab_bar(self) -> ft.Control:
        def tab(key: str, title: str) -> ft.Control:
            label = self._tab_labels[key] = ft.Text(
                title,
                size=16,
                color=ft.Colors.WHITE,
                weight=ft.FontWeight.BOLD if key == self.tab else ft.FontWeight.NORMAL,
            )
            return ft.Container(
                label,
                expand=1,
                height=TAB_BAR_HEIGHT,
                alignment=ft.Alignment.CENTER,
                on_click=lambda e, k=key: self._switch_tab(k),
            )

        return ft.Container(
            ft.Row([tab("workout", "Workout"), tab("stats", "Statystyki")], spacing=0),
            bgcolor=BTN_FILL,  # to samo wypełnienie co „Podsumowanie ćwiczenia”
            height=TAB_BAR_HEIGHT,
        )

    def _switch_tab(self, key: str) -> None:
        """Przełącza zakładki przez ukrywanie i pokazywanie (stan obu widoków zostaje)."""
        if key == "stats" and not self._stats_built:
            self._build_stats_view()
        self.tab = key
        self.workout_host.visible = key == "workout"
        self.stats_host.visible = key == "stats"
        for k, label in self._tab_labels.items():
            label.weight = ft.FontWeight.BOLD if k == key else ft.FontWeight.NORMAL
        if key == "stats":
            self.stats_period_start = None
            self.count_shift = 0
            self._refresh_stats(update=False)
        self.page.update()

    def _open_calendar_from_stats(self, e=None) -> None:
        self._switch_tab("workout")
        self._open_calendar()

    # --- statystyki ---
    def _build_stats_view(self) -> None:
        self._stats_built = True
        self.stats_exercise_text = ft.Text(
            "Wybierz ćwiczenie",
            size=16,
            color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        exercise_box = ft.Container(
            self.stats_exercise_text,
            height=NAME_ROW_HEIGHT,
            expand=True,
            padding=ft.Padding.symmetric(horizontal=12),
            alignment=ft.Alignment.CENTER_LEFT,
            bgcolor=FILL_DARK,
            border=ft.Border.all(1, ACCENT),
            border_radius=CARD_RADIUS,
            on_click=lambda e: self._open_exercise_picker(self._pick_stats_exercise, editable=False),
        )
        self.stats_interval_text = ft.Text(INTERVAL_LABELS[self.stats_interval], size=14, max_lines=1)
        interval_box = ft.Container(
            ft.PopupMenuButton(
                content=ft.Container(
                    ft.Row(
                        [self.stats_interval_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18, color=ACCENT)],
                        spacing=0,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    width=INTERVAL_WIDTH - 2,
                    height=NAME_ROW_HEIGHT - 2,
                    alignment=ft.Alignment.CENTER,
                ),
                items=self._menu_items(list(INTERVAL_LABELS.values()), self._choose_interval),
                bgcolor=FILL_DARK,
                shape=ft.RoundedRectangleBorder(side=ft.BorderSide(1, ACCENT), radius=CARD_RADIUS),
                padding=0,
            ),
            width=INTERVAL_WIDTH,
            height=NAME_ROW_HEIGHT,
            bgcolor=FILL_DARK,
            border=ft.Border.all(1, ACCENT),
            border_radius=CARD_RADIUS,
        )
        # okno przesuwania okresów: bieżący blok wykresów leży w układzie, nadjeżdżający jest dokładany nad nim (zob. _change_period)
        self.period_slider = ft.Stack([], clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.count_slider = ft.Stack([], clip_behavior=ft.ClipBehavior.HARD_EDGE)
        self.stats_charts = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )
        self.stats_host.content = ft.Container(
            padding=SCREEN_MARGIN,
            expand=True,
            content=ft.Column(
                [
                    ft.Column(
                        self._header_controls(self._open_calendar_from_stats, owner="stats"),
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    ft.Row([exercise_box, interval_box], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    self.stats_charts,
                ],
                expand=True,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

    def _pick_stats_exercise(self, exercise_id: int) -> None:
        self.stats_exercise = next((x for x in self.service.list_exercises() if x.id == exercise_id), None)
        self.page.pop_dialog()
        self._refresh_stats()

    def _choose_interval(self, label: str) -> None:
        self.stats_interval = next(k for k, v in INTERVAL_LABELS.items() if v == label)
        self.stats_period_start = None  # zmiana interwału wraca do bieżącego tygodnia / miesiąca
        self.count_shift = 0
        self._refresh_stats()

    def _refresh_stats(self, update: bool = True) -> None:
        """Pobiera dane na nowo i przebudowuje wykresy (przy wejściu w zakładkę i przy zmianie ćwiczenia lub interwału)."""
        today = date.today()
        self._info_texts["stats"].value = self._last_workout_info()
        exercise = self.stats_exercise
        self.stats_exercise_text.value = exercise.name if exercise else "Wybierz ćwiczenie"
        self.stats_exercise_text.color = None if exercise else ft.Colors.ON_SURFACE_VARIANT
        self.stats_interval_text.value = INTERVAL_LABELS[self.stats_interval]
        cards: list[ft.Control] = []
        if exercise is not None:
            if self.stats_period_start is None:
                self.stats_period_start = period_range(today, self.stats_interval)[0]
            self.period_slider.controls = [self._period_pane(self._period_column(exercise, today, self.stats_period_start))]
            cards.append(self._swipe_gesture(self.period_slider, self._change_period, lambda: self._period_busy))
        self.count_shift = count_window(today, self.stats_interval, self.count_shift, *self._count_bounds()).shift
        self.count_slider.controls = [self._count_column(today, self.count_shift).control]
        cards.append(self.count_slider)
        cards.append(ft.Container(height=TAB_SPACER))
        self.stats_charts.controls = cards
        if update:
            self.page.update()

    @staticmethod
    def _period_pane(content: ft.Control) -> ft.Container:
        return ft.Container(content, offset=ft.Offset(0, 0))

    def _period_column(self, exercise, today: date, start: date) -> ft.Control:
        """Trzy wykresy okresu zaczynającego się w `start`, każdy z własnym polem statystyk pod spodem."""
        interval = self.stats_interval
        daily = self.service.get_exercise_daily_stats(exercise)
        series = period_series(daily, start, interval, today)
        titles = stat_titles(exercise.load_type, exercise.effort_type)
        cards = exercise_stat_cards(exercise.load_type, exercise.effort_type, daily, start, interval, today)
        first, last = period_range(start, interval)
        count = (last - first).days + 1
        label = period_label(start, interval)
        page_width = self.page.width or 390
        icons = [
            (ft.Icons.FITNESS_CENTER, ft.Icons.EMOJI_EVENTS),
            (ft.Icons.FITNESS_CENTER, ft.Icons.EMOJI_EVENTS),
            (ft.Icons.REPEAT if exercise.effort_type == "reps" else ft.Icons.TIMER, ft.Icons.EMOJI_EVENTS),
        ]
        days = [first + timedelta(days=n) for n in range(count)]
        axis_labels = [f"{d.day:02d}.{d.month:02d}" for d in days]
        tip_titles = [fmt_chart_date(day) for day, _ in series]
        charts = []
        for index, (title, unit) in enumerate(zip(titles[:3], titles[3:])):
            points = [((day - first).days, stats[index]) for day, stats in series]
            charts.append(
                PeriodChart(
                    title,
                    ft.Text(label, size=13, color=ft.Colors.with_opacity(0.7, ft.Colors.WHITE)),
                    points,
                    tip_titles,
                    axis_labels,
                    lambda value, unit=unit: f"{fmt_stat_number(value)} {unit}",
                    nice_axis_scale(v for _, v in points),
                    self._stat_card(cards[index], icons[index]),
                    page_width,
                ).control
            )
        return ft.Column(charts, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    @staticmethod
    def _stat_card(card: StatCard, icons: tuple[str, str]) -> ft.Control:
        """Osobne pole pod wykresem: dwie kolumny (ikona, etykieta, wartość, zmiana procentowa, „vs. …”) rozdzielone linią."""

        def column(icon, col: StatColumn) -> ft.Control:
            change: list[ft.Control] = []
            pct = col.pct
            if pct:
                change.append(ft.Icon(ft.Icons.ARROW_UPWARD if pct > 0 else ft.Icons.ARROW_DOWNWARD, size=14, color=UP_COLOR if pct > 0 else DOWN_COLOR))
            color = UP_COLOR if pct and pct > 0 else DOWN_COLOR if pct else ft.Colors.WHITE
            change.append(ft.Text(fmt_percent(pct), size=12, color=color))
            return ft.Column(
                [
                    ft.Row(
                        [ft.Icon(icon, size=18, color=ACCENT), ft.Text(col.label, size=12, color=ft.Colors.WHITE, expand=True)],
                        spacing=6,
                        height=STAT_LABEL_HEIGHT,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Text(col.display or f"{fmt_stat_number(col.value)} {col.unit}", size=20, weight=ft.FontWeight.BOLD, color=ACCENT, max_lines=1),
                    ft.Row(change, spacing=2),
                    ft.Text(col.compare, size=10, color=ft.Colors.WHITE),
                ],
                spacing=2,
                expand=True,
            )

        return ft.Container(
            ft.Row(
                [
                    column(icons[0], card.left),
                    ft.Container(width=1, height=STATS_DIVIDER_HEIGHT, bgcolor=CHART_GRID_COLOR),
                    column(icons[1], card.right),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=12,
            bgcolor=STAT_CARD_BG,
            border=ft.Border.all(1, CHART_GRID_COLOR),
            border_radius=CARD_RADIUS,
        )

    def _swipe_gesture(self, content: ft.Control, change, busy) -> ft.GestureDetector:
        """Poziome przeciągnięcie `content` -> `change(-1)` (w prawo, wcześniej) lub `change(1)` (w lewo, później);
        kierunek rozpoznaje interpret_swipe, pionowe przewijanie zakładki nie jest przechwytywane; w trakcie animacji
        (`busy()`) gesty są ignorowane."""
        drag: list[float] = []  # [x startu, ostatni x]

        def start(e: ft.DragStartEvent) -> None:
            drag[:] = [e.global_position.x, e.global_position.x]

        def update(e: ft.DragUpdateEvent) -> None:
            if drag:
                drag[1] = e.global_position.x

        async def end(e: ft.DragEndEvent) -> None:
            moved, drag[:] = list(drag), []
            if not moved or busy():
                return
            direction = interpret_swipe(moved[1] - moved[0])
            if direction:
                await change(direction)

        return ft.GestureDetector(
            content,
            drag_interval=10,
            on_horizontal_drag_start=start,
            on_horizontal_drag_update=update,
            on_horizontal_drag_end=end,
        )

    async def _slide(self, stack: ft.Stack, incoming: ft.Container, delta: int) -> bool:
        """Animacja przesuwania w `stack` (ta sama co zmiana dnia w „Workout”: czas, krzywa i kierunek): `incoming`
        nadjeżdża z przeciwnej strony (delta = -1 z lewej), dotychczasowy blok wyjeżdża. True = animacja zakończona
        i `incoming` jest jedynym blokiem (widok mógł w międzyczasie zostać przebudowany)."""
        incoming.left = incoming.right = incoming.top = 0
        incoming.offset = ft.Offset(delta, 0)
        current = stack.controls[0]
        stack.controls.append(incoming)
        stack.update()
        await asyncio.sleep(0.03)
        width = (self.page.width or 390) - 2 * SCREEN_MARGIN
        duration = settle_duration(0.0, delta, width)
        began = time.perf_counter()
        while True:
            t = min(1.0, (time.perf_counter() - began) / duration)
            progress = delta * ease_out_cubic(t)  # jak _apply_progress: panel o kroku s leży w s - progress
            current.offset = ft.Offset(-progress, 0)
            incoming.offset = ft.Offset(delta - progress, 0)
            stack.update()
            if t >= 1.0:
                break
            await asyncio.sleep(0.012)
        if incoming not in stack.controls:
            return False
        incoming.left = incoming.right = incoming.top = None
        incoming.offset = ft.Offset(0, 0)
        stack.controls = [incoming]
        stack.update()
        return True

    async def _change_period(self, delta: int) -> None:
        """Przesuwa okres o `delta`; animowany jest cały blok trzech wykresów i pól statystyk, reszta ekranu stoi."""
        today = date.today()
        new = navigate_period(self.stats_period_start, self.stats_interval, delta, today, self.service.get_first_workout_date())
        if new == self.stats_period_start or self.stats_exercise is None or self._period_busy:
            return  # granica lub trwa animacja: nic się nie dzieje
        self._period_busy = True
        try:
            # nowy blok jest budowany przed startem animacji, żeby ciężka praca nie przerywała klatek
            incoming = self._period_pane(self._period_column(self.stats_exercise, today, new))
            if await self._slide(self.period_slider, incoming, delta):
                self.stats_period_start = new
        finally:
            self._period_busy = False

    # --- wykres liczby treningów ---
    def _count_bounds(self) -> tuple[date | None, date | None]:
        """(pierwszy trening, najnowszy wykonany trening) - granice okna wykresu liczby treningów."""
        return self.service.get_first_workout_date(), self.service.get_last_done_workout_date()

    async def _change_count(self, chart: PeriodChart, periods: int) -> None:
        """Po puszczeniu palca przesuwa okno o `periods` okresów (ze znakiem), co najwyżej do granicy; animowana jest
        tylko zawartość wykresu. Poniżej progu lub na granicy zawartość wraca na miejsce."""
        today = date.today()
        window = count_window(today, self.stats_interval, self.count_shift, *self._count_bounds())
        step = limit_swipe_periods(periods, window.shift, window.min_shift, window.max_shift)
        if step == 0:
            await chart.snap_back()
            return
        incoming = self._count_column(today, window.shift + step)
        await chart.slide_in(incoming, 1 if step > 0 else -1)
        if chart.control in self.count_slider.controls:  # widok mógł w międzyczasie zostać przebudowany
            self.count_shift = window.shift + step
            self.count_slider.controls = [incoming.control]
            self.count_slider.update()

    def _count_column(self, today: date, shift: int) -> PeriodChart:
        """Wykres liczby treningów okna przesuniętego o `shift` (jego `control` zawiera też pole statystyk pod spodem)."""
        interval = self.stats_interval
        first, last_done = self._count_bounds()
        window = count_window(today, interval, shift, first, last_done)
        sections = [c.name for c in self.service.get_categories() if c.name not in self.count_deselected]
        days = self.service.get_workout_days(sections)
        counts = count_by_period(days, window.starts, interval)
        labels = [count_period_label(start, interval) for start in window.starts]
        top, ticks = y_axis_ticks(max(counts, default=0), integer=True)
        total, average = workouts_total_and_average(days, today, interval, first)
        cmp = compare_windows(days, window.end, interval, first)
        month = interval == "month"
        vs = "vs. poprzednie 12 miesięcy" if month else "vs. poprzednie 12 tygodni"
        card = StatCard(
            StatColumn("Treningi od początku", total, "", cmp.total_pct, vs, str(total)),
            StatColumn("Średnia na miesiąc" if month else "Średnia na tydzień", average, "", cmp.average_pct, vs, fmt_average(average)),
        )
        filter_button = ft.IconButton(
            icon=ft.Icons.FILTER_LIST,
            icon_size=20,
            icon_color=ACCENT,
            width=32,
            height=32,
            style=ft.ButtonStyle(padding=0),
            on_click=self._open_count_filter,
        )
        return PeriodChart(
            "Ilość treningów w miesiącu" if month else "Ilość treningów w tygodniu",
            filter_button,
            list(enumerate(counts)),
            labels,
            labels,
            fmt_workouts,
            AxisScale(0, top, ticks),
            self._stat_card(card, (ft.Icons.FITNESS_CENTER, ft.Icons.EMOJI_EVENTS)),
            self.page.width or 390,
            highlight_label=True,
            on_shift=self._change_count,
        )

    def _rebuild_count(self) -> None:
        self.count_slider.controls = [self._count_column(date.today(), self.count_shift).control]
        self.count_slider.update()

    def _open_count_filter(self, e=None) -> None:
        """Lista wszystkich sekcji z polami wyboru; zmiana od razu odświeża wykres (lista zostaje otwarta)."""

        def toggle(name: str, checked: bool) -> None:
            if checked:
                self.count_deselected.discard(name)
            else:
                self.count_deselected.add(name)
            self._rebuild_count()

        rows: list[ft.Control] = []
        for category in self.service.get_categories():
            if rows:
                rows.append(ft.Container(height=1, bgcolor=ACCENT))
            rows.append(
                ft.Checkbox(
                    label=category.name,
                    value=category.name not in self.count_deselected,
                    active_color=ACCENT,
                    check_color=BLACK,
                    on_change=lambda ev, n=category.name: toggle(n, bool(ev.control.value)),
                )
            )
        # wysokość wynika z zawartości; dopiero gdy lista przekracza FILTER_MAX_HEIGHT ekranu, przewija się w oknie
        # (przycisk „Zamknij” jest w actions, więc zostaje widoczny)
        screen_h = self.page.height or 800
        estimated = sum(1 if isinstance(r, ft.Container) else FILTER_ROW_HEIGHT for r in rows)
        limit = FILTER_MAX_HEIGHT * screen_h
        self.page.show_dialog(
            ft.AlertDialog(
                content=ft.Container(
                    ft.Column(rows, scroll=ft.ScrollMode.AUTO if estimated > limit else None, spacing=0, tight=True),
                    width=min(320, (self.page.width or 390) - 80),
                    height=limit if estimated > limit else None,
                ),
                actions=[ft.TextButton("Zamknij", style=cancel_style(), on_click=lambda e: self.page.pop_dialog())],
                bgcolor=FILL_DARK,
                shape=ft.RoundedRectangleBorder(side=ft.BorderSide(1, ACCENT), radius=CARD_RADIUS),
                content_padding=ft.Padding.symmetric(horizontal=16, vertical=8),
                inset_padding=ft.Padding.symmetric(horizontal=12, vertical=24),
            )
        )

    # --- główny widok ---
    def _header_controls(self, on_calendar, owner: str = "workout") -> list[ft.Control]:
        """Wspólny nagłówek ekranu głównego i kalendarza: napis z hasłem oraz „Ostatni trening”, „Donate” i ikona kalendarza."""
        self.info_text = self._info_texts[owner] = ft.Text(self._last_workout_info(), size=16, expand=True)
        return [
            ft.Row(
                [
                    ft.Text(
                        spans=[
                            ft.TextSpan("Train", ft.TextStyle(color=ft.Colors.WHITE)),
                            ft.TextSpan("Beast", ft.TextStyle(color=ACCENT)),
                        ],
                        size=32,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding.only(left=HEADER_ICON_OFFSET),
                        content=ft.Image(src="no_excuses.png", width=96, fit=ft.BoxFit.CONTAIN),
                    ),
                ],
                spacing=4,
                height=HEADER_BTN_HEIGHT,  # dawniej wysokość wynikała z „Donate"; stała wysokość zachowuje położenie napisów
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    self.info_text,
                    ft.Button(
                        "Donate",
                        width=DONATE_WIDTH,
                        height=HEADER_BTN_HEIGHT,
                        style=header_btn_style(padding=ft.Padding.symmetric(horizontal=4)),
                        on_click=lambda e: None,  # na razie nieaktywny; bez handlera Flet wyszarza przycisk
                    ),
                    ft.IconButton(
                        ft.Icons.CALENDAR_MONTH,
                        icon_size=32,
                        icon_color=ACCENT,
                        style=header_btn_style(),
                        tooltip="Kalendarz",
                        on_click=on_calendar,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]

    def render(self) -> None:
        self.set_fields = {}
        self.set_groups = {}
        controls = self._header_controls(self._open_calendar)
        swipe_top: list[ft.Control] = [self._day_bar()]
        if self.selected != date.today():
            swipe_top.append(ft.TextButton("Wróć do dzisiaj", height=LINK_HEIGHT, style=ft.ButtonStyle(color=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=12)), on_click=lambda e: self._select(date.today())))
        self._show(controls, swipe_top, self._build_panels())

    def _last_workout_info(self) -> str:
        last = self.service.get_last_workout()
        if last is None:
            return "Brak zapisanych treningów"
        return (
            f"Ostatni trening: {fmt_date(last.workout_date)} – {workout_title(last)}, "
            f"{len(last.exercises)} ćwicz., {done_sets_count(last)} serii"
        )

    def _refresh_info(self) -> None:
        self.info_text = self._info_texts.get("workout", self.info_text)
        self.info_text.value = self._last_workout_info()
        self.info_text.update()

    # --- pasek dni ---
    def _select(self, day: date) -> None:
        self.selected = day
        self.expanded.clear()
        self.render()

    def _day_bar(self) -> ft.Control:
        today = date.today()  # przy każdym przerysowaniu, nie przy starcie
        self._reset_swipe()
        self._tabs = {}

        def tab(offset: int) -> ft.Container:
            day = self.selected + timedelta(days=offset)
            is_today = day == today
            label = "Dzisiaj" if is_today else fmt_short(day)
            abbr = ft.Text(weekday_abbr(day), size=DAY_ABBR_SIZE, text_align=ft.TextAlign.CENTER, max_lines=1)
            number = ft.Text(label, size=13, text_align=ft.TextAlign.CENTER, max_lines=1)
            container = ft.Container(
                ft.Column(
                    [abbr, number],
                    spacing=0,
                    tight=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                height=DAY_TAB_HEIGHT,
                top=0,
                border_radius=12,
                on_click=lambda e, d=day: self._select(d),
            )
            self._tabs[offset] = (container, abbr, number, is_today)
            return container

        def arrow(icon, delta: int) -> ft.Container:
            return ft.Container(
                ft.Icon(icon, color=ACCENT),
                alignment=ft.Alignment.CENTER,
                width=28,
                height=DAY_TAB_HEIGHT,
                on_click=lambda e: self._select(self.selected + timedelta(days=delta)),
            )

        # nieruchoma ramka (zewnętrzny kontener, strzałki) + okno z przycinaniem; przesuwa się tylko taśma dni w oknie
        self._tape_width = (self.page.width or 390) - 2 * SCREEN_MARGIN - 2 - 16 - 2 * 28 - 2 * 2
        self._tape = ft.Stack([tab(o) for o in range(-3, 4)], height=DAY_TAB_HEIGHT)
        window = ft.Container(
            self._tape,
            expand=True,
            height=DAY_TAB_HEIGHT,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            on_size_change=self._on_tape_size,
        )
        self._layout_tape(0.0)
        return ft.Container(
            ft.Row([arrow(ft.Icons.CHEVRON_LEFT, -1), window, arrow(ft.Icons.CHEVRON_RIGHT, 1)], spacing=2),
            bgcolor=FILL_DARK,
            border=ft.Border.all(1, ACCENT),
            border_radius=DAY_BAR_RADIUS,
            padding=ft.Padding.symmetric(horizontal=8, vertical=DAY_BAR_V_PAD),
        )

    def _on_tape_size(self, e) -> None:
        if abs(e.width - self._tape_width) > 0.5:
            self._tape_width = e.width
            self._layout_tape(self._progress)
            self.page.update()

    def _layout_tape(self, progress: float) -> None:
        """Ustawia położenie, szerokość i wyróżnienie każdego dnia taśmy dla danego postępu przesuwania."""
        for offset, left, width in day_tape_layout(progress, self._tape_width):
            container, abbr, number, is_today = self._tabs[offset]
            focus = max(0.0, 1 - abs(offset - progress))  # 1 = w pełni wybrany dzień, 0 = zwykły
            container.left = left + 1
            container.width = max(0.0, width - 2)
            container.bgcolor = ft.Colors.with_opacity(focus, ACCENT) if focus > 0 else None
            color = BLACK if focus > 0.5 else ft.Colors.WHITE if is_today else None
            abbr.color = number.color = color
            number.weight = ft.FontWeight.BOLD if focus > 0.5 or is_today else ft.FontWeight.NORMAL

    # --- przesuwanie dni gestem ---
    def _reset_swipe(self) -> None:
        self._progress = 0.0  # -1..1: ułamek szerokości zajęty przez sąsiada (>0: następny dzień nadjeżdża z prawej)
        self._drag_origin: tuple[float, float] | None = None  # (x palca, postęp) w chwili startu gestu
        self._anim_gen = getattr(self, "_anim_gen", 0) + 1  # unieważnia trwającą animację
        self._panels: dict[int, ft.Container] = {}  # -1 / 0 / 1 -> panel dnia
        self._panel_width = (self.page.width or 390) - 2 * SCREEN_MARGIN
        self._tabs: dict = {}
        self._tape_width = 0.0

    def _build_panels(self) -> ft.Control:
        self._panels = {0: self._make_panel(self._day_content())}
        self._panel_stack = ft.Stack([self._panels[0]])
        return ft.Container(
            self._panel_stack,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            on_size_change=self._on_panel_size,
        )

    @staticmethod
    def _make_panel(controls: list[ft.Control]) -> ft.Container:
        return ft.Container(
            ft.Column([*controls, ft.Container(height=TAB_SPACER)], scroll=ft.ScrollMode.AUTO, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=BLACK,  # tło: panel zasłania sąsiada i przyjmuje dotyk w pustych miejscach
            left=0,
            right=0,
            top=0,
            bottom=0,
            offset=ft.Offset(0, 0),
        )

    def _on_panel_size(self, e) -> None:
        if abs(e.width - self._panel_width) > 0.5:
            self._panel_width = e.width

    def _preview_panel(self, step: int) -> ft.Container:
        """Zawartość sąsiedniego dnia budowana bez naruszania stanu bieżącego widoku (cards_column, set_fields, ...)."""
        names = ("selected", "workout_id", "cards_column", "set_fields", "set_groups", "expanded")
        saved = {n: getattr(self, n, None) for n in names}
        try:
            self.selected = saved["selected"] + timedelta(days=step)
            self.expanded = set()
            self.set_fields, self.set_groups = {}, {}
            return self._make_panel(self._day_content())
        finally:
            for n, v in saved.items():
                setattr(self, n, v)

    def _ensure_neighbours(self) -> None:
        added = False
        for step in (-1, 1):
            if step not in self._panels:
                panel = self._preview_panel(step)
                panel.offset = ft.Offset(step - self._progress, 0)  # poza oknem do pierwszego ruchu
                self._panels[step] = panel
                self._panel_stack.controls.append(panel)
                added = True
        if added:
            self.page.update()

    def _apply_progress(self, progress: float) -> None:
        self._progress = progress
        for step, panel in self._panels.items():
            panel.offset = ft.Offset(step - progress, 0)
        self._layout_tape(progress)
        self.page.update()

    def _on_drag_start(self, e: ft.DragStartEvent) -> None:
        self._anim_gen += 1  # przejmuje trwającą animację: kontynuacja od bieżącej pozycji
        self._drag_origin = (e.global_position.x, self._progress)
        self._ensure_neighbours()

    def _on_drag_update(self, e: ft.DragUpdateEvent) -> None:
        if self._drag_origin is None:
            return
        x0, base = self._drag_origin
        self._apply_progress(drag_progress(e.global_position.x - x0, self._panel_width, base))

    async def _on_drag_end(self, e: ft.DragEndEvent) -> None:
        if self._drag_origin is None:
            return
        self._drag_origin = None
        await self._settle(e.primary_velocity or 0.0)

    async def _on_drag_cancel(self, e) -> None:
        if self._drag_origin is None:
            return
        self._drag_origin = None
        await self._settle(0.0)

    async def _settle(self, velocity: float) -> None:
        """Dokańcza ruch do 0 / ±1 wg reguły 25%; tę samą klatkę dostają widok treningu i taśma dni."""
        self._anim_gen += 1
        gen = self._anim_gen
        start, target = self._progress, settle_target(self._progress)
        duration = settle_duration(start, target, self._panel_width, velocity)
        began = time.perf_counter()
        while True:
            t = min(1.0, (time.perf_counter() - began) / duration)
            if gen != self._anim_gen:
                return  # nowy gest przejął animację
            eased = ease_out_cubic(t)
            self._apply_progress(start + (target - start) * eased)
            if t >= 1.0:
                break
            await asyncio.sleep(0.012)
        if gen != self._anim_gen:
            return
        if target:
            self._select(self.selected + timedelta(days=target))

    # --- kalendarz ---
    def _open_calendar(self, e=None) -> None:
        """Widok kalendarza: wspólny nagłówek + pionowa, leniwa lista miesięcy (bieżący miesiąc lub miesiąc wybranego dnia)."""
        today = date.today()
        months = month_range(today)
        first = date(*months[0], 1)
        end_year, end_month = shift_month(*months[-1], 1)
        marked = self.service.get_workout_dates_between(first, date(end_year, end_month, 1))  # jedno zapytanie
        grids = [month_grid(y, m) for y, m in months]
        heights = [CAL_MONTH_FIXED + len(g) * CAL_ROW_HEIGHT for g in grids]

        def day_cell(day: date | None) -> ft.Control:
            if day is None:
                return ft.Container(expand=1, height=CAL_ROW_HEIGHT)
            kind = classify_day(day, today, marked)
            return ft.Container(
                ft.Text(
                    str(day.day),
                    size=20,
                    weight=ft.FontWeight.W_500,
                    color=BLACK if kind in ("today", "workout") else CAL_SUN if kind == "sunday" else CAL_SAT if day.weekday() == 5 else ft.Colors.WHITE,
                ),
                expand=1,
                height=CAL_ROW_HEIGHT,
                alignment=ft.Alignment.CENTER,
                bgcolor=CAL_TODAY_BG if kind == "today" else CAL_WORKOUT_BG if kind == "workout" else None,
                on_click=lambda e, d=day: self._select(d),
            )

        def month_item(i: int) -> ft.Control:
            year, month = months[i]
            return ft.Container(
                ft.Column(
                    [
                        ft.Container(
                            ft.Text(
                                f"{MONTH_NAMES_GENITIVE[month - 1]} {year}",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                                max_lines=1,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            height=CAL_TITLE_HEIGHT,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Row(
                            [
                                ft.Container(
                                    ft.Text(n, size=13, weight=ft.FontWeight.BOLD, color=day_color(k)),
                                    expand=1,
                                    height=CAL_WEEKDAY_HEIGHT,
                                    alignment=ft.Alignment.CENTER,
                                )
                                for k, n in enumerate(WEEKDAY_ABBR)
                            ],
                            spacing=0,
                        ),
                        *[ft.Row([day_cell(d) for d in week], spacing=0) for week in grids[i]],
                    ],
                    spacing=0,
                ),
                height=heights[i],
                padding=ft.Padding.only(top=CAL_MONTH_GAP),
            )

        # miesiąc wybranego dnia (jak dawny kalendarz); poza zakresem: najbliższy brzeg listy
        current = (self.selected.year, self.selected.month)
        target = months.index(current) if current in months else 0 if self.selected < first else len(months) - 1
        month_list = ft.ListView(
            [month_item(i) for i in range(len(months))],
            expand=True,
            build_controls_on_demand=True,
            padding=ft.Padding.only(bottom=TAB_SPACER),
        )
        self._show(self._header_controls(self._close_calendar), [], month_list, gesture=False)
        self.page.run_task(self._scroll_calendar, month_list, sum(heights[:target]))

    async def _scroll_calendar(self, month_list: ft.ListView, offset: float) -> None:
        await month_list.scroll_to(offset=offset, duration=0)

    def _close_calendar(self, e=None) -> None:
        self.render()

    # --- zawartość wybranego dnia ---
    def _day_content(self) -> list[ft.Control]:
        workout = self.service.get_workout_by_date(self.selected)
        if workout is None:
            self.workout_id = None
            return [
                ft.Text("Brak treningu w tym dniu", size=18, text_align=ft.TextAlign.CENTER),
                ft.Row(
                    [
                        big_button("Dodaj trening", self._add_workout, outlined=True, expand=1),
                        big_button("Wklej trening", self._paste_workout, outlined=True, expand=1),
                    ],
                    spacing=8,
                ),
            ]
        self.workout_id = workout.id
        # Flet nie wymusza wysokości ramki TextField (rysuje ją wg treści), więc ramkę i tło daje Container
        # o wysokości NAME_ROW_HEIGHT - tej samej co „Kopiuj"; wewnątrz pole bez ramki, wyśrodkowane pionowo.
        name_field = ft.TextField(
            hint_text="Nazwa treningu (opcjonalnie)",
            value=workout.name,
            border=ft.InputBorder.NONE,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=0),
            dense=True,  # bez sztywnej height: ta wypychała tekst poza dolną krawędź; wysokość i tak daje Container
            on_change=lambda e: self.service.rename_workout(workout.id, e.control.value),
        )
        name_box = ft.Container(
            name_field,
            height=NAME_ROW_HEIGHT,
            expand=True,
            alignment=ft.Alignment.CENTER_LEFT,
            bgcolor=FILL_DARK,
            border=ft.Border.all(1, ACCENT),
            border_radius=CARD_RADIUS,
        )
        copy_button = ft.Container(  # Container zamiast przycisku Flet: ten ma minimalną wysokość i nie da się go zrównać z polem
            ft.Text("Kopiuj", color=ft.Colors.WHITE),
            height=NAME_ROW_HEIGHT,
            padding=ft.Padding.symmetric(horizontal=13),  # 12 + dawna grubość ramki (1): szerokość bez zmian
            alignment=ft.Alignment.CENTER,
            bgcolor=ACCENT_DARK,
            border_radius=CARD_RADIUS,
            ink=True,
            on_click=self._copy_workout,
        )
        self.cards_column = ft.Column(spacing=12)
        for we in workout.exercises:
            self.cards_column.controls.append(self._exercise_card(we))

        return [
            ft.Row(
                [
                    name_box,
                    copy_button,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            self.cards_column,
            ft.Row(
                [
                    big_button("Usuń trening", self._confirm_delete_workout, primary=False, expand=1, style=delete_style()),
                    big_button("+ Dodaj ćwiczenie", self._open_add_exercise, primary=False, expand=1, style=add_exercise_style()),
                ],
                spacing=8,
            ),
        ]

    def _add_workout(self, e=None) -> None:
        try:
            self.service.create_workout(self.selected)
        except ValidationError as err:
            self._toast(str(err))
        self.render()

    def _copy_workout(self, e=None) -> None:
        snapshot = self.service.snapshot_workout(self.workout_id)
        if snapshot is None:
            return
        self.snapshot = snapshot
        self._toast("Trening skopiowany")

    def _paste_workout(self, e=None) -> None:
        if not has_snapshot_to_paste(self.snapshot):
            self._toast("Brak skopiowanych treningów")
            return
        self.service.paste_snapshot(self.snapshot, self.selected)
        self.render()

    def _confirm_delete_workout(self, e=None) -> None:
        def do_delete(e):
            self.page.pop_dialog()
            self.service.delete_workout(self.workout_id)
            self.render()

        self._dialog(
            "Usunąć trening?",
            ft.Text(f"Cały trening z dnia {fmt_date(self.selected)} zostanie usunięty."),
            [
                ft.TextButton("Anuluj", style=cancel_style(), on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton("Usuń", style=cancel_style(), on_click=do_delete),
            ],
        )

    def _exercise_card(self, we) -> ft.Container:
        card = ft.Container(padding=12, bgcolor=FILL_DARK, border=ft.Border.all(1, ACCENT), border_radius=CARD_RADIUS)
        card.data = we.id
        self._fill_card(card, we)
        return card

    def _fill_card(self, card: ft.Container, we) -> None:
        if we.id in self.expanded:
            card.content = self._edit_content(we)
            card.padding = 8
            card.on_click = None
        else:
            card.content = self._collapsed_content(we)
            card.padding = 12
            card.on_click = lambda e, we_id=we.id: self._set_editing(we_id, True)

    def _set_editing(self, we_id: int, editing: bool) -> None:
        if editing:
            self.expanded.add(we_id)
        else:
            self.expanded.discard(we_id)
        self._refresh_card(we_id)

    def _edit_content(self, we) -> ft.Control:
        rows: list[ft.Control] = [
            ft.Container(
                ft.Text(we.exercise.name, size=EXERCISE_NAME_SIZE, weight=ft.FontWeight.BOLD),
                on_click=lambda e, we=we: self._finish_exercise(we),
            ),
        ]
        for i, st in enumerate(we.sets, start=1):
            rows.append(self._set_row(we.id, we.exercise, i, st))
        rows.append(ft.Container(height=EDIT_BTN_GAP))
        rows.append(
            ft.Row(
                [
                    ft.IconButton(
                        ft.Icons.DELETE,
                        tooltip="Usuń ćwiczenie",
                        icon_size=30,
                        on_click=lambda e, we_id=we.id, name=we.exercise.name: self._confirm_remove_exercise(we_id, name),
                    ),
                    ft.Button(
                        "+ Dodaj serię",
                        height=LIST_BTN_HEIGHT,
                        expand=1,
                        on_click=lambda e, we_id=we.id: self._add_set(we_id),
                    ),
                    ft.FilledButton(
                        "Zakończ",
                        height=EDIT_BTN_HEIGHT,
                        expand=1,
                        style=ft.ButtonStyle(bgcolor=ACTION_BLUE, shape=ft.RoundedRectangleBorder(radius=EDIT_BTN_HEIGHT / 2)),
                        on_click=lambda e, we=we: self._finish_exercise(we),
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return ft.Column(rows, spacing=4)

    def _collapsed_content(self, we) -> ft.Control:
        rows: list[ft.Control] = [ft.Text(we.exercise.name, size=EXERCISE_NAME_SIZE, weight=ft.FontWeight.BOLD)]
        for i, st in enumerate(we.sets, start=1):
            rows.append(
                ft.Row(
                    [
                        ft.Container(
                            done_icon(st.done),
                            padding=ft.Padding.all(DONE_ICON_PAD),
                            on_click=lambda e, we_id=we.id, sid=st.id, value=not st.done: self._toggle_done_card(we_id, sid, value),
                        ),
                        ft.Text(
                            fmt_set_line(we.exercise, st, i),
                            size=15,
                            weight=ft.FontWeight.W_500 if st.done else ft.FontWeight.NORMAL,
                            opacity=1 if st.done else 0.5,
                        ),
                    ],
                    spacing=2,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        rows.append(
            ft.Button(
                content=ft.Row(
                    [
                        ft.Text("Podsumowanie ćwiczenia", color=ft.Colors.WHITE, expand=True, text_align=ft.TextAlign.CENTER),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, color=ACCENT),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                style=outline_style(),
                height=44,
                on_click=lambda e, we_id=we.id: self._open_summary(we_id),
            )
        )
        return ft.Column(rows, spacing=6, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _finish_exercise(self, we) -> None:
        for st in we.sets:  # blur może się nie wykonać: puste pola -> 0 i zapis
            for kind, group in self.set_groups.get(st.id, []):
                self._fill_empty(kind, group)
                self._save_group(st.id, kind, group)
        if any(self._has_error(f) for st in we.sets for f in self.set_fields.get(st.id, [])):
            self._toast("Popraw błędne pola przed zakończeniem ćwiczenia.")
            return
        self._set_editing(we.id, False)

    def _open_summary(self, we_id: int) -> None:
        we = self._get_we(we_id)
        if we is None:
            return
        groups = summarize_exercise(we.exercise, we.sets)
        self._dialog(
            "Podsumowanie ćwiczenia",
            ft.Column(
                [ft.Text(we.exercise.name, size=EXERCISE_NAME_SIZE, weight=ft.FontWeight.BOLD), *self._summary_controls(groups)],
                tight=True,
                spacing=6,
            ),
            [ft.TextButton("Zamknij", style=cancel_style(), on_click=lambda e: self.page.pop_dialog())],
        )

    @staticmethod
    def _summary_controls(groups: list[SummaryGroup]) -> list[ft.Control]:
        if not groups:
            return [
                ft.Text(EMPTY_SUMMARY, size=16),
                ft.Text(
                    "Czy na pewno oznaczyłeś serie jako wykonane? "
                    "Naciśnij „wyk” przy każdej serii na karcie ćwiczenia.",
                    size=12,
                    opacity=0.6,
                ),
            ]
        controls: list[ft.Control] = []
        for group in groups:
            if group.heading:  # kilka jednostek: nagłówek z jednostką nad wynikami grupy
                controls.append(ft.Text(group.heading, size=14, weight=ft.FontWeight.BOLD, color=ACCENT))
            controls.extend(ft.Text(line, size=16) for line in group.lines)
        return controls

    # --- wiersz serii ---
    @staticmethod
    def _has_error(field: ft.TextField) -> bool:
        return field.border_color == ft.Colors.ERROR

    def _num_field(self, value: str, *, weight: bool = False) -> ft.TextField:
        return ft.TextField(
            # bez input_filter: filtr Fleta/Fluttera blokuje skasowanie ostatniego znaku; znaki pilnuje field.data
            data=is_valid_weight_input if weight else is_valid_digits_input,
            value=value,
            keyboard_type=ft.KeyboardType.NUMBER,
            height=SET_FIELD_HEIGHT,
            text_size=16,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(horizontal=6, vertical=SET_FIELD_V_GAP),
        )

    @staticmethod
    def _boxed(content: ft.Control, label: ft.Control, *, expand: int | None = None, width: int | None = None) -> ft.Control:
        """Kontrolka z etykietą na górnej krawędzi ramki (etykieta ma tło karty, więc „przecina" ramkę)."""
        return ft.Container(
            ft.Stack([ft.Container(content, padding=ft.Padding.only(top=LABEL_OVERHANG)), label]),
            expand=expand,
            width=width,
            height=SET_ROW_HEIGHT,
        )

    @staticmethod
    def _plain_label(text: str) -> ft.Control:
        return ft.Container(
            ft.Text(text, size=SET_LABEL_SIZE, color=ft.Colors.ON_SURFACE_VARIANT),
            bgcolor=FILL_DARK,
            padding=ft.Padding.symmetric(horizontal=3),
            left=8,
            top=0,
        )

    @staticmethod
    def _unit_menu_items(measure: str, choose) -> list[ft.PopupMenuItem]:
        return TrainBeastApp._menu_items(allowed_units(measure), choose)

    @staticmethod
    def _menu_items(options, choose) -> list[ft.PopupMenuItem]:
        """Pozycje listy rozdzielone żółtymi liniami (bez linii nad pierwszą i pod ostatnią)."""
        items: list[ft.PopupMenuItem] = []
        for u in options:
            if items:
                items.append(
                    ft.PopupMenuItem(content=ft.Container(height=1, width=UNIT_MENU_WIDTH, bgcolor=ACCENT), height=1, padding=0)
                )
            items.append(ft.PopupMenuItem(content=ft.Text(u), on_click=lambda e, u=u: choose(u)))
        return items

    def _unit_label(self, set_id: int, measure: str, unit: str) -> ft.Control:
        """Klikalna etykieta jednostki z niebieskim daszkiem; lista zmienia tylko jednostkę serii (bez przeliczania)."""
        text = ft.Text(unit, size=SET_LABEL_SIZE, color=ft.Colors.ON_SURFACE_VARIANT)

        def choose(choice: str) -> None:
            try:
                self.service.set_set_unit(set_id, measure, choice)
            except ValidationError as err:
                self._toast(str(err))
                return
            text.value = choice
            text.update()

        return ft.PopupMenuButton(
            content=ft.Container(
                ft.Row([text, ft.Icon(ft.Icons.ARROW_DROP_UP, size=14, color=ACTION_BLUE)], spacing=0, tight=True),
                bgcolor=FILL_DARK,
                padding=ft.Padding.symmetric(horizontal=3),
            ),
            items=self._unit_menu_items(measure, choose),
            bgcolor=FILL_DARK,
            shape=ft.RoundedRectangleBorder(side=ft.BorderSide(1, ACCENT), radius=CARD_RADIUS),
            padding=0,
            left=8,
            top=0,
        )

    def _done_button(self, set_id: int, done: bool) -> ft.Control:
        """Okrągłe „wyk": ten sam wskaźnik co w widoku nieedytowalnym (żółte kółko z ptaszkiem / puste kółko)."""
        state = {"done": done}
        button = ft.Container(
            done_icon(done),
            width=SET_FIELD_HEIGHT,
            height=SET_FIELD_HEIGHT,
            alignment=ft.Alignment.CENTER,
        )

        def toggle(e) -> None:
            state["done"] = not state["done"]
            button.content = done_icon(state["done"])
            button.update()
            self._toggle_done(set_id, state["done"])

        button.on_click = toggle
        return self._boxed(button, self._plain_label("wyk"), width=SET_FIELD_HEIGHT)

    def _set_row(self, we_id: int, exercise, number: int, st) -> ft.Control:
        first_kind = exercise.load_type
        if first_kind == "weight":
            first = [self._num_field(fmt_decimal(st.weight_kg), weight=True)]
            first_boxed = [self._boxed(first[0], self._unit_label(st.id, "weight", set_unit_of(st, "weight")), expand=1)]
        elif first_kind in ("reps", "floors"):
            first = [self._num_field(str(st.reps or 0))]
            first_boxed = [self._boxed(first[0], self._plain_label("powt" if first_kind == "reps" else "pięt"), expand=1)]
        else:
            km, m = divmod(st.distance_m or 0, 1000)
            first = [self._num_field(str(km)), self._num_field(str(m))]
            first_boxed = [
                self._boxed(first[0], self._unit_label(st.id, "distance", set_unit_of(st, "distance")), expand=1),
                self._boxed(first[1], self._unit_label(st.id, "distance_minor", set_unit_of(st, "distance_minor")), expand=1),
            ]
        if exercise.effort_type == "reps":
            second_kind = "reps"
            second = [self._num_field(str(st.reps or 0))]
            second_boxed = [self._boxed(second[0], self._plain_label("powt"), expand=1)]
        else:
            second_kind = "time"
            h, rest = divmod(st.duration_s or 0, 3600)
            mi, s = divmod(rest, 60)
            second = [self._num_field(str(h)), self._num_field(str(mi)), self._num_field(str(s))]
            second_boxed = [
                self._boxed(f, self._plain_label(name), expand=1) for f, name in zip(second, ("h", "min", "s"))
            ]
        self.set_fields[st.id] = first + second
        self.set_groups[st.id] = [(first_kind, first), (second_kind, second)]

        if second_kind == "time":  # minuty i sekundy: 1-2 cyfry, do 59
            second[1].data = second[2].data = is_valid_minsec_input
        if first_kind == "distance":  # metry: 0-999
            first[1].data = is_valid_distance_input

        for kind, group in ((first_kind, first), (second_kind, second)):
            for f in group:
                f.on_change = self._guarded_change(f, lambda e, sid=st.id, k=kind, g=group: self._save_group(sid, k, g))
                f.on_blur = f.on_submit = lambda e, k=kind, g=group: self._on_blur(k, g)

        def side(content: ft.Control, width: int) -> ft.Control:  # numer i X: wyrównane do środka pola, nie etykiety
            return ft.Container(
                content,
                width=width,
                height=SET_ROW_HEIGHT,
                padding=ft.Padding.only(top=LABEL_OVERHANG),
                alignment=ft.Alignment.CENTER,
            )

        number_text = side(ft.Text(f"{number}.", size=16, weight=ft.FontWeight.BOLD), 28)
        remove_btn = side(
            ft.IconButton(
                ft.Icons.CLOSE,
                tooltip="Usuń serię",
                icon_size=20,
                style=ft.ButtonStyle(padding=0),
                width=40,
                height=SET_FIELD_HEIGHT,
                on_click=lambda e, sid=st.id: self._remove_set(we_id, sid),
            ),
            40,
        )
        done = self._done_button(st.id, st.done)

        def line(fields: list[ft.Control], first_line: bool) -> ft.Row:
            items = [number_text, *fields, done, remove_btn] if first_line else fields
            return ft.Row(items, spacing=4, vertical_alignment=ft.CrossAxisAlignment.START)

        if len(first) == 1 and len(second) == 1:
            quantities = [line(first_boxed + second_boxed, True)]
        else:
            quantities = [line(first_boxed, True), line(second_boxed, False)]
        return ft.Column(quantities, spacing=0)

    @staticmethod
    def _guarded_change(field: ft.TextField, handler):
        """Niedozwolona wartość (field.data to walidator) jest cofana do poprzedniej, bez komunikatu."""
        last = [field.value]

        def on_change(e):
            validator = field.data
            if validator is not None and not validator(field.value):
                field.value = last[0]
                field.update()
                return
            last[0] = field.value
            handler(e)

        on_change.last = last
        return on_change

    @staticmethod
    def _parse_group(kind: str, fields: list[ft.TextField]) -> dict:
        values = [normalize_empty_input(f.value, allow_separator=kind == "weight") for f in fields]
        if kind == "weight":
            return {"weight_kg": parse_weight(values[0])}
        if kind == "reps":
            return {"reps": parse_reps(values[0])}
        if kind == "floors":
            return {"reps": parse_floors(values[0])}
        if kind == "distance":
            return {"distance_m": parse_distance(*values)}
        return {"duration_s": parse_duration(*values)}

    def _save_group(self, set_id: int, kind: str, fields: list[ft.TextField]) -> None:
        """Zapis po każdej zmianie; błędna wartość nie jest zapisywana (zostaje poprzednia)."""
        was_error = any(self._has_error(f) for f in fields)
        try:
            self.service.update_set(set_id, **self._parse_group(kind, fields))
            message = None
        except ValidationError as err:
            message = str(err)
        for f in fields:  # bez odświeżania pola w trakcie pisania, gdy nic się nie zmieniło
            color = ft.Colors.ERROR if message else None
            if f.border_color != color:
                f.border_color = color
                f.update()
        if message and not was_error:
            self._toast(f"{message} Zapisano poprzednią wartość.")

    @staticmethod
    def _fill_empty(kind: str, fields: list[ft.TextField]) -> None:
        """Puste pole (lub sam separator w ciężarze) dostaje wyświetlone 0."""
        for f in fields:
            filled = normalize_empty_input(f.value, allow_separator=kind == "weight")
            if filled != f.value:
                f.value = filled
                f.on_change.last[0] = filled
                f.update()

    def _on_blur(self, kind: str, fields: list[ft.TextField]) -> None:
        self._fill_empty(kind, fields)
        if len(fields) > 1:
            self._normalize(kind, fields)

    def _normalize(self, kind: str, fields: list[ft.TextField]) -> None:
        """Po opuszczeniu pola: 90 s -> 1 min 30 s, 1500 m -> 1 km 500 m."""
        try:
            parsed = self._parse_group(kind, fields)
        except ValidationError:
            return
        if kind == "distance":
            parts = divmod(parsed["distance_m"], 1000)
        else:
            h, rest = divmod(parsed["duration_s"], 3600)
            parts = (h, *divmod(rest, 60))
        for f, v in zip(fields, parts):
            if f.value != str(v):
                f.value = str(v)
                f.on_change.last[0] = f.value
                f.update()

    def _toggle_done(self, set_id: int, value: bool) -> None:
        for kind, group in self.set_groups.get(set_id, []):  # blur może się nie wykonać przy kliknięciu kółka
            self._fill_empty(kind, group)
            self._save_group(set_id, kind, group)
        self.service.update_set(set_id, done=value)
        self._refresh_info()

    def _toggle_done_card(self, we_id: int, set_id: int, value: bool) -> None:
        self.service.update_set(set_id, done=value)
        self._refresh_card(we_id)
        self._refresh_info()

    def _get_we(self, we_id: int):
        workout = self.service.get_workout(self.workout_id)
        return next((x for x in workout.exercises if x.id == we_id), None)

    def _refresh_card(self, we_id: int) -> None:
        we = self._get_we(we_id)
        for card in self.cards_column.controls:
            if card.data == we_id and we is not None:
                self._fill_card(card, we)
                card.update()

    def _add_set(self, we_id: int) -> None:
        self.service.add_set(we_id)
        self._refresh_card(we_id)

    def _remove_set(self, we_id: int, set_id: int) -> None:
        self.service.remove_set(set_id)
        self.set_fields.pop(set_id, None)
        self._refresh_card(we_id)
        self._refresh_info()

    def _confirm_remove_exercise(self, we_id: int, name: str) -> None:
        def do_remove(e):
            self.page.pop_dialog()
            self.service.remove_exercise_from_workout(we_id)
            self.render()

        self._dialog(
            "Usunąć ćwiczenie?",
            ft.Text(f"„{name}” wraz ze wszystkimi seriami zostanie usunięte z treningu."),
            [
                ft.TextButton("Anuluj", style=cancel_style(), on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton("Usuń", style=cancel_style(), on_click=do_remove),
            ],
        )

    def _open_add_exercise(self, e=None) -> None:
        self._open_exercise_picker(self._add_exercise_to_workout, editable=True)

    def _add_exercise_to_workout(self, exercise_id: int) -> None:
        try:
            we = self.service.add_exercise_to_workout(self.workout_id, exercise_id)
        except ValidationError as err:
            self._toast(str(err))
            return
        self.expanded.add(we.id)  # nowe ćwiczenie od razu w trybie edycji
        self.page.pop_dialog()
        self.render()

    def _open_exercise_picker(self, on_pick, editable: bool) -> None:
        """Lista ćwiczeń wspólna dla treningu i statystyk; editable=False ukrywa „Dodaj własne” i „Dodaj sekcję”."""
        expanded: set[str] = set()  # rozwinięte kategorie/sekcje (tylko UI, domyślnie wszystkie zwinięte)
        width = min(400, (self.page.width or 390) - 48)
        items = ft.Column(scroll=ft.ScrollMode.AUTO, width=width, spacing=8)

        def toggle(name: str):
            expanded.symmetric_difference_update({name})
            refresh()

        def category_controls(name: str) -> list[ft.Control]:
            opened = name in expanded
            controls: list[ft.Control] = [
                ft.Container(
                    ft.Row(
                        [
                            ft.Text(name, size=16, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Icon(ft.Icons.EXPAND_LESS if opened else ft.Icons.EXPAND_MORE),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    bgcolor=FILL_DARK,
                    border=ft.Border.all(1, ft.Colors.OUTLINE),
                    border_radius=12,
                    on_click=lambda e, n=name: toggle(n),
                )
            ]
            if opened:
                for ex in self.service.get_exercises_by_category(name):
                    controls.append(
                        ft.Container(
                            ft.Text(ex.name, size=15),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            margin=ft.Margin.only(left=12),
                            bgcolor=FILL_DARK,
                            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=8,
                            on_click=lambda e, exid=ex.id: on_pick(exid),
                        )
                    )
                buttons = [ft.Button("Zwiń listę", height=LIST_BTN_HEIGHT, expand=1, style=delete_style(), on_click=lambda e, n=name: toggle(n))]
                if editable:
                    buttons.insert(0, own_button("Dodaj własne", lambda e, n=name: self._open_create_exercise(n, on_created=refresh), expand=1))
                controls.append(ft.Row(buttons, spacing=8))
            return controls

        def fill():
            items.controls = []
            for category in self.service.get_categories():
                items.controls.extend(category_controls(category.name))
            if editable:
                items.controls.append(ft.Divider())
                items.controls.append(
                    own_button("Dodaj sekcję", lambda e: self._open_add_section(on_created=refresh))
                )

        def refresh():
            fill()
            items.update()

        fill()
        self._dialog(
            "Dodaj ćwiczenie",
            items,
            [ft.TextButton("Anuluj", style=cancel_style(), on_click=lambda e: self.page.pop_dialog())],
            inset_padding=ft.Padding.symmetric(horizontal=12, vertical=24),
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        )

    def _open_add_section(self, on_created) -> None:
        name = ft.TextField(label="Nazwa sekcji", height=FIELD_HEIGHT)

        def create(e):
            try:
                self.service.add_category(name.value)
            except ValidationError as err:
                name.error = str(err)
                name.update()
                return
            self.page.pop_dialog()  # wraca do listy kategorii
            on_created()

        self._dialog(
            "Dodaj sekcję",
            ft.Column([name], tight=True, width=300),
            [
                ft.TextButton("Anuluj", style=cancel_style(), on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Dodaj", height=BTN_HEIGHT, style=add_exercise_style(), on_click=create),
            ],
        )

    def _open_create_exercise(self, category: str, on_created) -> None:
        name = ft.TextField(label="Nazwa ćwiczenia", height=FIELD_HEIGHT)
        load = ft.Dropdown(
            label="Pierwsza miara",
            value="weight",
            options=[
                ft.DropdownOption(key="weight", text="Ciężar"),
                ft.DropdownOption(key="distance", text="Dystans"),
                ft.DropdownOption(key="reps", text="Powtórzenia"),
                ft.DropdownOption(key="floors", text="Piętra"),
            ],
        )
        effort = ft.SegmentedButton(
            selected=["reps"],
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.SELECTED: ACCENT_DARK},
                color=ft.Colors.WHITE,
            ),
            segments=[ft.Segment("reps", label=ft.Text("Powtórzenia")), ft.Segment("time", label=ft.Text("Czas"))],
        )

        def create(e):
            try:
                self.service.create_exercise(name.value, category, load.value, effort.selected[0])
            except ValidationError as err:
                name.error = str(err)
                name.update()
                return
            self.page.pop_dialog()  # wraca do listy wyboru ćwiczeń
            on_created()

        self._dialog(
            "Własne ćwiczenie",
            ft.Column([name, load, effort], tight=True, spacing=12, width=300),
            [
                ft.TextButton("Anuluj", style=cancel_style(), on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Dodaj", height=BTN_HEIGHT, style=add_exercise_style(), on_click=create),
            ],
        )

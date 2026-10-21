import asyncio
import time
from datetime import date, timedelta

import flet as ft

from .services import (
    EMPTY_SUMMARY,
    MONTH_NAMES,
    WEEKDAY_ABBR,
    TrainingService,
    ValidationError,
    SummaryGroup,
    WorkoutSnapshot,
    allowed_units,
    done_sets_count,
    has_snapshot_to_paste,
    fmt_decimal,
    fmt_set_line,
    day_tape_layout,
    drag_progress,
    is_calendar_today,
    is_valid_digits_input,
    is_valid_distance_input,
    is_valid_minsec_input,
    is_valid_weight_input,
    month_grid,
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
    summarize_exercise,
    weekday_abbr,
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
    """„Dodaj własne” i „Dodaj sekcję”: wspólny wygląd w oknie wyboru ćwiczenia."""
    return ft.FilledButton(text, height=BTN_HEIGHT - 8, on_click=on_click, **kwargs)


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
        self._reset_swipe()

        page.title = "TrainBeast"
        page.padding = 0
        page.bgcolor = BLACK
        if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
            page.window.width = 390  # tylko podgląd na komputerze
            page.window.height = 844
        self.render()

    # --- infrastruktura ---
    def _show(self, header: list[ft.Control], swipe_top: list[ft.Control], panel: ft.Control) -> None:
        """header: część nad paskiem dni (poza obszarem gestu); swipe_top + panel: obszar gestu od paska dni do dołu."""
        self.page.controls.clear()
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
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
                            ft.GestureDetector(
                                ft.Column(
                                    [*swipe_top, panel],
                                    expand=True,
                                    spacing=12,
                                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                ),
                                expand=True,
                                drag_interval=10,
                                on_horizontal_drag_start=self._on_drag_start,
                                on_horizontal_drag_update=self._on_drag_update,
                                on_horizontal_drag_end=self._on_drag_end,
                                on_horizontal_drag_cancel=self._on_drag_cancel,
                            ),
                        ],
                        expand=True,
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                ),
            )
        )
        self.page.update()

    def _toast(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    def _dialog(self, title: str, content: ft.Control | None, actions: list[ft.Control], **kwargs) -> None:
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(title), content=content, actions=actions, **kwargs))

    # --- główny widok ---
    def render(self) -> None:
        self.set_fields = {}
        self.set_groups = {}
        self.info_text = ft.Text(self._last_workout_info(), size=16, expand=True)
        controls: list[ft.Control] = [
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
                        on_click=self._open_calendar,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]
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
            ft.Column(list(controls), scroll=ft.ScrollMode.AUTO, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
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
        """Dokańcza ruch do 0 / ±1 wg reguły 50%; tę samą klatkę dostają widok treningu i taśma dni."""
        self._anim_gen += 1
        gen = self._anim_gen
        start, target = self._progress, settle_target(self._progress)
        duration = settle_duration(start, target, self._panel_width, velocity)
        began = time.perf_counter()
        while True:
            t = min(1.0, (time.perf_counter() - began) / duration)
            if gen != self._anim_gen:
                return  # nowy gest przejął animację
            eased = 1 - (1 - t) ** 3
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
        state = {"year": self.selected.year, "month": self.selected.month}
        holder = ft.Container(
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, CAL_TEXT),
            padding=ft.Padding.symmetric(horizontal=8, vertical=10),
            width=min(380, (self.page.width or 390) - 24),
            border_radius=10,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        def pick(day: date) -> None:
            self.page.pop_dialog()
            self._select(day)

        def move(delta: int) -> None:
            state["year"], state["month"] = shift_month(state["year"], state["month"], delta)
            holder.content = build()
            holder.update()

        def build() -> ft.Control:
            year, month = state["year"], state["month"]
            marked = self.service.get_workout_dates(year, month)  # z bazy przy każdym otwarciu/zmianie miesiąca
            line = ft.BorderSide(1, ft.Colors.GREY_400)
            today = date.today()

            def cell(content: ft.Control, **kwargs) -> ft.Container:
                return ft.Container(content, expand=1, alignment=ft.Alignment.CENTER, **kwargs)

            header = ft.Row(
                [
                    ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=CAL_TEXT, on_click=lambda e: move(-1)),
                    ft.Text(
                        spans=[
                            ft.TextSpan(MONTH_NAMES[month - 1], ft.TextStyle(color=CAL_TEXT, weight=ft.FontWeight.BOLD)),
                            ft.TextSpan(f" {year}", ft.TextStyle(color=ft.Colors.GREY_600)),
                        ],
                        size=20,
                        max_lines=1,
                        text_align=ft.TextAlign.CENTER,
                        expand=True,
                    ),
                    ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=CAL_TEXT, on_click=lambda e: move(1)),
                ],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            names = ft.Container(
                ft.Row(
                    [
                        cell(ft.Text(n, size=13, weight=ft.FontWeight.BOLD, color=day_color(i)), height=32)
                        for i, n in enumerate(WEEKDAY_ABBR)
                    ],
                    spacing=0,
                ),
                border=ft.Border(top=line, bottom=line),
            )
            rows: list[ft.Control] = [header, names]
            for week in month_grid(year, month):
                cells = []
                for day in week.days:
                    if day.month != month:
                        cells.append(cell(ft.Text(str(day.day), size=22, color=ft.Colors.GREY_300), height=56))
                        continue
                    has_workout = day in marked
                    is_today = is_calendar_today(day, month, today)
                    cells.append(
                        cell(
                            ft.Text(
                                str(day.day),
                                size=22,
                                weight=ft.FontWeight.W_500,
                                color=BLACK if has_workout or is_today else day_color(day.weekday()),
                            ),
                            height=56,
                            bgcolor=CAL_TODAY_BG if is_today else CAL_WORKOUT_BG if has_workout else None,
                            on_click=lambda e, d=day: pick(d),
                        )
                    )
                rows.append(ft.Container(ft.Row(cells, spacing=0), border=ft.Border(bottom=line)))
            return swipeable(ft.Column(rows, spacing=0, tight=True), move)

        holder.content = build()
        self.page.show_dialog(
            ft.AlertDialog(
                content=holder,
                bgcolor=ft.Colors.TRANSPARENT,
                elevation=0,
                content_padding=0,
                inset_padding=ft.Padding.symmetric(horizontal=12, vertical=24),
                shape=ft.RoundedRectangleBorder(radius=10),
            )
        )

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
                ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton("Usuń", on_click=do_delete),
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
            [ft.TextButton("Zamknij", on_click=lambda e: self.page.pop_dialog())],
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
                controls.append(ft.Text(group.heading, size=14, weight=ft.FontWeight.BOLD, color=ACTION_BLUE))
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
        """Pozycje listy jednostek rozdzielone żółtymi liniami (bez linii nad pierwszą i pod ostatnią)."""
        items: list[ft.PopupMenuItem] = []
        for u in allowed_units(measure):
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
                ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton("Usuń", on_click=do_remove),
            ],
        )

    def _open_add_exercise(self, e=None) -> None:
        expanded: set[str] = set()  # rozwinięte kategorie/sekcje (tylko UI, domyślnie wszystkie zwinięte)
        width = min(400, (self.page.width or 390) - 48)
        items = ft.Column(scroll=ft.ScrollMode.AUTO, width=width, spacing=8)

        def add(exercise_id: int):
            try:
                we = self.service.add_exercise_to_workout(self.workout_id, exercise_id)
            except ValidationError as err:
                self._toast(str(err))
                return
            self.expanded.add(we.id)  # nowe ćwiczenie od razu w trybie edycji
            self.page.pop_dialog()
            self.render()

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
                            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=8,
                            on_click=lambda e, exid=ex.id: add(exid),
                        )
                    )
                controls.append(
                    ft.Row(
                        [
                            own_button(
                                "Dodaj własne",
                                lambda e, n=name: self._open_create_exercise(n, on_created=refresh),
                                expand=1,
                            ),
                            ft.Button("Zwiń listę", height=LIST_BTN_HEIGHT, expand=1, on_click=lambda e, n=name: toggle(n)),
                        ],
                        spacing=8,
                    )
                )
            return controls

        def fill():
            items.controls = []
            for category in self.service.get_categories():
                items.controls.extend(category_controls(category.name))
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
            [ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog())],
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
                ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Dodaj", height=BTN_HEIGHT, on_click=create),
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
                ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Dodaj", height=BTN_HEIGHT, on_click=create),
            ],
        )

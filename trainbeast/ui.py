from datetime import date, timedelta

import flet as ft

from .services import (
    DIGIT_CHAR_PATTERN,
    EMPTY_SUMMARY,
    MONTH_NAMES,
    SUMMARY_SEP,
    WEEKDAY_ABBR,
    WEIGHT_CHAR_PATTERN,
    TrainingService,
    ValidationError,
    done_sets_count,
    fmt_decimal,
    fmt_set_line,
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
    shift_month,
    summarize_exercise,
)

BTN_HEIGHT = 60
FIELD_HEIGHT = 60
CAL_TEXT = "#222222"
CAL_SAT = ft.Colors.GREY_600
CAL_SUN = ft.Colors.RED_600
ACCENT = "#FCB808"  # żółty ramek (odczytany ze zrzutu inspiracji)
BLACK = "#000000"
CAL_WORKOUT_BG = "#FFE9A0"
CAL_TODAY_BG = ACCENT
OUTLINE_BTN_RADIUS = 22
CARD_RADIUS = 12
DAY_BAR_HEIGHT = 56
DAY_BAR_RADIUS = (DAY_BAR_HEIGHT + 2) / 2  # pigułka: połowa wysokości paska z ramką
BTN_FILL = ft.Colors.with_opacity(0.25, ACCENT)  # półprzezroczyste żółte wypełnienie przycisków


def day_color(weekday: int) -> str:
    """Kolor dnia tygodnia (0 = poniedziałek): sobota szara, niedziela czerwona."""
    return CAL_SAT if weekday == 5 else CAL_SUN if weekday == 6 else CAL_TEXT


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_short(d: date) -> str:
    return d.strftime("%d.%m")


def workout_title(w) -> str:
    return w.name or "Trening"


def outline_style() -> ft.ButtonStyle:
    """Przycisk z półprzezroczystym żółtym wypełnieniem, żółtą ramką i białym tekstem."""
    return ft.ButtonStyle(
        bgcolor=BTN_FILL,
        color=ft.Colors.WHITE,
        side=ft.BorderSide(1, ACCENT),
        shape=ft.RoundedRectangleBorder(radius=OUTLINE_BTN_RADIUS),
    )


def big_button(text: str, on_click, primary: bool = True, outlined: bool = False, **kwargs) -> ft.Control:
    cls = ft.FilledButton if primary else ft.Button
    if outlined:
        kwargs["style"] = outline_style()
    return cls(text, on_click=on_click, height=BTN_HEIGHT, expand=kwargs.pop("expand", None), **kwargs)


class TrainBeastApp:
    def __init__(self, page: ft.Page, service: TrainingService):
        self.page = page
        self.service = service
        self.selected = date.today()
        self.workout_id: int | None = None
        self.set_fields: dict[int, list[ft.TextField]] = {}
        self.set_groups: dict[int, list[tuple[str, list[ft.TextField]]]] = {}
        self.expanded: set[int] = set()  # karty w trybie edycji (tylko UI)

        page.title = "TrainBeast"
        page.padding = 0
        page.bgcolor = BLACK
        if page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX):
            page.window.width = 390  # tylko podgląd na komputerze
            page.window.height = 844
        self.render()

    # --- infrastruktura ---
    def _show(self, *controls: ft.Control) -> None:
        self.page.controls.clear()
        self.page.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    padding=8,
                    expand=True,
                    content=ft.Column(
                        list(controls),
                        scroll=ft.ScrollMode.AUTO,
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
        self.info_text = ft.Text(self._last_workout_info(), size=16, text_align=ft.TextAlign.CENTER)
        controls: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(
                        spans=[
                            ft.TextSpan("Train", ft.TextStyle(color=ft.Colors.WHITE)),
                            ft.TextSpan("Beast", ft.TextStyle(color=ACCENT)),
                        ],
                        size=36,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.IconButton(
                        ft.Icons.CALENDAR_MONTH,
                        icon_size=32,
                        icon_color=ACCENT,
                        bgcolor=BLACK,
                        style=ft.ButtonStyle(
                            side=ft.BorderSide(1, ACCENT),
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        tooltip="Kalendarz",
                        on_click=self._open_calendar,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            self.info_text,
            self._day_bar(),
        ]
        if self.selected != date.today():
            controls.append(ft.TextButton("Wróć do dzisiaj", on_click=lambda e: self._select(date.today())))
        controls.extend(self._day_content())
        self._show(*controls)

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

    def _day_bar(self) -> ft.Row:
        today = date.today()  # przy każdym przerysowaniu, nie przy starcie

        def tab(offset: int) -> ft.Container:
            day = self.selected + timedelta(days=offset)
            selected = offset == 0
            is_today = day == today
            label = "Dzisiaj" if is_today else fmt_short(day)
            return ft.Container(
                ft.Text(
                    label,
                    size=13,
                    weight=ft.FontWeight.BOLD if selected or is_today else ft.FontWeight.NORMAL,
                    color=BLACK if selected else ft.Colors.PRIMARY if is_today else None,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                ),
                alignment=ft.Alignment.CENTER,
                height=DAY_BAR_HEIGHT,
                expand=3 if selected else 2,
                border_radius=12,
                bgcolor=ACCENT if selected else None,
                on_click=lambda e, d=day: self._select(d),
            )

        def arrow(icon, delta: int) -> ft.Container:
            return ft.Container(
                ft.Icon(icon, color=ACCENT),
                alignment=ft.Alignment.CENTER,
                width=28,
                height=DAY_BAR_HEIGHT,
                on_click=lambda e: self._select(self.selected + timedelta(days=delta)),
            )

        return ft.Container(
            ft.Row(
                [arrow(ft.Icons.CHEVRON_LEFT, -1), *(tab(o) for o in (-2, -1, 0, 1, 2)), arrow(ft.Icons.CHEVRON_RIGHT, 1)],
                spacing=2,
            ),
            bgcolor=BLACK,
            border=ft.Border.all(1, ACCENT),
            border_radius=DAY_BAR_RADIUS,
            padding=ft.Padding.symmetric(horizontal=8),
        )

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
            return ft.Column(rows, spacing=0, tight=True)

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
                big_button("Dodaj trening", self._add_workout),
            ]
        self.workout_id = workout.id
        name_field = ft.TextField(
            label="Nazwa treningu (opcjonalnie)",
            value=workout.name,
            height=FIELD_HEIGHT,
            border_radius=CARD_RADIUS,
            bgcolor=BLACK,
            border_color=ACCENT,
            focused_border_color=ACCENT,
            on_change=lambda e: self.service.rename_workout(workout.id, e.control.value),
        )
        self.cards_column = ft.Column(spacing=12)
        for we in workout.exercises:
            self.cards_column.controls.append(self._exercise_card(we))

        return [
            name_field,
            self.cards_column,
            big_button("+ Dodaj ćwiczenie", self._open_add_exercise, primary=False, outlined=True),
            big_button("Usuń trening", self._confirm_delete_workout, primary=False, outlined=True),
        ]

    def _add_workout(self, e=None) -> None:
        try:
            self.service.create_workout(self.selected)
        except ValidationError as err:
            self._toast(str(err))
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
        card = ft.Container(padding=12, bgcolor=BLACK, border=ft.Border.all(1, ACCENT), border_radius=CARD_RADIUS)
        card.data = we.id
        self._fill_card(card, we)
        return card

    def _fill_card(self, card: ft.Container, we) -> None:
        if we.id in self.expanded:
            card.content = self._edit_content(we)
            card.on_click = None
        else:
            card.content = self._collapsed_content(we)
            card.on_click = lambda e, we_id=we.id: self._set_editing(we_id, True)

    def _set_editing(self, we_id: int, editing: bool) -> None:
        if editing:
            self.expanded.add(we_id)
        else:
            self.expanded.discard(we_id)
        self._refresh_card(we_id)

    def _edit_content(self, we) -> ft.Control:
        rows: list[ft.Control] = [
            ft.Row(
                [
                    ft.Text(we.exercise.name, size=20, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(
                        ft.Icons.DELETE,
                        tooltip="Usuń ćwiczenie",
                        icon_size=30,
                        on_click=lambda e, we_id=we.id, name=we.exercise.name: self._confirm_remove_exercise(we_id, name),
                    ),
                ]
            ),
        ]
        for i, st in enumerate(we.sets, start=1):
            rows.append(self._set_row(we.id, we.exercise, i, st))
        rows.append(
            ft.Row(
                [
                    big_button("+ Dodaj serię", lambda e, we_id=we.id: self._add_set(we_id), primary=False, expand=1),
                    big_button("Zakończ", lambda e, we=we: self._finish_exercise(we), expand=1),
                ],
                spacing=8,
            )
        )
        return ft.Column(rows, spacing=8)

    def _collapsed_content(self, we) -> ft.Control:
        rows: list[ft.Control] = [ft.Text(we.exercise.name, size=18, weight=ft.FontWeight.BOLD)]
        for i, st in enumerate(we.sets, start=1):
            rows.append(
                ft.Row(
                    [
                        ft.Container(
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if st.done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                size=22,
                                color=ACCENT if st.done else ft.Colors.OUTLINE,
                            ),
                            padding=ft.Padding.all(6),
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
        if any(self._has_error(f) for st in we.sets for f in self.set_fields.get(st.id, [])):
            self._toast("Popraw błędne pola przed zakończeniem ćwiczenia.")
            return
        self._set_editing(we.id, False)

    def _open_summary(self, we_id: int) -> None:
        we = self._get_we(we_id)
        if we is None:
            return
        lines = summarize_exercise(we.exercise, we.sets)
        self._dialog(
            "Podsumowanie ćwiczenia",
            ft.Column(
                [ft.Text(we.exercise.name, size=18, weight=ft.FontWeight.BOLD), *self._summary_controls(lines)],
                tight=True,
                spacing=6,
            ),
            [ft.TextButton("Zamknij", on_click=lambda e: self.page.pop_dialog())],
        )

    @staticmethod
    def _summary_controls(lines: list[str]) -> list[ft.Control]:
        if lines == [EMPTY_SUMMARY]:
            return [
                ft.Text(EMPTY_SUMMARY, size=16),
                ft.Text(
                    "Czy na pewno oznaczyłeś serie jako wykonane? "
                    "Zaznacz checkbox przy każdej serii na karcie ćwiczenia.",
                    size=12,
                    opacity=0.6,
                ),
            ]
        controls: list[ft.Control] = []
        for line in lines:
            if SUMMARY_SEP in line:  # wiersz grupy: dwa pola obok siebie, zawijane parami
                controls.append(
                    ft.Row([ft.Text(part, size=16) for part in line.split(SUMMARY_SEP)], wrap=True, spacing=16, run_spacing=2)
                )
            else:
                controls.append(ft.Text(line, size=16))
        return controls

    # --- wiersz serii ---
    @staticmethod
    def _has_error(field: ft.TextField) -> bool:
        return field.border_color == ft.Colors.ERROR

    def _num_field(
        self, value: str, *, label: str | None = None, suffix: str | None = None, expand: int = 1, weight: bool = False
    ) -> ft.TextField:
        return ft.TextField(
            input_filter=ft.InputFilter(regex_string=WEIGHT_CHAR_PATTERN if weight else DIGIT_CHAR_PATTERN, allow=True),
            data=is_valid_weight_input if weight else is_valid_digits_input,
            value=value,
            label=label,
            suffix=suffix,
            keyboard_type=ft.KeyboardType.NUMBER,
            height=FIELD_HEIGHT,
            expand=expand,
            text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(horizontal=6, vertical=8),
        )

    def _set_row(self, we_id: int, exercise, number: int, st) -> ft.Control:
        first_kind = exercise.load_type
        if first_kind == "weight":
            first = [self._num_field(fmt_decimal(st.weight_kg), suffix="kg", expand=2, weight=True)]
        elif first_kind == "reps":
            first = [self._num_field(str(st.reps or 0), suffix="powt.", expand=2)]
        elif first_kind == "floors":
            first = [self._num_field(str(st.reps or 0), suffix="pięt.", expand=2)]
        else:
            km, m = divmod(st.distance_m or 0, 1000)
            first = [self._num_field(str(km), label="km"), self._num_field(str(m), label="m")]
        if exercise.effort_type == "reps":
            second_kind = "reps"
            second = [self._num_field(str(st.reps or 0), suffix="powt.", expand=2)]
        else:
            second_kind = "time"
            h, rest = divmod(st.duration_s or 0, 3600)
            mi, s = divmod(rest, 60)
            second = [
                self._num_field(str(h), label="h"),
                self._num_field(str(mi), label="min"),
                self._num_field(str(s), label="s"),
            ]
        self.set_fields[st.id] = first + second
        self.set_groups[st.id] = [(first_kind, first), (second_kind, second)]

        if second_kind == "time":  # minuty i sekundy: 1-2 cyfry, do 59
            second[1].data = second[2].data = is_valid_minsec_input
        if first_kind == "distance":  # metry: 0-99
            first[1].data = is_valid_distance_input

        for kind, group in ((first_kind, first), (second_kind, second)):
            for f in group:
                f.on_change = self._guarded_change(f, lambda e, sid=st.id, k=kind, g=group: self._save_group(sid, k, g))
                f.on_blur = lambda e, k=kind, g=group: self._on_blur(k, g)

        done = ft.Checkbox(value=st.done, scale=1.4)
        done.on_change = lambda e, sid=st.id: self._toggle_done(sid, bool(done.value))

        header = ft.Row(
            [
                ft.Text(f"{number}.", size=18, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text("wykonana", size=12),
                done,
                ft.IconButton(
                    ft.Icons.CLOSE,
                    tooltip="Usuń serię",
                    on_click=lambda e, sid=st.id: self._remove_set(we_id, sid),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        if len(first) == 1 and len(second) == 1:
            quantities = [ft.Row(first + second)]
        else:
            quantities = [ft.Row(first), ft.Row(second)]
        return ft.Column([header, *quantities], spacing=4)

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
        for f in fields:
            f.border_color = ft.Colors.ERROR if message else None
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
                            ft.FilledButton(
                                "Dodaj własne",
                                height=BTN_HEIGHT - 8,
                                expand=1,
                                on_click=lambda e, n=name: self._open_create_exercise(n, on_created=refresh),
                            ),
                            ft.Button("Zwiń listę", height=BTN_HEIGHT - 8, expand=1, on_click=lambda e, n=name: toggle(n)),
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
                ft.Button("Dodaj sekcję", height=BTN_HEIGHT - 8, on_click=lambda e: self._open_add_section(on_created=refresh))
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

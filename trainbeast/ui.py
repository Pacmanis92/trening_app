from datetime import date, timedelta

import flet as ft

from .services import (
    EMPTY_SUMMARY,
    SUMMARY_SEP,
    TrainingService,
    ValidationError,
    done_sets_count,
    fmt_set_line,
    parse_distance,
    parse_duration,
    parse_reps,
    parse_weight,
    summarize_exercise,
)

BTN_HEIGHT = 60
FIELD_HEIGHT = 60


def fmt_number(value: float | None) -> str:
    return f"{value or 0:g}"


def fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def fmt_short(d: date) -> str:
    return d.strftime("%d.%m")


def workout_title(w) -> str:
    return w.name or "Trening"


def big_button(text: str, on_click, primary: bool = True, **kwargs) -> ft.Control:
    cls = ft.FilledButton if primary else ft.Button
    return cls(text, on_click=on_click, height=BTN_HEIGHT, expand=kwargs.pop("expand", None), **kwargs)


class TrainBeastApp:
    def __init__(self, page: ft.Page, service: TrainingService):
        self.page = page
        self.service = service
        self.selected = date.today()
        self.workout_id: int | None = None
        self.set_fields: dict[int, list[ft.TextField]] = {}
        self.expanded: set[int] = set()  # karty w trybie edycji (tylko UI)

        page.title = "TrainBeast"
        page.padding = 0
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

    def _dialog(self, title: str, content: ft.Control | None, actions: list[ft.Control]) -> None:
        self.page.show_dialog(ft.AlertDialog(title=ft.Text(title), content=content, actions=actions))

    # --- główny widok ---
    def render(self) -> None:
        self.set_fields = {}
        self.info_text = ft.Text(self._last_workout_info(), size=16, text_align=ft.TextAlign.CENTER)
        controls: list[ft.Control] = [
            ft.Row([ft.Text("TrainBeast", size=36, weight=ft.FontWeight.BOLD)], alignment=ft.MainAxisAlignment.CENTER),
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
                    color=ft.Colors.PRIMARY if is_today and not selected else None,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                ),
                alignment=ft.Alignment.CENTER,
                height=56,
                expand=3 if selected else 2,
                border_radius=12,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if selected else None,
                on_click=lambda e, d=day: self._select(d),
            )

        def arrow(icon, delta: int) -> ft.Container:
            return ft.Container(
                ft.Icon(icon),
                alignment=ft.Alignment.CENTER,
                width=28,
                height=56,
                on_click=lambda e: self._select(self.selected + timedelta(days=delta)),
            )

        return ft.Row(
            [arrow(ft.Icons.CHEVRON_LEFT, -1), *(tab(o) for o in (-2, -1, 0, 1, 2)), arrow(ft.Icons.CHEVRON_RIGHT, 1)],
            spacing=2,
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
            on_change=lambda e: self.service.rename_workout(workout.id, e.control.value),
        )
        self.cards_column = ft.Column(spacing=12)
        for we in workout.exercises:
            self.cards_column.controls.append(self._exercise_card(we))

        return [
            name_field,
            self.cards_column,
            big_button("+ Dodaj ćwiczenie", self._open_add_exercise, primary=False),
            big_button("Usuń trening", self._confirm_delete_workout, primary=False),
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
        card = ft.Container(padding=12, border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=12)
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
                                color=ft.Colors.PRIMARY if st.done else ft.Colors.OUTLINE,
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
                "Podsumowanie ćwiczenia",
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

    def _num_field(self, value: str, *, label: str | None = None, suffix: str | None = None, expand: int = 1) -> ft.TextField:
        return ft.TextField(
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
        if exercise.load_type == "weight":
            first_kind = "weight"
            first = [self._num_field(fmt_number(st.weight_kg), suffix="kg", expand=2)]
        else:
            first_kind = "distance"
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

        for kind, group in ((first_kind, first), (second_kind, second)):
            for f in group:
                f.on_change = lambda e, sid=st.id, k=kind, g=group: self._save_group(sid, k, g)
                if len(group) > 1:
                    f.on_blur = lambda e, k=kind, g=group: self._normalize(k, g)

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
    def _parse_group(kind: str, fields: list[ft.TextField]) -> dict:
        values = [f.value for f in fields]
        if kind == "weight":
            return {"weight_kg": parse_weight(values[0])}
        if kind == "reps":
            return {"reps": parse_reps(values[0])}
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
                f.update()

    def _toggle_done(self, set_id: int, value: bool) -> None:
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
        items = ft.Column(scroll=ft.ScrollMode.AUTO, width=400, spacing=8)

        def add(exercise_id: int):
            try:
                we = self.service.add_exercise_to_workout(self.workout_id, exercise_id)
            except ValidationError as err:
                self._toast(str(err))
                return
            self.expanded.add(we.id)  # nowe ćwiczenie od razu w trybie edycji
            self.page.pop_dialog()
            self.render()

        def fill():
            items.controls = [
                ft.Button(ex.name, height=BTN_HEIGHT - 8, on_click=lambda e, exid=ex.id: add(exid))
                for ex in self.service.list_exercises()
            ]
            items.controls.append(ft.Divider())
            items.controls.append(
                ft.FilledButton(
                    "Dodaj własne",
                    height=BTN_HEIGHT - 8,
                    on_click=lambda e: self._open_create_exercise(on_created=on_created),
                )
            )

        def on_created():
            fill()
            items.update()

        fill()
        self._dialog("Dodaj ćwiczenie", items, [ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog())])

    def _open_create_exercise(self, on_created) -> None:
        name = ft.TextField(label="Nazwa ćwiczenia", height=FIELD_HEIGHT)
        load = ft.SegmentedButton(
            selected=["weight"],
            segments=[ft.Segment("weight", label=ft.Text("Ciężar")), ft.Segment("distance", label=ft.Text("Dystans"))],
        )
        effort = ft.SegmentedButton(
            selected=["reps"],
            segments=[ft.Segment("reps", label=ft.Text("Powtórzenia")), ft.Segment("time", label=ft.Text("Czas"))],
        )

        def create(e):
            try:
                self.service.create_exercise(name.value, load.selected[0], effort.selected[0])
            except ValidationError as err:
                name.error = str(err)
                name.update()
                return
            self.page.pop_dialog()  # wraca do listy wyboru ćwiczeń
            on_created()

        self._dialog(
            "Własne ćwiczenie",
            ft.Column([name, load, effort], tight=True, spacing=12, width=400),
            [
                ft.TextButton("Anuluj", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton("Dodaj", height=BTN_HEIGHT, on_click=create),
            ],
        )

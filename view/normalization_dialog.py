"""
Diálogos de la normalización de nombres.

La revisión de nombres largos se invoca desde el hilo de trabajo y se
sincroniza con el bucle principal: el trabajador queda bloqueado hasta que la
persona usuaria decide, sin congelar la interfaz.
"""

from __future__ import annotations

import asyncio

import flet as ft

from service.name_normalizer import CandidateValidation, validate_candidate
from service.normalization_engine import (
    NormalizationPlan,
    PlanEntry,
    ReviewDecision,
)

GREEN = "#16A34A"
RED = "#DC2626"
AMBER = "#B45309"
SLATE = "#475569"


def _short(text: str, limit: int = 58) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


class NormalizationReviewDialog:
    """Cola de diálogos para decidir el nombre final de los elementos largos."""

    def __init__(self, page: ft.Page, loop: asyncio.AbstractEventLoop) -> None:
        self.page = page
        self.loop = loop
        self._skip_all = False

    def ask(self, entry: PlanEntry, reason: str) -> ReviewDecision:
        """Se llama desde el hilo de trabajo y espera la respuesta."""
        if self._skip_all:
            return ReviewDecision("skip")
        future = asyncio.run_coroutine_threadsafe(
            self._show(entry, reason), self.loop
        )
        return future.result()

    async def _show(self, entry: PlanEntry, reason: str) -> ReviewDecision:
        decision: asyncio.Future[ReviewDecision] = self.loop.create_future()

        def close(action: str, name: str | None = None) -> None:
            if action == "skip-all":
                self._skip_all = True
                action = "skip"
            if not decision.done():
                decision.set_result(ReviewDecision(action, name))
            self.page.pop_dialog()
            self.page.update()

        def evaluate(value: str) -> CandidateValidation:
            return validate_candidate(
                value,
                entry.parent_target,
                is_directory=entry.is_directory,
                siblings=entry.sibling_names,
                own_name=entry.original_name,
            )

        name_field = ft.TextField(
            value=entry.final_name,
            autofocus=True,
            dense=True,
            bgcolor="#FFFFFF",
            text_size=13,
            border_color=RED,
            focused_border_color=RED,
        )
        counter = ft.Text(size=12, weight=ft.FontWeight.W_600, color=RED)
        message = ft.Text(size=12, color=RED)
        accept_button = ft.FilledButton("Renombrar", disabled=True)

        def refresh(event: ft.ControlEvent | None = None) -> None:
            validation = evaluate(name_field.value or "")
            color = GREEN if validation.is_valid else RED
            name_field.border_color = color
            name_field.focused_border_color = color
            counter.value = (
                f"{validation.length} / {validation.max_length} caracteres"
            )
            counter.color = color
            message.value = validation.message
            message.color = color
            accept_button.disabled = not validation.is_valid
            self.page.update()

        name_field.on_change = refresh
        accept_button.on_click = lambda event: close("accept", name_field.value)
        refresh()

        kind = "Carpeta" if entry.is_directory else "Archivo"
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=AMBER, size=22),
                    ft.Text(
                        "Nombre demasiado largo",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
                spacing=8,
            ),
            content=ft.Container(
                width=600,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Text(
                            f"{kind}: {_short(entry.original_name, 80)}",
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color="#1E293B",
                            selectable=True,
                        ),
                        ft.Text(
                            f"Carpeta: {_short(entry.parent_target, 80)}",
                            size=11,
                            color=SLATE,
                            selectable=True,
                        ),
                        ft.Text(reason, size=12, color=AMBER),
                        ft.Text(
                            "Escribe un nombre que quepa en el límite. El borde "
                            "se pone verde cuando el nombre es válido.",
                            size=11,
                            color=SLATE,
                        ),
                        name_field,
                        ft.Row(
                            [counter, message],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    "Omitir todos",
                    on_click=lambda event: close("skip-all"),
                ),
                ft.TextButton(
                    "Omitir",
                    on_click=lambda event: close("skip"),
                ),
                ft.TextButton(
                    "Cancelar normalización",
                    on_click=lambda event: close("cancel"),
                ),
                accept_button,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(dialog)
        self.page.update()
        return await decision


class NormalizationPreviewDialog:
    """Muestra el plan completo antes de tocar el disco."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page

    async def confirm(self, plan: NormalizationPlan) -> bool:
        decision: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        def close(accepted: bool) -> None:
            if not decision.done():
                decision.set_result(accepted)
            self.page.pop_dialog()
            self.page.update()

        rows: list[ft.Control] = []
        for entry in plan.changes[:300]:
            rows.append(
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            _short(plan.relative_source(entry), 46),
                            size=11,
                            font_family="monospace",
                            color="#334155",
                            width=330,
                            no_wrap=True,
                        ),
                        ft.Icon(
                            ft.Icons.ARROW_FORWARD_ROUNDED, size=12, color=SLATE
                        ),
                        ft.Text(
                            _short(entry.final_name, 46),
                            size=11,
                            font_family="monospace",
                            color="#1D4ED8",
                            no_wrap=True,
                            expand=True,
                        ),
                    ],
                )
            )

        if not rows:
            rows.append(
                ft.Text(
                    "No hay nombres que cambiar.",
                    size=12,
                    color=SLATE,
                )
            )
        elif len(plan.changes) > 300:
            rows.append(
                ft.Text(
                    f"… y {len(plan.changes) - 300} elementos más.",
                    size=11,
                    color=SLATE,
                )
            )

        summary: list[ft.Control] = [
            ft.Text(
                f"Elementos analizados: {len(plan.entries)}",
                size=12,
                color="#1E293B",
            ),
        ]

        if plan.mode == "copy":
            summary.append(
                ft.Text(
                    f"Se copiarán {plan.file_count} archivo(s) en "
                    f"{plan.directory_count} carpeta(s).",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color="#1D4ED8",
                )
            )
            summary.append(
                ft.Text(
                    f"Destino: {_short(plan.destination_root or '', 80)}",
                    size=11,
                    color=SLATE,
                    selectable=True,
                )
            )
            warning = (
                "El origen no se modifica. Se guardará un diario para poder "
                "eliminar las copias creadas."
            )
        else:
            summary.append(
                ft.Text(
                    f"Se renombrarán {len(plan.changes)} elemento(s) en el disco.",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    color="#1D4ED8",
                )
            )
            warning = (
                "Esta acción cambia nombres en el disco. Se guardará un diario "
                "en Certificaciones para poder deshacer."
            )

        summary.append(
            ft.Text(
                f"Sin cambios de nombre: {len(plan.unchanged_entries)} · "
                + (
                    f"Omitidos: {len(plan.skipped_entries)}"
                    if plan.mode == "rename"
                    else f"Nombres conservados: {len(plan.skipped_entries)}"
                )
                + f" · Colisiones resueltas: {plan.collisions_resolved}",
                size=11,
                color=SLATE,
            )
        )

        if plan.ignored:
            summary.append(
                ft.Text(
                    f"Elementos ignorados por configuración: {len(plan.ignored)}",
                    size=11,
                    color=SLATE,
                )
            )

        if plan.errors:
            summary.append(
                ft.Text(
                    f"Avisos: {len(plan.errors)}. Revisa el resultado al finalizar.",
                    size=11,
                    color=AMBER,
                )
            )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                "Renombrar en el lugar"
                if plan.mode == "rename"
                else "Copiar árbol normalizado",
                size=16,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                width=720,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        ft.Column(spacing=2, controls=summary),
                        ft.Container(
                            height=260,
                            bgcolor="#F8FAFC",
                            border=ft.Border.all(1, "#E2E8F0"),
                            border_radius=8,
                            padding=8,
                            content=ft.ListView(controls=rows, spacing=4),
                        ),
                        ft.Text(warning, size=11, color=AMBER),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close(False)),
                ft.FilledButton(
                    "Aplicar" if plan.mode == "rename" else "Copiar",
                    on_click=lambda event: close(True),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(dialog)
        self.page.update()
        return await decision


async def ask_confirmation(
    page: ft.Page,
    title: str,
    message: str,
    confirm_label: str,
    *,
    danger: bool = False,
) -> bool:
    """Diálogo de confirmación reutilizable."""
    decision: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

    def close(accepted: bool) -> None:
        if not decision.done():
            decision.set_result(accepted)
        page.pop_dialog()
        page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=16, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            width=520,
            content=ft.Text(message, size=13, color="#1E293B", selectable=True),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda event: close(False)),
            ft.FilledButton(
                confirm_label,
                on_click=lambda event: close(True),
                style=ft.ButtonStyle(
                    bgcolor=RED if danger else "#2563EB",
                    color="#FFFFFF",
                ),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    page.show_dialog(dialog)
    page.update()
    return await decision

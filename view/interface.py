import os
import time
import asyncio
from datetime import datetime
from typing import Any
import flet as ft

import config
from service.generate import CertifyMaker
from service.file_validator import Validator, generate_dated_filename
from service.normalization_engine import (
    NormalizationApplier,
    NormalizationCancelled,
    NormalizationError,
    NormalizationPlanner,
    NormalizationUndo,
)
from view.normalization_dialog import (
    NormalizationPreviewDialog,
    NormalizationReviewDialog,
    ask_confirmation,
)


class Interface:
    async def main(self, page: ft.Page):
        # Configuración de la ventana y tema claro contemporáneo
        page.title = "Certificador de Integridad Documental - Huella HASH SHA-256"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.bgcolor = "#F1F5F9"
        page.padding = ft.Padding.only(left=16, top=16, right=16, bottom=24)
        page.window.alignment = ft.Alignment.CENTER
        page.window.maximizable = False
        page.window.resizable = False
        page.window.shadow = True
        page.window.width = 910
        page.window.height = 740

        # Referencia al bucle de eventos principal para actualizaciones thread-safe
        main_loop = asyncio.get_running_loop()

        # Última normalización aplicada, para habilitar la reversión.
        last_normalization: list[dict[str, str] | None] = [None]

        async def __pick_folder_event(e: ft.ControlEvent):
            """Abre el diálogo nativo y espera el resultado con await."""
            directory_path = await ft.FilePicker().get_directory_path()
            
            if directory_path:
                input_path.value = os.path.normpath(directory_path)
                page.update()

        # Almacenamiento en memoria de la última certificación completada
        active_certify_maker: list[CertifyMaker | None] = [None]

        # FUNCIONES DE ASISTENCIA Y COMPONENTES
        def __add_new_status(message: str):
            status_field.controls.append(
                ft.Text(f"• {message}", size=12, font_family="monospace", color="#334155")
            )
            page.update()

        def __create_label(
            label_text: str,
            font_size: int,
            weight: ft.FontWeight = ft.FontWeight.NORMAL,
            color: str = "#1E293B"
        ) -> ft.Text:
            return ft.Text(value=label_text, size=font_size, weight=weight, color=color)

        def __create_modal(modal_title: str, modal_content: str) -> ft.AlertDialog:
            return ft.AlertDialog(
                modal=True,
                title=__create_label(modal_title, 16, ft.FontWeight.BOLD),
                content=__create_label(modal_content, 14),
                actions=[
                    ft.TextButton("Aceptar", on_click=lambda e: page.pop_dialog())
                ],
                actions_alignment=ft.MainAxisAlignment.CENTER
            )

        def __update_filename_preview(e: ft.ControlEvent | None = None):
            raw_name = (input_fileName.value or "").strip()
            if raw_name:
                preview = generate_dated_filename(raw_name)
                filename_preview_label.value = f"Nombre final: {preview}"
                filename_preview_label.color = "#2563EB"
            else:
                date_sample = datetime.now().strftime("%d_%m_%y")
                filename_preview_label.value = f"Ejemplo de formato: NOMBRE-{date_sample}"
                filename_preview_label.color = "#64748B"
            page.update()

        # LÓGICA DE INTERFAZ
        def __populate_extension_list(file_list_obj: list[dict[str, Any]]):
            extension_list.controls.clear()
            sorted_items = sorted(file_list_obj, key=lambda x: x.get("conteo", 0), reverse=True)
            for item in sorted_items:
                ext = str(item.get("extension")).upper()
                ext_display = f".{ext}" if ext != "SIN_EXTENSION" else "(Sin ext)"
                inc_item = f"{ext_display:<14} : {item.get('conteo')} archivo(s)"
                extension_list.controls.append(
                    ft.Text(inc_item, font_family="monospace", size=12, color="#1E293B")
                )

        def __validations() -> tuple[str | None, str]:
            path = (input_path.value or "").strip()
            file = (input_fileName.value or "").strip()
            val = Validator(path, file)

            if len(path) < 2:
                return "Escribe o selecciona una ruta válida a certificar.", ""

            if not val.valid_dir_path():
                return "No se encontró el directorio especificado. Verifica que exista y cuente con permisos.", ""

            if len(file) < 2:
                return "El nombre del archivo de salida es demasiado corto (mínimo 2 caracteres).", ""

            if not val.valid_file_name_characters():
                return "El nombre contiene caracteres no válidos (< > : \" / \\ | ? *).", ""

            resolved_name = val.get_resolved_dated_filename()
            return None, resolved_name

        async def __certify_process(resolved_output_name: str):
            __disable_components(True)
            export_txt_button.disabled = True
            extension_list.controls.clear()
            active_certify_maker[0] = None

            progress_bar.value = 0.0
            progress_bar.visible = True
            progress_label.visible = True
            progress_label.value = "Descubriendo archivos..."
            page.update()

            __add_new_status(f"Iniciando certificación con nombre: {resolved_output_name}")
            target_directory = input_path.value.strip()

            last_update_time = [0.0]

            def thread_progress_callback(current: int, total: int, current_file: str):
                now = time.time()
                if (now - last_update_time[0] >= 0.03) or (current == total) or (current == 1):
                    last_update_time[0] = now
                    def force_update_ui():
                        if total > 0:
                            progress_bar.value = current / total
                            short_name = os.path.basename(current_file)
                            progress_label.value = f"Hasheando ({current}/{total}): {short_name[:30]}"
                        page.update()

                    main_loop.call_soon_threadsafe(force_update_ui)

            try:
                cm = await asyncio.to_thread(
                    CertifyMaker,
                    target_directory,
                    resolved_output_name,
                    config.SAVE_JSON_CERTIFICATIONS,
                    thread_progress_callback
                )

                active_certify_maker[0] = cm
                counted_files = cm.get_file_extension_list()
                total_files = cm.get_total_files_count()

                __add_new_status(f"Archivos procesados exitosamente: {total_files}")
                __populate_extension_list(counted_files)
                label_files.value = str(total_files)

                # Estadísticas de almacenamiento
                state_usedStorage.value = cm.get_used_space()
                state_totalStorage.value = cm.get_logical_drive_size()
                state_freeStorage.value = cm.get_logical_drive_free_space()

                if config.SAVE_JSON_CERTIFICATIONS:
                    __add_new_status(f"Reporte JSON guardado: Certificaciones/{resolved_output_name}.json")
                else:
                    __add_new_status("Almacenamiento JSON desactivado según configuración.")

                if config.SAVE_SQLITE_CERTIFICATIONS:
                    __add_new_status(f"Certificación registrada en SQLite: {config.SQLITE_DB_NAME}")
                else:
                    __add_new_status("Almacenamiento SQLite desactivado según configuración.")

                if cm.errors_log:
                    __add_new_status(f"Advertencia: {len(cm.errors_log)} archivo(s) no pudieron ser leídos.")

                __add_new_status("Certificación completada. Haz clic en 'Exportar a TXT' si requieres el reporte de texto.")
                
                export_txt_button.disabled = False

                success_msg = (
                    f"Certificación finalizada con éxito.\n\n"
                    f"• Nombre asignado: {resolved_output_name}\n"
                    f"• Archivos auditados: {total_files}\n"
                    f"• Espacio ocupado: {cm.get_used_space()}\n\n"
                    f"Haz clic en 'Exportar a TXT' para guardar el reporte de texto."
                )
                modal = __create_modal("Certificación Completada", success_msg)
                page.show_dialog(modal)

            except Exception as ex:
                __add_new_status(f"Error: {str(ex)}")
                error_modal = __create_modal("Error en la certificación", f"Ocurrió un error inesperado:\n{str(ex)}")
                page.show_dialog(error_modal)
            finally:
                progress_bar.visible = False
                progress_label.visible = False
                __disable_components(False)
                __update_filename_preview()
                page.update()

        async def __validation_task(e: ft.ControlEvent):
            error, resolved_name = __validations()
            if error:
                __add_new_status(f"Aviso: {error}")
                return
            await __certify_process(resolved_name)

        def __export_txt_action(e: ft.ControlEvent):
            cm = active_certify_maker[0]
            if not cm:
                __add_new_status("Aviso: Debes realizar una certificación antes de exportar.")
                return

            try:
                txt_path = cm.export_text_report()
                file_name_only = os.path.basename(txt_path)
                __add_new_status(f"Reporte de texto exportado exitosamente a: Certificaciones/{file_name_only}")
                
                export_modal = __create_modal(
                    "Exportación Exitosa",
                    f"El reporte de texto ha sido generado y guardado en:\n\n{txt_path}"
                )
                page.show_dialog(export_modal)
            except Exception as ex:
                __add_new_status(f"Error al exportar a TXT: {str(ex)}")
                error_modal = __create_modal("Error de Exportación", f"No se pudo guardar el archivo TXT:\n{str(ex)}")
                page.show_dialog(error_modal)

        def __invalidate_certification() -> None:
            """Una certificación previa deja de ser válida si cambian los nombres."""
            if active_certify_maker[0] is None:
                return
            active_certify_maker[0] = None
            export_txt_button.disabled = True
            label_files.value = "-"
            extension_list.controls.clear()
            __add_new_status(
                "La certificación anterior quedó desactualizada; vuelve a certificar."
            )
            page.update()

        async def __ask_normalization_mode() -> str | None:
            decision: asyncio.Future[str | None] = main_loop.create_future()

            def close(mode: str | None) -> None:
                if not decision.done():
                    decision.set_result(mode)
                page.pop_dialog()
                page.update()

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(
                    "Normalizar nombres",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Container(
                    width=560,
                    content=ft.Column(
                        tight=True,
                        spacing=8,
                        controls=[
                            ft.Text(
                                "Se eliminarán puntos, comas, barras y símbolos; "
                                "se sustituirán los acentos por su letra base y se "
                                "conservarán los paréntesis, los guiones y los "
                                "guiones bajos.",
                                size=12,
                                color="#334155",
                            ),
                            ft.Text(
                                "Renombrar en el lugar modifica el contenido "
                                "seleccionado. Copiar deja el origen intacto y "
                                "escribe el árbol normalizado en otra carpeta.",
                                size=12,
                                color="#334155",
                            ),
                            ft.Text(
                                "Los nombres que excedan el límite se revisan "
                                "contigo antes de aplicar cualquier cambio.",
                                size=11,
                                color="#64748B",
                            ),
                        ],
                    ),
                ),
                actions=[
                    ft.TextButton(
                        "Cancelar", on_click=lambda event: close(None)
                    ),
                    ft.OutlinedButton(
                        "Copiar a otra carpeta",
                        on_click=lambda event: close("copy"),
                    ),
                    ft.FilledButton(
                        "Renombrar en el lugar",
                        on_click=lambda event: close("rename"),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.show_dialog(dialog)
            page.update()
            return await decision

        async def __run_normalization(
            target_path: str, mode: str, destination: str | None
        ) -> None:
            __disable_components(True)
            normalize_button.disabled = True
            progress_bar.value = 0.0
            progress_bar.visible = True
            progress_label.visible = True
            progress_label.value = "Analizando nombres..."
            page.update()

            mode_label = "renombrado" if mode == "rename" else "copia normalizada"
            __add_new_status(f"Iniciando {mode_label}: {target_path}")

            reviewer = NormalizationReviewDialog(page, main_loop)
            last_update_time = [0.0]

            def planning_progress(current: int, total: int, current_path: str):
                now = time.time()
                if now - last_update_time[0] < 0.1:
                    return
                last_update_time[0] = now
                short_name = os.path.basename(current_path)[:38]

                def force_update_ui():
                    progress_label.value = f"Analizando ({current}): {short_name}"
                    page.update()

                main_loop.call_soon_threadsafe(force_update_ui)

            try:
                planner = NormalizationPlanner(
                    target_path,
                    mode=mode,  # type: ignore[arg-type]
                    destination_root=destination,
                    resolver=reviewer.ask,
                    progress_callback=planning_progress,
                )
                plan = await asyncio.to_thread(planner.build)
            except NormalizationCancelled:
                __add_new_status("Normalización cancelada durante la revisión.")
                return
            except NormalizationError as ex:
                __add_new_status(f"Aviso: {ex}")
                page.show_dialog(
                    __create_modal("No se pudo normalizar", str(ex))
                )
                return
            except Exception as ex:
                __add_new_status(f"Error al planificar la normalización: {ex}")
                page.show_dialog(
                    __create_modal(
                        "Error al planificar",
                        f"Ocurrió un error inesperado:\n{ex}",
                    )
                )
                return
            finally:
                progress_bar.visible = False
                progress_label.visible = False
                __disable_components(False)
                page.update()

            if not plan.entries:
                __add_new_status("No se encontraron archivos ni carpetas para procesar.")
                return

            if mode == "rename" and not plan.changes:
                __add_new_status("No hay nombres que requieran normalización.")
                return

            confirmed = await NormalizationPreviewDialog(page).confirm(plan)
            if not confirmed:
                __add_new_status("Operación cancelada desde la vista previa.")
                return

            __disable_components(True)
            normalize_button.disabled = True
            progress_bar.value = 0.0
            progress_bar.visible = True
            progress_label.visible = True
            progress_label.value = "Aplicando cambios..."
            page.update()

            def apply_progress(current: int, total: int, current_path: str):
                if total <= 0:
                    return

                def force_update_ui():
                    progress_bar.value = min(1.0, current / total)
                    progress_label.value = (
                        f"Aplicando ({current}/{total}): "
                        f"{os.path.basename(current_path)[:30]}"
                    )
                    page.update()

                main_loop.call_soon_threadsafe(force_update_ui)

            try:
                applier = NormalizationApplier(
                    plan, progress_callback=apply_progress
                )
                result = await asyncio.to_thread(applier.apply)
            except Exception as ex:
                __add_new_status(f"Error al aplicar la normalización: {ex}")
                page.show_dialog(
                    __create_modal(
                        "Error al aplicar",
                        f"Ocurrió un error inesperado:\n{ex}",
                    )
                )
                return
            finally:
                progress_bar.visible = False
                progress_label.visible = False
                __disable_components(False)
                page.update()

            if mode == "rename":
                __add_new_status(f"Elementos renombrados: {result.renamed}")
                if result.renamed:
                    __invalidate_certification()
            else:
                __add_new_status(f"Archivos copiados: {result.copied_files}")
                __add_new_status(
                    f"Carpetas creadas: {result.created_directories}"
                )

            if result.skipped:
                skipped_label = (
                    "Elementos omitidos"
                    if mode == "rename"
                    else "Nombres conservados sin cambios"
                )
                __add_new_status(f"{skipped_label}: {result.skipped}")

            for error in result.errors[:5]:
                __add_new_status(f"Aviso: {error}")
            if len(result.errors) > 5:
                __add_new_status(
                    f"Aviso: {len(result.errors) - 5} incidencia(s) adicionales."
                )

            if result.journal_path:
                last_normalization[0] = {
                    "journal": result.journal_path,
                    "mode": mode,
                }
                undo_button.disabled = False
                __add_new_status(
                    f"Diario de reversión: {os.path.basename(result.journal_path)}"
                )

            title = (
                "Normalización completada"
                if result.completed and not result.errors
                else "Normalización finalizada con avisos"
            )
            message_lines = [
                f"Modo: {'renombrado en el lugar' if mode == 'rename' else 'copia normalizada'}",
                f"Elementos analizados: {len(plan.entries)}",
            ]
            if mode == "rename":
                message_lines.append(f"Renombrados: {result.renamed}")
            else:
                message_lines.append(f"Archivos copiados: {result.copied_files}")
                message_lines.append(
                    f"Carpetas creadas: {result.created_directories}"
                )
            if result.skipped:
                message_lines.append(
                    f"Omitidos: {result.skipped}"
                    if mode == "rename"
                    else f"Nombres conservados: {result.skipped}"
                )
            if result.errors:
                message_lines.append(
                    f"Incidencias: {len(result.errors)} (revisa la consola de eventos)"
                )
            if result.journal_path:
                message_lines.append(
                    f"Diario: {os.path.basename(result.journal_path)}"
                )

            page.show_dialog(
                __create_modal(title, "\n".join(message_lines))
            )

        async def __normalize_event(e: ft.ControlEvent):
            if not config.NORMALIZATION_ENABLED:
                return

            target_path = (input_path.value or "").strip()
            validator = Validator(target_path, input_fileName.value or "")

            if len(target_path) < 2:
                __add_new_status(
                    "Aviso: escribe o selecciona una ruta válida para normalizar."
                )
                return

            if not validator.valid_dir_path():
                __add_new_status(
                    "Aviso: no se encontró el directorio para normalizar."
                )
                return

            mode = await __ask_normalization_mode()
            if mode is None:
                return

            destination = None
            if mode == "copy":
                destination = await ft.FilePicker().get_directory_path()
                if not destination:
                    __add_new_status("Aviso: copia normalizada cancelada.")
                    return

            await __run_normalization(target_path, mode, destination)

        async def __undo_normalization(e: ft.ControlEvent):
            state = last_normalization[0]
            if not state:
                __add_new_status("Aviso: no hay una normalización reciente que deshacer.")
                return

            is_copy = state["mode"] == "copy"
            message = (
                "Se eliminarán únicamente los archivos y carpetas creados por la "
                "última copia normalizada. Los archivos preexistentes en el destino "
                "no se tocan."
                if is_copy
                else "Se restaurarán los nombres originales de la última "
                "normalización. Si algún nombre original ya está ocupado, ese "
                "elemento se conservará y se reportará como conflicto."
            )

            confirmed = await ask_confirmation(
                page,
                "Deshacer normalización",
                message,
                "Eliminar copias" if is_copy else "Deshacer",
                danger=is_copy,
            )
            if not confirmed:
                return

            __disable_components(True)
            normalize_button.disabled = True
            progress_bar.visible = True
            progress_bar.value = 0.0
            progress_label.visible = True
            progress_label.value = "Revirtiendo cambios..."
            page.update()

            try:
                undo = NormalizationUndo(state["journal"])
                result = await asyncio.to_thread(undo.undo)
            except NormalizationError as ex:
                __add_new_status(f"Aviso: {ex}")
                page.show_dialog(
                    __create_modal("No se pudo deshacer", str(ex))
                )
                return
            except Exception as ex:
                __add_new_status(f"Error al deshacer: {ex}")
                page.show_dialog(
                    __create_modal(
                        "Error al deshacer",
                        f"Ocurrió un error inesperado:\n{ex}",
                    )
                )
                return
            finally:
                progress_bar.visible = False
                progress_label.visible = False
                __disable_components(False)
                page.update()

            if is_copy:
                __add_new_status(f"Archivos eliminados: {result.removed_files}")
                __add_new_status(
                    f"Carpetas eliminadas: {result.removed_directories}"
                )
            else:
                __add_new_status(f"Nombres restaurados: {result.restored}")
                if result.restored:
                    __invalidate_certification()

            for error in result.errors[:5]:
                __add_new_status(f"Aviso: {error}")

            if not result.errors:
                last_normalization[0] = None
                undo_button.disabled = True

            page.show_dialog(
                __create_modal(
                    "Reversión completada"
                    if not result.errors
                    else "Reversión finalizada con avisos",
                    "Los cambios se revirtieron correctamente."
                    if not result.errors
                    else (
                        "Se revirtieron los cambios posibles. "
                        f"Incidencias: {len(result.errors)}."
                    ),
                )
            )

        def __clean_components(e: ft.ControlEvent):
            active_certify_maker[0] = None
            state_totalStorage.value = "-"
            state_usedStorage.value = "-"
            state_freeStorage.value = "-"
            label_files.value = "-"
            input_path.value = ""
            input_fileName.value = ""
            progress_bar.value = 0.0
            progress_bar.visible = False
            progress_label.visible = False
            export_txt_button.disabled = True
            extension_list.controls.clear()
            status_field.controls.clear()
            __update_filename_preview()
            page.update()

        def __disable_components(component_state: bool):
            controls = [
                input_fileName,
                input_path,
                browse_button,
                make_button,
                clean_button,
                normalize_button,
                undo_button,
            ]
            for control in controls:
                control.disabled = component_state
            undo_button.disabled = component_state or last_normalization[0] is None
            page.update()

        # ELEMENTOS DE LA INTERFAZ (TEMA CLARO Y DISTRIBUCIÓN COHERENTE)
        font_label = 13
        font_big_label = 15
        font_count_label = 26

        # Entradas y Acciones
        label_path = __create_label("Directorio o unidad a certificar:", font_label, ft.FontWeight.W_600)
        input_path = ft.TextField(
            hint_text="Ejemplo: E:\\Archivos o C:\\Auditoria",
            multiline=False,
            expand=True,
            dense=True,
            bgcolor="#FFFFFF"
        )
        browse_button = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            icon_color="#2563EB",
            tooltip="Explorar carpeta en el equipo...",
            on_click=__pick_folder_event
        )

        label_fileName = __create_label("Nombre de certificación:", font_label, ft.FontWeight.W_600)
        input_fileName = ft.TextField(
            hint_text="Ejemplo: CERTIFICACION_USB",
            multiline=False,
            dense=True,
            expand=True,
            bgcolor="#FFFFFF",
            on_change=__update_filename_preview
        )
        filename_preview_label = ft.Text(
            value=f"Ejemplo de formato: NOMBRE-{datetime.now().strftime('%d_%m_%y')}",
            size=11,
            color="#64748B",
            weight=ft.FontWeight.W_500,
            text_align=ft.TextAlign.CENTER
        )

        make_button = ft.FilledButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.VERIFIED_ROUNDED, size=18), ft.Text("Certificar", weight=ft.FontWeight.BOLD)],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            style=ft.ButtonStyle(bgcolor="#2563EB", color="#FFFFFF"),
            on_click=__validation_task,
            expand=True,
            height=38
        )
        clean_button = ft.OutlinedButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.CLEANING_SERVICES_ROUNDED, size=18), ft.Text("Limpiar")],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            style=ft.ButtonStyle(color="#64748B"),
            on_click=__clean_components,
            expand=True,
            height=38
        )
        export_txt_button = ft.FilledTonalButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.DESCRIPTION_ROUNDED, size=18), ft.Text("Exportar a TXT", weight=ft.FontWeight.W_600)],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            style=ft.ButtonStyle(bgcolor="#0D9488", color="#FFFFFF"),
            on_click=__export_txt_action,
            disabled=True,
            expand=True,
            height=38
        )

        normalize_button = ft.FilledTonalButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.DRIVE_FILE_RENAME_OUTLINE_ROUNDED, size=18),
                    ft.Text("Normalizar nombres", weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(bgcolor="#EEF2FF", color="#3730A3"),
            on_click=__normalize_event,
            visible=config.NORMALIZATION_ENABLED,
            expand=True,
            height=36,
        )
        undo_button = ft.IconButton(
            icon=ft.Icons.UNDO_ROUNDED,
            icon_color="#B45309",
            tooltip="Deshacer la última normalización",
            on_click=__undo_normalization,
            disabled=True,
        )

        progress_bar = ft.ProgressBar(value=0.0, visible=False, color="#2563EB", bgcolor="#E2E8F0")
        progress_label = ft.Text(value="", size=11, visible=False, color="#475569", weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER)

        label_quantity = ft.Text(
            value="Archivos auditados",
            size=13,
            weight=ft.FontWeight.W_600,
            color="#475569",
            text_align=ft.TextAlign.CENTER
        )
        label_files = ft.Text(
            value="-",
            size=font_count_label,
            weight=ft.FontWeight.BOLD,
            color="#1E293B",
            text_align=ft.TextAlign.CENTER
        )

        # Métricas de Almacenamiento
        label_totalStorage = __create_label("Capacidad Total", 11, ft.FontWeight.W_600, "#1E40AF")
        state_totalStorage = __create_label("-", font_big_label, ft.FontWeight.BOLD, "#1E3A8A")
        label_usedStorage = __create_label("Espacio Utilizado", 11, ft.FontWeight.W_600, "#B45309")
        state_usedStorage = __create_label("-", font_big_label, ft.FontWeight.BOLD, "#92400E")
        label_freeStorage = __create_label("Espacio Libre", 11, ft.FontWeight.W_600, "#065F46")
        state_freeStorage = __create_label("-", font_big_label, ft.FontWeight.BOLD, "#064E3B")

        label_extensionList = __create_label("Formatos y Cantidades de Archivos", font_label, ft.FontWeight.W_600)
        extension_list = ft.ListView(
            height=180,
            controls=[]
        )

        label_status = __create_label("Consola de Eventos y Estado", font_label, ft.FontWeight.W_600)
        status_field = ft.ListView(
            height=95,
            padding=6,
            reverse=True,
            controls=[]
        )

        # DISTRIBUCIÓN Y ALINEACIÓN DE CONTENEDORES
        page.add(
            ft.Column(
                spacing=12,
                expand=True,
                controls=[
                    # FILA SUPERIOR: Distribución simétrica (Izquierda y Derecha)
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                        spacing=12,
                        height=486,
                        controls=[
                            # PANEL IZQUIERDO: Entradas, Acciones y Contador
                            ft.Container(
                                expand=1,
                                bgcolor="#FFFFFF",
                                border=ft.Border.all(1, "#E2E8F0"),
                                border_radius=10,
                                padding=14,
                                shadow=ft.BoxShadow(spread_radius=0.5, blur_radius=4, color=ft.Colors.BLACK12, offset=ft.Offset(0, 1)),
                                content=ft.Column(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Column(
                                            spacing=8,
                                            controls=[
                                                label_path,
                                                ft.Row(
                                                    controls=[input_path, browse_button],
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                                                ),
                                                label_fileName,
                                                ft.Row(
                                                    controls=[input_fileName],
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                                                ),
                                                ft.Row(
                                                    controls=[filename_preview_label],
                                                    alignment=ft.MainAxisAlignment.CENTER
                                                ),
                                            ]
                                        ),
                                        ft.Column(
                                            spacing=8,
                                            controls=[
                                                ft.Row(
                                                    controls=[make_button, clean_button],
                                                    spacing=8
                                                ),
                                                ft.Row(
                                                    controls=[normalize_button, undo_button],
                                                    spacing=8,
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                ),
                                                export_txt_button,
                                                ft.Column(
                                                    spacing=2,
                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                    controls=[progress_bar, progress_label]
                                                ),
                                            ]
                                        ),
                                        ft.Container(
                                            bgcolor="#F8FAFC",
                                            border=ft.Border.all(1, "#E2E8F0"),
                                            border_radius=8,
                                            padding=12,
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Column(
                                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                spacing=4,
                                                controls=[label_quantity, label_files]
                                            )
                                        )
                                    ]
                                )
                            ),
                            # PANEL DERECHO: Tarjetas de Almacenamiento y Lista de Formatos
                            ft.Container(
                                expand=1,
                                bgcolor="#FFFFFF",
                                border=ft.Border.all(1, "#E2E8F0"),
                                border_radius=10,
                                padding=14,
                                shadow=ft.BoxShadow(spread_radius=0.5, blur_radius=4, color=ft.Colors.BLACK12, offset=ft.Offset(0, 1)),
                                content=ft.Column(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        # 3 Tarjetas de Almacenamiento Destacadas
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.Container(
                                                    expand=1,
                                                    bgcolor="#EFF6FF",
                                                    border=ft.Border.all(1, "#BFDBFE"),
                                                    border_radius=8,
                                                    padding=8,
                                                    content=ft.Column(
                                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                        controls=[label_totalStorage, state_totalStorage]
                                                    )
                                                ),
                                                ft.Container(
                                                    expand=1,
                                                    bgcolor="#FFFBEB",
                                                    border=ft.Border.all(1, "#FDE68A"),
                                                    border_radius=8,
                                                    padding=8,
                                                    content=ft.Column(
                                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                        controls=[label_usedStorage, state_usedStorage]
                                                    )
                                                ),
                                                ft.Container(
                                                    expand=1,
                                                    bgcolor="#ECFDF5",
                                                    border=ft.Border.all(1, "#A7F3D0"),
                                                    border_radius=8,
                                                    padding=8,
                                                    content=ft.Column(
                                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                        controls=[label_freeStorage, state_freeStorage]
                                                    )
                                                )
                                            ]
                                        ),
                                        # Formatos y Cantidades de Archivos
                                        ft.Column(
                                            spacing=6,
                                            controls=[
                                                label_extensionList,
                                                ft.Container(
                                                    content=extension_list,
                                                    bgcolor="#F8FAFC",
                                                    border=ft.Border.all(1, "#E2E8F0"),
                                                    border_radius=8,
                                                    padding=8,
                                                    height=240
                                                )
                                            ]
                                        )
                                    ]
                                )
                            )
                        ]
                    ),
                    # FILA INFERIOR: Consola de Eventos y Estado
                    ft.Container(
                        bgcolor="#FFFFFF",
                        border=ft.Border.all(1, "#E2E8F0"),
                        border_radius=10,
                        padding=12,
                        shadow=ft.BoxShadow(spread_radius=0.5, blur_radius=4, color=ft.Colors.BLACK12, offset=ft.Offset(0, 1)),
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                label_status,
                                ft.Container(
                                    bgcolor="#F8FAFC",
                                    border=ft.Border.all(1, "#E2E8F0"),
                                    border_radius=8,
                                    content=status_field
                                ),
                                # Créditos y enlace al repositorio
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.TextButton(
                                            "Desarrollado por CharlieH52",
                                            icon=ft.Icons.CODE,
                                            url="https://github.com/CharlieH52",
                                            tooltip="Perfil de GitHub",
                                            style=ft.ButtonStyle(
                                                color="#475569",
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                overlay_color=ft.Colors.TRANSPARENT,
                                            ),
                                        ),
                                        ft.TextButton(
                                            "certificador-integral-documental",
                                            icon=ft.Icons.FOLDER_OPEN,
                                            url="https://github.com/CharlieH52/certificador-integral-documental",
                                            tooltip="Repositorio en GitHub",
                                            style=ft.ButtonStyle(
                                                color="#475569",
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                overlay_color=ft.Colors.TRANSPARENT,
                                            ),
                                        ),
                                    ],
                                ),
                            ]
                        )
                    )
                ]
            )
        )
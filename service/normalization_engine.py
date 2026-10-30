"""
Motor de planificación, aplicación y reversión de la normalización de nombres.

El flujo es siempre el mismo:

1. Se planifica el árbol completo sin tocar el disco.
2. Los nombres que exceden el límite disponible se resuelven con la persona
   usuaria mediante un ``resolver`` (o se marcan para revisión si no hay uno).
3. Se muestra el plan y, solo tras la confirmación, se aplica.
4. Cada aplicación deja un diario en ``Certificaciones`` que permite deshacer.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

import config
from service.name_normalizer import (
    DEFAULT_RULES,
    NormalizationRules,
    append_collision_suffix,
    max_name_length,
    normalize_name,
    utf16_length,
    validate_candidate,
)


class NormalizationError(Exception):
    """Error controlado del proceso de normalización."""


class NormalizationCancelled(Exception):
    """La persona usuaria canceló el proceso durante la revisión manual."""


ReviewAction = Literal["accept", "skip", "cancel"]
PlanMode = Literal["rename", "copy"]


@dataclass
class ReviewDecision:
    """Respuesta de la persona usuaria ante un nombre demasiado largo."""

    action: ReviewAction
    name: str | None = None


@dataclass
class PlanEntry:
    """Elemento del árbol con su nombre propuesto y su nombre final."""

    source_path: str
    original_name: str
    final_name: str
    is_directory: bool
    parent_source: str
    parent_target: str
    depth: int = 0
    skipped: bool = False
    reviewed: bool = False
    review_reason: str | None = None
    sibling_names: tuple[str, ...] = ()

    @property
    def target_path(self) -> str:
        return os.path.join(self.parent_target, self.final_name)

    @property
    def is_change(self) -> bool:
        return not self.skipped and self.original_name != self.final_name


@dataclass
class NormalizationPlan:
    """Resultado de la planificación, listo para previsualizar y aplicar."""

    root: str
    mode: PlanMode
    destination_root: str | None = None
    entries: list[PlanEntry] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    scanned_directories: int = 0
    collisions_resolved: int = 0

    @property
    def changes(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.is_change]

    @property
    def skipped_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.skipped]

    @property
    def reviewed_entries(self) -> list[PlanEntry]:
        return [entry for entry in self.entries if entry.reviewed]

    @property
    def unchanged_entries(self) -> list[PlanEntry]:
        return [
            entry
            for entry in self.entries
            if not entry.skipped and entry.original_name == entry.final_name
        ]

    @property
    def file_count(self) -> int:
        return sum(1 for entry in self.entries if not entry.is_directory)

    @property
    def directory_count(self) -> int:
        return sum(1 for entry in self.entries if entry.is_directory)

    def relative_source(self, entry: PlanEntry) -> str:
        try:
            return os.path.relpath(entry.source_path, self.root)
        except ValueError:
            return entry.source_path


@dataclass
class ApplyResult:
    """Resumen de una aplicación del plan."""

    renamed: int = 0
    copied_files: int = 0
    created_directories: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    journal_path: str | None = None
    completed: bool = True


@dataclass
class UndoResult:
    """Resumen de una reversión a partir del diario."""

    restored: int = 0
    removed_files: int = 0
    removed_directories: int = 0
    errors: list[str] = field(default_factory=list)


ProgressCallback = Callable[[int, int, str], None]
ReviewResolver = Callable[[PlanEntry, str], ReviewDecision]


@dataclass
class _ResolvedName:
    name: str
    reviewed: bool = False
    skipped: bool = False
    reason: str | None = None


def _normalized_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _is_within(path: str, parent: str) -> bool:
    """Indica si ``path`` es ``parent`` o está contenido en él."""
    normalized_path = _normalized_path(path)
    normalized_parent = _normalized_path(parent)
    if normalized_path == normalized_parent:
        return True
    return normalized_path.startswith(normalized_parent.rstrip(os.sep) + os.sep)


def _path_depth(path: str) -> int:
    return len([part for part in os.path.normpath(path).split(os.sep) if part])


class NormalizationPlanner:
    """Construye un plan de renombrado o de copia sin modificar el disco."""

    def __init__(
        self,
        root: str,
        *,
        mode: PlanMode = "rename",
        destination_root: str | None = None,
        resolver: ReviewResolver | None = None,
        progress_callback: ProgressCallback | None = None,
        rules: NormalizationRules | None = None,
    ) -> None:
        self.root = os.path.abspath(root.strip().strip('"').strip("'"))
        self.mode: PlanMode = mode
        self.destination_root = (
            os.path.abspath(destination_root.strip().strip('"').strip("'"))
            if destination_root
            else None
        )
        self.resolver = resolver
        self.progress_callback = progress_callback
        self.rules = rules or DEFAULT_RULES

        self._ignored_directories = {
            name.casefold() for name in config.NORMALIZATION_IGNORED_DIRECTORIES
        }
        self._ignored_files = {
            name.casefold() for name in config.NORMALIZATION_IGNORED_FILES
        }
        self._output_directory = _normalized_path(
            os.path.join(os.getcwd(), config.OUTPUT_DIRECTORY)
        )

    # ------------------------------------------------------------------
    # Planificación
    # ------------------------------------------------------------------
    def build(self) -> NormalizationPlan:
        self._validate_request()

        plan = NormalizationPlan(
            root=self.root,
            mode=self.mode,
            destination_root=self.destination_root,
        )
        queue: list[tuple[str, str, int]] = [
            (self.root, self.destination_root or self.root, 0)
        ]

        while queue:
            source_directory, target_directory, depth = queue.pop(0)
            self._plan_directory(
                source_directory, target_directory, depth, plan, queue
            )
            if self.progress_callback:
                self.progress_callback(len(plan.entries), 0, source_directory)

        return plan

    def _validate_request(self) -> None:
        if not self.root or not os.path.isdir(self.root):
            raise NormalizationError(
                "El directorio de origen no existe o no es accesible."
            )

        if self.mode == "copy":
            if not self.destination_root:
                raise NormalizationError("Debes indicar una carpeta de destino.")
            if _is_within(self.destination_root, self.root):
                raise NormalizationError(
                    "La carpeta de destino debe estar fuera del directorio de origen."
                )
            if os.path.exists(self.destination_root) and not os.path.isdir(
                self.destination_root
            ):
                raise NormalizationError(
                    "La ruta de destino existe, pero no es una carpeta."
                )
            try:
                os.makedirs(self.destination_root, exist_ok=True)
            except OSError as error:
                raise NormalizationError(
                    f"No se pudo crear la carpeta de destino: {error}"
                ) from error

    def _is_ignored(self, entry: os.DirEntry[str]) -> bool:
        name = entry.name
        if entry.is_dir(follow_symlinks=False):
            if name.casefold() in self._ignored_directories:
                return True
            return _normalized_path(entry.path) == self._output_directory
        return name.casefold() in self._ignored_files

    def _plan_directory(
        self,
        source_directory: str,
        target_directory: str,
        depth: int,
        plan: NormalizationPlan,
        queue: list[tuple[str, str, int]],
    ) -> None:
        try:
            with os.scandir(source_directory) as iterator:
                directory_entries = sorted(
                    iterator, key=lambda item: item.name.casefold()
                )
        except OSError as error:
            plan.errors.append(f"{source_directory}: {error}")
            return

        plan.scanned_directories += 1

        candidates: list[tuple[os.DirEntry[str], bool, str]] = []
        ignored_names: list[str] = []
        for entry in directory_entries:
            if self._is_ignored(entry):
                plan.ignored.append(entry.path)
                ignored_names.append(entry.name)
                continue
            is_directory = entry.is_dir(follow_symlinks=False)
            proposed = normalize_name(
                entry.name, is_directory=is_directory, rules=self.rules
            )
            candidates.append((entry, is_directory, proposed))

        sibling_names = tuple(entry.name for entry, _, _ in candidates)
        reserved: set[str] = set()

        if self.mode == "copy":
            # En una copia todo se escribe en el destino: hay que reservar lo
            # que ya existe allí para no sobrescribir nada.
            reserved.update(self._existing_target_names(target_directory))
        else:
            # En el renombrado, los nombres que no cambian siguen ocupados. Los
            # que podrían quedarse por una omisión también se reservan, igual
            # que los elementos ignorados que permanecen en la carpeta.
            sibling_names += tuple(ignored_names)
            reserved.update(name.casefold() for name in ignored_names)
            limit = max_name_length(target_directory, self.rules)
            for entry, _, proposed in candidates:
                if proposed == entry.name:
                    reserved.add(entry.name.casefold())
                elif utf16_length(proposed) > limit:
                    reserved.add(entry.name.casefold())

        for entry, is_directory, proposed in candidates:
            resolved = self._resolve_entry(
                entry=entry,
                is_directory=is_directory,
                proposed=proposed,
                target_directory=target_directory,
                reserved=reserved,
                sibling_names=sibling_names,
                plan=plan,
            )

            plan.entries.append(
                PlanEntry(
                    source_path=entry.path,
                    original_name=entry.name,
                    final_name=resolved.name,
                    is_directory=is_directory,
                    parent_source=source_directory,
                    parent_target=target_directory,
                    depth=depth,
                    skipped=resolved.skipped,
                    reviewed=resolved.reviewed,
                    review_reason=resolved.reason,
                    sibling_names=tuple(
                        name for name in sibling_names if name != entry.name
                    ),
                )
            )

            if is_directory:
                queue.append(
                    (
                        entry.path,
                        os.path.join(target_directory, resolved.name),
                        depth + 1,
                    )
                )

    def _existing_target_names(self, target_directory: str) -> set[str]:
        try:
            with os.scandir(target_directory) as iterator:
                return {entry.name.casefold() for entry in iterator}
        except OSError:
            return set()

    def _resolve_entry(
        self,
        *,
        entry: os.DirEntry[str],
        is_directory: bool,
        proposed: str,
        target_directory: str,
        reserved: set[str],
        sibling_names: tuple[str, ...],
        plan: NormalizationPlan,
    ) -> _ResolvedName:
        limit = max_name_length(target_directory, self.rules)

        if self.mode == "rename" and proposed == entry.name:
            # No hay nada que renombrar; no se revisa ni se reserva de nuevo.
            return _ResolvedName(proposed)

        # Colisiones deterministas: ``nombre (1).ext``, ``nombre (2).ext``...
        candidate = proposed
        counter = 1
        while candidate.casefold() in reserved and counter <= 9999:
            candidate = append_collision_suffix(
                proposed, counter, is_directory=is_directory, rules=self.rules
            )
            counter += 1
            plan.collisions_resolved += 1

        if utf16_length(candidate) <= limit:
            reserved.add(candidate.casefold())
            return _ResolvedName(candidate)

        reason = (
            f"El nombre propuesto tiene {utf16_length(candidate)} caracteres y "
            f"el límite disponible en esta ruta es de {limit}."
        )

        if self.resolver is None:
            reserved.add(candidate.casefold())
            return _ResolvedName(candidate, reviewed=True, reason=reason)

        decision = self.resolver(
            PlanEntry(
                source_path=entry.path,
                original_name=entry.name,
                final_name=candidate,
                is_directory=is_directory,
                parent_source=os.path.dirname(entry.path),
                parent_target=target_directory,
                sibling_names=tuple(
                    name for name in sibling_names if name != entry.name
                ),
            ),
            reason,
        )

        if decision.action == "cancel":
            raise NormalizationCancelled()

        if decision.action == "skip":
            reserved.add(entry.name.casefold())
            return _ResolvedName(entry.name, reviewed=True, skipped=True, reason=reason)

        chosen = (decision.name or "").strip()
        validation = validate_candidate(
            chosen,
            target_directory,
            is_directory=is_directory,
            siblings=sibling_names,
            own_name=entry.name,
            rules=self.rules,
        )
        if not validation.is_valid:
            plan.errors.append(
                f"{entry.path}: nombre manual rechazado ({validation.message}); se omite."
            )
            reserved.add(entry.name.casefold())
            return _ResolvedName(entry.name, reviewed=True, skipped=True, reason=reason)

        if chosen.casefold() == entry.name.casefold():
            reserved.add(entry.name.casefold())
            return _ResolvedName(entry.name, reviewed=True, skipped=True, reason=reason)

        if chosen.casefold() in reserved:
            counter = 1
            while chosen.casefold() in reserved and counter <= 9999:
                chosen = append_collision_suffix(
                    chosen, counter, is_directory=is_directory, rules=self.rules
                )
                counter += 1
                plan.collisions_resolved += 1
            if utf16_length(chosen) > limit:
                plan.errors.append(
                    f"{entry.path}: el nombre manual colisiona y no cabe en el límite; se omite."
                )
                reserved.add(entry.name.casefold())
                return _ResolvedName(
                    entry.name, reviewed=True, skipped=True, reason=reason
                )

        reserved.add(chosen.casefold())
        return _ResolvedName(chosen, reviewed=True, reason=reason)


class NormalizationApplier:
    """Aplica un plan confirmado y genera el diario de reversión."""

    def __init__(
        self,
        plan: NormalizationPlan,
        *,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.plan = plan
        self.progress_callback = progress_callback
        self._groups: list[dict[str, object]] = []
        self._copies: list[dict[str, str]] = []
        self._directories: list[dict[str, str]] = []

    def apply(self) -> ApplyResult:
        result = ApplyResult(skipped=len(self.plan.skipped_entries))

        try:
            if self.plan.mode == "rename":
                self._apply_rename(result)
            else:
                self._apply_copy(result)
        except Exception as error:
            result.completed = False
            result.errors.append(str(error))
        finally:
            if self._groups or self._copies or self._directories:
                try:
                    result.journal_path = self._write_journal(result)
                except OSError as error:
                    result.errors.append(f"No se pudo escribir el diario: {error}")

        return result

    # ------------------------------------------------------------------
    # Renombrado en el lugar
    # ------------------------------------------------------------------
    def _apply_rename(self, result: ApplyResult) -> None:
        groups: dict[str, list[PlanEntry]] = {}
        for entry in self.plan.changes:
            groups.setdefault(entry.parent_source, []).append(entry)

        # De más profundo a más superficial: así las rutas originales de los
        # padres siguen siendo válidas cuando se renombran sus hijos.
        ordered_groups = sorted(
            groups.items(), key=lambda item: _path_depth(item[0]), reverse=True
        )

        total = len(self.plan.changes)
        processed = 0

        for parent, entries in ordered_groups:
            operations = self._rename_group(parent, entries, result)
            if operations:
                self._groups.append({"parent": parent, "operations": operations})
            processed += len(entries)
            if self.progress_callback:
                self.progress_callback(processed, total, parent)

    def _rename_group(
        self, parent: str, entries: list[PlanEntry], result: ApplyResult
    ) -> list[dict[str, str]]:
        source_names = {entry.original_name.casefold() for entry in entries}
        needs_temporary_names = any(
            (
                entry.final_name.casefold() in source_names
                and entry.final_name.casefold() != entry.original_name.casefold()
            )
            or (
                os.path.normcase(entry.original_name)
                == os.path.normcase(entry.final_name)
                and entry.original_name != entry.final_name
            )
            for entry in entries
        )

        if not needs_temporary_names:
            operations: list[dict[str, str]] = []
            for entry in entries:
                original = os.path.join(parent, entry.original_name)
                target = os.path.join(parent, entry.final_name)
                if not os.path.lexists(original):
                    result.errors.append(
                        f"{original}: ya no existe; se omite el renombrado."
                    )
                    continue
                if os.path.lexists(target):
                    result.errors.append(
                        f"{target}: ya existe; se omite el renombrado."
                    )
                    continue
                try:
                    os.rename(original, target)
                except OSError as error:
                    result.errors.append(f"{original}: {error}")
                    continue
                result.renamed += 1
                operations.append(
                    {"original": entry.original_name, "result": entry.final_name}
                )
            return operations

        # Dos fases para resolver intercambios y cambios de mayúsculas.
        moved: list[tuple[PlanEntry, str]] = []
        try:
            for entry in entries:
                original = os.path.join(parent, entry.original_name)
                if not os.path.lexists(original):
                    result.errors.append(
                        f"{original}: ya no existe; se omite el renombrado."
                    )
                    continue
                temporary = self._temporary_name(parent)
                os.rename(original, temporary)
                moved.append((entry, temporary))
        except OSError as error:
            for entry, temporary in reversed(moved):
                try:
                    os.rename(temporary, os.path.join(parent, entry.original_name))
                except OSError:
                    pass
            result.errors.append(f"{parent}: {error}")
            return []

        operations: list[dict[str, str]] = []
        completed: list[tuple[str, str]] = []
        try:
            for entry, temporary in moved:
                target = os.path.join(parent, entry.final_name)
                if os.path.lexists(target):
                    raise FileExistsError(f"{target}: ya existe")
                os.rename(temporary, target)
                completed.append((temporary, target))
                result.renamed += 1
                operations.append(
                    {"original": entry.original_name, "result": entry.final_name}
                )
        except OSError as error:
            for temporary, target in reversed(completed):
                try:
                    os.rename(target, temporary)
                except OSError:
                    pass
            for entry, temporary in reversed(moved):
                try:
                    os.rename(temporary, os.path.join(parent, entry.original_name))
                except OSError:
                    pass
            result.errors.append(f"{parent}: {error}")
            return []

        return operations

    def _temporary_name(self, parent: str) -> str:
        for _ in range(100):
            candidate = os.path.join(parent, f"~n{uuid.uuid4().hex[:6]}")
            if not os.path.lexists(candidate):
                return candidate
        raise OSError(f"No se pudo generar un nombre temporal en {parent}")

    # ------------------------------------------------------------------
    # Copia normalizada
    # ------------------------------------------------------------------
    def _apply_copy(self, result: ApplyResult) -> None:
        total = len(self.plan.entries)
        for index, entry in enumerate(self.plan.entries, start=1):
            if self.progress_callback:
                self.progress_callback(index, total, entry.source_path)

            target = entry.target_path
            try:
                if entry.is_directory:
                    if os.path.isdir(target):
                        continue
                    os.makedirs(target, exist_ok=False)
                    result.created_directories += 1
                    self._directories.append(
                        {"source": entry.source_path, "result": target}
                    )
                else:
                    if os.path.lexists(target):
                        result.errors.append(
                            f"{target}: ya existe; se omite la copia."
                        )
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copy2(entry.source_path, target)
                    result.copied_files += 1
                    self._copies.append(
                        {"source": entry.source_path, "result": target}
                    )
            except OSError as error:
                result.errors.append(f"{entry.source_path}: {error}")

    # ------------------------------------------------------------------
    # Diario
    # ------------------------------------------------------------------
    def _write_journal(self, result: ApplyResult) -> str:
        directory = os.path.join(os.getcwd(), config.OUTPUT_DIRECTORY)
        os.makedirs(directory, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"normalizacion-{stamp}"
        path = os.path.join(directory, f"{base}.json")
        counter = 1
        while os.path.exists(path):
            path = os.path.join(directory, f"{base} ({counter}).json")
            counter += 1

        payload = {
            "version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "mode": self.plan.mode,
            "root": self.plan.root,
            "destination": self.plan.destination_root,
            "completed": result.completed,
            "renamed": result.renamed,
            "copied_files": result.copied_files,
            "created_directories": result.created_directories,
            "groups": self._groups,
            "copies": self._copies,
            "directories": self._directories,
            "errors": result.errors,
        }

        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4, ensure_ascii=False)

        return path


class NormalizationUndo:
    """Revierte una operación a partir de su diario."""

    def __init__(self, journal_path: str) -> None:
        self.journal_path = journal_path

    def undo(self) -> UndoResult:
        try:
            with open(self.journal_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise NormalizationError(f"No se pudo leer el diario: {error}") from error

        result = UndoResult()
        mode = payload.get("mode")

        if mode == "rename":
            self._undo_rename(payload.get("groups", []), result)
        else:
            self._undo_copy(payload, result)

        return result

    def _undo_rename(
        self, groups: list[dict[str, object]], result: UndoResult
    ) -> None:
        # Los grupos se guardaron de hijo a padre; se revierten de padre a hijo
        # para que las rutas originales vuelvan a ser válidas.
        for group in reversed(groups):
            parent = str(group.get("parent", ""))
            operations = group.get("operations", [])
            if not isinstance(operations, list) or not os.path.isdir(parent):
                if operations:
                    result.errors.append(
                        f"{parent}: la carpeta ya no existe; no se pudo revertir."
                    )
                continue

            moved: list[tuple[dict[str, object], str]] = []
            group_results = {
                str(operation.get("result", "")).casefold()
                for operation in operations
                if isinstance(operation, dict)
            }
            for operation in operations:
                if not isinstance(operation, dict):
                    continue
                original_name = str(operation.get("original", ""))
                result_name = str(operation.get("result", ""))
                if not original_name or not result_name:
                    continue

                current = os.path.join(parent, result_name)
                original = os.path.join(parent, original_name)

                if not os.path.lexists(current) and os.path.lexists(original):
                    continue  # Ya estaba revertido.
                if not os.path.lexists(current):
                    result.errors.append(f"{current}: no existe; no se pudo revertir.")
                    continue
                if (
                    os.path.lexists(original)
                    and original_name.casefold() not in group_results
                ):
                    # Un archivo ajeno ocupa el nombre original: no se toca.
                    result.errors.append(
                        f"{original}: ya existe; hay un conflicto y no se revierte."
                    )
                    continue

                temporary = self._temporary_name(parent)
                try:
                    os.rename(current, temporary)
                except OSError as error:
                    result.errors.append(f"{current}: {error}")
                    continue
                moved.append((operation, temporary))

            for operation, temporary in moved:
                original = os.path.join(parent, str(operation.get("original", "")))
                try:
                    os.rename(temporary, original)
                    result.restored += 1
                except OSError as error:
                    result.errors.append(f"{original}: {error}")

    def _undo_copy(self, payload: dict[str, object], result: UndoResult) -> None:
        copies = payload.get("copies", [])
        directories = payload.get("directories", [])
        copy_operations = copies if isinstance(copies, list) else []
        directory_operations = directories if isinstance(directories, list) else []

        for operation in reversed(copy_operations):
            target = str(operation.get("result", ""))
            try:
                if os.path.isfile(target):
                    os.remove(target)
                    result.removed_files += 1
            except OSError as error:
                result.errors.append(f"{target}: {error}")

        for operation in reversed(directory_operations):
            target = str(operation.get("result", ""))
            try:
                if os.path.isdir(target):
                    os.rmdir(target)
                    result.removed_directories += 1
            except OSError as error:
                # Una carpeta con contenido ajeno se conserva.
                result.errors.append(f"{target}: {error}")

    def _temporary_name(self, parent: str) -> str:
        for _ in range(100):
            candidate = os.path.join(parent, f"~u{uuid.uuid4().hex[:6]}")
            if not os.path.lexists(candidate):
                return candidate
        raise OSError(f"No se pudo generar un nombre temporal en {parent}")

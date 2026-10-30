"""
Reglas puras de normalización de nombres de archivos y carpetas.

El objetivo es que los nombres sean portables y legibles en Windows, en
medios ópticos y en herramientas que interpretan mal ciertos caracteres.
Todas las funciones de este módulo son deterministas y no tocan el disco,
de modo que puedan probarse y reutilizarse desde cualquier interfaz.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

import config


# Nombres reservados por Windows, tanto para archivos como para carpetas.
RESERVED_WINDOWS_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)

# Extensiones compuestas que deben conservarse completas al separar el nombre.
COMPOUND_EXTENSIONS: tuple[str, ...] = (
    "tar.gz",
    "tar.bz2",
    "tar.xz",
    "tar.zst",
    "tar.lz",
    "tar.lzma",
    "tar.lz4",
    "tar.br",
    "tar.sz",
    "tar.z",
    "user.js",
    "min.js",
    "min.css",
    "d.ts",
)

_COMPOUND_EXTENSIONS_SORTED: tuple[str, ...] = tuple(
    sorted(COMPOUND_EXTENSIONS, key=len, reverse=True)
)

# Caracteres prohibidos por Windows y caracteres de control.
INVALID_CHARACTERS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Letras que no se descomponen con NFKD y que conviene transliterar.
_TRANSLITERATIONS = str.maketrans(
    {
        "ß": "ss",
        "ẞ": "SS",
        "æ": "ae",
        "Æ": "AE",
        "œ": "oe",
        "Œ": "OE",
        "ø": "o",
        "Ø": "O",
        "ł": "l",
        "Ł": "L",
        "đ": "d",
        "Đ": "D",
        "ð": "d",
        "Ð": "D",
        "þ": "th",
        "Þ": "Th",
        "ı": "i",
        "ħ": "h",
        "Ħ": "H",
        "ŧ": "t",
        "Ŧ": "T",
    }
)

# Marcadores temporales para proteger la eñe durante la descomposición Unicode.
_N_TILDE_LOWER = "\ue000"
_N_TILDE_UPPER = "\ue001"


@dataclass(frozen=True)
class NormalizationRules:
    """Parámetros que controlan el resultado de la normalización."""

    preserve_extensions: bool = config.NORMALIZATION_PRESERVE_EXTENSIONS
    keep_word_separators: bool = config.NORMALIZATION_KEEP_WORD_SEPARATORS
    fallback_name: str = config.NORMALIZATION_FALLBACK_NAME
    max_component_length: int = config.NORMALIZATION_MAX_COMPONENT_LENGTH
    max_path_length: int = config.NORMALIZATION_MAX_PATH_LENGTH

    @property
    def separators(self) -> str:
        return "_-" if self.keep_word_separators else ""


DEFAULT_RULES = NormalizationRules()


@dataclass(frozen=True)
class CandidateValidation:
    """Resultado de validar un nombre propuesto por la persona usuaria."""

    is_valid: bool
    message: str
    length: int
    max_length: int


def utf16_length(text: str) -> int:
    """Longitud en unidades UTF-16, que es la que cuenta Windows."""
    return len(text.encode("utf-16-le")) // 2


def strip_diacritics(text: str) -> str:
    """
    Elimina tildes, diéresis y demás decoradores ortográficos conservando la
    letra base. La eñe se preserva porque distingue palabras en español.
    """
    protected = text.replace("ñ", _N_TILDE_LOWER).replace("Ñ", _N_TILDE_UPPER)
    protected = protected.translate(_TRANSLITERATIONS)
    decomposed = unicodedata.normalize("NFKD", protected)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return without_marks.replace(_N_TILDE_LOWER, "ñ").replace(_N_TILDE_UPPER, "Ñ")


def split_extension(name: str) -> tuple[str, str]:
    """
    Separa el nombre de su extensión, reconociendo extensiones compuestas
    como ``.tar.gz``. Devuelve ``(raiz, extension)``; la extensión incluye
    el punto inicial y puede ser una cadena vacía.
    """
    lowered = name.lower()
    for compound in _COMPOUND_EXTENSIONS_SORTED:
        suffix = f".{compound}"
        if lowered.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)], name[-len(suffix):]

    stem, extension = os.path.splitext(name)
    if not extension or extension == ".":
        return name, ""
    return stem, extension


def _sanitize_fragment(
    text: str, rules: NormalizationRules, *, keep_dots: bool = False
) -> str:
    """
    Conserva únicamente letras, números, espacios, paréntesis y los
    separadores permitidos. Todo lo demás se descarta sin interpretarlo.
    """
    normalized = strip_diacritics(text).replace("\u00a0", " ")
    kept: list[str] = []

    for character in normalized:
        if character.isalnum():
            kept.append(character)
        elif character.isspace():
            kept.append(" ")
        elif character in "()":
            kept.append(character)
        elif character in rules.separators:
            kept.append(character)
        elif keep_dots and character == ".":
            kept.append(character)

    result = re.sub(r" {2,}", " ", "".join(kept))
    result = result.strip()
    return result.strip(f" {rules.separators}")


def is_reserved_name(name: str) -> bool:
    """Indica si el nombre corresponde a un dispositivo reservado de Windows."""
    base = name.split(".", 1)[0].strip().upper()
    return base in RESERVED_WINDOWS_NAMES


def normalize_name(
    name: str,
    *,
    is_directory: bool = False,
    rules: NormalizationRules | None = None,
) -> str:
    """
    Devuelve el nombre normalizado según las reglas del proyecto.

    - Elimina puntos, comas, barras y cualquier símbolo salvo los paréntesis.
    - Conserva los separadores de palabra configurados (``_`` y ``-``).
    - Sustituye los decoradores ortográficos por su letra base.
    - Colapsa espacios repetidos y recorta espacios y separadores sobrantes.
    - Mantiene la extensión (incluidas las compuestas) cuando está habilitado.
    """
    rules = rules or DEFAULT_RULES
    source = name or ""

    if rules.preserve_extensions and not is_directory:
        stem, extension = split_extension(source)
        clean_stem = _sanitize_fragment(stem, rules)
        clean_extension = _sanitize_fragment(
            extension.lstrip("."), rules, keep_dots=True
        ).replace(" ", "")
        if clean_stem and clean_extension:
            result = f"{clean_stem}.{clean_extension}"
        else:
            result = clean_stem or clean_extension
    else:
        result = _sanitize_fragment(source, rules)

    if not any(character.isalnum() for character in result):
        result = rules.fallback_name

    if is_reserved_name(result):
        result = f"_{result}"

    return result


def max_name_length(
    parent_path: str = "", rules: NormalizationRules | None = None
) -> int:
    """
    Calcula el presupuesto de caracteres para un componente dentro de
    ``parent_path``: el menor entre el límite del sistema de archivos y el
    espacio que resta de la ruta completa.
    """
    rules = rules or DEFAULT_RULES
    parent = os.path.abspath(parent_path) if parent_path else ""
    available = rules.max_path_length - utf16_length(parent) - 1
    return max(1, min(rules.max_component_length, available))


def validate_candidate(
    candidate: str,
    parent_path: str = "",
    *,
    is_directory: bool = False,
    siblings: Iterable[str] = (),
    own_name: str | None = None,
    rules: NormalizationRules | None = None,
) -> CandidateValidation:
    """
    Valida un nombre propuesto antes de renombrar o copiar. No modifica el
    valor recibido: la decisión final siempre es de la persona usuaria.
    """
    rules = rules or DEFAULT_RULES
    name = candidate or ""
    limit = max_name_length(parent_path, rules)
    length = utf16_length(name)

    def invalid(message: str) -> CandidateValidation:
        return CandidateValidation(False, message, length, limit)

    if not name:
        return invalid("El nombre no puede quedar vacío.")

    if name in {".", ".."}:
        return invalid("El nombre no puede ser '.' ni '..'.")

    if name != name.rstrip(" ."):
        return invalid("El nombre no puede terminar en espacio ni en punto.")

    if INVALID_CHARACTERS_PATTERN.search(name):
        return invalid('Contiene caracteres no válidos: < > : " / \\ | ? *')

    if not any(character.isalnum() for character in name):
        return invalid("Debe contener al menos una letra o un número.")

    if is_reserved_name(name):
        return invalid("Es un nombre reservado por Windows (CON, PRN, AUX, NUL, COM1-9, LPT1-9).")

    if length > limit:
        return invalid(
            f"Excede el límite disponible: {length} de {limit} caracteres."
        )

    occupied = {
        sibling.casefold()
        for sibling in siblings
        if sibling.casefold() != (own_name or "").casefold()
    }
    if name.casefold() in occupied:
        return invalid("Ya existe otro elemento con ese nombre en la misma carpeta.")

    if is_directory and "." in name:
        # No es un error, pero se avisa porque las carpetas no usan extensión.
        return CandidateValidation(
            True,
            "El nombre es válido. Recuerda que las carpetas conservarán el punto.",
            length,
            limit,
        )

    return CandidateValidation(True, "El nombre es válido.", length, limit)


def append_collision_suffix(
    name: str,
    counter: int,
    *,
    is_directory: bool = False,
    rules: NormalizationRules | None = None,
) -> str:
    """
    Agrega el sufijo determinista `` (n)`` antes de la extensión, igual que
    el resto de nombres generados por la aplicación.
    """
    rules = rules or DEFAULT_RULES
    suffix = f" ({counter})"
    if is_directory or not rules.preserve_extensions:
        return f"{name}{suffix}"

    stem, extension = split_extension(name)
    return f"{stem}{suffix}{extension}"

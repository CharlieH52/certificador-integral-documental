"""
Compila y empaqueta la aplicación con ``flet pack``.

``flet pack`` usa PyInstaller por debajo, así que no necesita Visual Studio
Build Tools ni compila el runner de Flutter. El resultado es un ejecutable
único en ``dist/CERTIFICADOR_INTEGRIDAD.exe``.

Uso:
    python build.py            # ejecutable único para Windows
    python build.py --clean    # limpia la caché de PyInstaller antes de compilar
    python build.py --onedir   # genera una carpeta en lugar de un único .exe
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ARTIFACT_NAME = "CERTIFICADOR_INTEGRIDAD"
PRODUCT_NAME = "Certificador de Integridad Documental"
DESCRIPTION = "Certificación de integridad documental con huella hash SHA-256"
BUILD_VERSION = "1.0.0"
FILE_VERSION = "1.0.0.0"
OUTPUT_DIRECTORY = "dist"

# Argumentos que se pasan directamente a PyInstaller. Se envían uno por uno
# porque ``flet pack`` los recibe con ``--pyinstaller-build-args`` y argparse
# interpretaría los que empiezan por guion como opciones de Flet.
PYINSTALLER_ARGUMENTS = (
    "--collect-all",
    "flet",
    "--exclude-module",
    "tkinter",
    "--exclude-module",
    "_tkinter",
    "--exclude-module",
    "Tkinter",
)


def find_flet_command() -> list[str]:
    """Localiza el CLI de Flet en el entorno de Python actual."""
    executable_name = "flet.exe" if sys.platform == "win32" else "flet"
    beside_python = Path(sys.executable).parent / executable_name
    if beside_python.is_file():
        return [str(beside_python)]

    in_path = shutil.which("flet")
    if in_path:
        return [in_path]

    try:
        import flet_cli.cli  # noqa: F401
    except ImportError:
        print(
            "[ERROR] No se encontró Flet. Activa el entorno virtual e instala "
            "las dependencias con: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # ``flet_cli`` no expone un módulo ejecutable con ``-m``; se invoca su
    # función principal directamente.
    return [sys.executable, "-c", "from flet_cli.cli import main; main()"]


def build_arguments(clean: bool, onedir: bool) -> list[str]:
    """Construye los argumentos de ``flet pack``."""
    arguments = [
        "pack",
        "main.py",
        "--name",
        ARTIFACT_NAME,
        "--distpath",
        OUTPUT_DIRECTORY,
        "--product-name",
        PRODUCT_NAME,
        "--file-description",
        DESCRIPTION,
        "--product-version",
        BUILD_VERSION,
        "--file-version",
        FILE_VERSION,
    ]

    for pyinstaller_argument in PYINSTALLER_ARGUMENTS:
        arguments.append(f"--pyinstaller-build-args={pyinstaller_argument}")
    if clean:
        arguments.append("--pyinstaller-build-args=--clean")

    if onedir:
        arguments.append("--onedir")
    arguments.append("-y")
    return arguments


def build_exe(clean: bool = False, onedir: bool = False) -> int:
    base_dir = Path(__file__).parent.resolve()
    entry_point = base_dir / "main.py"

    if not entry_point.is_file():
        print(
            f"[ERROR] No se encontró el punto de entrada: {entry_point}",
            file=sys.stderr,
        )
        return 1

    command = find_flet_command() + build_arguments(clean, onedir)
    print("[INFO] Compilando con flet pack (PyInstaller)...")
    print(f"[INFO] Comando: {' '.join(command)}")

    # Evita problemas de codificación en consolas Windows que no usan UTF-8.
    environment = os.environ.copy()
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment["FLET_CLI_NO_RICH_OUTPUT"] = "1"

    try:
        result = subprocess.run(
            command, cwd=base_dir, check=False, env=environment
        )
    except KeyboardInterrupt:
        print("\n[INFO] Compilación cancelada por la persona usuaria.")
        return 130
    except OSError as error:
        print(f"[ERROR] No se pudo ejecutar Flet: {error}", file=sys.stderr)
        return 1

    if result.returncode != 0:
        print(
            f"\n[ERROR] La compilación falló con el código {result.returncode}.",
            file=sys.stderr,
        )
        return result.returncode

    output_path = base_dir / OUTPUT_DIRECTORY
    print(f"\n[OK] Paquete generado en: {output_path}")
    if onedir:
        executable = output_path / ARTIFACT_NAME / f"{ARTIFACT_NAME}.exe"
        print(f"[OK] Ejecutable: {executable}")
    else:
        print(f"[OK] Ejecutable: {output_path / f'{ARTIFACT_NAME}.exe'}")
    return 0


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compila y empaqueta la aplicación con flet pack (PyInstaller)."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Elimina la caché de compilación de PyInstaller antes de empezar.",
    )
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Genera una carpeta con el ejecutable en lugar de un único .exe.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    options = parse_arguments()
    raise SystemExit(build_exe(options.clean, options.onedir))

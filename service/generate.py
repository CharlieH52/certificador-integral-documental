"""
Módulo de generación de certificaciones y cálculo de huellas hash.
"""

import os
import json
import hashlib
import shutil
from typing import Any, Callable
from collections import defaultdict

import config
from service.exporter import TextExporter
from repository import (
    CertificationRecord,
    CertifiedFileRecord,
    ExtensionSummaryRecord,
    SQLiteRepository,
)


class CertifyMaker:
    """
    Motor de certificación de integridad de archivos.
    Calcula huellas criptográficas SHA-256 de forma nativa en Python,
    extrae métricas de almacenamiento y permite persistir en JSON, SQLite3 y Texto.
    """

    def __init__(
        self,
        target_path: str,
        output_file_name: str,
        save_json: bool = config.SAVE_JSON_CERTIFICATIONS,
        save_sqlite: bool = config.SAVE_SQLITE_CERTIFICATIONS,
        progress_callback: Callable[[int, int, str], None] | None = None
    ) -> None:
        self.target_path = os.path.abspath(target_path.strip().strip('"').strip("'"))
        self.output_file_name = output_file_name.strip()
        self.save_json = save_json
        self.save_sqlite = save_sqlite
        self.progress_callback = progress_callback

        self.working_path = os.path.join(os.getcwd(), config.OUTPUT_DIRECTORY)
        self.__check_output_directory()

        self.saved_json_path = os.path.join(self.working_path, f"{self.output_file_name}.json")
        self.saved_txt_path = os.path.join(self.working_path, f"{self.output_file_name}.txt")

        # Métricas de unidad
        self.mount_point = self.__get_mount_point(self.target_path)
        self.drive_total_bytes, self.drive_free_bytes = self.__get_drive_storage_info(
            self.target_path, self.mount_point
        )

        # Estructuras de datos
        self.current_data: list[dict[str, Any]] = []
        self.detailed_file_records: list[CertifiedFileRecord] = []
        self.extensions_counter: defaultdict[str, int] = defaultdict(int)
        self.total_analyzed_bytes: int = 0
        self.errors_log: list[tuple[str, str]] = []

        # Ejecutar el escaneo y cálculo de hash nativo
        self.__execute_native_hashing()

        # Guardar en JSON según la constante booleana
        if self.save_json:
            self.__save_json_file(self.current_data, self.saved_json_path)

        # Guardar en base de datos SQLite3 según la constante booleana
        if self.save_sqlite:
            self.__save_sqlite_database()

    def __check_output_directory(self) -> None:
        """Crea el directorio de salida si no existe."""
        if not os.path.exists(self.working_path):
            os.makedirs(self.working_path, exist_ok=True)

    def __get_mount_point(self, path: str) -> str:
        """Obtiene la letra de unidad (ej. 'C:') o raíz del punto de montaje."""
        drive, _ = os.path.splitdrive(path)
        if drive:
            return drive.upper()
        return path

    def __get_drive_storage_info(
        self, path: str, mount_point: str
    ) -> tuple[int | None, int | None]:
        """
        Obtiene el espacio total y libre de la unidad de almacenamiento de forma limpia
        y nativa sin dependencias COM/WMI que provoquen excepciones IUnknown en hilos.
        """
        total_size: int | None = None
        free_size: int | None = None

        try:
            drive_root = mount_point + "\\" if (mount_point and not mount_point.endswith("\\")) else path
            usage = shutil.disk_usage(drive_root)
            total_size = usage.total
            free_size = usage.free
        except Exception:
            try:
                usage = shutil.disk_usage(path)
                total_size = usage.total
                free_size = usage.free
            except Exception:
                pass

        return total_size, free_size

    def __format_bytes(self, size_in_bytes: int | None) -> str:
        """Convierte bytes a formato legible (B, KB, MB, GB, TB, PB)."""
        if size_in_bytes is None or size_in_bytes < 0:
            return "No disponible"

        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size_in_bytes)

        for unit in units:
            if value < 1024:
                return f"{round(value, 2)} {unit}"
            value /= 1024

        return f"{round(value, 2)} PB"

    def get_logical_drive_size(self) -> str:
        """Retorna el tamaño total formateado de la unidad."""
        return self.__format_bytes(self.drive_total_bytes)

    def get_logical_drive_free_space(self) -> str:
        """Retorna el espacio libre formateado de la unidad."""
        return self.__format_bytes(self.drive_free_bytes)

    def get_logical_drive_used_space(self) -> str:
        """Retorna el espacio utilizado de la unidad (Total - Libre)."""
        if self.drive_total_bytes is not None and self.drive_free_bytes is not None:
            used = max(0, self.drive_total_bytes - self.drive_free_bytes)
            return self.__format_bytes(used)
        return "No disponible"

    def get_used_space(self) -> str:
        """Retorna la suma total de los bytes de los archivos analizados."""
        return self.__format_bytes(self.total_analyzed_bytes)

    def get_total_files_count(self) -> int:
        """Retorna el número total de archivos auditados exitosamente."""
        return len(self.current_data)

    def get_file_extension_list(self) -> list[dict[str, Any]]:
        """Retorna el conteo clasificado por extensión de archivo."""
        return [
            {"extension": ext, "conteo": count}
            for ext, count in self.extensions_counter.items()
        ]

    def __calculate_file_sha256(self, file_path: str) -> str:
        """Calcula el hash SHA-256 de un archivo en bloques de 64 KB."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(config.HASH_CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest().upper()

    def __execute_native_hashing(self) -> None:
        """
        Escanea recursivamente el directorio objetivo, computando hashes SHA-256,
        tamaños y extensiones en una sola pasada.
        """
        all_file_paths: list[str] = []

        # Paso 1: Descubrimiento de archivos
        for root, _, files in os.walk(self.target_path):
            for file in files:
                all_file_paths.append(os.path.join(root, file))

        total_files = len(all_file_paths)

        # Paso 2: Hashing y recolección de estadísticas
        for idx, file_path in enumerate(all_file_paths, start=1):
            if self.progress_callback:
                self.progress_callback(idx, total_files, file_path)

            try:
                # Tamaño de archivo
                file_size = os.path.getsize(file_path)
                self.total_analyzed_bytes += file_size

                # Extensión
                _, ext = os.path.splitext(file_path)
                clean_ext = ext.lstrip(".").lower() if ext else "SIN_EXTENSION"
                self.extensions_counter[clean_ext] += 1

                # Hash SHA256
                file_hash = self.__calculate_file_sha256(file_path)

                self.current_data.append({
                    "Algorithm": config.DEFAULT_HASH_ALGORITHM,
                    "Hash": file_hash,
                    "Path": file_path
                })

                # Registro para repositorio estructurado
                self.detailed_file_records.append(
                    CertifiedFileRecord(
                        file_path=file_path,
                        file_hash=file_hash,
                        file_size_bytes=file_size,
                        file_extension=clean_ext
                    )
                )
            except Exception as e:
                self.errors_log.append((file_path, str(e)))

    def __save_json_file(self, data: list[dict[str, Any]], target_file_path: str) -> None:
        """Guarda la lista de hashes en formato JSON."""
        try:
            with open(target_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.errors_log.append((target_file_path, f"Error al guardar JSON: {e}"))

    def __save_sqlite_database(self) -> None:
        """Persiste la certificación y el detalle de archivos en la base de datos SQLite3."""
        try:
            repo = SQLiteRepository()
            master_record = CertificationRecord(
                certification_name=self.output_file_name,
                target_path=self.target_path,
                total_files=self.get_total_files_count(),
                total_size_bytes=self.total_analyzed_bytes,
                formatted_size=self.get_used_space(),
                drive_total_space=self.get_logical_drive_size(),
                drive_used_space=self.get_logical_drive_used_space(),
                drive_free_space=self.get_logical_drive_free_space(),
                hash_algorithm=config.DEFAULT_HASH_ALGORITHM
            )

            extensions_records = [
                ExtensionSummaryRecord(extension=ext, file_count=count)
                for ext, count in self.extensions_counter.items()
            ]

            repo.save_certification(
                certification=master_record,
                files=self.detailed_file_records,
                extensions=extensions_records
            )
        except Exception as e:
            self.errors_log.append((config.SQLITE_DB_NAME, f"Error al guardar en SQLite: {e}"))

    def export_text_report(self, target_txt_path: str | None = None) -> str:
        """
        Genera y exporta manualmente el reporte de resumen en archivo de texto plano (.txt).
        Retorna la ruta absoluta del archivo exportado.
        """
        dest_path = target_txt_path or self.saved_txt_path
        TextExporter.export_summary(
            file_path=dest_path,
            total_files=self.get_total_files_count(),
            extensions_data=self.get_file_extension_list(),
            total_drive_space=self.get_logical_drive_size(),
            used_drive_space=self.get_logical_drive_used_space(),
            free_drive_space=self.get_logical_drive_free_space(),
            analyzed_files_size=self.get_used_space(),
            analyzed_path=self.target_path
        )
        return dest_path
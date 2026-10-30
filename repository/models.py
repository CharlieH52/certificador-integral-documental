"""
Modelos de datos para el repositorio de certificaciones SQLite3.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CertificationRecord:
    """
    Modelo representativo del registro maestro de una certificación.
    """
    certification_name: str
    target_path: str
    total_files: int
    total_size_bytes: int
    formatted_size: str
    drive_total_space: str
    drive_used_space: str
    drive_free_space: str
    hash_algorithm: str = "SHA256"
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class CertifiedFileRecord:
    """
    Modelo representativo del registro de un archivo individual auditado.
    """
    file_path: str
    file_hash: str
    file_size_bytes: int
    file_extension: str
    certification_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class ExtensionSummaryRecord:
    """
    Modelo representativo del resumen agrupado por extensión de archivo.
    """
    extension: str
    file_count: int
    certification_id: Optional[int] = None
    id: Optional[int] = None

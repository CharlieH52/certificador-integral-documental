"""
Repositorio SQLite3 para persistencia de certificaciones de archivos.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any

import config
from repository.models import (
    CertificationRecord,
    CertifiedFileRecord,
    ExtensionSummaryRecord,
)


class SQLiteRepository:
    """
    Gestor de base de datos SQLite3 para el almacenamiento de certificaciones.
    Maneja la inicialización del esquema y operaciones atómicas de guardado y consulta.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            self.db_path = os.path.join(os.getcwd(), config.SQLITE_DB_NAME)
        else:
            self.db_path = db_path

        # Inicializa las tablas y el archivo si no existen
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Crea una conexión a la base de datos con soporte para claves foráneas."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """
        Inicializa el archivo .sqlite3 creando las tablas e índices necesarios
        si aún no se encuentran presentes.
        """
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Tabla Maestra de Certificaciones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS certifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    certification_name TEXT NOT NULL UNIQUE,
                    target_path TEXT NOT NULL,
                    total_files INTEGER NOT NULL,
                    total_size_bytes INTEGER NOT NULL,
                    formatted_size TEXT NOT NULL,
                    drive_total_space TEXT NOT NULL,
                    drive_used_space TEXT NOT NULL,
                    drive_free_space TEXT NOT NULL,
                    hash_algorithm TEXT NOT NULL DEFAULT 'SHA256',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Tabla de Detalle de Archivos Hasheados
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS certified_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    certification_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    file_extension TEXT NOT NULL,
                    FOREIGN KEY (certification_id) REFERENCES certifications(id) ON DELETE CASCADE
                );
            """)

            # 3. Tabla de Resumen por Formatos y Extensiones
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS certification_extensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    certification_id INTEGER NOT NULL,
                    extension TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    FOREIGN KEY (certification_id) REFERENCES certifications(id) ON DELETE CASCADE
                );
            """)

            # Índices de optimización de búsquedas
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_certified_files_cert_id
                ON certified_files(certification_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_certified_files_hash
                ON certified_files(file_hash);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cert_extensions_cert_id
                ON certification_extensions(certification_id);
            """)

            conn.commit()

    def save_certification(
        self,
        certification: CertificationRecord,
        files: List[CertifiedFileRecord],
        extensions: List[ExtensionSummaryRecord],
    ) -> int:
        """
        Inserta la certificación completa (maestro + detalle de archivos + extensiones)
        dentro de una única transacción atómica.

        :return: ID de la certificación insertada.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Si ya existe una certificación con el mismo nombre, eliminarla para reemplazo limpio
            cursor.execute(
                "DELETE FROM certifications WHERE certification_name = ?;",
                (certification.certification_name,)
            )

            # Insertar registro maestro
            cursor.execute("""
                INSERT INTO certifications (
                    certification_name,
                    target_path,
                    total_files,
                    total_size_bytes,
                    formatted_size,
                    drive_total_space,
                    drive_used_space,
                    drive_free_space,
                    hash_algorithm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                certification.certification_name,
                certification.target_path,
                certification.total_files,
                certification.total_size_bytes,
                certification.formatted_size,
                certification.drive_total_space,
                certification.drive_used_space,
                certification.drive_free_space,
                certification.hash_algorithm,
            ))

            cert_id = cursor.lastrowid
            if cert_id is None:
                raise RuntimeError("No se pudo obtener el ID de la certificación insertada.")

            # Inserción en lote de archivos certificados
            file_rows = [
                (cert_id, f.file_path, f.file_hash, f.file_size_bytes, f.file_extension)
                for f in files
            ]
            cursor.executemany("""
                INSERT INTO certified_files (
                    certification_id,
                    file_path,
                    file_hash,
                    file_size_bytes,
                    file_extension
                ) VALUES (?, ?, ?, ?, ?)
            """, file_rows)

            # Inserción en lote de resumen de extensiones
            ext_rows = [
                (cert_id, e.extension, e.file_count)
                for e in extensions
            ]
            cursor.executemany("""
                INSERT INTO certification_extensions (
                    certification_id,
                    extension,
                    file_count
                ) VALUES (?, ?, ?)
            """, ext_rows)

            conn.commit()
            return cert_id

    def get_all_certifications(self) -> List[Dict[str, Any]]:
        """Retorna todas las certificaciones registradas ordenadas por fecha reciente."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM certifications ORDER BY id DESC;")
            return [dict(row) for row in cursor.fetchall()]

    def get_certification_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Busca una certificación por su nombre único."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM certifications WHERE certification_name = ?;", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

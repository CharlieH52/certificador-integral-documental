"""
Servicio de exportación de reportes a texto plano.
"""

import os
from typing import Any


class TextExporter:
    """
    Exportador exclusivo a texto plano (.txt) con las métricas de certificación:
    - Archivos totales
    - Formatos y cantidades de archivos
    - Espacio total, libre y utilizado de la unidad analizada
    """

    @staticmethod
    def export_summary(
        file_path: str,
        total_files: int,
        extensions_data: list[dict[str, Any]],
        total_drive_space: str,
        used_drive_space: str,
        free_drive_space: str,
        analyzed_files_size: str,
        analyzed_path: str = ""
    ) -> str:
        """
        Genera y guarda el archivo .txt con el resumen de la certificación.

        :param file_path: Ruta destino del archivo .txt.
        :param total_files: Cantidad total de archivos procesados.
        :param extensions_data: Lista de diccionarios con {'extension': str, 'conteo': int}.
        :param total_drive_space: Espacio total formateado de la unidad.
        :param used_drive_space: Espacio utilizado formateado de la unidad.
        :param free_drive_space: Espacio libre formateado de la unidad.
        :param analyzed_files_size: Espacio ocupado por los archivos analizados.
        :param analyzed_path: Ruta analizada (opcional como referencia).
        :return: Ruta del archivo generado.
        """
        lines = [
            "==================================================",
            "        REPORTE DE CERTIFICACIÓN DE ARCHIVOS      ",
            "==================================================",
            "",
        ]

        if analyzed_path:
            lines.append(f"Ruta analizada: {analyzed_path}")
            lines.append("")

        lines.extend([
            "--- MÉTRICAS DE ALMACENAMIENTO DE LA UNIDAD ---",
            f"Espacio Total de la Unidad:       {total_drive_space}",
            f"Espacio Utilizado de la Unidad:   {used_drive_space}",
            f"Espacio Libre de la Unidad:       {free_drive_space}",
            f"Espacio Ocupado por los Archivos: {analyzed_files_size}",
            "",
            "--- RESUMEN DE ARCHIVOS ---",
            f"Archivos Totales Analizados:      {total_files}",
            "",
            "--- FORMATOS Y CANTIDADES DE ARCHIVOS ---",
        ])

        if extensions_data:
            # Ordenar por conteo descendente
            sorted_extensions = sorted(
                extensions_data, key=lambda x: x.get("conteo", 0), reverse=True
            )
            for item in sorted_extensions:
                ext = str(item.get("extension", "")).upper()
                count = item.get("conteo", 0)
                ext_display = f".{ext}" if ext != "SIN_EXTENSION" else "(Sin extensión)"
                lines.append(f"  {ext_display:<20}: {count} archivo(s)")
        else:
            lines.append("  (No se encontraron archivos)")

        lines.extend([
            "",
            "==================================================",
        ])

        content = "\n".join(lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

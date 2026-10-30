import os
import re
from datetime import datetime
from config import OUTPUT_DIRECTORY


def generate_dated_filename(base_name: str, output_dir: str | None = None) -> str:
    """
    Genera el nombre del archivo agregando la fecha de la certificación al final
    con la nomenclatura 'nombre-DD_MM_YY' (ej. 'RESPALDO-23_08_26').
    Si el archivo ya existe en la carpeta de Certificaciones (tanto .json como .txt),
    agrega un sufijo enumerado secuencial: 'nombre-DD_MM_YY (1)', 'nombre-DD_MM_YY (2)', etc.
    """
    clean_name = base_name.strip()
    if not clean_name:
        clean_name = "CERTIFICACION"

    # Formato de fecha día_mes_año (ej. 23_08_26)
    date_suffix = datetime.now().strftime("%d_%m_%y")
    target_dir = output_dir or os.path.join(os.getcwd(), OUTPUT_DIRECTORY)

    if clean_name.endswith(f"-{date_suffix}"):
        candidate = clean_name
    else:
        candidate = f"{clean_name}-{date_suffix}"

    json_path = os.path.join(target_dir, f"{candidate}.json")
    txt_path = os.path.join(target_dir, f"{candidate}.txt")

    if not os.path.exists(json_path) and not os.path.exists(txt_path):
        return candidate

    counter = 1
    while True:
        numbered_candidate = f"{candidate} ({counter})"
        numbered_json = os.path.join(target_dir, f"{numbered_candidate}.json")
        numbered_txt = os.path.join(target_dir, f"{numbered_candidate}.txt")
        if not os.path.exists(numbered_json) and not os.path.exists(numbered_txt):
            return numbered_candidate
        counter += 1


class Validator:
    """
    Validador de rutas de origen, nombres de salida y permisos.
    """

    def __init__(self, path: str, file_name: str, output_dir: str | None = None) -> None:
        self.path = path.strip().strip('"').strip("'")
        self.file_name = file_name.strip()
        self.output_dir = output_dir or os.path.join(os.getcwd(), OUTPUT_DIRECTORY)

    def get_resolved_dated_filename(self) -> str:
        """
        Calcula y retorna el nombre final de la certificación con la fecha y sufijo enumerado si colisiona.
        """
        return generate_dated_filename(self.file_name, self.output_dir)

    def valid_file_name_characters(self) -> bool:
        """
        Verifica que el nombre del archivo no contenga caracteres prohibidos por Windows.
        """
        invalid_chars = r'[<>:"/\\|?*]'
        return not bool(re.search(invalid_chars, self.file_name))

    def valid_mount_point(self) -> bool:
        """
        Verifica si la ruta corresponde a un punto de montaje.
        """
        return os.path.ismount(self.path)

    def valid_dir_path(self) -> bool:
        """
        Verifica que el directorio a analizar exista y sea accesible.
        """
        return os.path.exists(self.path) and os.path.isdir(self.path)
"""
Configuración global del Certificador de Integridad Documental.
"""

# Constante de tipo boolean para activar y desactivar el almacenamiento
# de las certificaciones en el repositorio JSON.
SAVE_JSON_CERTIFICATIONS: bool = True

# Constante de tipo boolean para activar y desactivar el almacenamiento
# de las certificaciones en la base de datos SQLite3.
SAVE_SQLITE_CERTIFICATIONS: bool = True

# Directorio de salida para reportes y certificaciones
OUTPUT_DIRECTORY: str = "Certificaciones"

# Nombre del archivo de base de datos SQLite3
SQLITE_DB_NAME: str = "certificaciones.sqlite3"

# Algoritmo de hash por defecto. Se resuelve con hashlib.new(), por lo que
# acepta nombres como SHA256, SHA1, MD5, SHA512 o SHA3-256. El valor se guarda
# en mayúsculas en los reportes JSON y en la base de datos SQLite3.
DEFAULT_HASH_ALGORITHM: str = "SHA256"

# Tamaño de bloque para lectura de archivos (64 KB)
HASH_CHUNK_SIZE: int = 65536

# ---------------------------------------------------------------------------
# Normalización de nombres de archivos y carpetas
# ---------------------------------------------------------------------------

# Activa o desactiva el botón de normalización en la interfaz.
NORMALIZATION_ENABLED: bool = True

# Conserva las extensiones (incluidas las compuestas como .tar.gz) al
# normalizar el nombre. Si se desactiva, los puntos se eliminan por completo.
NORMALIZATION_PRESERVE_EXTENSIONS: bool = True

# Conserva los guiones y guiones bajos como separadores de palabras. Sin ellos
# la eliminación estricta de símbolos uniría palabras y generaría colisiones.
NORMALIZATION_KEEP_WORD_SEPARATORS: bool = True

# Nombre de reserva cuando la normalización deja el nombre vacío.
NORMALIZATION_FALLBACK_NAME: str = "SIN_NOMBRE"

# Límite de caracteres para un componente individual (NTFS/FAT32).
NORMALIZATION_MAX_COMPONENT_LENGTH: int = 255

# Límite de la ruta completa en Windows (MAX_PATH, incluido el terminador).
NORMALIZATION_MAX_PATH_LENGTH: int = 259

# Directorios que nunca se recorren ni se renombran.
NORMALIZATION_IGNORED_DIRECTORIES: tuple[str, ...] = (
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "System Volume Information",
    "$RECYCLE.BIN",
)

# Archivos generados por el sistema operativo que se omiten.
NORMALIZATION_IGNORED_FILES: tuple[str, ...] = (
    "desktop.ini",
    "thumbs.db",
)

# Subcarpeta sugerida para copias normalizadas. Actualmente es un valor
# reservado: la interfaz solicita la carpeta de destino de forma explícita.
NORMALIZATION_OUTPUT_SUBDIR: str = "normalizado"

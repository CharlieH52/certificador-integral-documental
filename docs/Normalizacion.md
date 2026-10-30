# Normalización de nombres

[Volver al README](../README.md)

La normalización convierte nombres de archivos y carpetas en nombres portables, legibles y compatibles con Windows, medios ópticos y herramientas que interpretan mal ciertos caracteres.

El proceso se aplica al **contenido** de la ruta seleccionada. La carpeta raíz nunca se renombra.

<div align="center">
  <img src="assets/screenshot-normalization-preview.png" alt="Vista previa de la tabla comparativa al normalizar nombres." width="720"/>
</div>

## Modos de trabajo

### Renombrar en el lugar

Cambia los nombres directamente en el disco.

- Genera un diario en `Certificaciones/normalizacion-AAAAMMDD-HHMMSS.json`.
- El diario permite revertir la operación desde el botón **Deshacer**.
- En medios ópticos, de solo lectura o sin permisos de escritura, el renombrado falla.

### Copiar a otra carpeta

Deja el origen intacto y escribe el árbol normalizado en una carpeta de destino.

- El destino debe estar fuera del directorio de origen.
- No sobrescribe archivos existentes: si el nombre final ya existe en el destino, la copia se omite y se registra la incidencia.
- La reversión elimina los archivos y carpetas creados por la copia, pero conserva las carpetas que contengan elementos ajenos.

## Reglas aplicadas

1. Elimina los puntos del nombre y conserva solo el que separa la extensión.
2. Elimina comas, barras (`/` y `\`) y cualquier símbolo o signo de puntuación, sin interpretarlo.
3. Conserva los paréntesis.
4. Conserva los guiones (`-`) y guiones bajos (`_`) como separadores de palabras.
5. Sustituye los decoradores ortográficos por su letra base: `canción` → `cancion`, `ü` → `u`.
6. Conserva la eñe.
7. Colapsa los espacios repetidos y recorta espacios y separadores sobrantes.
8. Conserva la extensión, incluidas las extensiones compuestas como `.tar.gz`, `.min.js` o `.d.ts`.
9. Evita los nombres reservados de Windows: `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9` y `LPT1`–`LPT9`.
10. Usa `SIN_NOMBRE` cuando el resultado queda vacío.
11. Resuelve colisiones con sufijos deterministas ` (1)`, ` (2)`, ... antes de la extensión.
12. Mantiene la extensión original aunque el resto del nombre cambie.

## Vista previa y nombres largos

Antes de aplicar cualquier cambio se muestra una vista previa con el nombre original y el nombre propuesto. Nada se modifica hasta que la persona confirma.

Windows limita los nombres por componente y la ruta completa. La aplicación calcula el espacio disponible con:

```text
min(NORMALIZATION_MAX_COMPONENT_LENGTH,
    NORMALIZATION_MAX_PATH_LENGTH - longitud de la carpeta - 1)
```

Si un nombre excede ese límite, se abre un diálogo de revisión con:

- Contador de caracteres en vivo.
- Borde verde cuando el nombre cabe.
- Borde rojo cuando excede el límite.
- Opción de escribir un nombre final o omitir el renombrado.

La aplicación **no trunca** el nombre automáticamente ni agrega un hash para acortarlo.

> 📷 **Captura pendiente — `docs/assets/screenshot-normalization-long-name.png`**
>
> Debe mostrar el diálogo de revisión de un nombre largo, con el contador de caracteres en vivo y el borde verde o rojo según el límite.

## Exclusiones

No se recorren ni se renombran los siguientes directorios:

- `.git`
- `.svn`
- `.hg`
- `node_modules`
- `__pycache__`
- `venv`
- `.venv`
- `System Volume Information`
- `$RECYCLE.BIN`
- La carpeta de salida `Certificaciones`

Se omiten los archivos:

- `desktop.ini`
- `Thumbs.db`

Las listas se configuran en `config.py` mediante `NORMALIZATION_IGNORED_DIRECTORIES` y `NORMALIZATION_IGNORED_FILES`.

## Diario y reversión

El diario se guarda en la carpeta de salida configurada:

```text
Certificaciones/normalizacion-AAAAMMDD-HHMMSS.json
```

Si ya existe un diario con el mismo nombre, se agrega un sufijo ` (1)`, ` (2)`, etc.

El diario contiene, entre otros datos:

- Versión del formato.
- Fecha de creación.
- Modo utilizado (`rename` o `copy`).
- Ruta de origen y, si aplica, destino.
- Estado de finalización.
- Operaciones agrupadas por carpeta.
- Copias realizadas.
- Directorios creados.
- Errores registrados.

La reversión se puede ejecutar con el botón **Deshacer** de la interfaz o con el diario correspondiente. Si un archivo ajeno ocupa el nombre original, la operación no lo sobrescribe y registra un conflicto.

## Configuración relacionada

| Variable | Valor por defecto | Efecto |
|---|---|---|
| `NORMALIZATION_ENABLED` | `True` | Muestra u oculta el botón de normalización. |
| `NORMALIZATION_PRESERVE_EXTENSIONS` | `True` | Conserva las extensiones. |
| `NORMALIZATION_KEEP_WORD_SEPARATORS` | `True` | Conserva guiones y guiones bajos. |
| `NORMALIZATION_FALLBACK_NAME` | `"SIN_NOMBRE"` | Nombre de respaldo. |
| `NORMALIZATION_MAX_COMPONENT_LENGTH` | `255` | Límite por componente. |
| `NORMALIZATION_MAX_PATH_LENGTH` | `259` | Límite de ruta completa. |
| `NORMALIZATION_IGNORED_DIRECTORIES` | Lista | Directorios excluidos. |
| `NORMALIZATION_IGNORED_FILES` | Lista | Archivos excluidos. |
| `NORMALIZATION_OUTPUT_SUBDIR` | `"normalizado"` | Valor reservado; el destino se solicita de forma explícita. |

## Limitaciones

- En medios ópticos o de solo lectura no se puede renombrar en el lugar; debe usarse la copia.
- La normalización debe ejecutarse antes de certificar, porque las certificaciones guardan las rutas literales.
- Los nombres que exceden el límite requieren intervención manual.
- La copia no sobrescribe archivos existentes.
- La reversión no puede restaurar nombres si la carpeta original ya no existe o si un archivo ajeno ocupa el nombre.
- Las reglas están orientadas a Windows; otros sistemas de archivos pueden tener restricciones distintas.

## Pruebas

```powershell
python -m unittest discover -s tests
```

Las pruebas de normalización cubren las reglas puras y el motor de planificación, renombrado, copia y reversión.

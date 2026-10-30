# Certificador de archivos
Analiza la ruta especificada e itera sobre los archivos contenidos para generar un registro de los archivos con su respectiva huella hash hecha con SHA256. Integra opciones como conteo total de archivos analizados, espacio total utilizado por estos, listado de extensiones y conteo por extensión, además de proveer datos sobre la unidad analizada (capacidad total, espacio ocupado por los archivos y espacio libre en la unidad). Soporta almacenamiento estructurado en repositorio JSON, base de datos SQLite3 y exportación de resúmenes a texto plano (.txt).

## Detrás del proyecto
### Contexto
Anteriormente un **órgano auditor** solía solicitar archivos expedidos por la organización para la que he trabajado, archivos que se envían aún en unidades extraíbles como USB, CD o DVD.

Estos archivos se solían enviar sin más. En la actualidad, este y otros órganos encargados de realizar auditorías han comenzado a solicitar respaldos digitales sobre el contenido de las unidades entregadas. Es por ello que se han comenzado a utilizar las certificaciones mediante huella hash; en nuestro caso particular se solicitan mediante el algoritmo `SHA256` junto con los datos mencionados en el primer párrafo. Esto con la finalidad de asegurar y mantener la integridad de la información que se entrega desde la organización.

### Justificación
El proceso planteado por el órgano en turno consistía en una serie de pasos sistemáticos y varias aplicaciones libres de por medio muy sencillas. Decidí crear una herramienta centralizada que realizara exactamente lo que se solicita con una interfaz sencilla y muy directa, para así eficientar todo el proceso, el cual cada día es más solicitado en mi área de Sistemas.

### ¿Por qué SHA256?
Actualmente es el requisito principal solicitado por el organo auditor respecto a la generación de la huella hash.

### Motivación
Realicé una investigación respecto al método utilizado para esta actividad dentro de los documentos proporcionados por el órgano auditor y me di cuenta de que, en general, era una actividad sistemática muy sencilla respecto a los requisitos solicitados, por lo que consideré que era un reto muy sencillo de trabajar con Python. Además, considerando la demanda creciente de estas solicitudes, encontré óptimo crearla no solo para mi uso en el área, sino para el uso común de las áreas que también lo requieran.

Es posible implementarla para otras organizaciones que tengan esta misma necesidad e incluso implementar otros algoritmos para la generación de la huella hash.

## Información técnica
Este proyecto consiste en una aplicación de escritorio con interfaz gráfica para centralizar los datos solicitados con un flujo de trabajo sencillo.

<div align="center" style="width:100%">
    <picture>
        <source srcset="./docs/screenshot-main_view.png" media="(max-width: 600px)"/>
        <img style="max-width: 600px;" src="./docs/screenshot-main_view.png" alt="Captura de pantalla de la vista previa de la interfaz al iniciar el programa."/>
    </picture>
</div>

<br/>

### Tecnologías utilizadas
- Python, lenguaje utilizado.
- Flet, librería de interfaces modernas de escritorio.
- SQLite3, motor de base de datos relacional para persistencia estructurada.
- Flet pack (PyInstaller), empaquetado del ejecutable de escritorio.

### Características
- Generación nativa de hashes `SHA256` por bloques (streaming).
- Conteo total de archivos auditados.
- Estadísticas y clasificación por formato/extensión.
- Cálculo del espacio total ocupado por los archivos analizados.
- Detección de capacidad total, espacio utilizado y libre en la unidad de almacenamiento.
- Nomenclatura automática con fecha (`nombre-DD_MM_YY`) y sufijos secuenciales anti-colisión.
- Selector interactivo para explorar directorios en el equipo.
- Barra de progreso reactiva en tiempo real.
- Exportación manual de reportes resumidos a formato de texto plano (`.txt`).
- Persistencia configurable en repositorios JSON y base de datos SQLite3.
- Normalización opcional de nombres de archivos y carpetas, con vista previa, revisión manual de nombres largos y reversión.

#### Justificación técnica
Decidí utilizar Python, pues para la primera versión rápida de prueba de concepto realicé varias certificaciones con algunas líneas de código y una interfaz CLI.

Una vez terminadas las funciones principales implementé Flet para centralizar la información y volver más accesible la aplicación mediante una interfaz gráfica clara y moderna con soporte asíncrono.

Para la entrega de reportes utilicé un formato de salida en JSON, pues esto puede ser extendible para otro tipo de lectores automatizados, implementación de APIs y facilita su importación en programas compatibles con este formato. Asimismo, integré una base de datos en SQLite3 para almacenar el histórico relacional de auditorías y un servicio de exportación a texto plano (.txt) para la entrega inmediata y legible de los resúmenes.

Por último, `flet pack` es esencial para portabilizar el programa, pues es necesario que sea más sencillo de implementar para el personal externo al área de Sistemas.

<div align="center" style="width:100%">
    <picture>
        <source srcset="./docs/screenshot-output-example.png" media="(max-width: 600px)"/>
        <img style="max-width: 600px;" src="./docs/screenshot-output-example.png" alt="Captura de pantalla de la salida resultante de una certificacion."/>
    </picture>
</div>

<br/>

## Flujo de trabajo

### Instalación
Preparar entorno virtual:
> `python -m venv venv`

Instalación de dependencias:
> `pip install -r requirements.txt`

Ejecución:
> `python .\main.py`

Compilar programa:
> `python .\build.py`

El paquete se genera en `dist/` (en Windows, `dist/GENERADOR_HUELLA_HASH.exe`). Para limpiar la caché de PyInstaller usa `python .\build.py --clean`; para generar una carpeta en lugar de un único `.exe` usa `python .\build.py --onedir`.

> [!NOTE]  
> En el archivo `config.py` es posible activar o desactivar el guardado de certificaciones en JSON (`SAVE_JSON_CERTIFICATIONS`) y SQLite3 (`SAVE_SQLITE_CERTIFICATIONS`), ajustar el comportamiento de la normalización de nombres (`NORMALIZATION_*`) y los parámetros de compilación en `build.py`.

### Resultado obtenido
El siguiente es un ejemplo del resultado esperado:

<div align="center" style="width:100%">
    <source srcset="./docs/screenshot-output-view-example.png" media="(max-width: 600px)"/>
    <img style="max-width: 600px;" src="./docs/screenshot-output-view-example.png" alt="Captura de pantalla del resultado obtenido en la interfaz de la aplicación."/>
</div>

<br/>

> [!NOTE]  
> Puede existir el caso de que el dispositivo analizado no provea información respecto a su capacidad o propiedades fisicas, como en el siguiente caso.  

<div align="center" style="width:100%">
    <picture>
        <source srcset="./docs/screenshot-cd_case.png" media="(max-width: 600px)"/>
        <img style="max-width: 600px;" src="./docs/screenshot-cd_case.png" alt="Captura de pantalla del resultado obtenido de un CD antiguo de Windows NT Original."/>
    </picture>
</div>

<br/>

> Eso sucede principalmente en unidades de CD o DVD, pues dependiendo del fabricante, la antigüedad, entre otros factores como codificación de los archivos y formato de la unidad.

### Normalización de nombres

El botón **Normalizar nombres** trabaja sobre el contenido de la ruta seleccionada (nunca sobre la carpeta raíz) y aplica reglas deterministas para que los nombres sean portables y legibles:

- Elimina los puntos del nombre (conserva solo el que separa la extensión), las comas, las barras (`/` y `\`) y cualquier símbolo o signo de puntuación, sin interpretarlo.
- Conserva los paréntesis y, como separadores de palabra, los guiones (`-`) y guiones bajos (`_`).
- Sustituye los decoradores ortográficos por su letra base (`canción` → `cancion`, `ü` → `u`) y conserva la eñe.
- Colapsa los espacios repetidos y recorta espacios y separadores sobrantes.
- Conserva la extensión, incluidas las compuestas (`.tar.gz`, `.min.js`, `.d.ts`).
- Evita los nombres reservados de Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) y usa `SIN_NOMBRE` cuando el resultado queda vacío.
- Resuelve colisiones con sufijos deterministas ` (1)`, ` (2)`, ... antes de la extensión.

Hay dos modos:

- **Renombrar en el lugar**: cambia los nombres en el disco y guarda un diario en `Certificaciones/normalizacion-AAAAMMDD-HHMMSS.json` para poder deshacer.
- **Copiar a otra carpeta**: deja el origen intacto y escribe el árbol normalizado en el destino, sin sobrescribir archivos existentes.

Antes de aplicar cualquier cambio se muestra una vista previa. Los nombres que exceden el límite disponible de la ruta (`min(255, 259 - longitud de la carpeta - 1)`) abren un diálogo con contador en vivo y borde verde o rojo; la persona decide el nombre final u omite el renombrado. Nunca se trunca el nombre ni se agrega un hash automático.

Se excluyen `.git`, `.svn`, `.hg`, `node_modules`, `__pycache__`, `venv`, `.venv`, `System Volume Information`, `$RECYCLE.BIN`, `desktop.ini`, `Thumbs.db` y la carpeta `Certificaciones`.

> [!NOTE]
> En medios ópticos o de solo lectura el renombrado en el lugar falla; en ese caso usa la copia normalizada. La normalización debe ejecutarse antes de certificar, porque las certificaciones guardan las rutas literales de los archivos.

Pruebas automatizadas:

> `python -m unittest discover -s tests`

### Limitaciones conocidas
- El tiempo que demora el análisis depende principalmente del tamaño de la muestra y la velocidad de lectura de la unidad.
- Los archivos bloqueados con permisos exclusivos del sistema operativo podrían omitirse.
- Actualmente la certificación principal está enfocada en el estándar solicitado por auditoría con el algoritmo `SHA256`.

<table style="width:100%; border:none;">
  <tr>
    <td align="center">
      <picture>
        <source srcset="./docs/screenshot-output-view-test.png" media="(max-width: 400px)"/>
        <img style="max-width: 400px;" src="./docs/screenshot-output-view-test.png" alt="Captura de pantalla que contrasta el resultado de la aplicación con el mostrado por Windows."/>
      </picture>
    </td>
    <td align="center">
      <picture>
        <source srcset="./docs/windows-info.png" media="(max-width: 240px)"/>
        <img style="max-width: 240px;" src="./docs/screenshot-windows-info.png" alt="Captura de pantalla del las propiedades mostradas por Windows."/>
      </picture>
    </td>
  </tr>
</table>

> [!CAUTION]  
> Puede haber una ligera discrepancia en el espacio ocupado mostrado por la aplicación y el marcado por las propiedades de Windows, ya que influyen factores como los mencionados en las limitaciones conocidas.
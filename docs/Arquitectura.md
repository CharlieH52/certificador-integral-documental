# Arquitectura y decisiones de diseño

[Volver al README](../README.md)

Este documento conserva el detalle técnico de las decisiones que dieron forma al Certificador de Integridad Documental. El README resume el uso; aquí se explica el porqué de la implementación.

## Python como base

La primera versión de prueba de concepto se resolvió con pocas líneas de Python y una interfaz de línea de comandos. Ese prototipo permitió validar el recorrido de unidades, el cálculo de hashes y la obtención de métricas antes de invertir en una interfaz gráfica.

Python resultó adecuado por:

- Su biblioteca estándar cubre recorrido de archivos, cálculo de hashes, SQLite3 y manejo de rutas.
- Permite iterar rápido sobre una herramienta interna.
- Facilita el empaquetado posterior con PyInstaller.
- El equipo destinatario no necesita conocimientos de Python si recibe el ejecutable.

## Flet para la interfaz

Una vez terminadas las funciones principales se incorporó Flet para centralizar la información en una interfaz gráfica clara y moderna.

La interfaz permite:

- Seleccionar la ruta sin escribirla manualmente.
- Ver el progreso del hashing en tiempo real.
- Revisar métricas, conteos y extensiones en un solo lugar.
- Exportar el resumen sin usar la línea de comandos.
- Ejecutar la normalización con vista previa y reversión.

Flet aporta soporte asíncrono y un modelo de componentes adecuado para una aplicación de escritorio. El cálculo pesado se ejecuta fuera del hilo de la interfaz para evitar que la ventana se bloquee.

## Formatos de salida

### JSON

Se eligió JSON para el detalle de hashes porque:

- Es legible por personas y por programas.
- Puede extenderse a otros lectores automatizados.
- Facilita la integración con APIs y herramientas compatibles.
- No requiere un motor de base de datos para consultarse.

El archivo contiene una lista de objetos con `Algorithm`, `Hash` y `Path`. El resumen de métricas y el conteo por extensión se mantienen en el TXT y en SQLite para no duplicar estructuras.

### SQLite3

SQLite3 se incorporó para conservar un histórico relacional de certificaciones sin depender de un servidor de base de datos.

El esquema separa:

- El registro maestro de la certificación.
- El detalle de archivos y hashes.
- El resumen por extensión.

Esta separación permite consultas por certificación, por archivo o por hash, y mantiene la base portátil junto con la aplicación.

### Texto plano

El reporte `.txt` se pensó para la entrega inmediata y legible. Incluye:

- Ruta analizada.
- Métricas de capacidad, espacio utilizado y libre.
- Total de archivos.
- Conteo por extensión.

La exportación es manual para que la persona decida cuándo generar el resumen y no producir archivos innecesarios.

## Empaquetado

`flet pack` utiliza PyInstaller por debajo. Se eligió porque:

- Genera un ejecutable de Windows sin necesidad de Visual Studio Build Tools.
- No compila el runner de Flutter.
- Permite distribuir la aplicación a personal externo al área de Sistemas.
- Ofrece modo de archivo único y modo de carpeta (`--onedir`).

Los parámetros de nombre, versión y descripción se mantienen en `build.py` para que la compilación sea reproducible.

## Separación por capas

| Capa | Responsabilidad |
|---|---|
| `view/` | Interfaz Flet, diálogos y presentación de resultados. |
| `service/` | Hashing, validación, exportación, normalización y planificación. |
| `repository/` | Modelos de datos y persistencia SQLite3. |
| `config.py` | Constantes globales de salida, hashing y normalización. |
| `tests/` | Pruebas unitarias de las reglas y motores. |

La separación permite probar la lógica sin abrir la interfaz y reutilizar los servicios desde otros puntos de entrada.

## Algoritmo de hash

El algoritmo se configura en `DEFAULT_HASH_ALGORITHM`. El valor se resuelve con `hashlib.new()`, se valida al construir el motor y se guarda en mayúsculas en el JSON y en SQLite.

SHA-256 es el valor predeterminado porque es el requisito principal del órgano auditor. La constante permite seleccionar otros algoritmos disponibles en el intérprete sin cambiar el flujo de la aplicación.

## Normalización

La normalización se diseñó como una operación separada de la certificación:

- La certificación solo lee.
- La normalización modifica nombres o copia el árbol, según el modo.
- Antes de aplicar cambios siempre hay una vista previa.
- El modo de renombrado genera un diario reversible.
- El modo de copia deja el origen intacto.

El detalle funcional está en [`Normalizacion.md`](Normalizacion.md).

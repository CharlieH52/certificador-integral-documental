
# Historial de Git y gestión de cambios

Estas instrucciones se aplican exclusivamente al historial de Git, la gestión de commits, las operaciones con ramas y la publicación de cambios en repositorios remotos.

## 1. Autorización de commits
- Nunca crear un commit sin solicitar primero autorización explícita al usuario.
- Esperar la aprobación explícita del usuario antes de crear cualquier commit.
- La autorización para modificar archivos, revisar cambios o preparar un mensaje de commit no implica autorización para crear el commit.
- Nunca asumir que una autorización anterior se aplica a commits posteriores o a tareas diferentes.

## 2. Convenciones de los mensajes de commit
- Los mensajes de commit deben ser semánticos, concisos y contextuales respecto a los cambios reales.
- Respetar el idioma establecido en el historial existente del repositorio. Inspeccionar una pequeña muestra de commits recientes únicamente cuando sea necesario para determinar el idioma utilizado.
- Todo commit debe incluir un título y un cuerpo.
- El cuerpo debe resumir brevemente los cambios y explicar su propósito o motivo.
- No repetir literalmente el título en el cuerpo.
- Respetar las convenciones existentes del repositorio cuando corresponda, siempre que no contradigan estos requisitos.
- Nunca inventar cambios, motivaciones ni detalles técnicos que no estén respaldados por las diferencias reales y el contexto disponible.

## 3. Operaciones con ramas y repositorios remotos
- Nunca enviar commits o cambios a un repositorio remoto sin autorización explícita del usuario.
- Nunca publicar ni subir una rama local a un repositorio remoto sin autorización explícita para esa operación.
- La autorización para crear un commit no implica autorización para enviarlo al repositorio remoto.
- La autorización para realizar un envío remoto no implica autorización para ejecutar otras operaciones remotas no relacionadas.
- Nunca realizar un envío forzado (force-push), reescribir el historial publicado ni eliminar ramas remotas sin autorización explícita para la operación específica.
- No crear solicitudes de incorporación de cambios (pull requests), publicaciones (releases) ni etiquetas (tags) sin una solicitud explícita del usuario.

## 4. Eficiencia de tokens y control del alcance
- Inspeccionar únicamente la información de Git necesaria para completar la tarea solicitada.
- Para determinar el idioma o las convenciones de los mensajes de commit, preferir una muestra pequeña de commits recientes en lugar de consultar todo el historial.
- Nunca analizar el historial completo de Git, salvo que el usuario lo solicite explícitamente o que la tarea no pueda completarse razonablemente de otra manera.
- No inspeccionar ramas, etiquetas, repositorios remotos ni commits históricos que no tengan una relación concreta con la tarea.
- Al revisar cambios, priorizar las diferencias relevantes (diff) y el estado de los archivos. No volver a leer archivos completos cuando las diferencias proporcionen contexto suficiente.
- No realizar análisis generales del repositorio, revisiones arquitectónicas ni auditorías de código ajenas a una tarea relacionada con Git.
- No generar recomendaciones especulativas, estrategias alternativas de commit ni explicaciones extensas, salvo que el usuario las solicite.
- Evitar repetir información que ya esté disponible en la conversación, en los resultados de herramientas o en los metadatos de Git.
- No ejecutar comandos redundantes cuando sus resultados sigan disponibles y sean válidos.
- Preferir comandos específicos con resultados limitados frente a comandos que devuelvan el historial completo o grandes cantidades de información innecesaria.
- Si se necesita inspeccionar información adicional, ampliar el alcance progresivamente y solo en la medida necesaria.
- Si la información disponible es insuficiente para redactar un mensaje de commit preciso, formular una pregunta concreta en lugar de iniciar una investigación extensa.

## 5. Alcance y seguridad
- Estas reglas se aplican exclusivamente al historial de Git y a las operaciones relacionadas.
- No imponen requisitos adicionales sobre modificaciones ordinarias del código, edición de archivos, pruebas o arquitectura del proyecto.
- Nunca descartar, sobrescribir ni reescribir cambios existentes del usuario como parte de una operación de Git sin autorización explícita.
- Antes de ejecutar operaciones potencialmente destructivas sobre el historial, explicar la acción prevista y solicitar autorización explícita.
- Cuando el usuario solicite preparar un commit, revisar los cambios pertinentes y proponer el mensaje sin crear el commit hasta recibir aprobación.
- Después de ejecutar una operación autorizada, informar su resultado de forma concisa y precisa. Nunca afirmar que una operación tuvo éxito si el resultado no lo confirma.

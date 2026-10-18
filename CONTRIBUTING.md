# Contribuir · Contributing

[Español](#español) · [English](#english) · [README](README.md) · [Seguridad / Security](SECURITY.md)

## Español

Gracias por contribuir a report-gen. Priorizamos **seguridad, conservación de datos y facilidad de uso**. Son útiles las correcciones reproducibles, mejoras de documentación, traducciones y plantillas con licencia y atribución claras.

### Antes de empezar

- Para un error, abre una [incidencia](https://github.com/IphobiusS/report-gen/issues) con versión y commit si lo conoces, entorno, pasos mínimos, resultado esperado y observado. Usa proyectos y evidencias ficticios.
- Para una función grande, describe primero el problema del usuario y el alcance en una incidencia. Mantén cada pull request centrado en un cambio revisable.
- Para una vulnerabilidad, sigue la [política de seguridad](SECURITY.md#español); no la publiques en una incidencia abierta.
- No incluyas informes de clientes, credenciales, datos personales ni respaldos privados, tampoco en fixtures, capturas o logs.

### Preparar el entorno

Sigue la [guía de instalación](docs/guide.es.md#instalar-y-abrir) y trabaja en una rama propia. Se requiere **Python 3.11+**; para las pruebas de interfaz, **Node.js 22+**. Node.js no es necesario para usar el editor.

Desde la raíz del repositorio, con el entorno del proyecto ya instalado, en Linux o macOS:

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci --ignore-scripts
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
npm test
```

En Windows, utiliza `.venv\Scripts\python.exe` en lugar de `.venv/bin/python`. Los exportadores y las pruebas opcionales pueden necesitar dependencias del sistema, fuentes o navegadores adicionales: consulta [desarrollo y límites](docs/guide.es.md#desarrollo-y-límites) y los [workflows de CI](.github/workflows). `npm test` cubre contratos de guardado y borradores; no representa por sí solo todas las pruebas de interfaz.

### Preparar un pull request

Explica el problema, el cambio y el comportamiento resultante. Incluye los pasos de reproducción y los comandos de verificación ejecutados, con sus resultados. Indica cualquier comprobación pendiente y los sistemas operativos, navegadores y motores de documentos utilizados.

Para corregir un bug, añade una regresión que falle en la versión afectada y pase con el cambio. Conserva las pruebas existentes salvo que cambie intencionalmente el contrato público; explica ese cambio. Ejecuta las pruebas Python, las de guardado y combinación en JavaScript, y el recorrido de navegador real que corresponda al área modificada. Un cambio de documentación requiere comprobar enlaces, comandos y coherencia, sin atribuirle una nueva aceptación funcional.

| Área modificada | Comprobaciones necesarias |
| --- | --- |
| Interfaz, ayuda o plantillas | Español, inglés y portugués de Brasil; navegación aplicable; contenido y aspecto de las salidas afectadas. |
| Privacidad o publicación | Capturas privadas, originales, contenido desactivado, revisiones antiguas, metadatos de imágenes y todos los formatos públicos. |
| Guardado y recuperación | Conflictos, escrituras fallidas, cierre abrupto de pestaña y restauración real de respaldos. |
| Exportación | Contenido, enlaces, tablas, imágenes y paginación; identifica cada motor realmente probado. |

**Una renderización en LibreOffice no es una prueba en Microsoft Word.** No presentes una ejecución parcial como aprobación de toda la batería ni una comprobación automática como una sesión con usuarios.

### Idiomas, contenido y dependencias

La interfaz y las plantillas deben mantener **ES, EN y pt-BR**. No traduzcas ni reescribas silenciosamente el contenido de una evaluación. Conserva Calibri/Carlito y los comandos monoespaciados en los informes.

Mantén las licencias y la atribución de los recursos de terceros. Las nuevas plantillas no deben sugerir afiliación con un proveedor ni cumplimiento de las reglas actuales de un examen sin verificación. No añadas telemetría ni una dependencia de red a la edición habitual sin una revisión explícita del diseño.

### Distribución reproducible

La descarga pública de una versión publicada debe apuntar al ZIP de su Release verificada:

```text
https://github.com/IphobiusS/report-gen/releases/download/v<VERSION>/report-gen-<VERSION>-<SHA12>.zip
```

La etiqueta, los siete workflows definidos en [`scripts/publish-release.py`](scripts/publish-release.py) y el manifiesto deben identificar el mismo commit completo. Usa ese mismo archivo y SHA-256 en el sitio y en los anuncios; enlaza las guías por el commit correspondiente. No mantengas otro ZIP de la aplicación dentro del sitio.

Para comprobar una distribución desde los objetos de Git, usa un commit que ya incluya los cambios que deseas distribuir:

```bash
python scripts/build-release.py --ref HEAD --output out/release
```

El comando genera el ZIP, su SHA-256 y un JSON de procedencia y archivos. Excluye cambios sin commit y archivos ignorados; es reproducible con la misma referencia. El archivo `archive/<commit-completo>.zip` de GitHub es una alternativa de código fuente con un contenedor y hash diferentes: no intercambies los hashes de ambos artefactos.

CI separa las comprobaciones rápidas, los recorridos de interfaz y exportación, y cuatro grupos de Pytest. La comprobación final exige que su unión cubra exactamente la colección completa, sin duplicados. Consulta el [registro de cambios](CHANGELOG.md) y la [auditoría de 0.45.0](docs/QA-AUDIT-0450.md) para conocer el alcance documentado de esa versión.

### Sesiones externas de primer uso

Este es un **protocolo pendiente de ejecución**, no un resultado de usabilidad. Invita por separado a cinco voluntarios del público objetivo con diferentes niveles de experiencia en reportería. La aplicación no envía invitaciones ni recopila datos de sesión. Usa identificadores P1–P5 y datos ficticios; no grabes sin permiso. Conserva las observaciones de participantes fuera del repositorio público.

#### Preparar los materiales

```bash
python scripts/prepare-external-acceptance.py --output out/external-acceptance
```

Se generan siete DOCX ficticios —Nimbus, laboratorio de calidad, severidades pendientes, tabla larga y tres casos de URLs y numeración en ES/EN/PT— y quince filas vacías para las tres tareas de P1–P5. El manifiesto conserva `word_native: not_run` y `human_sessions: not_run`: preparar materiales no ejecuta esas comprobaciones.

Entrega a cada participante el mismo paquete identificado por versión y commit, el README y una carpeta nueva de trabajo. Registra sistema operativo, navegador y visores Word/PDF. Comprueba los requisitos del equipo y deja que siga la instalación documentada. No dirijas al participante hacia la demo Nimbus antes de observar su elección. Utiliza una instalación aislada para la restauración.

#### Tareas de cada participante

1. **Crear.** Instalar y abrir el editor, crear un proyecto, documentar un hallazgo ficticio y asociar una imagen con pie descriptivo.
2. **Entregar.** Localizar un pendiente de revisión preparado en el caso, explicar qué falta y resolverlo con el material ficticio. Generar PDF y Word, abrir ambos y comprobar hallazgo y evidencia.
3. **Recuperar.** Guardar y cerrar el editor, reabrir el proyecto, crear un respaldo y restaurarlo en la instalación vacía. Comprobar que el hallazgo y la imagen siguen presentes.

El moderador lee la tarea sin indicar dónde pulsar. Registra cada petición de ayuda o bloqueo antes de ayudar; una finalización asistida no es independiente. Una salida cuenta solo cuando se abre y contiene lo esperado. Descargar el respaldo sin restaurarlo no demuestra recuperación.

#### Registrar resultados y revisión de Word

Completa una fila por participante y tarea. Mide desde la lectura de la tarea hasta verificar el resultado; registra el tiempo de instalación y descarga por separado. Cuenta las intervenciones del moderador y utiliza los valores del kit: `independent`, `assisted` o `blocked`. No rellenes observaciones humanas a partir de pruebas automáticas.

| Participante | Versión y commit | Entorno y visores | Tarea | Tiempo | Instalación y descarga | Ayudas | Bloqueo observado | Resultado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |

El kit incluye `word-review.csv` e `INSTRUCTIONS.txt`. En un equipo Windows con Microsoft Word licenciado, ejecuta [`scripts/verify-microsoft-word.ps1`](scripts/verify-microsoft-word.ps1) con `-InputDirectory out/external-acceptance/word-input` y una carpeta de salida vacía mediante `-OutputDirectory out/external-acceptance/word-verified`. Inspecciona todas las páginas de sus PDF y registra pass/fail, revisor, fecha y SHA-256.

```bash
python scripts/prepare-external-acceptance.py --summarize out/external-acceptance
```

El resumen valida hashes y coherencia de los registros sin modificarlos. Mantiene separados la automatización Word, la inspección visual y las sesiones; no autentica participantes ni sustituye la evaluación humana. El manifiesto distingue el commit de las modificaciones locales.

Para añadir el caso complejo Boreal al corpus de Word:

```bash
python scripts/build-boreal-case.py --output out/boreal-case
python scripts/prepare-external-acceptance.py --output out/external-acceptance --additional-projects out/boreal-case/projects
```

Los diez DOCX conservan hashes de origen y estados pendientes. Ejecutar el workflow de Word requiere un runner Windows dedicado con Microsoft Word licenciado.

Al cerrar las cinco sesiones, resume resultados por tarea, errores repetidos y puntos de ayuda. Prioriza pérdida de datos y bloqueos antes de preferencias visuales; repite las tareas afectadas tras corregirlas. Cinco sesiones descubren dificultades concretas, pero no acreditan facilidad de uso para toda la audiencia.

## English

Thank you for contributing to report-gen. We prioritize **security, data preservation and usability**. Reproducible fixes, documentation improvements, translations and templates with clear licensing and attribution are welcome.

### Before you start

- For a bug, open an [issue](https://github.com/IphobiusS/report-gen/issues) with the version and commit if known, environment, minimal steps, and expected and observed behavior. Use synthetic projects and evidence.
- For a large feature, first describe the user problem and scope in an issue. Keep each pull request focused on a reviewable change.
- For a vulnerability, follow the [security policy](SECURITY.md#english); do not disclose it in a public issue.
- Do not include client reports, credentials, personal data or private backups, including in fixtures, screenshots or logs.

### Set up the environment

Follow the [installation guide](docs/guide.en.md#install-and-launch) and work on your own branch. **Python 3.11+** is required; interface tests also require **Node.js 22+**. Node.js is not needed to use the editor.

From the repository root, with the project environment already installed, on Linux or macOS:

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci --ignore-scripts
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
npm test
```

On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`. Exporters and optional tests may require additional system dependencies, fonts or browsers: see [CLI and development](docs/guide.en.md#cli-and-development) and the [CI workflows](.github/workflows). `npm test` covers save and draft contracts; it is not the complete interface test suite.

### Prepare a pull request

Explain the problem, change and resulting behavior. Include reproduction steps and the verification commands you ran, with their results. State any outstanding checks and identify the operating systems, browsers and document renderers used.

For a bug fix, add a regression that fails on the affected version and passes with the change. Preserve existing tests unless the public contract intentionally changes; explain that change. Run Python tests, JavaScript save/merge tests and the real-browser flow relevant to the affected area. Documentation changes require checks of links, commands and consistency, without claiming new functional acceptance.

| Changed area | Required checks |
| --- | --- |
| Interface, help or templates | Spanish, English and Brazilian Portuguese; applicable navigation; content and layout of affected outputs. |
| Privacy or publication | Private captures, originals, disabled content, old revisions, image metadata and all public formats. |
| Persistence and recovery | Conflicts, failed writes, abrupt tab closure and actual backup restoration. |
| Export | Content, links, tables, images and pagination; identify every renderer actually tested. |

**A LibreOffice render is not a Microsoft Word test.** Do not present a partial run as a full-suite pass, or an automated check as a user session.

### Languages, content and dependencies

The interface and templates must maintain **ES, EN and pt-BR**. Do not silently translate or rewrite assessment content. Keep Calibri/Carlito and monospaced commands in reports.

Preserve licenses and attribution for third-party assets. New templates must not imply provider affiliation or compliance with current exam rules without verification. Do not add telemetry or a network dependency to ordinary editing without explicit design review.

### Reproducible distribution

Public downloads of a published version must use its verified Release ZIP:

```text
https://github.com/IphobiusS/report-gen/releases/download/v<VERSION>/report-gen-<VERSION>-<SHA12>.zip
```

The tag, the seven workflows defined in [`scripts/publish-release.py`](scripts/publish-release.py) and the manifest must identify the same complete commit. Reuse that file and SHA-256 on the website and in announcements, with guides pinned to the corresponding commit. Do not host a second application ZIP inside the website.

To check a distribution built from Git objects, use a commit that already contains the intended changes:

```bash
python scripts/build-release.py --ref HEAD --output out/release
```

The command writes the ZIP, its SHA-256 and a JSON provenance/file record. It excludes uncommitted and ignored files and is reproducible for the same ref. GitHub's `archive/<complete-commit>.zip` is an alternative source archive with different container bytes and a different hash: do not interchange their checksums.

CI separates fast checks, interface/export flows and four Pytest shards. The final gate requires their union to match the complete collection without duplicates. See the [changelog](CHANGELOG.md) and [0.45.0 audit](docs/QA-AUDIT-0450.md) for that release's documented scope.

### External first-use sessions

This is a **protocol awaiting execution**, not a usability result. Recruit five volunteers from the intended audience separately, with different levels of reporting experience. The application does not send invitations or collect session data. Use participant IDs P1–P5 and synthetic content; ask before recording. Keep participant observations outside the public repository.

#### Prepare the materials

```bash
python scripts/prepare-external-acceptance.py --output out/external-acceptance
```

This creates seven synthetic DOCX inputs—Nimbus, the quality laboratory, pending severities, a long table, and three URL/numbering cases in ES/EN/PT—and fifteen blank rows for the three P1–P5 tasks. The manifest retains `word_native: not_run` and `human_sessions: not_run`: preparing materials does not execute those checks.

Give each participant the same package identified by version and commit, the README and a fresh working directory. Record the operating system, browser and Word/PDF viewers. Check the machine requirements, then let them follow the documented installation. Do not direct them to the Nimbus demo before observing their choice. Use an isolated installation for restoration.

#### Tasks for each participant

1. **Create.** Install and open the editor, create a project, document a synthetic finding and link a captioned image.
2. **Deliver.** Find a seeded review issue, explain what is missing and resolve it using the synthetic material. Generate PDF and Word, open both and check the finding and evidence.
3. **Recover.** Save and close the editor, reopen the project, create a backup and restore it into the empty installation. Check that the finding and image remain present.

The moderator reads each task without pointing to controls. Record requests for help and blockers before assisting; assisted completion is not independent. An output counts only when it opens and contains the expected content. Downloading a backup without restoring it does not establish recovery.

#### Record outcomes and Word review

Complete one row per participant and task. Measure from reading the task to verifying the outcome; record installation/download time separately. Count moderator interventions and use the kit's values: `independent`, `assisted` or `blocked`. Do not populate human observations from automated tests.

| Participant | Version and commit | Environment and viewers | Task | Time | Setup/download time | Interventions | Observed blocker | Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |

The kit includes `word-review.csv` and `INSTRUCTIONS.txt`. On Windows with licensed Microsoft Word, run [`scripts/verify-microsoft-word.ps1`](scripts/verify-microsoft-word.ps1) with `-InputDirectory out/external-acceptance/word-input` and an empty output directory via `-OutputDirectory out/external-acceptance/word-verified`. Inspect every page of the resulting PDFs and record pass/fail, reviewer, date and SHA-256.

```bash
python scripts/prepare-external-acceptance.py --summarize out/external-acceptance
```

The summary validates hashes and record consistency without changing records. Native Word automation, visual inspection and participant sessions remain separate; it does not authenticate participants or replace human assessment. The manifest distinguishes the commit from local modifications.

To add the complex Boreal case to the Word corpus:

```bash
python scripts/build-boreal-case.py --output out/boreal-case
python scripts/prepare-external-acceptance.py --output out/external-acceptance --additional-projects out/boreal-case/projects
```

The ten DOCX files retain source hashes and pending statuses. Running the Word workflow requires a dedicated Windows runner with licensed Microsoft Word.

After five sessions, summarize outcomes by task, recurring errors and requests for help. Prioritize data loss and blockers before visual preferences, then repeat affected tasks after fixes. Five sessions reveal specific obstacles; they do not establish usability for the entire audience.

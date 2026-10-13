# Contributing / Contribuir

Prioritize security, data preservation and usability fixes. Start an issue with the user problem and a small reproducible case before proposing a large feature. Use synthetic projects and evidence.

For a fix, include a regression that fails on the affected version and passes with the change. Preserve existing tests unless the public contract intentionally changes; explain that change. Run Python tests, JS save/merge tests and the applicable real-browser flow. Report exactly which OS, browser and document renderer were used. A LibreOffice render is not a Microsoft Word test.

UI and template changes must support Spanish and English. Keep Calibri/Carlito and monospaced commands in reports. Do not silently translate or rewrite assessment content. Keep licenses and source attribution with third-party assets. New templates must not imply provider affiliation or compliance with current exam rules without verification.

For privacy changes, test private captures, originals, disabled content, old revisions, image metadata and all public formats. For persistence, test conflicts, failed writes, abrupt tab closure and backup restoration. Never add a telemetry or network dependency to ordinary editing without explicit design review.

En español: prioriza errores reproducibles, datos ficticios y pruebas que protejan el contenido. Mantén ES/EN, registra los motores probados y documenta cambios de contrato. Las contribuciones de plantillas necesitan licencia y atribución. No incluyas informes reales de clientes.

## Distribución y pruebas / Distribution and tests

La descarga pública de una versión publicada debe apuntar al ZIP de su Release verificada: `https://github.com/IphobiusS/report-gen/releases/download/v<VERSION>/report-gen-<VERSION>-<SHA12>.zip`. La etiqueta, los seis workflows de `scripts/publish-release.py::WORKFLOWS` y el manifiesto deben identificar el mismo commit completo. Utiliza ese mismo archivo y su SHA-256 en el sitio y en el anuncio; enlaza la guía por el commit correspondiente. El archivo `archive/<commit-completo>.zip` de GitHub sigue siendo una alternativa de código fuente, con un contenedor y un hash distintos. No mantengas otro ZIP de la aplicación dentro del sitio.

Published versions use the verified Release ZIP, with its version, commit prefix and SHA-256. The tag, all six workflow gates in `scripts/publish-release.py::WORKFLOWS` and the package manifest must identify the same complete commit. Reuse the same asset on the website and in announcements, with guides pinned to that commit. GitHub's commit archive remains an alternative source archive with different container bytes and a different checksum. Do not host a second application ZIP inside the website.

Para comprobar localmente una distribución desde los objetos de Git, utiliza un commit que ya incluya los cambios que quieres distribuir:

```bash
python scripts/build-release.py --ref HEAD --output out/release
```

El comando genera un ZIP identificado por versión y commit, su SHA-256 y un registro JSON de procedencia y archivos. No incluye modificaciones sin commit ni archivos ignorados. Es reproducible con la misma referencia; el ZIP generado por GitHub puede tener bytes distintos aunque contenga los mismos archivos rastreados. No atribuyas el hash de uno al otro.

This command packages committed Git objects and writes a ZIP, checksum and JSON provenance/file record. Uncommitted and ignored files are excluded. It is reproducible for the same ref; GitHub's archive can have different ZIP bytes despite containing the same tracked content. Checksums are specific to each artifact.

CI separa las comprobaciones rápidas, los recorridos de interfaz y exportación, y cuatro grupos de Pytest. La comprobación final exige que la unión de estos grupos cubra exactamente la colección completa, sin duplicados. Una ejecución parcial no debe presentarse como aprobación de toda la batería.

CI separates fast checks, interface/export flows and four Pytest shards. The final gate requires their union to match the complete collection without duplicates. Partial execution is not a full-suite pass.

## Prueba de primer uso con personas externas / External first-use sessions

Este es un protocolo pendiente de ejecución, no un resultado de usabilidad. Invita por separado a cinco personas del público objetivo, con distintos niveles de experiencia en reportería. Su participación debe ser voluntaria. No se envían invitaciones ni se recopilan datos automáticamente desde report-gen. Utiliza identificadores P1–P5 y datos ficticios; evita nombres de clientes, credenciales y capturas reales. No grabes la sesión sin permiso.

This protocol has not been executed as part of the release. Recruit five volunteers from the intended audience separately. Use participant IDs P1–P5 and synthetic content. The application does not send invitations or collect session data. Ask before recording.

### Preparación / Setup

Genera los materiales ficticios y el registro vacío con `python scripts/prepare-external-acceptance.py --output out/external-acceptance`. Incluye cuatro DOCX (Nimbus, laboratorio de calidad, severidades pendientes y tabla larga) y quince filas vacías para P1–P5. El manifiesto conserva `word_native: not_run` y `human_sessions: not_run`: preparar el material no ejecuta estas comprobaciones. Conserva los registros de participantes fuera de Git. Para Word, ejecuta `scripts/verify-microsoft-word.ps1` con `-InputDirectory out/external-acceptance/word-input` y una carpeta de salida vacía; después inspecciona sus PDF.

Run the preparation command above to create four synthetic DOCX inputs and a blank fifteen-row session record. Its manifest explicitly records native Word and human sessions as not run. Keep participant observations outside Git. The Word workflow uses the same corpus; its output still requires visual inspection.

Entrega a cada participante el mismo paquete identificado por versión y commit, el README y una carpeta nueva de trabajo. Registra sistema operativo, navegador y visor de Word/PDF. Comprueba únicamente los requisitos del equipo; deja que la persona siga la instalación documentada. Usa una instalación aislada para probar la restauración. La demo Nimbus está disponible, pero no dirijas al participante hacia ella antes de observar su elección.

Give each participant the same versioned package and README, a fresh working directory, and synthetic assessment material. Record the OS, browser and document viewers. Let them follow the installation instructions and choose their starting point. Use an isolated installation when checking restoration.

### Tareas / Tasks

1. **Crear / Create.** Instalar y abrir el editor. Crear un proyecto, documentar un hallazgo ficticio y asociar una imagen con pie descriptivo. Install and open the editor, then create a project with one synthetic finding and a captioned image linked to it.
2. **Entregar / Deliver.** Localizar un pendiente de revisión preparado en el caso, explicar qué falta y resolverlo con la información ficticia suministrada. Generar PDF y Word, abrir ambos y comprobar hallazgo y evidencia. Find a seeded review issue, explain and resolve it using the supplied material, then generate and inspect PDF and Word.
3. **Recuperar / Recover.** Guardar y cerrar el editor, reabrir el proyecto, crear un respaldo y restaurarlo en la instalación vacía. Comprobar que el hallazgo y su imagen siguen presentes. Save and close the editor, reopen the project, create a backup, restore it into the empty installation and check the finding and image.

El moderador lee la tarea sin enseñar dónde pulsar. Si la persona pide ayuda o queda bloqueada, registra primero el punto y después ayuda; no se considera finalización independiente. Una salida generada cuenta solo cuando puede abrirse y contiene lo esperado. Para la tercera tarea, comprobar el ZIP descargado sin restaurarlo no es suficiente.

Read the task without pointing to controls. Record requests for help and blockers before assisting; assisted completion is separate from independent completion. Generated files must open and contain the expected content. Downloading a backup alone does not establish successful recovery.

### Registro vacío / Blank observation record

Completa una fila por tarea y participante, fuera del repositorio público. Mide el tiempo desde que se lee la tarea hasta que se verifica el resultado; registra por separado el tiempo de descarga o instalación. Cuenta cada intervención del moderador. Usa `independiente`, `con ayuda` o `bloqueado` como resultado. No rellenes datos a partir de una prueba automática.

Record one row per participant and task outside the public repository. Measure from the task being read to verified completion, noting installation/download time separately. Count moderator interventions. Use `independent`, `assisted` or `blocked`; automated tests are not participant observations.

| Participante / Participant | Versión y commit / Version and commit | SO, navegador, visores / Environment | Tarea / Task | Tiempo / Time | Instalación y descarga / Setup time | Ayudas / Interventions | Bloqueo observado / Observed blocker | Resultado / Outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |

Al cerrar las cinco sesiones, resume resultados por tarea, errores repetidos y puntos donde se pidió ayuda. Prioriza pérdida de datos y bloqueos antes que preferencias visuales. Vuelve a comprobar las correcciones con las tareas afectadas. Cinco sesiones sirven para descubrir dificultades concretas; no acreditan por sí solas que el producto sea fácil para toda su audiencia.

After five sessions, summarize outcomes by task, recurring errors and requests for help. Prioritize data loss and blockers, then repeat affected tasks after fixes. Five sessions help discover specific obstacles; they do not establish usability for the entire audience.

### Registrar la evidencia / Record evidence

El kit incluye `word-review.csv` e `INSTRUCTIONS.txt`. Ejecuta Word con salida `<kit>/word-verified`; inspecciona todas sus páginas y registra pass/fail, revisor, fecha y SHA-256 del PDF. Completa las quince tareas P1–P5 con observador, fecha, tiempos, ayudas y resultado `independent`, `assisted` o `blocked`. `python scripts/prepare-external-acceptance.py --summarize <kit>` valida consistencia y muestra avance sin alterar los registros. La automatización Word, la inspección visual y las sesiones conservan estados separados; quince filas registradas no equivalen a aceptación general de usabilidad. El manifiesto distingue el commit de las modificaciones locales.

The kit provides separate evidence for native Word automation, visual inspection and participant sessions. Run the summary command to validate document hashes and observation completeness without changing records. It does not authenticate participant identities or replace human assessment of usability. Keep completed participant records outside the public repository.

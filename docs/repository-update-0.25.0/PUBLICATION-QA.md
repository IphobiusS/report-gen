# report-gen 0.25.0 — verificación de publicación

> **Evidencia de publicación.** Los archivos técnicos citados se conservan archivados fuera de GitHub y no se adjuntan en este repositorio. El resumen siguiente documenta la ejecución local ya realizada; esta edición documental no representa una nueva ejecución.

La instalación editable con el extra `dev` y `requirements-audited.txt` terminó correctamente en un entorno virtual nuevo externo al repositorio. `npm ci --ignore-scripts`, `pip check` y Ruff aprobaron. Los 817 archivos del manifiesto inicial permanecieron idénticos al terminar.

| Comprobación | Resultado |
|---|---:|
| Python: YAML 0.25, firma/huella, señales POSIX y contrato de instalación | 162 aprobadas, 0 fallos, 0 omitidas |
| Node: guardado y borradores | 12 aprobadas, 0 fallos |
| UI 0.25: retest, revisión y ajuste de vista previa | 67 controles aprobados |
| Perfiles UI | 32 de retest + 12 de portada |
| Consola JavaScript / solicitudes externas | 0 / 0 |
| CLI PDF, DOCX, Markdown ZIP, HTML | 4 exportaciones abiertas y verificadas |

El ejemplo existente `tests/fixtures/sections.yaml` conserva título, resumen y hallazgo en los cuatro formatos. El PDF contiene seis páginas. `start.py --help`, `export.py --help` y `start.py --diagnose` terminan correctamente. El diagnóstico confirma WeasyPrint y Word listos; la alternativa PDF mediante Playwright de Python no está instalada. La geometría usa Playwright de Node y el Chromium existente, sin descargar navegadores.

Entorno: Linux, Python 3.12.14, Node 24.19.0, npm 11.9.0, Playwright 1.62.1, Chromium 153.0.8010.0, WeasyPrint 70.0, pytest 9.1.1, Ruff 0.17.0. El inventario completo `pip-freeze.txt` permanece archivado fuera de GitHub y no se adjunta al repositorio.

Esta es una verificación focal de publicación, no una nueva ejecución de la auditoría histórica completa. Se ejercitó el launcher real y sus señales en POSIX; los casos de limpieza Windows son simulados. El contrato de `--setup` se comprobó con prueba unitaria y las dependencias se instalaron realmente en el entorno externo; no se ejecutó `--setup` para crear otro entorno local. El DOCX se abrió programáticamente, sin Word de escritorio. No se publicó ni se ejecutaron flujos remotos de GitHub.

Evidencia archivada fuera de GitHub, no adjunta en este repositorio: `publication-validation.json`, `publication-smoke.json`, `selected-tests.xml`, `ui-geometry/results.json`, `runtime-final-integrity.json`, `documentation-links.json`, `pip-freeze.txt`, registros de instalación/comandos y los cuatro archivos exportados bajo `export-smoke/`. Aquí se publica únicamente el resumen de los resultados locales y sus límites, sin logs ni rutas internas del entorno. Esta selección documental conserva idénticos los bytes del código operativo y de los recursos de la aplicación; no añade ejecuciones de pruebas a las aquí descritas.

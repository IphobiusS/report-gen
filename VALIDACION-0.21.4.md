# Validación de report-gen 0.21.4

Fecha: 2026-10-08. Auditoría conjunta de la herramienta y del sitio que la distribuye. Entorno Linux, Python 3.12, Node 24, Playwright 1.62.1 y Chromium 153.0.8010.0. Datos de prueba sintéticos y temporales.

## Cambios comprobados

**Severidad con vector y sin puntuación escalar.** La versión anterior aceptaba un hallazgo `low` con un vector CVSS 3.1 de 9,8 si `cvss` no existía, era nulo o estaba vacío. Se aplica la comprobación de coherencia que ya existía para puntuaciones guardadas al resultado del vector admitido. El cálculo se usa para validar; no se incorpora una puntuación al proyecto ni se inventa un valor visible en el informe. Se cubren CVSS 3.1 y 4.0, español e inglés, cero explícito y exportación API en los cuatro formatos.

**Tema nulo.** `meta.theme: null` pasaba la validación final, pero el renderizador rechazaba después el tema. Ahora se rechaza antes de capturar la entrega. La ausencia del campo conserva el valor predeterminado. La normalización preexistente del editor a `serio` se conserva; no se presenta este caso como un fallo 500 de su interfaz.

**Limpieza demostrada.** Se retiran `CVSS_VECTOR_RE` de `validate.py` e `IMG_RE` de `safe_markup.py`, sin consumidores en el proyecto. Se corrigen los comentarios que describían CVSS 3.0 como admitido o CVSS 4.0 como pendiente. Las funciones públicas de compatibilidad permanecen.

## Resultados

| Control | Resultado |
| --- | --- |
| Suite Python completa final | 1.112 aprobados, 0 fallos, 0 errores, 0 omisiones (299,10 s) |
| Contratos nuevos incluidos en Python | 62 aprobados |
| Los mismos 62 contratos sobre 0.21.3 | 31 fallan y 31 pasan |
| Guardado y borradores, `npm test` | 12 aprobados |
| Workspace DOM/API | 29 comprobaciones aprobadas |
| Editor, Chromium real | 72 comprobaciones aprobadas |
| Exportación y anexos, Chromium real | 48 comprobaciones aprobadas |
| Recuperación, privacidad y respaldos, Chromium real | 24 comprobaciones aprobadas |
| Ruff, reglas E9/F del proyecto | Aprobado |

Los tres recorridos Chromium terminaron con código 0 y sin excepciones JavaScript. Los contratos nuevos se ejecutaron contra copias aisladas de ambas versiones con la misma expectativa, en lugar de utilizar un detector distinto para el código antiguo. La suite completa se ejecuta después de congelar el código corregido. Los contratos portátiles reciben el ejecutable de Chromium real; cualquier omisión se declara expresamente en el resultado.

## Reproducción

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci --ignore-scripts
npx playwright install chromium
export REPORT_GEN_CHROMIUM="$(node -p "require('playwright').chromium.executablePath()")"
.venv/bin/python -m pytest
npm test
npm run test:workspace
RG_PYTHON=.venv/bin/python node tests/test_editor_browser_0213.cjs --output out/editor-chromium
RG_PYTHON=.venv/bin/python node scripts/audit-browser-0210.cjs --browser chromium --output out/browser-chromium
RG_PYTHON=.venv/bin/python node scripts/audit-browser-0211.cjs --browser chromium --output out/recovery-chromium
.venv/bin/python -m ruff check .
```

Las denominaciones históricas de los scripts no cambian la versión que prueban. `REPORT_GEN_PLAYWRIGHT_MODULE` puede apuntar al módulo Playwright cuando no está en la resolución normal de Node. Los scripts del editor también admiten `RG_CHROMIUM_EXECUTABLE`.

## Distribución e integración

La identidad Python y npm es 0.21.4. `MANIFEST-0.21.4.sha256` enumera todos los archivos distribuidos salvo el propio manifiesto. Se verifican los miembros y sus hashes, y se generan e inspeccionan HTML, PDF, Markdown y DOCX desde una extracción independiente. La distribución no incorpora datos privados ni archivos temporales de la auditoría.

El sitio actualiza su descarga y guía a esta versión, con tamaño y SHA-256 comprobados. Las capturas antiguas siguen identificadas como 0.21.2 y los PDF públicos conservan su procedencia histórica. La demo Nimbus, las dependencias, los perfiles y el formato de respaldo no se modifican en este parche.

## Límites y mejoras posteriores

El resultado permite publicar esta corrección para el flujo local documentado en Linux/Chromium; no constituye una garantía de ausencia de defectos. No se ejecutaron Firefox local, Windows, macOS, Microsoft Word de escritorio ni lectores de pantalla en esta ronda, ni una CI remota o un nuevo análisis de vulnerabilidades de dependencias.

Los inspectores de exportación conservan sus límites documentados; no certifican toda la geometría, accesibilidad o asociación visual del informe. Los PDF públicos de ejemplo carecen de etiquetado estructural completo: mejorar ese etiquetado o ofrecer un equivalente HTML accesible queda como trabajo posterior. El aviso de puntuación ausente puede explicar mejor que un vector permite validar la clasificación aunque no exista una puntuación escalar guardada.

Los resultados detallados del ciclo anterior permanecen en `AUDITORIA-0.21.3.md` y `VALIDACION-0.21.3.md`; sus cifras y fechas son históricas.

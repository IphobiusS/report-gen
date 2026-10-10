# Validación de report-gen 0.21.3

Fecha: 2026-10-08. Entorno local Linux, Python 3.12, Node 24.19.0, Playwright 1.62.1 y Chromium 153.0.8010.0. Ejecuciones sobre proyectos sintéticos desechables y copias de los informes; sin modificar el sitio suministrado ni el PDF de Banco Lumbre.

## Resultados ejecutados

| Control | Resultado | Alcance |
| --- | --- | --- |
| Suite Python original 0.21.2 | 854 aprobados | Referencia completa, no prueba de ausencia de defectos. |
| Suite Python corregida 0.21.3 | 1.050 aprobados, 0 fallos, 0 errores, 0 omisiones | Incluye la integración DOM con la API real y el navegador portátil. 305,90 s. |
| Regresiones nuevas de HTML portátil | 16 aprobadas | ES/EN, diseño por secciones y heredado; reflow, filtros, anclas, teclado, sin JS e impresión. Incluidas en la suite Python. |
| Regresiones nuevas de exportaciones | 117 aprobadas | HTML, PDF, Markdown, Word; WebP, CVSS ausente/null/vacío/cero, referencias literales, enlaces y mutaciones. Incluidas en Python. |
| Regresiones nuevas de biblioteca | 40 aprobadas | Formas Markdown, código literal, variables, bibliografía y rutas privadas Windows. Incluidas en Python. |
| Regresiones nuevas de entrada YAML | 16 aprobadas | Constructores inválidos, entradas válidas, GET/importación y ausencia de estado parcial. Incluidas en Python. |
| Regresiones nuevas de respaldo | 7 aprobadas | Recuperación heredada y sus imágenes, colisiones Unicode, fallos tras commit y reintento de limpieza. Incluidas en Python. |
| `npm test` | 12 aprobadas | Gestor de guardado y borradores. |
| `npm run test:workspace` | 29 aprobadas | DOM/API del espacio de trabajo. |
| Navegador del editor 0.21.3 | 72 comprobaciones aprobadas | Modales, importación inválida/válida, cambios concurrentes, proyecto cambiado, Deshacer, móvil y avisos de restauración. |
| Recorrido adicional Nimbus | 29 comprobaciones aprobadas | Editor, evidencias, revisión, entrega HTML, idiomas, redimensionado, 503 y conflicto de pestañas. |
| Axe sobre Nimbus | 12 vistas; 0 infracciones detectadas | Reglas WCAG 2 A/AA y 2.1 A/AA ejecutadas. Hay resultados incompletos; no es certificación. |
| Ruff | Aprobado | Reglas `E9` y `F` configuradas en pyproject.toml. |

Las suites existentes de navegador se repitieron sobre el código final: `audit-browser-0210.cjs` aprobó 48 comprobaciones de crear, guardar, exportar y revisar anexos; `audit-browser-0211.cjs` aprobó 24 de conflictos, fallos de almacenamiento, reinicio, privacidad y respaldo restaurado. Ambas terminaron sin excepciones JavaScript.

La suite Python final emitió seis avisos: deprecación de `Image.getdata()` dentro de pruebas de colores de logos y un nombre ZIP duplicado creado deliberadamente por una prueba negativa. No hubo omisiones de pruebas de navegador: se proporcionó el ejecutable real mediante `REPORT_GEN_CHROMIUM`.

## Evidencia contra el original

Se ejecutaron los mismos contratos sobre la fuente 0.21.2 aislada, sin adaptar el defecto a un detector separado:

| Contratos | Original | Corregido |
| --- | --- | --- |
| HTML portátil | 12 fallos, 4 aprobados | 16 aprobados |
| Biblioteca | 29 fallos, 11 aprobados | 40 aprobados |
| YAML | 12 fallos, 4 aprobados | 16 aprobados |
| Respaldo | 7 fallos | 7 aprobados |
| Contratos focales del editor | 3 fallos, 2 aprobados | 5 aprobados |

La revisión de exportaciones conserva reproducciones independientes del rechazo WebP, vector omitido, referencia literal alterada, imagen enlazada perdida, referencia mutada aceptada y API de perfil sin contrato. El nuevo módulo además verifica que las mutaciones de contenido/destino/píxeles/contexto sean rechazadas. No se atribuye un conteo global antes/después a casos que no se ejecutaron juntos sobre el original.

## Navegador y revisión visual

El HTML de Banco Lumbre ES y dos informes sintéticos ES/EN se midieron a 320/360/390/601/768/1366 px: 18 estados sin desbordamiento de página ni errores JS. Antes: Banco Lumbre ES 345 px a 320 y 365 px a 360; muestra EN 322 px a 320. El SHA-256 de `<main>` fue idéntico antes/después para las tres muestras.

Se renderizaron y revisaron tres DOCX finales, cuatro páginas cada uno, con LibreOfficeDev 26.8.0.0.alpha0: imagen enlazada, estilos dentro de enlace y WebP. Se comprobó igualdad de sus páginas finales con las páginas ya inspeccionadas. También se revisaron las cuatro páginas del PDF final con `cvss: null` y vector presente. HTML, Markdown, Word y PDF de las variantes null/vacía/cero en ES/EN pasaron el inspector correspondiente.

Las comprobaciones automáticas de accesibilidad mantienen resultados incompletos de `color-contrast` y `label-content-name-mismatch` para revisión humana. Los contratos de teclado prueban Tab, Shift+Tab, Escape, Enter, Space, foco inicial/restaurado y bloqueo del fondo; no equivalen a ejecutar un lector de pantalla.

## Reproducir

Instala dependencias de desarrollo dentro del entorno del proyecto y los navegadores que quieras ejecutar:

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

`REPORT_GEN_CHROMIUM` apunta al ejecutable Chromium. Si Playwright no está en la resolución habitual de Node, `REPORT_GEN_PLAYWRIGHT_MODULE` puede apuntar a su módulo. Los scripts del editor también permiten `RG_CHROMIUM_EXECUTABLE`; si se omite, usan el navegador instalado por Playwright. Sin el runtime requerido, los contratos portátiles indican omisión: revisar ese resultado, no contarlo como aprobación.

El workflow `browser-acceptance.yml` incorpora los contratos nuevos en el trabajo Chromium y sus artefactos de salida. Conserva los trabajos anteriores Chromium/Firefox. No se ejecutó una CI remota en esta sesión.

## Paquete y compatibilidad

La entrega usa la identidad 0.21.3 en Python y npm y un manifiesto nuevo `MANIFEST-0.21.3.sha256`, que enumera todos los archivos de la distribución excepto el propio manifiesto. La comprobación del ZIP exige integridad de cada miembro, conjunto de nombres idéntico al manifiesto y ausencia de caches, proyectos temporales y dependencias de auditoría. Sobre una extracción independiente se comprueba la identidad y se generan/inspeccionan las cuatro exportaciones del ejemplo de severidad pendiente.

Se mantuvieron las dependencias, la demo Nimbus, los perfiles y el formato portable de respaldo versión 1. El módulo nuevo `reusable_markup` está registrado en pyproject.toml. Un `.bak` heredado válido se conserva como snapshot estándar y sus bytes originales en los objetos del historial; no exige un miembro ZIP nuevo incompatible.

No se ejecutaron Firefox local, Microsoft Word de escritorio, Windows, macOS ni lectores de pantalla en esta ronda. LibreOfficeDev no garantiza paginación igual a Word nativo. No se revalidaron bases externas de vulnerabilidades de dependencias. La comparación de PDF conserva sus límites: presencia textual, imágenes e índice no certifican espacios de código ni asociación visual de todos los bloques.

La herramienta sigue siendo local y de un único proceso. Biblioteca, detector de secretos e inspectores de exportación no sustituyen la revisión de contenido privado y la aceptación visual. Consulte AUDITORIA-0.21.3.md para los defectos y propuestas, y README.md para el caso de migración de `.bak` desde 0.21.2.

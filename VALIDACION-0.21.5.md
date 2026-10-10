# Validación de report-gen 0.21.5

Fecha: 2026-10-08. Linux, Python 3.12, Node 24, Playwright 1.62.1 y Chromium 153.0.8010.0. Proyectos sintéticos temporales y una copia pública de Banco Lumbre, sin ejecución contra una entidad real.

## Defectos corregidos

Las tablas del HTML portátil empleaban `table-layout:fixed` para cualquier contenido. Las fichas de un hallazgo reservaban aproximadamente la mitad del ancho a las etiquetas: en escritorio generaban columnas vacías muy amplias; a 320 px dejaban unos 114 px para descripciones extensas. Las tablas comparativas estrechas fragmentaban expresiones como `4×5=20` en dos líneas. No se perdían datos y las pruebas de overflow y axe podían aprobar, pero la lectura era deficiente.

La exportación distingue fichas de campo/valor de tablas comparativas. Las etiquetas tienen anchura acotada y alineación superior en escritorio; en móvil se apilan con el valor, conservando la relación de encabezado y celda. Las comparativas amplias se desplazan dentro de una región con nombre y acceso por teclado; la página conserva su ancho. La impresión utiliza una disposición tabular independiente del ancho mínimo de pantalla. Las comparativas de dos columnas con encabezados reciben la misma región de datos; las palabras de su primera columna se conservan completas. La tabla TD/TD de portada se mantiene intacta.

Se reprodujo además un salto durante la descarga por streaming: la barra de filtros aparecía después de la portada. Un arranque mínimo en head reserva su geometría en pantalla; los controles siguen invisibles hasta que el script instala los eventos. Sin JavaScript, la barra se omite y todo el informe permanece disponible. Ambos scripts están autorizados por sus hashes CSP. La cuenta inicial de resultados se genera con el documento para que su aparición no cambie el reparto de la barra.

La fuente embebida Carlito utiliza `font-display:optional` únicamente en el HTML portátil. Cuando no alcanza la ventana inicial, se conserva la fuente de respaldo sin un intercambio tardío; no se afirma que Carlito se aplique en todas las cargas. El motor PDF y sus fuentes permanecen intactos.

No se cambia el esquema del proyecto ni se retocan manualmente los documentos exportados. Los inspectores comprueban la conservación de contenido, tablas, referencias y evidencia. Los PDF originales públicos permanecen íntegros.

## Resultados finales

| Control | Resultado |
| --- | --- |
| Contratos nuevos: tablas, semántica y streaming | 16/16 nuevos; 32/32 al repetir también los contratos portátiles heredados |
| Los mismos contratos sobre 0.21.4 | 12 fallan y cuatro pasan, con la misma expectativa |
| Suite Python completa | 1.128 aprobados, cero fallos, errores u omisiones; 350,22 s |
| JavaScript: guardado y borradores | 12 aprobados |
| Workspace DOM/API | 29 comprobaciones aprobadas |
| Editor y exportación/recuperación en Chromium | 72 editor + 48 exportación/anexos + 24 recuperación/privacidad; todos código 0 |
| Ruff, E9/F | Aprobado para las reglas E9/F configuradas |
| Banco Lumbre, HTML completo | Inspector íntegro; ocho estados JS/sin JS, 19 flujos, 58 controles de tablas, 12 de títulos y 32 adicionales de comparativas de dos columnas; axe/overflow/errores 0; CLS streaming 0 a 390/1366 px |

Los casos nuevos cubren español/inglés y disposición por secciones/heredada. Los resultados originales y corregidos usan la misma expectativa. Las pruebas de navegador validan distribución, lectura, teclado, lectura sin JavaScript, impresión y primera carga con descarga parcial. No sustituyen un lector de pantalla. El contrato de contenido inerte del arnés anterior se actualiza para exigir los dos scripts legítimos y sus hashes CSP, conservando el rechazo de ejecución del contenido de prueba.

La suite Python completa terminó antes de los últimos ajustes del tamaño de h2 móvil y las comparativas de dos columnas. Después se repitieron los 32 contratos portátiles sobre la fuente definitiva, incluidas las expectativas de palabras completas, semántica y portada preservada. La aceptación de exportaciones de 48 comprobaciones se repitió asimismo sobre esa fuente. Editor, API, guardado y recuperación no cambiaron después de sus recorridos. Las seis advertencias de la suite completa corresponden a deprecaciones de librerías y un ZIP duplicado fabricado por una prueba negativa; no hubo fallos.

## Reproducir

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

Si Playwright no está en la resolución habitual de Node, `REPORT_GEN_PLAYWRIGHT_MODULE` puede apuntar a su módulo. Los scripts del editor también admiten `RG_CHROMIUM_EXECUTABLE`. No contar como aprobación los contratos omitidos por ausencia de navegador.

## Integridad y límites

La distribución identifica 0.21.5 en Python y npm. `MANIFEST-0.21.5.sha256` contiene las huellas de todos los archivos salvo el propio manifiesto. Se comprueban sus miembros, y desde una extracción independiente se generan e inspeccionan HTML, PDF, Markdown y DOCX.

Banco Lumbre se reexporta como HTML desde la misma captura pública que produjo su PDF original. Se conserva la procedencia de contenido 0.21.2; la nueva salida se identifica externamente como exportación 0.21.5, sin retest ni nuevas evidencias. Su valoración técnica y su índice de riesgo empresarial permanecen separados. El tamaño móvil de h2 evita una última letra aislada en Autoaprobación; escritorio e impresión conservan sus reglas.

No se anuncia PDF/UA. El ensayo separado de PDF etiquetado mostró que activar `pdf_tags=True` produce un árbol de estructura, pero todavía requiere resolver alternativas de figuras y artefactos, validación específica y lector de pantalla. Este parche mejora el HTML portátil; no cambia el motor PDF ni sus garantías.

No se ejecutaron Firefox local, Safari, Windows, macOS, Microsoft Word de escritorio, lectores de pantalla reales ni una CI remota en esta ronda. Los registros de 0.21.4 y 0.21.3 se conservan como historial. Los límites de los inspectores de exportación siguen vigentes.

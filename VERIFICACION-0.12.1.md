# report-gen 0.12.1 — Paginación continua

Fecha: 8 de septiembre de 2026. Actualización sobre report-gen 0.12.0.

## Comportamiento

- Se elimina la regla que iniciaba cada hallazgo en una página nueva.
- Dos o más hallazgos pueden compartir una página si caben.
- En PDF, el encabezado acompaña a la tabla principal del hallazgo.
- Las tablas de los hallazgos se conservan completas; si no caben en el espacio
  restante, pasan a la página siguiente.
- Los procedimientos extensos pueden continuar en otra página y el siguiente
  hallazgo aprovecha el espacio que queda.
- En Word se eliminan los saltos entre hallazgos y se protege cada tabla mediante
  filas indivisibles y párrafos enlazados hasta el final de la tabla.
- Los números de página del índice siguen el encabezado al desplazarse.
- Se mantienen los tamaños de fuente, los márgenes y el contenido del informe.

Una tabla mayor que el área útil de una página no puede conservarse entera sin
reorganizarla. El PDF detecta ese caso y devuelve el hallazgo que se debe ajustar,
sin modificar el proyecto guardado. La solución es resumir la tabla y pasar los
detalles al procedimiento, o repartir su contenido en tablas más pequeñas.

## Verificación ejecutada

**140 pruebas Python aprobadas**, sin fallos ni pruebas omitidas. La suite incluye
15 nuevos casos de paginación. Ruff no detectó errores. Las pruebas se ejecutaron
en Linux con Python 3.12 y WeasyPrint 70.0.

| Caso | Resultado |
| --- | --- |
| Hallazgos cortos | Comparten página; una muestra con tres hallazgos quedó completa en una sola página de contenido. |
| Cuatro temas | Serio, corporativo, OffSec y HTB comprobados mediante render real. |
| Dos estructuras | Informes por secciones y estructura clásica comprobados. |
| Tabla principal al final de página | Encabezado, contenido y marcador del índice permanecen en la misma página. |
| Tabla Markdown extensa que cabe en una página | Se desplaza entera; primera y última fila aparecen en la misma página. |
| Tabla mayor que una página | Exportación PDF rechazada; se conserva la salida anterior. |
| Error desde el editor/API | Respuesta 422 con ID del hallazgo y recomendación de ajuste; el YAML guardado permanece igual. |
| DOCX | Ambas rutas del exportador sin saltos entre hallazgos; propiedades de protección comprobadas para todas las filas. |
| Revisión visual DOCX | Muestras renderizadas con LibreOffice de 3 y 4 páginas, revisadas completas. |
| Comprobación por marcadores PDF | Lógica que acepta tablas completas y rechaza tablas repartidas entre páginas, probada sobre PDF reales. |

La suite emitió el aviso ya conocido de WeasyPrint sobre la futura necesidad de
HarfBuzz-Subset. Las pruebas y los PDF se completaron.

## Límites

- WeasyPrint comprueba el árbol de paginación real antes de escribir el PDF. Esta
  integración se mantiene aislada en `pdf_pagination.py` y cubierta por pruebas.
- Chromium incorpora una comprobación mediante marcadores temporales en un PDF
  previo, que se retiran de la salida final. La lógica de lectura de ese PDF se
  probó; Chromium completo y Windows no se ejecutaron en este entorno.
- El DOCX se compone al abrirlo. Word o LibreOffice pueden ignorar las instrucciones
  de mantener una tabla unida si la tabla supera una página completa. En DOCX
  debes reorganizar ese contenido; el bloqueo automático corresponde al PDF.
- Las fuentes y el programa utilizado pueden cambiar el número de páginas. La
  regla consiste en aprovechar el espacio disponible, no en imponer dos hallazgos
  exactos por página.
- Los saltos entre secciones principales y la portada se conservan.

## Actualización

Conserva `webapp/projects/` y cualquier informe propio al actualizar. Instala la
nueva versión desde la carpeta descomprimida y reinicia el servidor:

```bash
python -m pip install -e .
python webapp/app.py
```

Recarga la pestaña del editor. No es necesario migrar el YAML.

Para reproducir las pruebas, sigue el apartado de desarrollo del README:

```bash
python -m pip install -e ".[dev]"
npm ci --ignore-scripts
python -m pytest -q
ruff check .
```

Los casos específicos están en `tests/test_pagination.py`.

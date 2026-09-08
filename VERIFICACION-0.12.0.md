# report-gen 0.12.0 — Correcciones y verificación

Fecha: 8 de septiembre de 2026.
Base: el archivo `report-gen(1).zip` recibido, versión declarada 0.11.0.
Entrega: código fuente completo, con los nueve hallazgos de la auditoría corregidos.

## Qué se corrigió

| Hallazgo | Corrección | Comprobación |
| --- | --- | --- |
| RG-01 · Guardado en otro proyecto | Captura del proyecto y contenido al solicitar el guardado; navegación bloqueada hasta completarlo. | Pruebas de la cola JavaScript y del editor completo contra la API local. |
| RG-02 · Error anunciado como guardado | Comprobación HTTP, conservación de cambios pendientes y revisión de cada confirmación. | Error 500, respuestas antiguas y conflicto 409. |
| RG-03 · XSS en Markdown | Saneado de etiquetas, atributos y URL; HTML de los payloads conservado como texto. | Atributos de eventos, protocolos peligrosos, código literal y bases de imágenes concurrentes. |
| RG-04 · CVSS incoherente | Rango 0–10, valores finitos, vector completo, correspondencia vector/score/severidad y cero visible. | Valores fuera de rango, NaN, infinito, vectores incompletos o duplicados, y cero en HTML/DOCX/MD. |
| RG-05 · Estructuras inválidas | Validación de estructuras anidadas antes de guardar; arreglo de la traducción del validador. | Entradas mal formadas devuelven 422 sin alterar el YAML previo. |
| RG-06 · Pérdidas en Word | Conversión de Markdown a párrafos, tablas, enlaces, código e imágenes nativas. | Inspección del DOCX y revisión de sus páginas renderizadas con LibreOffice. |
| RG-07 · Markdown sin imágenes | ZIP con `report.md` y recursos relativos del proyecto. | Inspección del ZIP y descarga desde el editor. |
| RG-08 · Peticiones web ajenas | Host local, Origin, CSRF, cookie SameSite, contenido JSON y política CSP; recursos PDF restringidos. | Peticiones sin token, host/origen incorrectos, text/plain y rutas/URL no permitidas. |
| RG-09 · Gráfico PDF incorrecto | Colores explícitos y ancho suficiente para las etiquetas SVG. | Generación real con WeasyPrint y revisión visual del resumen. |

## Mejoras de integridad

- Escritura atómica y copia de una versión previa en `engagement.yaml.bak`.
- Botón **Restaurar** para recuperar esa versión del YAML.
- Revisión ETag/If-Match para evitar sobrescrituras entre pestañas.
- Exportaciones desde instantáneas que no modifican el proyecto guardado.
- Nombres únicos de imágenes para conservar las evidencias previas.
- Vista previa y título del selector actualizados tras el autoguardado.
- Dependencias Python/Node, CI, README y guía de migración actualizados.

## Resultados ejecutados

| Comprobación | Resultado |
| --- | --- |
| Suite completa pytest | **125 aprobadas**, 0 fallidas, 0 omitidas. |
| Pruebas Node del guardado | **5 aprobadas**, 0 fallidas. |
| Ruff | Sin errores. |
| Sintaxis JavaScript del editor y prueba de integración | Correcta. |
| CVSS 4.0 frente a `cvss==3.6` de referencia | **20.087 vectores**, 270/270 MacroVectors, **0 divergencias**. |
| PDF | Generación real del informe canónico de 12 páginas y de una muestra de contenido enriquecido de 3 páginas. |
| DOCX | Apertura y renderizado con LibreOffice: informe canónico de 11 páginas y muestra de 2 páginas; revisión visual de todas las páginas. |
| Recursos Markdown | ZIP con texto e imágenes; las rutas relativas se conservan. |
| Integración del editor | Carga, guardado/cambio de proyecto, CSRF, autoguardado con preview, exportación ZIP, validación y conservación ante conflicto. |

La suite Python emitió un aviso de deprecación de WeasyPrint sobre una futura
necesidad de HarfBuzz-Subset. Las pruebas y los PDF actuales se completaron.
La guía de instalación incluye esa biblioteca del sistema.

Las pruebas se ejecutaron en Linux con Python 3.12, Node 24, Flask 3.1.3,
WeasyPrint 70.0, python-docx 1.2.0, nh3 0.3.7, lxml 6.1.1 y jsdom 26.1.0.

## Reproducir

Desde la carpeta `report-gen`, con el entorno Python activado y Node 22 o posterior:

```bash
python -m pip install -e ".[dev]"
npm ci --ignore-scripts
python -m pytest -q
npm test
ruff check .
```

El sello CVSS se reproduce con `seal_upstream.py`, siguiendo el entorno aislado
descrito en ese archivo. Los casos de regresión están en
`tests/test_regressions.py`, `tests/test_save_manager.cjs`,
`tests/test_ui_integration.py` y `tests/ui_integration.cjs`.

## Instalar o actualizar

Lee el apartado **Actualizar sin perder proyectos** del README. Conserva la
instalación anterior y copia sus carpetas de proyectos e imágenes a la nueva.
Para usar el editor, desde la carpeta del proyecto:

```bash
python -m pip install -e .
python webapp/app.py
```

Abre `http://127.0.0.1:8080`. Si ya tenías una pestaña abierta, recárgala.
Node.js solo es necesario para las pruebas de desarrollo.

Cambios de compatibilidad: Markdown ahora descarga un ZIP; los clientes API
propios necesitan sesión/CSRF y ETag; un informe inválido puede guardarse como
borrador si su estructura es correcta, pero no se exportará hasta corregirlo.

## Límites de la verificación

- La integración del editor usa un DOM simulado con jsdom y una API HTTP real.
  No constituye una prueba visual o de compatibilidad en Chrome, Firefox o Safari.
- Windows, macOS y la alternativa PDF Chromium no se ejecutaron en esta entrega.
- Word y PDF pueden tener diferente paginación y sustitución de fuentes.
- La copia automática conserva una versión del YAML; no es un historial completo
  ni un respaldo de toda la carpeta. Los cambios pendientes en memoria necesitan
  atención antes de cerrar o recargar una pestaña con errores de guardado.
- La herramienta conserva su propósito local y monousuario. No incorpora usuarios,
  colaboración remota ni cifrado de proyectos.
- Las correcciones y pruebas cubren los problemas identificados y casos concretos;
  no son una certificación ni una garantía de ausencia de todos los errores posibles.

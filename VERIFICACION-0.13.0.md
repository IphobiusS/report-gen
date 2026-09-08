# Verificación de report-gen 0.13.0

Fecha: 2026-09-08. Se verificó la aplicación completa y las funciones nuevas, sobre la versión 0.12.1 que corregía la paginación.

## Resultado

- **187 pruebas Python aprobadas**, sin fallos (62,15 segundos en la ejecución final).
- **5 pruebas JavaScript del guardado aprobadas**, sin fallos.
- **Ruff: sin errores**. Sintaxis de los módulos JavaScript comprobada.
- PDF real mediante WeasyPrint, DOCX real mediante python-docx y ZIP de Markdown con imágenes generados correctamente.
- Ejemplo integral revisado visualmente: 8 páginas PDF y 7 páginas Word renderizadas mediante LibreOffice. Se comprobó la versión final de las páginas modificadas; las restantes eran idénticas en píxeles a las ya revisadas.

## Comprobaciones de las funciones nuevas

| Área | Evidencia de verificación |
| --- | --- |
| Compatibilidad | Migración de YAML antiguo; preservación del contenido; referencia permanente estable tras abrir, guardar y reordenar. |
| Versiones | Etapas con nombre, deduplicación de imágenes, comparación entre versiones y con el estado actual, restauración de bytes de YAML e imágenes y recuperación ante un fallo simulado de intercambio de carpetas. |
| Respaldo | Exportación e importación completas con originales e historial; rechazo de destino existente; integridad SHA-256 de archivos. |
| Importación hostil | Rechazo de traversal, rutas absolutas y de Windows, duplicados por mayúsculas/minúsculas, enlaces simbólicos, archivos no permitidos, imágenes falsas, hash alterado y límites de expansión. |
| Evidencias | Censura comprobada en píxeles negros; original conservado; ausencia de metadatos en el PNG procesado; anotaciones aplanadas; censura aplicada sobre anotaciones superpuestas. |
| Entrega | El ZIP Markdown incluye solamente las imágenes procesadas referenciadas; recursos de originales e historial rechazados; referencias inexistentes impiden exportar en los tres formatos. |
| Retest | Nuevos registros con identificadores distintos, cambio correcto de estado y evidencias vinculadas. |
| Revisión | Omisiones, TODO, pasos ausentes, recursos rotos y navegación al campo desde el editor. |
| Biblioteca | Retirada de campos del cliente, sustitución de variables, nuevos IDs al insertar, etiquetas, versiones, control de revisión e importación atómica. |
| Informes | Activos, cobertura, limitaciones, responsables, estados, fechas y resultados presentes en HTML, Word y Markdown; números de página del índice PDF para las secciones nuevas. |
| Paginación | Regresiones de 0.12.1 conservadas: varios hallazgos por página y protección de las tablas en los cuatro temas, tanto con secciones como en formato heredado. |
| Editor | Editor completo con jsdom y API HTTP Flask real: alta de activos/cobertura, revisión y navegación, retest, versiones, plantilla reutilizable, respaldo, edición de evidencia y restauración posterior. |

También se conservan las pruebas existentes de CVSS 3.1 y 4.0, saneado de Markdown, aislamiento de recursos, sesiones CSRF, guardado atómico y conflictos entre pestañas. El motor CVSS no fue modificado en esta ampliación.

## Reproducción

Desde la raíz del proyecto, con Python y Node.js 22 o posterior:

```bash
python -m pip install -e ".[dev]"
npm ci --ignore-scripts
python -m pytest
npm test
ruff check .
```

Para la demostración manual, abre `examples/workflow-demo-project.zip` mediante **Abrir respaldo**. Contiene exclusivamente datos ficticios, una entrega inicial y una versión de retest.

## Límites de la verificación

- Entorno verificado: Linux, Flask 3.1.3, WeasyPrint 70.0, python-docx 1.2.0 y Pillow 12.3.0. El renderizado de Word se revisó con LibreOffice.
- La interfaz se probó con un DOM simulado y una API HTTP real; no se afirma una comprobación visual del editor en todos los navegadores.
- No se ejecutaron Windows, Microsoft Word ni el renderizador opcional Chromium. Las pruebas del verificador de límites PDF compartido no equivalen a ejecutar Chromium.
- WeasyPrint emitió un aviso de deprecación sobre HarfBuzz-Subset para versiones futuras; no impidió los renders ni las pruebas.
- La revisión de entrega detecta omisiones conocidas; no determina por sí sola la corrección técnica ni la exhaustividad de un pentest.
- Las plantillas requieren revisar el texto libre para evitar datos de otro cliente. Los respaldos editables incluyen originales e historial y no están cifrados.
- El historial conserva versiones del editor; no reconstruye archivos eliminados antes de que existiera una instantánea. No se incorpora colaboración multiusuario ni sincronización remota.

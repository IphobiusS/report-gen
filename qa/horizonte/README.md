# Banco Horizonte Austral — caso ficticio complejo

Este caso ejercita la generación documental de report-gen con una entidad bancaria **completamente ficticia**. No contiene datos de clientes, credenciales operativas, hallazgos reales ni resultados de un pentest. Los destinos usan `.example` y las redes de documentación `192.0.2.0/24`, `198.51.100.0/24` y `203.0.113.0/24`; el constructor nunca los contacta.

## Reconstrucción de las entradas

Desde la raíz del repositorio, dentro del entorno de report-gen:

```sh
python scripts/build-horizonte-case.py --output /tmp/horizonte-case --languages es en pt
```

El directorio de destino debe ser nuevo. El comando compone proyectos YAML, imágenes PNG sintéticas deterministas, anexos y archivos de importación; **no genera informes** PDF, DOCX, Markdown ni HTML. Usa las fuentes empaquetadas con report-gen para dibujar las imágenes y calcula los valores CVSS con su implementación. No necesita servicios externos ni herramientas de escaneo.

La API Python equivalente es `build_case(output: Path, languages=('es', 'en', 'pt'))`, que devuelve el manifiesto. `make_project(language='es')` devuelve los datos sin escribir archivos; las rutas de imágenes y anexos requieren ejecutar el constructor completo antes de exportar.

El árbol generado contiene:

- `projects/{es,en,pt}/engagement.yaml`, imágenes, un original privado y anexos.
- `inputs/findings.csv`, `burp.xml`, `nuclei.jsonl`, `nmap.xml` y `sarif.json`.
- `manifest.json`, con hashes, tamaños, conteos y resultados de validación de las entradas.

Los proyectos comparten prosa española y contenido de seguridad idéntico. `meta.lang` cambia las etiquetas, la navegación y la presentación de report-gen a español, inglés o portugués. **Las variantes EN/PT no son traducciones completas de la prosa del caso**, y el propio informe declara esa limitación. Los UUID, fechas y bytes son estables para el mismo entorno de dependencias.

## Alcance del caso

| Elemento | Cantidad / cobertura |
| --- | --- |
| Vulnerabilidades ficticias | 24: 3 críticas, 7 altas, 8 medias, 4 bajas y 2 informativas |
| Cuadernos de máquinas | 3; no cuentan como vulnerabilidades |
| Activos | 12: web, móvil, API, identidad, directorio, administración, nube, conciliación, observabilidad, tercero y recuperación |
| Evidencias | 24 PNG dibujados; 22 apaisados y 2 verticales |
| Marca y portada | 2 PNG adicionales |
| Secciones de autor | 16: las 13 del catálogo más 3 anexos personalizados |
| Proyecciones del flujo | Inventario, cobertura, causas raíz y retest |
| Cobertura | 48 contratos: caso permitido y rechazado por hallazgo |
| Causas raíz | 4 grupos con relaciones por UUID |
| Registros de retest | 9, incluida una nota sin fecha |
| Anexos | 4 revisados e incluidos; 1 privado y excluido |
| CVSS | 3.1 y 4.0; puntuación y severidad calculadas y coherentes |
| Estados | Todos los estados de seguimiento, todos los resultados de retest y los 4 estados de cobertura |

Los estados, la aceptación de riesgo y los resultados de retest son partes inventadas del guion. No deben interpretarse como controles ejecutados o aprobaciones reales. Cada figura declara que no es una captura bancaria. La documentación no atribuye conformidad regulatoria ni porcentajes de madurez.

El caso contiene tablas extensas de 48 filas, listas anidadas, bloques literales inertes, Unicode latino, URL larga con parámetros codificados y fragmento Unicode, referencias internas, cadenas narrativas, evidencia reutilizada y anexos con hashes. F12 incorpora tres bordes de imagen dentro de tabla: una imagen enlazada, dos imágenes bajo un mismo enlace y texto pegado a una imagen dentro de una autorreferencia. Esto permite repetir las regresiones encontradas en la preparación de esta ronda.

## Generación exclusivamente con report-gen

Usar el exportador público, que aplica la frontera de publicación y mantiene los originales privados:

```sh
python export.py /tmp/horizonte-case/projects/es/engagement.yaml --format pdf -o /tmp/horizonte-es.pdf
python export.py /tmp/horizonte-case/projects/es/engagement.yaml --format docx -o /tmp/horizonte-es.docx
python export.py /tmp/horizonte-case/projects/es/engagement.yaml --format md -o /tmp/horizonte-es-markdown.zip
python export.py /tmp/horizonte-case/projects/es/engagement.yaml --format html -o /tmp/horizonte-es.html
```

La API es `export.export(yaml_path, format, output_path)`. El registro `export_formats.REGISTRY` define los cuatro formatos admitidos. La entrega verificable se debe capturar y revisar mediante las funciones de `delivery`; construir las entradas o exportar un archivo no acredita por sí solo que una entrega haya pasado la auditoría.

Para una selección técnica reducida que pruebe tablas, vínculos y diagrama de máquina, usar F01, F12 y M01 mediante la función de audiencia de report-gen. F12 sólo se enlaza a sí mismo; las referencias entre hallazgos están en las secciones narrativas generales. Eliminar esas secciones del perfil parcial según las reglas de audiencia. El comparador PDF conserva su límite de 80 páginas y puede usar esa exportación parcial si el documento completo lo supera.

## Importadores y publicación

Las cinco entradas de escáner son fabricadas. La vista previa CSV contiene dos filas válidas con una identidad duplicada deliberada. Burp y Nuclei tienen un resultado cada uno. Nmap contiene un host de documentación y dos puertos. SARIF 2.1.0 contiene un resultado del driver y otro de una extensión autocontenida. El constructor ejecuta las vistas previas de report-gen y rechaza errores estructurales; no aplica las filas al proyecto de 24 vulnerabilidades.

Tres canarios comprueban la publicación:

- `HORIZONTE_PRIVATE_INBOX_DO_NOT_PUBLISH_2026`: nota de bandeja y anexo privado; debe quedar fuera de la entrega pública.
- `HORIZONTE_SYNTHETIC_REDACTION_CANARY_2026`: texto ficticio en F13, con sustitución literal configurada explícitamente.
- `HORIZONTE_PRIVATE_IMAGE_METADATA_2026`: metadato PNG; debe retirarse de las imágenes publicadas sin cambiar el contenido visible.

El inventario de anexos es independiente del cuerpo del informe: no se supone que el PDF incorpore automáticamente archivos seleccionados. Las entradas `originals/` y la bandeja privada permanecen en el proyecto. Ningún canario es un secreto real.

`coverage-plan.json` registra el plan de aceptación amplio. Un elemento sólo se considera comprobado cuando existe su evidencia; generar este caso no significa haber cubierto todas las funciones, todos los diseños ni todos los renderizadores de report-gen.

## Recorridos reproducibles

Con un directorio de salida nuevo para cada ejecución:

```sh
python scripts/audit-horizonte-exports.py --projects /tmp/horizonte-case/projects --output /tmp/horizonte-exports --mode all
python scripts/audit-horizonte-lifecycle.py --case /tmp/horizonte-case/projects/es --output /tmp/horizonte-lifecycle --ui-bundle /tmp/horizonte-input.zip --pdf /tmp/horizonte-exports/principal/es/outputs/informe.pdf
python scripts/audit-horizonte-supplement.py --case /tmp/horizonte-case/projects/es --pdf /tmp/horizonte-exports/principal/es/outputs/informe.pdf --output /tmp/horizonte-supplement
RG_PYTHON=python node scripts/audit-horizonte-browser.cjs --bundle /tmp/horizonte-input.zip --project-dir /tmp/horizonte-case/projects/es --input-dir /tmp/horizonte-case/inputs --before-pdf /tmp/horizonte-lifecycle/audiences/executive.pdf --after-pdf /tmp/horizonte-lifecycle/audiences/public.pdf --slug horizonte-es --allow-export --output /tmp/horizonte-browser
RG_PYTHON=python node scripts/audit-horizonte-authoring.cjs --bundle /tmp/horizonte-input.zip --project-dir /tmp/horizonte-case/projects/es --pdf /tmp/horizonte-exports/principal/es/outputs/informe.pdf --slug horizonte-authoring --output /tmp/horizonte-authoring
RG_PYTHON=python node scripts/audit-horizonte-recovery.cjs --bundle /tmp/horizonte-input.zip --project-dir /tmp/horizonte-case/projects/es --slug horizonte-recovery --output /tmp/horizonte-recovery
python scripts/audit-horizonte-updater.py --case /tmp/horizonte-case/projects/es --output /tmp/horizonte-updater --allow-network
```

La matriz completa incluye 12 exportaciones principales, 20 de los otros cinco temas generales y 120 PDF/DOCX de los 30 diseños especializados en sus dos apariencias. Estos últimos utilizan la selección técnica F01/F12/M01. Los recibos vinculan las entradas y el código productor mediante SHA-256; no reutilizar resultados después de modificar el productor. `--native-executable /usr/bin/libreoffice --require-stable` añade la inspección del DOCX con LibreOffice estable, que no equivale a una prueba de Microsoft Word.

El recorrido API utiliza una copia aislada para importaciones, censura, firmas, remediación y recuperación. El recorrido Chromium importa el ZIP inicial y conserva capturas reales; requiere Playwright y su navegador instalados. Tesseract permite ejecutar OCR local. Las dependencias opcionales ausentes se registran como límites, nunca como funciones aprobadas. La inferencia de un modelo Ollama requiere su instalación y no se inicia automáticamente.

Los recorridos adicionales comprueban creación desde galería, orden de secciones, visor y registro autodeclarado, filtros del catálogo, error de guardado y recuperación de borradores. La consulta opcional de actualizaciones usa la red de producción sólo con `--allow-network`: no envía el proyecto, no prepara paquetes y no instala nada. Si no hay una versión oficial posterior, no acredita la preparación de una actualización futura. Las claves privadas de la prueba de firma se crean en un directorio temporal externo y se eliminan incluso si falla la prueba.

El workflow `R16 trilingual acceptance` ejecuta el caso principal, el recorrido API y Chromium, y conserva informes, recibos y capturas como artefactos de GitHub Actions. La inspección automatizada no sustituye la revisión visual de los documentos resultantes.

# Validación de report-gen 0.20.1

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Fecha de cierre: 5 de octubre de 2026. Pruebas realizadas entre el 4 y el 5 de octubre. Correcciones sobre la versión 0.20.0 entregada por el propietario. Esta revisión cubre los defectos de exportación observados durante la preparación de un informe extenso y sus regresiones. No constituye una auditoría de seguridad completa de la herramienta.

## Problemas corregidos

| Problema en 0.20.0 | Corrección | Comprobación |
| --- | --- | --- |
| Los hallazgos sin severidad desaparecían del resumen; los conteos podían diferir entre formatos. | Se conservan con la etiqueta «Pendiente de valoración» en español y su equivalente en inglés. Las máquinas se cuentan por separado. No se asigna CVSS ni se modifica el estado de verificación. | HTML, PDF, Word y Markdown; modelos clásico y por secciones; registros pendientes, puntuados, máquinas y caso vacío. |
| El gráfico de severidad podía mostrarse vacío mientras había hallazgos pendientes. | Se muestra únicamente cuando hay severidades asignadas; si conviven con pendientes, una nota aclara qué representa. | Aserciones del HTML y exportación del ejemplo incluido. |
| Los puntos del índice PDF podían quedar desalineados. | Se corrige el reparto del espacio y la alineación de título, puntos y página. | Inspección geométrica en WeasyPrint y revisión visual del índice. |
| Las columnas de tablas podían dividir identificadores o dejar poco espacio para texto largo; Word repartía anchos iguales. | PDF/HTML y Word comparten un cálculo de anchos por contenido, con espacio mínimo para palabras ordinarias y proporciones explícitas para tablas de seguimiento. | Tablas con identificadores, etiquetas, descripciones y valores largos; comparación de proporciones HTML/Word; revisión visual. |
| Los bloques Markdown heredaban el estilo de código en línea y podían partirse innecesariamente. | Estilo de bloque común para comandos y Markdown. Los bloques que caben permanecen juntos. Las etiquetas breves en negrita acompañan al bloque siguiente. | Bloques cortos, bloque PDF de 130 líneas sin pérdida de texto y etiquetas de evidencias al final de página. |
| El DOCX carecía de un índice equivalente al del PDF. | Índice nativo con entradas enlazadas, marcadores y campos de página actualizables. Los números dependen de la paginación del editor. | Estructura OOXML, campos equilibrados, destinos existentes, títulos con comillas y renderizado en LibreOffice. |

El texto del informe, sus comandos y sus datos siguen siendo la fuente de verdad. El exportador no completa severidades para evitar una tabla vacía. Se eliminó código duplicado del resumen y de los hallazgos en Word para aplicar el mismo comportamiento a ambos modelos de proyecto.

## Resultados

| Comprobación final | Resultado |
| --- | --- |
| Suite Python completa | 678 aprobadas; 0 fallos, 0 errores, 0 omitidas; 145,10 s. |
| Regresiones nuevas, incluidas en las 678 | 19 aprobadas. |
| Esas mismas regresiones sobre el código original 0.20.0 | 17 fallan y 2 pasan. Son 19 casos de prueba, no 19 defectos distintos. Algunas comprobaciones exigen las funciones incorporadas en esta versión. |
| Subconjunto de exportación y paginación, también incluido en la suite | 38 aprobadas. |
| JavaScript: guardado y borradores | 11 aprobadas. |
| DOM de la interfaz y endpoints reales de Flask mediante el puente de pruebas | 29 comprobaciones aprobadas. |
| Ruff | Sin errores con la configuración del proyecto. |
| Revisión de espacios del diff | Sin errores. |

Se registraron seis avisos en pytest: uno sobre HarfBuzz-Subset, cuatro sobre una API de Pillow obsoleta en pruebas existentes y uno del caso que crea deliberadamente un ZIP con una entrada duplicada. Ninguno produjo un fallo. Se incluyen el resultado JUnit y un resumen estructurado en `docs/validation-0.20.1/`.

### Revisión visual

Se exportó de nuevo el informe extenso que motivó la corrección sin modificar su fuente: 20 páginas en PDF de WeasyPrint y 21 páginas al renderizar el DOCX en LibreOffice. Se inspeccionaron todas las páginas, incluidas portada, índice, tablas, hallazgos, procedimientos y etiquetas con hashes. Esos documentos y sus evidencias privadas no forman parte de esta distribución.

El ejemplo ficticio `examples/pending-severity/engagement.yaml` se exportó a PDF, Word y HTML. Sus siete páginas PDF y sus siete páginas Word renderizadas se inspeccionaron completas. Comprueba dos hallazgos confirmados sin severidad, columnas con demandas diferentes, código Markdown, comandos y seguimiento de verificación. No requiere datos ni acceso a un servicio real.

### Entorno utilizado

Linux x86_64, Python 3.12.14 y Node.js 24.19.0. Versiones relevantes: pytest 9.1.1, Ruff 0.16.10, WeasyPrint 70.0, python-docx 1.2.0, Markdown 3.11, nh3 0.3.7, lxml 6.1.1, Pillow 12.3.0, pdfplumber 0.11.8, pypdf 6.10.0, Flask 3.1.3 y jsdom 26.1.0. El renderizador disponible del DOCX se identifica como LibreOfficeDev 26.8.0.0.alpha0.

Estas son las versiones realmente ejecutadas. No se afirma haber repetido esta validación con cada versión de `requirements-audited.txt`, con el instalador en una máquina Kali limpia, con Windows, con Microsoft Word de escritorio ni con el motor PDF opcional Chromium.

## Índice de Word

El DOCX contiene desde la exportación los títulos y enlaces internos del índice. Los campos `TOC`, `TC` y `PAGEREF` permiten que un editor calcule las páginas. Se solicita actualización de campos al abrir, pero cada editor decide cuándo ejecutarla.

La conversión automática de LibreOffice utilizada aquí conservó el índice enlazado sin calcular sus números de página. Para actualizarlos en Microsoft Word, seleccionar todo con **Ctrl+A**, pulsar **F9** y actualizar la tabla completa si aparece esa opción. Esta interacción en Microsoft Word no se ejecutó durante la revisión. El generador no utiliza los números del PDF ni valores de página ficticios como sustituto.

La cantidad de páginas puede cambiar según fuentes, editor y actualización del índice. Las tablas excepcionalmente grandes siguen sujetas a la comprobación de paginación existente. El cálculo de anchos es una ayuda de maquetación, no una garantía de que cualquier tabla pueda caber en una página.

## Reproducir las comprobaciones

Desde la carpeta del proyecto, con sus dependencias instaladas:

```bash
.venv/bin/python -m pip install -e '.[dev]'
npm ci
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
npm test
RG_PYTHON="$PWD/.venv/bin/python" npm run test:workspace
```

Solo las regresiones incorporadas:

```bash
.venv/bin/python -m pytest tests/test_release_0201.py
```

Exportar el ejemplo ficticio:

```bash
.venv/bin/python export.py examples/pending-severity/engagement.yaml -f pdf -o out/pending-severity.pdf
.venv/bin/python export.py examples/pending-severity/engagement.yaml -f docx -o out/pending-severity.docx
.venv/bin/python export.py examples/pending-severity/engagement.yaml -f html -o out/pending-severity.html
```

## Actualizar y conservar proyectos

No hay migración de esquema. Crear un respaldo integral desde la instalación anterior, descomprimir 0.20.1 en una carpeta nueva y restaurar el respaldo en esa instalación vacía. Conservar la carpeta anterior hasta comprobar los proyectos. No reutilizar una `.venv` de otra instalación.

El ZIP contiene código fuente, recursos de la herramienta, pruebas, documentación y ejemplos ficticios. No incorpora los proyectos privados usados durante la revisión, cookies, credenciales ni evidencias del informe que originó estas correcciones.

# Validación de report-gen 0.20.2

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Fecha de cierre: 5 de octubre de 2026 UTC. Revisión funcional del guardado y las exportaciones de 0.20.1, con correcciones reproducibles. No constituye una auditoría de seguridad completa ni una certificación de todos los entornos soportados.

## Cinco defectos corregidos

| Identificador | Defecto en 0.20.1 | Corrección y evidencia |
| --- | --- | --- |
| A01 | La descarga individual de HTML terminaba con `File is not a zip file`. La entrega conjunta sí generaba el HTML. | Inspector común por formato en `delivery.py` y `export_jobs.py`; descarga verificada desde los controles del editor simulado para ambos proyectos. |
| A02 | Una etiqueta antepuesta en la misma línea rompía tablas, listas o código al inicio de campos Markdown. | Separación en párrafos en `exporters/markdown.py`; cobertura de descripción, impacto, remediación, pasos y resúmenes. |
| A03 | Word desplazaba bloques de código al comienzo de listas complejas y perdía la sangría de las continuaciones. | Procesamiento por bloques, en orden, en `exporters/richtext.py`; pruebas de párrafos, sublistas, código y espacios entre estilos. |
| A04 | Los enlaces Markdown a `#F01` se convertían en enlaces externos de Word, sin marcador de destino. | Marcadores estables para hallazgos y secciones y enlaces internos OOXML; pruebas para proyectos por secciones y heredados. |
| A05 | La exportación HTML por CLI no aplicaba la validación final que sí aplicaban PDF, DOCX y Markdown. | Validación común antes de la copia pública en `export.py`; IDs duplicados rechazados y destino preexistente intacto. La cola del editor ya validaba. |

Las prioridades del documento de auditoría son prioridades de producto. No se asigna CVSS a estos problemas.

## Resultados

| Comprobación | Resultado |
| --- | --- |
| Suite Python final | 705 aprobadas; cero fallos, errores u omisiones; 151,729 s. |
| Pruebas nuevas, incluidas en las 705 | 27 aprobadas. |
| Mismas pruebas contra el código original 0.20.1 | 23 fallan y 4 pasan. Tres fallos corresponden a controles nuevos del inspector HTML, no a tres defectos adicionales. |
| JavaScript: guardado y borradores | 11 aprobadas. |
| DOM de la interfaz, suite existente | 29 controles aprobados. |
| Simulación de los dos proyectos | 26 controles aprobados. |
| Inspección independiente de los archivos finales | 168 controles aprobados. |
| HTML portátil: búsqueda, filtros y navegación | 12 controles DOM aprobados. |
| Ruff y espacios del diff | Sin errores. |

Los resultados JUnit y un resumen estructurado se encuentran en `docs/validation-0.20.2/`. Los recuentos representan casos o aserciones, no defectos distintos. Los avisos de las dependencias permanecen en el registro de pytest.

## Simulación y revisión de archivos

Se importó el proyecto redactado de Fondos Cultura, se abrió en el editor, se cambió un título mediante eventos DOM, se guardó, se recargó y se restauró el original. Se conservaron F01/F02, sus valoraciones pendientes, las referencias temporales y CWE-315. Esta revisión no contrastó los hashes de evidencia escritos en ese informe con sus originales privados.

Portal Aurora es un caso completamente ficticio. El proyecto y el primer hallazgo se crearon desde controles del editor. Los datos adicionales se incorporaron por la API para repetir exactamente el caso: cuatro hallazgos, una máquina, CVSS cero, valoración pendiente, tabla inicial, código, listas anidadas, imagen sintética y nota privada.

Los botones del editor solicitaron cada formato mediante la cola real de Flask. La entrega conjunta se pidió por la API. Los bytes descargados se abrieron e inspeccionaron. El guardado con una revisión antigua respondió 409 y una edición posterior al encolado no alteró la revisión exportada. Se comprobó la censura de una cadena sintética, la exclusión de una nota privada y la retirada de un comentario privado de PNG. Estos controles concretos no garantizan detectar cualquier secreto.

| Salida | Fondos Cultura | Portal Aurora |
| --- | --- | --- |
| PDF | 20 páginas; 40 enlaces internos comprobados. | 9 páginas; 25 enlaces internos comprobados. |
| DOCX | 21 páginas en el render; 10 enlaces del índice resueltos. | 9 páginas en el render; 5 enlaces del índice resueltos. |
| Markdown ZIP | Contenido y estructura conservados. | Tabla, código, listas e imagen comprobados. |
| HTML | Descarga individual y conjunta correctas. | Recursos incorporados y controles DOM correctos. |

Se revisaron visualmente las 29 páginas PDF y las 30 páginas de los DOCX renderizados. El cambio final de espacios en listas modificó una sola página del render de Fondos, que se volvió a revisar; las otras 29 eran idénticas píxel a píxel. Se comprobaron los SHA-256 y tamaños de los cuatro formatos en ambos manifiestos de entrega.

Las reexportaciones de Fondos son muestras de auditoría, no un nuevo envío a ANCI: conservan las referencias históricas de la fuente a versiones y anexos. Los originales privados de evidencia no se incluyen ni se reconstruyen. El paquete de la herramienta tampoco incluye ese proyecto. Las muestras y sus registros se distribuyen por separado.

## Entorno y límites

Linux x86_64; Python 3.12.14; Node 24.19.0; jsdom 26.1.0; pytest 9.1.1; Ruff 0.16.10; WeasyPrint 70.0; python-docx 1.2.0; pypdf 6.10.0; pdfplumber 0.11.8; lxml 6.1.1; Flask 3.1.3; Pillow 12.3.0; Markdown 3.11; nh3 0.3.7.

Chromium no pudo arrancar: el entorno rechazó la creación de un socket con `Operation not permitted`. Se utilizó jsdom con el puente de pruebas y las rutas reales de Flask. No se afirma haber realizado una prueba visual en navegador real, móvil o del motor PDF Chromium.

El DOCX se renderizó con el conversor LibreOffice disponible. No se ejecutó Microsoft Word de escritorio. El índice contiene títulos, enlaces y campos propios; sus números de página necesitan actualización en Word, normalmente con Ctrl+A y F9. El generador no copia los números del PDF. Se conservan fichas que empiezan cerca de un salto y continúan en la página siguiente; mejorar esa distribución queda como propuesta.

Algunas dependencias del entorno difieren de `requirements-audited.txt`. No se repitió una instalación limpia en Kali o Windows ni todas las combinaciones de dependencias. Una primera ejecución no encontró jsdom en la copia aislada; se configuró su ruta y la suite completa pasó. No se hicieron peticiones a Fondos Cultura.

## Repetir las pruebas

Con las dependencias del proyecto instaladas, desde su directorio:

```bash
.venv/bin/python -m pip install -e '.[dev]'
npm ci
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_release_0202.py
.venv/bin/python -m ruff check .
npm test
RG_PYTHON="$PWD/.venv/bin/python" npm run test:workspace
```

El paquete separado de auditoría contiene el caso Aurora editable, los scripts de simulación y las salidas verificadas. La simulación usa proyectos temporales mediante el puente de pruebas, no la carpeta de proyectos del usuario.

## Actualizar

No hay migración de esquema. Crear un respaldo integral desde la instalación anterior, descomprimir 0.20.2 en una carpeta nueva y restaurar allí el respaldo en una instalación vacía. Conservar la carpeta anterior hasta comprobar los proyectos. El manifiesto `MANIFEST-0.20.2.sha256` corresponde a este paquete; los registros de validación de versiones anteriores se conservan como historial.

# Validación de report-gen 0.21.1

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Fecha: 5 de octubre de 2026 UTC. Base: ZIP 0.21.0 con SHA-256 `36269addce287924a81a6d7de1dc3e1c6106a54614024436606e9595fbaaffa7`; manifiesto íntegro verificado antes de editar.

La versión incorpora comparación de contenido por hallazgo, conservación de código literal, gestión explícita de copias privadas y anexos obligatorios. La entrega está probada en Linux con Chromium. Firefox, Windows, Kali nativo y Microsoft Word conservan los límites descritos abajo.

## Correcciones comprobadas

| Problema | Corrección y prueba |
| --- | --- |
| El comparador anterior podía aceptar una pérdida de párrafo o un cambio de espacios en código | Contrato v2: párrafos completos, multiplicidad, orden y pertenencia al hallazgo. Código literal por bloque en HTML, Markdown y DOCX. Mutaciones deliberadas deben fallar. |
| Los comandos perdían espacios iniciales/finales y líneas vacías | Se eliminó `trim`/`strip` de su exportación. Solo se normaliza CRLF/CR a LF. |
| Markdown expandía tabulaciones en bloques de código | Los bloques se extraen antes de normalizar la prosa; se conserva el saneamiento frente a HTML activo y controles falsificados. |
| Un informe antiguo sin evaluador perdía el nombre genérico del equipo en Word y Markdown | Los exportadores usan el mismo valor alternativo que HTML/PDF. Regresión en los cuatro formatos. |
| El error de nombre de anexo persistía después de corregirlo | Aviso dentro del diálogo y borrado al editar/corregir. La operación rechazada no altera el proyecto. |
| Un anexo pequeño se mostraba como 0.0 KiB | Tamaños inferiores a 1 KiB expresados en bytes. Caso real de interfaz: 28 bytes. |
| La eliminación protegida de un borrador comparaba solo su fecha | Se compara el registro completo. Un cambio en el mismo milisegundo impide eliminar la copia nueva. |

## Funciones incorporadas

**Datos privados guardados** inventaría proyecto, imágenes, originales, anexos registrados/retirados, historial, respaldo YAML y otros archivos. Enumera borradores del navegador y permite descargar o eliminar uno concreto. El borrado del disco exige selección explícita, identificador del proyecto y versiones vigentes del proyecto e inventario. La limpieza es transaccional. Mantiene el estado actual y un nuevo punto de recuperación al retirar el historial. No borra originales ni copias externas.

**Anexos obligatorios** bloquean la entrega si el archivo falta, fue excluido o su hash no coincide. Aceptar avisos no evita el bloqueo. Los anexos siguen privados hasta revisión y selección. El análisis orientativo examina patrones en el primer MiB de texto UTF-8 y metadatos de imágenes, sin mostrar valores detectados. No hace OCR ni inspecciona contenido PDF; muestra la revisión incompleta. No modifica el archivo ni certifica ausencia de secretos.

Los proyectos anteriores son legibles. Los registros con el campo `required`, incluso falso, necesitan 0.21.1 o posterior; los lectores anteriores pueden rechazarlos.

## Resultado de las ejecuciones

Los registros originales se incluyen en `docs/validation-0.21.1/`.

- Suite Python final: **787 pruebas aprobadas**, registradas en `pytest-final.xml` y `pytest-final.log`. Incluye pruebas adversas, API real, importación/exportación y la integración DOM. Hay advertencias de entradas ZIP duplicadas creadas deliberadamente y de una API de Pillow usada en pruebas que quedará obsoleta; no son fallos de la suite.
- 48 comprobaciones del editor en Chromium: creación, importación del caso ficticio, guardado, cuatro descargas, paquete, anexos, búsqueda, teclado, tema y móvil.
- 24 comprobaciones adicionales en Chromium: dos pestañas, errores reales inyectados en escritura atómica, terminación abrupta, reinicio, privacidad y restauración.
- 12 pruebas JavaScript. Ruff y `pip check` sin errores. Entorno virtual nuevo con dependencias restringidas por `requirements-audited.txt`.
- Diagnóstico local de WeasyPrint, motor PDF alternativo Chromium y creación DOCX aprobado. No equivale a validación de Microsoft Word.
- 17 capturas originales del navegador, distribuidas aparte con fecha, viewport, URL local y SHA-256. Sin imágenes generadas ni retoques.

### Fallos y recuperación

El servidor de aceptación trabaja exclusivamente en carpetas temporales sintéticas y exige un marcador de prueba. Los endpoints de inyección solo se registran al ejecutar ese servidor de pruebas; no forman parte del servidor normal.

Se inyectaron `ENOSPC` y `EACCES` durante el reemplazo atómico del YAML. El disco mantuvo la revisión anterior, la interfaz anunció el error, IndexedDB conservó el borrador y el reintento guardó los cambios. Se terminó el proceso con `os._exit(92)` entre los dos renombres de la transacción. Al reiniciar en el mismo host y puerto, el disco recuperó su última revisión completa y se recuperó explícitamente el borrador. Un respaldo posterior se descargó y restauró en otra instalación vacía.

Dos pestañas reales partieron de la misma revisión. Un conflicto 409 mantuvo los cambios de la segunda pestaña. La elección explícita conservó la edición guardada y combinó una remediación independiente. No se ensayó pérdida eléctrica, fallo físico del disco ni concurrencia de varios procesos del servidor.

### Informes completos

| Caso | Entradas | PDF | DOCX, Markdown y HTML | Paquete |
| --- | ---: | ---: | --- | --- |
| Aurora ficticio | 4 hallazgos y 1 máquina | 9 páginas | Comprobados | 4 hashes verificados |
| Nimbus ficticio | 12 hallazgos | 38 páginas | Comprobados | 4 hashes verificados |
| Fondos Cultura redactado | 2 hallazgos | 20 páginas | Comprobados | 4 hashes verificados |

El informe histórico se recreó desde su respaldo redactado, fuera del paquete de código. No hubo nuevas solicitudes a Fondos Cultura ni cambios de conclusiones. El caso ficticio contiene tablas, listas anidadas, código, imagen con metadatos, nota privada y secreto sintético censurado. Los controles verificaron que los dos marcadores privados no alcanzan los artefactos publicados.

### Carga acotada

| Entradas | Formato | Tiempo observado | Resultado |
| ---: | --- | ---: | --- |
| 100 | PDF | 14,794 s | 49 páginas |
| 100 | HTML | 0,745 s | Comprobado |
| 100 | Markdown | 0,745 s | Comprobado |
| 100 | DOCX | 1,892 s | Comprobado |
| 1.000 | HTML | 6,810 s | 2.001 párrafos, 1.000 bloques literales |
| 1.000 | Markdown | 6,666 s | 2.001 párrafos, 1.000 bloques literales |
| 1.000 | DOCX | 47,453 s | 2.001 párrafos, 1.000 bloques literales |

Tiempos de una ejecución, no garantía de rendimiento. No se generó PDF de 1.000 hallazgos. El editor recorrió un tablero y una búsqueda de 500 hallazgos. Las mediciones exactas figuran en `browser-results.json`.

## Alcance de las comprobaciones

HTML, Markdown y Word comparan los párrafos definidos por la copia pública, conservan las repeticiones y rechazan traslados entre hallazgos. El código compara tabulaciones, espacios, comillas, Unicode y líneas vacías. Los finales de línea son la única normalización del código. Tablas y listas mantienen sus comprobaciones por hallazgo. El contrato no certifica todo el contenido arbitrario de una plantilla ni equivalencia visual entre motores.

Markdown no genera el gráfico de severidad ni su leyenda de alcance; la omisión específica se registra. El resto del resumen se compara.

PDF comprueba presencia textual. La extracción puede introducir espacios dentro de palabras/URLs y ordenar bloques de forma distinta a la página visible. Los espacios presentes en la fuente siguen siendo obligatorios. Para un párrafo dividido por paginación se admiten fragmentos contiguos de texto en páginas consecutivas, sin omitir palabras ni saltar páginas. No se acredita literalidad de espacios, asociación de bloques ni ausencia de superposición: la ficha indica revisión manual requerida.

Se revisaron mosaicos de Aurora y Fondos Cultura y páginas completas de ambos PDF. El control geométrico de 116 páginas no encontró bloques de texto fuera del papel; no prueba ausencia de superposición dentro de la página. El DOCX de Aurora se renderizó con LibreOffice en 8 páginas y se revisaron todas. El índice conserva enlaces y campos, pero el cálculo de números requiere actualizar campos en el editor. No se copian los números del PDF al DOCX.

## Compatibilidad pendiente

| Entorno | Estado |
| --- | --- |
| Linux, Python 3.12, Chromium 141.0.7390.37 | Ejecutado: 72 comprobaciones de navegador |
| Firefox 153 | Bloqueado antes de crear página: `Sandbox: writing /proc/self/uid_map: EPERM`. Cero comprobaciones de aplicación. |
| Microsoft Word de escritorio | No disponible. `scripts/verify-microsoft-word.ps1` preparado, sin ejecución nativa. |
| Windows | Matriz de CI ampliada, sin ejecución en esta sesión. |
| Kali instalado o VM | No disponible. La ejecución en Linux no sustituye una prueba de instalación específica en Kali. |
| GitHub Actions | Workflows preparados, no ejecutados remotamente. |

El bloqueo de Firefox se registró sin desactivar sus protecciones. Chromium sí abrió páginas, realizó clics y descargó archivos reales.

## Repetir las pruebas

```bash
python3 start.py --setup
.venv/bin/python -m pip install -e '.[dev,previews]' -c requirements-audited.txt
npm ci --ignore-scripts
.venv/bin/python -m pytest --junitxml=out/pytest.xml
npm test
npx playwright install chromium firefox
RG_PYTHON=.venv/bin/python node scripts/audit-browser-0210.cjs --browser chromium --output out/browser
RG_PYTHON=.venv/bin/python node scripts/audit-browser-0211.cjs --browser chromium --output out/recovery
.venv/bin/python scripts/audit-exports-0210.py --output out/corpus --stress
```

Usar carpetas de salida vacías. El corpus histórico opcional se proporciona con `--project` y debe ser una copia ya redactada. Los proyectos de los recorridos de recuperación son temporales y ficticios. Para Windows, los workflows usan `RG_PYTHON=python`.

La actualización recomendada es respaldar desde la versión anterior, extraer 0.21.1 en una carpeta nueva, restaurar en una instalación vacía y comprobar los proyectos. Conservar la instalación anterior hasta terminar la revisión.

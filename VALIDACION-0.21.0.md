# Validación de report-gen 0.21.0

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Fecha: 5 de octubre de 2026 (UTC; 4 de octubre en Santiago durante la auditoría). Base: ZIP 0.20.2 con SHA-256 `5e60fe2efed31b62bf720214999348948ed74eef20b2af794260465337311dfe`.

La versión incorpora las ocho propuestas de la auditoría anterior. La ejecución real en Chromium, la instalación limpia, la suite y los tres informes aprobaron los controles descritos aquí. Firefox no pudo completar el arranque de una página por restricciones del entorno; Microsoft Word de escritorio no está disponible. Sus flujos de validación quedan implementados y pendientes de ejecución. No se certifica ausencia absoluta de errores.

## Cambios y defectos corregidos

1. **Severidad sin valorar en la interfaz.** Un dato ausente seleccionaba visualmente la primera opción, Crítica; Inicio lo presentaba como Informativa. Ahora se muestra Pendiente de valoración, existe una opción explícita y un filtro propio. Crear un hallazgo ya no asigna Media automáticamente. CVSS y verificación técnica permanecen independientes.
2. **Búsqueda incompleta.** Los pasos de máquina consultaban `text` y `code`, pero los datos usan `text_md` y `command`; tampoco se recorría `walkthrough`. Se buscan los campos reales y se comprobó el acceso al resultado mediante teclado.
3. **Borrador sin identificador.** Inicio usaba una variable de índice no definida en su texto alternativo. El índice local está definido; no se inventa ni persiste un identificador para disimular el borrador.
4. **Instalación.** El pip incluido por `venv` era 25.0.1 y la auditoría detectó avisos sobre ese instalador. `start.py --setup` actualiza pip a la serie 26 desde 26.2 antes de instalar dependencias. La comprobación final con pip 26.2.1 no detectó avisos conocidos. Esto es endurecimiento del proceso de instalación, no una explotación demostrada del editor.
5. **Incidencias detectadas durante el desarrollo de 0.21.0.** Se corrigieron un estado vacío ausente en el HTML, el rechazo de anexos en la comparación visual de versiones y una declaración de anexo inválida que podía dejar cambios pendientes. Las entradas se validan antes de guardar. Estos eran defectos del desarrollo nuevo, no fallos atribuidos a 0.20.2.

## Las ocho propuestas

| Propuesta | Implementación | Validación y límite |
| --- | --- | --- |
| Navegador real y CI | Prueba del editor en Chromium y Firefox, con servidor efímero y capturas | Chromium ejecutado. Firefox local bloqueado; matriz CI preparada, no ejecutada remotamente |
| Consistencia entre formatos | Contrato de contenido de la copia pública y comprobación del archivo final | Títulos y líneas de código; tablas y orden de listas en formatos estructurados. No equivalencia visual universal |
| Word nativo | Script PowerShell sobre copias y workflow manual con Word instalado | OOXML y render LibreOffice comprobados; Word nativo pendiente |
| Filtros HTML | Tipo, severidad pendiente, restablecer, sin resultados y navegación a destinos | Comprobados en HTML real sin recursos externos |
| Comprobaciones visibles | Revisión, tamaño, SHA-256, resultados y descarga JSON por trabajo | Descargas individuales y paquete; autorización por sesión conservada |
| Paginación y densidad | Espaciado cómodo/compacto y unión del inicio del hallazgo a su contenido | PDF y DOCX revisados; paginación propia de cada motor |
| Inventario de anexos | Declaración, carga, revisión, selección y hashes en ZIP | Predeterminado privado; seleccionados ausentes o alterados bloquean; respaldos e historial preservados |
| Registro único de exportadores | `export_formats.py` define extensiones, MIME, nombre, escritor e inspector | CLI, API, cola y controles de selección utilizan el registro |

## Ejecuciones verificadas

- **Python:** suite completa de 738 casos, sin fallos ni omitidos, más un caso adicional del instalador aprobado después de ese recorrido. Total: 739 casos diferentes. Los 34 casos nuevos también se ejecutaron como grupo durante el desarrollo. No se suman las repeticiones al total.
- **JavaScript:** 11 pruebas de guardado y borradores; 29 comprobaciones adicionales del DOM con rutas reales de Flask.
- **Chromium:** 49 comprobaciones con clics, formularios y descargas reales. Creación, importación, persistencia tras recargar, recuperación de fallo 503, clasificación pendiente, anexos, las cuatro descargas, ZIP, comprobaciones visibles, HTML sin ejecución del contenido de prueba, teclado, tema claro y viewport móvil.
- **Interfaz bajo carga:** 500 hallazgos, incluyendo búsqueda de un comando del último. Las medidas de tiempo están en `browser-results.json`; son observaciones de este entorno, no un SLA.
- **Instalación limpia:** entorno virtual independiente, dependencias fijadas de `requirements-audited.txt`, `pip check` sin inconsistencias y diagnóstico del lanzador correcto.
- **Dependencias:** npm audit sin avisos conocidos; pip-audit sin avisos conocidos tras actualizar el instalador. El código local report-gen no se audita por PyPI y se revisa por separado. Los resultados dependen de las bases consultadas y su fecha.
- **Revisión visual:** PDF de los tres casos; render con LibreOffice del ficticio y del histórico redactado. Se combinaron mosaicos, páginas a tamaño completo y revisión automatizada de límites. Se comprobaron 116 páginas PDF, sin cajas de texto fuera del papel. Esto no detecta por sí solo toda superposición o problema visual.

## Informes recreados

| Caso | Entradas | PDF | Word y demás formatos |
| --- | ---: | ---: | --- |
| Fondos Cultura redactado | 2 hallazgos | 20 páginas | DOCX, Markdown y HTML generados y verificados; render DOCX en LibreOffice: 21 páginas |
| Aurora ficticio complejo | 4 hallazgos y 1 máquina | 9 páginas | Código, listas, tablas, imagen, secreto sintético censurado y nota privada excluida; render DOCX: 8 páginas |
| Nimbus | 12 hallazgos | 38 páginas | 19 recursos de imagen publicados conservados; los cuatro formatos verificados |

Las tres entregas conjuntas se generaron desde copias fijas. Se verificaron todos sus archivos contra los SHA-256 del manifiesto. Fondos se importó desde el respaldo redactado existente; no se realizaron nuevas solicitudes al servicio ni se alteraron sus conclusiones técnicas.

## Carga y entradas adversas

El corpus adicional exportó 100 hallazgos a PDF, HTML, Markdown y Word. El PDF ocupa 49 páginas. Exportó 1.000 hallazgos a HTML, Markdown y Word: aproximadamente 5,9 s, 6,1 s y 40,6 s, respectivamente, en la ejecución registrada. No se ensayó PDF de 1.000 hallazgos. Los controles contrastaron 2.000 unidades de texto y 4.000 unidades estructurales por formato estructurado en ese caso.

Las regresiones cubren, entre otros límites: rutas y enlaces simbólicos, ZIP alterados, duplicación y expansión de entradas, JSON/YAML no válidos o demasiado profundos, recursos externos, HTML de prueba, secretos sintéticos, borradores y conflictos, cancelación y limpieza. Los anexos añaden rechazo de nombres reservados, controles Unicode y colisiones de normalización, límites de 16 MiB por archivo y 64 MiB activos, hash de contenido y revisión explícita. Los comandos se conservan como datos; el caso con sustituciones de shell no creó su archivo marcador.

## Qué incluye y qué excluye la entrega

El ZIP de uso contiene fuentes, pruebas, automatizaciones, ejemplos ficticios y documentación. No incluye proyectos de trabajo, el respaldo de Fondos, cookies, entornos virtuales ni node_modules. Las capturas se entregan aparte con su inventario y SHA-256. Son PNG del viewport real de Chromium; no son maquetas ni imágenes generadas.

Un anexo se adjunta únicamente después de seleccionarlo. Se copia sin censura y sin limpieza de metadatos; hay que cargar una copia ya revisada. Los originales privados, borradores y archivos retirados del inventario pueden permanecer en respaldos e historial. Estos respaldos no son el paquete para el cliente.

## Límites pendientes

- **Firefox 153 / Playwright build 1538:** `Sandbox: writing /proc/self/uid_map: EPERM`, terminación de procesos de contenido y falta de página utilizable. No se rebajó el aislamiento para forzar un aprobado. El registro del entorno se conserva.
- **Microsoft Word y Windows:** se prepararon workflows; no se ejecutaron aquí. El índice DOCX tiene destinos y campos nativos, pero sus números requieren actualizar campos en Word. LibreOfficeDev 26.8.0.0.alpha0 es un control adicional, no prueba de Microsoft Word.
- **CI remota:** los archivos están listos para ejecutarse al incorporarlos al repositorio; no se afirma que GitHub Actions haya pasado.
- **Alcance técnico:** los controles de formato no confirman vulnerabilidades, valoraciones CVSS ni ausencia total de secretos. No hay promesa de identidad de píxeles entre motores.

## Repetir las pruebas

```bash
python3 start.py --setup
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci --ignore-scripts
.venv/bin/python -m pytest
npm test
npx playwright install chromium firefox
RG_PYTHON="$PWD/.venv/bin/python" node scripts/audit-browser-0210.cjs --browser chromium --output out/browser-chromium
RG_PYTHON="$PWD/.venv/bin/python" node scripts/audit-browser-0210.cjs --browser firefox --output out/browser-firefox
.venv/bin/python scripts/audit-exports-0210.py --output out/export-audit --stress
```

Cada ejecución usa un directorio de salida nuevo. La opción `--project` permite agregar un respaldo redactado propio. `RG_CHROMIUM_EXECUTABLE` permite seleccionar explícitamente un Chromium instalado; esta auditoría utilizó Chromium 141.0.7390.37 y Playwright Node 1.62.1. El ejecutable predeterminado de esa versión de Playwright no estaba instalado. Las versiones Python y los registros están en `docs/validation-0.21.0/`.

## Actualizar

Crear respaldo integral, descomprimir 0.21.0 en una carpeta nueva y restaurar en una instalación vacía. Conservar la instalación anterior hasta comprobar los proyectos. No copiar la `.venv` anterior. Los respaldos con anexos requieren 0.21.0 o posterior.

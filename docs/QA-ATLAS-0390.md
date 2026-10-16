# Protocolo de aceptación Atlas — report-gen 0.39.0

Estado de este documento: **protocolo preparado; aceptación integral pendiente**.
Los comandos describen cómo obtener evidencia. Su presencia, el número de
combinaciones previsto o una prueba aislada aprobada no acreditan la generación
completa. El cierre debe registrar commit, hashes, motores, resultados y páginas
observados en la ejecución final.

La prioridad es generar un caso extenso con report-gen, inspeccionar sus salidas
y corregir cualquier error reproducido antes de repetir los controles afectados.
Las mejoras de navegación se comprueban sobre ese mismo trabajo.

## Caso e idiomas

**Atlas Servicios Financieros 1.0** es ficticio. Sus datos e imágenes son entradas
de prueba y no describen una evaluación realizada a una organización real.

| Recurso de entrada | Cantidad prevista por idioma |
| --- | ---: |
| Hallazgos de vulnerabilidad | 60 |
| Cuadernos de máquinas | 7 |
| Activos | 28 |
| Evidencias | 84 |
| Secciones | 23 |
| Registros de cobertura | 180 |
| Retests | 31 |

Son 67 entradas de hallazgos y máquinas; no son 67 vulnerabilidades. Los idiomas
son español (`es`), inglés (`en`) y portugués de Brasil (`pt`). Cada uno tiene
contenido redactado propio en `scripts/atlas-case-content/`. Cambiar únicamente
`meta.lang` no satisface este protocolo: deben conservarse las identidades,
relaciones, cifras y significado del caso al localizar la prosa.

`build-atlas-case.py` prepara YAML, PNG sintéticos y entradas inertes para anexos
e importadores. No genera los informes. La creación de PDF, DOCX, Markdown y
HTML utiliza exclusivamente las funciones de exportación y entrega de
report-gen; no se retocan externamente sus resultados para aprobar la prueba.

## Preparación y conservación

Ejecuta desde la raíz de una instalación de desarrollo de report-gen, con su
entorno Python activado. Para el recorrido completo se necesitan las dependencias
de desarrollo, Node.js y las dependencias npm del proyecto, Chromium de
Playwright, LibreOffice estable, las fuentes multilingües y las dependencias de
OCR que usa el flujo de evidencias. La configuración concreta y los paquetes de
CI están en el trabajo `atlas` de
[`r16-acceptance.yml`](../.github/workflows/r16-acceptance.yml).

Elige una carpeta nueva **fuera de la instalación y de los proyectos reales**:

```bash
export ATLAS_OUTPUT=/ruta/fuera/de/report-gen/atlas-0390-r01
export RG_PYTHON=python
export REPORT_GEN_LIBREOFFICE=/usr/bin/libreoffice
export REPORT_GEN_REQUIRE_MULTISCRIPT_FONTS=1
mkdir -p "$ATLAS_OUTPUT/runtime"
git rev-parse HEAD > "$ATLAS_OUTPUT/runtime/checkout.txt"
git status --short > "$ATLAS_OUTPUT/runtime/working-tree.txt"
libreoffice --version > "$ATLAS_OUTPUT/runtime/libreoffice-version.txt"
python -m pip freeze > "$ATLAS_OUTPUT/runtime/python-packages.txt"
```

Ajusta la ruta de LibreOffice a tu instalación. Para una aceptación final, usa
un checkout limpio y conserva también las versiones de fuentes, sistema y
navegador. No cambies el productor durante las exportaciones. Los runners
registran hashes y rechazan cambios observados en el código o las entradas.

Si una ejecución falla, conserva sus recibos y archivos. Corrige la causa y usa
otra carpeta para repetir; no sobreescribas el resultado anterior ni presentes
su estado fallido como aprobado. Los proyectos mutables del recorrido API se
crean aislados de los originales.

## 1. Localización y construcción de las entradas

```bash
python scripts/audit-atlas-localization.py \
  --output "$ATLAS_OUTPUT/localization.json"
python scripts/build-atlas-case.py \
  --output "$ATLAS_OUTPUT/case"
```

El builder crea `case/projects/es`, `case/projects/en`, `case/projects/pt`, las
entradas de importación en `case/inputs` y un manifiesto. Su destino no debe
existir previamente. La validación comprueba esquema, referencias, anexos y
preflight. Clasifica las advertencias por su causa: un control negativo
deliberado se documenta y no se convierte automáticamente en un error del motor.

La auditoría de localización compara estructura, identidades, cobertura de
campos y marcadores previstos. Es una comprobación determinista del catálogo;
no sustituye la revisión lingüística del contenido ni detecta universalmente
cualquier mezcla de idiomas.

## 2. Informes completos y muestras de presentación

Primero genera los cuatro formatos principales para cada idioma y comprueba
la composición nativa del DOCX con LibreOffice estable:

```bash
python scripts/audit-atlas-exports.py \
  --projects "$ATLAS_OUTPUT/case/projects" \
  --output "$ATLAS_OUTPUT/exports" \
  --mode principal \
  --native-executable "$REPORT_GEN_LIBREOFFICE" \
  --require-stable
```

Después ejercita los estilos generales y los perfiles del catálogo mediante
muestras del mismo caso:

```bash
python scripts/audit-atlas-exports.py \
  --projects "$ATLAS_OUTPUT/case/projects" \
  --output "$ATLAS_OUTPUT/exports" \
  --mode styles
```

Ambos modos pueden escribir en el mismo directorio porque conservan recibos
distintos: `matrix-principal.json` y `matrix-styles.json`. No repitas el mismo
modo sobre un recibo existente. Alternativamente, `--mode all` ejecuta ambas
partes en una carpeta nueva; no mezcles matrices duplicadas de `all` y de los
modos separados para sumar resultados.

La matriz se deriva del catálogo disponible al ejecutar. Distingue
`complete_case` de `targeted_excerpt`: las muestras de estilos no son informes
completos. Incluye cada idioma, estilo general y perfil, con controles de ambas
variantes por composición; no prueba todas las combinaciones posibles de
perfil, variante, contenido y formato. Una salida solicitada o parcialmente
generada no cuenta como verificada. Los recuentos finales se toman de
`exported_formats`, `complete_case_formats` y `excerpt_formats`, junto con el
estado de cada trabajo y su cobertura.

Las salidas principales quedan en
`exports/principal/<idioma>/outputs/`, incluyendo `informe.pdf`. La composición
nativa tiene sus propios recibos; no se suma otra vez como un formato completo
adicional. LibreOffice no acredita aceptación de Microsoft Word. Las páginas
se registran después de generar e inspeccionar cada archivo, sin fijar aquí
un total anticipado.

## 3. Inspección de las publicaciones

```bash
python scripts/audit-atlas-publication.py \
  --exports "$ATLAS_OUTPUT/exports" \
  --case "$ATLAS_OUTPUT/case/projects" \
  --output "$ATLAS_OUTPUT/publication-scan.json"
```

La inspección exige matrices completas, productores coherentes, cobertura del
plan y originales inalterados. Comprueba los marcadores sintéticos definidos
para el caso en los archivos inspeccionados. No garantiza ausencia universal
de información privada. La inspección estructural de anexos PDF del producto
es acotada, no hace OCR y no sustituye su revisión y autorización manual.

## 4. Recorrido API completo en cada idioma

Cada recorrido usa los handlers reales de Flask en un espacio de trabajo
aislado. No equivale a un recorrido HTTP ni a una prueba de navegador. Lee un
PDF ya generado por report-gen y conserva la fuente original.

```bash
for language in es en pt; do
  python scripts/audit-atlas-api.py \
    --case "$ATLAS_OUTPUT/case/projects/$language" \
    --inputs "$ATLAS_OUTPUT/case/inputs" \
    --pdf "$ATLAS_OUTPUT/exports/principal/$language/outputs/informe.pdf" \
    --output "$ATLAS_OUTPUT/api/$language" \
    --ui-bundle "$ATLAS_OUTPUT/ui/atlas-$language.zip" \
    --require-stable-native || exit 1
done
```

El idioma se toma del proyecto; no hay un argumento `--lang` para este runner.
El recorrido cubre catálogos, puntuación, revisión e historial, destinatarios,
vista DOCX, anexos PDF, importaciones y diagnósticos, evidencias y captura,
bibliotecas, decisiones y remediación, comparación y los demás ciclos
enumerados en `results.json`. Comprueba fase por fase antes de declarar
completo un idioma. La publicación de un paquete de UI no acredita por sí
sola que el navegador se haya ejecutado.

## 5. Navegador real y capturas

Con los tres paquetes editables y las muestras generadas, ejecuta Chromium
visible. En CI Linux sin pantalla física, `xvfb-run` proporciona la pantalla
virtual; no sustituye la comprobación de que el visor pinte las páginas.

```bash
xvfb-run -a node scripts/audit-atlas-browser.cjs --headed \
  --bundles "$ATLAS_OUTPUT/ui" \
  --projects "$ATLAS_OUTPUT/case/projects" \
  --pdf "$ATLAS_OUTPUT/exports/principal/es/outputs/informe.pdf" \
  --compare-pdf "$ATLAS_OUTPUT/exports/samples/general/es/serio/outputs/informe.pdf" \
  --compare-other-pdf "$ATLAS_OUTPUT/exports/samples/general/en/serio/outputs/informe.pdf" \
  --output "$ATLAS_OUTPUT/browser"
```

El recorrido debe documentar escritorio y móvil, temas claro y oscuro, los
tres idiomas, teclado, cinco grupos de navegación, índices y paginación,
tutorial, diagnósticos, visor DOCX y anexos PDF. Abrir un control plegado exige
activar su `summary` visible; no se usan clics forzados para saltar la interfaz.
La comparación utiliza PDF de muestras compatibles con los límites del
comparador. El rechazo esperado de un PDF que supera un límite de comparación
no se presenta como fallo de generación del informe.

Conserva `browser/results.json`, capturas originales, descargas y sus hashes.
Una URL `blob:` o un visor abierto no prueban que una página esté pintada. Las
capturas y aserciones del navegador tampoco sustituyen la revisión visual de
los documentos completos. Registra por separado qué páginas se revisaron,
con qué motor y si se usaron hojas de contacto o ampliaciones.

## Criterios de cierre y estado

| Control | Evidencia requerida | Estado en este protocolo |
| --- | --- | --- |
| Fuente trilingüe | Catálogos, auditoría de localización y manifiesto del builder | Pendiente de cierre |
| Informes principales | Matriz, inspecciones por formato y hashes originales | Pendiente de cierre |
| Muestras de catálogo | Matriz y cobertura sin combinaciones pendientes | Pendiente de cierre |
| Inspección de publicación | Recibo con alcance y marcadores efectivamente inspeccionados | Pendiente de cierre |
| API ES/EN/PT | Tres resultados completos, fases y controles negativos clasificados | Pendiente de cierre |
| Navegador | Recibo, errores revisados, capturas y descargas reales | Pendiente de cierre |
| Composición y lectura | Revisión visual documentada y páginas observadas | Pendiente de cierre |
| CI y publicación | Controles del commit exacto y artefactos verificados | Pendiente de cierre |

Añade los resultados finales sin borrar los intentos fallidos. No sumes suites
solapadas, muestras como informes completos ni vistas derivadas como formatos
originales. Los límites que permanezcan deben conservarse en el informe final.
Este protocolo no afirma ausencia universal de errores, código muerto,
filtraciones o equivalencia entre motores de documentos.

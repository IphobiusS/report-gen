# report-gen 0.20.0: cambios y validación

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Base de comparación: 0.18.0. Revisión: 4 de octubre de 2026. Se documentan ejecuciones reales, sin afirmar ausencia total de errores ni validez técnica de los hallazgos escritos por el autor.

## Qué cambia

- Cuatro tareas principales: **Trabajar, Revisar, Entregar y Biblioteca**. Preferencias agrupadas, cabecera móvil compacta, identidad de Prometeo y Evaristo conservada.
- Borradores de proyecto en IndexedDB con confirmación después de completar la escritura, retención de 30 días y descarga de emergencia. Recuperación validada y comparación explícita de conflictos entre revisiones.
- Una copia de publicación común para PDF, Word, Markdown y HTML: recursos del informe habilitado, imágenes sin metadatos y originales conservados dentro del proyecto.
- Inspector del texto y las imágenes que saldrán: huellas del original y la derivada, patrones orientativos de secretos, excepciones justificadas y censura literal explícita.
- Informe HTML autónomo con búsqueda, filtro por severidad, vista ejecutiva e impresión. Funciona sin conexión; sin JavaScript muestra el documento completo y oculta los controles que requieren scripts.
- Revisión con explicaciones, estados coherentes al duplicar e interpretación temporal del último retest.
- Lanzador con instalación y diagnóstico, README ES/EN, recorrido inicial sobre la demo y documentación de seguridad y contribuciones.

## Correcciones de la auditoría

| ID | Problema | Corrección y evidencia |
| --- | --- | --- |
| A01 | Comparación descargable incluía capturas privadas | Proyección pública por defecto; comparación interna identificada y confirmación explícita al descargar. La compartible omite imágenes históricas y aplica las censuras actuales también al texto anterior. |
| A02 | Borrador pendiente desaparecía al cerrar | Persistencia por pestaña/proyecto, aviso tras confirmar IndexedDB, copia de emergencia y resolución de conflictos con la revisión actual. |
| A03 | Captura vinculada a un hallazgo eliminado | Se detecta el vínculo roto y se permite reincorporar, conservando la procedencia histórica. |
| A04 | Fila CSV inválida impedía importar otra válida | Duplicados calculados sobre candidatos válidos y filas seleccionadas; las coincidencias existentes no se sobrescriben. |
| A05 | SHA-256 correspondía al texto normalizado | Se calcula sobre los bytes recibidos antes de decodificar. La huella de normalización queda separada. Las importaciones antiguas mantienen la atribución correcta. |
| A06 | Imágenes conservaban metadatos ocultos | Derivada de publicación para todos los formatos. JPEG elimina segmentos APP/COM y bytes posteriores sin recomprimir cuando no necesita corregir orientación. PNG/WebP/GIF se reconstruyen. |
| A07 | Markdown sin etiqueta accesible | Etiqueta explícita del textarea y barra de herramientas fuera del label. |
| A08 | Entrega inglesa acompañada de instrucciones españolas | README de entrega y avisos de revisión en el idioma del documento. |
| A09 | Duplicación y retest atribuían estados incoherentes | Nuevas instancias sin verificar; regla temporal del último retest y aviso de contradicción. |
| A10 | Cabecera móvil de 412 px | Preferencias y acciones secundarias agrupadas; cabecera de trabajo de unos 135 px a 390 px de ancho. |

También se corrigen la exportación desde un YAML con nombre distinto de `engagement.yaml`, las credenciales JSON en el detector y los desbordes de controles y referencias largas del HTML a 360 px.

## Evidencia de esta distribución

Resultados: **659 pruebas Python**, **11 de JavaScript**, **29 del DOM**, **58 comprobaciones del editor en Chromium**, **8 de recuperación**, **12 del HTML portátil** y **22 de conservación de Nimbus**, todas aprobadas. Las comparaciones de archivo y el lint también pasan.

Con vista previa e imágenes activas, la carga y apertura del tablero fue de **2,352 s para 100 hallazgos** y **10,123 s para 500** en este entorno. Son medidas de referencia, no promesas para otros equipos.

Los recuentos finales y tiempos se incluyen en `docs/verification-0.20.0/resultados.json`. Los registros completos y las capturas están en el paquete separado `report-gen-0.20.0-capturas-y-validacion.zip`. Las baterías se informan por separado: pueden comprobar varias veces el mismo flujo y no representan defectos distintos.

Entorno: Linux, Python 3.12, Chromium 141, WeasyPrint 70. Word se renderizó con LibreOfficeDev 26.8.0.0.alpha0; no con Microsoft Word.

Nimbus conserva 12 hallazgos, 19 imágenes publicadas y 673 fragmentos comparados en los dos motores PDF, Word, Markdown y HTML. WeasyPrint produce 38 páginas y Chromium 39. El renderizado de Word tiene 42 páginas, idénticas píxel a píxel a la base en el mismo entorno de LibreOffice. Los originales del proyecto no se modifican al exportar.

Once casos de regresión del backend se ejecutaron contra la 0.18 sin modificar y fallaron allí; pasaron con los cambios. Esos once casos no equivalen a once defectos diferentes. El detalle se conserva en el registro de comparación.

## Diseños e idiomas conservados

Comparación SHA-256 frente a la base: catálogos, plantillas, traducciones, temas, logos de proveedores, 300 recursos de la galería, ambas imágenes de marca y demo Nimbus intactos. Continúan los 22 perfiles, seis diseños generales y 50 apariencias por idioma. Se mantienen Calibri en Word, Carlito en PDF/HTML y fuente monoespaciada para los comandos. No se regeneró toda la biblioteca de muestras en esta versión: se verificó su conservación y se probó el flujo bilingüe y la creación de plantillas personales.

## Límites y comprobaciones pendientes

- Windows y Microsoft Word de escritorio no se ejecutaron aquí. La automatización de Windows se actualiza, pero no se presenta como ejecutada.
- No se realizó una sesión con lector de pantalla ni pruebas de uso con tres personas nuevas. Los objetivos de instalación y primera entrega en diez minutos siguen siendo criterios de una futura prueba con usuarios.
- Los borradores pertenecen al perfil y origen del navegador. No incluyen archivos de imagen ni formularios auxiliares aún sin incorporar. No están cifrados por la aplicación; borrar datos del navegador, cambiar de perfil/puerto o usar modo privado puede eliminarlos.
- El detector de patrones no encuentra todos los secretos. Una excepción registra una decisión, pero no cambia el texto. Revisa también las imágenes antes de publicar.
- El HTML siempre contiene el informe completo. Sus filtros y vista ejecutiva son presentación, no permisos de acceso.
- La comparación compartible contiene texto histórico; requiere revisión antes de enviarla. Las imágenes antiguas se omiten para no recuperar una versión anterior a su censura.
- Las explicaciones de revisión no demuestran que el hallazgo esté confirmado ni que el pentest sea completo. La confirmación general de avisos de entrega no constituye una excepción justificada individual para cada regla.
- Plantillas, interfaz nueva e instrucciones de la entrega inglesa están disponibles en inglés. Algunos errores heredados del backend siguen en español.
- El editor mantiene su alcance local y de un solo proceso. No debe exponerse como servicio multiusuario.

## Reproducir

```bash
python3 start.py --setup
.venv/bin/python -m pip install -e '.[dev,previews]' -c requirements-audited.txt
.venv/bin/python -m playwright install chromium
npm ci --ignore-scripts
.venv/bin/python -m pytest
npm test
node tests/test_workspace_dom.cjs
.venv/bin/python scripts/audit-studio-0200.py --output qa/studio
.venv/bin/python scripts/audit-recovery-0200.py --output qa/recovery
```

Para revisar el HTML, importa la demo Nimbus en el editor y pasa la carpeta resultante:

```bash
.venv/bin/python scripts/audit-portable-0200.py --project webapp/projects/SLUG-DE-NIMBUS --output qa/portable
```

`scripts/record-demo-0200.py --output qa/capturas` captura y graba el recorrido real en Chromium, usando una copia temporal de la demo. Los comandos de navegador necesitan las dependencias opcionales `previews`.

## Actualización y contenido del paquete

Descomprime la aplicación en una carpeta nueva. Respalda la instalación anterior mediante **Respaldo integral** y restaura en la instalación nueva vacía. Mantén el respaldo y la carpeta anterior hasta revisar tus proyectos. No copies una `.venv` entre instalaciones.

El ZIP principal conserva fuentes, pruebas, diseños, recursos, demo y documentación vigente. Las evidencias históricas se distribuyen en `report-gen-historial-hasta-0.18.0.zip`, con sus rutas relativas originales. Su extracción es opcional y no es necesaria para usar el programa. El historial contiene datos de validaciones anteriores, no resultados nuevos de la 0.20.

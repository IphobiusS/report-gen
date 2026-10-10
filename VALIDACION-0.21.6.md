# Validación de report-gen 0.21.6

Revisión nueva del paquete 0.21.5, realizada el 8 de octubre de 2026. Se corrigieron defectos reproducidos y se generó un informe nuevo con el exportador nativo. Esta validación describe el entorno realmente ejecutado; no certifica ausencia universal de errores.

## Correcciones verificadas

- Anclas: la validación rechaza colisiones entre IDs de hallazgos, controles portátiles, secciones canónicas, índice y bloques de seguimiento realmente emitidos. Conserva IDs existentes y permite claves personalizadas cuando el bloque automático equivalente no se publica. 43 contratos nuevos; la misma suite produce 38 fallos y 5 controles legítimos aprobados sobre 0.21.5.
- Proyección de seguimiento: todos los activos conservan su orden aunque no tengan UID. El UID sirve solo para resolver vínculos explícitos; una cobertura sin vínculo no hereda el último activo. Un título nulo no interrumpe el seguimiento; se conserva la advertencia de título ausente y la fuente no se modifica. 12 contratos nuevos con cuatro formatos y modos canónico/heredado.
- Comprobación PDF: se conservan los saltos físicos de extracción y se admiten envolturas dentro de tokens largos. Las líneas no vacías deben aparecer en el orden de origen; no se omiten repeticiones. Se rechazan alteraciones de caracteres, puntuación y espacios fuente. La comprobación sigue siendo de presencia textual, no una certificación de espacios/indentación o asociación de código en PDF. 17 contratos nuevos, 7 fallan sobre el comprobador anterior. Las salidas estructuradas mantienen su comprobación literal.
- HTML portátil: palabras de columnas intermedias conservan sus mínimos léxicos sin partir categorías cortas; las tablas siguen desplazándose localmente. Nota y estado vacío dentro de main, contenido en report-content con geometría equivalente; nota visible de versión de exportación; impresión A4 con márgenes de 16 mm. La acción sigue siendo Imprimir vista: los filtros y la vista ejecutiva afectan a esa impresión; el PDF oficial exportado contiene el informe completo.
- Copia del vector CVSS: el estado de éxito aparece solo después de resolver writeText. La escritura pendiente se anuncia ocupada; rechazo o ausencia de API produce error accesible y alternativa manual, sin falso éxito ni promesas rechazadas sin controlar. Botón con nombre accesible estable. 58 comprobaciones en Chromium, ES/EN y cuatro escenarios; el contrato falla sobre el original.

## Ejecuciones nuevas

- Python: 1.200 pruebas aprobadas, cero omisiones, 383,02 segundos. Incluye las 72 pruebas Python nuevas anteriores.
- JavaScript: npm test, 12 aprobadas; DOM/API de workspace, 29 comprobaciones aprobadas.
- Chromium 153.0.8010.0: aceptación 48, editor 72, recuperación 24 y copia CVSS 58 comprobaciones aprobadas. Sin errores JavaScript ni solicitudes externas en las suites que las instrumentan.
- Ruff E9/F aprobado. pip check no detecta incompatibilidades entre los paquetes instalados.
- Seis avisos de la suite Python: uno por futura dependencia HarfBuzz-Subset; cuatro por getdata de Pillow en una prueba de marca; uno por ZIP duplicado creado deliberadamente en un caso negativo. No son seis defectos de producto.

Tras el pase completo, el ajuste acotado de wrapping en tablas de pantalla se verificó nuevamente con 75 contratos de tablas/navegador/anclas y la matriz móvil, sin modificar Python de validación, PDF, Word, Markdown ni JavaScript.

La primera ejecución de npm workspace usó por error el Python del sistema sin Flask; el pase citado usa RG_PYTHON con el entorno de dependencias de la herramienta.

## Informe nuevo Cooperativa Faro

Caso financiero ficticio y rotulado como simulación pública, con ocho condiciones técnicas, seis activos, riesgo empresarial separado de CVSS, apetito de riesgo, cobertura pendiente/bloqueada, responsables y plan propuesto. No acredita un pentest ni un retest real. Dominios .example y evidencia sintética.

Los cuatro formatos se exportaron desde una captura inmutable con 0.21.6 y aprobaron inspect_export. PDF de 22 páginas y Word renderizado de 21 páginas revisados visualmente en su totalidad; ocho evidencias conservadas. El código largo que reveló el falso rechazo sigue en la fuente y en las salidas. 31 comprobaciones independientes de contenido y 34 estados/acciones de Chromium del HTML portátil; cero desbordamiento, errores JavaScript o infracciones axe detectadas en los estados evaluados.

El índice de Word conserva enlaces y campos de paginación que deben actualizarse en el procesador de texto. La impresión de HTML puede tener una paginación distinta del PDF oficial. La valoración financiera pertenece al modelo ficticio, no a una institución evaluada.

## Límites y mejoras pendientes

No se ejecutó Word nativo, un lector de pantalla humano, Firefox/Safari, instalación nueva desde Internet, revisión remota de dependencias/CVE ni pruebas en Windows en esta ronda. La revisión visual Word usa LibreOfficeDev. No se declara conformidad PDF/UA. Los comprobadores y axe complementan la revisión humana; no la sustituyen.

Mejoras opcionales: identificar en papel la vista filtrada/ejecutiva; optimizar densidad de páginas y accesibilidad etiquetada del PDF. No se expanden automáticamente filtros al pulsar Imprimir vista.

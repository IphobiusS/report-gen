# Validación de report-gen 0.21.7

Auditoría final de publicación realizada el 8 de octubre de 2026, partiendo del ZIP 0.21.6 verificado por SHA-256. Se comprobaron entradas extremas, importación, arranque del editor, exportadores y contratos de entrega. No se declara ausencia universal de errores.

## Correcciones

- Los valores nulos conservan su fuente y se presentan sin la palabra Python None. Los títulos ausentes mantienen sus avisos y reciben una etiqueta de presentación accesible.
- Un único idioma efectivo alinea publicación, proyección, plantillas y HTML portátil. Documentos heredados sin idioma/null conservan el fallback inglés del motor; los proyectos nuevos del asistente siguen declarando español. La cadena vacía mantiene el rechazo de validación final.
- Los fragmentos generados codifican los IDs literales que contienen porcentajes, sin renombrarlos. Un resumen sin cuerpo de hallazgos conserva su contenido y omite enlaces automáticos a destinos ausentes. Los apéndices canónicos opcionales sin contenido se omiten de presentación y del espacio de anclas; los personalizados o con contenido se conservan.
- Números CVSS fuera de rango y secuencias de identificadores no representables en JavaScript se rechazan antes de una mutación. Agotar el contador no impide editar o exportar el documento existente.
- Importación coherente con creación respecto a nombres Unicode/casefold, árbol archivo/directorio, tipos de versión, ZIP corrupto y métodos de compresión no admitidos. Los fallos conservan el destino y se anuncian de forma controlada.
- Si falla una API necesaria para arrancar el editor, se muestra un error persistente y una acción de recarga; no se presenta una interfaz habilitada sin eventos.
- El verificador compara orden y límites de tablas en HTML, Markdown y Word, además de contenido. La comprobación PDF sigue siendo de presencia textual y requiere inspección visual.
- El HTML portátil adapta columnas al tamaño de texto extremo y omite controles sin fichas cuando se publican extractos sin detalles.
- Las tablas Word extensas permiten paginación, conservando filas sin corte y cabecera repetible. Se retiraron dos helpers sin consumidores del antiguo camino HTML a Word, conservando el exportador nativo.
- La dependencia opcional de previsualización PyMuPDF pasa de 1.26.6 a 1.26.7, corrección indicada por GHSA-cxqh-p2w9-fmr7/CVE-2026-3029. No se confirmó exposición de la función afectada a través del editor de report-gen.

## Evidencia y límites

Los contratos negativos se ejecutaron sobre la fuente 0.21.6 y los positivos sobre la corrección.

- Suite Python completa: **1324 aprobadas**, sin fallos ni omisiones; 457,80 segundos. Los seis avisos son de APIs de Pillow usadas por pruebas y un ZIP duplicado construido deliberadamente en un negativo.
- Ruff: cero errores. Tras retirar dos imports de pruebas sin uso, se repitieron las 18 pruebas afectadas: todas aprobadas.
- Suites JavaScript declaradas: 12 pruebas de guardado/borradores y 29 contratos de workspace, todos aprobados; 24 contratos adicionales de IDs del editor.
- Modelo: 80 contratos nuevos aprobados; el mismo contrato falla 58 veces sobre la base original. Fuzz de 1062 mutaciones, 173 aceptadas, sin excepciones no controladas después del arreglo.
- IO/API: 27 contratos Python nuevos aprobados; 16 fallan sobre la base original. Editor en Chromium: 22 contratos de límites y 43 de arranque/recuperación aprobados.
- Exportación: 17 contratos de regresión física fallan sobre el original y pasan sobre la corrección; incluyen orden/límites de tablas, texto extremo portátil y paginación Word extensa.
- Consulta OSV del 8 de octubre de 2026: 75 versiones declaradas revisadas, cero coincidencias después de actualizar PyMuPDF; `pip check` no detecta requisitos rotos.

La suite completa incluye las pruebas Python permanentes nuevas; los conteos dirigidos son subconjuntos o comprobaciones complementarias y no se suman como una cifra única de cobertura.

El informe financiero ficticio Cooperativa Faro se conserva como simulación pública, sin pentest o retest real. El riesgo de negocio, apetito y presupuesto son contenido del modelo simulado; la herramienta no calcula ni aprueba automáticamente una política empresarial.

Se generaron exportaciones reales en los seis diseños y cuatro formatos, con español/inglés, código largo, tablas y volumen de cien hallazgos. Una tabla que no cabe completa en una página de un hallazgo PDF conserva la guarda de error explícito: se evita publicar un archivo parcial o una tabla cortada. No se presenta ese rechazo controlado como una exportación aprobada.

Entorno: Linux, Python 3.12, Chromium 153, Word renderizado con LibreOffice. No se probaron Word nativo, Safari/Firefox, Windows ni lector de pantalla humano. El PDF no se certifica PDF/UA. La consulta OSV cubre versiones concretas declaradas en requirements-audited y package-lock; no certifica dependencias del sistema ni vulnerabilidades futuras.

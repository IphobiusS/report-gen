# Validación de report-gen 0.21.8

Auditoría de cierre del 8 de octubre de 2026, desde la entrega 0.21.7 verificada por SHA-256. Se corrigieron defectos reproducidos con contratos que rechazan el original y aprueban la corrección. No se declara ausencia universal de errores ni se sustituye la revisión visual por los controles de contenido.

## Correcciones

- El contrato compara la secuencia de elementos entre listas completas en HTML, Word y Markdown, conservando la anidación. La búsqueda del HTML portátil normaliza NFC sin retirar acentos.
- Una guarda común rechaza en los cuatro formatos una numeración inicial o final superior a 2.147.483.647 sin modificar la fuente o un archivo existente. Los identificadores que excedan ese límite deben presentarse como texto o renumerarse. Chromium reiniciaba esas listas a 1/2 o repetía el máximo; LibreOffice mostraba 0/1. El contenido literal en código sigue conservado.
- WeasyPrint omitía los inicios válidos de listas, como 0 o 7. El renderer emite un reinicio de contador calculado y validado para conservarlos en PDF, sin admitir CSS arbitrario del autor. Los 28 contratos nuevos aprueban, junto con seis específicos de Word. En la iteración anterior a esta guarda común, que ya incluía la guarda de Word, fallan 12 de los 28: nueve rechazos ausentes y tres PDF con inicio incorrecto. Chromium real confirma los ordinales 0, 7 y 2.147.483.647; Faro y Banco se revalidan contra sus fuentes canónicas intactas.
- El índice PDF usa marcadores codificados para claves con espacios/porcentajes y destinos independientes para las secciones heredadas. Los extractos piden páginas solo de bloques emitidos. El inspector detecta residuos de los marcadores codificados.
- Las opciones CLI de idioma y tema se aplican antes de validar. Se retiró la validación redundante del motor.
- Python y editor reservan IDs referenciados con URL codificada. El seguimiento exige fechas AAAA-MM-DD; campos vacíos conservan su estado de borrador.
- Enteros fuera del rango exacto de JavaScript (±9.007.199.254.740.991) se rechazan con la ruta del campo. No se redondean ni convierten en null: los valores documentales mayores se guardan como texto entre comillas.
- Crear desde diseños rechaza nombres Unicode equivalentes; anexos rechazan JSON duplicado y biblioteca exige una versión entera estricta. Fallos de entrada no cambian destino ni historial.
- Tres diálogos de Workflow usan dialog nativo, fondo bloqueado y foco restaurado. El editor con app.js ausente o JavaScript deshabilitado presenta un aviso con recarga nativa y permanece inerte hasta instalar eventos. Se retiraron la trampa manual de foco y ocho reglas de carga/markup animado sin consumidor.
- La guía inglesa enlaza la validación vigente y explica la actualización a esta versión; las notas históricas se conservan.

## Contratos dirigidos y límites

- Modelo: 72 contratos nuevos aprobados; el mismo corpus sobre 0.21.7 produce 42 fallos y 30 pases. El conjunto final de datos/modelo/paginación/entradas ejecuta 150 casos aprobados. Fuzz final: 705 mutaciones, 142 aceptadas, 563 rechazadas, cero excepciones inesperadas.
- IO/API: 13 contratos aprobados; el original produce 12 fallos y un pase. Editor Chromium: 48 del recorrido principal, 24 de recuperación, 72 de edición, 22 de límites y 43 de arranque API. Nuevos: 81 contratos de los tres diálogos, 22 de referencias codificadas y 37 del fallo de recurso/lectura sin JS.
- Editor axe: 64 estados, cero violaciones; 30 estados tienen comprobaciones de contraste incompletas. No se presenta ese resultado como certificación visual o prueba con lector de pantalla.
- Exportación: 15 contratos de listas/Word pasan; nueve negativos rechazan el original y tres positivos Word siguen admitidos. Las cuatro reproducciones Unicode de navegador fallan antes y pasan después. El conjunto de portátil/listas relacionado ejecuta 49 casos aprobados.
- Reflujo portátil Banco/Faro/100 fichas: 63 estados, 280–1366 px, raíz al 400 % y texto al 200 %, sin desbordamiento de página. Doce estados de comportamiento/noJS y seis análisis axe pasan; contraste de algunas imágenes queda incompleto.

Estos grupos se solapan con la suite Python completa o entre sí. No se suman como una cifra única de cobertura.

## Generación real

Matriz nativa: 52 intentos, 46 exportaciones aceptadas y seis rechazos deliberados de PDF por una tabla interna de 44 filas más cabecera que no cabe íntegra. Un seguimiento de 25 operaciones pasa: 24 combinaciones de seis diseños por cuatro formatos con tabla reducida, más una repetición PDF. El informe de 100 hallazgos conserva su tabla-resumen y exporta PDF de 128 páginas. Ambos motores PDF rechazan el caso sobredimensionado conservando exactamente el archivo anterior y la fuente. El rechazo no se cuenta como exportación aprobada.

Cooperativa Faro se genera desde su proyecto nativo y recursos sintéticos sin modificaciones: PDF principal WeasyPrint de 22 páginas; Word renderizado de 21; HTML portátil y Markdown con imágenes. Se inspeccionaron individualmente las 43 páginas de PDF/Word sin recortes, solapes ni hojas vacías. El PDF alternativo Chromium tiene 21 páginas y conserva contenido, ocho imágenes y doce destinos del índice; la diferencia de paginación es esperable.

Banco Lumbre conserva su fuente canónica y PDF histórico. El HTML regenerado verifica 131 unidades de contenido, 219 párrafos, 24 códigos, 33 destinos, 14 evidencias y 49 tablas. Faro y Banco aprueban require_valid(final=True) tras la última guarda numérica. Son simulaciones públicas; riesgo, apetito y presupuesto son supuestos redactados, no resultados empresariales calculados o aprobados por el motor.

## Entorno

Linux, Python 3.12, Chromium 153 y LibreOffice para renderizar Word. Windows, Microsoft Word de escritorio, Firefox/Safari y lector de pantalla humano no se ejecutaron en esta ronda. PDF no se certifica PDF/UA. Los controles de PDF son textuales y de presencia de imágenes/índice; su revisión visual aquí corresponde al Faro final, no a cada página de toda la matriz de estrés.

Consulta OSV del 8 de octubre de 2026: 75 versiones declaradas (33 PyPI, 42 npm), cero coincidencias y sin paginación pendiente. pip check no detecta requisitos incompatibles. Esta consulta no cubre el sistema operativo ni vulnerabilidades futuras.

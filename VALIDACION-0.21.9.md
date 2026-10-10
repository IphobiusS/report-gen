# Validación de report-gen 0.21.9

Repaso final del 8 de octubre de 2026 desde el ZIP 0.21.8 verificado por SHA-256. Se reproduce y corrige la pérdida de entradas al elegir un destino de exportación que coincide con la fuente o sus recursos.

## Corrección

Una guarda compartida rechaza destinos coincidentes con el YAML, imágenes de figuras/Markdown/branding, originales declarados y anexos, aunque estén excluidos de la publicación. Compara rutas resueltas y aliases reales (symlink/hardlink). Markdown comprueba el ZIP efectivo; la CLI comprueba el PDF y el HTML secundario. La selección --only conserva la protección de recursos omitidos. La validación final de las entradas precede a la guarda y ninguna creación de directorio o escritura la antecede. Los informes anteriores distintos de las entradas siguen pudiendo sustituirse.

## Contratos

El mismo corpus de 46 pruebas produce 31 fallos y 15 pases sobre 0.21.8; corregido aprueba 46/46. Incluye seis entradas inválidas con rechazo controlado, API en cuatro formatos y reemplazos normales. Los negativos cotejan las huellas de fuente, recursos y salida previa; no se cuenta un rechazo deliberado como exportación aprobada. Un conjunto relacionado de 97 contratos de exportación/listas/regresiones también pasa.

Npm aprueba 12 pruebas y workspace 29; Ruff y pip check sin errores. El recorrido principal Chromium se repite tras la corrección y aprueba 48 comprobaciones; los demás 188 de editor/arranque/referencias se ejecutan en esta ronda sobre las mismas fuentes UI verificadas por SHA. La suite Python completa y la aceptación de ZIP se documentan, con cifras reales y alcance, en el informe de cierre que acompaña la entrega.

## Generación y límites

Faro y Banco siguen siendo simulaciones públicas. Se generan nuevamente los cuatro formatos de Faro y el HTML portátil de Banco con esta versión y se cotejan contra sus fuentes canónicas; no se inventa un retest empresarial. La revisión visual se documenta por salida en el informe final.

Entorno: Linux, Python 3.12, Chromium 153 y LibreOffice. Microsoft Word nativo, Firefox/Safari y lector de pantalla humano no se verifican aquí. Los controles automáticos de contenido no sustituyen la revisión visual. Las dependencias declaradas no cambian respecto de 0.21.8.

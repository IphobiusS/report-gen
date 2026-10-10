# Validación de report-gen 0.22.0

Revisión de uso y entrega del 8 de octubre de 2026, desde el ZIP 0.21.9 verificado por SHA-256. Se recorrieron proyectos nuevos, Nimbus, evidencias, revisión, entrega de cuatro formatos, respaldo e importación en Chromium real.

## Orientación y diseño

La guía visual opcional puede abrirse desde Inicio y desde el acceso lateral o Más en móvil. Sus seis pasos cubren inicio, alcance, hallazgos, evidencias, revisión y entrega/respaldo. Incluye ejemplos ficticios, acciones hacia las vistas reales y explicaciones de guardado, privacidad, CVSS, riesgo empresarial y retest. No crea proyectos ni completa campos al leerla. La animación de entrada es breve y respeta movimiento reducido. No requiere GIF ni servicios externos.

## Defectos corregidos

- Hallazgos vacío y poblado disponen de acciones visibles para añadir un hallazgo o usar la biblioteca. Antes, el tablero vacío remitía a un control que quedaba oculto.
- Los editores Markdown y las opciones de inclusión ya no añaden campos vacíos al abrir Alcance, Cobertura o Retest. Incorporan los valores al editar; la navegación conserva los datos y la revisión.
- Revisión y captura comparten un preflight. Los avisos de validación, incluido CVSS ausente, se conservan junto a los del flujo en verificacion.json y LEEME.txt. La entrega directa y la cola requieren su confirmación. Los avisos siguen siendo opcionales de contenido; los errores permanecen bloqueantes. La publicación usa exactamente el documento revisado.
- Los README ES/EN priorizan instalación y primer uso, remiten a la guía integrada y actualizan las instrucciones de migración. Las referencias históricas de compatibilidad se conservan.

## Contratos de esta entrega

La guía aprueba 388 contratos en Chromium 153: 96 estados de geometría, seis pasos, español/inglés, 280/320/390/1366 px y texto al 100/200 %. No hay desbordamiento de documento ni de la guía; las acciones tienen 44 px como mínimo. Ocho revisiones axe en dos idiomas, dos anchos y ambos temas no detectan violaciones ni resultados incompletos. Se prueban foco y teclado nativos, movimiento reducido, importación propia y descarga abortada de guide.js. Leer la guía no cambia YAML, revisión ni datos del proyecto.

La revisión de foco detectó y corrigió un defecto de la guía nueva: cambiar de paso en móvil podía enfocar un título fuera de pantalla. El destino se revela con desplazamiento inmediato solo cuando hace falta. Dieciocho comprobaciones exigen intersección real con el viewport; el mismo contrato sobre la implementación previa falla en los doce casos móviles y pasa en los seis de escritorio.

Los contratos aislados de Hallazgos y lectura de editores aprueban siete comprobaciones; ambos fallan sobre 0.21.9 con el mismo contrato. Las pruebas de los editores incluyen persistencia real después de editar.

La trazabilidad de avisos tiene 27 casos nuevos y 105 regresiones relacionadas aprobados. Tres contratos idénticos fallan sobre 0.21.9: entrega directa y en cola sin confirmación, y pérdida del aviso en el ZIP de cuatro formatos. Incluye ES/EN, avisos combinados, errores, CSRF, revisión obsoleta, fuente legacy, snapshot único y ediciones posteriores al encolado.

La suite completa aprueba 1.529 pruebas Python, sin fallos, errores ni pruebas saltadas; npm aprueba 12 y el contrato DOM heredado 29. Ruff y pip check terminan sin errores. Las seis advertencias del entorno corresponden a deprecaciones y al ZIP duplicado intencional de un caso de rechazo; no son exportaciones fallidas. La ejecución anterior interrumpida antes de corregir el preflight queda excluida.

Desde el ZIP extraído, la guía y los dos contratos aislados aprueban 395 comprobaciones. Las seis puertas de regresión del editor aprueban otras 236: 190 en Chromium real y 46 en Node. Los archivos de producto y pruebas cotejados coinciden con la fuente congelada. El manifiesto SHA-256 incluye todos los archivos de la entrega salvo el propio manifiesto; la validación final se comprueba después de reconstruir el ZIP.

## Generación y límites

Se genera Faro nuevamente en PDF, Word, Markdown y HTML desde su fuente canónica pública de simulación, conservada intacta junto a sus ocho imágenes. PDF tiene 22 páginas y Word 21 páginas renderizadas. Texto, posiciones de palabras PDF, miembros Word/Markdown y los 43 PNG de páginas coinciden con la entrega anterior; HTML solo cambia el rótulo de versión. Se reabren seis páginas de portada, hallazgo y final, sin defectos. Los contratos de exportación se repiten sobre la captura final.

El pipeline nativo de entrega conserva exactamente los siete avisos de cobertura de Faro en verificacion.json y LEEME.txt. Al retirar una puntuación CVSS en una copia de prueba conserva los ocho, incluido ese aviso. Esta comprobación es del pipeline, no una prueba de interfaz. Banco Lumbre se reexporta a HTML con contrato completo y contenido idéntico salvo versión; su PDF histórico no se modifica. Las fuentes siguen rotuladas como simulaciones y no representan un encargo ni un retest empresarial nuevo.

Entorno: Linux, Python 3.12 y Chromium 153. No se verifica Microsoft Word nativo en Windows, Firefox/Safari ni lector de pantalla humano. Los controles de integridad no sustituyen revisar visualmente los archivos. CVSS es severidad técnica; el contexto de negocio y el apetito de riesgo los documentan y justifican el evaluador y la organización. Los respaldos conservan datos privados y no son el paquete ordinario para el cliente.

Las dependencias declaradas no cambian respecto de 0.21.9. Se mantienen las protecciones de entradas y destinos de exportación de esa versión.

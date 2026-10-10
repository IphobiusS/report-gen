# Validación de report-gen 0.22.1

Cierre de observaciones de la auditoría independiente del 8 de octubre de 2026 sobre el ZIP 0.22.0, identificado por SHA-256 `993c59adceeee1f303b0192dd7d23159b8f98c08161ff8e5e95458a1e906fb59`.

## Cambios de esta revisión

- CHANGELOG incorpora la entrada histórica que faltaba de 0.22.0 y la entrada de esta revisión. Los README ES/EN, la versión Python, package.json y su lock coinciden en 0.22.1; los comandos y dependencias conservan su contenido anterior.
- La cabecera solicita desde el HTML inicial el símbolo SVG de 1.311 bytes que ya utilizaba después de arrancar. El PNG detallado permanece en Bienvenida, Acerca de y documentación.
- El PNG se recomprime sin pérdida: de 1.602.203 a 1.483.406 bytes, ahorro de 118.797 bytes. Se conservan dimensiones 1536 × 1024, RGBA y todos los píxeles decodificados, incluidos los transparentes. No se rediseña ni reduce la resolución del logo.
- La revisión visual encuentra un defecto adicional en Acerca de: su enlace GitHub heredaba el azul de navegador sobre el panel oscuro. Los enlaces de estos diálogos usan ahora el acento del tema y mantienen el subrayado.

## Verificación acotada

Se contrastan los 154 archivos Python con el ZIP 0.22.0: solo cambia version.py. También permanecen idénticos los 14 archivos JavaScript, 12 de los 13 CSS y los 18 CJS. El único CSS modificado es workbench.css, con la regla para los enlaces de los diálogos. Los motores de informe, CVSS, almacenamiento, importación, preflight y entrega conservan los bytes previamente validados.

Se repiten 12 pruebas npm, 29 comprobaciones DOM/API, 37 contratos de arranque degradado y 388 de la guía visual en Chromium 153. La guía conserva 96 estados de geometría, ES/EN, 280/320/390/1366 px, texto al 100/200 %, ocho estados axe sin infracciones ni resultados incompletos, navegación y ausencia de modificación de datos al leer. Se comprueban además los activos reales de cabecera, bienvenida y Acerca de en escritorio y móvil, con densidad de píxeles 2: 44 comprobaciones aprobadas en seis estados.

El enlace de Acerca de aprueba 57 comprobaciones en ocho estados ES/EN × oscuro/claro × 320/1366 px. Se desplaza dentro del diálogo para comprobarlo visible, con foco nativo, objetivo de 44 px, subrayado y contraste 12,57:1 en oscuro / 7,67:1 en claro. El mismo contrato sobre el CSS anterior rechaza el enlace azul de 1,83:1; axe también detecta el defecto cuando está dentro del área visible. Axe no devuelve infracciones en los ocho estados: sus cuatro estados de escritorio son completos y los cuatro móviles tienen resultados incompletos, por lo que en móvil la evidencia principal es el contraste calculado desde los colores y fondo reales del navegador. La corrección se verifica sobre el CSS final, separado de los contratos de la guía que ya habían terminado.

Banco Lumbre se exporta nuevamente a HTML con 0.22.1 desde su fuente pública de simulación. El contrato comprueba metadatos, 219 párrafos, 24 bloques de código, 49 tablas, 14 imágenes y asociaciones, enlaces y referencias internas. El contenido coincide con la exportación anterior salvo el rótulo de versión. La fuente y recursos siguen intactos. Su PDF histórico de 60 páginas no se modifica.

El manifiesto MANIFEST-0.22.1.sha256 cubre todos los archivos del nuevo paquete excepto el propio manifiesto. La integridad y el contenido se cotejan tras construir el ZIP; el sitio asociado contiene exactamente ese mismo ZIP y sus metadatos de bytes/SHA-256.

## Trazabilidad y límites

Las 1.529 pruebas Python completas sin fallos ni omisiones pertenecen a la validación anterior de 0.22.0, conservada en VALIDACION-0.22.0.md; no se presentan como una nueva ejecución en esta revisión documental y de recursos. La procedencia binaria y los contratos de interfaz determinan las comprobaciones pertinentes de este parche.

El log externo report-gen-0.22.0-pytest.log adjunto termina con 1.492 aprobadas, un fallo por ausencia de jsdom y 36 omitidas por requisitos de navegador. Su resumen declara repeticiones posteriores aprobadas, pero estas no figuran en ese archivo. Por ello se distingue esa declaración de la evidencia directamente observable y del registro completo de nuestra validación anterior.

Entorno de este cierre: Linux, Python 3.12 y Chromium 153. No se verifica Word nativo en Windows, Firefox/Safari ni lector de pantalla humano. El contrato de contenido no certifica por sí solo toda la geometría de una exportación; se mantienen los límites y la revisión visual requeridos. No hay cambios de esquema ni nuevas funciones de escaneo o aprobación automática de riesgo. Las simulaciones siguen declaradas como ficticias y sin ejecución empresarial ni retest nuevos.

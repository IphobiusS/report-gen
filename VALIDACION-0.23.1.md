# Validación 0.23.1 (2026-10-08)

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Iteración de UX sobre 0.23.0. No cambia el formato del proyecto ni el contenido narrativo del informe. Sí corrige metadatos heredados del DOCX. Leer y navegar entre hallazgos no guarda ni reescribe el proyecto.

## Cambios y límites de comportamiento

- La preview HTML sigue el hallazgo abierto, con resaltado y desplazamiento inmediato. Vincula UID, snapshot y documento para rechazar respuestas antiguas. Solo genera cuando el panel está realmente visible. El visor PDF nativo no permite esta sincronización; el panel de preview aparece desde 1101 px.
- Anterior/Siguiente utiliza el orden completo del proyecto, conserva los UID, anuncia posición y mueve el foco al título. Los extremos quedan deshabilitados. No equivale al orden de una tabla filtrada.
- La marca WebP lossless pesa 344.486 bytes, frente a 1.483.406 del PNG original: 76,78 % menos transferencia. Conserva exactamente los píxeles del PNG redimensionado a 900 × 600; se conserva el PNG para las referencias documentales.
- Corregidos al ampliar texto al 200 %: solapamiento de pestañas, campos vacíos que creaban scroll sin foco, reflow de CVSS y botones de galería. El selector de versión CVSS tiene nombre accesible ES/EN y la etiqueta crítica cumple contraste en claro y oscuro.
- DOCX recibe título, autor e idioma de la copia preparada para su audiencia, con el límite de 255 caracteres de sus propiedades. Se eliminan el autor y las fechas de plantilla de 2013; no se inventa una fecha de creación. No cambian la fecha de evaluación ni el texto del cuerpo. Las propiedades de comentarios y último editor quedan vacías.
- Las instrucciones de actualización ES/EN apuntan a 0.23.1. Las notas y los ejemplos históricos conservan su versión real.

## Evidencia final

- Suite completa: 1.750 aprobadas, cero fallos, cero errores y cero omitidas, Python 3.12.14 y Chromium 153.0.8010.0. Los 229 archivos de runtime/contratos se mantuvieron idénticos durante la ejecución final. SHA de log, JUnit y fuentes en docs/validation-0.23.1-summary.json.
- Node: guardado 12/12, workspace 29/29 y editor 24/24. pip check sin conflictos y ruff check . aprobado.
- Auditoría independiente: 47 contratos funcionales y 107 de texto al 200 % efectivo, en 53 estados. El mismo contrato sobre el código anterior produce 34 fallos y salida 1. El negativo de sincronización también falla al retirar la guarda; el de metadatos DOCX falla sobre el exportador original.
- Los cuatro formatos se generaron desde una misma revisión guardada de Nimbus: PDF, Word, Markdown y HTML. Comprobaciones separadas 140, 506 y 17; se solapan y no representan 663 escenarios únicos. PDF de 38 páginas rasterizadas, revisado mediante hojas de contacto y tres páginas detalladas. HTML comprobado con y sin JS a 320, 390 y 1366 px. Word verificado por OPC/XML, imágenes, metadatos y CRC, sin Microsoft Word nativo.
- La primera ejecución completa encontró una carrera del arnés de streaming: el servidor liberaba la respuesta a los 800 ms antes de garantizar la lectura del estado inicial. Se sustituyó el temporizador por liberación explícita después de las mismas aserciones iniciales; se conservan las comprobaciones de altura, invisibilidad, listeners, CLS y CSP. La suite completa indicada arriba corresponde al arnés final.
- Sitio: 21 páginas, 252 estados de ancho/tema y 21 adicionales sin JS, movimiento reducido y CLS: 273/273. CLS máximo medido 0. Capturas actuales y su procedencia verificada, cuaderno compacto y sus regresiones, enlaces y build comprobados por separado. El ZIP exacto de la herramienta se integra y verifica al cerrar los paquetes.

## Alcance de la entrega

Se atendieron las prioridades de sitio 1, 2 y 6 y de herramienta 1, 2 y 13 del informe independiente, además de errores observados durante esta auditoría. Fondo ya tenía semántica coherente: aria-pressed=true corresponde a movimiento activo; no se invirtió su lógica. Las otras 19 propuestas siguen como evolución futura.

No se ejecutó un pentest nuevo. Nimbus y Banco Lumbre conservan sus rótulos y procedencia de simulación. Los PDFs y HTML históricos publicados no se atribuyen retroactivamente a 0.23.1.

Firefox, Safari, Microsoft Word nativo en Windows, lector de pantalla humano y un modelo Ollama instalado requieren evaluación separada. La suite automatizada valida su alcance, no garantiza la ausencia de cualquier error futuro. No se desplegó ni se creó un tag.

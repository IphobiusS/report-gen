# Validación 0.23.0 (2026-10-08)

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Versión nueva sobre 0.22.1, con modelo de decisiones opcional y compatibilidad con proyectos anteriores. Leer las pantallas no rellena campos. Las identidades de revisión son declaraciones locales, no firmas autenticadas; la aprobación no verifica un pentest ni da permiso para publicar.

## Alcance integrado

Mapa de evidencia y límites; contexto de riesgo sin pérdidas inventadas; observaciones y revisión vinculadas a contenido, imágenes y comentarios; entregas independientes para técnico, dirección y público; revisión de páginas del PDF real; reglas de redacción y asistencia Ollama opcional; paginación y guardas de lectura en proyectos grandes. Guía ES/EN en docs/evidence-decisions-0230.md y su versión inglesa.

## Evidencia de esta iteración

- Suite completa final: 1.748 pruebas, cero fallos y cero omitidas en Python 3.12.14, sobre la fuente cerrada. XML y log identificados por SHA-256 en docs/validation-0.23.0/summary.json.
- Modelo de decisiones, IA y avisos: 150 contratos; audiencias y presupuesto de sustitución: 71; revisión visual: 25.
- Chromium 153 real: 503 comprobaciones independientes de las seis pantallas, 96 estados de idioma, ancho, tema y texto al 200 %, sin errores de consola, overflow ni violaciones axe en el panel nuevo; los controles y flujos heredados tienen regresiones separadas.
- Regresiones heredadas: 236 contratos de navegador/DOM, más 388 de la guía; guardado/borradores Node 12 y espacio de trabajo DOM 29. La expectativa antigua de 500 filas se reemplazó por el mismo contrato reforzado: 500 registros, 50 visibles y último alcanzable por teclado/búsqueda.
- Cuatro entregas directas/en cola con los cuatro formatos: 53 comprobaciones adicionales. Comentarios privados y marcados públicos, revisiones y notas internas quedan fuera de documentos, manifiestos y avisos.
- Nueva generación real de Faro y Banco Lumbre: PDF, Word, Markdown y HTML. Fuentes y recursos conservados. PDF 22/60 páginas; todas renderizadas y muestras revisadas. El PDF histórico de Banco publicado en la web permanece íntegro; su HTML se reexporta con 0.23.0.
- 51 contratos finales de escala: 50, 250 y 1.000 hallazgos con igual número de evidencias; búsqueda, asociaciones, reordenación, vista previa y conservación de fuentes mediante HTML. La cola y los otros formatos tienen contratos separados; no se midió PDF/Word de 1.000 hallazgos. Contratos negativos reales sobre 0.22.1 y sobre copias con guardas retiradas.

## Defectos detectados y corregidos

Exclusión de comentarios privados de avisos/exportaciones; invalidación al cambiar o eliminar comentarios; alias con `_` o `.` antes del escape Markdown; límites de expansión literal UTF-8 antes de reservar memoria; editores heredados que añadían campos al leer; render de preview oculto; galería cuadrática; borrado del PDF temporal que pedía JSON; borradores de un proyecto borrado que reaparecían al recrear el slug; selección del PDF principal con anexos PDF e identidad separada de cada trabajo; colisión de nombres Flask durante la integración.

## Rendimiento y límites

Comparación de tres rondas con 1.000 hallazgos y 20 imágenes pequeñas: mediana de tablero 253,5 → 79,8 ms; nodos de galería 45.440 → 839; RSS de Chromium 951 → 530 MB. Máquina compartida con otras comprobaciones: no es una garantía universal. Son snapshots comparativos; los 51 contratos finales verifican SHA de las fuentes actuales.

Guardar modelos grandes conserva coste de YAML: unos 5,9 s con 1.000 hallazgos; unos 13,3 s con 1.000 afirmaciones, riesgos y comentarios adicionales. Las cifras incluyen esperas HTTP y debounce. No se optimizó la persistencia sacrificando recuperación o historial.

Miniaturas requieren PyMuPDF opcional. Límite 16 MB, 500 páginas, cuatro vistas por sesión y ocho globales; proceso acotado con plazo, y memoria/CPU en POSIX. El acceso caduca tras 30 minutos y la purga de memoria es diferida hasta la siguiente consulta o el reinicio. La caché de miniaturas tiene un presupuesto separado y acotado. El registro visual se refiere al PDF exacto; subir un archivo no acredita que provenga del proyecto. No se validó Microsoft Word nativo.

IA: se verificó el protocolo con respuestas sintéticas, guardas de fuente/revisión y un servidor HTTP local real para interrupción por plazo. No se ejecutó un modelo LLM instalado. Ollama es opcional, no se instala ni inicia; desactivar nube en su servidor. El adaptador rechaza modelos remotos conocidos, URLs ajenas, proxies del entorno y redirecciones, pero no certifica el aislamiento de otro proceso. Ninguna sugerencia se aplica automáticamente.

Firefox, Safari, Word de Windows y lector de pantalla humano requieren validación separada. Los extractos y patrones de secretos tienen límites documentados; el autor debe revisar cada salida y contar con permiso real. Ningún despliegue está incluido en esta entrega.

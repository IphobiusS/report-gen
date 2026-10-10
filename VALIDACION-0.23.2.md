# Validación 0.23.2

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

Iteración R03, R04, R05 y R06 sobre la base 0.23.1 comprobada por SHA-256. No se cambió el esquema del proyecto ni los exportadores. La navegación, la revisión editorial y la preparación de entrega conservan las identidades y los controles de concurrencia.

- Suite completa: 1770 pruebas distintas aprobadas, cero fallos, errores u omitidas, repartidas en cuatro grupos de archivos disjuntos. La colección y los JUnit concuerdan; no se suman pruebas duplicadas. Python 3.12.14, Linux, Chromium 153.0.8010.0.
- 234 archivos de fuentes y contratos permanecieron idénticos durante la ejecución final. Hashes, comandos y distribución en docs/validation-0.23.2-summary.json.
- Node: guardado y recuperación 12/12; workspace DOM 29/29; navegación existente 24/24; flujo diario 29/29; preparación 13/13.
- Auditoría independiente de report-gen: 34/34, incluidos lectura sin mutación, UID tras reordenación, conflictos, datos reales, revisión guardada, foco y texto al 200 % en ES/EN y claro/oscuro. Son suites con solapes; no se suman como escenarios únicos.
- Ruff y pip check aprobados. Los contratos de preparación incluyen recursos corruptos o ausentes, anexos alterados, secretos redactados, asociaciones inexistentes y errores estructurales.

La revisión agrupa avisos y muestra cuántos avisos iniciales dejaron de aparecer en esta sesión. No registra aceptación editorial ni verificación técnica. La lista de entrega deriva hechos de la revisión guardada; imágenes y anexos necesitan revisión humana. Una coincidencia con justificación sigue siendo una decisión del autor.

Se corrigieron la navegación de teclado anclada al UID mostrado frente a una reordenación interpuesta y la inspección de una imagen corrupta, que debe declarar Sin comprobar. La suite completa también reveló un defecto heredado de importación y restauración, reproducido con fallos deterministas en la base original: una transacción anidada podía dejar un registro dirigido a una carpeta privada que reaparecía al recuperar y bloqueaba el respaldo del espacio. La preparación privada ahora usa el contexto de staging existente; conserva la publicación única, la recuperación externa, los snapshots y sus hashes. Diez contratos nuevos prueban limpieza, fallos de YAML/checkpoint/publicación, contexto restaurado y rollback de una edición posterior.

Se corrigió además la espera del arnés de integración para distinguir la revisión resuelta de su mensaje de carga, manteniendo la aserción de avisos pendientes. La primera ejecución completa tuvo estos dos fallos y se conserva como evidencia de diagnóstico; no acredita el resultado final. Las ejecuciones anteriores a la congelación también quedan separadas.

El sitio integra el ZIP exacto de esta versión. Las capturas históricas 0.23.1 y los documentos de Nimbus y Banco Lumbre conservan su versión real; no se atribuyen a una generación nueva. Esta ronda no acredita una revisión visual detallada nueva de un PDF completo ni Microsoft Word nativo. Las pruebas de regresión de los exportadores sí forman parte de la suite.

No se verificaron Firefox, Safari, un lector de pantalla humano ni un modelo Ollama real. No se ejecutó un pentest nuevo, no se desplegó y no se creó un tag. La cobertura automatizada no garantiza la ausencia absoluta de errores.

Contratos nuevos: tests/test_daily_workflow_0232.cjs, tests/test_delivery_readiness_0232.cjs, tests/test_delivery_readiness_0232.py y tests/test_private_staging_0232.py. Ejecución: pytest, npm test, npm run test:workspace, npm run test:editor, npm run test:daily y npm run test:delivery con Python, Playwright y Chromium disponibles.

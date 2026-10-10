# Validación 0.23.3

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

R07, R08 y R09 sobre el ZIP verificado 0.23.2. No se cambia el esquema del proyecto ni los exportadores. Lectura sin guardado implícito, borradores por UID, baselines identificados y separación entre estado, verificación y resultado observado.

- Suite completa: 1814 pruebas distintas aprobadas, cero fallos, errores u omitidas. Cuatro grupos disjuntos; colección, JUnit y códigos de salida concuerdan. Python 3.12.14 y Chromium 153.0.8010.0 en Linux.
- 246 fuentes y contratos sin cambios durante la suite final. Comandos, hashes y resultados completos en docs/validation-0.23.3-summary.json.
- Regresiones Node/Chromium: guardado 12, workspace 29, navegación 24, flujo diario 29 y preparación 13.
- Nuevos contratos Chromium: pestañas 29, comparación 16, matriz 36. Auditorías independientes: API 37 y navegador 57. Suites con solapes, no se suman como escenarios únicos.
- Ruff y pip check aprobados. Lecturas no alteran archivos ni asignan UID a documentos heredados. Fechas UTC, empate y fechas ambiguas exigen una base explícita; las versiones draft/retest no se presentan como entregas. Revisión y hash de snapshot bloquean comparaciones obsoletas. La visual compartible usa la proyección existente de publicación y sus redacciones; la privada exige reconocimiento explícito.

Después de la suite Python se alineó únicamente el indicador superior Revisar para las dos nuevas vistas y se amplió la aserción de sus dos contratos de navegador. Tres archivos frontend/contratos cambiaron; todos los Python conservaron sus bytes. Las suites nuevas y la auditoría independiente de navegador se repitieron sobre ese estado definitivo. Deltas y hashes finales en docs/validation-0.23.3-summary.json y post-python-ui.json.

La integración lateral mueve explícitamente los dos accesos nuevos antes de retirar el contenedor anterior. Los contratos de comparación y matriz abren esas vistas con clics de usuario. Una ejecución anterior se interrumpió al detectar ese defecto; no acredita el resultado final.

La etapa delivered es una declaración local del autor. No demuestra exportación completada ni recepción del cliente. Retirar un hallazgo no demuestra corrección. La matriz usa la última observación con fecha ISO válida, desempata por orden de registro y expone registros excluidos o resultados no reconocidos; cuenta asociaciones registradas, sin acreditar archivos, suficiencia o aprobación técnica. La vista ejecutiva en pantalla no cambia los informes exportados.

La auditoría cubre foco, pestañas ARIA, borradores y enlaces por UID, cambios de proyecto/revisión, ETag rechazado, datos privados y móviles con texto al 200 % en ES/EN. Los logs crudos se conservan y los totales se derivan de JUnit; su completitud se declara en commands.json.

Las capturas y documentos históricos conservan sus versiones reales. No se verificaron Word nativo, Firefox, Safari, lector de pantalla humano ni Ollama real. No hubo pentest nuevo, despliegue o tag, ni revisión visual detallada nueva de un PDF. Los contratos de exportadores sí forman parte de pytest. Automatización no garantiza ausencia absoluta de defectos.

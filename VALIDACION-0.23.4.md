# Validación 0.23.4

> **Nota de archivo para GitHub.** Las referencias de esta acta a registros técnicos, resultados estructurados, capturas y otros archivos de evidencia corresponden a material archivado fuera de GitHub, no adjunto en este repositorio. Se conserva aquí el resumen y el alcance de la validación documentada. Publicar esta acta no supone una nueva ejecución de esas pruebas ni cambia sus resultados.

R11 y R14 sobre la base 0.23.3 verificada, sin cambio de esquema ni de políticas de publicación. Históricos intactos.

- Suite completa final: 1898 pruebas distintas, cero fallos, errores u omitidas. Colección y JUnit concuerdan en cuatro grupos disjuntos; logs crudos con finalización al 100 %. 253 fuentes y contratos de runtime conservan sus bytes durante la ejecución. Ruff y pip check aprobados.
- Nueve comandos finales Node/Chromium aprobados: guardado 12, workspace 29, navegación 24, flujo diario 29, preparación 13, pestañas 29, comparación 16, matriz 36 y cliente de idioma 7. La matriz ejecuta axe en 16 estados.
- R11 focal: 57 pruebas. Catálogo explícito de 549 plantillas, selección antes de interpolar datos y contextos aislados por solicitud y trabajo. Auditoría independiente real: 81 comprobaciones HTTP y 22 Chromium mediante botones y errores reales; sus 253 fuentes de código quedan intactas. Las suites se solapan y no se suman como escenarios únicos.
- R14 focal: 27 pruebas, seis PDF reales con 112 páginas y 142 paneles; presencia de texto y MediaBox comprobados. Once páginas seleccionadas rasterizadas e inspeccionadas, sin atribuir revisión detallada a las otras páginas. Independiente: 86 comprobaciones sobre nueve PDF actuales más una base negativa y 20 de límites y mutantes; once páginas seleccionadas inspeccionadas. Las ocho fuentes del recorrido coinciden con el estado final.

La primera suite Node se detuvo al vencer el plazo original de seis segundos del workspace antes de recibir una respuesta HTTP 200 de guardado. La repetición aislada conservó el mismo límite y pasó 29/29. No se cambió código ni expectativas; se repitieron los nueve comandos originales después de terminar Python. La causa concreta del retraso no está establecida. Diagnósticos separados en la evidencia de auditoría.

R11 mantiene códigos, claves, status HTTP, Host/Origin, CSRF, ETag y revisión. X-UI-Language selecciona es/en; ausencia o valor no admitido conserva el español predeterminado, incluso en URL abiertas directamente. El idioma del informe es independiente. Descripciones heredadas de Werkzeug y diagnósticos externos se conservan literalmente. Los errores de trabajos mantienen el idioma capturado al crearlos. Se retiró una sustitución posterior a la interpolación que podía modificar identificadores o texto del usuario.

R14 representa fases y pasos registrados. Las flechas indican orden documental, sin inferir causalidad, ramas, privilegios o éxito. Los comandos no se usan como etiquetas. Las referencias de figuras provienen de la numeración real; una imagen Markdown sin número no se declara evidencia ausente. La evidencia añadida por workflow se separa del recorrido. La proyección de audiencia precede al gráfico. Los paneles contienen hasta tres pasos; el texto completo puede fluir a otras páginas. En la muestra de 105 fases el PDF tiene 58 páginas; 70 pasos producen 31. No se omiten entradas para ahorrar páginas. HTML, Word y Markdown no incorporan el grafo.

Se corrigieron recortes de etiquetas sin marcador y contraste de leyendas sobre tema oscuro; las ejecuciones previas son diagnósticos y no acreditan el producto final. Código, comandos, hashes y resultados en docs/validation-0.23.4-summary.json y docs/validation-0.23.4.

Python 3.12.14, Chromium 153.0.8010.0 y WeasyPrint en Linux. No se verificaron Word nativo, Firefox, Safari, lector humano ni Ollama real. No hubo pentest nuevo, despliegue ni tag. La automatización no garantiza ausencia absoluta de defectos.

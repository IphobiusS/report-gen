# Aceptación del inicio guiado — report-gen 0.43.0

Este protocolo verifica las vistas Guiado y Completo, el recorrido contextual y la práctica ficticia. Describe qué comprobar; no acredita una ejecución ni una ausencia universal de defectos. Los resultados deben vincularse al commit exacto evaluado.

## Comportamiento esperado

- El primer acceso permite elegir Guiado o Completo sin bloquear el editor. La elección se recuerda por espacio de trabajo y se puede cambiar. Ambas vistas conservan nombres, rutas, capacidades y datos; los grupos avanzados plegados siguen accesibles.
- Las seis etapas Proyecto, Alcance, Hallazgos, Evidencias, Revisión y Entrega explican y destacan controles reales. El usuario puede saltar, volver, pausar, reanudar y reiniciar sin ejecutar la acción explicada. La ayuda contextual corresponde a la vista actual.
- Cambiar de vista, leer ayuda y avanzar en el recorrido conserva el contenido del modelo, la revisión guardada, los identificadores y el archivo del proyecto. Tampoco marca pruebas como ejecutadas, evidencias como aprobadas, vulnerabilidades como verificadas o retests como cerrados.
- El progreso didáctico se separa por espacio de trabajo y proyecto. Las preferencias corruptas se recuperan sin bloquear el editor; si el almacenamiento está denegado, el recorrido funciona durante la sesión.
- Cada práctica crea una copia Nimbus independiente en el idioma de la interfaz, identificada como práctica por la procedencia registrada al crearla. Guarda primero las ediciones del proyecto abierto. Un fallo de guardado impide iniciar o volver de la práctica; el retorno al proyecto previo conserva sus datos. Ocultar el recorrido Nimbus no oculta la identidad de práctica.
- La etiqueta de práctica procede del registro creado por el servidor, no del nombre ni de preferencias del navegador. Un proyecto normal cuyo nombre empiece por `nimbus-demo-` no recibe la etiqueta. Guardar, renombrar y restaurar el historial integrado conservan la procedencia. Bloquear el almacenamiento del navegador no la oculta. Los respaldos portátiles no la incluyen; demos anteriores a 0.43 y copias reimportadas pueden no mostrar etiqueta. La etiqueta acredita el origen de la copia, no que todas las ediciones posteriores sean ficticias.
- Las vistas, ejemplos y ayudas funcionan en ES/EN/PT. El teclado alcanza los controles, el foco sigue siendo visible y cerrar ayudas devuelve el foco a un control adecuado. Los diálogos y la navegación móvil conservan sus contratos.
- Todos los botones, selectores y controles de despliegue visibles de la barra lateral mantienen al menos 40 px de alto en escritorio y 44 px en móvil, en Guiado y Completo. El selector de vista y los dos accesos de ayuda se incluyen explícitamente en la medición para evitar una comprobación vacía.
- El Tutorial visual anterior sigue disponible y mantiene su progreso separado. Los accesos de revisión, vista previa, exportación y respaldo siguen usando las rutas existentes.

## Verificación local

Desde la raíz del repositorio, con dependencias Python y Node instaladas:

```bash
node tests/test_onboarding_ui_0430.cjs
RG_PYTHON=/ruta/al/python node tests/test_onboarding_browser_0430.cjs --output out/onboarding-0430
```

El recorrido de navegador requiere Chromium instalado para Playwright; `REPORT_GEN_CHROMIUM=/ruta/a/chromium` permite indicar otro ejecutable compatible. El harness prepara un espacio Flask temporal y conserva `results.json`, `server.log`, capturas y, en caso de fallo, `failure.png`.

La comprobación DOM cubre estados de la interfaz y preferencias, pero no acredita distribución ni pintura. El recorrido de navegador contrasta ES/EN/PT, temas claro y oscuro, anchos de 320, 390, 1366 y 1440 píxeles y texto al 100 % y 200 %. Comprueba controles resaltados, teclado, geometría, reglas de accesibilidad automatizadas, almacenamiento bloqueado o corrupto, persistencia del modo, invariancia del proyecto y práctica con éxito o fallo de guardado.

Las capturas se revisan visualmente además de registrar tamaño y hash. La automatización de accesibilidad no sustituye una sesión humana con lector de pantalla. Una prueba simulada de fallo no acredita todos los errores posibles del almacenamiento o del sistema operativo.

## Regresión y publicación

1. Ejecutar los contratos existentes del tutorial, primer uso, barra lateral e índice contextual, junto a las pruebas pertinentes de práctica y persistencia.
2. Ejecutar los recorridos de edición y exportación requeridos por el repositorio; generar los documentos únicamente con report-gen. Abrir y comprobar las salidas dentro del alcance declarado por cada corpus.
3. Exigir los siete workflows de publicación sobre el mismo commit de `main`: **tests**, **Browser acceptance**, **Windows compatibility**, **macOS compatibility**, **Additional renderer acceptance**, **Reproducible source package** y **R16 trilingual acceptance**.
4. Verificar que el ZIP fuente, su manifiesto y su SHA-256 corresponden a ese árbol de Git. Conservar resultados, incidencias corregidas, capturas y límites de la revisión en la auditoría de la versión.

Los resultados del recorrido didáctico son independientes de los resultados técnicos del informe. Completar seis etapas no demuestra exhaustividad del pentest, calidad editorial, corrección de hallazgos ni preparación de una entrega al cliente.

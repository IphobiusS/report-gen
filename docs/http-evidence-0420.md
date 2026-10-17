# Evidencia HTTP estructurada

La vista **Evidencia y alcance → Evidencias → Evidencia HTTP** conserva una petición y su respuesta como una unidad, con método, URL, versión HTTP, cabeceras ordenadas, cuerpo, identidad/rol observado, procedencia, fecha declarada y fecha de incorporación. La respuesta puede faltar cuando no se capturó. Las URLs son datos: report-gen no envía peticiones a ellas.

## Captura y revisión

Se puede capturar manualmente, importar entradas seleccionadas de un HAR o recibir mensajes seleccionados de Burp mediante la extensión opcional. La evidencia permite vincular varios hallazgos y activos, registrar anotaciones privadas, buscar por título/URL/rol/anotación y comparar A/B para distintos roles o un antes/después. El inspector de hallazgos permite fijar la evidencia mientras se redacta.

El original permanece separado de la copia de publicación. Los cambios ordinarios del proyecto no pueden reemplazar el original de una identidad existente. Para documentar otra observación se crea otra captura; restaurar una versión sigue siendo una operación explícita de historial. Los hashes comprueban consistencia, no autenticidad del emisor.

Para publicar, abre la evidencia, activa **Incluir una copia revisada en el informe técnico**, copia el original si lo necesitas y edita la petición, respuesta y descripción. Retira credenciales y datos que no correspondan al informe. Confirma el contenido exacto antes de guardar. Cualquier edición de esa copia desmarca la confirmación. La copia se incluye en los hallazgos vinculados de la entrega técnica; nunca se publica automáticamente el original, su URL, título, identidad o anotaciones privadas. Las versiones ejecutiva y pública conservan sus propios flujos de redacción y consentimiento.

Los borradores de captura y edición usan la recuperación local existente. Se conservan sin cifrar en el navegador y su estado se muestra en el formulario. Recuperar una copia no la publica ni conserva una aprobación anterior. Una referencia mínima de entrega contiene solo identificador, hash y si la copia técnica se incluyó; permite conservar la trazabilidad de planes de prueba sin revelar el original. Una referencia con contenido reservado no significa que el lector recibió esa prueba.

## Límites y fidelidad

- 500 pares por proyecto; presupuesto HTTP acumulado de 8 MiB.
- 100 entradas y 4 MiB por importación; 200 cabeceras y 256 KiB por cuerpo.
- HAR: vista previa sin escritura y selección explícita. Una respuesta de estado 0 representa ausencia de respuesta. Un cuerpo no capturado no se reconstruye desde parámetros.
- UTF-8 o base64 canónico para cuerpos binarios. Se conservan orden y duplicados de cabeceras; no se promete preservar la trama de transporte ni el espaciado exacto de una captura de paquetes.
- Comparación textual acotada a 128 KiB y 4.000 líneas entre ambos mensajes. Para mensajes mayores se indica el límite y se mantienen disponibles los originales completos dentro del presupuesto de captura. No se deduce automáticamente una vulnerabilidad ni una corrección.
- La vinculación Burp requiere sesión local, CSRF, destino de proyecto/revisión/espacio de trabajo y un token de un uso con 15 minutos de vigencia. Los mensajes siguen siendo privados después de la recepción.

La extensión y sus instrucciones de compilación están en `integrations/burp-report-gen/README.md`. La compilación contra Montoya y las pruebas de transporte están separadas de la aceptación en Burp nativo, pendiente de un entorno con la aplicación instalada.

## Comprobaciones

```sh
python -m pytest tests/test_http_evidence_0420.py -q
node tests/test_http_evidence_0420.cjs
RG_PYTHON=python node tests/test_http_evidence_0420_browser.cjs
```

El último comando requiere Chromium instalado para Playwright. Un guion existente o sintácticamente válido no equivale a una ejecución satisfactoria: el resultado del navegador y las capturas se registran solo cuando realmente se ejecuta.

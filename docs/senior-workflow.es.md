# Flujo de evaluación y revisión en report-gen 0.42.0

[Guía general](guide.es.md) · [English](senior-workflow.en.md) · [Português](senior-workflow.pt.md)

## Revisar sin perder la prueba

Filtra los hallazgos por la tarea que vas a resolver y comienza una sesión de
revisión. La cola conserva las identidades seleccionadas: **Guardar y
siguiente** avanza dentro de esa sesión y muestra tu posición. Puedes fijar
evidencia junto al texto mientras redactas impacto o remediación. Las
preferencias de navegación no reescriben el contenido del informe. La búsqueda
permite llegar a activos, evidencias y comentarios; las selecciones de la tabla
alimentan la comparación de asignaciones por lotes antes de guardar.

Elige un objetivo pequeño para la sesión, por ejemplo revisar los hallazgos de
una API con el responsable técnico. Guarda los cambios del informe y trata los
formularios pendientes como propuestas separadas. Recuperar un formulario no
aplica sus cambios ni recupera un consentimiento anterior.

## Separar las instancias afectadas

Dentro del hallazgo, **Instancias afectadas** registra destino, parámetro,
identidad o rol, entorno, activo, responsable, plazo, evidencia y notas. Cada
instancia tiene su propio historial de retests. No se crean automáticamente a
partir de una lista de activos: debes declarar qué combinación representa una
exposición concreta.

Registra el retest en la instancia evaluada. La fecha, el evaluador y el
resultado observado son obligatorios. Un registro con fecha anterior se conserva
sin sustituir el resultado más reciente; para una misma fecha prevalece el
último registro añadido. El estado general se deriva del conjunto. Quince
instancias corregidas, dos abiertas y una bloqueada siguen mostrando trabajo
pendiente. Una observación general del hallazgo no certifica todos sus destinos.
El límite es 500 instancias por hallazgo, 10.000 por proyecto y 200 retests por
instancia. Los proyectos anteriores sin instancias conservan su comportamiento.

## Capturar HTTP y preparar una copia publicable

**Evidencia HTTP** conserva petición, respuesta, cabeceras, cuerpo y procedencia.
Se pueden importar selecciones HAR o usar la extensión opcional de Burp.
Compara dos registros para revisar roles o un antes/después. El original privado
y la copia publicable tienen comprobaciones de integridad separadas. El hash no
autentica al autor ni convierte una representación estructurada en una captura
de paquetes exacta.

Edita y confirma la copia destinada a la entrega técnica. Revisa especialmente
credenciales, cookies, identificadores y cuerpo; el original no se publica por
aprobar una derivada. Las entregas ejecutivas y públicas no reciben esos cuerpos
automáticamente. Se admiten 100 pares por importación, 500 por proyecto, 200
cabeceras por mensaje y 256 KiB por cuerpo, con límites agregados adicionales.

Para Burp, guarda el proyecto, genera un código de emparejamiento y selecciona
expresamente los mensajes desde su menú contextual. El código caduca y queda
vinculado a la revisión del proyecto. La extensión no recorre todo el historial
ni ejecuta un escaneo. Consulta [compilación, uso y límites](../integrations/burp-report-gen/README.md).

## Documentar cobertura y causalidad

En **Plan de pruebas**, registra metodología y versión, especialidad,
condiciones previas, resultado esperado, resultado observado y relaciones con
activos, hallazgos y evidencias. La matriz rol × organización × operación crea
casos pendientes: no multiplica resultados ni pruebas realizadas. Admite 300
combinaciones por matriz y 3.000 casos por proyecto. Los planes iniciales son
ayudas de autoría, no catálogos oficiales ni certificaciones de cumplimiento.

**Rutas de ataque** relaciona etapas con transiciones declaradas como
demostradas, inferidas o bloqueadas. Una transición demostrada requiere
observación y evidencia vinculada. Explica condiciones, consecuencias y qué
medida interrumpe la ruta. Cada ruta admite 40 etapas y 100 transiciones, sin
ciclos; el proyecto admite 100 rutas. La herramienta comprueba la estructura,
pero no deduce explotación ni causalidad técnica por ti.

## Reconciliar y recibir revisión

Al reimportar resultados, compara las observaciones con los hallazgos existentes
y decide qué vincular o qué campos incorporar. Se conserva la valoración
manual; desaparecer de un escáner no equivale a un retest corregido. Las
observaciones se limitan a 100 por hallazgo, 500 en total y 4 MiB agregados.

Los paquetes de revisión editorial transportan campos seleccionados con su
base. Al recibir cambios, compara original, actual y propuesta antes de aceptar
cada campo. El nombre del revisor es declarado, no una identidad autenticada.
Los perfiles versionados de cliente conservan terminología, secciones exigidas,
criterios y preferencias; aplicarlos requiere revisar sus cambios.

Jira Cloud y DefectDojo permiten vínculos con registros existentes e intercambios
explícitos de campos. Los conectores actuales solo aceptan HTTPS público, no
servidores internos. Sus tokens no se guardan en proyectos ni borradores. El
estado externo informa seguimiento, sin verificar la corrección local. La
revisión editorial opcional con Ollama usa únicamente el texto y pies de
evidencia seleccionados; sus observaciones requieren juicio del autor.

## Comprobar la entrega

Usa **Entregar**, revisa destinatario y contenido, y abre los archivos finales.
El caso [Aster](../qa/aster/README.md) permite repetir un ejercicio extenso en
ES/EN/PT exclusivamente con los exportadores de report-gen. Sus resultados
sintéticos no son una evaluación real. La aceptación nativa en Word requiere
Windows y Word licenciado; el procedimiento existe y su ejecución debe
registrarse aparte. La carga real de la extensión en Burp, las cuentas vivas de
Jira/DefectDojo y la inferencia con un modelo Ollama requieren igualmente su
aceptación de entorno. Las pruebas documentadas no garantizan ausencia universal
de errores ni compatibilidad con cualquier informe posible.

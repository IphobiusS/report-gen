> **Documento histórico.** Este es el README que acompañaba a la entrega 0.25.0, incluidas las referencias de actualización que aún decían 0.24.0. Las instrucciones vigentes están en la [guía de 0.25.0](../guide.es.md) y en la [bienvenida actual](../../README.md). Se ha conservado el contenido; solo se reubicaron sus enlaces.

# report-gen 0.25.0

Convierte tu trabajo de pentesting en un informe claro: organiza hallazgos, conecta evidencias y prepara PDF, Word, Markdown y HTML portátil desde una misma revisión guardada. Trabaja localmente, sin cuentas, telemetría ni servicios externos para editar. Prometeo y Evaristo acompañan el laboratorio.

Puedes documentar alcance y metodología, calcular CVSS 3.1 o 4.0, registrar remediación y retest, conservar versiones y revisar qué compartes antes de entregar. La herramienta organiza tu documentación; la verificación técnica y las conclusiones siguen a cargo del evaluador.

[English](README-0.25.0-original.en.md) · [Cambios y validación](../../VALIDACION-0.25.0.md) · [Seguridad](../../SECURITY.md) · [Contribuir](../../CONTRIBUTING.md)

## Novedades de 0.25.0

La matriz de retest mantiene cada barra junto a su etiqueta y cantidad, también al ampliar el texto o imprimir. La lista de preparación muestra el estado de cada comprobación, un contador y accesos a las pantallas que permiten resolverla. La revisión humana sigue siendo explícita.

La vista previa se ajusta al ancho disponible al abrir un proyecto y permite elegir un zoom manual. El recorrido PDF agrupa los pasos por fase, conserva su alternativa textual completa y continúa cuando hay demasiados pasos o texto largo. Los párrafos que introducen tablas, comandos o figuras permanecen junto al inicio del bloque cuando el espacio lo permite.

La lectura YAML utiliza libyaml cuando puede conservar los contratos de entrada y recurre al cargador Python para sintaxis que requiere compatibilidad. Ambos caminos mantienen los límites de tamaño, nodos, profundidad y expansión, las fechas como texto y el rechazo de claves duplicadas. Las mediciones y sus límites figuran en la validación de esta versión.

`python -m delivery_signature fingerprint --public-key CLAVE.pem` muestra la huella de una clave pública Ed25519 para contrastarla por un canal de confianza. En POSIX, el lanzador reemplaza su proceso por el servidor: las señales terminan ese mismo proceso. La integración continua incorpora las nuevas comprobaciones de interfaz.

## Novedades de 0.24.0

El guardado incremental reutiliza los fragmentos de hallazgos que no cambiaron y evita duplicar su contenido en el historial de proyectos grandes. Un guardado sin cambios verificados no reescribe archivos ni cambia el ETag. Los cambios siguen activándose de forma atómica, con versiones recuperables; `engagement.yaml` continúa siendo un YAML completo que pueden leer los exportadores y otras herramientas.

La mejora se concentra en cambios localizados y guardados sin cambios. Crear el primer historial compuesto o guardar con caché fría puede añadir coste; no se garantiza una reducción de tiempo en cada caso. Las medidas, el coste de metadatos y la memoria observada están en la validación de esta versión.

La firma separada opcional permite verificar una entrega con una clave pública externa que hayas fijado. Vincula los bytes exactos del ZIP y de su manifiesto sin modificar la entrega. Se usa localmente con `python -m delivery_signature`; el editor nunca recibe la clave privada. Consulta [Firma de entregas](../delivery-signing.md) para instalar el extra, generar claves y firmar/verificar. Generar y usar claves privadas requiere POSIX; la edición y las exportaciones normales conservan sus plataformas anteriores.

Para trasladar un proyecto de 0.24.0 a una versión anterior, usa un respaldo exportado por 0.24.0. Ese respaldo conserva el formato portátil v1 y materializa su historial. No copies directamente la carpeta de historial local de un proyecto grande a 0.23.4: esa versión no interpreta los nuevos objetos compuestos. Conserva el origen hasta comprobar la restauración.

## Novedades de 0.23.4

Los errores propios del servidor siguen el idioma de la interfaz, incluidos los mensajes de validación y los trabajos de exportación. El idioma del informe sigue siendo una elección independiente; los códigos, revisiones y controles de seguridad conservan su función.

El PDF en modo máquina añade un Recorrido documentado con los pasos y las referencias de figuras registrados. Las flechas indican orden documental; no prueban causalidad ni explotación exitosa. Los paneles tienen un tamaño acotado y una versión textual completa, por lo que un recorrido largo puede añadir páginas al informe. HTML, Word y Markdown conservan su contenido anterior.

## Novedades de 0.23.3

Dentro de cada hallazgo, las pestañas Evidencia y Decisiones reutilizan los vínculos, afirmaciones y contexto de negocio existentes. Cambiar de pestaña conserva los borradores; leer una vista no guarda ni verifica el hallazgo.

Cambios desde la entrega compara la revisión guardada con una versión marcada localmente como entrega. Muestra la base elegida y su identidad, permite elegir otra y distingue la vista interna de la comparación compartible. Esa marca no prueba una exportación ni la recepción del cliente; retirar un hallazgo tampoco acredita su corrección.

La Matriz de retest resume la última observación válida registrada, con filtros y gráfico numérico. Estado de corrección, verificación técnica y resultado del retest permanecen separados. Si cambia el borrador, guarda explícitamente y vuelve a cargar las vistas.

## Novedades de 0.23.2

Usa `j` y `k` fuera de los campos para recorrer hallazgos y `?` para consultar los atajos. Dentro del editor, `Ctrl+Enter` o `⌘+Enter` guarda y avanza al siguiente hallazgo únicamente si el guardado termina sin conflicto y la selección sigue igual. Las fichas y la tabla muestran activos, responsable, estado y evidencias realmente registrados.

La revisión agrupa los avisos y permite guardar y comprobar el siguiente pendiente. El progreso compara los avisos que dejaron de aparecer durante esta sesión; no acredita una validación técnica. Entregar incorpora una lista calculada desde la revisión guardada para anexos, patrones de posibles secretos y asociaciones de evidencia, con revisión humana obligatoria y aviso cuando cambia el borrador.

Se corrige también la recuperación tras importar o restaurar: un fallo transitorio al limpiar una copia privada podía hacer reaparecer una carpeta temporal y bloquear el respaldo del espacio. La publicación del proyecto y sus snapshots siguen protegidos por sus controles de recuperación.

## Novedades de 0.23.1

Recorre los hallazgos con Anterior/Siguiente en el orden del proyecto, sin volver a la tabla. La preview HTML visible sigue el hallazgo después de cargar usando las identidades de esa revisión; el resaltado queda en la preview y no entra en los documentos exportados. Los paneles ocultos dejan de pedir previews, también en pantallas estrechas. Bienvenida y Acerca de usan un WebP de marca más ligero y sin compresión con pérdida.

La navegación superior, las relaciones de activos, la calculadora CVSS y las acciones de galería se redistribuyen en pantallas estrechas al ampliar el texto al 200 %.

Los nuevos DOCX toman título, evaluador e idioma del informe preparado. Se retiran los comentarios y las fechas heredadas de la plantilla; las fechas de creación desconocidas se omiten.

## Novedades de 0.23.0

**Evidencia y decisiones** reúne seis pantallas opcionales: afirmaciones y límites, contexto de negocio, observaciones y revisión, destinatarios, revisión visual del PDF y ayuda editorial. Las relaciones se basan en tus datos; abrir el espacio no rellena el proyecto. La guía de primer informe sigue disponible.

Las entregas técnica, ejecutiva y pública son archivos independientes. La pública requiere texto aprobado explícito y consentimiento; no hereda el cliente, comandos, evidencias, comentarios ni historial privados. Revisa siempre el plan de inclusión y sus avisos.

Las miniaturas de PDF requieren las dependencias opcionales de vistas previas. La IA permanece apagada hasta que solicitas una propuesta: solo envía los campos elegidos a Ollama en loopback y la aceptación es explícita. Consulta [el flujo, requisitos y límites](../evidence-decisions-0230.md). El trabajo cotidiano no necesita Ollama ni conexión externa.

## Novedades de 0.22.1

El [registro de cambios](../../CHANGELOG.md) incorpora la entrada que faltaba de 0.22.0. La cabecera usa el símbolo SVG desde el arranque; el PNG de marca se conserva y se recomprime sin cambiar sus píxeles. La guía y las correcciones de 0.22.0 siguen disponibles, con su [validación original](../../VALIDACION-0.22.0.md).

## Novedades de 0.22.0

La **Guía: primer informe** explica el recorrido en seis pasos, con ejemplos didácticos y accesos a las pantallas reales. Es opcional y puedes reabrirla desde Inicio, el acceso lateral o **Más**. Leerla y cambiar de paso no completa campos ni valida el pentest. Sirve tanto para una demo como para tu propio proyecto.

Inicio también facilita continuar los hallazgos y añadir uno cuando comienzas un proyecto. Si ya conoces el flujo, puedes trabajar directamente sin recorrer el tutorial.

Los hallazgos nuevos empiezan **Pendientes de valoración**. Clasificación, CVSS y verificación técnica se registran por separado. La aplicación no inventa puntuaciones para completar el informe.

## Instalar y abrir

Ruta prioritaria: Linux/Kali con Python 3.10 o superior. Consulta el registro de validación para los entornos y comprobaciones de esta entrega. Windows y Microsoft Word de escritorio requieren su propia validación.

```bash
# Desde la carpeta que contiene este README
python3 start.py --setup
python3 start.py --diagnose
python3 start.py
```

La instalación crea `.venv`, actualiza su instalador pip (26.2 o posterior de la serie 26), usa `requirements-audited.txt` como restricciones y descarga dependencias de Python. Abre **http://127.0.0.1:8080**. El lanzador también funciona con un entorno ya preparado. Otro puerto: `python3 start.py --port 8081`.

En Debian/Kali, si faltan las bibliotecas de PDF o venv:

```bash
sudo apt install python3-venv python3-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

Chromium es un motor PDF alternativo, opcional:

```bash
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
```

## Primer informe

En Inicio, pulsa **Abrir guía visual** en la tarjeta **¿Es tu primer informe aquí?**. También puedes usar **Guía: primer informe** en el lateral o en **Más** en móvil. Puedes saltar a cualquier paso y volver a consultar la ayuda mientras trabajas.

1. **Empieza.** Usa **Crear proyecto** o **Nuevo proyecto** para elegir diseño e idioma del informe. Si prefieres aprender con contenido preparado, **Probar demo Nimbus** crea una copia editable de un caso ficticio con 12 hallazgos. También puedes abrir un respaldo de tu trabajo.
2. **Define el alcance.** Completa cliente, evaluador, fechas y datos del informe. Documenta objetivos, activos incluidos, exclusiones y limitaciones. Registra **Activos** y **Cobertura** cuando sean útiles para tu evaluación.
3. **Redacta un hallazgo.** Añade una entrada en blanco o abre una existente. Describe qué control falló, qué observaste, cómo reproducirlo, su impacto demostrado y la remediación propuesta. Registra severidad, vector CVSS y verificación técnica cuando puedas sustentarlos.
4. **Conecta la evidencia.** En **Evidencias**, sube la captura, escribe su título y pie y selecciónala bajo **Usada en hallazgos**. Revisa y censura la copia que publicarás. Las notas de Captura rápida permanecen fuera del informe hasta que las incorpores.
5. **Revisa lo que compartes.** En **Revisar**, abre errores, avisos y sus explicaciones; después inspecciona texto e imágenes en el **Inspector de publicación**. Confirma el guardado en disco: un borrador recuperable del navegador es otra protección, no una entrega guardada. Estas comprobaciones detectan omisiones, no confirman vulnerabilidades.
6. **Entrega y conserva.** En **Entregar**, revisa los anexos: carga copias ya redactadas y selecciona los archivos revisados. Elige formatos, genera el paquete y abre **Exportaciones y descargas**. Comprueba archivos y presentación; **Ver comprobaciones** muestra el registro. Puedes seguir editando sin modificar la revisión en cola. Descarga también el **Respaldo del proyecto**: conserva originales y versiones, es privado y distinto del paquete al cliente. Usa **Versiones** para identificar entregas y **Correcciones y retest** para registrar comprobaciones posteriores reales; una corrección comunicada todavía requiere verificación.

CVSS expresa severidad técnica, no el riesgo empresarial por sí solo. **Postura de riesgo e impacto de negocio** y **Recomendaciones estratégicas** permiten documentar el contexto, las prioridades y el apetito de riesgo que acuerdes con la organización. Puedes activar estos apartados desde **Gestionar secciones**. Sus conclusiones las redactas tú; seleccionar un diseño no las calcula ni las aprueba.

**Biblioteca** conserva 22 perfiles de certificación, seis diseños generales, variantes Marca/Sobria y plantillas personales. Todos los perfiles permiten español e inglés. Cambiar apariencia no reemplaza los hallazgos. Word usa Calibri; PDF y HTML emplean Carlito como fuente compatible. Los comandos conservan su monoespaciada.

## Qué comprueba cada entrega

**Ver comprobaciones** muestra revisión, SHA-256, tamaño y controles de cada descarga. HTML, Markdown y Word comparan párrafos, código literal, metadatos, destinos de enlaces y colocaciones de evidencia dentro de su hallazgo, además de tablas y listas. La imagen se compara por su huella pública, pie y contexto precedente. Para código solo se normalizan los finales de línea CRLF/CR a LF; se conservan espacios, tabulaciones, comillas y líneas vacías. Markdown omite el gráfico de severidad y su leyenda de alcance; se registra esa diferencia.

Los IDs existentes, como `F10`, no se renumeran al editar la lista. Los nuevos reciben un identificador no reutilizado. Una referencia interna a un destino inexistente bloquea la publicación y muestra el enlace que hay que corregir. La comparación estática de HTML detecta `hidden`, `display:none`, `visibility:hidden`, opacidad cero y sus ancestros. No certifica geometría, oclusiones ni todos los estados de CSS y JavaScript: todos los formatos requieren revisión visual.

Los enteros del proyecto deben estar entre −9.007.199.254.740.991 y 9.007.199.254.740.991 para conservar su valor al editar en el navegador. Guarda identificadores o valores documentales mayores como texto entre comillas en YAML/JSON. Las entradas que exceden ese rango se rechazan con la ruta del campo; no se redondean ni sustituyen por `null`.

PDF comprueba presencia textual, imágenes y destinos del índice. La extracción puede cambiar orden y espacios: no acredita indentación literal ni asociación de bloques. La ficha lo marca como revisión manual requerida. Ningún formato queda certificado visualmente por estos controles.

En **Informe → Espaciado del informe** puedes elegir cómoda o compacta. Es independiente de la densidad visual del editor. El HTML portátil permite filtrar por tipo, severidad pendiente y texto, y restablecer los filtros.

Los anexos van exclusivamente en el paquete ZIP bajo `anexos/`, con su hash en `verificacion.json`. Se excluyen hasta que los revises y marques. No se censuran ni se limpian sus metadatos: carga copias ya redactadas. Un anexo seleccionado ausente o alterado bloquea la entrega. Declaraciones pendientes y exclusiones aparecen en los avisos. Al marcar **Obligatorio para entregar**, el paquete queda bloqueado hasta incluir una copia revisada e íntegra, incluso si aceptas los avisos.

**Analizar posibles secretos** busca patrones en el primer MiB de textos UTF-8 y cuenta metadatos de imágenes. No realiza OCR ni inspecciona el contenido de PDF. Muestra alcance y límites, sin reproducir los valores detectados. No sustituye la revisión ni cambia los archivos.

## Datos y recuperación

Los proyectos viven en `webapp/projects/`; las bibliotecas personales, en `webapp/library/`. Usa **Respaldo integral** para trasladar proyectos, originales y bibliotecas juntos. Es información privada.

Los borradores pendientes se conservan en IndexedDB, en el perfil del navegador y el mismo origen (host y puerto), durante 30 días. Solo se anuncian como recuperables cuando la escritura termina. No están cifrados por la aplicación. Recuperan datos del proyecto, no los archivos de imagen ni formularios auxiliares aún sin incorporar. El modo privado, borrar los datos del navegador o cambiar de perfil/puerto puede hacerlos inaccesibles. **Más → Descargar borrador privado** permite guardar una copia de emergencia. Recuperarla exige abrir el mismo proyecto y resolver conflictos; nunca sustituye una revisión concurrente sin elegirlo.

**Datos privados guardados** inventaría archivos actuales, originales, historial y anexos retirados. Puedes descargar o eliminar borradores del navegador y limpiar categorías concretas del disco. La limpieza requiere selección y escribir el identificador del proyecto. Conserva los datos actuales y, al limpiar historial, un punto nuevo de recuperación. Las descargas y respaldos externos no se borran desde esta vista.

La censura de texto se aplica a una copia de publicación. La censura de imagen crea una derivada de píxeles; conserva el original privado. Las exportaciones eliminan metadatos de las imágenes. El detector de patrones ayuda a revisar, pero no identifica todos los secretos.

El HTML portátil contiene todo el informe; los filtros y la vista ejecutiva son opciones de lectura, no permisos de acceso. La comparación compartible omite imágenes históricas; la comparación interna puede incluir capturas privadas y no debe entregarse al cliente.

## Actualizar desde una versión anterior

Descomprime 0.24.0 en una carpeta nueva. Crea un respaldo integral con la versión anterior y restáuralo en la instalación nueva vacía. Conserva la carpeta anterior hasta verificar tus proyectos. No copies una `.venv` de otra instalación ni sustituyas tus datos por la demo. Abrir un proyecto no cambia su contenido para adaptarlo a la interfaz.

Si un proyecto antiguo conserva su única revisión previa en `engagement.yaml.bak`, sin historial, el exportador de 0.21.2 omite esa copia. Conserva también una copia completa de `webapp/projects/` y `webapp/library/`. Para trasladar ese estado heredado, copia esos directorios a una instalación nueva de 0.24.0 y genera allí el respaldo: esta versión incorpora la recuperación antigua sin modificar el origen al exportar. Un ZIP antiguo que ya omitió la copia no permite reconstruirla.

Los proyectos anteriores siguen siendo legibles. Los respaldos que contengan el directorio de anexos requieren 0.21.0 o posterior; una versión anterior puede rechazarlos. Los registros de anexos con el campo `required` necesitan 0.21.1 o posterior, aunque su valor sea falso. Desde 0.21.2, el contador `finding_sequence` impide reutilizar números eliminados; no modifica los IDs existentes. Versiones anteriores no conservan esta garantía. Si una edición antigua ya cambió el significado de una referencia, esta versión no puede inferir el destino original: revisa las referencias heredadas.

## Exportar por terminal

```bash
.venv/bin/python export.py webapp/projects/mi-proyecto/engagement.yaml -f html -o informe.html
```

Otros formatos: `pdf`, `docx`, `md` (ZIP con imágenes). Los recursos se procesan localmente.

El ejemplo `examples/pending-severity/engagement.yaml` permite comprobar el resumen con dos hallazgos ficticios confirmados y sin severidad. En Word, las entradas del índice están disponibles desde la exportación; sus números de página se calculan al actualizar los campos en el editor. Si no aparecen o cambias el contenido, selecciona todo con **Ctrl+A** y actualiza con **F9**. El exportador no inventa números a partir de la paginación PDF. LibreOffice y Microsoft Word pueden distribuir el contenido de forma distinta.

Las listas numeradas de los informes admiten ordinales de 0 a 2.147.483.647, compatibles con el navegador y Word. Si una lista supera ese límite, la exportación se detiene y conserva cualquier archivo anterior. Renumera la lista o presenta esos identificadores como texto; no se reduce ni reemplaza su valor en silencio.

## Desarrollo y límites

Los clientes API seleccionan el idioma de error con `X-UI-Language: es` o `en`. Sin ese encabezado, o con otro valor, se conserva el español predeterminado. Las URL abiertas directamente usan ese valor predeterminado; los diagnósticos de bibliotecas y herramientas externas se conservan sin sustituciones. Esto no cambia el idioma ni el contenido del informe.

```bash
.venv/bin/python -m pip install -e '.[dev]'
npm ci
.venv/bin/python -m pytest
npm test
export RG_PYTHON="$PWD/.venv/bin/python"
npm run test:workspace
npx playwright install chromium firefox
export REPORT_GEN_CHROMIUM="$(node -p "require('playwright').chromium.executablePath()")"
.venv/bin/python -m pytest tests/test_portable_report_browser.py
node tests/test_editor_browser_0213.cjs --output out/editor-chromium
node scripts/audit-browser-0210.cjs --browser chromium --output out/browser-chromium
node scripts/audit-browser-0211.cjs --browser chromium --output out/recovery-chromium
node scripts/audit-browser-0212.cjs --project-zip /ruta/Grupo-Ladera-proyecto-editable.zip --output out/ladera-0212
node scripts/audit-browser-0210.cjs --browser firefox --output out/browser-firefox
.venv/bin/python scripts/audit-exports-0210.py --output out/export-audit --stress
```

El editor es de un solo proceso y está limitado a `127.0.0.1`. No lo expongas como servicio multiusuario. Las certificaciones son perfiles de ayuda; consulta las reglas vigentes del proveedor antes de entregar un examen. Los logos pertenecen a sus titulares y no implican afiliación.

El paquete de uso conserva las fuentes, pruebas, demo, diseños y documentación vigente. Las capturas y muestras históricas se distribuyen aparte para reducir el tamaño. [README anterior](README-0.18.md).

El control nativo de Microsoft Word es optativo: `scripts/verify-microsoft-word.ps1` y el workflow manual `word-desktop.yml` requieren Windows con Word instalado. Trabajan sobre copias y no modifican los originales.

## Historial conservado

<details>
<summary>Mejoras de 0.21.3 a 0.21.9</summary>

0.21.9 protege las entradas al exportar: rechaza destinos que coinciden con el YAML de origen o sus recursos locales, incluidos sus alias. Permite sustituir un informe previo que no sea una entrada. Consulta la validación para los contratos y límites de este repaso.

0.21.8 refuerza la conservación del orden de listas y la numeración de Word, las referencias del índice PDF y los extractos de informe. Unifica las entradas de bibliotecas, valida las fechas de seguimiento y usa diálogos nativos para las plantillas. La búsqueda portátil reconoce texto Unicode equivalente. Consulta el registro para las pruebas ejecutadas y los límites de cada formato.

0.21.7 corrige entradas nulas, IDs y anclas codificadas, coherencia del idioma, resúmenes sin detalles, importación de proyectos y recuperación del arranque. Refuerza la comprobación del orden de tablas en HTML, Word y Markdown, el ajuste del HTML portátil y la paginación de tablas largas en Word. Actualiza la dependencia opcional PyMuPDF a la versión corregida. Los contratos ejecutados y sus límites figuran en el registro de validación.

0.21.6 valida las colisiones de anclas antes de exportar y mejora la semántica y la impresión del HTML portátil. Conserva las tablas responsivas de 0.21.5. El registro de validación documenta los contratos de exportación y el informe nuevo generado en esta revisión.

0.21.5 mejora las tablas del HTML portátil: fichas de campo/valor con etiquetas acotadas en escritorio y lectura apilada en móvil; tablas comparativas con desplazamiento local accesible. Conserva el contenido, los filtros, la lectura sin JavaScript y las exportaciones de la misma revisión.

0.21.4 comprueba la coherencia entre severidad y vector CVSS incluso cuando no se ha registrado una puntuación escalar. Rechaza un tema nulo en la entrada validada y conserva el valor por defecto del editor. No asigna ni publica puntuaciones ausentes. También retira dos expresiones regulares sin consumidor y corrige la documentación de CVSS 4.0.

0.21.3 corrige el HTML portátil en pantallas estrechas y la navegación por referencias cuando hay filtros activos. También protege la conservación de imágenes, referencias literales y vectores CVSS en las exportaciones, los respaldos heredados, la reutilización de plantillas y los recorridos de teclado del editor. Conserva los controles de contenido e integridad de 0.21.2. Consulta el registro de validación para los defectos reproducidos, las pruebas ejecutadas y los límites de compatibilidad.

Los contratos ejecutados y sus límites de estas revisiones figuran en [VALIDACION-0.21.9.md](../../VALIDACION-0.21.9.md).

</details>

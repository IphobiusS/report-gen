# Guía de uso de report-gen 0.25.0

[Bienvenida](../README.md) · [English](guide.en.md) · [Cambios](../CHANGELOG.md)

Esta guía reúne la documentación operativa que antes estaba en el README. Todos los comandos se ejecutan desde la raíz del proyecto, donde está `start.py`, salvo indicación contraria. La primera instalación y las descargas opcionales requieren conexión; la edición normal y las exportaciones trabajan localmente.

## Instalar y abrir

Ruta prioritaria: Linux/Kali con Python 3.10 o superior. Windows y Microsoft Word de escritorio requieren su propia validación.

```bash
# Desde la raíz del proyecto (donde está start.py)
python3 start.py --setup
python3 start.py --diagnose
python3 start.py
```

La instalación crea `.venv`, actualiza su instalador pip (26.2 o posterior de la serie 26), usa `requirements-audited.txt` como restricciones y descarga dependencias de Python. Abre **http://127.0.0.1:8080** en el navegador. Revisa los estados de cada motor en el diagnóstico; su código de salida por sí solo no acredita que todos estén disponibles. El lanzador también funciona con un entorno ya preparado. Otro puerto: `python3 start.py --port 8081`.

En Debian/Kali, si faltan las bibliotecas de PDF o venv:

```bash
sudo apt install python3-venv python3-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

Chromium es un motor PDF alternativo, opcional:

```bash
.venv/bin/python -m pip install playwright -c requirements-audited.txt
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

Instala 0.25.0 en una carpeta nueva. Crea un respaldo integral con la versión anterior y restáuralo en la instalación nueva vacía. Conserva la carpeta anterior hasta verificar tus proyectos. No copies una `.venv` de otra instalación ni sustituyas tus datos por la demo. Abrir un proyecto no cambia su contenido para adaptarlo a la interfaz.

Si un proyecto antiguo conserva su única revisión previa en `engagement.yaml.bak`, sin historial, el exportador de 0.21.2 omite esa copia. Conserva también una copia completa de `webapp/projects/` y `webapp/library/`. Para trasladar ese estado heredado, copia esos directorios a una instalación nueva de 0.25.0 y genera allí el respaldo: esta versión incorpora la recuperación antigua sin modificar el origen al exportar. Un ZIP antiguo que ya omitió la copia no permite reconstruirla.

Los proyectos anteriores siguen siendo legibles. Los respaldos que contengan el directorio de anexos requieren 0.21.0 o posterior; una versión anterior puede rechazarlos. Los registros de anexos con el campo `required` necesitan 0.21.1 o posterior, aunque su valor sea falso. Desde 0.21.2, el contador `finding_sequence` impide reutilizar números eliminados; no modifica los IDs existentes. Versiones anteriores no conservan esta garantía. Si una edición antigua ya cambió el significado de una referencia, esta versión no puede inferir el destino original: revisa las referencias heredadas.

## Exportar por terminal

```bash
.venv/bin/python export.py webapp/projects/mi-proyecto/engagement.yaml -f html -o informe.html
```

Otros formatos: `pdf`, `docx`, `md` (ZIP con imágenes). Los recursos se procesan localmente.

El ejemplo `examples/pending-severity/engagement.yaml` permite comprobar el resumen con dos hallazgos ficticios confirmados y sin severidad. En Word, las entradas del índice están disponibles desde la exportación; sus números de página se calculan al actualizar los campos en el editor. Si no aparecen o cambias el contenido, selecciona todo con **Ctrl+A** y actualiza con **F9**. El exportador no inventa números a partir de la paginación PDF. LibreOffice y Microsoft Word pueden distribuir el contenido de forma distinta.

Las listas numeradas de los informes admiten ordinales de 0 a 2.147.483.647, compatibles con el navegador y Word. Si una lista supera ese límite, la exportación se detiene y conserva cualquier archivo anterior. Renumera la lista o presenta esos identificadores como texto; no se reduce ni reemplaza su valor en silencio.

## Desarrollo y límites

Estas pruebas requieren Node.js 22+ y un entorno Python instalado. Ejecuta los comandos desde la raíz del proyecto.

Los clientes API seleccionan el idioma de error con `X-UI-Language: es` o `en`. Sin ese encabezado, o con otro valor, se conserva el español predeterminado. Las URL abiertas directamente usan ese valor predeterminado; los diagnósticos de bibliotecas y herramientas externas se conservan sin sustituciones. Esto no cambia el idioma ni el contenido del informe.

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
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
node scripts/audit-browser-0210.cjs --browser firefox --output out/browser-firefox
.venv/bin/python scripts/audit-exports-0210.py --output out/export-audit --stress
```

### Escenario externo opcional: Grupo Ladera

El siguiente escenario requiere un ZIP de proyecto editable **que no está incluido** en el repositorio. No forma parte del bloque básico anterior. Si dispones de ese fixture, sustituye la ruta por su ubicación real; de lo contrario, omite este comando.

```bash
node scripts/audit-browser-0212.cjs --project-zip /ruta/Grupo-Ladera-proyecto-editable.zip --output out/ladera-0212
```

El editor es de un solo proceso y está limitado a `127.0.0.1`. No lo expongas como servicio multiusuario. Las certificaciones son perfiles de ayuda; consulta las reglas vigentes del proveedor antes de entregar un examen. Los logos pertenecen a sus titulares y no implican afiliación.

El repositorio incluye las fuentes, pruebas, demo, diseños y documentación de uso.

El control nativo de Microsoft Word es optativo: `scripts/verify-microsoft-word.ps1` y el workflow manual `word-desktop.yml` requieren Windows con Word instalado. Trabajan sobre copias y no modifican los originales.

<div align="center">

<img src="webapp/static/brand-mark.png" alt="report-gen" width="360">

# report-gen

**Toolkit local-first para informes de pentesting · v0.18.0.**

Engagements estructurados · PDF / DOCX / Markdown · CVSS 3.1 y 4.0 · Editor visual · Informes reproducibles

</div>

<div align="center">

<img src="docs/evidence-0.18.0/dashboard.png" alt="Inicio de report-gen 0.18.0" width="900">

</div>

---

## Qué es

`report-gen` convierte un engagement de pentest en un informe profesional sin
depender de servicios externos. Cada trabajo es un `engagement.yaml`; el motor
produce el informe completo (portada, secciones, tabla de contenidos, resumen de
hallazgos con gráfico de severidades, hallazgos con CVSS y CWE, máquinas estilo
CTF/OSCP y apéndice de evidencias) en **PDF, DOCX y Markdown** desde una única
fuente. Todo corre en tu máquina, sin marcas de agua y con diseño propio.

## Novedades 0.18.0

- Inicio con pendientes reales y «Continuar informe» desde el último hallazgo y posición.
- Espacio de trabajo más compacto, densidad cómoda/compacta y modo Concentración.
- Símbolo vectorial de Prometeo y Evaristo para la cabecera; la ilustración original se conserva.
- Editor organizado en Descripción, Reproducción, Evidencias y Remediación, con cabecera contextual.
- Vista previa HTML que sigue al hallazgo, ancho ajustable e indicación de revisión desactualizada.
- Importación en tres etapas y panel de exportaciones que permite seguir editando.
- Deshacer eliminaciones y cambios de orden sin descartar otras ediciones; búsqueda de acciones con Ctrl+K.
- Vista Hallazgos con filtros por estado, activo, responsable y verificación, y vistas guardadas.
- Verificación técnica separada de remediación/retest y de la revisión de una importación.
- Bandeja privada de notas, comandos, mensajes HTTP e imágenes, con incorporación explícita al informe.
- Controles nuevos en ES/EN; 22 perfiles y seis diseños generales bilingües conservados.

Lee [VERIFICACION-0.18.0.md](VERIFICACION-0.18.0.md) para el alcance, los resultados y las limitaciones.

### Retomar y organizar el trabajo

«Continuar informe» recuerda el hallazgo por su identificador permanente y la posición
de lectura. El inicio muestra omisiones de la revisión, importaciones pendientes,
correcciones comunicadas sin retest, evidencias registradas sin vincular y capturas pendientes.
Cada aviso lleva al lugar donde resolverlo. El registro de actividad reciente refleja los
hallazgos que se han abierto en este navegador.

«Hallazgos» muestra el listado con filtros y permite guardar hasta 20 vistas por proyecto.
Ctrl+K busca contenido y acciones. «Concentración» oculta la barra lateral en escritorio;
«Densidad» modifica el espaciado del editor. La tipografía del documento no cambia:
Calibri en Word, Carlito en PDF y la fuente monoespaciada existente para comandos.
La vista HTML sigue al hallazgo seleccionado; la vista PDF mantiene su visor habitual.

El botón «Deshacer» revierte la última eliminación o cambio de orden de la sesión,
conservando las otras ediciones. Hay hasta 20 operaciones; al recargar, cambiar de
proyecto o aplicar una operación del servidor se vacía esa pila. Ctrl+Z dentro de un
campo mantiene la edición nativa de texto. El historial guardado continúa disponible.

Posición, vistas, actividad reciente, densidad y ancho de vista previa se guardan en
este navegador. No viajan con el respaldo del proyecto. Los datos del informe, sus
estados, la bandeja y sus originales sí se guardan en el proyecto.

### Capturar durante el trabajo

«Captura rápida» admite notas, comandos, mensajes HTTP y archivos de imagen; también
puedes pegar una imagen en su diálogo. Las entradas se guardan en «Bandeja de captura»
y conservan fecha y SHA-256 del contenido original. Se admiten 500 entradas por proyecto,
128 KiB de texto por entrada y los límites habituales de imágenes de la aplicación.

Selecciona un hallazgo y pulsa «Incorporar al hallazgo» para añadir un paso o vincular una
evidencia. La captura original permanece disponible. Las notas se incorporan como texto
plano, mientras que comandos y HTTP conservan su contenido literal. Los hallazgos de
máquinas reciben el paso en su última fase. Vincular no confirma técnicamente el hallazgo.

La bandeja no aparece en PDF, Word, Markdown ni en la copia fuente de una entrega. Los
respaldos editables y su historial sí incluyen la bandeja y sus originales. «Retirar de la
bandeja» elimina la entrada actual y admite deshacer; no borra copias históricas ni archivos
originales, y no retira del informe algo ya incorporado. Revisa los mensajes HTTP y las
imágenes antes de incorporarlos o compartir un respaldo.

### Registrar la verificación técnica

Un hallazgo puede estar «Sin registrar», «Sin verificar», «Confirmado», «No reproducido»
o «Inconcluso». Es un campo independiente del estado de remediación y de sus retests.
Si lo completas, se refleja en el apartado de seguimiento del informe. Los proyectos
anteriores conservan sus estados y quedan sin verificación técnica registrada; no se
convierte automáticamente «No verificable» en «Sin verificar» ni se supone confirmación.

### Usar la cola de exportación

«Exportar» y «Preparar entrega» añaden una tarea. «Vista y exportación → Exportaciones»
permite volver a la cola, cancelar o descargar. El indicador «Exportaciones» permanece
visible en la cabecera. Puedes cerrar el panel y continuar
editando: la tarea conserva la revisión que tenía al iniciarse. La cola ejecuta una
tarea a la vez y admite ocho tareas activas o pendientes. No muestra porcentajes
estimados. Conserva los resultados durante una hora mientras el servidor siga
abierto. Reiniciar el servidor descarta la cola; los proyectos guardados se conservan.
Cancelar elimina la copia temporal y cualquier resultado parcial. La vista previa
HTML/PDF conserva su flujo independiente.

### Importar hallazgos

En el menú «Proyecto → CSV / Burp XML». Usa UTF-8, hasta 4 MiB y 500 filas. El CSV acepta
coma, punto y coma o tabulador, campos entre comillas y saltos de línea. Asigna
como mínimo título y severidad; puedes mapear objetivo, descripción, impacto,
remediación, CVSS, CWE, referencias e ID de origen. El vector CVSS se valida y
su puntuación se calcula, sin inventar valores ausentes.

Burp debe exportarse como informe XML de issues, no como historial HTTP. Se
conservan ID, confianza, mensajes HTTP y SHA-256 de origen. Las entidades XML
externas no se resuelven. La vista previa nunca modifica el proyecto. Un mismo
título y objetivo, o la huella de una importación previa aunque se haya editado,
se consideran duplicados y se omiten. No se sobrescriben hallazgos existentes.

Los hallazgos nuevos entran con verificación «Sin verificar», remediación «Abierto»
y revisión de importación pendiente. Revisa cada
uno desde «Seguimiento y vínculos → Origen de importación». Marcar la revisión
no confirma la vulnerabilidad ni cambia su estado. La preparación de entrega
bloquea los pendientes; la vista previa sigue disponible. Conserva el respaldo
previo y las nuevas versiones en el historial habitual. Los mensajes HTTP pueden
contener cookies o tokens: revisa el contenido antes de compartirlo.

### Comparar dos entregas

Desde «Versiones», elige el destino y pulsa «Comparar» en la versión de origen.
Se resaltan inserciones y eliminaciones; las imágenes se leen de cada versión,
incluso cuando conservan el mismo nombre. «Descargar comparación HTML» genera
un documento autónomo con imágenes y fuente incluidas. Puedes abrirlo sin
conexión o imprimirlo a PDF con el navegador. Retirar un hallazgo del informe
no se interpreta como haberlo corregido. Se incluye un ejemplo ficticio en
`docs/evidence-0.17.0/comparison.html`.

### Compatibilidad con Windows y Microsoft Word

La automatización de Windows está en `.github/workflows/windows.yml`. Instala
Pango mediante MSYS2 UCRT64 y ejecuta pruebas de API, archivos, cancelación y
Chromium. Este trabajo se validó en Linux; el workflow de Windows aún no fue
ejecutado en un runner Windows.

Para validar con Microsoft Word de escritorio, en un equipo Windows con Word
instalado y desde una sesión interactiva:

```powershell
.\scripts\verify-microsoft-word.ps1 -InputDirectory .\examples\designs-en\offsec-oscp -OutputDirectory .\word-validation-oscp
.\scripts\verify-microsoft-word.ps1 -InputDirectory .\examples\designs-en\htb-cpts -OutputDirectory .\word-validation-cpts
```

El script abre los DOCX como solo lectura, desactiva macros y actualización de
vínculos para esa ejecución, repagina, exporta PDF y registra versión y páginas.
Comprueba que los DOCX originales no cambiaron. Revisa después títulos, tablas,
comandos, imágenes e índice en los PDF. LibreOffice y validación OOXML no
sustituyen esta aceptación en Microsoft Word.

## Características

- **Demo editable en un clic** con Nimbus y diagnóstico real de instalación.
- **Plantillas de hallazgos con editor visual**: campos, pasos, fases, variables,
  vista previa y versiones; el JSON queda como opción avanzada.
- **Preparar entrega**: PDF, Word y Markdown desde una misma revisión guardada,
  con revisión previa y un registro de integridad dentro del ZIP.
- **Seis diseños**: Serio, Corporativo, OffSec, HTB, Ejecutivo y Laboratorio;
  catorce presets de contenido, independientes del aspecto visual.
- **Biblioteca de informes**: 22 perfiles de certificación en variantes Marca y
  Sobria, con logos de OffSec o Hack The Box integrados y plantillas personales.
- **Editor web local** con vista previa en vivo (HTML instantáneo) o PDF real,
  buscador global, arrastrar-para-reordenar y guardado automático.
- **Secciones encendibles** desde un catálogo canónico único; PDF, DOCX y MD
  reflejan siempre las mismas secciones activas.
- **Calculadora CVSS 3.1 y 4.0** por casillas **o pegando el vector completo**
  (detecta la versión y calcula al instante), con severidad y MacroVector en vivo.
- **Autodetección de CWE**: escribes el número o el nombre y lo resuelve.
- **Dos modos de hallazgo**: vulnerabilidad (CVSS, causa raíz, impacto,
  remediación, referencias) y máquina (host, fases, pasos con comando y figura,
  tabla de flags).
- **Exportación consistente** a PDF (WeasyPrint o Chromium), DOCX (`python-docx`
  puro, sin LibreOffice) y Markdown con imágenes incluidas en un ZIP.
- **Guardado con control de versiones**: escritura atómica, detección de conflictos
  entre pestañas y copia de la versión anterior del YAML.
- **Validación antes de exportar**: estructura, CVSS, severidad y recursos locales.
- **Interfaz bilingüe** ES/EN con un clic.

## Inicio rápido

Necesitas Python 3.10 o posterior. Descomprime el paquete y abre una terminal
**dentro de la carpeta `report-gen`**:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell, en lugar de la línea anterior:
# .venv\Scripts\Activate.ps1

python -m pip install -e . -c requirements-audited.txt
python webapp/app.py
```

Abre `http://127.0.0.1:8080` en el navegador. Node.js se necesita únicamente
para ejecutar las pruebas de desarrollo, no para utilizar el editor.

WeasyPrint es el motor PDF predeterminado y necesita sus bibliotecas del sistema.
En Debian/Ubuntu:

```bash
sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libharfbuzz-subset0
```

Si WeasyPrint no puede cargarse, se conserva la alternativa Chromium:

```bash
python -m pip install playwright
python -m playwright install chromium
```

La versión 0.16.0 se ha verificado en Linux con WeasyPrint 70 y Chromium Headless 141.
Se generaron las 50 combinaciones de diseño en inglés en PDF y DOCX. Las muestras
Word OSCP y CPTS incluidas se renderizaron y revisaron con LibreOffice. Windows,
macOS y Microsoft Word no se probaron en esta entrega. Consulta
[VERIFICACION-0.16.0.md](VERIFICACION-0.16.0.md).

## Nuevo en 0.16.0

El inicio muestra el proyecto activo, sus hallazgos, activos, evidencias registradas y
pruebas realizadas. **Informe** abre el editor; **Vista y exportación** agrupa la
vista previa, validación y exportaciones individuales. **Preparar entrega** conserva
el flujo de varios formatos desde una revisión guardada. En móvil, **Navegación**
abre el panel lateral y **Proyecto** contiene la creación de proyectos.

Prometeo y Evaristo estrenan un emblema de consola pixel. El nombre report-gen se
renderiza como texto para conservar su legibilidad. Los informes mantienen Calibri
en Word, Carlito en PDF y código monoespaciado, junto con los logos OffSec y HTB.

La biblioteca contiene 22 perfiles y seis diseños generales. Cada uno permite
crear contenido inicial en español e inglés. Las 50 combinaciones de apariencia
por idioma tienen portada, resumen y página técnica reales: 300 imágenes locales.
El idioma de las muestras se elige en la galería. Las plantillas personales tienen
campos ES y EN independientes. Los textos que escribiste no se traducen automáticamente.
Cambiar **ES / EN** en la cabecera solo cambia la interfaz; el idioma del documento
se elige al crearlo o en los metadatos del informe.

**Respaldo integral** descarga todos los proyectos, originales, historial y bibliotecas
personales. La restauración solo se admite en una instalación vacía: no combina ni
sobrescribe datos. El ZIP no está cifrado y contiene información de trabajo.
Límites: 200 proyectos, 256 MiB de ZIP, 512 MiB expandidos incluyendo ZIP internos,
20.000 entradas. Si el conjunto supera estos límites, usa los respaldos individuales.

Para actualizar, cierra la aplicación, conserva `webapp/projects/` y `webapp/library/`
y sustituye los archivos del programa. El paquete no incluye tus carpetas de datos.
Las versiones anteriores no requieren migración de contenido. Dos muestras inglesas
PDF/Word están en `examples/designs-en/`; el catálogo completo se consulta sin conexión.

## Pruébalo sin preparar datos

1. Pulsa **Probar demo Nimbus** en la bienvenida, o **Proyecto > Probar demo**.
   Se crea una copia independiente de un caso ficticio con doce hallazgos.
2. Sigue los pasos para editar un hallazgo y añadir evidencia. Desde
   **Biblioteca**, crea una plantilla con campos visuales y variables.
3. Pulsa **Preparar entrega**, revisa los avisos y elige los formatos.
   El ZIP contiene los documentos elegidos y su registro de comprobación.

**Comprobar instalación** prueba escritura local, ambos motores PDF y la
generación de Word con documentos desechables. Si falta un motor, muestra
el motivo; Chromium es una alternativa opcional, no un requisito para Word.

La entrega y el respaldo cumplen funciones distintas: **Respaldo del proyecto**
conserva el YAML, originales e historial para continuar editando. **Preparar
entrega** incluye solo las salidas seleccionadas, los recursos del Markdown y
el registro. Una entrega fallida no descarga un ZIP parcial ni marca el proyecto
como entregado. Revisa los documentos antes de enviarlos al cliente.

## Elegir un diseño

**Biblioteca de informes** reúne 22 perfiles OffSec y HTB en variantes Marca y
Sobria, vistas previas reales y plantillas personales. Crear desde un perfil añade
su estructura; aplicar apariencia conserva todo el contenido del informe. Consulta
[la biblioteca 0.15.0](docs/BIBLIOTECA-0.15.0.md) para el catálogo y sus referencias.

Desde 0.15.1, cada perfil incorpora el logo de su proveedor en la portada PDF,
Word y la galería. Se elige una versión legible sobre el fondo del diseño;
los archivos están incluidos y funcionan sin conexión. Los logos propios de
autor y cliente mantienen sus campos independientes. Una plantilla personal
conserva el proveedor de su perfil original, incluso después de borrar su
entrada de biblioteca. Las fuentes de los recursos y sus adaptaciones están
en `exporters/branding/NOTICE.md` y `sources.json`.


Para clientes, recomiendo **Ejecutivo** si buscas una portada editorial sobria,
o **Corporativo** para una presentación convencional. **Laboratorio** ofrece
un cuaderno técnico claro y apto para imprimir; **HTB** conserva su estilo oscuro
para lectura digital. **OffSec** y **Serio** siguen disponibles.

El aspecto visual se cambia en **Informe → Tema**. El preset decide las
secciones iniciales al crear el proyecto; cambiar el tema no reescribe contenido.
Los diseños son propios y no acreditan cumplimiento de requisitos de examen.
Las portadas de 0.14.1 separan marca, título central y datos en el tercio inferior.
La tipografía de portada es Calibri en Word y Carlito incrustada en PDF;
los comandos conservan fuente monoespaciada. Consulta
[docs/DISENOS-0.14.1.md](docs/DISENOS-0.14.1.md) para comparar los diseños.
La revisión de los catorce presets permanece en
[docs/DISENOS-0.14.0.md](docs/DISENOS-0.14.0.md).

## Actualizar sin perder proyectos

1. Cierra el servidor antiguo y conserva una copia de su carpeta completa.
2. Descomprime esta versión en una carpeta nueva.
3. Copia `webapp/projects/` de tu instalación anterior al mismo lugar en la nueva.
   Copia también `webapp/library/` si existe: contiene tus bibliotecas de hallazgos y diseños.
   Si tienes informes propios en `reports/`, copia también esas carpetas y sus imágenes.
4. Instala las dependencias con `python -m pip install -e . -c requirements-audited.txt` y arranca el editor.
5. Recarga la pestaña del navegador para obtener el nuevo código y la sesión local.
   Abre un proyecto, pulsa **Validar** y genera un informe de prueba.

El formato YAML se conserva. Los borradores pueden contener datos incompletos,
pero una estructura mal formada se rechaza antes de escribirla. Los errores de
CVSS y de validación bloquean la exportación final, sin cambiar el informe guardado.

Cada guardado conserva versiones del proyecto con sus imágenes. En **Versiones**
puedes nombrar borradores, entregas y retests, compararlos y restaurarlos. Los
respaldos editables incluyen el YAML, imágenes, originales, configuración e historial.
La biblioteca global de plantillas se guarda en `webapp/library/`: cópiala también
al actualizar. Ante un conflicto entre pestañas se conserva la edición en memoria.

## Historial: reauditoría y correcciones de 0.13.5

La auditoría sobre el ZIP exacto 0.13.4 confirmó seis grupos adicionales de fallos.
La batería anterior pasaba; no demostraba los contratos ahora comprobados.

- Recuperación de guardados y restauraciones interrumpidos entre renombrados.
  Un registro privado permite reponer el estado anterior o conservar el nuevo
  al acceder de nuevo al editor. Si la recuperación falla, conserva las copias.
- La censura cambia destinos de imagen y enlaces a ella; preserva comandos,
  texto, nombres y pies, incluso dentro de citas y listas Markdown anidadas.
- Revisión de imágenes por el parser real, incluyendo referencias Markdown;
  los ejemplos de código no se confunden con recursos y las imágenes remotas
  bloquean la exportación en lugar de desaparecer silenciosamente.
- Validación de campos usados por los exportadores y compatibilidad de Word
  con valores numéricos de presentación y campos opcionales nulos.
- El cambio de idioma del informe queda bloqueado durante cambios de proyecto.
- Markdown conserva barras verticales y caracteres de formato en títulos y
  tablas, sin truncar columnas ni interpretar texto plano como instrucciones. Las tablas
  estructuradas de Word también conservan literalmente esos caracteres.

Consulta [VERIFICACION-0.13.5.md](VERIFICACION-0.13.5.md) y su PDF. Se incluyen
reproducciones antes/después y pruebas de terminación real del proceso. La
recuperación automática solo cubre transacciones con el registro de 0.13.5:
no intenta adivinar el proyecto al que pertenecen temporales de versiones antiguas.
No se acredita resistencia a cortes eléctricos, fallo del dispositivo ni edición
simultánea por varios procesos. No es una certificación de ausencia de defectos.

## Historial: reauditoría de 0.13.4

El aval general anterior a 0.13.3 fue demasiado amplio. Esta revisión corrige fallos
reproducidos de persistencia, navegación y fidelidad del documento:

- Guardado del conjunto completo de YAML, imágenes e historial con recuperación
  ante errores de escritura o activación.
- Rechazo de un YAML serializado que el propio lector no podría volver a abrir.
- Navegación bloqueada durante eliminación y restauración pendientes para conservar borradores.
- Imágenes Markdown por referencia y código literal tratados por el mismo parser.
- Vector CVSS nulo compatible con DOCX; rechazo explícito de controles incompatibles.
- Presupuesto de nodos YAML aplicado durante la composición.

Consulta **[VERIFICACION-0.13.4.md](VERIFICACION-0.13.4.md)**: 293 pruebas Python,
5 JavaScript y 75 comprobaciones en Chromium. Incluye fallos reproducidos, una
expectativa antigua de test corregida y límites del dictamen. No es una certificación.

Las transacciones requieren espacio adicional, especialmente si el sistema no admite
enlaces internos. Si falla la limpieza después de confirmar un guardado, se registra
un aviso y se conserva una copia privada para retirarla después. En 0.13.4 no había
recuperación automática entre renombrados; 0.13.5 incorpora un registro para
interrupciones del proceso, con los límites indicados arriba.

## Historial: correcciones de 0.13.3

- La censura actualiza todas las referencias a la misma imagen, incluidos nombres
  con espacios, rutas relativas equivalentes y URLs codificadas. La imagen previa
  sale del conjunto de entrega; los originales e historial siguen en el respaldo privado.
- Versiones y respaldos conservan logos y diagramas referenciados fuera de `img/`.
  La vista previa admite esos recursos mediante una ruta que solo sirve imágenes del proyecto.
- JSON/YAML rechaza claves duplicadas, ciclos, números no finitos y estructuras
  excesivas antes de guardar. Las fechas ISO y los alias YAML pequeños conservan
  su contenido; las filas aliadas reciben identidades independientes.
- Los nombres de archivo con porcentajes se decodifican una sola vez.
- Cabeceras de origen malformadas y tokens CSRF no ASCII devuelven 403, sin errores 500.
- Arranque WSGI con Waitress, manteniendo el editor local y monousuario.

Los límites de documentos son 12 MiB de entrada, 64 niveles, 250.000 nodos
expandidos y 16 MiB de texto expandido. La biblioteca se valida antes de crecer
más allá de su límite de lectura. Los ZIP mantienen los límites de 256 MiB
comprimidos, 512 MiB expandidos y 20.000 archivos.

`requirements-audited.txt` fija las versiones de producción de la instantánea del
2026-10-03. Es una instantánea reproducible de Python 3.12 / Linux; se debe revisar
cuando aparezcan nuevas versiones o avisos. El paquete no incluye un entorno virtual.

Actualiza conservando `webapp/projects/` y `webapp/library/`. Un respaldo antiguo
que ya omitió una imagen no puede reconstruirla: recupera ese archivo de la
carpeta original. Si un YAML tiene claves repetidas, corrígelo explícitamente;
esta versión rechaza la ambigüedad en vez de decidir qué contenido descartar.

## Correcciones de 0.13.2

- Markdown conserva el rol, OSID, correo y recursos gráficos de la portada.
- Los pies con corchetes y los nombres de imagen con espacios se exportan sin
  perder recursos ni cambiar el nombre real dentro del ZIP.
- Los comandos con cercas de backticks se conservan como un solo bloque de código.
- Los hallazgos antiguos sin `mode` usan el mismo comportamiento de vulnerabilidad
  en las figuras y en la plantilla PDF clásica.
- El gráfico de Word respeta ES/EN, con texto más legible y una fuente incluida
  que reproduce los acentos. Los encabezados de listas y los plazos de remediación
  permanecen junto a su contenido.

## Correcciones de 0.13.1

- Exportaciones protegidas ante fallos y cambios simultáneos de imágenes.
- Referencias de evidencia precisas y validación final más estricta de IDs y CVSS.
- Tablas Markdown legibles, contraste de severidades y retests mejor agrupados.
- Word admite WebP, logos e ilustración de portada; ajusta las figuras verticales
  y usa texto oscuro en el cuerpo del tema HTB para lectura sobre papel.
- Logo completo, controles adaptables, foco visible y vista previa sin respuestas
  antiguas que sustituyan el proyecto actual.

## Nuevas funciones de 0.13.0

- Historial completo con comparación y restauración de imágenes.
- Revisión de entrega con navegación al campo que requiere atención.
- Responsables, fechas, estados y comprobaciones de retest con nuevas evidencias.
- Galería compartida entre hallazgos, anotaciones y censura incorporada a los píxeles.
- Múltiples activos por hallazgo, cobertura de pruebas y limitaciones.
- Biblioteca local con etiquetas, variables, versiones e importación/exportación.
- Referencias permanentes independientes de los números F1, F2, etc.
- Respaldo e importación de proyectos editables completos.

Consulta **[GUIA-0.13.0.md](GUIA-0.13.0.md)** para usarlas y actualizar sin perder datos.
Para probarlas, importa `examples/workflow-demo-project.zip` desde **Abrir respaldo**.
El ejemplo contiene únicamente datos ficticios.

## Corrección de CVSS

report-gen no solo "tiene una calculadora": el motor CVSS se valida contra los
vectores y recursos de referencia de **FIRST** y contra la implementación
**RedHatProductSecurity/cvss** (ejecutada sin modificar).

**CVSS 3.1**
- ✓ Vectores oficiales de FIRST
- ✓ Paridad Python ↔ JavaScript sobre 2.592 combinaciones de métricas Base

**CVSS 4.0**
- ✓ Parser canónico estricto
- ✓ MacroVector EQ1–EQ6 + interpolación de score
- ✓ 270/270 MacroVectors representados
- ✓ Paridad Python ↔ JavaScript en score y MacroVector
- ✓ 20.087 vectores contra `RedHatProductSecurity/cvss` v3.6, ejecutado sin modificar
- ✓ 0 divergencias de score

La historia completa (procedencia, sello y reproducción) está en
[`docs/CVSS40.md`](docs/CVSS40.md).

## Por qué está construido así

- **Engagement estructurado.** Un `engagement.yaml` es la única fuente de verdad;
  el informe es una proyección de esos datos, no un documento que se edita a mano.
- **Exporters desde una fuente común.** `engine.py` (HTML→PDF), `exporters/docx.py`
  y `exporters/markdown.py` recorren la misma estructura de secciones, así que los
  tres formatos coinciden en secciones y contenido (motores de render distintos).
- **Validación.** `validate.py` detecta severidades inválidas,
  IDs duplicados, vectores CVSS mal formados y desajustes entre vector, puntuación y severidad antes de
  exportar. Una puntuación de 0 es válida y se conserva.
- **CVSS con frontera de versiones.** El paquete `cvss/` separa 3.1 y 4.0 y
  despacha por versión; el motor 4.0 está congelado y sellado contra la referencia.

## Demo

<div align="center">
<img src="docs/img/report-example.png" alt="Página de un informe generado" width="440">
</div>

Genera el informe de ejemplo en los tres formatos:

    python engine.py reports/canon/engagement.yaml -o out/informe.pdf
    python export.py reports/canon/engagement.yaml -f docx -o out/informe.docx
    python export.py reports/canon/engagement.yaml -f md   -o out/informe.zip

## Arquitectura

    engine.py            YAML + Markdown -> Jinja2 -> WeasyPrint/Chromium -> PDF
    export.py            fachada de exportación
    exporters/           markdown.py, docx.py, richtext.py, pdf.py, common.py
    safe_markup.py       Markdown saneado y contexto de imágenes por petición
    resources.py         política de imágenes locales y recursos PDF
    storage.py           escritura atómica, copia anterior y revisión del YAML
    delivery.py          instantánea y paquete de entrega con comprobaciones
    diagnostics.py       pruebas locales de escritura y motores de exportación
    cvss/                v31, v40 (+ lookup/constants), dispatch por version
    validate.py          validación de estructura, campos y coherencia CVSS
    sections.py          catalogo canonico de secciones
    designs/             report_sections.yaml (catalogo)
    templates/ themes/   Jinja2 + CSS (seis diseños PDF y paletas Word)
    lang/                paquetes de idioma es / en
    wizard.py            asistente CLI para nuevos engagements
    webapp/              editor local (Flask): app.py, static/ (app.js, cvss40.js)
    tests/               suite pytest + pruebas Node y corpus de referencia CVSS

## CLI / uso avanzado

    # asistente guiado
    python wizard.py

    # render directo con backend explícito y tema
    python engine.py reports/canon/engagement.yaml -o out/r.pdf --backend chromium

El formato del `engagement.yaml` (meta, secciones, hallazgos vuln/machine) está
documentado en los ejemplos de `reports/`.

## Pruebas de desarrollo

Con Node.js 22 o posterior y el entorno Python activado, desde la raíz:

```bash
python -m pip install -e ".[dev]"
npm ci --ignore-scripts
python -m pytest -q
npm test
ruff check .
```

La suite comprueba CVSS, API, saneado, aislamiento de recursos, integridad del
YAML, exportaciones reales y el editor completo con una API HTTP local y un DOM
simulado mediante jsdom. El archivo `tests/run_stdlib.py` se conserva como entrada
de compatibilidad, pero ahora ejecuta pytest: ya no anuncia soporte sin pytest.
GitHub Actions instala las dependencias y ejecuta los tres comandos de comprobación.

Consulta [VERIFICACION-0.15.1.md](VERIFICACION-0.15.1.md) para los fallos corregidos,
los resultados, los comandos de reproducción y los límites de esta entrega.

## Paginación de hallazgos

Los hallazgos se distribuyen de forma continua: dos o más pueden compartir una
página si hay espacio. El encabezado y la tabla principal se mantienen unidos;
las tablas de los hallazgos se desplazan completas a la página siguiente cuando
no caben en el espacio restante. Los procedimientos largos pueden continuar en
otra página. La fuente y los márgenes conservan su tamaño.

En PDF se comprueba la paginación antes de escribir la salida. Si una tabla es
más alta que una página disponible, la exportación se detiene y muestra el ID del
hallazgo. En ese caso, resume la tabla y mueve las explicaciones extensas al
**Procedimiento detallado**, o reorganiza su contenido en tablas más pequeñas.

En DOCX se eliminan los saltos entre hallazgos y se aplican propiedades de Word
para conservar cada tabla completa y sus filas sin cortar. La tabla debe caber
en una página: Word y LibreOffice pueden ignorar esas propiedades si es más alta
que la página. El PDF es la salida con comprobación y bloqueo de ese caso límite.

## Markdown e imágenes

El Markdown admite negrita, cursiva, enlaces, listas, tablas, código y figuras.
El HTML crudo se conserva como texto literal, útil para documentar payloads;
no permite ejecutar scripts ni introducir atributos de eventos.

Las imágenes deben pertenecer al proyecto y usar rutas relativas, por ejemplo
`![Evidencia](img/captura.png){width="70%"}`. Se admiten PNG, JPEG, GIF y WebP.
Las imágenes remotas y las rutas fuera del proyecto no se cargan. Sube la captura
al editor para insertarla. Una referencia local válida cuyo archivo falte produce
un error de exportación, en vez de un informe final incompleto.

`-f md` y el botón Markdown producen ahora un ZIP con `report.md` y las imágenes
referenciadas. Este cambio es intencional: si automatizabas una salida `.md`,
adapta el consumidor para descomprimir el ZIP. La función Python
`to_markdown(data, meta, L, engagement_dir)` sigue devolviendo texto.

## API local

El editor administra estos controles automáticamente. Si tienes un cliente propio:

1. Haz `GET /api/session`, conserva la cookie y el campo `csrf`.
2. Envía `X-CSRF-Token` en las peticiones POST, PUT y DELETE.
3. Envía JSON con `Content-Type: application/json`, excepto las imágenes multipart.
4. Para guardar, eliminar o restaurar, lee primero el proyecto y conserva su `ETag`.
   Envíalo como `If-Match`; un conflicto devuelve 409 y una revisión ausente, 428.

Los errores de estructura o exportación inválida devuelven 422; un token u origen
inválidos, 403. Solo se aceptan nombres de host locales. Las exportaciones usan
una instantánea temporal y no escriben sobre `engagement.yaml`.

## Modelo de uso y límites

Herramienta local y monousuario: se sirve con Waitress en `127.0.0.1`, con un proceso y cuatro hilos.
El arranque habitual ya no usa el servidor de desarrollo de Flask.
Las comprobaciones de host, origen y CSRF protegen la API frente a peticiones
web ajenas; **no constituyen un sistema de usuarios o permisos** para un servicio
público. No se ha añadido cifrado de proyectos ni colaboración remota.

El HTML del contenido se sanea, la vista previa del informe usa un iframe con
`sandbox` y el render PDF restringe los recursos a los archivos permitidos.
Las plantillas, temas y código de la instalación son componentes de confianza.

Los tres formatos mantienen sus motores de composición: Word puede paginar de
forma diferente al PDF y no reproduce todas las reglas CSS. El aspecto también
depende de las fuentes disponibles. La verificación incluye muestras concretas;
no equivale a una garantía de ausencia de errores para cualquier entrada.

## Inspiración

La interfaz de edición se inspira en el flujo de herramientas como SysReptor
(encender secciones y editarlas en el navegador), con un motor, un diseño y una
base de código propios.

## Licencia

MIT. Isotipo: Prometeo y Evaristo.

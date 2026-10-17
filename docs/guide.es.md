# Guía de uso de report-gen 0.42.0

[Bienvenida](../README.md) · [English](guide.en.md) · [Português (Brasil)](guide.pt.md) · [Cambios](../CHANGELOG.md)

Todos los comandos se ejecutan desde la raíz del proyecto, donde está `start.py`, salvo indicación contraria. La primera instalación y las descargas opcionales requieren conexión; la edición normal y las exportaciones trabajan localmente.

## Trabajo de evaluación en 0.42.0

Consulta el [recorrido de revisión, instancias, HTTP, planes, rutas e integraciones](senior-workflow.es.md). Incluye decisiones de publicación, límites de los módulos y verificaciones de entorno que se acreditan por separado.

## Instalar y abrir

Ruta prioritaria: Linux/Kali con Python 3.11 o superior. Las pruebas de compatibilidad de Windows no sustituyen la revisión de documentos en Microsoft Word de escritorio.

Descarga y descomprime el ZIP de la [última Release](https://github.com/IphobiusS/report-gen/releases/latest). Desde su carpeta:

```bash
python3 scripts/install.py --desktop
~/.local/bin/report-gen
```

El primer comando instala las dependencias en `.venv` con las restricciones auditadas y crea `~/.local/bin/report-gen`. `--desktop` añade también un acceso al menú de aplicaciones que abre una terminal. La instalación necesita conexión, Python 3.11+ y soporte para venv; no usa `sudo` ni instala paquetes del sistema. No es un ejecutable autónomo: conserva la carpeta descomprimida y `.venv`. El acceso apunta a esa ubicación y al espacio de trabajo elegido; abrirlo después no reinstala ni descarga dependencias. Si mueves la aplicación, vuelve a ejecutar el instalador desde su nueva ubicación.

El instalador elige `--workspace` si lo proporcionas, después `REPORT_GEN_WORKSPACE`, y por último `$XDG_DATA_HOME/report-gen` o `~/.local/share/report-gen`. Por ejemplo, `python3 scripts/install.py --desktop --workspace /ruta/datos` prepara una carpeta externa concreta. No mueve datos heredados automáticamente: consulta la migración antes de interpretar una lista vacía como pérdida de proyectos.

También sigue disponible `python3 start.py --ready`. Sin `--workspace` ni variable de entorno, este arranque conserva la ubicación tradicional `webapp/`. `--ready` autoriza la instalación de dependencias si el entorno local falta o está incompleto, ejecuta el diagnóstico y arranca el editor si sus requisitos están disponibles. La instalación crea `.venv`, actualiza pip y usa `requirements-audited.txt` como restricciones. Abre **http://127.0.0.1:8080** en el navegador; `Ctrl+C` detiene el servidor. Otro puerto: `python3 start.py --ready --port 8081`.

El diagnóstico distingue el editor de cada motor de exportación. Puedes editar aunque falte un motor opcional; no presupongas que todos los formatos están disponibles por haber abierto el editor. Si se detiene la preparación, sigue el mensaje y corrige la dependencia indicada antes de repetirla.

| Necesidad | Comando |
| --- | --- |
| Instalar con acceso al menú, sin arrancar | `python3 scripts/install.py --desktop` |
| Abrir la instalación preparada | `~/.local/bin/report-gen` |
| Preparar, comprobar y abrir | `python3 start.py --ready` |
| Reinstalar dependencias y terminar | `python3 start.py --setup` |
| Consultar el diagnóstico sin instalar ni arrancar | `python3 start.py --diagnose` |
| Arrancar con el entorno ya preparado, sin instalar | `python3 start.py` |

Añade `--lang en` para mensajes del lanzador y el idioma inicial de la interfaz en inglés. Si el navegador ya tiene una preferencia de idioma, se conserva; puedes cambiarla desde el editor. El idioma del informe es independiente. **Node.js no es necesario para el uso normal.**

Al recargar, las etiquetas del Inspector de publicación, Mostrar/Ocultar vista previa y el nombre accesible de Validar informe se restauran en el idioma elegido. Cambiarlo no traduce el contenido escrito ni cambia la revisión guardada del proyecto.

Los selectores de proyecto y formato conservan su funcionamiento nativo y siguen el esquema oscuro o claro del editor. Esto corrige el texto claro sobre fondo claro observado en WebKit para Linux. La comprobación abarca el control cerrado, con y sin foco; la apariencia del menú desplegado depende del navegador y del sistema operativo.

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

En Inicio, elige **Probar demo Nimbus** o **Crear mi proyecto**. Con un proyecto abierto, la tarjeta **Siguiente acción sugerida** propone un paso según el título y cliente, objetivos de alcance, hallazgos, asociaciones de evidencia y resultados reales de la última revisión guardada. **Ver este paso en la guía** abre su explicación. También puedes abrir **Tutorial visual** desde **Más**, tanto en escritorio como en móvil y consultar cualquiera de sus seis pasos.

El primer acceso muestra una invitación opcional: **Empezar recorrido** o **Ahora no**. El tutorial tiene capturas reales de datos ficticios en español, inglés y portugués de Brasil y controles para ampliarlas o verlas a tamaño real. **Escape** cierra la captura y devuelve el foco al botón que la abrió. Conserva el paso consultado en este navegador; **Reiniciar recorrido** solo reinicia ese progreso, sin cambiar proyectos. Si el almacenamiento está bloqueado, el recorrido sigue funcionando durante la sesión. No envía las capturas a un servicio externo.

La sugerencia orienta la escritura, sin exigir que inventes un hallazgo o una captura: puedes ir directamente a la revisión cuando una recomendación no corresponda a tu evaluación. Una revisión sin avisos sugiere preparar la entrega, pero no aprueba su contenido. Si cambias el borrador después de revisarlo, repite la revisión guardada antes de entregar.

1. **Empieza.** Usa **Crear mi proyecto** o **Nuevo proyecto** para abrir la galería. Elige una plantilla, compara sus muestras y continúa para completar título, cliente, carpeta e idioma del informe. Puedes volver a la galería sin perder esos datos. Si prefieres aprender con contenido preparado, **Probar demo Nimbus** crea una copia editable de un caso ficticio con 12 hallazgos. También puedes abrir un respaldo de tu trabajo.
2. **Define el alcance.** Completa cliente, evaluador, fechas y datos del informe. Documenta objetivos, activos incluidos, exclusiones y limitaciones. Registra **Activos** y **Cobertura** cuando sean útiles para tu evaluación.
3. **Redacta un hallazgo.** Añade una entrada en blanco o abre una existente. Describe qué control falló, qué observaste, cómo reproducirlo, su impacto demostrado y la remediación propuesta. Registra severidad, vector CVSS y verificación técnica cuando puedas sustentarlos.
4. **Conecta la evidencia.** En **Evidencias**, sube la captura, escribe su título y pie y selecciónala bajo **Usada en hallazgos**. Revisa y censura la copia que publicarás. Las notas de Captura rápida permanecen fuera del informe hasta que las incorpores.
5. **Revisa lo que compartes.** En **Revisar**, abre errores, avisos y sus explicaciones; después inspecciona texto e imágenes en el **Inspector de publicación**. Confirma el guardado en disco: un borrador recuperable del navegador es otra protección, no una entrega guardada. Estas comprobaciones detectan omisiones, no confirman vulnerabilidades.
6. **Entrega y conserva.** En **Entregar**, revisa los anexos: carga copias ya redactadas y selecciona los archivos revisados. Elige formatos, genera el paquete y abre **Exportaciones y descargas**. Comprueba archivos y presentación; **Ver comprobaciones** muestra el registro. Puedes seguir editando sin modificar la revisión en cola. Descarga también el **Respaldo del proyecto**: conserva originales y versiones, es privado y distinto del paquete al cliente. Usa **Versiones** para identificar entregas y **Correcciones y retest** para registrar comprobaciones posteriores reales; una corrección comunicada todavía requiere verificación.

CVSS expresa severidad técnica, no el riesgo empresarial por sí solo. **Postura de riesgo e impacto de negocio** y **Recomendaciones estratégicas** permiten documentar el contexto, las prioridades y el apetito de riesgo que acuerdes con la organización. Puedes activar estos apartados desde **Gestionar secciones**. Sus conclusiones las redactas tú; seleccionar un diseño no las calcula ni las aprueba.

**Biblioteca** recomienda Serio como punto de partida general. Compara la misma página de muestra: portada, resumen o página técnica. La galería reúne seis diseños generales, 26 perfiles de certificación y práctica, cuatro estructuras empresariales y tus plantillas personales. Filtra por propósito o proveedor, busca por nombre y compara las variantes Marca/Sobria. **Enterprise Control Review** añade una composición editorial y ocho apartados sobre diseño y operación de controles, muestreo, excepciones y retest. Si tu proyecto ya tiene un diseño especializado, la biblioteca abre ese contexto; navegar no cambia su apariencia. La apariencia y la estructura inicial son elecciones distintas; cambiar un preset no sustituye el diseño elegido.

Todos los perfiles permiten español, inglés y portugués de Brasil. Cambiar apariencia no reemplaza los hallazgos. Word usa Calibri; PDF y HTML emplean Carlito como fuente compatible. Los comandos conservan su monoespaciada.

La exportación PDF predeterminada con WeasyPrint detecta caracteres sin glifo en las fuentes disponibles y detiene la entrega antes de sustituir la salida anterior. El error identifica códigos como `U+1F3E6`: instala una fuente que contenga esos caracteres o corrige el texto y vuelve a exportar. La presencia de texto extraíble no demuestra que el símbolo se vea correctamente. Esta comprobación no certifica fuentes ni composición visual del motor Chromium opcional.

En páginas con mapas de fuentes personalizados o texto de derecha a izquierda, el lector sólo recupera un guion ASCII de final de línea cuando los códigos y mapas explícitos del PDF y un segundo lector concuerdan carácter por carácter. Un guion blando, un mapa no admitido o una lectura divergente aún pueden resultar ambiguos. Si aparece ese error específico, la entrega se detiene sin sustituir el archivo anterior: ajusta ese salto o usa otro formato y revisa el resultado. El verificador no inventa el carácter que falta.

En Inicio, **Más herramientas del proyecto** reúne controles menos frecuentes. Las herramientas globales y el índice de contenido se describen a continuación.

<a id="navegación-lateral-en-0390"></a>

## Navegación lateral en 0.40.0

La barra izquierda reúne herramientas en cinco grupos estables. Las listas de contenido están en un **Índice** separado, junto al editor: recorrer una lista extensa no alarga la navegación global.

| Grupo | Contenido |
| --- | --- |
| **01 Proyecto** | Inicio y datos generales del informe. |
| **02 Contenido** | **Hallazgos** abre el tablero; **Secciones del informe** y **Lista de hallazgos** abren el índice correspondiente. |
| **03 Evidencia y alcance** | Evidencias, bandeja de captura, activos y cobertura. |
| **04 Análisis y seguimiento** | Causas raíz, tareas de remediación, correcciones y retest, cambios desde la entrega, matriz de retest y versiones. |
| **05 Entrega** | Revisión de entrega, respaldo del proyecto y **Herramientas**. |

En las vistas del informe, secciones, hallazgos y tablero, usa **Índice** para abrir el panel y **Cerrar índice** para plegarlo. Sus pestañas **Secciones** y **Hallazgos** cambian la lista, sin cambiar la ficha abierta. Busca por ID o título y, para hallazgos, filtra por **Severidad** o **Tipo**. La lista conserva el orden del proyecto y muestra hasta 50 entradas por página. Buscar, filtrar o cambiar de página no reordena ni edita el informe.

Si la selección actual queda fuera del filtro, el panel lo indica y ofrece **Mostrar selección**. La ficha abierta permanece en el editor hasta que elijas otra. Cada lista tiene su propio desplazamiento dentro del panel; ya no está anidada en una lista de la barra global.

Para cambiar el orden de las secciones, activa **Ordenar secciones**, usa **Mover** en la fila correspondiente e indica la posición de destino. Puedes deshacer ese cambio; **Terminar orden** vuelve a la navegación normal. Las filas normales no se arrastran. Para mover hallazgos, abre el tablero **Hallazgos**, selecciona el orden **Manual** y usa su acción **Mover**. Estos movimientos sí cambian el orden del proyecto; los filtros del índice no lo hacen.

En escritorio, **Ancho del índice** permite ajustar el panel entre 220 y 420 píxeles, en pasos de 20. El control admite teclado: flechas para ajustar, **Inicio** para el mínimo y **Fin** para el máximo. Apertura, ancho, pestaña, búsquedas, filtros y página se conservan en este navegador por espacio de trabajo y proyecto; no se escriben como contenido del informe. En pantallas pequeñas, el ancho se adapta automáticamente. Si el índice deja sin espacio a la vista previa, ciérralo o usa **Mostrar vista previa** para recuperar ese espacio.

En **Entrega → Herramientas** están **Biblioteca de informes**, **Respaldo integral**, **Datos privados guardados**, **Comprobar instalación**, **Actualizar report-gen** y, en escritorio, **Evidencia y decisiones**. En móvil, esta última conserva su acceso en **Más**; **Tutorial visual** también permanece en **Más**. El respaldo del proyecto sigue separado del respaldo integral.

En móvil, **Navegación** abre la barra global. El índice se abre con su propio botón; seleccionar una entrada lo cierra y lleva el foco al contenido. **Escape** cierra el panel abierto y devuelve el foco a su botón. Un diálogo superpuesto conserva su propio manejo del foco. Los nombres y controles están disponibles en español, inglés y portugués de Brasil, en temas claro y oscuro; cambiar el idioma de la interfaz no traduce el contenido redactado.

## Organizar varios proyectos

En **Inicio → Tus proyectos**, busca por título, cliente o identificador; la búsqueda admite texto sin acentos. Filtra por activos, archivados, todos o retest pendiente. Ordena por última modificación, cliente, fecha más próxima o cantidad de retests pendientes. La lista muestra ocho proyectos por página.

**Entrega prevista → Guardar fecha** registra una fecha independiente de la fecha del informe. **Próxima fecha** muestra la menor entre esa entrega y los plazos de hallazgos que no estén corregidos y verificados ni tengan el riesgo aceptado; incluye vencimientos pasados. **Retests pendientes** cuenta hallazgos con estado **Corrección comunicada**, no todas las comunicaciones recibidas por CSV.

**Archivar** conserva el contenido y permite abrirlo, editarlo y **Reactivar** después. No elimina archivos ni convierte el proyecto en solo lectura. El inicio automático elige un proyecto activo; los archivados siguen accesibles desde su filtro y el selector. Fechas y estado de archivo viajan en respaldos e historial, y no se publican como contenido del informe.

## Editar hallazgos por lotes

En **Hallazgos → Editar por lotes**, selecciona expresamente los hallazgos. La búsqueda y las páginas de 50 elementos conservan la selección de otras páginas; el contador incluye todos los seleccionados. El límite es de 500 hallazgos por operación.

1. Marca los campos que quieres cambiar: **Responsable**, **Fecha de corrección** o **Grupo de causa raíz**. Un valor vacío retira esa asignación; los campos no marcados se conservan.
2. Pulsa **Comparar cambios**. Se guardan primero los cambios pendientes del informe y se presenta cada valor anterior y propuesto, también para hallazgos ocultos por la búsqueda.
3. Revisa la comparación, marca la confirmación y pulsa **Guardar cambios revisados**. La asignación se guarda en una sola operación y crea una versión recuperable en **Versiones**. Si el proyecto cambia mientras revisas, debes comparar de nuevo.

No modifica estado, verificación técnica, evidencias ni retests. Un error de guardado conserva la selección y propuesta en el diálogo para reintentar; no se promete recuperar este formulario tras recargar o cerrar el navegador. Cerrar una propuesta sin guardar requiere confirmar su descarte.

**Mover** permite reordenar hallazgos con teclado también en proyectos pequeños; no exige arrastrar. Los filtros, vistas guardadas, posición y actividad reciente se separan por espacio de trabajo y proyecto. Las preferencias antiguas sin identidad no se adoptan por coincidencia de nombre. Si un filtro apunta a un valor eliminado, aparece **No disponible** junto al contador de filtros activos; **Limpiar filtros** vuelve a mostrar todos los hallazgos.

## Compartir un diagnóstico

Abre **Entrega → Herramientas → Comprobar instalación**. Las pruebas generan archivos sintéticos temporales para los motores PDF y DOCX y comprueban la escritura del espacio de trabajo; no exportan proyectos reales. Un motor ausente aparece como fallo, separado de los demás.

En **Diagnóstico para compartir**, revisa el JSON, marca **He revisado los campos del diagnóstico** y usa **Descargar diagnóstico revisado**. El archivo contiene únicamente versión de report-gen, sistema operativo genérico, versión de Python y estados de exportaciones sintéticas y escritura. Excluye nombres de proyectos, clientes y usuarios, rutas, hostname, variables de entorno y detalles de excepciones. No se envía automáticamente. Cambiar el contenido de la vista previa invalida su descarga; vuelve a generar el diagnóstico si necesitas actualizar los resultados.

La comprobación DOCX genera y vuelve a leer un documento: no acredita la paginación ni la apertura en Microsoft Word nativo.

## Qué comprueba cada entrega

**Ver comprobaciones** muestra revisión, SHA-256, tamaño y controles de cada descarga. HTML, Markdown y Word comparan párrafos, código literal, metadatos, destinos de enlaces y colocaciones de evidencia dentro de su hallazgo, además de tablas y listas. La imagen se compara por su huella pública, pie y contexto precedente. Para código solo se normalizan los finales de línea CRLF/CR a LF; se conservan espacios, tabulaciones, comillas y líneas vacías. Markdown incluye el gráfico de severidad como PNG, su texto alternativo con los conteos y su leyenda de alcance. Se comprueban los bytes de esa imagen generada, el texto y su posición respecto del resumen, por separado de las evidencias.

Los manifiestos y registros de comprobación descargables conservan categorías y cantidad de avisos, pero no sus mensajes privados, rutas ni valores de origen. El detalle completo permanece en el editor para revisión. Esta separación no censura los campos que decidas incluir en el informe o en un anexo.

Los IDs existentes, como `F10`, no se renumeran al editar la lista. Los nuevos reciben un identificador no reutilizado. Una referencia interna a un destino inexistente bloquea la publicación y muestra el enlace que hay que corregir. La comparación estática de HTML detecta `hidden`, `display:none`, `visibility:hidden`, opacidad cero y sus ancestros. No certifica geometría, oclusiones ni todos los estados de CSS y JavaScript: todos los formatos requieren revisión visual.

Los enteros del proyecto deben estar entre −9.007.199.254.740.991 y 9.007.199.254.740.991 para conservar su valor al editar en el navegador. Guarda identificadores o valores documentales mayores como texto entre comillas en YAML/JSON. Las entradas que exceden ese rango se rechazan con la ruta del campo; no se redondean ni sustituyen por `null`.

PDF comprueba presencia textual, incluidas celdas de tablas y elementos de listas, imágenes y destinos del índice. La comprobación textual es global: no prueba la posición ni asociación de una celda o elemento. Las envolturas de una línea de código se mantienen en una misma página; una línea que supera la altura imprimible se rechaza conservando la salida anterior. La extracción puede cambiar orden y espacios: no acredita indentación literal ni asociación de bloques. La ficha lo marca como revisión manual requerida. Ningún formato queda certificado visualmente por estos controles.

Las tablas extensas dentro de un hallazgo, incluido su procedimiento detallado, pueden continuar por filas entre páginas con cabeceras repetidas. Las tablas breves se mantienen juntas. Cada celda y el encabezado deben caber en la altura imprimible; si no, reduce o divide ese contenido según el diagnóstico. El proceso de exportación PDF dispone de 300 segundos por defecto. Puedes definir `REPORT_GEN_PDF_TIMEOUT` antes de iniciar report-gen con un número entero entre 30 y 600 segundos; un valor inválido se rechaza antes de lanzar el motor. Si vence el plazo, conserva la salida anterior y retira sus archivos intermedios. La cola mantiene su cancelación y su plazo exterior de 1.800 segundos. El presupuesto no se amplía automáticamente después de un fallo: divide el contenido, ajusta explícitamente la configuración o reintenta con menos carga.

La versión 0.34.0 corrigió el coste excesivo de maquetación de las URLs literales largas. La prueba de 72 filas con una URL de unos 300 caracteres por fila, situada en una sección narrativa, pasó dentro del límite tras esa corrección. No establece un máximo universal de filas ni un tiempo garantizado: influyen el contenido y los recursos disponibles. Conserva las URLs literales que formen parte de la evidencia; las etiquetas descriptivas son una opción de redacción, no un requisito para exportar ese caso.

La verificación PDF reserva ocurrencias físicas independientes para cada línea de código y, dentro de cada categoría, para encabezados, celdas, elementos de lista y párrafos distintos. Una celda larga no puede suplir simultáneamente otra celda ausente cuyo texto contiene. Las categorías se comprueban por separado porque un párrafo dentro de una lista pertenece legítimamente a ambas. Si una combinación de saltos ambiguos supera el presupuesto de comprobación, informa que no pudo completar la verificación y conserva la entrega anterior; no acusa pérdida de contenido sin demostrarla.

Cuando el informe conserva las secciones canónicas, la verificación PDF también
exige que el texto de cada hallazgo aparezca dentro de su región, entre los
destinos PDF que la delimitan. Comprueba título, encabezados, párrafos, código,
celdas, listas y metadatos. Las copias del índice o del resumen no sustituyen
texto ausente allí. Este control no verifica el orden visual ni la asociación
de cada imagen; los documentos no canónicos conservan el alcance global.

En **Informe → Espaciado del informe** puedes elegir cómoda o compacta. Es independiente de la densidad visual del editor. El HTML portátil permite filtrar por tipo, severidad pendiente y texto, y restablecer los filtros. PDF y HTML ajustan las URL literales al ancho disponible sin modificar su texto. Sin el complemento descrito más abajo, LibreOffice puede adelantar algunos saltos de URL en DOCX; no se insertan saltos ni caracteres artificiales en el documento para ocultar esa limitación.

En PDF, los identificadores ASCII de 32 o más caracteres, o de 24 o más con dígitos, guion bajo, barra o dos puntos, pueden continuar desde el espacio que queda en la línea. El ajuste se limita a esas cadenas y las URLs; conserva sus caracteres y las reglas normales de la prosa Unicode. No garantiza el mismo salto para cualquier palabra o ancho arbitrario.

El cuerpo de PDF y Word continúa entre capítulos sin imponer una página nueva a cada uno. La portada y el índice permanecen separados. Una figura que no cabe completa pasa a la página siguiente, conservando tamaño y orden; ese espacio no se elimina recortando la evidencia.

Las leyendas extensas pueden continuar por páginas sin reducir la imagen hasta hacerla invisible. Word conserva sus saltos explícitos; HTML, PDF y Markdown también los representan. Una leyenda vacía mantiene el rótulo y número de figura, sin asteriscos residuales en Markdown. Los controles de contenido no sustituyen la revisión de la asociación visual entre imagen y leyenda.

Las tablas de retest dentro de citas o listas pueden continuar por filas, igual que las tablas directas de esa sección. En Word, el título y el recuento inicial permanecen junto a la tabla; esta regla no encadena todas sus filas ni cambia las notas narrativas sin tabla. Si no registras fecha, el encabezado omite su separador vacío, sin inventar una fecha.

Mientras el servidor siga abierto, salir de la página no cancela una exportación en curso. El navegador suspende las consultas de estado de ese documento y las reanuda cuando se restaura. Un error real al consultar sigue visible y permite reintentar; este comportamiento no garantiza recuperar un borrador que no se haya guardado.

En HTML portátil, las tablas con una fila de encabezados y celdas uniformes se muestran por registros cuando el ancho es reducido, con el encabezado junto a cada valor. Las tablas con celdas combinadas o encabezados complejos conservan desplazamiento horizontal local para mantener sus relaciones. Los ordinales extensos quedan sobre el texto cuando falta ancho.

**Compatibilidad de URLs en Word**, dentro de la revisión, identifica ubicaciones con URLs visibles de 96 o más caracteres en el contenido que se publicará. Es una señal para inspeccionar el DOCX, no una medición del salto ni un fallo de preparación; no cambia la puntuación. Los campos Markdown ofrecen **Enlace** para introducir un nombre descriptivo y una URL HTTP/HTTPS cuyo destino se conserva literalmente. Es una alternativa voluntaria de redacción: si la URL literal forma parte de una evidencia o un comando, consérvala. El aviso no modifica automáticamente el informe ni muestra el valor detectado.

Los anexos van exclusivamente en el paquete ZIP bajo `anexos/`, con su hash en `verificacion.json`. Se excluyen hasta que los revises y marques. No se censuran ni se limpian sus metadatos: carga copias ya redactadas. Un anexo seleccionado ausente o alterado bloquea la entrega. Declaraciones pendientes y exclusiones aparecen en los avisos. Al marcar **Obligatorio para entregar**, el paquete queda bloqueado hasta incluir una copia revisada e íntegra, incluso si aceptas los avisos.

**Analizar posibles secretos** busca patrones en el primer MiB de textos UTF-8, cuenta metadatos de imágenes e inspecciona PDF con alcance acotado. [Consulta el recorrido y los límites](#revisar-errores-y-documentos-en-0380). No realiza OCR de anexos ni los autoriza o modifica. El Inspector ofrece por separado OCR local opcional de las imágenes publicadas. Se muestran alcance y límites, sin reproducir los valores sensibles.

## Complemento opcional para LibreOffice

**Entorno comprobado:** distribución oficial de LibreOffice 26.2.6.3 para Linux x86-64, con su proveedor Python UNO. La aceptación instala el OXT mediante el cargador real en un perfil temporal y comprueba apertura, cambio de ancho, guardado y reapertura. No sustituye la revisión visual de tu informe ni garantiza iguales saltos en otros editores.

El exportador DOCX marca por defecto los literales elegibles con el idioma no lingüístico privado `zxx-ZZ-x-rgwrap`. Cambia los metadatos de idioma de esos fragmentos, no el idioma de la prosa ni los caracteres, estilos o destinos de los enlaces. La marca puede aparecer en cuerpo, tablas, cabeceras y pies; los campos y sus resultados se conservan. Exportar y abrir el DOCX no requiere instalar LibreOffice ni el complemento.

El ajuste se limita a URL HTTP/HTTPS/FTP/FTPS completamente ASCII de al menos 32 caracteres y a identificadores ASCII imprimibles sin espacios de al menos 24 que contengan un dígito, guion bajo, barra o dos puntos. No se aplica a palabras compuestas sólo por letras ni a URL con caracteres no ASCII. El complemento aprovecha el espacio disponible de la línea sin insertar caracteres invisibles, guiones ni saltos manuales. Si añades prosa después de un literal al editar en Writer, conserva el idioma de la prosa circundante.

Necesita el proveedor de componentes Python UNO de la misma instalación de LibreOffice. El entorno virtual de report-gen no lo sustituye. La prueba aceptada usó los paquetes oficiales 26.2.6.3, incluidos `libobasis26.2-pyuno` y `libobasis26.2-python-script-provider`. No mezcles esos componentes con el Python de otra distribución de LibreOffice.

En **LibreOffice 24.2.7.2 de los paquetes de Ubuntu**, la instalación del complemento falló, incluso con `python3-uno` y `libreoffice-script-provider-python` presentes. Esos paquetes no constituyen una ruta aceptada para este complemento. Ese fallo se conserva por separado de la aceptación del paquete oficial 26.2.6.3.

Para construir el OXT desde el código fuente descargado de report-gen, sin instalarlo:

```bash
python integrations/libreoffice/build_oxt.py --output report-gen-libreoffice-0.42.0.oxt
```

1. En la instalación de LibreOffice elegida abre **Herramientas → Extensiones → Añadir**. Algunas versiones llaman al menú **Gestor de extensiones**.
2. Selecciona `report-gen-libreoffice-0.42.0.oxt` e instálalo para tu usuario.
3. Cierra todas las ventanas de esa instalación de LibreOffice, vuelve a abrirla y abre una copia del DOCX recién exportado por report-gen.
4. Comprueba sus URL, listas y tablas después de abrirlo, editarlo y guardarlo. Para retirarlo, desactívalo o elimínalo en el mismo gestor y reinicia LibreOffice.

Sin el complemento, el DOCX conserva su texto y sigue siendo editable, pero el motor puede mantener los saltos anticipados. Instalarlo no añade la marca a documentos antiguos: vuelve a exportarlos desde report-gen. La mejora depende del complemento y del motor, no es una reparación portable contenida únicamente en el DOCX. No hay aceptación acreditada de Microsoft Word ni de LibreOffice para Windows o macOS.

El complemento no afecta a las exportaciones PDF, HTML o Markdown de report-gen. Tampoco garantiza extracción literal universal ni evita la normalización de URLs al convertir desde LibreOffice a PDF; por ejemplo, el motor puede convertir `%2D` en `-` en una anotación de enlace aunque el literal visible y el destino DOCX se conserven.

El OXT se construye por separado: no es un cuarto artefacto de la Release y el actualizador no lo instala. Consulta el [gestor de extensiones de LibreOffice](https://help.libreoffice.org/latest/es/text/shared/01/packagemanager.html).

## Datos y recuperación

La cola de exportación termina los procesos de cada trabajo antes de limpiar sus archivos. Windows utiliza un grupo privado de procesos. En Linux y macOS, un supervisor conserva el grupo del trabajo hasta que termina la limpieza, sin depender de `waitid`/`WNOWAIT`; comunica el resultado del trabajador por separado y detiene el grupo si el proceso padre desaparece. La limpieza cubre los descendientes que permanecen en ese grupo: no es un aislamiento contra programas que deliberadamente crean otra sesión. El gate de macOS ejecuta Python 3.11 y 3.12.

La carpeta externa contiene `projects/` y `library/`; originales, historial y anexos permanecen dentro de cada proyecto. El lanzador resuelve `--workspace` antes que `REPORT_GEN_WORKSPACE`. Sin ninguna selección, conserva `webapp/projects/` y `webapp/library/`; no busca ni traslada datos automáticamente. Usa **Respaldo integral** para trasladar proyectos, originales y bibliotecas juntos. Es información privada.

Los borradores pendientes se conservan en IndexedDB durante 30 días, separados por identidad del espacio de trabajo, perfil del navegador y origen (host y puerto). Solo se anuncian como recuperables cuando la escritura termina. No están cifrados por la aplicación. Recuperan los datos del proyecto. Un registro separado protege las capturas y los formularios de Evidencia y decisiones aún sin incorporar: se recuperan explícitamente como formularios, no se adjuntan ni aprueban solos. El registro admite hasta 16 MiB por imagen, 1 MiB por formulario y 64 MiB en total. Si falla la escritura o se supera el límite, se indica que el trabajo permanece sólo en la pestaña. Los consentimientos de publicación se vuelven a pedir al recuperar. Esta protección también cubre edición masiva y formularios auxiliares de bibliotecas, importación, anotaciones y creación. Las contraseñas, aprobaciones y archivos que requieren volver a seleccionarse no se recuperan automáticamente. Estas copias pendientes no se incluyen en el respaldo integral ni en el JSON de emergencia: incorpóralas y guarda antes de cambiar de instalación u origen del navegador. El modo privado, borrar los datos del navegador o cambiar de perfil/puerto puede hacerlos inaccesibles. **Más → Descargar borrador privado** permite guardar una copia de emergencia. Recuperarla exige abrir el mismo proyecto y resolver conflictos; nunca sustituye una revisión concurrente sin elegirlo.

La identidad permanece estable al reiniciar o actualizar la aplicación si conservas la misma ubicación externa de datos. Mover la carpeta o restaurar un respaldo en un espacio nuevo crea un ámbito distinto: no adopta borradores porque coincida el identificador del proyecto. El respaldo integral conserva proyectos guardados, pero excluye la identidad local y los diarios del navegador. Descarga los pendientes antes de trasladarte. Si una pestaña detecta que el servidor cambió de espacio, bloquea las peticiones y permite descargar el borrador antes de recargar.

Las versiones anteriores no identificaban el espacio de sus copias. **Más → Copias anteriores sin asignación** las conserva sin incorporarlas ni borrarlas automáticamente. Elige **Entiendo el origen incierto; revisar copias**, revisa el contenido privado y usa **Descargar copia privada**; una captura pendiente ofrece por separado su imagen original. Para un borrador descargado, abre el proyecto correcto y elige **Recuperar archivo de borrador**: si la identidad no coincide o falta, se requiere confirmar la comparación antes de resolver cambios. Las copias antiguas solo se eliminan al elegirlo expresamente.

**Datos privados guardados** inventaría archivos actuales, originales, historial y anexos retirados. Puedes descargar o eliminar borradores del navegador y limpiar categorías concretas del disco. La limpieza requiere selección y escribir el identificador del proyecto. Conserva los datos actuales y, al limpiar historial, un punto nuevo de recuperación. Las descargas y respaldos externos no se borran desde esta vista.

La censura de texto se aplica a una copia de publicación. La censura de imagen crea una derivada de píxeles; conserva el original privado. Las exportaciones eliminan metadatos de las imágenes. El detector de patrones ayuda a revisar, pero no identifica todos los secretos.

El HTML portátil contiene todo el informe; los filtros y la vista ejecutiva son opciones de lectura, no permisos de acceso. La comparación compartible omite imágenes históricas; la comparación interna puede incluir capturas privadas y no debe entregarse al cliente.

## Actualización asistida

Abre **Entrega → Herramientas → Actualizar report-gen**. No hay consultas de red en segundo plano ni actualizaciones automáticas.

1. Marca **Permitir consulta y descarga desde GitHub** y pulsa **Comprobar versión oficial**. Se consulta exclusivamente el repositorio oficial `IphobiusS/report-gen`; no se envían informes, rutas locales ni credenciales. Si no existe una versión estable más reciente, se indica sin preparar archivos.
2. Revisa la versión, el tamaño, el SHA-256 y su publicación. Confirma por separado la preparación del paquete y del **respaldo privado sin cifrar**; pulsa **Descargar, verificar y respaldar**. Se guardan los cambios pendientes del proyecto abierto antes de preparar.
3. Descarga las **instrucciones privadas**. Incluyen las rutas de la nueva aplicación y del respaldo, su fecha y SHA-256, los comandos para continuar y cómo volver a la instalación anterior.
4. Guarda o descarga los borradores pendientes de otras pestañas, ciérralas y detén el editor con `Ctrl+C`. No cambies proyectos entre el respaldo y la actualización. Ejecuta las líneas indicadas una a una; si alguna falla, detente. Instalar las dependencias de la nueva carpeta requiere Internet.
5. Comprueba proyectos, imágenes, historial y exportaciones antes de retirar la instalación anterior; conserva el respaldo.

La preparación verifica la etiqueta y su commit, los tres artefactos de aplicación de la Release (ZIP, JSON y SHA-256), el SHA-256 del ZIP y todos los archivos del manifiesto. El complemento opcional de LibreOffice se construye por separado desde las fuentes descargadas: el actualizador no descarga ni verifica un OXT independiente, ni lo instala. Rechaza rutas y tipos de entrada no admitidos. Comprueba integridad desde el origen oficial por HTTPS; no es una firma criptográfica independiente del repositorio. El paquete fuente admite hasta 128 MiB comprimidos, 256 MiB extraídos y 4.000 archivos.

Los archivos quedan en `~/report-gen-updates/update-*/`: `application/`, `workspace-backup.zip` y `receipt.json`. Cada preparación captura los datos guardados actuales y valida una restauración temporal del respaldo. Una captura idéntica puede reutilizar la preparación verificada; si cambian los datos, se crea otra conservando el respaldo anterior. Estos archivos son privados y el ZIP de respaldo no está cifrado. Los borradores del navegador quedan fuera.

No se ejecuta el código descargado ni se reemplaza la aplicación mientras preparas. Las instrucciones reutilizan el espacio externo o trasladan explícitamente los datos heredados a uno nuevo. En Linux usan el instalador local; Windows y macOS usan el lanzador Python. Conserva la aplicación anterior y ejecuta solo un proceso sobre el espacio de trabajo. Para volver, detén el nuevo editor y usa el comando mostrado. Si ya editaste con la nueva versión, conserva ambas carpetas y restaura el respaldo en un espacio vacío en vez de sobrescribir trabajo.

## Actualizar desde una versión anterior

Si prefieres actualizar manualmente y ya tienes datos externos, detén el editor, descomprime o clona la versión actual en una carpeta nueva y ejecuta `python3 scripts/install.py --desktop --workspace /ruta/datos-existentes`. Así preparas la nueva `.venv` y actualizas el acceso para reutilizar esos datos; no necesitas importarlos ni `--upgrade-from`. No abras dos procesos sobre el mismo espacio de trabajo. Una vez comprobada la nueva instalación, puedes retirar la carpeta de la aplicación anterior conservando los datos externos.

Para separar datos que aún están dentro de una instalación antigua, detén ambos editores y ejecuta desde la nueva carpeta:

```bash
python3 start.py --ready --workspace /ruta/datos-nuevos --upgrade-from /ruta/report-gen-anterior
```

El destino externo debe estar vacío y fuera de ambas instalaciones. Si actualizaste el código en la propia carpeta que contiene los datos heredados, `python3 start.py --ready --workspace /ruta/datos-nuevos --upgrade-from .` permite trasladarlos desde allí. El mismo comando sin `--workspace` conserva la migración anterior entre dos instalaciones distintas; no borres ni mezcles carpetas manualmente.

El lanzador prepara su propio entorno, crea un respaldo integral del origen, valida una restauración temporal y traslada los datos al destino vacío seleccionado. Muestra el resultado, la ruta del ZIP y su SHA-256; luego comprueba los motores y abre el editor. Si ya instalaste las dependencias y prefieres revisar el resultado antes de arrancar, omite `--ready`: la migración termina después del diagnóstico.

El respaldo se conserva en `~/report-gen-backups/upgrade-*/workspace.zip`, fuera de las instalaciones y del destino externo, junto a `result.json` con su SHA-256 y contadores. Es privado: incluye los originales y el historial. Si falla la activación en el destino, el respaldo ya creado se conserva y la instalación anterior no se modifica. Las rutas solapadas, enlaces simbólicos, estados de recuperación pendientes y destinos con proyectos o bibliotecas personales se rechazan para evitar una mezcla o sobrescritura. Corrige la causa indicada y utiliza un destino vacío; no borres tus datos para forzar la operación.

La migración conserva los proyectos, evidencias, historial y bibliotecas incluidos en el respaldo integral. No copia `.venv`, salidas de entregas ni borradores del navegador. Descarga un borrador pendiente antes de cambiar de instalación u origen del navegador. Abre tus proyectos, verifica las imágenes y el historial y conserva también las entregas que necesites antes de retirar la carpeta anterior.

Como alternativa, crea **Respaldo integral** con la versión anterior y restáuralo en la instalación nueva vacía. Si un proyecto antiguo solo conserva su revisión previa en `engagement.yaml.bak`, sin historial, el exportador de 0.21.2 omite esa copia. Conserva el directorio original y usa el traslado de 0.30.0 para incorporar esa recuperación heredada. Un ZIP antiguo que ya omitió la copia no permite reconstruirla.

Los proyectos anteriores siguen siendo legibles. Los respaldos que contengan el directorio de anexos requieren 0.21.0 o posterior; una versión anterior puede rechazarlos. Los registros de anexos con el campo `required` necesitan 0.21.1 o posterior, aunque su valor sea falso. Desde 0.21.2, el contador `finding_sequence` impide reutilizar números eliminados; no modifica los IDs existentes. Versiones anteriores no conservan esta garantía. Si una edición antigua ya cambió el significado de una referencia, esta versión no puede inferir el destino original: revisa las referencias heredadas.

## Exportar por terminal

```bash
.venv/bin/python export.py /ruta/datos/projects/mi-proyecto/engagement.yaml -f html -o informe.html
```

Sustituye `/ruta/datos` por el espacio de trabajo elegido; en una instalación heredada, el proyecto está bajo `webapp/projects/`. Otros formatos: `pdf`, `docx`, `md` (ZIP con imágenes). Los recursos se procesan localmente.

El resumen automático describe los hallazgos y las severidades registradas, sin afirmar que todos estén confirmados. Las entradas de máquinas son registros; **Inventario de activos** tampoco acredita una evaluación realizada. Consulta **Cobertura y limitaciones** y el estado de verificación de cada ficha. Si no has escrito un enfoque propio, el texto predeterminado se limita a la información documentada y no afirma una reproducción manual. Un texto escrito expresamente por el autor se conserva y debe revisarse antes de entregar.

El ejemplo `examples/pending-severity/engagement.yaml` permite comprobar el resumen con dos hallazgos ficticios confirmados y sin severidad. En Word, las entradas del índice están disponibles desde la exportación, con enlaces internos y campos nativos `PAGEREF` independientes. LibreOffice calcula sus números al componer el documento; si cambias el contenido, selecciona todo con **Ctrl+A** y actualiza con **F9**. Las cifras siguen la paginación real del editor, no la del PDF. Para añadir, quitar, renombrar o reordenar capítulos del índice, modifica el informe en report-gen y vuelve a exportar: la lista de entradas no es un campo TOC que se reconstruya automáticamente en Word. LibreOffice y Microsoft Word pueden distribuir el contenido de forma distinta.

El índice reserva ancho para el número de página, evitando que un título cercano al límite lo deje solo en otra línea. Revisa nuevamente las cifras, enlaces y distribución después de cambiar el contenido o abrir el archivo en otro editor; las comprobaciones de LibreOffice no acreditan por sí solas Microsoft Word nativo.

Las listas numeradas de los informes admiten ordinales de 0 a 2.147.483.647, compatibles con el navegador y Word. Si una lista supera ese límite, la exportación se detiene y conserva cualquier archivo anterior. Renumera la lista o presenta esos identificadores como texto; no se reduce ni reemplaza su valor en silencio.

Dentro de una lista Markdown, indenta la continuación y las cercas de código con cuatro espacios por nivel, aunque el ordinal tenga muchas cifras. Ocho espacios en el primer nivel representan código indentado, no una continuación equivalente. Los bloques cercados conservan tabulaciones, espacios y líneas vacías; el código indentado sigue la normalización de Markdown.

Una lista de Word cuyo inicio supera 65.535 utiliza campos `SEQ` para evitar el truncamiento observado en LibreOfficeDev 26.8. Las demás mantienen la numeración automática, incluso al cruzar ese valor. Para ampliar una lista con campos, puedes editarla en report-gen y volver a exportar. Dentro de Word, copia un elemento posterior al primero, conservando su campo, y actualiza con **Ctrl+A → F9**; el primer campo fija el inicio. Si sólo hay un elemento, usa la edición en report-gen. Pulsar Enter por sí solo no añade un campo. Las comprobaciones de HTML, Markdown y Word comparan ordinales, formato decimal y orden con el texto fuente; en Word también comprueban la instrucción y el resultado guardado de cada campo. No sustituyen comprobar cómo lo presenta tu editor. PDF mantiene la numeración como revisión visual requerida.

## Desarrollo y límites

Estas pruebas requieren Node.js 22+ y un entorno Python instalado. Ejecuta los comandos desde la raíz del proyecto.

Los clientes API seleccionan el idioma de error con `X-UI-Language: es`, `en` o `pt` (también se acepta `pt-BR`). Sin ese encabezado, o con otro valor, se conserva el español predeterminado. Las URL abiertas directamente usan ese valor predeterminado; los diagnósticos de bibliotecas y herramientas externas se conservan sin sustituciones. Esto no cambia el idioma ni el contenido del informe.

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

## Importar resultados de escáneres

En la importación existente puedes elegir CSV, Burp, Nuclei (JSONL) o Nmap (XML). Primero se presenta una vista previa; selecciona sólo los elementos pertinentes antes de incorporar. Nuclei conserva el origen y entra sin verificación técnica: importar no confirma una vulnerabilidad. Nmap incorpora activos, servicios y cobertura pendiente; un puerto abierto no crea un hallazgo. La incorporación comprueba la revisión del proyecto, conserva la procedencia y evita duplicados. Los archivos se leen localmente; no se ejecutan comandos ni se contactan los objetivos importados. Se admiten hasta 4 MiB, 500 filas o hosts y 10.000 puertos. Nmap omite scripts NSE, OS y traceroute; un escaneo sin cierre satisfactorio registrado se identifica como parcial.

## OCR opcional de capturas

En el Inspector de publicación, solicita OCR para una imagen concreta. Requiere Tesseract local con el idioma `eng`; no descarga motores ni envía imágenes a un servicio. Acepta imágenes estáticas de hasta 12 MiB y 12 megapíxeles. Señala categorías y regiones de posibles datos sensibles sin devolver el texto reconocido. Una ausencia de alertas no demuestra que la imagen sea segura: revisa la captura y aplica manualmente una copia censurada cuando proceda. La imagen original no se modifica. Los errores, límites o motor ausente quedan visibles; no se presentan como una revisión completada.

## Respaldos periódicos opcionales

En **Respaldo integral → Respaldos periódicos opcionales**, escribe la ruta absoluta de una carpeta existente, fuera de la aplicación y del espacio de trabajo. Elige **cada hora**, **cada día** o **cada semana**, y entre **1 y 90 copias**. Revisa el destino, confirma que las copias son privadas **sin cifrar** y pulsa **Guardar programación**. La opción viene desactivada. Para detenerla, usa **Desactivar programación**; las copias existentes permanecen.

La programación funciona únicamente mientras sigue abierto el servidor local iniciado por el lanzador de report-gen. Cerrar una pestaña no detiene ese servidor; cerrar el proceso sí. Al reiniciar el editor se comprueba si hay una copia vencida, sin crear una copia por cada intervalo perdido. Se revisa al iniciar y cada minuto. Tras un fallo se espera al menos cinco minutos antes de reintentar. No se instala una tarea del sistema ni se envían datos por red.

Cada copia incluye los proyectos, originales, anexos, versiones y bibliotecas guardados. La captura comparte el bloqueo de las ediciones, de modo que no combina una operación a medias. No incluye borradores o formularios pendientes del navegador; guarda o descarga ese trabajo aparte. **Crear y comprobar copia ahora** guarda primero el proyecto abierto; una ejecución programada solo captura datos que ya están en disco. No se conservan contraseñas. Usa una carpeta protegida y, si buscas protección ante una avería del disco, un disco distinto.

El programa crea una subcarpeta `report-gen-backups-<identificador>`. Antes de registrar una copia y retirar las antiguas, restaura el ZIP en una carpeta temporal, valida su contenido y comprueba los bytes escritos. La retención solo afecta a archivos registrados e intactos de esa serie; archivos ajenos, copias alteradas y destinos anteriores se conservan. Cambiar de destino inicia otra serie, incluso si después regresas a la carpeta anterior. Un aviso indica si la retención quedó pendiente por permisos o por una copia alterada. Si un archivo cambia durante la retirada y no se puede devolver a su nombre original sin sobrescribir otro, queda conservado en una subcarpeta privada `.retention-*`; revísala antes de cualquier limpieza manual. Esta medida no aísla los archivos de un proceso malicioso que ya tenga acceso a la misma cuenta del sistema.

El panel muestra la última copia correcta, la última restauración temporal correcta, su ruta privada y su SHA-256. **Actualizar estado** consulta el estado actual; **Comprobar última copia** vuelve a restaurarla en una carpeta temporal sin modificar tus proyectos actuales. Una fecha anterior no acredita que el último intento haya funcionado: revisa los avisos. Si falta espacio, desconectaste el disco o cambiaron permisos, corrige la causa y vuelve a crear o comprobar una copia.

La configuración se guarda de forma privada en el espacio de trabajo y queda fuera de las exportaciones y del respaldo integral. Al trasladar o restaurar tus proyectos a otro espacio, configura de nuevo la programación. Para recuperar una copia, selecciona su ZIP con la opción de restauración integral en una instalación vacía. La comprobación temporal verifica que el respaldo es recuperable con esta versión; no sustituye mantener una copia en otro dispositivo.

## Respaldos privados con contraseña

Instala la dependencia opcional en el entorno del proyecto:

```bash
.venv/bin/python -m pip install -e '.[privacy]' -c requirements-audited.txt
```

En **Respaldo integral**, indica y confirma una contraseña de 12 a 256 caracteres y elige **Descargar respaldo cifrado**. El `.rgbackup` contiene el espacio privado completo; no es una entrega para un cliente. AES-256-GCM autentica el archivo y scrypt deriva su clave con parámetros fijos. Conserva la contraseña por separado: report-gen no puede recuperarla. Esta opción protege el archivo descargado, no cifra los datos en disco ni los borradores del navegador. El ZIP privado sin cifrar continúa disponible y está identificado como tal.

Para restaurar, selecciona el `.rgbackup` y su contraseña en una instalación vacía. Se autentica antes de validar y activar su contenido mediante el restaurador existente. Contraseña incorrecta, archivo alterado o destino ocupado no autorizan una mezcla de proyectos ni una restauración parcial.

## Causas raíz y tareas de remediación

En **Análisis y seguimiento → Causas raíz**, crea un grupo con nombre, causa y acción común. Asigna los hallazgos relacionados; cada uno conserva su identificador permanente, severidad, evidencias, responsable y retests. Quitar un grupo desvincula sus miembros después de confirmar, pero no elimina los hallazgos. En cada hallazgo puedes definir además un **Criterio de cierre** comprobable.

La acción específica de un hallazgo tiene prioridad sobre la acción común. La sección de causas raíz del informe está desactivada por defecto: actívala expresamente y revisa el resultado. Las entregas parciales conservan solo grupos con hallazgos incluidos; las vistas pública y ejecutiva no incorporan este contenido privado automáticamente.

En **Tareas de remediación**, selecciona los campos que necesitas compartir. Las referencias permanentes mantienen la correspondencia con los hallazgos originales. El contenido redactado por ti requiere una confirmación de revisión: puede contener datos de clientes. Guarda el proyecto, genera la vista previa y descarga CSV o fichas HTML dentro de un ZIP. Cambiar los campos o el proyecto invalida la vista previa y exige revisarla de nuevo. Ninguna tarea se envía a un servicio externo.

El CSV protege las celdas que podrían interpretarse como fórmulas. Las fichas muestran el contenido como texto, sin ejecutar HTML. Los campos vacíos permanecen vacíos; ni la exportación ni el criterio escrito acreditan que la corrección se haya realizado.

## Recibir avances de remediación

En **Tareas de remediación → Recibir avances del responsable**, abre **1. Emitir una plantilla**. Selecciona hallazgos con responsable asignado, revisa los datos que saldrán y confirma la retención antes de **Emitir plantilla de retorno CSV**. Emitir guarda una asignación dentro del proyecto y su historial; no es una descarga sin cambios. Se conservan hasta 20 lotes o 4 MiB: los más antiguos dejan de admitirse al emitir nuevos lotes. Respaldos y reinicios conservan los lotes vigentes.

Entrega `remediation-return.csv` y pide editar solo `owner`, `due_date` y `reported_remediation`. Conserva referencias, cabeceras y apóstrofos iniciales en los campos de texto, incluido `project_slug`; son parte del formato reversible que neutraliza fórmulas. El responsable no puede quedar vacío. La fecha usa `AAAA-MM-DD`; dejarla vacía propone borrar el plazo. Guarda CSV UTF-8 separado por comas, hasta 2 MiB y 500 filas. Se pueden devolver algunas filas, pero no combinar lotes. El CSV informativo de tareas no sirve como plantilla de retorno.

Sube el archivo y elige **Comparar retorno**. Se muestran valor actual y propuesta; si cambió desde la emisión, también el valor emitido. Ningún campo queda aceptado por defecto. Selecciona cada cambio, confirma su revisión y pulsa **Guardar cambios seleccionados**. Un cambio concurrente exige repetir la comparación. Ante un error temporal al guardar, el archivo leído y las selecciones permanecen en la pestaña para reintentar. Después de guardar, la vista previa del informe deja de presentar la revisión anterior como actual; si está visible en modo vivo, se solicita de nuevo.

La comunicación se conserva separada como **Corrección comunicada por retorno (sin verificar)**. Importar no cambia estado, verificación técnica, retests, descripción ni evidencias: registra cualquier comprobación real en **Correcciones y retest**. La plantilla identifica el lote y proyecto, pero no autentica a quien la devuelve; revisa la procedencia antes de aceptar cambios.

## Entregas y registro por responsable

En **Tareas de remediación → Recibir avances del responsable → 1. Emitir una plantilla**, selecciona hallazgos con responsable y los campos de las fichas en los controles superiores. Confirma los datos privados y la retención. Usa **Previsualizar entrega por responsable** para revisar tanto las fichas como los valores incluidos siempre en el CSV: `owner`, `due_date` y `reported_remediation`, incluida la última comunicación existente.

**Emitir fichas y CSV por responsable (ZIP)** crea `remediation-delivery.zip` y guarda el lote en el proyecto. Cada carpeta `owner-001/`, `owner-002/`, etc., contiene un índice HTML, fichas y su CSV de retorno. El manifiesto registra campos, responsables, revisión de origen y hashes; `INSTRUCTIONS.txt` explica cómo separar la entrega. Las fichas incluyen únicamente los campos seleccionados; no añaden imágenes ni anexos. Su texto no ejecuta HTML o Markdown. El ZIP completo reúne a todos los responsables seleccionados: revisa y separa las carpetas que corresponden a cada destinatario antes de compartirlas. No hay envío automático ni permisos de acceso dentro del ZIP.

**Registro local de lotes** distingue emisión local, recepción registrada, cambios aceptados y revocación, con fechas, revisión de origen y hashes. Comparar un CSV es de solo lectura. Tras revisarlo puedes elegir **Registrar recepción sin aplicar cambios**, o seleccionar cambios y guardarlos; ninguna de las dos opciones certifica la identidad del remitente. **Revocar este lote** impide aceptar nuevos retornos de ese lote, sin borrar hallazgos ni registros.

Se conservan hasta 20 lotes o 4 MiB en total y 16 eventos por lote; el registro señala cuántos eventos antiguos se omitieron. Los lotes viajan en respaldos e historial y se excluyen del informe publicado. Restaurar una versión antigua también restaura su estado de lotes y revocaciones. Es un registro local editable: no demuestra que alguien recibió el archivo, autenticidad del remitente ni remediación verificada.

## Publicaciones descargables

La [última Release](https://github.com/IphobiusS/report-gen/releases/latest) reúne el ZIP de fuentes, su archivo SHA-256 y el manifiesto JSON. Su publicación automática exige los siete procesos del mismo commit: **tests**, **Browser acceptance**, **Windows compatibility**, **macOS compatibility**, **Additional renderer acceptance**, **Reproducible source package** y **R16 trilingual acceptance**. El publicador reconstruye los archivos desde Git, verifica los tres adjuntos tras subirlos y solo entonces publica la Release. Que una comprobación automática pase no sustituye la revisión de documentos ni las sesiones humanas.

## Materiales para las comprobaciones externas

`python scripts/prepare-external-acceptance.py --output out/external-acceptance` prepara siete DOCX ficticios y un CSV vacío de cinco participantes y tres tareas. El manifiesto declara Word y las sesiones humanas como `not_run`. El workflow manual de Word usa ese corpus y necesita un equipo Windows con Word de escritorio instalado. Consulta el protocolo y el comando de revisión en CONTRIBUTING.md. Generar estos materiales o ejecutar pruebas automáticas no equivale a haber observado personas ni a validar Word nativo.

El kit incluye `word-review.csv` para revisión visual y `INSTRUCTIONS.txt`. Tras realizar las comprobaciones, ejecuta `python scripts/prepare-external-acceptance.py --summarize out/external-acceptance`: valida hashes y registros sin alterarlos. Los estados de Word automático, inspección visual y sesiones humanas permanecen separados; preparar materiales o completar filas no acredita usabilidad general.

## Importar SARIF y comparar páginas PDF

En **Importar resultados**, elige **SARIF 2.1.0** y un archivo `.sarif` o `.json` UTF-8 (máximo 4 MiB, 50 ejecuciones y 500 resultados). Revisa la vista previa antes de importar la selección. Los resultados con supresión aceptada, pendiente o sin estado, ausentes o que no representan una comprobación fallida se muestran excluidos; una supresión rechazada no los excluye. Los duplicados ya incorporados no vuelven a importarse. Se conserva el origen, la ubicación y el nivel del analizador, junto con el hash del archivo. No se descargan ubicaciones, esquemas ni fragmentos externos; el archivo debe ser autónomo.

Se admiten reglas del analizador principal (`driver`) y de `tool.extensions`, ubicaciones físicas y nombres lógicos incluidos directamente. Las referencias a extensiones se resuelven por índice o GUID coherentes; el nombre solo corrobora la selección. Cada ejecución admite hasta 100 extensiones y 10.000 reglas agregadas. Los catálogos se mantienen separados. Sin GUID, la identidad de una extensión usa el hash de su componente completo: un cambio de versión o metadatos puede producir una observación nueva para evitar unir componentes distintos. Las huellas anteriores del driver se conservan. Se rechazan artefactos anidados mediante `parentIndex` y ubicaciones lógicas indexadas.

Las observaciones entran con severidad informativa, sin CVSS inferido y pendientes de revisión. Revisa el significado y la evidencia antes de clasificarlas. Marcar el contenido como revisado no confirma técnicamente un hallazgo.

En el historial, **Comparar PDF** permite elegir un archivo anterior y otro posterior. La comparación presenta las páginas lado a lado, diferencias de píxeles resaltadas, cambios de tamaño y páginas añadidas o retiradas. Por defecto se comparan por posición. Con el emparejamiento manual puedes relacionar cada página anterior con una posterior o indicar que no tiene equivalente; las páginas posteriores sin asignación se muestran como añadidas. La vista muestra la cobertura y bloquea las referencias repetidas. Cada página de ambos documentos debe aparecer exactamente una vez, hasta 160 parejas. Cambiar archivos invalida las correspondencias; cambiar el mapa invalida el resultado previo. Los hashes comprueban que los PDF comparados correspondan a los inspeccionados.

El resultado identifica el modo, el ordinal de cada pareja y los números originales de ambas páginas. Se alinean por la esquina superior izquierda y comparten escala. Una igualdad visual no acredita igualdad de texto, enlaces, adjuntos o metadatos. La inspección de páginas y la comparación se ejecutan en procesos aislados, con los mismos límites; la inspección devuelve solo geometría y hashes.

El HTML descargable contiene imágenes de ambos documentos y sus hashes. Revísalo antes de compartirlo, pues puede incluir información privada. Los PDF temporales se eliminan al terminar. Límites: 16 MiB y 80 páginas por PDF, 64 millones de píxeles comparados en total, 32 MiB de salida y 45 segundos por operación. Los PDF cifrados o que superan los límites se rechazan explícitamente.

**Registro opcional de revisión:** después de comparar, indica autor (1–120 caracteres), decisión y una nota de hasta 4000 caracteres. Si registras problemas, la nota es obligatoria. Guardar crea un anexo JSON privado con hashes de los originales y del HTML, correspondencias, conteos y tu declaración de revisión. El proyecto solo se modifica al guardar explícitamente; el registro queda excluido de la entrega por defecto y pendiente de revisión como anexo. Los registros comparten la cuota existente de 100 anexos y 64 MiB por proyecto.

El recibo temporal pertenece a la sesión, caduca a los 30 minutos y conserva como máximo ocho comparaciones por sesión, dentro de una cuota global de 64. Una nueva comparación sustituye el recibo más antiguo de esa sesión cuando se alcanza el límite de ocho. La caducidad impide usar el recibo; sus metadatos en memoria se depuran con la siguiente operación del almacén temporal. Cerrar el resultado o cambiar los archivos o correspondencias también descarta su recibo temporal, sin borrar los registros ya guardados.

Los registros guardados se conservan en el proyecto, sus revisiones y sus respaldos, sin caducidad ni borrado automático. Descargar el JSON permite conservar el registro; descarga el HTML por separado para conservar las imágenes. No se copian automáticamente los PDF, el HTML, las imágenes ni los nombres de los archivos originales; sí se guarda el texto que introduzcas en autor y nota. La autoría es autodeclarada, también en los registros importados: el JSON no es una firma ni demuestra autenticidad, equivalencia semántica o validación de Microsoft Word. Gestiona también las copias históricas y respaldos si necesitas retirar definitivamente un registro.

La protección de memoria depende del sistema: Linux limita a 768 MiB el espacio virtual y Windows la memoria comprometida del proceso. En macOS se limita el crecimiento virtual a 768 MiB sobre los mapas iniciales y un supervisor termina el proceso si una muestra de memoria residente o huella física supera 768 MiB. El intervalo objetivo de muestreo es 50 ms; puede haber exceso entre muestras y no constituye un techo físico instantáneo.

## Revisar errores y documentos en 0.38.0

### Encontrar el origen de un error

En **Importar resultados**, la ubicación aparece debajo del error o de la fila correspondiente. CSV identifica el registro y, cuando están disponibles, las líneas físicas inicial/final y la columna mapeada; un registro puede ocupar varias líneas. Burp muestra la entrada y su ubicación XML; Nuclei, el registro, línea y campo; Nmap, el host o puerto. SARIF identifica la ejecución y el resultado: sus índices empiezan en cero, como en el archivo. Una línea JSON solo se muestra cuando procede del analizador de sintaxis.

En **Exportaciones y descargas**, una exportación fallida puede mostrar el identificador del hallazgo y el campo afectado. Para tablas redactadas, los números de tabla, fila y celda empiezan en uno y la cabecera cuenta como fila. El índice de evidencia empieza en cero. No se inventa una celda cuando varias tablas tienen cabeceras o dimensiones ambiguas; un fallo global puede indicar únicamente operación y formato. Corrige el origen, guarda y vuelve a generar. Estos detalles permanecen en la interfaz y el estado privado del trabajo, fuera de los manifiestos y entregas.

### Ver el DOCX con LibreOffice

1. Instala **LibreOffice Writer** en tu equipo si no está disponible. report-gen lo detecta localmente; no lo descarga ni lo instala. Reabre el editor después de instalarlo.
2. Genera una exportación que incluya **Word** y espera a que termine. En **Exportaciones y descargas**, pulsa **Vista DOCX con LibreOffice** y después **Generar vista nativa**.
3. Revisa el PDF derivado, especialmente índice, tablas, URLs, leyendas y saltos de página. Puedes descargar el PDF y su recibo, que identifica motor, versión, SHA-256 del DOCX, revisión y hash del PDF.

La conversión toma el DOCX ya generado, también cuando está dentro de una entrega combinada; no reconstruye el documento desde el proyecto actual ni cambia la fuente. Una vista anterior sigue perteneciendo a su revisión original. Es una operación opcional con un proceso y perfil temporal separados: máximo 16 MiB de entrada, 32 MiB de PDF, 500 páginas y 180 segundos. Solo hay una conversión simultánea. Si el motor falta, falla o alcanza un límite, el editor lo informa sin atribuir una revisión completada.

La vista y su recibo son privados y caducan a los 15 minutos; el servidor limpia material caducado al operar o cerrarse. Cerrar el diálogo cancela la operación activa y solicita retirar sus temporales. No se guardan automáticamente en el proyecto. Las descargas que conserves siguen siendo privadas y debes administrarlas tú. **Esta vista acredita únicamente el resultado de LibreOffice sobre esos bytes: no es equivalencia ni aceptación de Microsoft Word.** La revisión nativa en Word sigue siendo una comprobación independiente.

Si tienes Windows y Microsoft Word de escritorio instalado y licenciado, puedes vincular esa comprobación al mismo DOCX: guarda únicamente ese documento en `word-input` y ejecuta `powershell -NoProfile -File .\scripts\verify-microsoft-word.ps1 -InputDirectory .\word-input -OutputDirectory .\word-output -ExpectedSourceReceipt .\docx-libreoffice-preview.json`. Usa una carpeta de salida vacía. El recibo descargado verifica el hash y conserva la revisión de origen antes de abrir Word; el script trabaja sobre una copia, actualiza campos, exporta un PDF y registra versión, métricas y hashes. Debes revisar después ese PDF: disponer del comando o del recibo de LibreOffice no demuestra que Word haya sido ejecutado.

### Inspeccionar un anexo PDF

En **Inventario de anexos → Analizar posibles secretos**, revisa las categorías y ubicaciones detectadas. Para PDF se muestran las páginas, objetos y caracteres examinados. Se inspeccionan texto extraíble, metadatos Info/XMP y cadenas de estructuras actuales, incluidos enlaces, anotaciones, formularios y JavaScript como texto estático. El análisis detecta presencia de acciones, imágenes y archivos incrustados; no ejecuta acciones, visita enlaces ni abre esos archivos.

El resultado nunca reproduce el valor sensible y se vincula al hash y revisión inspeccionados. El análisis es temporal; no se añade a la entrega ni a su manifiesto. Un estado «inspeccionado» significa que terminó ese alcance acotado, no que el archivo sea seguro. El alcance siempre es parcial y exige revisión manual: no hay OCR ni inspección completa de binarios incrustados o historial de revisiones incrementales. Los PDF cifrados, incluso con contraseña vacía, quedan sin inspeccionar. Los errores, límites y partes omitidas se indican expresamente.

Los límites incluyen 16 MiB por PDF, 200 páginas, 8000 objetos, 2 097 152 caracteres y 20 segundos, además de límites de profundidad y flujos de texto. **El análisis no censura, modifica ni autoriza el anexo.** Revisa la copia que realmente compartirás y marca expresamente su revisión e inclusión. Las alertas orientan la revisión; los requisitos de anexos obligatorios continúan bloqueando una entrega incompleta.

## Integración 0.41.0

**Entregar** reúne revisión, destinatario, vista previa y exportación. Los bloqueos tienen acceso a su origen; cambiar contenido u opciones invalida la vista previa. La exportación conserva la revisión comprobada y exige confirmar de nuevo los avisos cuando corresponde.

Las tablas extensas dentro de hallazgos pueden continuar por filas entre páginas, repitiendo su cabecera. Las tablas breves se conservan juntas. Una celda o un encabezado que exceda la altura útil sigue rechazándose con un diagnóstico; no se recorta contenido para forzar la salida.

Los borradores recuperables se amplían a edición masiva y formularios auxiliares de bibliotecas, importación, anotaciones y creación. Recuperar abre el formulario para revisarlo; nunca ejecuta cambios ni restaura aprobaciones. Los formularios del espacio de trabajo se distinguen de los de cada informe. Se mantienen los límites y los 30 días de retención del navegador.

La revisión visual permite **Guardar progreso en el proyecto**: página actual, notas y pendientes, vinculados al SHA-256 del PDF y a la revisión de origen. Guardar una copia privada del PDF es opcional. Sin ella debes volver a abrir el mismo archivo. Estas revisiones no se publican en los informes; sí viajan en respaldos e historial. Eliminar la revisión actual no elimina versiones anteriores.

Abre el asistente con `python scripts/install.py --gui --lang es`. Requiere Python 3.11 o posterior, Tkinter y una sesión gráfica. El asistente guía diagnóstico, carpetas, instalación y recuperación. Las actualizaciones se preparan en una carpeta nueva; el bloqueo de aplicación y datos impide ejecutarlas con el editor abierto. Se conservan Python y los requisitos del sistema: el asistente no es un instalador autónomo que incluya todas las dependencias.

La comprobación nativa de Microsoft Word continúa separada. El corpus incluye español, inglés y portugués; `--additional-projects RUTA` incorpora los tres proyectos complejos situados en `es/`, `en/` y `pt/`. Requiere Windows con Word de escritorio instalado y licenciado. Preparar el kit, validar DOCX o renderizar con LibreOffice no equivale a ejecutar Word.

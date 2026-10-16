# Cambios 0.38.0 (2026-10-16)

- Diagnósticos privados de importación y exportación con registro, línea, campo,
  hallazgo o coordenadas de tabla/evidencia cuando se conocen con certeza.
  Se conserva el error general si no hay localización inequívoca; los detalles
  no se copian a los hallazgos importados ni a manifiestos de entrega.
  Se conserva también el hallazgo al rechazar tablas PDF demasiado altas,
  incluso cuando el motor se ejecuta en un proceso separado.
- Vista PDF opcional del DOCX exacto de una exportación mediante LibreOffice
  instalado localmente. Incluye hashes, revisión y motor en un recibo privado;
  usa proceso/perfil temporal y caducidad de 15 minutos. No cambia el DOCX
  ni atribuye equivalencia o aceptación de Microsoft Word.
  La cancelación se conserva si el servidor aún no devolvió el identificador.
  La verificación optativa con Word admite vincular el DOCX al recibo de
  esta vista mediante su hash y revisión, sin atribuir una ejecución de Word.
- Inspección acotada de anexos PDF: texto extraíble, metadatos, anotaciones,
  formularios y otras cadenas de las estructuras actuales. Muestra categorías
  y ubicaciones sin reproducir valores. El resultado siempre exige revisión
  manual; no hace OCR, no ejecuta acciones ni modifica o autoriza anexos.
- Limpieza comprobada de dos helpers DOCX privados, un helper JS, cinco
  bindings ignorados, dos constantes y un import redundante, y 20 reglas CSS
  de controles retirados. Se preservan las llamadas con efectos, los protocolos
  de bibliotecas y los adaptadores públicos. La inspección no constituye una
  garantía universal de ausencia de código muerto.
- Nuevo caso ficticio Grupo Meridiano Logística (GML 1.0): 30 hallazgos,
  cuatro cuadernos de máquinas, 16 activos y 32 evidencias. La matriz prevista
  distingue 12 salidas completas en tres idiomas de 28 salidas de muestras
  para otros estilos y perfiles; no presenta 40 informes completos. La prosa
  redactada permanece en español al localizar las etiquetas EN/PT. Los estados
  de aceptación se registran por ejecución, sin declarar resultados anticipados.
- Guías ES/EN/PT actualizadas para los recorridos nuevos y sus límites.

# Cambios 0.37.1 (2026-10-16)

- Corregidas las imágenes enlazadas dentro de celdas de tablas Word: se conservan
  los destinos de imagen y leyenda, los fragmentos de URL y el texto circundante,
  también con varias figuras consecutivas.
  Los saltos de maquetación no forman parte de las etiquetas de los enlaces;
  el contrato normaliza únicamente los límites visuales de figura en celdas,
  manteniendo la detección de texto, imágenes y enlaces eliminados o alterados.
- El registro del visor PDF identifica la revisión como autodeclarada y aclara
  que no verifica identidad ni método; ya no atribuye automáticamente una
  revisión humana. Se conservan el autor, la decisión y el hash exacto del PDF.
- Corregido el guardado de importaciones Burp con referencias HTML: los
  destinos HTTP/HTTPS se extraen como texto nativo y se conservan al recargar
  el proyecto, sin alterar los hallazgos previos ni su estado de revisión.
- La búsqueda rápida actualiza los resultados de la consulta actual antes
  de ejecutar Enter o navegar con las flechas; descarta los resultados y
  temporizadores anteriores para evitar activar comandos obsoletos.
- Nuevo caso bancario ficticio reproducible Banco Horizonte Austral y recorridos
  de aceptación de exportaciones, interfaz y ciclo de vida del proyecto.
  La matriz distingue lo ejecutado de las dependencias externas pendientes.
- Guías actualizadas y corregido el número de documentos del kit Word opcional.

# Cambios 0.37.0 (2026-10-16)

- Emparejamiento manual de páginas PDF con cobertura completa y referencias
  explícitas a las páginas originales, incluidas las añadidas y retiradas.
  La inspección de geometría y hashes usa el mismo proceso aislado y sus límites.
- Registro opcional de revisiones como anexos JSON privados del proyecto:
  autor autodeclarado, decisión, nota, correspondencias y hashes, sin copiar
  automáticamente los PDF, el HTML, las imágenes ni los nombres originales.
  Los registros permanecen en historial y respaldos;
  no se borran automáticamente ni se incluyen por defecto en las entregas.
- Importación SARIF de reglas de extensiones autocontenidas, con selección
  coherente por índice/GUID, catálogos separados y procedencia del componente.
  Se conservan las huellas previas del driver y el estado sin verificar.
- Interfaz, mensajes y guías en español, inglés y portugués. Pruebas ampliadas
  de navegador y controles nativos Windows/macOS para las funciones nuevas.

# Cambios 0.36.0 (2026-10-15)

- Importación local de SARIF 2.1.0 con vista previa, selección, deduplicación
  y procedencia. Los resultados permanecen informativos y sin verificar;
  se distinguen los resultados excluidos y no se infiere CVSS.
- Comparación de páginas PDF renderizadas, con vistas anterior/posterior,
  diferencias resaltadas, cambios de dimensiones y páginas añadidas o retiradas.
  El HTML autónomo conserva hashes y el alcance de la comparación por posición.
- Procesamiento acotado y aislado de PDF, sin guardar los archivos en proyectos.
  Interfaz y mensajes en español, inglés y portugués.
- Corregida la documentación de publicación: siete controles obligatorios
  y seis documentos ficticios en el corpus opcional de Microsoft Word.
  La aceptación de Word sigue requiriendo una ejecución real en un equipo apto.
- Corregido el aislamiento en macOS: techo de crecimiento virtual y supervisor
  de memoria residente/huella física con muestreo, descritos explícitamente.
  Las pruebas nativas exigen rechazo real de reservas y terminación del proceso.
- Las pruebas de navegador esperan recepción del servidor y cierre del diálogo;
  su inicialización no se ejecuta en los PDF aislados mediante sandbox.

# Cambios 0.35.0 (2026-10-15)

- Recuperados los tres casos Estuario originales y su auditoría reproducible
  de doce exportaciones. La publicación exige además la aceptación trilingüe
  y la revisión automática con LibreOffice estable del mismo commit.
- El verificador PDF distingue los glifos vacíos de composición Unicode,
  corrobora guiones con lectores independientes y conserva los separadores
  de las celdas. Las tablas con valores repetidos admiten una asignación
  completa sin agotar la búsqueda; se sigue rechazando texto perdido.
- Los guiones partidos de PDF nativos de LibreOffice se corroboran también
  en fuentes simples con mapas Unicode de un byte. Los mapas parciales solo
  se admiten con prueba independiente de la fuente TrueType incrustada, el
  código del glifo y su posición; no se reconstruye texto desde lo esperado.
- Los rótulos generados «Causa raíz» y «Acción común» son encabezados
  semánticos y conservan la unión con el contenido siguiente en DOCX,
  evitando títulos huérfanos sin alterar el Markdown escrito por el autor.
- Diez errores internos de composición y regiones PDF disponen de mensajes
  explícitos en español, inglés y portugués y pasan el control del catálogo.
- El apéndice describe referencias documentadas sin atribuir acceso ni
  recolección comprobada. Corregidas las etiquetas españolas de evidencia
  y confidencialidad; las notas redactadas por el autor se conservan.
- Recuperadas las imágenes portuguesas del tutorial y las miniaturas de
  páginas reales de las plantillas. Las pruebas de perfiles exigen ES/EN/PT.
- Nimbus crea la demostración en el idioma de la interfaz. Las ediciones
  editoriales inglesa y portuguesa conservan los doce hallazgos, las dieciocho
  evidencias y las referencias técnicas, con diagramas ficticios localizados
  y paquetes reproducibles; la edición española original se conserva.
- Renovadas las veintiuna capturas reales del tutorial, con procedencia y
  hashes registrados. La vista de entrega incluye todos sus controles.
- Las comprobaciones HTML en Windows leen UTF-8 de forma explícita.
- Portugués de Brasil en la interfaz, los mensajes del servidor, el tutorial,
  los catálogos de plantillas y las exportaciones PDF, DOCX, Markdown y HTML.
  La clave interna es `pt`; se admite el alias `pt-BR` en las entradas de idioma.
  Los documentos publican la etiqueta `pt-BR` en sus metadatos de idioma.
- Un selector explícito sustituye la alternancia binaria de la interfaz.
  El idioma del informe es independiente; cambiar idioma no traduce ni altera
  el contenido redactado, sus evidencias ni la revisión guardada del proyecto.
- Los títulos de secciones se actualizan al cambiar el idioma del informe,
  conservando el foco en el control de metadatos.
- Markdown conserva la introducción del apéndice en los informes por secciones;
  antes el comprobador detectaba su ausencia y rechazaba la entrega incompleta.
- La revisión editorial distingue el marcador `TODO` de la palabra portuguesa
  «todo», evitando avisos incorrectos sobre texto de evaluación pendiente.
- Guía y bienvenida de GitHub en portugués; los comandos de inicio, diagnóstico,
  migración, creación y firma admiten mensajes en los tres idiomas.

# Cambios 0.34.5 (2026-10-13)

- El sondeo de exportaciones se suspende al salir de la página y se reanuda
  al restaurarla, evitando peticiones tardías en WebKit sin cancelar las tareas.
- Las etiquetas del inspector de publicación y la vista previa, y el nombre
  accesible de validar, se actualizan al cambiar o restaurar el idioma ES/EN.
  La preferencia de interfaz no modifica el contenido ni la revisión del informe.
- Los selectores nativos adoptan el esquema oscuro o claro del editor. Se corrige
  el contraste del texto sobre el fondo del control cerrado en WebKit para Linux,
  conservando su apariencia y navegación nativas.
- El recorrido de Safari nativo amplía la cobertura a importar una copia de Nimbus
  mediante la API del navegador, editar y autoguardar, recargar y exportar HTML.
  Comprueba revisión, bytes y contenido; no cubre el selector de archivos del
  sistema, Safari móvil ni la recuperación de borradores sin guardar.
- El exportador DOCX marca por defecto los literales técnicos ASCII elegibles
  con el idioma privado `zxx-ZZ-x-rgwrap`, conservando texto, estilos y enlaces.
  El complemento opcional aprovecha esa marca para ajustar las líneas en
  LibreOffice oficial 26.2.6.3 para Linux x86-64, con instalación y reapertura
  comprobadas. Se construye desde las fuentes y requiere instalación expresa;
  el DOCX sigue siendo editable sin él. No es una reparación portable a cualquier
  editor: la instalación falló en LibreOffice 24.2.7.2 de Ubuntu y no se acredita
  Microsoft Word ni LibreOffice para Windows o macOS. Las guías detallan el alcance.
- El índice Word reserva espacio para sus números de página incluso cuando
  un título llena casi toda la línea; los campos PAGEREF siguen siendo nativos.
- Se corrige la pérdida parcial del área enlazada al guardar en LibreOffice
  un enlace DOCX externo con fragmento y cambios de escritura o formato.
  Los tramos contiguos conservan sus caracteres, estilos y destino completo;
  no se insertan separadores ni se modifica la URL para evitar ese fallo.
- Las leyendas extensas pueden continuar por páginas sin reducir sus imágenes
  hasta volverlas invisibles. Se conserva el texto y el tamaño de las figuras
  con leyendas breves.
- HTML, PDF y Markdown conservan los saltos de línea de las leyendas. Markdown
  también exporta figuras con leyenda vacía sin introducir asteriscos visibles.
  El HTML portátil y la vista previa Markdown del editor conservan esas líneas
  también con texto ampliado y en pantallas estrechas.
- Las tablas de retest dentro de citas o listas fluyen por filas, igual que
  las tablas directas. El recuento inicial en Word permanece junto a la tabla.
  Los retests sin fecha omiten el separador vacío del encabezado.
- La revisión detecta entidades Markdown que producirían caracteres XML no
  válidos, indicando el campo antes de exportar. El código literal y las
  entidades escapadas conservan sus caracteres.

# Cambios 0.34.4 (2026-10-13)

- El índice DOCX utiliza entradas enlazadas y campos PAGEREF independientes,
  calculados por el editor. LibreOffice ya muestra las cifras y las actualiza
  al cambiar la paginación. Se retiran los campos TOC/TC redundantes; añadir,
  renombrar o reordenar entradas requiere volver a exportar desde report-gen.
- Los capítulos del cuerpo fluyen de forma continua en PDF y Word. Portada e
  índice mantienen sus páginas propias, y las evidencias conservan tamaño y
  orden. No se fuerzan páginas nuevas que dejen referencias aisladas.
- Las tablas de verificación técnica pueden continuar por filas en PDF,
  manteniendo su título y cabecera. Ya no saltan completas por compartir la
  agrupación de las notas de retest; las notas narrativas conservan su protección.
- El PDF aprovecha también la primera línea disponible para identificadores
  ASCII extensos después de una etiqueta, conservando sus caracteres y los
  saltos normales del texto Unicode.
- Markdown incluye el gráfico de severidades como PNG y la leyenda de alcance.
  El contrato comprueba imagen, conteos, texto y posición por separado de las
  evidencias; rechaza pérdidas, sustituciones y desplazamientos.
- Las tablas simples del HTML portátil se presentan por registros en anchos
  reducidos, conservando estructura y encabezados. Las tablas complejas mantienen
  desplazamiento local. Los ordinales extensos dejan espacio al texto ampliado.
- El gráfico SVG expone sus cinco conteos como alternativa accesible. Su revisión
  de contraste mide rellenos y fondos reales, sin usar el color CSS heredado.
- La aceptación LibreOffice comprueba cifras del índice contra páginas de destino
  y exige una prueba de actualización tras cambiar el contenido. CI instala
  Tesseract para ejecutar la regresión OCR real y añade recorridos ES/EN en Safari
  de macOS mediante SafariDriver, por separado del motor WebKit.

# Cambios 0.34.3 (2026-10-12)

- El resumen automático describe hallazgos y severidades registradas sin afirmar
  que todos fueron identificados mediante una evaluación ejecutada. Las entradas
  de máquinas se describen como registros, sin inferir un compromiso demostrado.
- La sección automática de activos pasa a llamarse «Inventario de activos» /
  «Asset inventory». La presencia de un objetivo no implica cobertura realizada;
  los estados de prueba siguen en su sección de cobertura y limitaciones.
- El enfoque predeterminado deja de atribuir reproducción manual a todos los
  hallazgos. Remite a los estados técnicos, evidencias y límites documentados;
  conserva el enfoque que el autor haya escrito expresamente.
- README y guías ES/EN explican estos límites de los textos automáticos. No se
  cambia la severidad, verificación ni el contenido de las fichas guardadas.

# Cambios 0.34.2 (2026-10-12)

- El HTML portátil aprovecha la línea disponible también con URLs literales
  e identificadores ASCII largos después de una etiqueta. El ajuste se limita
  a esos tokens, conserva exactamente el texto y los enlaces, y no cambia los
  saltos de las palabras normales ni las salidas PDF, Word o Markdown.
- Conserva la alineación izquierda, centrada y derecha de las tablas Markdown
  en HTML, PDF y Word. La alineación procede del parser; no se admite CSS
  arbitrario ni se habilita HTML sin filtrar.
- El verificador PDF comprueba títulos, encabezados, párrafos, código, celdas,
  listas y metadatos dentro de la región de cada hallazgo canónico. Una copia
  del título en el índice o el resumen ya no suple un encabezado perdido.
  La presencia regional no certifica el orden visual ni la pertenencia de
  cada imagen o evidencia; los documentos no canónicos conservan el control
  global explícito.
- La corroboración de guiones PDF valida los objetos dibujados en la página,
  sin rechazar recursos Form que solo estén declarados y no se utilicen.
  Los objetos Form ejecutados siguen requiriendo corroboración; la prueba no
  acepta texto ambiguo ni lo completa a partir del contenido esperado.
- Evita desbordamientos PDF de URLs escritas como texto común, también tras
  formato en línea, en listas y en tablas. Añade puntos de corte opcionales
  únicamente a la URL y conserva sus caracteres. El verificador prueba primero
  la continuación estricta entre líneas antes de una búsqueda genérica, evitando
  falsos límites con URLs largas después de muchos párrafos parecidos.
- Las cadenas narrativas sin espacios, como hashes e identificadores largos,
  se ajustan al ancho disponible sin alterar sus caracteres. Las palabras
  corrientes conservan los mismos saltos de línea en los seis temas.
- La ventana de comprobaciones traduce el nuevo contador PDF a español e inglés
  y mantiene explícito que no certifica la asociación visual de las evidencias.
- El enlace a la guía en «Preparar entrega» usa el color accesible del editor
  en los temas oscuro y claro, conservando su subrayado.
- Corrige un falso rechazo de evidencias Markdown: el texto de contexto
  conserva los encabezados de pasos que proceden de rótulos en línea. Se
  mantiene la comparación exacta de contexto y el rechazo de imágenes movidas.
- Un supervisor POSIX conserva el grupo del trabajo hasta la limpieza y
  comunica el resultado del trabajador por separado. Funciona sin
  `waitid`/`WNOWAIT`, incluidos Python 3.11/3.12 en macOS, y limpia el grupo si
  desaparece el padre. El trabajo privado de Windows se conserva.
- Añade aceptación nativa macOS, render de Word con LibreOffice estable y
  recorridos de navegador WebKit. Los seis workflows son obligatorios antes
  de publicar una versión. WebKit no equivale a Safari; LibreOffice no equivale
  a Microsoft Word de escritorio.
- Corrige la referencia residual a 120 segundos en los README: el presupuesto
  PDF vigente es 300 segundos, configurable entre 30 y 600.
- Se conserva el texto literal de las URLs. El salto anticipado de algunas
  URLs en LibreOffice sigue siendo un límite del renderizador: no se insertan
  caracteres invisibles ni se cambian las evidencias para esconderlo.

# Cambios 0.34.1 (2026-10-12)

- El verificador PDF reserva apariciones independientes para los encabezados escritos y los títulos de hallazgos. Evita que un título repetido o contenido dentro de otro supla una aparición ausente y acepta títulos íntegros que se envuelven entre líneas. Conserva el presupuesto de trabajo y el alcance de presencia textual global: no certifica posición ni asociación visual.
- La cola termina los descendientes de un trabajador que ya finalizó. En POSIX con `waitid` y `WNOWAIT` conserva el identificador del grupo hasta limpiarlo; en Windows utiliza un Job Object privado y no permite que el trabajador continúe antes de asignarlo. Al cerrar, impide nuevas incorporaciones y espera los handles de sus procesos antes de retirar archivos. Los errores de limpieza se registran sin detener el hilo de la cola. Las regresiones usan hijos y nietos reales y un proceso ajeno que debe permanecer vivo.
- En POSIX sin `waitid`/`WNOWAIT`, incluido macOS con Python 3.11/3.12, se mantiene la compatibilidad y el límite anterior de limpieza tras la salida anticipada del trabajador. No se señala un grupo cuyo identificador podría haberse reutilizado. La prueba nativa de macOS sigue pendiente.
- Crear un proyecto desde el tutorial conserva el botón original para devolverle el foco al cerrar la galería, cancelar el formulario o volver atrás. Se comprueban los tres recorridos en español e inglés. Si una captura no carga, su nombre accesible también anuncia que no está disponible, en lugar de ofrecer ampliarla.
- Word separa la línea del encabezado de las tablas que comienzan una página. Ajusta únicamente la distancia del encabezado; conserva los márgenes y el espacio disponible para el cuerpo del informe. Al iniciar un capítulo, retira el párrafo espaciador totalmente vacío que sigue a una tabla y podía provocar una página vacía; preserva párrafos con contenido, propiedades o marcadores.
- Las cabeceras PDF reservan 3 mm entre la línea divisoria y el cuerpo en los seis temas. Evita que tablas, código o figuras que continúan al principio de una página toquen la línea, sin desplazar el contenido ni modificar los márgenes del cuerpo.
- El índice PDF reutiliza el texto extraído y verificado de la primera pasada de WeasyPrint. Evita volver a analizar el mismo archivo con otro lector; conserva las dos maquetaciones, las validaciones completas y el lector alternativo para Chromium.
- El presupuesto del motor PDF pasa explícitamente de 120 a 300 segundos por defecto para admitir informes extensos. `REPORT_GEN_PDF_TIMEOUT` permite configurarlo entre 30 y 600 segundos; los valores inválidos se rechazan antes de lanzar el proceso. Conserva la cancelación, las dos pasadas, los controles de contenido y la escritura atómica. La regresión de 72 URLs de 0.34.0 sigue comprobándose con el presupuesto explícito de 120 segundos.
- Las guías dejan de presentar como pendiente el coste de exportación de 72 URLs largas corregido en 0.34.0. Se elimina una rama privada de búsqueda PDF sin consumidores; no se añaden documentos residuales de auditoría.
- Persiste el salto anticipado de algunas URLs literales de DOCX en LibreOffice. No se modifican sus caracteres o destinos para disimularlo; la revisión en Microsoft Word nativo permanece pendiente.

# Cambios 0.34.0 (2026-10-12)

- Tutorial visual opcional de seis pasos, con 14 capturas reales ES/EN de datos ficticios, acceso permanente desde el menú, ampliación accesible, progreso local y reinicio independiente del proyecto. La invitación inicial se puede omitir; el recorrido sigue disponible sin almacenamiento del navegador.
- Las oportunidades de salto de las URLs del PDF se compactan solo en la entrada privada del renderizador. Evita miles de elementos de composición por tabla sin modificar YAML, HTML portátil, DOCX ni Markdown. Se desactivan las ligaduras opcionales solo en la URL transformada para conservar cada letra al copiarla; las regresiones comprueban texto con dos extractores independientes, destinos, geometría y Unicode en los seis diseños.
- La regresión de 72 URLs literales de más de 300 caracteres se exporta en ambos idiomas dentro del límite original de 120 segundos, conservando los dos pasos de maquetación, controles de contenido, tablas y escritura atómica. Esto corrige ese caso concreto, no elimina el límite para cualquier informe o carga del sistema.
- Se corrige un falso rechazo del verificador PDF cuando una URL literal de un párrafo continúa en la página siguiente. La comprobación utiliza límites reales de línea y páginas adyacentes, conserva los rangos consumidos y rechaza fragmentos alterados o ausentes; no relaja la comparación de la prosa ni certifica maquetación.
- El comprobador opcional de Microsoft Word admite únicamente los campos SEQ de numeración propios de report-gen y verifica sus instrucciones y resultados. Los fragmentos de enlaces externos ya no se exigen como marcadores locales. El kit incluye un caso específico de URLs literales y ordinales grandes para revisión en Word.
- La guía aclara que el OCR local es opcional y no censura automáticamente. No se añaden documentos residuales de auditoría al proyecto.
- Permanece el salto anticipado de algunas URLs DOCX en LibreOffice: las variantes nativas probadas no lo corrigen de forma portable. No se insertan caracteres invisibles, saltos manuales ni nombres alternativos para disimularlo. Las comprobaciones de OOXML y LibreOffice no sustituyen la aceptación visual en Microsoft Word nativo, que sigue pendiente.

# Cambios 0.33.2 (2026-10-12)

- El HTML portátil reserva la sangría de las listas ordinarias según sus dígitos y el tamaño de la fuente. Evita recortar marcadores como 73 o 973 en móvil al ampliar el texto al 200 %. Conserva los contadores nativos, el texto y el desplazamiento local de las listas de muchos dígitos. Las viñetas también escalan su sangría con el texto.
- La regresión de navegador comprueba marcadores de dos, tres y diez dígitos en 320, 390 y 1440 px, con texto al 100 y 200 %. No se modifican los renderizadores PDF, DOCX ni Markdown.

# Cambios 0.33.1 (2026-10-12)

- La tabla de activos de Word reserva más ancho a los nombres, para mantener completos identificadores corrientes como DIRECTORY-05 y RECOVERY-12. Conserva el espacio de tipo y notas y todos los valores; HTML y PDF mantienen sus proporciones.
- Los puntos de ajuste visual de URLs del PDF dejan de generar anotaciones de enlace sin área. Se conservan los enlaces visibles y sus destinos literales, la composición y el texto; se evita que cientos de anotaciones vacías por URL ralenticen los informes extensos.
- El aviso de una tabla de hallazgo demasiado grande indica alternativas verificables: dividirla, reducirla o moverla a una sección narrativa o anexo. Aclara que el procedimiento del mismo hallazgo conserva el mismo límite de paginación.
- Al superar los 120 segundos, la exportación PDF muestra un mensaje ES/EN con alternativas sin exponer el comando ni las rutas del proceso. Mantiene intacta la salida anterior. Cada ejecución aísla sus pases intermedios para retirarlos también si el proceso se interrumpe por tiempo o falla.
- Las regresiones comprueban enlaces visibles, destinos codificados, preservación del contenido, tablas en las tres ubicaciones, fallos del proceso y limpieza que respeta otros archivos. Se conservan los documentos útiles del proyecto y los límites de revisión en Word nativo y ajuste de URLs en LibreOffice.

# Cambios 0.33.0 (2026-10-12)

- Crear un proyecto comienza en una galería visual con filtros por propósito y proveedor, búsqueda, muestras de portada/resumen/página técnica y comparación ES/EN. El formulario posterior conserva título, cliente, carpeta, idioma y estructura al volver a la galería. La estructura inicial no sustituye la apariencia elegida.
- Se corrigen la selección invisible al reabrir una búsqueda vacía, el reinicio de la variante al pulsar de nuevo la misma tarjeta y los textos que excedían las tarjetas o controles en móvil. Explorar o cancelar no crea proyectos; los fallos de red conservan los datos para reintentar.
- Guardar o duplicar una plantilla personal restablece los filtros incompatibles y muestra la tarjeta guardada, conservando su variante. Los bloques de código cercados dentro de listas o citas mantienen su estructura, espacios, tabulaciones y líneas vacías; dejan de convertirse en código en línea con el nombre del lenguaje visible.
- Se añade Enterprise Control Review, una estructura empresarial de ocho apartados para diseño y operación de controles, muestreo, excepciones y retest. Su composición editorial alinea a la izquierda la portada. El catálogo contiene 30 perfiles especializados, cuatro de ellos empresariales, además de seis diseños generales; los perfiles comparten seis composiciones, no 30 diseños estructurales distintos.
- Los campos Markdown permiten insertar un enlace con nombre descriptivo y destino HTTP/HTTPS literal. Un apartado opcional de la revisión identifica ubicaciones con URLs visibles de al menos 96 caracteres en la publicación, sin modificar la fuente, exponer la URL en el aviso ni alterar la puntuación de preparación. No confunde un destino largo con una etiqueta visible larga.
- Las portadas Word de perfiles con ilustración reservan más margen. En los casos verificados con títulos largos y los tres recursos opcionales, los metadatos permanecen en la primera página. Se conserva el tamaño de letra y de imagen. La celda de relleno vacía de las portadas HTML apiladas deja de ocupar una fila; se conservan los cinco campos reales y la composición de escritorio.
- El código breve del HTML portátil prefiere separar palabras e identificadores por los espacios disponibles; evita partir el último dígito de una IP cuando el token cabe entero. Las URLs literales y los comandos conservan el aprovechamiento del ancho y la copia exacta del texto.
- Se retiran el generador de motivos SVG y dos reglas CSS sin consumidores. La comparación de los 116 estados anteriores (29 perfiles, dos variantes, dos idiomas) conserva el HTML visible; los metadatos de apariencia guardados mantienen compatibilidad.
- Las regresiones cubren el flujo real de galería, reintentos, cambios rápidos de vista previa, preservación de enlaces, celdas de portada y la nueva estructura empresarial. README y guías describen el flujo y sus límites; se conservan los documentos útiles del proyecto.
- Límite abierto: LibreOffice sigue adelantando algunos saltos de URLs literales de DOCX. Ocho controles nativos de esta ronda conservaron los mismos cortes. Los enlaces descriptivos son una alternativa voluntaria de redacción, no una corrección del motor. No se insertan caracteres invisibles ni saltos artificiales. La revisión en Microsoft Word nativo sigue pendiente; las conversiones visuales locales usan LibreOfficeDev 26.8.0.0.alpha0.

# Cambios 0.32.3 (2026-10-11)

- Word conserva los ordinales de listas cuyo inicio supera 65.535 mediante campos `SEQ` actualizables, evitando el truncamiento observado en LibreOfficeDev 26.8. Las listas que empiezan dentro del rango nativo mantienen su numeración automática, incluso cuando lo cruzan. El primer campo fija el inicio y los siguientes incrementan la misma secuencia; se conservan resultados visibles para lectores que no recalculan campos.
- Las listas decimales de Word reservan espacio según sus dígitos y tamaño de letra para separar marcador y texto. Las continuaciones, listas anidadas, tablas, figuras y código conservan ese eje sin reducir la fuente. Las viñetas mantienen su geometría.
- Cuando un elemento de Word comienza con código, tabla o cita, su marcador permanece con el primer bloque. Evita un número aislado al pie de la página sin obligar a mantener todo el bloque o toda la lista en una sola página.
- Los controles de HTML y Markdown comprueban los ordinales efectivos, además del contenido de cada elemento. Word compara las definiciones nativas o las instrucciones y resultados de los campos de secuencia, vinculados a su lista. Un inicio alterado o una caché incoherente bloquea la entrega y conserva el archivo anterior. El verificador PDF sigue sin acreditar ordinales ni maquetación; requieren revisión visual.
- El HTML portátil responde al ancho real de lectura al ampliar: reduce marcos anidados y rellenos, apila metadatos y evita que la barra fija ocupe buena parte de una pantalla estrecha. Conserva tamaño de letra, contenido literal, marcadores, enlaces y desplazamiento local de tablas o bloques que lo necesitan. El relleno compacto deja de reaparecer al imprimir por una regla tardía de CSS.
- Los logos e imágenes personalizados de la portada HTML respetan tanto su límite visual como el ancho disponible, también en pantallas estrechas con ampliación. Se retiran cuatro selectores sin emisor del CSS portátil.
- El PDF mantiene juntas las etiquetas breves en negrita y sus listas de hasta cuatro elementos cortos, como los activos afectados. Evita dejar una o dos IP aisladas en la página siguiente; las listas largas, anidadas o con bloques e imágenes siguen pudiendo dividirse. La misma preparación se aplica en WeasyPrint y Chromium.
- El HTML adopta la fuente incrustada cuando termina de cargar, en vez de conservar de forma intermitente una fuente de sustitución. Evita diferencias persistentes de altura y ajuste de línea en una misma plantilla según la carga del navegador.
- Retirado el correo personal de los metadatos del paquete. Los tres proyectos de demostración usan identidades y contactos ficticios, direcciones de documentación y marcadores no operativos; sus evidencias gráficas son nuevas ilustraciones rotuladas como simulación.
- README y guías explican la edición de listas excepcionales con campos y los límites de la comprobación. Se retira del README la cronología duplicada, conservada en este registro, y la actualización manual deja de remitir a una versión antigua.
- Límites: algunas URL de DOCX siguen envolviéndose prematuramente en LibreOffice; ocho alternativas nativas adicionales no resolvieron el comportamiento. No se insertan caracteres invisibles ni saltos artificiales para ocultarlo. Las pruebas visuales de esta ronda usan LibreOfficeDev 26.8.0.0.alpha0; la revisión en Microsoft Word nativo sigue pendiente. LibreOffice estable 26.8.1.1 se obtuvo de su distribución oficial y se verificó, pero su conversión mínima no funcionó en este entorno: no se le atribuye una validación visual.

# Cambios 0.32.2 (2026-10-11)

- Las filas narrativas de PDF que realmente superan una página se vuelven a maquetar con fragmentación permitida. Conservan el título acompañado y los encabezados de columna en las continuaciones. Las filas normales no requieren una segunda maquetación; las tablas protegidas de hallazgos conservan sus comprobaciones.
- Los títulos PDF con identificadores o URL extensas admiten ajuste dentro del margen. La cabecera de hallazgo permite reducir el ancho del título para conservar visibles el identificador y la etiqueta de severidad o dirección.
- Word estima la altura de las tablas antes de encadenar todas sus filas. Una tabla de pocas filas con celdas extensas puede continuar sin dejar un gran hueco en la página anterior. El espaciado compacto del cuerpo deja de aumentar por herencia la altura de las celdas de Table Grid; se conserva el formato explícito de cada párrafo.
- Las tablas dentro de listas de Word respetan la sangría y el ancho disponible de su nivel. Los bloques de código anidados consideran ese ancho reducido antes de solicitar mantenerse en una sola página.
- Las listas breves de Word precedidas por una etiqueta en negrita permanecen juntas cuando tienen hasta cuatro elementos y texto corto. Evitan páginas casi vacías con una única viñeta de activos afectados; listas largas, anidadas o con imágenes conservan su posibilidad de continuar.
- Los capítulos Word y el contenido posterior al índice solicitan el salto de página en su propio encabezado. Se elimina el párrafo vacío de salto que podía desbordarse cuando el contenido anterior llenaba exactamente una página y dejar otra página sin contenido.
- Eliminada una rama inalcanzable de la composición de metadatos Word; se conserva la separación explícita entre bloques.
- Las citas y listas anidadas del HTML portátil usan sangrías adaptables para evitar que el ancho útil colapse en pantallas estrechas con ampliación. Se conservan texto, marcadores, orden, enlaces y controles de lectura. Las listas con numeraciones iniciales largas reservan espacio para el marcador; cuando no caben en HTML disponen de desplazamiento local por teclado y no ensanchan la página. El PDF reserva su sangría dentro del margen imprimible.
- Los logos de proveedor del HTML portátil conservan su proporción y se ajustan al ancho de la portada en móvil y al ampliar al 200 %. La identidad puede ocupar varias filas sin recortar el logo.
- La verificación PDF impide que una misma aparición física justifique valores distintos de celdas, listas o párrafos dentro de cada categoría. Conserva alternativas de coincidencia y límites de trabajo; una comprobación inconclusa no reemplaza la salida anterior. No acredita asociación entre bloques, geometría ni espacios literales.
- Nuevas regresiones con tablas extensas, anidación, encabezados repetidos, documentos realmente alterados y conservación de exportaciones completas. Chromium ejecuta los nuevos casos de anidación y ampliación.
- Límites conocidos: LibreOffice aún puede adelantar algunos saltos de URL en DOCX. LibreOfficeDev 26.8.0.0.alpha0 también trunca inicios de lista grandes al importar DOCX (65536 aparece como 0 y 1234567890 como 722), incluso con `startOverride`; el XML conserva los valores originales. No se altera el texto ni se atribuye una validación realizada en Microsoft Word nativo o LibreOffice estable.

# Cambios 0.32.1 (2026-10-11)

- El PDF normaliza el interlineado y la separación de los títulos de sección y los encabezados Markdown. Ejecutivo y Laboratorio dejan de sumar un relleno inferior desproporcionado al margen del título.
- Los marcos de las figuras siguen la proporción y el tamaño visible de la imagen, incluso al alcanzar el límite de altura. Desaparecen las bandas vacías laterales sin recortar, recomprimir ni modificar la evidencia fuente.
- El código y las URL literales del PDF disponen de oportunidades de ruptura visual para utilizar el ancho disponible. La preparación pertenece únicamente al renderizador PDF; conserva el texto fuente, los saltos explícitos y los destinos. Los grafemas Unicode no se separan.
- El HTML portátil aplica el ajuste continuo a código y etiquetas que son URL literales; los enlaces con texto descriptivo conservan el ajuste normal de prosa. Las listas de pasos y el relleno del código mantienen un ancho útil en pantallas estrechas con texto ampliado.
- Word calcula las figuras según la sangría de la lista y el ancho interior de la celda. Fija explícitamente las distancias de los dibujos en línea para evitar desplazamientos implícitos en LibreOffice. Las leyendas reservan espacio según su ancho real.
- La verificación PDF exige ocurrencias físicas independientes para las líneas de código: una línea envuelta ya no puede justificar simultáneamente otro bloque ausente. Una búsqueda ambigua que agota su presupuesto de trabajo detiene la entrega con un error de verificación no completada y conserva la salida anterior. Conserva los límites de presencia global: no certifica asociación entre bloques, orden global ni espacios literales de PDF.
- Las regresiones incluyen documentos realmente incompletos, URLs con puntuación, tablas y listas con imágenes anchas, conservación de imágenes y comprobaciones de texto copiado. La aceptación Chromium ejecuta también los nuevos casos de ajuste de enlaces.
- Límite conocido: LibreOffice sigue adelantando algunos saltos de URL en DOCX. No se añaden caracteres invisibles ni saltos artificiales al contenido para simular un ajuste correcto. Microsoft Word nativo requiere su propia revisión.

# Cambios 0.32.0 (2026-10-11)

- La biblioteca añade cuatro perfiles de práctica e investigación para CRTO, CRTL, BTL1 y BTL2, y tres estructuras empresariales: evaluación ejecutiva, respuesta a incidentes y validación Purple Team. Cada perfil incluye orientación ES/EN, referencias y apartados propios. No se atribuyen requisitos de examen ni colores oficiales sin respaldo.
- Los filtros de familias se generan desde el catálogo. Los perfiles sin un recurso de marca incluido conservan su identidad textual sin intentar cargar un logotipo inexistente.
- Las secciones personales con una sola traducción conservan su título y contenido al crear un informe en el otro idioma, tanto en el backend como en la biblioteca.
- Actualizadas las referencias de entrega de HTB para indicar inglés y el límite consultado de CWEE, junto con su paso de cifrado externo. El catálogo distingue prácticas, informes y referencias históricas; la guía vigente de cada proveedor prevalece.
- La verificación PDF exige líneas lógicas completas de código, admite su envoltura física y comprueba su multiplicidad global. Rechaza prefijos, sufijos y líneas repetidas ausentes que antes podían pasar como coincidencias parciales.
- HTML, Word y Markdown comparan las unidades completas y ordenadas de portada: título, subtítulo y pares de etiqueta y valor. Una subcadena o el contenido de otro campo ya no puede suplir un metadato alterado.
- La portada Word separa marca y clasificación en columnas cuando su anchura medida no permite compartir una línea. Las continuaciones de una clasificación larga mantienen su alineación y no caen bajo la marca. Las portadas habituales conservan su estructura.
- Las transcripciones Word cuya altura estimada supera una página permiten continuaciones entre páginas; evitan desplazar el bloque completo y dejar su título aislado. Los fragmentos cortos conservan la instrucción de mantenerse juntos.
- Las muestras inglesas de los seis diseños generales muestran nombres traducidos; las miniaturas se generan desde las exportaciones reales.
- Las pruebas de regresión incluyen archivos alterados, conservación de exportaciones válidas y recorridos de creación, aplicación y personalización de plantillas. Los controles PDF siguen sin certificar asociación entre bloques, orden global ni maquetación; estas comprobaciones requieren revisión independiente.

# Cambios 0.31.5 (2026-10-11)

- Al deshacer un hallazgo eliminado, el editor conserva sus evidencias y retests pero descarta referencias a activos o grupos que se borraron después; informa del ajuste.
- Duplicar o importar hallazgos JSON crea una identidad abierta y sin verificar, sin heredar retests ni comunicaciones de corrección del original. Conserva responsable y plazo como datos de planificación. Los respaldos completos mantienen sus estados e historial.
- Recuperar un borrador conserva el hallazgo seleccionado por UID aunque cambie de posición. Si desaparece el hallazgo o el capítulo abierto, vuelve al informe.
- Word separa figuras, leyendas y prosa dentro de enlaces, énfasis, citas y listas. Conserva formato, tamaño y destinos nativos de la imagen y de la leyenda. Los enlaces que cruzan una figura se verifican mediante sus fragmentos originales, en orden y sin contenido interpuesto.
- Las listas de Word conservan el marcador y la sangría cuando un ítem comienza con una figura. La verificación reconstruye sus continuaciones desde la estructura original, incluidas varias figuras enlazadas, sin aceptar traslados entre ítems ni pérdida de texto.
- El PDF mantiene en una página las envolturas de cada línea lógica de código y evita dividir transcripciones cortas de hasta cuatro líneas. Los bloques largos continúan en páginas posteriores. Una línea más alta que la página imprimible se rechaza antes de reemplazar la salida anterior.
- La cabecera PDF reserva columnas y separación para marca, título y metadatos en los seis temas; permite ajustar líneas sin recortar el contenido ni cambiar los márgenes del cuerpo.
- La verificación PDF incluye presencia y multiplicidad de celdas de tablas y elementos de listas, que antes podían quedar fuera del contrato textual. Los límites de palabra evitan coincidencias dentro de otra palabra. La presencia sigue siendo global y no certifica asociación de bloques, geometría ni significado.
- En mapas Unicode explícitos compatibles, el lector PDF recupera un guion ASCII de final de línea sólo si los códigos reales del archivo, su mapa y un segundo lector corroboran todos los caracteres. No toma caracteres del texto esperado. Guiones blandos, mapas no admitidos o lecturas divergentes mantienen un rechazo explícito.
- La comprobación de portada usa la geometría textual de la primera página para separar títulos y subtítulos largos. El contenido de páginas posteriores no puede suplir metadatos alterados de la portada.
- Los diagnósticos internos nuevos del PDF y la plantilla de texto ausente usan el sistema bilingüe de mensajes; se conservan las condiciones de rechazo y los valores informados.
- Las regresiones incluyen archivos realmente alterados, conservación de la salida anterior, listas y tablas extensas, enlaces con figuras y recorridos del editor con almacenamiento fallido y recuperación. La inspección visual de las entregas sigue siendo necesaria.

# Cambios 0.31.4 (2026-10-11)

- La búsqueda compara texto Unicode normalizado y espacios coherentes: los acentos equivalentes y las frases partidas entre líneas se encuentran sin alterar el contenido guardado.
- El resaltado traduce los índices de la comparación a los caracteres mostrados y recorta por grafemas completos. Evita desplazar coincidencias tras letras cuya minúscula cambia de longitud o partir emojis y secuencias combinadas.
- Las figuras de Word reservan espacio según su leyenda y la mantienen unida a la imagen. Las imágenes insertadas en párrafos Markdown separan texto anterior, figura y continuación, también dentro de listas, sin dejar la prosa pegada al borde inferior.
- Las tablas largas de Word conservan juntas sus tres últimas filas cuando su altura estimada cabe en la página, sin encadenar todo el inventario ni forzar colas demasiado altas.
- El seguimiento de retest de Word redistribuye sus columnas para conservar completos nombres de responsables, estados traducidos y fechas ISO habituales.
- Las figuras verticales o casi cuadradas del PDF disponen de más altura para conservar legibilidad; las panorámicas mantienen su tamaño habitual. La clasificación usa recursos locales permitidos y no modifica las imágenes fuente.
- El contrato PDF conserva la extracción habitual para páginas ordinarias y usa PDFium bajo exclusión mutua cuando detecta mapas de fuentes personalizados o texto RTL. Mantiene los guiones de fin de línea, cierra los recursos nativos y sigue rechazando cambios reales de portada, prosa y código. Los casos especiales cuya extracción de guiones resulte ambigua se rechazan de forma explícita.
- El motor WeasyPrint detecta glifos ausentes antes de escribir el archivo. Indica sus códigos Unicode y conserva la salida anterior, en lugar de producir cuadrados de sustitución o un error engañoso de portada. Requiere WeasyPrint 70 o posterior; PDFium queda declarado como dependencia directa, ya fijada en las dependencias auditadas.
- Las regresiones conservan la prioridad de los identificadores exactos y la exclusión de notas privadas.
- La segunda prueba bancaria verifica contenido complejo en español e inglés, incluidos inventarios, seguimiento de correcciones, tablas largas y recuperación de originales. La inspección nativa en Microsoft Word continúa pendiente.

# Cambios 0.31.3 (2026-10-11)

- Las descripciones, impactos, remediaciones y referencias extensas fluyen entre páginas del PDF y del HTML; solo la cabecera y los metadatos breves forman el bloque inicial protegido. Las tablas reales conservan sus guardas de tamaño y paginación.
- Las tablas de resumen y de secciones conservan juntas sus tres últimas filas al paginar, evitando continuaciones con una sola fila sin convertir la tabla completa en un bloque indivisible.
- La búsqueda incluye el identificador propio del hallazgo y prioriza su coincidencia exacta. También encuentra el título y contenido públicos de capítulos personalizados, sin indexar notas privadas.
- La primera edición de una imagen importada sin campo de original conserva su archivo fuente dentro de la transacción recuperable. Las ediciones posteriores mantienen ese original y la publicación excluye las copias privadas.
- Las etiquetas de severidad de Word permanecen completas al cambiar de línea. Los rótulos anteriores a imágenes coinciden con los de otros formatos para mantener verificable la asociación de evidencia.
- En escritorio, enfocar el buscador cierra el menú «Más» que podía cubrir los resultados; en móvil conserva el menú que contiene ese buscador.
- La revisión de informes en español distingue el pronombre «todo» del marcador editorial explícito TODO, conservando los demás avisos de contenido pendiente.
- El resumen utiliza un desglose neutral cuando hay hallazgos pendientes de valoración, sin afirmar que todos tienen severidad asignada.
- Los filtros del HTML portátil se adaptan al texto ampliado en pantallas estrechas, conservando legible la opción seleccionada.
- README y guías de ambos idiomas indican la misma versión. Las regresiones incluyen informes largos en español e inglés; la revisión en Microsoft Word nativo permanece pendiente.

# Cambios 0.31.2 (2026-10-11)

- La recuperación de borradores queda ligada al proyecto, revisión y diálogo que la inició; las respuestas atrasadas no adoptan contenido después de cancelar o navegar. Las vistas previas de Markdown y el inspector de publicación descartan respuestas de ediciones anteriores.
- Las rutas del proyecto rechazan alias simbólicos antes de resolver la identidad. La subida de imágenes rechaza carpetas enlazadas para evitar escrituras fuera del proyecto ante un workspace alterado localmente.
- Guardado, restauración e importación registran su preparación antes de copiar datos; al reiniciar, la recuperación puede retirar preparaciones interrumpidas con registro válido sin borrar carpetas desconocidas.
- Los respaldos comprueban tamaños y presupuestos antes de leer recursos, snapshots e historial; las entradas desmesuradas se rechazan de forma controlada.
- La exportación distingue citas, encabezados redactados y ejemplos de anclas de los límites del informe. Las comprobaciones de HTML, Markdown y Word detectan texto perdido o alterado y cambios de orden entre encabezados dentro de cada hallazgo; mantienen el rechazo de contenido movido entre hallazgos. No certifican el nivel visual del encabezado ni su posición respecto de párrafos. La anidación Markdown desmesurada se rechaza antes de que el parser HTML pueda truncar contenido.
- Crear una versión con una etapa de tipo incorrecto devuelve un error de validación sin modificar el proyecto ni su historial.
- El recibo de pytest verifica las identidades ejecutadas y su multiplicidad: ejecutar un caso dos veces ya no puede compensar otro omitido.
- Retiradas funciones y un listener vacíos sin consumidores. Se conservan las herramientas manuales de auditoría y la documentación de uso, seguridad y licencias.

# Cambios 0.31.1 (2026-10-11)

- El editor conserva métricas opcionales CVSS 4.0 al calcular, editar, guardar y recargar; evita mostrar una puntuación base diferente de la del vector completo.
- Las respuestas de validación quedan ligadas al proyecto, revisión e idioma que las solicitaron. Editar o cambiar de proyecto retira resultados anteriores.
- Los nombres de proyectos nuevos evitan dispositivos reservados de Windows y limitan bytes UTF-8, manteniendo el acceso a proyectos heredados. La restauración integral rechaza nombres no portables antes de activarlos.
- Verificar el último respaldo conserva los avisos de retención todavía pendientes. La restauración de diseños personales valida revisiones, identidades únicas y metadatos antes de activarlos.
- Markdown y DOCX conservan literalmente nombres de cliente y evaluador que contienen sintaxis Markdown. El verificador distingue encabezados dentro de un hallazgo, anclas de ejemplo en código y títulos visibles coincidentes sin permitir mover contenido entre hallazgos.
- DOCX limita dimensiones de imagen extremas antes de convertirlas, evitando desbordamientos al exportar Markdown válido con atributos desmesurados.
- Requisito mínimo corregido a Python 3.11 por las dependencias fijadas. Los lanzadores rechazan versiones anteriores antes de modificar el entorno; CI sigue validando Python 3.12.
- Pruebas de regresión para cada defecto, incluidos nombres portables en Windows, métricas CVSS completas en ambos idiomas y exportaciones en los cuatro formatos. Word nativo y las sesiones humanas continúan pendientes.

# Cambios 0.31.0 (2026-10-10)

- Respaldo periódico local desactivado por defecto: destino externo explícito, frecuencia, retención de copias propias, verificación mediante restauración temporal y estado privado por workspace. Requiere mantener el servidor abierto; las copias no se cifran ni incluyen borradores del navegador.
- Separación del transporte HTTP, CVSS 3.1, controles de CVSS y vista previa. El estado y las revisiones guardadas siguen compartidos.
- Corrección del pegado CVSS 3.1: vectores incompletos, duplicados o inválidos se rechazan sin rellenar métricas ni cambiar el hallazgo. Paridad con el cálculo Python para las combinaciones válidas.
- Corrección de la carrera que podía reanudar una escritura tras bloquear el workspace mientras se esperaba el token CSRF.
- Corpus de escala con imágenes distintas y mediciones reproducibles de edición y cuatro exportaciones; entorno, contenido y límites explícitos.
- La preparación de entrega valida las imágenes sin recomprimirlas al contar alertas de texto. Conserva redacciones, excepciones y errores por imágenes no válidas; el inspector completo y los formatos mantienen la limpieza de publicación.
- Inspección y preparación rechazan contenedores de imagen truncados incluso cuando el motor PDF permite decodificación parcial. La validación compartida con OCR no modifica opciones globales de Pillow.
- Inspección estructural automatizada de los cuatro DOCX preparados para revisión externa. La revisión visual en Word y las cinco sesiones humanas siguen pendientes.
- Documentación de distribución alineada con las Releases verificadas y exclusión del estado privado de respaldos en los paquetes fuente.

# Cambios 0.30.0 (2026-10-10)

- Edición por lotes de hasta 500 hallazgos: selección explícita, responsable, fecha y grupo de causa raíz, comparación antes/después, guardado atómico y versión recuperable. No altera estado, verificación técnica, evidencias ni retests.
- Fichas y CSV de retorno en un ZIP organizado por responsable, con revisión de todos los valores salientes. Registro privado de emisión local, recepción, aceptación y revocación, con revisiones, hashes y retención visible. No hay envío automático ni autenticación del remitente.
- Actualización asistida desde la interfaz: consulta oficial explícita, verificación de etiqueta, paquete y manifiesto, preparación en carpeta nueva y respaldo privado sin cifrar validado mediante restauración temporal. Las instrucciones continúan después de detener el editor; no se ejecuta código descargado durante la preparación.
- Filtros, vistas, posición y actividad reciente separados por espacio de trabajo y proyecto. Los filtros obsoletos permanecen visibles y pueden limpiarse; las preferencias heredadas sin identidad no se asignan automáticamente.
- La aceptación de retornos y las asignaciones guardadas desde el servidor invalidan las vistas previas antiguas. Los errores de retorno conservan archivo y selección para reintentar; una descarga ya emitida se conserva aunque falle la recarga posterior del proyecto.
- Control Mover disponible con teclado para hallazgos de cualquier cantidad, además de la reordenación de secciones.
- Los manifiestos de entrega y las comprobaciones individuales publican categorías de avisos sin copiar mensajes privados, rutas, valores censurados ni nombres de anexos excluidos. El diagnóstico completo sigue disponible en el editor.
- Respaldo y restauración funcionan en una extracción nueva que conserva el marcador `.gitkeep` vacío. Se siguen rechazando archivos inesperados, marcadores modificados y enlaces simbólicos.
- `--lang en` llega al idioma inicial de la interfaz sin sobrescribir una preferencia previa del navegador ni cambiar el idioma del informe.
- Retirada la constante sin consumidores del retorno CSV. Se conserva la documentación de instalación, uso, seguridad y licencias.
- Microsoft Word nativo y las cinco sesiones con participantes siguen pendientes. Las pruebas automáticas y los materiales preparados no sustituyen su ejecución.

# Cambios 0.29.0 (2026-10-10)

- Carpeta de datos externa seleccionable con `--workspace` o `REPORT_GEN_WORKSPACE`: proyectos, bibliotecas, historial, originales y anexos se conservan al cambiar la instalación. El arranque sin selección mantiene las rutas anteriores; la migración explícita crea un respaldo y revierte activaciones incompletas.
- Borradores y capturas pendientes separados por espacio de trabajo en el navegador, con identidad estable y protección de pestañas antiguas al cambiar de carpeta. Las copias anteriores sin identidad conservan una ruta de revisión explícita y no se asignan por coincidencia de nombre.
- Instalador Linux/Kali con entorno Python y acceso directo opcional, sin privilegios ni instalación automática de bibliotecas del sistema. La apertura habitual no instala dependencias. El paquete se comprueba desde una extracción limpia, con guardado externo y cuatro formatos de exportación.
- Releases automáticas vinculadas a un commit de `main`, tras aprobar las cuatro baterías independientes. ZIP, SHA-256 y manifiesto se reconstruyen, suben y verifican antes de publicar. Las etiquetas y los archivos existentes no se sobrescriben.
- Inicio multiproyecto con búsqueda por cliente, título o identificador, filtros, orden, paginación, fechas y retests pendientes. Archivo y reactivación conservan el proyecto completo; el selector mantiene el proyecto activo al actualizar otro.
- Retorno de tareas mediante una plantilla CSV específica: lote persistente, comparación con los valores actuales y emitidos, selección por campo y guardas de revisión. Solo admite responsable, plazo y corrección comunicada; no altera verificación técnica ni retests.
- Diagnóstico compartible con revisión previa, datos permitidos y descarga ligada a la vista revisada. Incluye versión, entorno general y pruebas sintéticas, sin proyectos, rutas personales ni mensajes de excepción arbitrarios.
- Los bloques internos de gestión y lotes se conservan en respaldos y se excluyen de la publicación antes de aplicar la censura. Evita que reglas destinadas al informe alteren metadatos internos y bloqueen las exportaciones.
- Microsoft Word nativo y las cinco sesiones con participantes siguen pendientes; la automatización no sustituye esas comprobaciones.

# Cambios 0.28.0 (2026-10-10)

- Recuperación de borradores sin diálogos duplicados: las lecturas concurrentes o antiguas no muestran registros de otro proyecto ni reinician una revisión abierta.
- Agrupación explícita por causa raíz y remediación común con identidades estables; los hallazgos conservan su evidencia, valoración y retest individuales.
- Exportación local de tareas en CSV y fichas HTML, con selección de campos, vista previa ligada a la revisión guardada y protección frente a fórmulas en hojas de cálculo.
- Criterio de cierre por hallazgo y navegación integrada en el seguimiento del proyecto.
- Registro verificable de la aceptación externa: materiales, hashes, resultados de Word, inspección visual y sesiones humanas se conservan como estados distintos. Preparar el kit no acredita haber realizado las pruebas pendientes.

- Corrección de un hueco de paginación en tablas Markdown largas del DOCX; se conservan filas completas y cabecera repetida.
- Importación de hallazgos y Deshacer conservan los datos sin restaurar vínculos a grupos inexistentes; avisos explícitos sobre el alcance del JSON individual.
- Retiradas cuatro muestras binarias regenerables sin referencias; se mantienen fuentes, diseños y documentación útil.

# Cambios 0.27.0 (2026-10-10)

- Recuperación explícita de capturas y formularios de Evidencia y decisiones todavía no incorporados, con registro privado separado por proyecto, límites, caducidad y controles de conflicto. No adjunta archivos ni recupera consentimientos de publicación automáticamente.
- Importación con vista previa de Nuclei JSONL y Nmap XML: resultados sin verificación técnica, activos y servicios con procedencia, deduplicación y guardas de revisión. Un puerto abierto no se convierte en hallazgo.
- OCR local opcional de imágenes publicadas mediante Tesseract: categorías y regiones sin devolver secretos reconocidos, límites de recursos y estados explícitos; sin red ni modificación automática de originales.
- Respaldo integral cifrado opcional `.rgbackup`: AES-256-GCM y scrypt de parámetros fijos, autenticación previa a la restauración y conservación del ZIP sin cifrar. No cifra proyectos en disco ni borradores del navegador.
- Corpus ampliado de cuatro DOCX y registro vacío reproducible para sesiones externas. Word de escritorio y las cinco sesiones con personas permanecen pendientes; no se sustituyen por pruebas automáticas.

# Cambios 0.26.0 (2026-10-10)

- Preparación, diagnóstico y arranque con `start.py --ready`; los motores opcionales ausentes se distinguen de los requisitos del editor. El arranque habitual y `--diagnose` no instalan dependencias.
- Traslado con `--upgrade-from` hacia una instalación vacía: respaldo privado fuera de ambas carpetas, restauración temporal verificada y conservación del origen. No mezcla proyectos existentes ni copia entornos virtuales, entregas o borradores del navegador.
- Inicio centrado en la demo Nimbus y la creación de un proyecto. Siguiente acción sugerida a partir de los datos y la revisión guardada, con acceso al paso correspondiente de la guía; no inventa hallazgos ni aprueba el contenido.
- Registro, cobertura, historial y seguimiento agrupados en desplegables que conservan el contexto de navegación. Las herramientas menos frecuentes permanecen disponibles.
- Selección de presentación con Serio como recomendación general, muestras comparables de los seis diseños y catálogo especializado desplegable. Navegar no cambia la apariencia de un proyecto existente.
- Distribución identificada por commit, constructor reproducible desde objetos Git y enlace único de descarga para repositorio y sitio. Comprobaciones rápidas y recorridos independientes; Pytest repartido en cuatro grupos con control de cobertura exacta.
- README y guías ES/EN centrados en el primer resultado y la actualización. Protocolo de cinco sesiones externas y tres tareas documentado en CONTRIBUTING, pendiente de ejecución; no se declara validación con usuarios externos.
- La revisión nativa de Microsoft Word sigue siendo una comprobación específica pendiente: las pruebas de OOXML, LibreOffice y compatibilidad de Windows no la sustituyen.

# Cambios 0.25.0 (2026-10-09)

- Gráfico de retest con etiqueta, cantidad y barra en una misma fila; geometría responsiva y ampliación de texto verificables.
- Preparación con estados, contador y accesos directos; vista previa ajustada al ancho con zoom manual.
- Lectura YAML acelerada con prevalidación acotada, controles de grafo y fallback de compatibilidad.
- Recorrido PDF compacto por fases y conservación del texto introductorio junto al siguiente bloque.
- Fingerprint de claves públicas Ed25519, ciclo de vida POSIX sin servidor hijo y limpieza de señales de consola en Windows.
- CI ampliado y variable canónica de Chromium con compatibilidad del nombre anterior.

# Cambios 0.24.0 (2026-10-09)

- R10: firma Ed25519 separada y opcional para entregas, con clave pública externa, captura inmutable, verificación del ZIP/manifiesto exactos y rechazo de entradas ambiguas o no portables. Claves privadas locales fuera del editor; dependencia signing opcional.
- R12: serialización incremental de hallazgos y objetos compuestos del historial para proyectos grandes. No-op verificado sin escrituras ni cambio de ETag; YAML completo, activación atómica, recuperación y respaldos portátiles v1 conservados.
- Firma no equivale a cifrado, identidad real ni validación técnica. El historial local nuevo requiere 0.24.0; un respaldo exportado permite migrarlo a la versión anterior sin perder sus objetos.

# Cambios 0.23.4 (2026-10-09)

- R11: catálogo explícito para errores propios y validación, elegido por el idioma de la interfaz antes de interpolar datos; idioma capturado para los trabajos y subprocesos de exportación. Sin sustituciones sobre texto del usuario ni cambios en códigos HTTP, CSRF, Origin/Host, revisiones o ETag.
- R14: recorrido vectorial por máquina en PDF desde fases, pasos y figuras registrados, con orden documental explícito, evidencia vinculada separada y alternativa textual paginable. Las flechas no acreditan causalidad, éxito ni verificación técnica. Los otros formatos conservan su contenido.

# Cambios 0.23.3 (2026-10-09)

- R07: pestañas accesibles Evidencia y Decisiones por hallazgo, con vínculos y modelo existentes, galería compartida y borradores conservados.
- R08: comparación de solo lectura con snapshot de entrega identificado, selección explícita ante ambigüedad, guardas de revisión y comparación visual compartible o privada.
- R09: matriz y gráfico de retest derivados de observaciones reales, con filtros y distinción de estado, verificación técnica y resultado observado.
- La etapa delivered significa entrega registrada localmente, sin acreditar recepción del cliente ni éxito de exportación. Eliminar un hallazgo no acredita corrección.
- Sin cambio del esquema de proyectos ni de las políticas de publicación y exportación.

# Cambios 0.23.2 (2026-10-09)

- R03: atajos contextuales j/k, Ctrl+Enter/⌘+Enter y ayuda ?, con guardas de guardado, proyecto, revisión, foco y diálogos.
- R04: contexto de activos, responsable, estado y evidencias en fichas y tabla, a partir de las referencias reales; relaciones ausentes se indican explícitamente.
- R05: revisión agrupada, progreso de avisos de sesión y Guardar y comprobar siguiente. Resolver un aviso editorial no registra verificación técnica.
- R06: lista de preparación de entrega de solo lectura para anexos, posibles secretos y asociaciones, derivada de la revisión guardada y marcada como antigua cuando cambia el borrador.
- La importación y restauración preparan sus copias privadas sin una segunda transacción interna. Se corrige un defecto heredado: un fallo transitorio de limpieza podía dejar un registro que posteriormente recreaba una carpeta temporal y bloqueaba el respaldo del espacio. Se conservan la publicación atómica, los snapshots y la recuperación del proyecto.
- La navegación de teclado resuelve el UID del hallazgo visible tras una reordenación; los recursos corruptos o ausentes producen una comprobación pendiente en Entregar.
- No cambia el esquema de proyectos, los exportadores ni los documentos históricos. Se conservan revisión, recuperación y control de concurrencia.

# Cambios 0.23.1 (2026-10-08)

- Anterior/Siguiente dentro del editor de hallazgo, con foco accesible y orden completo explícito del proyecto; selección por UID, sin reescribir fuentes al navegar.
- Preview sincronizada tras load con el mapa UID del snapshot renderizado; una respuesta antigua no reclama el proyecto actual y el resaltado no se exporta.
- Se comprueba visibilidad real del panel antes de pedir previews, incluidas vistas de inicio, tabla y móvil.
- Marca WebP lossless a 900×600, suficiente para el mayor uso a DPR3; transparencia conservada y PNG reducido retenido por documentación histórica.
- Navegación superior, relaciones de activos, calculadora CVSS y acciones de galería redistribuidas en móvil con texto ampliado al 200 %, sin etiquetas superpuestas, desbordamiento de página ni regiones vacías con scroll.
- Selector de versión CVSS con nombre accesible en español e inglés y etiqueta crítica con contraste AA en tema claro.
- Metadatos DOCX tomados de la copia preparada del informe: título, evaluador e idioma; sin autor de biblioteca, comentarios de plantilla ni fechas heredadas de 2013. Las fechas de creación desconocidas se omiten.
- Instrucciones de actualización ES/EN alineadas con 0.23.1; referencias históricas conservadas.
- Contrato de descarga progresiva del HTML sin carreras de temporizador: el servidor espera a comprobar controles aún sin cablear antes de liberar el resto, conservando las guardas de CLS, visibilidad y CSP.

# Cambios 0.23.0 (2026-10-08)

- Espacio opcional Evidencia y decisiones: mapa basado en vínculos existentes, afirmaciones observadas/inferidas/hipotéticas y límites explícitos de evidencia.
- Priorización empresarial redactada por el autor: servicio, objetivo, consecuencia, tolerancia, fuente, supuestos, razón y responsable; no se calcula pérdida financiera desde CVSS.
- Observaciones por campo y revisión ligada al contenido y a los comentarios. Una modificación invalida la aceptación previa; identidades declaradas localmente.
- Entregas técnica, ejecutiva y pública como archivos independientes. La pública usa texto aprobado explícito, alias y consentimiento; el modelo privado de revisión queda fuera de todos los informes.
- Revisión visual del PDF real, con miniaturas aisladas, notas por página y registro descargable ligado al SHA-256. Es opcional, temporal y no certifica Word nativo.
- Sustituciones literales con límites UTF-8 acumulados e intermedios, comprobados antes de reservar memoria; rechazo controlado de expansión excesiva.
- Reglas editoriales transparentes y adaptador Ollama opcional: solo campos seleccionados, modelos locales instalados, comparación antes de aceptación y guardas de revisión.
- Galería, tablero y lateral paginados para proyectos grandes. La vista previa oculta deja de renderizar y leer un editor heredado no añade campos al proyecto.

# Cambios 0.22.1 (2026-10-08)

- Los enlaces de los diálogos de trabajo usan el acento del tema y conservan el subrayado: el enlace GitHub de Acerca de ya no hereda el azul oscuro del navegador.

- El registro de cambios incorpora la entrada de 0.22.0, antes documentada únicamente en los README y su validación. Se conserva el registro histórico de aquella entrega.
- La cabecera usa desde el inicio el símbolo SVG que ya empleaba tras la inicialización; evita solicitar el logotipo completo durante ese arranque. El PNG permanece en bienvenida, Acerca de y documentación.
- El PNG de marca se recomprime sin cambiar sus píxeles RGBA ni sus dimensiones de 1536 × 1024: pasa de 1.602.203 a 1.483.406 bytes.

# Cambios 0.22.0 (2026-10-08)

- Guía visual opcional de seis pasos en español e inglés: inicio, alcance, hallazgos, evidencia, revisión y entrega/respaldo. Se abre desde Inicio, el lateral o Más en móvil, con ejemplos ficticios y enlaces a las pantallas reales.
- Leer la guía no crea proyectos ni rellena campos. Su animación breve respeta movimiento reducido; al cambiar de paso, el foco revela el título si queda fuera de pantalla.
- El tablero de Hallazgos ofrece acciones visibles para añadir una entrada o usar la biblioteca, también cuando todavía está vacío.
- Abrir editores Markdown y opciones de inclusión conserva los datos y la revisión; los campos ausentes solo se incorporan al editar.
- Revisión y entrega comparten un preflight. Los avisos de validación y del flujo se conservan en verificacion.json y LEEME.txt, y requieren confirmación al entregar directamente o en cola. Los errores siguen bloqueando la entrega y la publicación usa el documento revisado.
- Los README priorizan instalación, primer uso y actualización.

# Cambios 0.21.9 (2026-10-08)

- La exportación rechaza destinos que coinciden con la fuente o recursos locales referenciados, incluidos symlinks y hardlinks, antes de escribir. Se conserva la sustitución legítima de informes previos.
- La CLI protege también sus salidas secundarias y comprueba los destinos efectivos de Markdown.

# Cambios 0.21.8 (2026-10-08)

- Contrato de listas compara la secuencia y sus límites en HTML, Word y Markdown; conserva listas anidadas. Una guarda común rechaza ordinales fuera del rango representable por navegador y Word en los cuatro formatos, sin alterar archivos previos.
- Índice PDF codifica las claves documentales, evita colisiones de secciones heredadas y exige referencias solo a los bloques emitidos. Las opciones CLI se aplican antes de la validación final.
- Referencias internas codificadas reservan sus IDs también en el editor. Fechas de seguimiento usan AAAA-MM-DD para mantener comparación cronológica y estados coherentes.
- Enteros no representables exactamente por el editor se rechazan con ruta de campo y recomendación de guardarlos como texto, sin redondear ni modificar la fuente.
- Creación desde diseños rechaza colisiones Unicode; declaraciones de anexos rechazan JSON ambiguo; bibliotecas exigen una versión entera válida.
- Tres diálogos de plantillas y notas usan modalidad nativa, foco inicial y restauración. Retiradas las trampas manuales de foco redundantes.
- Arranque con app.js ausente o JavaScript desactivado muestra un aviso operable y recarga nativa; el editor queda inerte hasta instalar sus eventos. Retirados estilos y markup animado de carga sin consumidor.
- Búsqueda del HTML portátil reconoce representaciones Unicode equivalentes sin retirar acentos. Documentación inglesa de actualización y validación puesta al día.

# Cambios 0.21.7 (2026-10-08)

- Entradas nulas y títulos ausentes accesibles; idioma efectivo consistente; fragmentos codificados y resúmenes sin enlaces a detalles omitidos.
- Límites numéricos/contador seguros, importaciones Unicode y ZIP inválidos controlados, y arranque del editor con recuperación visible.
- Orden y límites de tablas comprobados en HTML, Word y Markdown; HTML portátil y tablas Word extensas mejorados.
- Retirados helpers sin consumidores; dependencia opcional PyMuPDF corregida a 1.26.7.

# Cambios 0.21.6 (2026-10-08)

- Valida el espacio efectivo de anclas antes de exportar, incluidos controles portátiles y secciones automáticas, conservando identidades y claves personalizadas legítimas.
- Conserva todos los activos sin UID en el inventario, evita vínculos implícitos al último activo y admite títulos nulos en proyección sin inventar un título ni modificar la fuente.
- Corrige el falso rechazo de código PDF envuelto físicamente y detecta líneas reordenadas o repeticiones ausentes; mantiene explícitos los límites de extracción textual y revisión manual.
- HTML portátil con palabras completas en columnas comparativas intermedias, nota en main, versión visible de exportación y márgenes de impresión A4; el contenido histórico del ejemplo Banco Lumbre se conserva.
- Copia de CVSS espera confirmación de portapapeles, informa fallos y conserva nombre accesible estable.
- 1.200 pruebas Python, npm 12, DOM/API 29 y Chromium 48/72/24/58 aprobados. Nuevo informe Cooperativa Faro exportado en cuatro formatos, revisado en PDF/Word/HTML.

# Cambios 0.21.5 (2026-10-08)

- Fichas del HTML portátil con columna de etiquetas acotada y alineación superior en escritorio; lectura apilada en móvil, conservando filas, encabezados y contenido.
- Tablas comparativas con anchura suficiente para leer los datos, región de desplazamiento local accesible por teclado y comportamiento de impresión independiente.
- Barra de filtros con geometría reservada antes del primer pintado y controles disponibles después de instalar eventos; arranque mínimo y script de lectura autorizados por sus hashes CSP.
- Fuente opcional en HTML portátil para evitar su intercambio tardío. Sin cambios de esquema, del motor PDF ni de los PDF históricos.
- Títulos móviles más contenidos para mantener palabras largas completas a 320 px, sin alterar escritorio ni impresión.
- Contratos de navegador y contenido para ES/EN y disposiciones por secciones/heredada.

# Cambios 0.21.4 (2026-10-08)

- Severidad contrastada con vectores CVSS 3.1 y 4.0 cuando la puntuación escalar está ausente, nula o vacía, sin modificar ni completar datos del informe.
- Un tema explícitamente nulo se rechaza en la validación final; el editor conserva su normalización compatible al tema serio.
- Retiradas dos expresiones regulares sin uso y corregidas las descripciones de compatibilidad CVSS.
- 62 contratos nuevos de validación y exportación, con evidencia antes/después.

# Cambios 0.21.3 (2026-10-08)

- HTML portátil sin desbordamiento en 320/360 px; reapertura del mismo fragmento con filtros activos y separación de anclas según la altura real de la barra.
- Exportaciones conservan imágenes WebP y enlazadas, referencias literales y vectores CVSS con puntuación ausente/null/vacía/cero. El inspector compara las referencias y la huella exacta de la conversión Word; mantiene las guardas de contenido y asociaciones.
- Importación JSON validada sobre copia antes de modificar el editor, con protección de cambios concurrentes y del proyecto elegido. La incorporación conserva las identidades del modelo para que Deshacer siga operativo.
- Diálogos nativos con foco, teclado y errores contextualizados; nombres de controles, semántica de listas, contraste observado, Ctrl+K móvil y referencias ARIA de exportación corregidos.
- Biblioteca sanea formas Markdown y rutas privadas sin alterar código literal ni citas bibliográficas. Las variables se vuelven a comprobar después de rellenarse.
- Respaldo conserva recuperación heredada y sus recursos sin escribir en el origen; creación y respaldo rechazan colisiones Unicode. Restauración completada con fallo posterior de limpieza devuelve éxito con aviso y conserva un reintento seguro.
- Excepciones de constructores YAML inválidos normalizadas como entrada 422, sin estado parcial.
- 196 casos Python nuevos; suite final completa: 1.050 aprobados sin omisiones. Editor: 72 comprobaciones en Chromium real; npm: 12; DOM/API: 29. Las suites previas de navegador aprueban 48 y 24 comprobaciones. Revisión visual de DOCX con LibreOfficeDev y PDF sintéticos. Nuevas guardas incorporadas al workflow Chromium.
- Guía de actualización con el caso de `.bak` omitido por exportadores anteriores. Word nativo, Firefox local y lector de pantalla siguen sin ejecutar en esta ronda.

# Cambios 0.21.2 (2026-10-05)

- RG-L01: IDs persistentes al eliminar, reordenar y duplicar fichas, contador de asignación sin reutilización y bloqueo de referencias internas huérfanas. Markdown incluye anclas explícitas; Word y Markdown enlazan también desde el resumen.
- RG-L02: contrato v3 con portada, metadatos tipados, tablas nativas y destinos de enlaces comparados con la copia pública de origen. CVSS escalar, incluido cero, se publica de forma explícita en Markdown.
- RG-L03: huella de cada imagen pública, pie, contexto y posición respecto de los comandos. Se detecta también el traslado de una evidencia entre pasos sin comandos. Recursos con espacios y corchetes se resuelven correctamente.
- RG-L04: el verificador excluye HTML estáticamente oculto mediante atributos o reglas CSS soportadas. Todos los formatos declaran revisión visual requerida. La interfaz muestra las nuevas comprobaciones y sus límites.
- RG-L05: metadatos iniciales de Word como párrafos nativos con continuidad de paginación. En el motor disponible, los 24 hallazgos y dos máquinas conservan su título con el comienzo del contenido; los cuatro casos huérfanos de la auditoría ya no se reproducen.
- Texto contextual ES/EN para CVSS/CWE opcionales sin registrar.
- 67 pruebas Python nuevas; suite completa: 854 aprobadas. 12 pruebas JS, 29 comprobaciones DOM/Flask y 26 comprobaciones en Chromium. Ocho mutaciones rechazadas. Informe Grupo Ladera repetido: PDF de 78 páginas y DOCX renderizado de 65 páginas. Word nativo, LibreOffice estable y Firefox siguen pendientes en este ciclo.

# Cambios 0.21.1 (2026-10-05)

- Contrato de contenido por hallazgo: párrafos completos con repeticiones y código literal. Mutaciones de contenido, espacios y ubicación provocan rechazo en HTML, Markdown y Word. PDF declara sus límites de extracción y revisión manual.
- Corregidos el recorte de espacios y líneas vacías de comandos y la expansión de tabulaciones dentro de bloques Markdown. Se conserva la protección contra HTML activo.
- Corregida la omisión del nombre genérico del equipo en Word y Markdown de informes antiguos sin evaluador.
- Inventario de datos privados, descarga y eliminación protegida de borradores, y limpieza transaccional de historial, anexos retirados y respaldo YAML anterior. La limpieza es explícita y conserva los datos actuales.
- Anexos obligatorios bloquean la entrega cuando faltan, están excluidos o no conservan su hash. Análisis orientativo de patrones y metadatos sin divulgar secretos ni modificar el anexo.
- Tamaños pequeños expresados en bytes, errores de anexos dentro del diálogo y limpieza del error al corregir el campo.
- Pruebas reales de conflictos entre pestañas, ENOSPC, EACCES, terminación del proceso entre renombres y recuperación en el mismo origen. Respaldo restaurado en una instalación vacía.
- CI ampliada para Chromium, Firefox y Windows; script de Word nativo disponible. Las ejecuciones remotas y Word de escritorio siguen pendientes.

# Cambios 0.21.0 (2026-10-05)

- Inventario explícito de anexos con SHA-256, límites de tamaño, revisión individual y copia seleccionada en `anexos/`. Los respaldos conservan anexos privados; las exportaciones individuales no los adjuntan.
- Registro visible y descargable de revisión, huellas y comprobaciones en cada exportación. Los resultados siguen ligados a su sesión local.
- Registro único de formatos para CLI, API, cola e interfaz. Comparación de títulos, comandos, filas de tablas y orden de listas con la copia de publicación.
- Inspección adicional de enlaces, integridad e imágenes publicadas en Word; retención del bloque introductorio del hallazgo con su contenido.
- Espaciado cómodo o compacto del informe, separado de la densidad del editor. Filtros de tipo, valoración pendiente, limpieza y estado vacío en HTML.
- Búsqueda de pasos y comandos en hallazgos y máquinas. Severidad pendiente explícita en selector, inicio y tablero; los hallazgos nuevos no reciben severidad por defecto.
- Corregida una referencia de índice no definido en Inicio para borradores sin ID.
- Instalador pip del entorno virtual actualizado antes de instalar dependencias. Comprobación final de paquetes sin avisos conocidos en las bases consultadas; no equivale a ausencia de vulnerabilidades.
- Pruebas reales en Chromium, matriz Chromium/Firefox en CI, ejemplo ficticio complejo y corpus de carga. Control manual de Microsoft Word sobre copias, con revisión de campos y exportación nativa.
- 34 pruebas Python nuevas. 739 casos Python distintos aprobados en la suite completa y la comprobación adicional del instalador; 49 comprobaciones reales de navegador. Firefox local bloqueado por EPERM y Microsoft Word nativo sin ejecutar.

# Cambios 0.20.2 (2026-10-05)

- La descarga individual de HTML deja de tratarse como ZIP. La cola y la entrega conjunta comparten el selector de inspección por formato. El inspector HTML comprueba recursos incorporados y destinos internos.
- Las etiquetas de Markdown se separan del contenido para conservar tablas, código y listas al comienzo de campos, pasos y resúmenes.
- Word conserva el orden de párrafos, código y sublistas, sus sangrías y los espacios entre estilos en línea.
- Los enlaces Markdown a hallazgos y secciones se convierten en enlaces internos de Word a marcadores estables. Los enlaces web siguen siendo externos.
- La exportación HTML por terminal valida el proyecto antes de publicar, igual que los otros formatos; un error no sobrescribe un destino existente.
- 27 pruebas nuevas; suite completa de 705 aprobadas. Dos simulaciones y verificación de PDF, DOCX, Markdown y HTML. Sin migración de esquema.

# Cambios 0.20.1 (2026-10-05)

- Los hallazgos sin severidad permanecen en el resumen PDF, HTML, Word y Markdown, con etiqueta pendiente ES/EN. El conteo de máquinas se mantiene separado y no se fabrican puntuaciones.
- Los puntos del índice PDF se alinean con su entrada, incluidos los títulos que requieren varias líneas.
- Las tablas Markdown y estructuradas reparten columnas por contenido. PDF/HTML y Word comparten el criterio y las proporciones específicas de las tablas de activos, cobertura y retest.
- Los bloques Markdown usan el mismo estilo de bloque que los comandos, sin heredar cajas de código en línea. Los bloques cortos se mantienen juntos; las etiquetas breves en negrita acompañan a su bloque.
- Índice Word nativo con enlaces, marcadores y campos actualizables. El resultado inicial conserva títulos y no inventa números de página; F9 actualiza los campos en el editor.
- Pruebas de regresión y ejemplo ficticio de hallazgos pendientes.

# Cambios 0.20.0 (2026-10-04)

- Navegación Trabajar, Revisar, Entregar y Biblioteca; cabecera móvil compacta y preferencias agrupadas.
- Borradores recuperables, descarga de emergencia y resolución explícita de conflictos con validación estructural.
- Proyección pública común, imágenes sin metadatos, originales privados conservados y comparación compartible separada de la interna.
- Inspector de texto, recursos y huellas; patrones de secretos, excepciones registradas y censuras literales.
- Informe HTML autónomo con búsqueda, severidad, vista ejecutiva e impresión; lectura completa sin JavaScript.
- Corregidos vínculos rotos de capturas, selección CSV, huella original del importador, etiquetas Markdown y estados al duplicar/retest.
- Instrucciones inglesas de entrega y biblioteca ES/EN conservada. Calibri/Carlito y las mascotas no cambian.
- Lanzador de instalación/diagnóstico y documentación ES/EN. Evidencias antiguas separadas del paquete principal.

# Cambios 0.18.0 (2026-10-04)

- Inicio contextual, retorno al último hallazgo y posición, y lista de actividad reciente.
- Navegación por trabajo, revisión y herramientas, densidad y concentración; autoría en «Acerca de».
- Símbolo vectorial compacto con Prometeo y Evaristo; ilustración original conservada.
- Editor por apartados con cabecera contextual; vista HTML sincronizada, ancho ajustable y revisión visible.
- Vista propia de Hallazgos, filtros y vistas guardadas. Corregido «Ver todos los hallazgos», que llevaba a la configuración del informe.
- Deshacer por operación para eliminaciones y reordenaciones, sin revertir texto editado después.
- Búsqueda de acciones con Ctrl+K y navegación de resultados por teclado.
- CSV/Burp en Archivo, Columnas y Revisión; protección frente a respuestas de archivos anteriores.
- Exportaciones en panel no modal con estado persistente, cancelación y restauración del foco.
- Verificación técnica separada de remediación/retest y revisión de importación; estados antiguos conservados.
- Bandeja privada con notas, comandos, HTTP e imágenes, original/SHA-256, vínculo explícito y respaldo.
- Traducciones de controles nuevos, barra Markdown y ubicaciones de búsqueda; idiomas del informe y de la interfaz independientes.
- Diseños, biblioteca bilingüe, logos de plataformas y tipografías de informes conservados.

# Cambios 0.17.0 (2026-10-04)

- Versión canónica en `version.py`, compartida por empaquetado Python, API, dashboard y entregas.
- Corregido el manifiesto de entrega que todavía anunciaba 0.15.1.
- Estados de guardado, hora real, error persistente y reintento; la exportación no sobrescribe el estado de guardado.
- Cola de procesos con revisión inmutable, etapas reales, cancelación activa/en espera, limpieza y caducidad.
- CSV y Burp XML con vista previa, mapeo, procedencia, límites, deduplicación y revisión previa a entrega.
- Comparación visual de texto y evidencia histórica, con HTML autónomo imprimible.
- Conservados diseños, tipografías, logos y biblioteca bilingüe.
- Automatización Windows y script de Microsoft Word incluidos; ejecución nativa pendiente.

# Cambios 0.16.0 (2026-10-03)

- Dashboard con estado real del proyecto, accesos a hallazgos y preparación de entrega.
- Cabecera reorganizada, navegación móvil, temas claro y oscuro y foco visible.
- Emblema de Prometeo y Evaristo sobre una consola; wordmark HTML sin cortes.
- Separados el idioma de interfaz y el del documento: cambiar ES/EN no altera el informe.
- 150 nuevas vistas inglesas, además de las 150 españolas. Editor personal con campos ES/EN.
- Respaldo integral de proyectos, originales, historial y ambas bibliotecas personales.
- Restauración solo en instalación vacía, límites acumulados, hashes y recuperación ante interrupciones.
- 574 pruebas Python, 29 comprobaciones del nuevo DOM, cinco de guardado y 50 en Chromium.
- Muestras inglesas OSCP y CPTS en PDF/Word; fuentes del informe y motores conservados.

# Cambios 0.15.1 (2026-10-03)

- Logos de OffSec y Hack The Box en los 22 perfiles y sus dos variantes, en PDF,
  Word y vistas previas. Recursos incluidos, con procedencia y hashes.
- Selección clara u oscura según el fondo, sin sustituir los logos de autor y cliente.
- Corregida la vista previa de plantillas personales con estructura mínima.
- Conservada la variante Sobria al duplicar, guardar y crear desde una plantilla personal.
- Valores inválidos para un diseño general devuelven 422 sin modificar el proyecto.

# Cambios 0.15.0 (2026-10-03)

- Biblioteca con 14 perfiles OffSec y ocho HTB, seis diseños generales conservados y referencias históricas separadas.
- Cinco composiciones nuevas con título central y datos en el tercio inferior, variantes Marca y Sobria, Calibri/Carlito y código monoespaciado.
- Galería con 150 vistas reales de portada, resumen y página técnica, búsqueda y filtros.
- Creación ES/EN con guías TODO; aplicar apariencia conserva el contenido existente.
- Plantillas personales con edición de colores, composición y estructura. Cada proyecto conserva su propia copia de la apariencia.
- Orientación de entrega con fuente y fecha de consulta; Markdown propuesto para CWEE y limitación de cifrado explícita.
- Escrituras atómicas, revisión de biblioteca y proyecto, entradas acotadas y comprobación de que la biblioteca escrita pueda volver a abrirse.

# Cambios 0.14.0 (2026-10-03)

- Demo Nimbus editable con copias independientes, guía breve y diagnóstico real de instalación.
- Editor visual para plantillas reutilizables: vulnerabilidades, máquinas, fases,
  pasos, variables, CVSS, ayuda de redacción, vista previa y JSON opcional.
- Preparar entrega desde una instantánea guardada: formatos seleccionables,
  avisos explícitos, comprobación de recursos y ZIP con hashes de las salidas.
- Diseños propios Ejecutivo y Laboratorio en PDF y Word; seis temas revisados.
- Catorce presets revisados en ES/EN, con guías TODO y sin afirmaciones de
  compromisos no realizados. Se corrige la especialidad de CWEE y CWPE.
- Portadas con ilustraciones más compactas, encabezados Word alineados y código
  monoespaciado con DejaVu Sans Mono. No se añade un prompt ficticio a los comandos.
- Contraste corregido en etiquetas de máquinas y avisos del editor en modo claro.

# Cambios 0.13.5 (2026-10-03)

- Registro de activación y recuperación de procesos interrumpidos, con copias
  conservadas cuando falla también la reversión.
- Reescritura de destinos Markdown comprobada por el parser, sin alterar código,
  etiquetas ni texto; trabajo de análisis acotado y rechazo sin cambios si no
  puede demostrar la conservación del contenido.
- Revisión de imágenes consistente con el parser y separación de campos de
  texto, comandos y recursos; rechazo final de imágenes no locales.
- Validación de campos legacy de exportación; valores nulos y numéricos admitidos
  conservados en Word y Markdown.
- Bloqueo del idioma durante navegación pendiente.
- Escape de texto plano y tablas Markdown; celdas estructuradas Word literales
  para conservar todos sus valores.

# 0.13.2 - 2026-10-02

## 0.13.4 - 2026-10-03

Reauditoría sobre el ZIP 0.13.3 entregado. Guardado y evidencias se preparan como
un estado completo; errores controlados conservan el proyecto anterior. El escritor
comprueba los límites de su lector. Eliminación/restauración bloquean la navegación
hasta completar la operación. Markdown conserva código literal y normaliza también
imágenes por referencia. DOCX admite vector CVSS nulo y se rechazan caracteres no
compatibles. YAML limita nodos durante su composición. Se corrige una expectativa
antigua que aprobaba modificar código literal al censurar una imagen.

293 tests Python, 5 JavaScript, 75 comprobaciones Chromium. Nimbus conserva sus
673 fragmentos, 19 imágenes y composición.

## 0.13.3 - 2026-10-03

Auditoría adversa sobre 0.13.2. Censura por recurso canónico, respaldo e historial
con imágenes externas a img/, lectura acotada de JSON/YAML con rechazo de claves
duplicadas y datos no finitos, fechas ISO, alias con identidades independientes,
decodificación única de URLs y cabeceras inválidas rechazadas sin errores 500.
Arranque con Waitress local de un proceso. Dependencias de producción fijadas y
consultadas contra avisos conocidos.


- Auditoría del informe Nimbus completo usando las salidas nativas y el editor real.
- Markdown conserva los metadatos y las imágenes de portada en las dos ramas de exportación.
- Escape de pies de figura, rutas locales codificadas y empaquetado de nombres reales.
- Cercas de código más largas que las presentes en el comando original.
- Modo `vuln` implícito coherente en numeración de figuras y plantilla PDF clásica.
- Word: gráfico de severidad ES/EN, tamaño legible y fuente DejaVu Sans incluida con licencia.
- Word: unión de etiquetas de lista y plazos de remediación con su contenido.
- Diez regresiones adicionales.
- Se conservan los cálculos CVSS y el formato de los proyectos.

# 0.13.1 - 2026-10-02

- Protege las entregas con escritura atómica y copia consistente de YAML e imágenes durante la exportación web.
- Corrige la sustitución de referencias de evidencia para no modificar nombres que solo comparten un prefijo.
- Rechaza exportaciones finales de hallazgos sin ID o con versión CVSS incompatible con su vector; conserva los borradores.
- Da formato a tablas Markdown y columnas de activos, cobertura y retest; mantiene encabezados y evidencias de retest juntos cuando caben.
- Corrige el contraste de etiquetas de severidad en los cuatro temas y los colores de texto del gráfico.
- Añade soporte WebP/rotación EXIF a Word, logos e ilustración de portada, OSID/correo y figuras ajustadas al área imprimible.
- Adapta el cuerpo del tema HTB en Word a papel blanco; conserva su portada oscura.
- Escapa cadenas de cabeceras CSS de forma segura y evita entidades HTML visibles.
- Conserva el nombre report-gen en una línea, mejora controles estrechos y foco; completa etiquetas ES/EN.
- Descarta vistas previas antiguas, libera sus URLs y permite reintentar la sesión tras un error transitorio.
- Corrige pies de evidencia con escapes Markdown y estilos de títulos/pies de Word.
- Incluye regresiones Python/DOM, comprobación reproducible en Chromium y registro de auditoría.

---

# 0.13.0 — 2026-09-08

- Añade historial completo de proyectos con objetos deduplicados, etapas con nombre, comparación por identidad y restauración de archivos con rollback.
- Añade respaldos portables con manifiesto de integridad y un importador acotado que verifica rutas, tipos de imagen, enlaces, duplicados y tamaños.
- Añade revisión de entrega, activos, cobertura, limitaciones, seguimiento de correcciones y registros de retest.
- Añade galería de evidencias compartidas, originales separados y edición que aplana anotaciones/censura en PNG sin metadatos.
- Añade biblioteca local versionada con etiquetas, variables, saneado de campos del proyecto, revisión de texto e importación/exportación.
- Introduce identificadores permanentes y migración compatible de proyectos antiguos.
- Integra activos, evidencias, cobertura y retest en PDF, DOCX y Markdown; incluye sus secciones en el índice PDF.
- Conserva la paginación continua y la protección de tablas de hallazgos. Evita párrafos vacíos añadidos entre pasos en Word.
- Incluye guía, respaldo de demostración ficticio y pruebas de los nuevos recorridos con el editor y la API reales.

---

# Changelog

Formato basado en Keep a Changelog. Versionado semantico aproximado.

## [0.12.1] - 2026-09-08

### Paginación
- Se elimina el salto obligatorio entre hallazgos en todos los temas PDF y en
  ambas rutas del exportador DOCX.
- El encabezado PDF permanece unido a su tabla principal; las tablas del hallazgo
  no se fragmentan para aprovechar un espacio insuficiente al final de página.
- Los procedimientos largos conservan el flujo entre páginas.
- Los marcadores del índice acompañan al encabezado al cambiar de página.
- Word utiliza filas indivisibles y encadena los párrafos de cada tabla; los
  encabezados permanecen con su contenido siguiente.
- WeasyPrint comprueba sus fragmentos de página antes de escribir. Chromium
  dispone de una comprobación mediante marcadores temporales en un PDF previo;
  esos marcadores se retiran de la salida final.
- Un PDF con una tabla demasiado alta se rechaza con un mensaje accionable. La
  API devuelve el motivo sin cambiar el proyecto guardado.
- Se añaden pruebas de paginación real, movimiento de tablas, índice, DOCX y API.

## [0.12.0] - 2026-09-08

### Corregido
- RG-01: los guardados capturan proyecto, contenido y revisión; cambiar de
  proyecto espera el guardado pendiente y se cancela si falla.
- RG-02: los errores HTTP conservan el estado pendiente; las respuestas antiguas
  no marcan como guardadas ediciones más recientes.
- RG-03: saneado compartido de Markdown y atributos; payloads HTML visibles como
  texto, sin ejecución. Las bases de imágenes se aíslan por petición.
- RG-04: validación de rango y finitud del score, coherencia con vector y severidad,
  parser CVSS 3.1 estricto y visualización correcta de la puntuación numérica 0.
- RG-05: validación de estructuras anidadas antes de escribir, y reparación del
  fallo de traducción del validador. La exportación final exige datos válidos.
- RG-06: Word conserva las imágenes Markdown, enlaces, listas, tablas y bloques
  de código con saltos e indentación.
- RG-07: Markdown se entrega en un ZIP con sus imágenes relativas.
- RG-08: validación de Host y Origin, CSRF de sesión, tipo JSON obligatorio,
  política CSP y restricción de recursos externos y rutas en los renderizadores.
- RG-09: colores explícitos y etiquetas completas en el gráfico SVG del PDF.

### Añadido
- Escritura atómica del YAML, copia de una versión anterior y botón Restaurar.
- ETag/If-Match para detectar conflictos entre pestañas; subida de imágenes con
  nombres únicos y sin sobrescribir evidencias existentes.
- Exportación desde instantáneas temporales sin modificar el proyecto guardado.
- Pruebas de regresión, guardado JavaScript y editor con API HTTP real y jsdom.
- Dependencias de desarrollo JavaScript y CI actualizado; guía de migración y
  registro de verificación. Nuevas dependencias runtime: nh3 y lxml.

### Compatibilidad
- Markdown CLI/UI ahora produce `.zip`; `to_markdown` sigue devolviendo texto.
- Los clientes API deben enviar cookie de sesión, token CSRF y revisión ETag.
- El YAML sigue siendo compatible; datos inválidos antes tolerados pueden bloquear
  una exportación hasta que se corrijan. Las imágenes se limitan al proyecto.
- `tests/run_stdlib.py` requiere pytest y delega la ejecución de la suite.

### Funciones ya presentes en el ZIP recibido


### Anadido
- Biblioteca de hallazgos reutilizables (guardar un hallazgo como plantilla e
  insertarlo despues; se guarda en el navegador).
- Importar / exportar hallazgos en JSON.
- Mensajes de validacion bilingues (ES/EN) segun el idioma de la interfaz.

## [0.11.0] - 2026-09-02

### Anadido
- Dashboard de hallazgos (seccion Hallazgos): tabla Severidad/Hallazgo/CWE/CVSS con
  resumen y barra de distribucion, conmutador de orden Severidad/Manual (en Manual se
  reordena arrastrando), filtro por severidad y marcador de hallazgos incompletos
  (sin CVSS/CWE).
- Panel de resultados CVSS en el editor: tarjeta de puntuacion, tarjeta MacroVector y
  metricas en lenguaje claro (3.1 y 4.0, bilingue).
- Tema claro/oscuro de la interfaz (persistente), con boton en la barra superior.
- Indicador de carga en la vista previa (patita giratoria + "Actualizando...") mientras
  se re-renderiza o se cambia el idioma del informe.
- Toasts de feedback (proyecto creado, exportado, copiado) y estado de exportacion
  (el boton muestra "Generando..." y se deshabilita hasta terminar).
- Validacion visible: boton que revisa el informe y muestra un panel de avisos; incluye
  ahora hallazgos sin CVSS o sin titulo, y el badge indica errores/avisos.
- Atajos de teclado: Ctrl/Cmd+K (buscador), Ctrl/Cmd+S (guardar), Esc (cerrar).

### Corregido
- El primer hallazgo ya no se separa del titulo de su seccion en el PDF (evita la
  pagina casi en blanco con solo el titulo): solo saltan de pagina los hallazgos que
  siguen a otro.
- La barra de la vista previa (Vivo/PDF) ahora se adapta al tema claro/oscuro.

## [0.10.0] - 2026-09-01

### Anadido
- Plantillas por tipo de informe con diseno propio: OffSec (estilo OSCP, claro/azul
  acero, sans) y HTB (oscuro de punta a punta, verde-lima). Cada plantilla fija su
  tema automaticamente al crear el proyecto.
- Familia HTB con selector en dos pasos: al elegir "HTB (certificacion)" aparece un
  2o selector con 8 certificaciones (CPTS, CWES, CAPE, COAE, CWEE, CWPE, CJCA, CDSA),
  cada una con su estructura de secciones e indice propios y texto base bilingue.
- Portadas con imagenes: logo propio y logo del cliente (HTB) e imagen representativa
  del caso (OffSec), subibles desde el editor; disposicion vertical por tema.
- Campos OSID y Email en la portada (para informes de examen), en tabla ordenada.
- Secciones genericas con titulo propio (apendices nombrados A-G, Technical Analysis,
  Exam Objectives, Phase 1/2, etc.), editables en el webapp y con entrada propia en
  el indice.
- Splash de arranque minimalista (patita + report-gen, fade-out al cargar).

### Corregido
- Coherencia editor <-> informe: el listado de secciones a la izquierda coincide
  exactamente con el indice del informe en cada plantilla (se elimino el forzado de
  secciones "obligatorias"; ahora son solo recomendadas y el preset manda).
- El selector de plantillas del modal se repuebla al abrir, respetando el idioma de
  la interfaz (antes quedaba en espanol al cambiar a ingles).
- El validador ya no marca como error las secciones genericas (con titulo propio).
- i18n completado en el modo maquina, el modo secciones y las nuevas etiquetas.

### Nota de marca
Los nombres "estilo OSCP/HTB" y las certificaciones (CPTS, CWES, etc.) son
descriptivos. report-gen no esta afiliado ni respaldado por OffSec ni Hack The Box y
no reproduce sus plantillas oficiales: los disenos, la estructura y el texto son
propios; los logos los aporta el usuario.


### Anadido
- Plantillas (presets) de secciones al crear proyecto: Pentest cliente, Examen de
  certificacion (estilo OSCP), certificacion HTB (estilo CPTS: pentest de red con
  narrativa de ataque, y estilo CWES: explotacion web), y CTF/Maquina. Encienden las
  secciones tipicas y rellenan texto base bilingue (ES/EN). Nombres descriptivos, sin
  logos y con nota de no-afiliacion a OffSec / Hack The Box.

## [0.9.0] - 2026-09-01
### Anadido
- Buscador global: campo en la barra superior que busca una palabra en TODO el
  proyecto (portada, contactos, alcance, secciones, hallazgos, maquinas y pasos),
  muestra resultados con contexto resaltado y navega al sitio con un clic.
- Calculadora CVSS: barra "Pegar vector" — pega un vector completo (3.1 o 4.0, con o
  sin prefijo, admite espacios) y calcula al instante; detecta la version y cambia
  sola. Sigue disponible el modo casilla por casilla.
- Duplicar hallazgo (copia todo el contenido con nuevo id).
- Renombrar proyecto (boton junto al selector); el nombre del selector se sincroniza
  solo al editar el titulo o el tema/idioma.
- Auto-foco en el titulo al crear un hallazgo; Enter para crear en el dialogo de
  nuevo proyecto; aviso al salir con cambios sin guardar.
- Editor: contactos y alcance se editan desde su propia seccion (antes solo en
  «Informe»); los datos siguen en meta.contacts/meta.scope.
- Vista previa colapsable (boton mostrar/ocultar; recuerda la preferencia).
- Eliminar proyecto (boton + endpoint DELETE seguro por ruta).
- Autodeteccion de CWE: al escribir un numero o nombre, autocompletado que filtra
  segun escribes y muestra el nombre (endpoint /api/cwe). Trae ~124 CWE comunes;
  `webapp/data/build_cwe.py` genera el catalogo COMPLETO de MITRE (requiere red).
- i18n del sitio: toggle ES/EN que traduce toda la interfaz (topbar, sidebar,
  editores, modales) y pone el informe en ese idioma; recuerda la preferencia.
### Cambiado
- UI del sitio: paleta oscura neutra con acento teal, tipografia sans, tamanos
  mayores; botones de anadir hallazgo agrupados.
### Corregido
- PDF con acentos en Windows (HTML temporal de Chromium en UTF-8); backend PDF
  cae a Chromium si WeasyPrint no carga (GTK ausente en Windows).
- Empaquetado: pyproject declara paquetes/modulos (arreglo de `pip install -e .`).
- Figuras Markdown: el borde se ajusta a la imagen (no una caja ancha).
- Preview a altura completa (regla #pdfPreview) y sin perder el scroll al hacer zoom.
- Eliminados presets, designs obsoletos y las referencias OSCP/CAPE del README que
  ya no formaban parte del flujo actual (quedan menciones conceptuales legitimas en
  ejemplos/plantillas).

## [0.8.0] - 2026-08-31

CVSS 4.0 de extremo a extremo (motor, JS, API y UI) validado contra la
implementacion de referencia de FIRST/Red Hat.

### Anadido
- CVSS 4.0 como motor separado de la 3.1 en el paquete `cvss/`: `v31.py` intacto,
  `v40.py` nuevo, interfaz comun en `__init__.py` con `score(vector)` que despacha
  estrictamente por version (`CVSS:3.1/`, `CVSS:4.0/`; cualquier otra -> ValueError).
- Parser 4.0 normativo estricto: prefijo de version, metricas y valores permitidos,
  orden canonico de FIRST, sin duplicados, sin segmentos vacios (barra final/doble
  barra) y todas las Base presentes. No normaliza entradas mal formadas: las rechaza.
- `effective_metrics()` (defaults 4.0 sin mutar el parsed: original -> parsed ->
  effective), `eq1..eq6`, `macrovector()` e interpolacion `_score()` portada de la
  implementacion de referencia FIRST/Red Hat (misma aritmetica; sin "mejorarla",
  el objetivo es same input -> same output).
- Artefactos de referencia congelados: tabla oficial MacroVector->score
  (`v40_lookup.py`, 270 entradas) y `MAX_COMPOSED`/`MAX_SEVERITY`/`EPSILON`
  (`v40_constants.py`).
- `cvss.score('CVSS:4.0/...')` devuelve `{score, severity, vector, macrovector}`.

### Verificacion
- Integridad estructural: los EQ derivan exactamente el espacio de los 270
  MacroVectors oficiales (y los 5 pares validos EQ3/EQ6).
- Corpus de referencia externo congelado (`tests/reference/first_v40_vectors.json`,
  367 vectores: 270 MacroVectors, 101 scores distintos 0.0-10.0, anclas y el caso
  de redondeo del issue como regresion permanente).
- Sin divergencias (0) entre `v40` y una copia VERBATIM del algoritmo de la
  implementacion de referencia FIRST/Red Hat (ramas exactas, incl. EQ3/EQ6 sin
  colapsar) sobre 19.815 vectores aleatorios + el corpus; anclas publicadas por
  FIRST (10.0, el 8.7 interpolado del issue, 0.0) correctas.
- Tests en dos clases: `test_cvss_v40.py` (propiedades propias: parser, EQ,
  invariantes) y `test_cvss_v40_reference.py` (vs el oraculo de referencia).

- Port JavaScript de CVSS 4.0 (`webapp/static/cvss40.js`): port mecanico del Python
  validado (no un tercer algoritmo); las tablas JS se generan desde los datos de
  Python, asi que solo el algoritmo es manual. Lo usa la calculadora web sin duplicar
  el algoritmo en app.js.
- Paridad Python<->JS: 0 divergencias en SCORE **y** en MACROVECTOR sobre el corpus
  congelado (367) + ~20k deterministas (20.087 en total, 270/270 MacroVectors);
  test separado de effective_metrics/defaults (E:X->A, CR/IR/AR:X->H, modificadas
  X->base, MSI:S/MSA:S -> EQ4). Anclas de FIRST en JS: 10.0 / 8.7 / 0.0.

- Integracion web 4.0 (sin tocar los motores CVSS):
  - `/api/cvss`, politica de despacho documentada: si `version` esta presente se
    respeta estrictamente; si falta, compat legacy (prefijo CVSS:4.0/ -> 4.0; el
    resto o `metrics` -> 3.1); si `version` y el prefijo del vector se contradicen
    -> 400. En modo 3.1 un vector debe empezar por CVSS:3.1/ (o enviar `metrics`);
    en 4.0 debe empezar por CVSS:4.0/. Version no soportada / vector invalido -> 400,
    nunca cross-version silencioso ni score parcial. 3.1 conserva su comportamiento;
    4.0 devuelve {score, severity, vector, macrovector}.
  - UI: selector CVSS 3.1 / 4.0 en la calculadora del hallazgo; al cambiar de version
    se reconstruyen las metricas y se descarta el estado incompatible. La logica 4.0
    NO se duplica en app.js: la UI llama a `cvss40.js` (buildVector canonico + score).
    Alcance: calculadora CVSS 4.0 Base (11 metricas); las opcionales (Threat,
    Environmental, Supplemental) toman sus defaults, el MOTOR ya las soporta, y su
    edicion desde la UI queda para v0.9+.
  - Verificado con Playwright: UI 4.0 == backend Python (10.0/000100 y 8.7/001200
    interpolado), vector en orden canonico, sin errores de consola, y 4.0 -> 3.1
    resetea el estado.
- Tests nuevos: API (`test_api_cvss.py`: 3.1 preservado, 4.0 shape, version/vector
  invalidos 4xx, sin cross-version) y `test_ui_loads_cvss40.py` (index.html carga
  cvss40.js antes de app.js; app.js no duplica tablas 4.0). Skips de Node ahora via
  `pytest.skip`/runner (PASS vs SKIPPED); CI instala Node. Suite: 86 tests.

### Referencia (procedencia)
- Implementacion y datos: `RedHatProductSecurity/cvss`, release v3.6 (commit
  2f149099257ae06b98cef252efc440bddafe61e5, 2026-08-04), ficheros `cvss/cvss4.py` y `cvss/constants4.py` (este ultimo
  contiene MAX_COMPOSED, MAX_SEVERITY, EPSILON y CVSS_LOOKUP_GLOBAL).
- Origen de la tabla lookup: FIRSTdotorg/cvss-v4-calculator (`cvss_lookup.js`),
  vendorizada por FIRST/Red Hat.

- Corroboracion del changelog upstream: v3.2 "Fixes CVSS v4.0 rounding issues /
  Makes rounding match official Javascript implementation" respalda la aritmetica
  de redondeo portada (EPSILON + Decimal half-up).

### Sello de referencia (cerrado)
- Python vs implementacion de referencia = 100%: ejecutado el paquete upstream
  `cvss==3.6` de PyPI (RedHatProductSecurity/cvss), SIN modificar, en subproceso
  aislado, sobre 20.087 vectores (corpus congelado + ~20k deterministas, 270/270
  MacroVectors): 0 errores de parseo, 0 divergencias de score. Script reproducible:
  `seal_upstream.py`.
- Procedencia resuelta: el sello confirma que los artefactos vendorizados
  (`v40_lookup.py`, `v40_constants.py`) corresponden a la referencia v3.6
  (commit 2f149099257ae06b98cef252efc440bddafe61e5); se elimina el residuo
  "master@2026-08-31".
- [hecho] Paridad Python<->JS 4.0 (score + macrovector) sin tocar la UI.
- [hecho] Integracion web: /api/cvss por version + selector UI 3.1/4.0 (UI == backend).
- [hecho] Regresion completa (incl. 3.1): 86/86.
- Nota (compat parser): el `parse_vector` de upstream acepta metricas fuera de orden;
  el nuestro es estricto. El sello compara solo vectores canonicos (validos para ambos).

Nota: `cvss/v40.py` permanece congelado (misma aritmetica que la referencia; solo
se modificaria ante una divergencia contra upstream, que no la hay).

### Seguridad / robustez (auditoria exhaustiva)
- Slug de proyecto capado a 80 chars: un slug enorme ya no crashea con OSError (500).
- Endpoints endurecidos: un body JSON no-dict (lista/string/null) devuelve 400 en vez
  de 500 en /api/cvss, /api/validate, /api/md, crear y guardar proyecto; el PUT con
  body invalido ya NO sobrescribe el proyecto con vacio.
- /api/cvss coacciona el vector a string (antes un vector numerico crasheaba).
- proj_dir con defensa en profundidad: el path resuelto debe quedar dentro de projects/.
- i18n completado: el modo maquina (fases, pasos, evidencia), el boton de preview y el
  titulo "Contenido" ahora traducen al ingles. CSS muerto eliminado.

### Corregido
- Export DOCX/MD de maquinas: exportar un informe con un hallazgo `machine` (sin
  `severity`) ya no crashea (`KeyError: 'severity'`); en el resumen aparece como
  "Maquina" sin score, con sus fases/pasos/comandos y tabla de flags.
- Resumen de hallazgos: las maquinas ya no cuentan como severidad "Media" ni entran
  al grafico; aparecen listadas como "Maquina" y se mencionan aparte en el intro.
- Log de PDF: se silencia el bloque de aviso de WeasyPrint; una sola linea limpia
  cuando cae a Chromium.
- UX: selector de color para el acento, selector de fecha nativo, tooltips en cada
  metrica CVSS, confirmacion al borrar un hallazgo, boton "copiar vector", y
  placeholders con ejemplos en portada y hallazgos (IP, SO, puertos, ruta de ataque), pista en el modo
  maquina (el comando va en el paso, no en el nombre de fase) y estado vacio que guia
  a "Nuevo proyecto".
- Validador: los vectores CVSS 4.0 validos ya no se marcan como "formato
  inesperado" (la regex solo conocia 3.1); ahora el 4.0 se valida con el motor CVSS.
- Informe: la etiqueta CVSS ahora refleja la version real del vector (CVSS 4.0 /
  CVSS 3.1) en PDF/HTML, DOCX y Markdown; antes rotulaba siempre "CVSS 3.1".
- Preview no ejecuta scripts del contenido (iframe sandbox) y el HTML crudo de la
  prosa se muestra como texto literal (payloads visibles, sin self-XSS).
- Textareas de contenido auto-expandibles (crecen con el texto, sin scroll).
- Portabilidad Windows: el HTML temporal que se pasa a Chromium para el PDF se
  escribe ahora en UTF-8 (`NamedTemporaryFile(..., encoding="utf-8")`); en Windows
  el default es cp1252 y las tildes/acentos salian como "?" en el PDF, aunque el
  preview HTML se veia bien. Con test de regresion independiente de plataforma.
- Portabilidad Windows: los tests que leen/escriben archivos (`test_ui_loads_cvss40`,
  `test_cvss_v40_js_parity`) ahora fijan `encoding="utf-8"`; en Windows el default
  es cp1252 y fallaba al leer `app.js` (iconos multibyte de la barra del editor). El
  codigo del producto ya usaba utf-8 explicito en todas sus lecturas/escrituras.
- Empaquetado: `pyproject.toml` declara explicitamente los paquetes (`cvss`,
  `exporters`) y modulos (`engine`, `export`, `sections`, `validate`, `wizard`),
  arreglando el fallo de setuptools "Multiple top-level packages ... flat-layout"
  que rompia `pip install -e .` (y por tanto el CI). `license` pasa a string SPDX
  ("MIT"), sin la deprecacion de la tabla.
- Backend PDF mas robusto: si `import weasyprint` falla por CUALQUIER motivo
  (p. ej. `OSError` por faltar GTK en Windows), el backend `auto` cae a Chromium
  en vez de crashear; con `--backend weasyprint` el mensaje indica la causa.
- Typo en el docstring de `export.py` ("e re-exporta" -> "y reexporta").

## [0.7.0] - 2026-08-31
### Cambiado
- Refactor puramente estructural de la exportacion: `export.py` (950 lineas) se
  divide en el paquete `exporters/` (`common.py`, `markdown.py`, `docx.py`,
  `pdf.py`) y queda como fachada de compatibilidad de ~50 lineas. Sin cambios de
  comportamiento: salida MD identica byte a byte y DOCX identico (mismo contenido
  y estilos); los 40 tests siguen verdes antes y despues. Los consumidores
  (`webapp`, tests, CLI) no cambian: siguen usando `import export`.
- Micro-limpieza en la subida de imagenes: la imagen se abre una sola vez con
  context manager (`with Image.open(...)`).

## [0.6.0] - 2026-08-31
### Anadido
- Suite de tests con pytest (`tests/`): CVSS (vectores oficiales + paridad
  Python/JS sobre 2592 combinaciones), motor, secciones, export PDF/DOCX/MD,
  seguridad (traversal, saneo, subida de imagenes) y validacion. Runner de
  stdlib (`tests/run_stdlib.py`) para entornos sin pytest.
- Validacion de engagement sin dependencias (`validate.py`): IDs duplicados,
  severidad invalida, hallazgo machine sin host, CVSS mal formado, severidad
  incoherente con CVSS y secciones inexistentes. Integrada en el motor (avisos
  al generar) y en la app (`POST /api/validate`).
- Scaffolding de proyecto: `pyproject.toml` (config de pytest y Ruff),
  `.gitignore`, `LICENSE` (MIT), este `CHANGELOG.md` y CI en GitHub Actions.

### Corregido
- Contradiccion en el README: el DOCX se genera con python-docx puro (sin
  LibreOffice), no convirtiendo HTML.
- README: aclarado que `tests/run_stdlib.py` evita pytest pero no las
  dependencias runtime (los tests importan engine, Flask, Markdown, etc.).
- Validacion: los fallos internos del validador ya no se silencian; se muestran
  como aviso, para no dar por validado un engagement cuando el validador fallo.
- Subida de imagenes endurecida: validacion real con Pillow (`Image.verify()`,
  no solo magic bytes), formato restringido a png/jpg/gif/webp, extension
  derivada del formato REAL detectado (el nombre no decide el tipo servido),
  limite HTTP (`MAX_CONTENT_LENGTH`) y lectura acotada en memoria.
- Marcadores de numeracion a dos pasadas endurecidos (fuera de flujo dentro de
  contenedor posicionado) para paginacion identica entre pasadas en informes
  largos.

## [0.5.0] - 2026-08-31
### Anadido
- Constructor modular de secciones con catalogo canonico unificado y editor
  Markdown por seccion estilo SysReptor (barra, Write/Preview, imagenes).
- Secciones obligatorias bloqueables; toggle de idioma ES/EN a un clic.
- Export DOCX y Markdown conscientes de las secciones activas.

### Corregido
- Auditoria de seguridad: crash por tema invalido, inyeccion de ruta via
  meta.theme, subida de imagen con nombre malicioso.

## [0.4.0] - 2026-08-31
### Anadido
- App web local estilo SysReptor: editor de hallazgos, calculadora CVSS 3.1,
  catalogos OWASP (web y LLM), preview en vivo y export multiformato.
- DOCX reescrito en python-docx puro (identico al PDF, sin LibreOffice).

## [0.1.0 - 0.3.0] - 2026-08-31
### Anadido
- Motor de render (WeasyPrint/Chromium), temas, i18n ES/EN, numeracion de TOC a
  dos pasadas, hallazgos vuln/machine, asistente CLI y export inicial.

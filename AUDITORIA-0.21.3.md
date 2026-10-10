# Auditoría de report-gen 0.21.2 y correcciones 0.21.3

Fecha: 8 de octubre de 2026. Revisión de código, reproducciones sobre copias aisladas, pruebas automatizadas y revisión visual de exportaciones.

El desbordamiento del HTML portátil era real. No se limitaba a 320 px: el informe Banco Lumbre en español alcanzaba 345 px de ancho a 320 px y 365 px a 360 px. La versión corregida permite que los controles reduzcan su ancho y se distribuyan dentro de la pantalla. No se oculta el desbordamiento global ni se recorta el informe para hacer pasar la medición.

La revisión también encontró problemas de conservación de contenido, importación, teclado y respaldo. Las correcciones se identifican como **0.21.3**. El ZIP 0.21.2 suministrado, el proyecto web v10 y el PDF de Banco Lumbre se conservaron como fuentes de comparación; esta entrega actualiza la herramienta.

## Alcance y criterio

Se revisaron el generador HTML portátil, las exportaciones HTML/PDF/Markdown/DOCX, los contratos que verifican las entregas, la biblioteca de hallazgos, el editor ES/EN, la entrada YAML y los respaldos de proyecto y espacio de trabajo. La demo Nimbus y los perfiles existentes se conservaron.

Los hallazgos siguientes son defectos reproducidos, agrupados por comportamiento. «Media» y «baja» expresan prioridad de ingeniería dentro de una herramienta local; no son puntuaciones CVSS ni una certificación de seguridad. Las comprobaciones positivas del servidor no demuestran ausencia de todas las vulnerabilidades.

## Defectos corregidos

| ID | Prioridad | Comportamiento anterior | Corrección |
| --- | --- | --- | --- |
| HTML-01 | Baja | El mínimo intrínseco del selector de severidad ensanchaba la barra y la página en móvil. | Controles con mínimo de ancho cero y ancho limitado por su contenedor. |
| HTML-02 | Media | Volver a pulsar un enlace al mismo hallazgo no provocaba `hashchange`; el destino seguía oculto por los filtros. | Los enlaces internos ordinarios también revelan el destino, restablecen filtros y recuperan la vista completa. |
| HTML-03 | Baja | El margen fijo de anclas era menor que la barra sticky cuando esta ocupaba varias filas. A 601 px tapaba unos 23 px del comienzo de la sección. | El margen sigue la altura real de la barra y se actualiza cuando cambia su tamaño. |
| EXP-01 | Media | Word convertía WebP a PNG, pero el inspector comparaba la huella con el WebP original y rechazaba una exportación legítima. | Renderizado y verificación comparten la conversión; se comprueba la huella exacta del PNG esperado. No se relaja la comparación de imágenes. |
| EXP-02 | Media | Un vector CVSS sin score desaparecía en HTML/PDF. La variante `cvss: null` producía `None` en Markdown/Word y fallaba la entrega. | Se conserva el vector, se omite la puntuación ausente y se mantiene explícitamente el cero. Cubierto en ES/EN, ambos diseños y cuatro formatos. |
| EXP-03 | Media | Markdown interpretaba la puntuación de una referencia de texto plano como énfasis o enlace y alteraba su contenido. | Referencias escapadas como texto literal y lista separada correctamente del párrafo anterior. |
| EXP-04 | Media | Una imagen incluida dentro de un enlace desaparecía en Word; el enlace también podía perder estilos internos. | Conversión recursiva que conserva imagen, pie, enlace, negrita, código y saltos de línea. |
| EXP-05 | Media | El contrato omitía las referencias bibliográficas; modificar una referencia podía seguir obteniendo una verificación satisfactoria. | Las referencias forman parte del contenido esperado y se comparan en HTML, Markdown y Word. |
| EXP-06 | Media | Un enlace a `#` generaba un destino Word sin marcador y bloqueaba una entrega válida. | Marcador real al inicio del documento. `None` continúa significando ausencia de enlace. |
| EXP-07 | Baja | Invocar el perfil de inspección HTML/Markdown sin contrato esperado podía producir `KeyError`. | Valores opcionales coherentes para esa API. |
| ED-01 | Media | Importar JSON con campos del tipo incorrecto modificaba el búfer, anunciaba éxito y fallaba después al guardar o editar. | Validación sobre una copia antes de incorporar hallazgos. Una respuesta tardía no sustituye cambios escritos entretanto ni datos de otro proyecto. |
| ED-02 | Media | Varios overlays del editor no aseguraban foco dentro, fondo modal ni restauración del foco. | Diálogos nativos con nombre, foco, Escape y restauración. Los errores de creación aparecen dentro del diálogo, conservando los campos y el reintento. |
| ED-03 | Baja | Selector de modo, referencias e imágenes carecían de nombres adecuados; filas con rol de botón alteraban la semántica de listas. | Controles etiquetados, imágenes con alternativa y botones nativos dentro de las listas. |
| ED-04 | Baja | Ctrl+K en móvil intentaba enfocar el buscador dentro de un menú cerrado. | Abre el menú y después enfoca el buscador. |
| ED-05 | Baja | El botón de eliminación tenía contraste insuficiente en el tema oscuro observado. | Colores ajustados y comprobación en los temas claro y oscuro. |
| ED-06 | Baja | El indicador de exportación podía conservar `aria-controls` hacia un drawer inexistente. | La referencia existe únicamente mientras existe el drawer. |
| LIB-01 | Media | La limpieza por expresiones regulares omitía formas de imágenes Markdown y referencias del proyecto, incluidas rutas Windows; una plantilla podía conservar recursos privados o apuntar a otro hallazgo. | Análisis semántico de las referencias activas, retirada de imágenes y destinos locales, y nueva limpieza después de resolver variables. |
| LIB-02 | Media | La limpieza podía retirar sintaxis literal de imagen dentro de comandos y bloques de código. | Se preserva el código literal y se rechazan transformaciones ambiguas que alteren contenido ajeno. Las citas bibliográficas de texto plano se conservan. |
| BK-01 | Media | Un respaldo antiguo sin historial omitía la única revisión previa en `engagement.yaml.bak`; restaurar ese respaldo devolvía el estado actual. | La copia válida y sus recursos propios se incorporan como snapshot estándar, con los bytes originales, sin modificar el origen al exportar. |
| BK-02 | Media | Se podían crear `straße` y `strasse`; el respaldo se descargaba con éxito pero su restauración rechazaba la colisión Unicode. | Creación rechazada con 409 y comprobación previa del namespace antes de respaldar instalaciones que ya tengan colisiones. No se renombra ni se omite un proyecto en silencio. |
| BK-03 | Baja | Un fallo al limpiar después del commit devolvía 503 aunque los datos ya estuvieran instalados. | Éxito con aviso visible, registro de recuperación conservado y limpieza reintentable. No se revierte una restauración ya completada. |
| IN-01 | Baja | Escalares YAML pequeños, como `!!int ""`, podían propagar excepciones de constructores y producir 500. | Normalización limitada a la construcción YAML; GET/importación responden 422 sin instalar un proyecto parcial ni revelar el escalar. |

## Evidencia y pruebas de regresión

La suite completa de 0.21.3 aprobó **1.050 casos Python**, sin fallos, errores ni omisiones. Incluye 196 casos nuevos: 16 de HTML portátil, 117 de exportaciones, 40 de biblioteca, 16 de entrada YAML y 7 de respaldos. La suite original de 0.21.2 también se ejecutó completa: 854 casos aprobados.

Las mismas guardas nuevas sobre el original produjeron 12 fallos de 16 en HTML portátil, 29 de 40 en biblioteca, 12 de 16 en YAML y 7 de 7 en respaldo. No se suman estas ejecuciones repetidas al total de casos de la suite final.

En Chromium 153.0.8010.0, el editor aprobó **72 comprobaciones** de diálogos, importación, concurrencia, Deshacer, teclado y avisos de restauración. El recorrido adicional con Nimbus aprobó 29 comprobaciones. Las suites npm aprobaron 12 pruebas de guardado/borradores y 29 comprobaciones DOM/API. Ruff no detectó errores en las reglas configuradas. Los comandos y límites están en VALIDACION-0.21.3.md.

La matriz visual del HTML portátil cubrió Banco Lumbre ES y datos sintéticos ES/EN a 320, 360, 390, 601, 768 y 1366 px: **18 estados sin desbordamiento de página ni excepciones JavaScript**. Se comprobó búsqueda, severidad, pendientes, máquinas, vista ejecutiva, teclado, lectura sin JavaScript e impresión de la vista elegida.

El contenido de `<main>` del informe de banca y de las dos muestras sintéticas mantuvo exactamente la misma huella antes y después de la corrección del HTML portátil. El cambio de presentación no reconstruyó el contenido de la evaluación ficticia.

Las exportaciones se comprobaron con documentos sintéticos y con sus inspectores reales. Las mutaciones deliberadas de imágenes, posición de evidencia, referencias, vectores y destinos de enlaces fueron rechazadas en los casos cubiertos. La conversión WebP conserva la comprobación de bytes de la derivada prevista; no se sustituyó por un conteo de imágenes.

Se renderizaron tres DOCX finales de cuatro páginas cada uno con LibreOfficeDev 26.8 y se revisaron sus páginas, incluyendo imágenes enlazadas, WebP y formato dentro de enlaces. Las páginas finales fueron idénticas a las ya inspeccionadas. Se revisaron visualmente también las cuatro páginas del PDF del caso `cvss: null`: el vector está completo, sin `None` ni una puntuación inventada.

La revisión independiente detectó y corrigió tres problemas durante el desarrollo antes de entregar: pérdida de citas bibliográficas por confundir prosa con rutas, rutas Windows confundidas con esquemas URL y pérdida de Deshacer al reemplazar el modelo del editor. El caso borrar → importar → deshacer → guardar conserva valores, UID, ID, referencias y el hallazgo importado.

## Diseño y accesibilidad

Las mejoras aplicadas responden a acciones concretas: controles que caben en móvil, anclas visibles, diálogos que se operan por teclado, errores dentro del contexto de trabajo, nombres de controles y contraste del botón de eliminación. Se conserva el sistema visual existente.

El barrido axe de 12 vistas del editor con la demo Nimbus no detectó infracciones en las reglas ejecutadas. Quedaron comprobaciones incompletas de contraste y correspondencia entre etiqueta y nombre; requieren revisión manual. No se presenta este resultado como accesibilidad completa ni como certificación. Tampoco se ejecutó un lector de pantalla de escritorio.

Como evolución de UX, priorizaría:

1. **Filtros móviles progresivos:** agrupar opciones secundarias en un plegable, mostrando siempre el filtro activo y la acción de limpiar. Reduciría la altura inicial de la barra sin quitar funciones.
2. **Importación explicable:** vista previa del número de hallazgos, campos rechazados y cambios que se incorporarán antes de confirmar una importación grande.
3. **Revisión por formato:** acceso directo desde un hallazgo a su posición en la vista previa de cada exportación, con sus límites de comprobación visibles.
4. **Compatibilidad continua:** ejecutar las guardas nuevas en la CI y ampliar la revisión visual con Word de escritorio y lectores de pantalla. El workflow está preparado; no se afirma que una ejecución remota ya haya ocurrido.

Estas son propuestas de producto, no defectos bloqueantes adicionales reproducidos.

## Código, paleta y mantenimiento

Se revisaron los cambios con Ruff y las regresiones existentes. La limpieza de plantillas dejó de depender de una expresión regular insuficiente; la conversión de imágenes Word comparte un helper con su verificador. El nuevo módulo está registrado en el empaquetado. La identidad de la versión se mantiene en `version.py` y se alinea con los metadatos npm.

Se comprobó y corrigió un problema concreto de contraste. No se hizo una recoloración global ni se retiraron tokens o helpers únicamente porque una búsqueda local pareciera no encontrarlos: los templates, exportadores y APIs opcionales también forman parte del uso. Los colores de marca presentes en perfiles distintos no son, por sí solos, código muerto o paletas desactualizadas.

No se cambiaron las versiones de dependencias ni se ejecutó un análisis nuevo de vulnerabilidades de dependencias contra bases externas. No se atribuyen a esta entrega las comprobaciones históricas de ese tipo.

## Actualización y límites

Extrae 0.21.3 en una carpeta nueva y conserva la instalación anterior hasta verificar tus proyectos. No copies su entorno virtual. Los pasos de instalación y migración están en README.md y README.en.md.

**Caso heredado importante:** el exportador de 0.21.2 sigue omitiendo una `.bak` que sea la única revisión previa. Conserva una copia completa de los directorios de proyectos y bibliotecas, úsala en una instalación nueva de 0.21.3 y genera allí el respaldo corregido. Un ZIP antiguo que ya omitió esos bytes no permite recuperarlos automáticamente.

La validación local usó Chromium real en modo headless, Linux y Python 3.12. No se ejecutaron Firefox local, Microsoft Word de escritorio, Windows ni macOS para esta entrega. LibreOfficeDev no garantiza la misma paginación que Word. Los filtros HTML son presentación, no control de acceso; la biblioteca tampoco certifica que la prosa libre carezca de información privada.

El paquete incorpora las fuentes, las pruebas nuevas, los perfiles y la documentación, con un manifiesto SHA-256 actualizado. Los proyectos temporales, capturas y dependencias del entorno de auditoría no forman parte de la distribución.

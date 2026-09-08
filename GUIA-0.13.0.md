# report-gen 0.13.0 · Guía de las nuevas funciones

Esta versión mantiene tus diseños, CVSS, editor Markdown y exportadores. Añade gestión del proyecto desde el borrador hasta la entrega y el retest.

## Actualizar tu instalación

1. Cierra el servidor anterior y conserva una copia de esa carpeta.
2. Descomprime la versión nueva en otra carpeta.
3. Copia **toda** la carpeta `webapp/projects/` anterior. Incluye sus imágenes y, al actualizar desde 0.13, sus originales e historial. Copia también `webapp/library/` si existe y tus informes propios en `reports/`.
4. Instala con `python -m pip install -e .` y ejecuta `python webapp/app.py`.
5. Abre `http://127.0.0.1:8080` y recarga la pestaña. Los proyectos antiguos reciben sus identificadores permanentes al abrirse por primera vez.

No copies únicamente `engagement.yaml` si necesitas recuperar evidencias o versiones. Los campos y números visibles F1, F2, etc. se mantienen; cada hallazgo tiene además una referencia permanente que sigue siendo la misma al reordenarlo.

## Probarlo con datos ficticios

Pulsa **Abrir respaldo**, selecciona `examples/workflow-demo-project.zip` y escribe un nombre nuevo. El ejemplo incluye cuatro hallazgos, dos activos, cobertura, una evidencia censurada, una entrega inicial y un retest. Puedes comparar las versiones y restaurar cualquiera. Todas las personas, objetivos y evidencias del ejemplo son ficticios.

## Versiones y restauración

En **Versiones**, crea un punto con nombre y etapa: **Borrador**, **Entregado al cliente** o **Retest**. La etapa es una etiqueta manual; no envía el informe ni acredita por sí sola una entrega.

Los autoguardados conservan también los estados anteriores. Activa **Mostrar autoguardados** para verlos. Las imágenes iguales se almacenan una sola vez por proyecto mediante sus hashes. No se borran versiones automáticamente: el historial puede crecer con las evidencias nuevas.

**Comparar** muestra los campos anteriores y posteriores. Puedes comparar una versión con el proyecto actual o con otra versión. Los hallazgos se comparan por su referencia permanente: cambiar su orden no los convierte en hallazgos nuevos.

**Restaurar** recupera el YAML, imágenes y originales de esa versión, conservando el estado actual en el historial. El botón superior **Restaurar** recupera la revisión anterior del YAML con las imágenes de esa revisión. En instalaciones antiguas que únicamente tengan `.yaml.bak`, esa copia anterior sigue disponible, pero no puede recuperar imágenes que nunca fueron archivadas.

## Revisión antes de entregar

En **Revisión de entrega**, el editor guarda primero el proyecto y comprueba:

- Títulos, descripción, impacto o remediación sin completar.
- Falta de pasos de reproducción o evidencias.
- Imágenes ausentes, rutas no permitidas y vínculos rotos.
- Texto TODO, TBD, FIXME y variables sin resolver.
- Pruebas pendientes o bloqueadas, plazos vencidos y correcciones marcadas como verificadas sin un retest registrado.
- Los errores y avisos de la validación existente, incluido CVSS.

**Ir al campo** abre el hallazgo o la vista correspondiente. Los avisos permiten trabajar con borradores. Los errores de estructura, CVSS, recursos o vínculos inválidos impiden generar una entrega incoherente. Estas comprobaciones no sustituyen la validación técnica de un pentester.

## Correcciones y retest

Cada hallazgo permite registrar responsable, fecha objetivo y estado:

| Estado | Interpretación |
| --- | --- |
| Abierto | La corrección sigue pendiente. |
| En corrección | Se está trabajando o la corrección es parcial. |
| Corrección comunicada | El cliente informa de una corrección que aún requiere comprobación. |
| Corregido y verificado | La comprobación confirma la corrección. |
| Riesgo aceptado | La organización ha registrado la aceptación del riesgo. |
| No verificable | No fue posible comprobar el estado. |

En **Correcciones y retest**, añade fecha, evaluador, resultado observado y evidencias. Se conserva cada comprobación. Un resultado corregido, abierto, parcial o no verificable actualiza el estado correspondiente. No escribas que está verificado solamente porque el cliente haya anunciado un cambio.

La opción **Incluir seguimiento y retest** añade al informe el resumen de estados, responsables y fechas, seguido del detalle de las comprobaciones y sus evidencias. **Exportar informe con retest** usa el formato seleccionado en la barra superior e incluye los hallazgos del proyecto y el seguimiento; no elimina hallazgos abiertos ni crea una declaración automática de seguridad.

## Galería de evidencias

En **Evidencias**, sube imágenes o registra las que ya existen en el proyecto. Añade título y pie de imagen. Una misma evidencia puede vincularse a varios hallazgos y a comprobaciones de retest.

**Anotar / censurar** permite arrastrar una zona sobre la imagen o introducir sus coordenadas como porcentajes. Admite recuadros, flechas, texto y censura negra. Al guardar:

- Las anotaciones y la censura quedan incorporadas a los píxeles de una nueva imagen PNG.
- La copia procesada no conserva EXIF, miniaturas, comentarios ni fotogramas adicionales.
- Todos los vínculos y referencias a esa imagen se actualizan en el proyecto.
- El original permanece separado y puede descargarse expresamente desde la galería.

Las ediciones se aplican sobre la copia procesada actual. No se puede retirar la censura de esa copia. Para recuperar un estado anterior, restaura una versión del proyecto o vuelve a registrar el original descargado. Revisa visualmente la copia guardada para confirmar que la zona cubre todo el dato que deseas ocultar.

PDF, DOCX y el ZIP de Markdown usan las imágenes referenciadas de entrega. No incluyen los archivos guardados en `originals/` ni los objetos del historial. El respaldo editable completo sí los incluye.

## Activos, cobertura y limitaciones

En **Activos**, registra URLs, endpoints, hosts o redes. Los hallazgos admiten varios activos vinculados; el campo de objetivo anterior también se conserva para compatibilidad.

En **Cobertura**, registra cada prueba, su activo, su estado (realizada, pendiente, bloqueada o no aplica) y las observaciones. Documenta aparte las limitaciones del trabajo. Las casillas de inclusión permiten añadir o retirar del informe las secciones generadas de activos, cobertura y retest, sin borrar sus datos del proyecto.

## Biblioteca de hallazgos

La biblioteca se guarda en `webapp/library/findings.json`, junto a la herramienta, con versiones por plantilla. Puedes buscar por nombre, etiqueta y contenido; editar, exportar e importar la biblioteca completa.

Desde un hallazgo, pulsa **Plantilla**. Se retiran evidencias, activos, responsables, retests y referencias internas. Los valores conocidos de cliente y objetivo se convierten en variables. Antes de guardar, revisa el texto reutilizable: una herramienta no puede identificar automáticamente todos los datos del cliente presentes en una descripción, URL o comando.

Variables disponibles: `{{cliente}}`, `{{objetivo}}`, `{{evaluador}}` y nombres propios como `{{endpoint}}`. Al insertar, completa sus valores. Se crea un hallazgo con referencia nueva y sin heredar el historial de correcciones del cliente anterior.

Si el navegador conserva plantillas de versiones anteriores, aparecerán en **Plantillas antiguas de este navegador**. Ábrelas, revísalas y guárdalas en la nueva biblioteca. El contenido antiguo del navegador no se borra automáticamente. La migración requiere usar el mismo navegador, perfil y dirección de la instalación donde se guardaron.

Importar una biblioteca crea nuevas copias de sus plantillas y conserva sus versiones. No fusiona ni sobrescribe automáticamente plantillas del mismo nombre.

## Respaldo y traslado a otro equipo

**Respaldo del proyecto → Descargar respaldo ZIP** incluye YAML, imágenes, originales, configuración del informe y todo el historial. **Abrir respaldo** lo importa como otro proyecto, sin sobrescribir uno existente.

El importador verifica rutas, integridad de cada archivo y estructura, y rechaza enlaces simbólicos, archivos activos disfrazados de imágenes y archivos fuera del formato admitido. Límites: 256 MiB comprimidos, 512 MiB descomprimidos y 20.000 archivos. No admite cualquier ZIP arbitrario: utiliza el generado por **Respaldo del proyecto**.

El respaldo contiene material interno, incluidos originales anteriores a la censura, y no está cifrado. Guarda ese archivo con el acceso apropiado. Para entregar al cliente, usa **Exportar** en la barra superior. La biblioteca global de plantillas se exporta aparte desde **Biblioteca**.

## Paginación

Los hallazgos siguen fluyendo por el espacio disponible. Sus tablas se mantienen completas y se mueven a la página siguiente cuando sea necesario. Si una tabla supera una página por sí sola, el PDF detiene la exportación e indica qué hallazgo debes resumir o trasladar al procedimiento detallado. Las nuevas evidencias y listas de activos se añaden fuera de la tabla principal para no inflarla.

## Alcance de esta entrega

La herramienta sigue siendo local, para un único operador, con detección de conflictos entre pestañas. No se han añadido cuentas multiusuario, sincronización remota ni cifrado del disco. Las pruebas de esta entrega se ejecutaron en Linux, con PDF mediante WeasyPrint y Word renderizado con LibreOffice. Windows, Microsoft Word y el renderizador alternativo Chromium requieren comprobación en tu entorno.

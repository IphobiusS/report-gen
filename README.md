<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen, con Prometeo y Evaristo" width="300">
</p>

<a id="report-gen"></a>

# report-gen 0.44.0

<a id="qué-es"></a>

**Un editor local para convertir tus evaluaciones de seguridad en informes claros.** Organiza hallazgos, conecta evidencias, registra remediación y retest, y prepara **PDF, Word, Markdown con imágenes y HTML portátil** desde una revisión guardada.

[English](README.en.md) · [Português (Brasil)](README.pt.md) · [Guía completa](docs/guide.es.md) · [Cambios](CHANGELOG.md) · [Seguridad](SECURITY.md)

<a id="inicio-rápido"></a>

## Instalar y abrir

Ruta principal: **Linux/Kali y Python 3.11+**. Descarga y descomprime la [última versión publicada](https://github.com/IphobiusS/report-gen/releases/latest), o clona el repositorio:

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 scripts/install.py --desktop
~/.local/bin/report-gen
```

El instalador prepara `.venv`, descarga las dependencias con `requirements-audited.txt` y añade un acceso al menú de aplicaciones. No utiliza `sudo` ni instala paquetes del sistema. **Conserva la carpeta de la aplicación y su `.venv`: el acceso las necesita; no es un ejecutable autónomo.** Abrir el acceso después no reinstala dependencias.

Los datos quedan fuera de la aplicación, en `$XDG_DATA_HOME/report-gen` o `~/.local/share/report-gen` por defecto. Puedes elegir otra carpeta con `--workspace /ruta/datos`; si omites esa opción, se respeta `REPORT_GEN_WORKSPACE`. El instalador no mueve proyectos antiguos automáticamente.

Abre **http://127.0.0.1:8080** en tu navegador; `Ctrl+C` detiene el servidor. El acceso admite `--port 8081`. La ruta anterior `python3 start.py --ready` sigue disponible y conserva `webapp/` cuando no seleccionas una carpeta externa. **Node.js no es necesario para usar el editor.** Consulta [requisitos de PDF, migración y otras opciones](docs/guide.es.md#instalar-y-abrir).

<a id="demo"></a>

## Primer informe

1. En **Inicio**, elige **Probar demo Nimbus**: crea una copia editable de un caso ficticio con 12 hallazgos. Para tu propio trabajo, usa **Crear mi proyecto**.
2. En el proyecto, **Siguiente acción sugerida** te orienta según lo que ya has escrito. **Ver este paso en la guía** abre la ayuda correspondiente. La ayuda no completa ni valida los datos de tu evaluación por ti.
3. Guarda, revisa el **Inspector de publicación** y genera los formatos que necesites desde **Entregar**. Abre los archivos antes de compartirlos y conserva un respaldo privado del proyecto.

**Tutorial visual** está disponible desde el menú, con capturas ES/EN/PT ampliables y progreso local. La invitación inicial se puede omitir.

[Recorrido completo y recomendaciones](docs/guide.es.md#primer-informe).

<a id="características"></a>

## Qué puedes hacer

- **Documentar una evaluación:** alcance, metodología, activos, cobertura, hallazgos y pasos reproducibles; CVSS 3.1 y 4.0 cuando corresponda.
- **Trabajar con evidencia:** galería, pies de imagen, vínculos a hallazgos, copias censuradas e inspección de lo que se publicará.
- **Conservar el seguimiento:** identidades estables, revisiones recuperables, comparación con una entrega marcada, correcciones y matriz de retest.
- **Elegir la presentación:** crear un proyecto desde una galería con seis diseños generales y 30 perfiles especializados, agrupados por propósito. El idioma del informe es independiente del de la interfaz.
- **Separar destinatarios:** entregas técnica, ejecutiva y pública con planes de inclusión explícitos; la pública requiere texto aprobado y consentimiento registrado.
- **Relacionar evidencia y decisiones:** afirmaciones, límites, contexto de negocio, observaciones y revisión visual del PDF. [Flujo y requisitos opcionales](docs/evidence-decisions-0230.md).

| Formato | Archivo que recibes |
| --- | --- |
| PDF | Informe paginado `.pdf`. |
| Word | Documento editable `.docx`, con campos propios para el índice. |
| Markdown | ZIP con `report.md` y sus imágenes. |
| HTML portátil | Un `.html` autónomo con filtros de lectura. |

## Biblioteca y preparación del trabajo en 0.44.0

**Biblioteca de hallazgos → Catálogo curado** reúne 90 fichas originales en español, inglés y portugués: 18 web, 12 API, 8 identidad/AD, 8 infraestructura, 8 cloud, 6 móviles y 30 IA/LLM/agentes. Busca por texto o filtra por categoría e idioma. Cada ficha explica condiciones, evidencia necesaria, falsos positivos, corrección y retest, con fuentes y fecha de revisión. **Mi biblioteca** conserva tus plantillas y versiones.

Las fichas de IA incluyen inyección directa/indirecta/multimodal, RAG, memoria, herramientas, identidades de agentes, cadena de suministro, privacidad y límites de recursos. Referencias revisadas el 17-10-2026: OWASP LLM Top 10 2026, Agentic Applications 2026, MITRE ATLAS y NIST AI 100-2e2025. El selector de categorías OWASP 2025 permanece identificado con su edición; sus IDs históricos no se reinterpretan.

**Paquetes de trabajo** crea proyectos independientes con estructura y pruebas pendientes para siete especialidades. Puedes incluir explícitamente fichas sugeridas; empiezan sin verificar y sin severidad/CVSS asignados. **Informe comentado** explica nueve decisiones de redacción del caso ficticio Nimbus. Las ayudas junto a los campos contrastan ejemplos adecuados e insuficientes y no rellenan resultados automáticamente.

[Guía de biblioteca y paquetes](docs/knowledge.es.md) · [Protocolo de aceptación](docs/QA-KNOWLEDGE-0440.md). La fecha de revisión indica una edición del contenido, no una actualización en línea ni una garantía de cobertura exhaustiva.

## Inicio guiado en 0.43.0

En el primer acceso puedes elegir **Guiado** o **Completo** y cambiar después desde el selector de vista. Ambas opciones conservan las mismas rutas, herramientas y datos. Guiado reduce la densidad inicial plegando herramientas avanzadas y ofrece una siguiente acción; puedes desplegarlas cuando las necesites.

El recorrido opcional **Proyecto → Alcance → Hallazgos → Evidencias → Revisión → Entrega** explica y destaca controles del editor. Permite saltar, volver, pausar, reanudar y reiniciar. **Explícame esta sección** ofrece ayuda contextual. La preferencia de vista se recuerda por espacio de trabajo y el progreso de aprendizaje por proyecto, en este navegador; si el almacenamiento no está disponible, funcionan durante la sesión.

La práctica abre una copia ficticia independiente de Nimbus, identificada como tal, y permite volver a tu proyecto. Completar una guía nunca verifica hallazgos, aprueba evidencias, ejecuta pruebas ni certifica una entrega. El **Tutorial visual** con capturas sigue disponible. [Uso del inicio guiado](docs/guide.es.md#inicio-guiado-y-ayuda-contextual).

## Flujo de evaluación 0.42.0

La revisión conecta la cola filtrada, la evidencia fijada junto al editor, las selecciones de tabla y la búsqueda de activos, evidencias y comentarios. **Guardar y siguiente** conserva la sesión de revisión activa.

Los hallazgos admiten **instancias afectadas** con responsable, plazo, evidencia y retests independientes. El estado general se deriva del conjunto: una corrección parcial no cierra los destinos pendientes. Los **planes de prueba** registran metodología y versión, roles, organizaciones y resultados; las **rutas de ataque** distinguen transiciones demostradas, inferidas y bloqueadas.

La **evidencia HTTP** separa originales privados de copias revisadas para entrega técnica. Incluye importación HAR, comparación y una extensión opcional de Burp para enviar únicamente mensajes seleccionados. Las reimportaciones de escáner permiten comparar y vincular nuevas observaciones conservando las decisiones del analista.

Los perfiles versionados de cliente y los paquetes de revisión editorial reúnen requisitos y cambios por campo. Jira Cloud y DefectDojo admiten intercambios explícitos con registros existentes en servidores HTTPS públicos; el estado externo no sustituye al retest. La revisión editorial con Ollama utiliza fuentes seleccionadas y conserva el juicio del autor.

[Recorrido práctico y límites de 0.42](docs/senior-workflow.es.md) · [Caso ficticio Aster ES/EN/PT](qa/aster/README.md) · [Extensión Burp](integrations/burp-report-gen/README.md). La aceptación nativa de Word y Burp, las cuentas vivas de Jira/DefectDojo y la inferencia Ollama requieren sus propios registros; esta lista de capacidades no acredita esas ejecuciones.

## Integración 0.41.0

**Entregar** reúne revisión, destinatario, vista previa y exportación. Los bloqueos tienen acceso a su origen; cambiar contenido u opciones invalida la vista previa. La exportación conserva la revisión comprobada y exige confirmar de nuevo los avisos cuando corresponde.

Las tablas extensas dentro de hallazgos pueden continuar por filas entre páginas, repitiendo su cabecera. Las tablas breves se conservan juntas. Una celda o un encabezado que exceda la altura útil sigue rechazándose con un diagnóstico; no se recorta contenido para forzar la salida.

Los borradores recuperables se amplían a edición masiva y formularios auxiliares de bibliotecas, importación, anotaciones y creación. Recuperar abre el formulario para revisarlo; nunca ejecuta cambios ni restaura aprobaciones. Los formularios del espacio de trabajo se distinguen de los de cada informe. Se mantienen los límites y los 30 días de retención del navegador.

La revisión visual permite **Guardar progreso en el proyecto**: página actual, notas y pendientes, vinculados al SHA-256 del PDF y a la revisión de origen. Guardar una copia privada del PDF es opcional. Sin ella debes volver a abrir el mismo archivo. Estas revisiones no se publican en los informes; sí viajan en respaldos e historial. Eliminar la revisión actual no elimina versiones anteriores.

Abre el asistente con `python scripts/install.py --gui --lang es`. Requiere Python 3.11 o posterior, Tkinter y una sesión gráfica. El asistente guía diagnóstico, carpetas, instalación y recuperación. Las actualizaciones se preparan en una carpeta nueva; el bloqueo de aplicación y datos impide ejecutarlas con el editor abierto. Se conservan Python y los requisitos del sistema: el asistente no es un instalador autónomo que incluya todas las dependencias.

La comprobación nativa de Microsoft Word continúa separada. El corpus incluye español, inglés y portugués; `--additional-projects RUTA` incorpora los tres proyectos complejos situados en `es/`, `en/` y `pt/`. Requiere Windows con Word de escritorio instalado y licenciado. Preparar el kit, validar DOCX o renderizar con LibreOffice no equivale a ejecutar Word.

## Novedades de 0.40.0

La barra izquierda mantiene cinco grupos de herramientas. Las listas de secciones y hallazgos se abren en un **Índice** junto al editor, con búsqueda, filtros de hallazgos y páginas de 50 entradas. Puedes cerrar el panel o ajustar su ancho sin cambiar el informe. Si un filtro oculta la ficha abierta, **Mostrar selección** permite localizarla de nuevo.

**Ordenar secciones** activa los controles para moverlas de forma explícita. La lista normal conserva el orden del proyecto. En móvil, el índice se cierra al elegir una entrada; **Escape** devuelve el foco a su botón. Las preferencias del índice se conservan en este navegador por espacio de trabajo y proyecto. [Uso del índice y navegación](docs/guide.es.md#navegación-lateral-en-0400).

## Novedades de 0.39.0

*Historial de 0.39.0: la organización de cinco grupos se conserva; sus listas desplegables dentro de la barra fueron sustituidas por el índice contextual en 0.40.0.*

La barra izquierda organiza el trabajo en cinco grupos: **Proyecto**, **Contenido**, **Evidencia y alcance**, **Análisis y seguimiento** y **Entrega**. Las filas mantienen un tamaño y espaciado coherentes; los índices desplegables de secciones y hallazgos muestran sus cantidades y conservan la paginación de proyectos extensos.

Al navegar a un elemento, se abre su grupo y se muestra la selección. Ese ajuste de visibilidad de la barra conserva el foco y no desplaza el editor. Puedes plegar el grupo actual: los refrescos de fondo respetan esa decisión. **Entrega → Herramientas** reúne bibliotecas, respaldo integral, privacidad, diagnóstico y actualización. En móvil, **Navegación** abre la barra y **Escape** la cierra devolviendo el foco al botón.

El nuevo caso ficticio **Atlas Servicios Financieros** prepara una prueba amplia con contenido redactado en español, inglés y portugués de Brasil. Su [protocolo de aceptación](docs/QA-ATLAS-0390.md) distingue informes completos, muestras de estilos, recorridos API y comprobaciones visuales; los resultados se acreditan por ejecución, sin dar por aprobadas salidas todavía pendientes. [Recorrido de la barra lateral](docs/guide.es.md#navegación-lateral-en-0390).

## Novedades de 0.38.0

**Errores con ubicación:** las importaciones muestran el registro, campo y línea disponibles; las exportaciones fallidas identifican el hallazgo, tabla, fila, celda o evidencia cuando el contrato puede localizarlos con certeza. Si no puede, conserva el error general. Estos detalles privados no se copian a los manifiestos de entrega.

**Vista DOCX con LibreOffice:** desde una exportación finalizada que incluya Word, genera explícitamente una vista PDF con LibreOffice instalado en tu equipo. La vista se vincula al DOCX exacto por SHA-256 y revisión, sin modificarlo. Es temporal y privada; muestra la composición de LibreOffice, sin acreditar equivalencia con Microsoft Word.

**Inspección de anexos PDF:** analiza texto extraíble, metadatos y estructuras del PDF con límites explícitos. Señala categorías y ubicaciones, sin mostrar valores sensibles ni modificar el archivo. El alcance siempre es parcial: no incluye OCR, binarios arbitrarios ni reconstrucción de versiones anteriores del PDF. La autorización manual del anexo sigue siendo necesaria.

La limpieza retira helpers privados, bindings sin uso, constantes obsoletas y 20 reglas CSS sin emisores actuales. Se conservan adaptadores públicos, callbacks de bibliotecas y recursos con funciones documentadas. No se afirma ausencia universal de código muerto. [Uso y límites de las funciones nuevas](docs/guide.es.md#revisar-errores-y-documentos-en-0380).

## Correcciones de 0.37.1

Las imágenes enlazadas dentro de tablas Markdown conservan sus destinos y leyendas al exportar a Word, también con fragmentos de URL y texto alrededor. La verificación de enlaces permanece activa. El caso ficticio Banco Horizonte Austral amplía la aceptación de contenidos y flujos; consulta su matriz de cobertura en `qa/horizonte/`.

## Novedades de 0.37.0

**Emparejar páginas PDF:** relaciona manualmente las páginas anteriores y posteriores cuando hay inserciones o cambios de orden. La vista muestra las correspondencias y las páginas sin equivalente; cada página debe quedar cubierta exactamente una vez.

**Registrar la revisión:** guarda opcionalmente autor autodeclarado, decisión, nota, correspondencias y hashes como un registro JSON privado del proyecto. Solo se guarda al solicitarlo y queda excluido de la entrega por defecto. Permanece en su historial y respaldos, sin borrado automático. Los PDF, el HTML y las imágenes no se copian al registro; descarga el HTML aparte para conservar las imágenes de la comparación.

**SARIF con extensiones:** se admiten reglas de componentes `tool.extensions` autocontenidos, con referencias coherentes por índice o GUID. El origen de cada componente se conserva y las observaciones siguen informativas, sin verificar.

## Funciones incorporadas en 0.36.0

**SARIF 2.1.0:** importa resultados desde **Importar resultados**, revisa su origen y selecciona qué incorporar. Se conservan como observaciones informativas sin verificar; el nivel del analizador no se convierte en CVSS.

**Comparar PDF:** selecciona dos archivos desde el historial para ver sus páginas y las diferencias resaltadas. Descarga la comparación como HTML autónomo. La comparación predeterminada es por posición de página; un cambio visual no demuestra por sí solo un cambio de significado.

## Novedades de 0.35.0

Portugués de Brasil se suma a español e inglés en el editor, los mensajes del servidor, el tutorial, la galería y los cuatro formatos de informe. El selector permite elegir el idioma de la interfaz de forma explícita; el idioma del informe continúa separado y cambiar cualquiera de ellos conserva el contenido redactado.

Los títulos de las secciones se actualizan inmediatamente al cambiar el idioma del informe. Markdown conserva también la introducción del apéndice en informes por secciones. Las comprobaciones incluyen catálogos y marcadores de traducción, exportaciones en portugués y recorridos del tutorial en los tres idiomas.

### Correcciones conservadas de 0.34.5

El índice Word reserva espacio para el número de página cuando el título ocupa casi toda la línea. Las leyendas largas pueden continuar por páginas sin hacer desaparecer la figura; HTML, PDF y Markdown conservan sus saltos de línea. Markdown admite también leyendas vacías sin mostrar asteriscos. Las tablas de retest anidadas en citas o listas aprovechan el espacio disponible, y los retests sin fecha ya no muestran un separador vacío.

La revisión señala el campo que contiene una entidad Markdown incompatible con Word antes de exportar. El código escrito literalmente se conserva. Los textos automáticos siguen describiendo lo registrado sin afirmar verificaciones que no constan.

El seguimiento de exportaciones pausa sus consultas al salir de la página y las reanuda al restaurarla, sin cancelar los trabajos del servidor. Las etiquetas del inspector, la vista previa y la validación respetan el idioma de la interfaz después de recargar; cambiar ese idioma no modifica el informe. Los selectores nativos siguen el tema oscuro o claro del editor, corrigiendo el contraste insuficiente observado en WebKit para Linux.

El [complemento opcional para LibreOffice](docs/guide.es.md#complemento-opcional-para-libreoffice) ajusta el salto de literales técnicos ASCII marcados, sin insertar caracteres ni cambiar enlaces. **La instalación y el ajuste se comprobaron con la distribución oficial de LibreOffice 26.2.6.3 para Linux x86-64 y su Python UNO.** El exportador DOCX añade por defecto la marca de idioma técnico; el complemento se construye desde las fuentes y se instala expresamente. El documento sigue siendo editable sin él, aunque pueden reaparecer los saltos anticipados. No acredita Microsoft Word ni LibreOffice para Windows o macOS.

## Exportación y tutorial visual

La alineación izquierda, centrada o derecha de las tablas Markdown se conserva al exportar. El verificador PDF comprueba el contenido de cada hallazgo dentro de su región, para que una copia en el índice o el resumen no oculte texto ausente. Las URLs largas escritas como texto común ya no desbordan el PDF; su verificación evita búsquedas ambiguas innecesarias. En Linux y macOS, un supervisor mantiene reservado el grupo del trabajo hasta detener sus procesos, incluso si el trabajador termina antes. La publicación exige también las comprobaciones de macOS, LibreOffice estable y WebKit, junto con un recorrido del proyecto y tutorial ES/EN/PT en Safari nativo de escritorio. Este recorrido automatizado tiene un alcance concreto; no sustituye una revisión en Microsoft Word ni una evaluación humana con lector de pantalla.

**Tutorial visual** acompaña el primer acceso con una invitación opcional y queda disponible en el menú. Sus seis pasos incluyen capturas reales en español, inglés y portugués: plantilla, datos del informe, hallazgos, evidencias, revisión y entrega con respaldo. Puedes ampliar las capturas, continuar donde quedaste o reiniciar el recorrido sin cambiar tus proyectos. Funciona localmente y también cuando el navegador no permite guardar el progreso.

La exportación PDF reduce el trabajo de composición de URLs literales extensas. Conserva su texto seleccionable y sus destinos completos, con un presupuesto predeterminado de 300 segundos, configurable entre 30 y 600, y sin retirar las comprobaciones del informe. Las pruebas incluyen tablas con 72 URLs de más de 300 caracteres, ambos idiomas y los seis diseños generales. También se corrige el falso rechazo de un párrafo cuando una URL completa continúa entre páginas.

El kit opcional de aceptación en Microsoft Word admite los campos de numeración generados por report-gen y distingue los fragmentos de URLs externas de los marcadores del documento. Añade un caso explícito de URLs largas y numeración excepcional para la revisión nativa.

**Límites:** sin el complemento, algunas URL de Word pueden saltar antes de llenar la línea en LibreOffice; no se altera su texto para ocultarlo. La integración comprobada se limita al entorno y los literales descritos en la guía. La revisión en Microsoft Word nativo permanece pendiente. El verificador PDF no acredita ordinales ni maquetación; ambas requieren revisión visual. [Cambios completos](CHANGELOG.md) · [Guía de entrega](docs/guide.es.md#qué-comprueba-cada-entrega).

## Qué comprueba cada entrega

**Ver comprobaciones** muestra revisión, SHA-256, tamaño y controles por archivo. Las exportaciones comparan contenido y referencias con alcances distintos según el formato. **Estas comprobaciones no certifican la validez del pentest ni la presentación visual:** revisa PDF, Word, Markdown y HTML antes de entregar.

[Contratos de exportación, anexos y límites](docs/guide.es.md#qué-comprueba-cada-entrega). La [firma Ed25519 opcional](docs/delivery-signing.md) acredita integridad respecto de una clave pública fijada; no cifra la entrega ni certifica sus conclusiones.

<a id="por-qué-está-construido-así"></a>
<a id="modelo-de-uso-y-límites"></a>

## Datos y recuperación

El editor trabaja en **`127.0.0.1` y un solo proceso**, sin cuentas ni servicios externos para la edición normal. Después de instalar sus dependencias, el trabajo habitual es local. La asistencia con Ollama es **opcional y explícita**; consulta qué campos envía y sus límites antes de activarla.

La carpeta externa contiene `projects/` y `library/`. El arranque tradicional sin `--workspace` ni `REPORT_GEN_WORKSPACE` conserva `webapp/projects/` y `webapp/library/`. **Respaldo integral** conserva proyectos, originales e historial; es material privado. Los proyectos en disco y borradores del navegador no están cifrados por la aplicación. El respaldo descargado puede cifrarse con contraseña instalando la opción `privacy`; no cifra la instalación ni sustituye conservar la contraseña. [Recuperación, copias y privacidad](docs/guide.es.md#datos-y-recuperación).

Los borradores del navegador se separan por espacio de trabajo, perfil, host y puerto. Actualizar la aplicación manteniendo la misma carpeta externa conserva esa separación; moverlo o restaurar en otro espacio crea un ámbito distinto. Descarga los borradores pendientes antes de trasladarlo: no viajan en el respaldo integral. Las copias antiguas sin identidad se conservan en **Más → Copias anteriores sin asignación** para revisarlas y descargarlas expresamente.

El HTML portátil contiene el informe completo: sus filtros no son permisos de acceso. Los detectores de posibles secretos no sustituyen la revisión humana. Las pruebas de compatibilidad de Windows no sustituyen la revisión en Microsoft Word de escritorio; Word y LibreOffice pueden paginar de forma distinta. Los perfiles de certificación no implican afiliación ni garantizan cumplir las reglas de un examen.

<a id="actualizar-sin-perder-proyectos"></a>

## Actualizar desde una versión anterior

**Actualizar report-gen** permite consultar una nueva versión, revisar su paquete y preparar un respaldo privado sin cifrar. La preparación no sustituye la instalación en ejecución: descarga las instrucciones privadas, detén el editor y sigue los comandos indicados. [Flujo asistido y límites](docs/guide.es.md#actualización-asistida).

Si ya usas una carpeta externa, detén el editor, descarga **0.44.0 en una carpeta nueva** y ejecuta allí `python3 scripts/install.py --desktop --workspace /ruta/datos-existentes`. Conserva los datos y actualiza el acceso; abre una sola instalación a la vez. No copies la `.venv` antigua.

Para trasladar proyectos de una instalación que todavía usa `webapp/`, ejecuta desde la nueva:

```bash
python3 start.py --ready --workspace /ruta/datos-nuevos --upgrade-from /ruta/report-gen-anterior
```

El destino debe estar vacío. Se conserva el origen y se genera un respaldo privado. Para separar los datos de la propia carpeta actual, usa `--upgrade-from .` con un destino externo vacío. Comprueba proyectos, imágenes e historial antes de retirar cualquier instalación. También puedes usar **Respaldo integral**. [Detalles y compatibilidad](docs/guide.es.md#actualizar-desde-una-versión-anterior).

<a id="cli--uso-avanzado"></a>

## Exportar por terminal

Prueba un ejemplo ficticio incluido, desde la raíz del proyecto:

```bash
.venv/bin/python export.py examples/pending-severity/engagement.yaml -f html -o out/ejemplo.html
```

Los valores de `-f` son `pdf`, `docx`, `md` y `html`; `md` produce un ZIP. [Más sobre CLI, Word e imágenes](docs/guide.es.md#exportar-por-terminal).

<a id="pruebas-de-desarrollo"></a>

## Desarrollo y límites

Para desarrollo y pruebas de interfaz se necesita **Node.js 22+**. Desde un entorno ya instalado:

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci
.venv/bin/python -m pytest
npm test
```

[Pruebas de navegador y escenarios opcionales](docs/guide.es.md#desarrollo-y-límites) · [Contribuir](CONTRIBUTING.md) · [Seguridad](SECURITY.md) · [Licencia MIT](LICENSE).

## Documentación

- [Guía de uso: instalación, publicación, respaldo, CLI y desarrollo](docs/guide.es.md).
- [Evidencia y decisiones; vistas previas y Ollama opcionales](docs/evidence-decisions-0230.md).
- [CVSS 4.0](docs/CVSS40.md) y [firma de entregas](docs/delivery-signing.md).
- [Biblioteca de diseños y plantillas](docs/design-library.md).
- [Registro de cambios](CHANGELOG.md).

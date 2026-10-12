<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen, con Prometeo y Evaristo" width="300">
</p>

<a id="report-gen"></a>

# report-gen 0.34.1

<a id="qué-es"></a>

**Un editor local para convertir tus evaluaciones de seguridad en informes claros.** Organiza hallazgos, conecta evidencias, registra remediación y retest, y prepara **PDF, Word, Markdown con imágenes y HTML portátil** desde una revisión guardada.

[English](README.en.md) · [Guía completa](docs/guide.es.md) · [Cambios](CHANGELOG.md) · [Seguridad](SECURITY.md)

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

**Tutorial visual** está disponible desde el menú, con capturas ES/EN ampliables y progreso local. La invitación inicial se puede omitir.

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

## Novedades de 0.34.1

La revisión del PDF distingue apariciones repetidas o solapadas de encabezados y acepta títulos completos que se envuelven entre líneas. El tutorial devuelve el foco al botón que abrió la galería al cancelarla o cerrarla, en ambos idiomas. Las guías ya reflejan la corrección de rendimiento de las URLs aplicada en 0.34.0.

**Tutorial visual** acompaña el primer acceso con una invitación opcional y queda disponible en el menú. Sus seis pasos incluyen capturas reales en español e inglés: plantilla, datos del informe, hallazgos, evidencias, revisión y entrega con respaldo. Puedes ampliar las capturas, continuar donde quedaste o reiniciar el recorrido sin cambiar tus proyectos. Funciona localmente y también cuando el navegador no permite guardar el progreso.

La exportación PDF reduce el trabajo de composición de URLs literales extensas. Conserva su texto seleccionable y sus destinos completos, sin aumentar el límite de 120 segundos ni retirar las comprobaciones del informe. Las pruebas incluyen tablas con 72 URLs de más de 300 caracteres, ambos idiomas y los seis diseños generales. También se corrige el falso rechazo de un párrafo cuando una URL completa continúa entre páginas.

El kit opcional de aceptación en Microsoft Word admite los campos de numeración generados por report-gen y distingue los fragmentos de URLs externas de los marcadores del documento. Añade un caso explícito de URLs largas y numeración excepcional para la revisión nativa.

**Límites:** algunas URL de Word siguen saltando antes de llenar la línea en LibreOffice; no se altera su texto para ocultarlo. La revisión en Microsoft Word nativo permanece pendiente. El verificador PDF no acredita ordinales ni maquetación; ambas requieren revisión visual. [Cambios completos](CHANGELOG.md) · [Guía de entrega](docs/guide.es.md#qué-comprueba-cada-entrega).

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

Si ya usas una carpeta externa, detén el editor, descarga **0.34.1 en una carpeta nueva** y ejecuta allí `python3 scripts/install.py --desktop --workspace /ruta/datos-existentes`. Conserva los datos y actualiza el acceso; abre una sola instalación a la vez. No copies la `.venv` antigua.

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

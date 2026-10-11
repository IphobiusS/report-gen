<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen, con Prometeo y Evaristo" width="300">
</p>

<a id="report-gen"></a>

# report-gen 0.31.2

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

[Recorrido completo y recomendaciones](docs/guide.es.md#primer-informe).

<a id="características"></a>

## Qué puedes hacer

- **Documentar una evaluación:** alcance, metodología, activos, cobertura, hallazgos y pasos reproducibles; CVSS 3.1 y 4.0 cuando corresponda.
- **Trabajar con evidencia:** galería, pies de imagen, vínculos a hallazgos, copias censuradas e inspección de lo que se publicará.
- **Conservar el seguimiento:** identidades estables, revisiones recuperables, comparación con una entrega marcada, correcciones y matriz de retest.
- **Elegir la presentación:** empezar con Serio, comparar los seis diseños generales y abrir el catálogo especializado cuando lo necesites. El idioma del informe es independiente del de la interfaz.
- **Separar destinatarios:** entregas técnica, ejecutiva y pública con planes de inclusión explícitos; la pública requiere texto aprobado y consentimiento registrado.
- **Relacionar evidencia y decisiones:** afirmaciones, límites, contexto de negocio, observaciones y revisión visual del PDF. [Flujo y requisitos opcionales](docs/evidence-decisions-0230.md).

| Formato | Archivo que recibes |
| --- | --- |
| PDF | Informe paginado `.pdf`. |
| Word | Documento editable `.docx`, con campos propios para el índice. |
| Markdown | ZIP con `report.md` y sus imágenes. |
| HTML portátil | Un `.html` autónomo con filtros de lectura. |

## Correcciones de 0.31.2

La segunda auditoría corrige carreras al recuperar borradores y previsualizar Markdown, rechaza enlaces simbólicos que cambian la identidad de un proyecto y limita recursos de respaldo antes de cargarlos en memoria. La recuperación contempla interrupciones durante la preparación de guardados, restauraciones e importaciones. También mejora la comprobación de encabezados y citas en las exportaciones, rechaza etapas de historial malformadas y elimina funciones sin uso. El control de CI verifica las identidades de las pruebas ejecutadas, además del total. [Detalle de las correcciones](CHANGELOG.md).

## Novedades de 0.31.0

- **Rutina de respaldo opcional:** elige una carpeta externa, frecuencia y copias que conservar. Mientras el servidor esté abierto, prepara respaldos privados sin cifrar y comprueba su restauración antes de rotar las copias propias. La pantalla muestra el último resultado y permite comprobar una copia manualmente. Los borradores del navegador no se incluyen.
- **Vectores CVSS 3.1 sin correcciones silenciosas:** pegar un vector incompleto, duplicado o inválido muestra un error y conserva el hallazgo anterior. Los vectores válidos mantienen el mismo cálculo.
- **Editor más mantenible:** transporte, cálculo CVSS y vista previa tienen módulos propios; el proyecto conserva un único estado guardado. Una pestaña bloqueada por cambio de carpeta ya no reanuda una escritura al terminar de preparar la sesión.
- **Pruebas de escala reproducibles:** corpus sintéticos con cientos de hallazgos e imágenes distintas, medidas de interfaz y exportación en los cuatro formatos. Los resultados identifican entorno y tamaño; no prometen tiempos universales.
- **Revisión más ligera:** la comprobación de posibles secretos en texto valida las imágenes sin recomprimirlas. El inspector completo y las exportaciones mantienen su limpieza y comprobaciones.
- **Materiales externos comprobados:** los cuatro DOCX del kit pasan la inspección estructural automatizada antes de entregarse a revisión. Word nativo y las cinco sesiones con participantes siguen pendientes.

Se mantienen la edición por lotes, las entregas por responsable, el instalador y la actualización asistida. [Cambios completos](CHANGELOG.md).

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

Si ya usas una carpeta externa, detén el editor, descarga **0.31.2 en una carpeta nueva** y ejecuta allí `python3 scripts/install.py --desktop --workspace /ruta/datos-existentes`. Conserva los datos y actualiza el acceso; abre una sola instalación a la vez. No copies la `.venv` antigua.

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

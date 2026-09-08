<div align="center">

<img src="docs/img/report-gen-logo.png" alt="report-gen" width="360">

# report-gen

**Toolkit local-first para informes de pentesting · v0.13.0.**

Engagements estructurados · PDF / DOCX / Markdown · CVSS 3.1 y 4.0 · Editor visual · Informes reproducibles

</div>

<div align="center">

<img src="docs/img/report-gen-ui.png" alt="Editor de report-gen" width="900">

</div>

---

## Qué es

`report-gen` convierte un engagement de pentest en un informe profesional sin
depender de servicios externos. Cada trabajo es un `engagement.yaml`; el motor
produce el informe completo (portada, secciones, tabla de contenidos, resumen de
hallazgos con gráfico de severidades, hallazgos con CVSS y CWE, máquinas estilo
CTF/OSCP y apéndice de evidencias) en **PDF, DOCX y Markdown** desde una única
fuente. Todo corre en tu máquina, sin marcas de agua y con diseño propio.

## Características

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

python -m pip install -e .
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

La versión 0.13.0 se ha verificado en Linux con WeasyPrint. Windows y la
alternativa Chromium requieren una prueba en tu entorno; no se han verificado
en esta entrega. El DOCX se genera directamente con `python-docx`.

## Actualizar sin perder proyectos

1. Cierra el servidor antiguo y conserva una copia de su carpeta completa.
2. Descomprime esta versión en una carpeta nueva.
3. Copia `webapp/projects/` de tu instalación anterior al mismo lugar en la nueva.
   Si tienes informes propios en `reports/`, copia también esas carpetas y sus imágenes.
4. Instala las dependencias con `python -m pip install -e .` y arranca el editor.
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
    cvss/                v31, v40 (+ lookup/constants), dispatch por version
    validate.py          validación de estructura, campos y coherencia CVSS
    sections.py          catalogo canonico de secciones
    designs/             report_sections.yaml (catalogo)
    templates/ themes/   Jinja2 + CSS (temas serio / corporativo)
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

Consulta `VERIFICACION-0.13.0.md` para los resultados y límites de esta entrega.

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

Herramienta local y monousuario: se sirve en `127.0.0.1` con `debug=False`.
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

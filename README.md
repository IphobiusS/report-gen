<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen, con Prometeo y Evaristo" width="300">
</p>

<a id="report-gen"></a>

# report-gen 0.25.0

<a id="qué-es"></a>

**Un editor local para convertir tus evaluaciones de seguridad en informes claros.** Organiza hallazgos, conecta evidencias, registra remediación y retest, y prepara **PDF, Word, Markdown con imágenes y HTML portátil** desde una revisión guardada.

[English](README.en.md) · [Guía completa](docs/guide.es.md) · [Validación de 0.25.0](VALIDACION-0.25.0.md) · [Seguridad](SECURITY.md)

<a id="inicio-rápido"></a>

## Instalar y abrir

Ruta principal: **Linux/Kali y Python 3.10+**. La validación de esta entrega documenta Linux con Python 3.12; consulta allí el alcance de las pruebas.

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 start.py --setup
python3 start.py --diagnose
python3 start.py
```

Abre **http://127.0.0.1:8080** en tu navegador. `Ctrl+C` detiene el servidor; `--port 8081` permite elegir otro puerto local.

`--setup` crea `.venv` e instala las dependencias con las restricciones de `requirements-audited.txt`; necesita conexión a Internet. Revisa el resultado de cada motor en el diagnóstico. Para bibliotecas nativas de PDF o el motor Chromium opcional, consulta [la instalación detallada](docs/guide.es.md#instalar-y-abrir). **Node.js no es necesario para usar el editor.**

<a id="demo"></a>

## Primer informe

1. En **Inicio**, elige **Probar demo Nimbus**: crea una copia editable de un caso ficticio con 12 hallazgos. Para tu propio trabajo, usa **Crear proyecto**.
2. Abre **Guía: primer informe**. Sus seis pasos recorren alcance, hallazgos, evidencias, revisión y entrega sin completar ni validar datos por ti.
3. Guarda, revisa el **Inspector de publicación** y genera los formatos que necesites desde **Entregar**. Abre los archivos antes de compartirlos y conserva un respaldo privado del proyecto.

[Recorrido completo y recomendaciones](docs/guide.es.md#primer-informe).

<a id="características"></a>

## Qué puedes hacer

- **Documentar una evaluación:** alcance, metodología, activos, cobertura, hallazgos y pasos reproducibles; CVSS 3.1 y 4.0 cuando corresponda.
- **Trabajar con evidencia:** galería, pies de imagen, vínculos a hallazgos, copias censuradas e inspección de lo que se publicará.
- **Conservar el seguimiento:** identidades estables, revisiones recuperables, comparación con una entrega marcada, correcciones y matriz de retest.
- **Elegir la presentación:** diseños y perfiles de certificación, plantillas personales e informes en español o inglés. El idioma del informe es independiente del de la interfaz.
- **Separar destinatarios:** entregas técnica, ejecutiva y pública con planes de inclusión explícitos; la pública requiere texto aprobado y consentimiento registrado.
- **Relacionar evidencia y decisiones:** afirmaciones, límites, contexto de negocio, observaciones y revisión visual del PDF. [Flujo y requisitos opcionales](docs/evidence-decisions-0230.md).

| Formato | Archivo que recibes |
| --- | --- |
| PDF | Informe paginado `.pdf`. |
| Word | Documento editable `.docx`, con campos propios para el índice. |
| Markdown | ZIP con `report.md` y sus imágenes. |
| HTML portátil | Un `.html` autónomo con filtros de lectura. |

## Novedades de 0.25.0

La matriz de retest mantiene juntas las etiquetas y sus cifras; la preparación de entrega muestra estados y accesos para resolver pendientes. La vista previa se ajusta al ancho disponible y admite zoom manual. El recorrido documentado del PDF agrupa los pasos por fase y conserva su alternativa textual completa.

También se mejora la lectura YAML con libyaml y una ruta de compatibilidad acotada, y se añade la consulta de huella de claves públicas para la firma opcional. [Cambios completos](CHANGELOG.md) · [Pruebas, medidas y límites](VALIDACION-0.25.0.md).

## Qué comprueba cada entrega

**Ver comprobaciones** muestra revisión, SHA-256, tamaño y controles por archivo. Las exportaciones comparan contenido y referencias con alcances distintos según el formato. **Estas comprobaciones no certifican la validez del pentest ni la presentación visual:** revisa PDF, Word, Markdown y HTML antes de entregar.

[Contratos de exportación, anexos y límites](docs/guide.es.md#qué-comprueba-cada-entrega). La [firma Ed25519 opcional](docs/delivery-signing.md) acredita integridad respecto de una clave pública fijada; no cifra la entrega ni certifica sus conclusiones.

<a id="por-qué-está-construido-así"></a>
<a id="modelo-de-uso-y-límites"></a>

## Datos y recuperación

El editor trabaja en **`127.0.0.1` y un solo proceso**, sin cuentas ni servicios externos para la edición normal. Después de instalar sus dependencias, el trabajo habitual es local. La asistencia con Ollama es **opcional y explícita**; consulta qué campos envía y sus límites antes de activarla.

Los proyectos están en `webapp/projects/` y las bibliotecas personales en `webapp/library/`. **Respaldo integral** conserva proyectos, originales e historial; es material privado. Los datos y borradores no están cifrados por la aplicación. [Recuperación, copias y privacidad](docs/guide.es.md#datos-y-recuperación).

El HTML portátil contiene el informe completo: sus filtros no son permisos de acceso. Los detectores de posibles secretos no sustituyen la revisión humana. Windows nativo y Microsoft Word de escritorio requieren validación específica; Word y LibreOffice pueden paginar de forma distinta. Los perfiles de certificación no implican afiliación ni garantizan cumplir las reglas de un examen.

<a id="actualizar-sin-perder-proyectos"></a>

## Actualizar desde una versión anterior

Instala **0.25.0 en una carpeta nueva**. Crea un respaldo integral con la versión anterior, restáuralo en la instalación nueva vacía y comprueba tus proyectos antes de retirar la anterior. No copies su `.venv` ni sustituyas datos por la demo.

[Compatibilidad de respaldos y recuperación de proyectos antiguos](docs/guide.es.md#actualizar-desde-una-versión-anterior).

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
- [Registro de cambios](CHANGELOG.md) y [validación de 0.25.0](VALIDACION-0.25.0.md).

## Historial conservado

<details>
<summary>Notas anteriores y enlaces de la bienvenida previa</summary>

Las instrucciones vigentes están en la guía de arriba. Estos documentos conservan el contexto de versiones anteriores.

<a id="novedades-de-0240"></a><a id="novedades-de-0234"></a><a id="novedades-de-0233"></a><a id="novedades-de-0232"></a><a id="novedades-de-0231"></a><a id="novedades-de-0230"></a><a id="novedades-de-0221"></a><a id="novedades-de-0220"></a>

- [Notas detalladas que acompañaban a 0.25.0](docs/history/README-0.25.0-original.md).

<a id="nuevas-funciones-de-0130"></a><a id="corrección-de-cvss"></a><a id="arquitectura"></a><a id="paginación-de-hallazgos"></a><a id="markdown-e-imágenes"></a><a id="api-local"></a><a id="inspiración"></a><a id="licencia"></a>

- [Bienvenida histórica de GitHub 0.13.0](docs/history/README-github-0.13.0.md).
- [README anterior de 0.18](docs/history/README-0.18.md).

</details>

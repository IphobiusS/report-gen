# Changelog

Formato basado en Keep a Changelog. Versionado semantico aproximado.

## [Unreleased]

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

> **Nota histórica.** Auditoría realizada durante el desarrollo (anterior a la
> implementación de CVSS 4.0 / v0.9). Se conserva como historial de desarrollo; sus
> hallazgos y referencias de arquitectura pueden no reflejar el estado actual del
> proyecto. Para el estado vigente, ver `README.md`, `CHANGELOG.md` y la suite de
> tests.

# Auditoría de report-gen

Fecha: 2026-08-31. Alcance: motor (engine.py), export (export.py), app web
(webapp/), asistente (wizard.py), temas, paquetes de idioma y esquemas.
Metodología: compilación estática, pruebas de casos límite y pruebas de seguridad
sobre la app en localhost (path traversal, inyección de tema, subida de archivos).

## Corregido en esta auditoría

- **[Alta] Caída del servidor por tema inválido.** `engine.render_html` hacía
  `sys.exit` si el tema no existía; usado como librería en el endpoint de preview,
  eso cerraba el hilo de la petición ("connection closed without response"). Ahora
  lanza `ValueError` y el endpoint lo captura. Verificado: preview con tema basura
  responde 200 sin caerse.
- **[Media] Inyección de ruta vía `meta.theme`.** Un `theme` arbitrario
  (`../../etc/passwd`) llegaba al render y filtraba la ruta interna. Se añadió
  saneo en el backend (`sanitize_meta`) que fija `theme` a la lista permitida y
  `lang` a `es|en` en guardar, render, export y preview. Verificado: queda
  `theme: serio`, `lang: es` en disco.
- **[Media] Subida de imagen con nombre malicioso.** El nombre `..` provocaba un
  500 (se intentaba escribir sobre un directorio). Ahora se usa
  `secure_filename` con nombre de respaldo generado. `../../x.png` se neutraliza a
  `x.png`; `..` pasa a `img_<hash>.png`.
- **[Media] Word discrepaba del PDF** (reportado por el usuario, corregido antes de
  esta auditoría y verificado aquí): el DOCX se reescribió en python-docx puro
  leyendo los colores del tema, con portada fiel (regla de cabecera, caja del tag,
  reglas de acento, tabla de metadatos), cabecera/pie con número de página, cajas
  de finding, chips de severidad, bloques de código, gráfico e imágenes. No
  depende de LibreOffice.

## Verificado correcto

- Path traversal en `/theme/<...>`, `/api/projects/<slug>/img/<...>` y en `<slug>`:
  bloqueado (404) por `send_from_directory`/`slugify`.
- Escapado de HTML en campos de texto (títulos, etc.): `<script>` se renderiza
  como texto escapado, sin inyección en el PDF.
- Casos límite del motor y del export: engagement vacío, findings sin campos,
  `mode` ausente, unicode/acentos: renderizan y exportan sin romperse.
- Numeración de páginas a dos pasadas: estable (marcadores en posición absoluta,
  sin desplazar la maquetación entre pasadas).
- CVSS 3.1: contrastado contra vectores conocidos (9.8, 9.9, 6.1, 2.9, 0.0).
- OWASP Top 10:2025 (web) y OWASP LLM Top 10 2025: contrastados con la fuente
  oficial.

## Riesgos aceptados (bajos, propios de una herramienta local monousuario)

- **Self-XSS en el preview en vivo.** El Markdown de la prosa deja pasar HTML
  crudo; si escribes `<script>` en una descripción, se ejecutaría en el preview
  (tu propio navegador, mismo origen localhost). Impacto mínimo en uso local. Para
  un futuro multiusuario: sanear el HTML (p. ej. bleach) antes de servir el preview.
- **Sin autenticación ni control de concurrencia.** Es monousuario por diseño; el
  autoguardado y un render simultáneo podrían competir por `engagement.yaml`.
  Entra en el trabajo de "versionado/multiusuario".

## Decisión de diseño: secciones no excluyentes

Los módulos de `designs/sections_library.yaml` no son mutuamente excluyentes: se
pueden combinar los que el informe necesite. Se agrupan por `group` solo para
ordenarlos en la UI. Los nombres se aclararon en español indicando su origen
(OSCP+/CAPE) para que módulos de rol parecido no se confundan (p. ej. "Resumen de
alto nivel (OSCP+)" vs "Resumen ejecutivo (CAPE)", "Hallazgos: por host" vs
"Hallazgos: por vulnerabilidad").

## Idioma

La app y los informes están pensados en español. El idioma del informe se cambia
con un clic (botón ES/EN en la barra superior) y el preview se actualiza al
instante; internamente fija `meta.lang` a `es|en`.

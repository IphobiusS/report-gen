> **Nota histórica.** Auditoría realizada durante el desarrollo (anterior a la
> implementación de CVSS 4.0 / v0.9). Se conserva como historial de desarrollo; sus
> hallazgos y referencias de arquitectura pueden no reflejar el estado actual del
> proyecto. Para el estado vigente, ver `README.md`, `CHANGELOG.md` y la suite de
> tests.

# Auditoría en profundidad y prueba de estrés

Fecha: 2026-08-31. Enfoque: ¿sirve para redactar un informe comercial exigente?
Método: validación de la calculadora CVSS contra vectores oficiales y paridad
Python/JS, prueba de estrés con un informe grande, y revisión de vacíos con
criterio de pentester senior. Estándares corroborados vía web.

## 1. Calculadora CVSS: correcta

- Implementa CVSS v3.1 Base según la especificación FIRST (Exploitability,
  Impact, Scope, roundup). Validada contra 15 vectores oficiales/CVE conocidos
  (9.8, 10.0, 8.1, 7.8, 7.5, 6.1, 5.9, 2.9, 0.0, 9.9, etc.): 15/15 correctos.
- Paridad total entre el Python (`webapp/cvss.py`) y el puerto JS del navegador
  (`app.js`): se compararon las 2592 combinaciones posibles de métricas Base y
  hubo 0 diferencias. El score que ves en la calculadora nunca diferirá del que
  va al informe.
- La severidad se sincroniza automáticamente con el score al usar la calculadora,
  evitando la inconsistencia clásica "severidad Alta con CVSS 9.8".

Recomendación: añadir CVSS v4.0. Es el estándar vigente de FIRST desde el
1-nov-2023 (nomenclatura Base/Threat/Environmental/Supplemental, se elimina
Scope, se separan sistema vulnerable y afectado). En la práctica v3.1 sigue
siendo la mayoría de los scores y NVD publica ambos, así que 3.1 es válido hoy,
pero un informe moderno debería poder emitir 4.0. Es un desarrollo mediano
(nueva fórmula y tabla de métricas), no un ajuste.

## 2. Sobre "la lista de CVE actuales"

La herramienta es un generador de informes, no un escáner ni una base de CVE.
Por diseño no incluye un listado de CVE (quedaría obsoleto de inmediato; eso es
trabajo de NVD/escáneres). Lo que sí trae, y está verificado y vigente:

- OWASP Top 10 (web, 2025) y OWASP Top 10 para LLM (2025), como catálogos para
  clasificar hallazgos.
- CWE y referencias como texto libre por hallazgo.
- La calculadora CVSS.

Recomendaciones si quieres datos de CVE/CWE: (a) un campo de referencias CVE con
enlace a NVD por hallazgo; (b) validación del formato CWE contra una lista local
de CWE; (c) opcionalmente, una consulta en vivo a la API de NVD para traer CVSS y
descripción de un CVE. Nada de esto requiere empaquetar "todos los CVE".

## 3. Prueba de estrés: aprobada

Informe comercial grande generado y renderizado: 30 hallazgos (mezcla de
severidades, CVSS reales), markdown largo con bloques de código, imágenes y
tablas, y 13 secciones canónicas activas.

- PDF: 77 páginas, sin errores. Tiempo ~56 s con el motor Chromium de respaldo
  (hace dos pasadas para numerar). Con WeasyPrint instalado el tiempo baja
  mucho; es el backend recomendado para informes grandes.
- DOCX: 0.8 s, 47 KB, con los 30 hallazgos y las 13 secciones en orden.
- Markdown: 0.3 s, 97 KB, estructura correcta.
- Numeración de páginas: verificada hallazgo por hallazgo. Las 30 páginas que
  declara la tabla de resumen coinciden exactamente con la página real de cada
  hallazgo. El resumen va ordenado por severidad (correcto para lectura
  ejecutiva).
- Unicode, acentos, símbolos `<>&` y HTML en títulos: se escapan y renderizan
  sin romper el documento.

Endurecimiento aplicado en esta auditoría: los marcadores de página invisibles
que sostienen la numeración a dos pasadas se movieron a posición absoluta dentro
de un contenedor posicionado (fuera de flujo, anclados al inicio de su
sección/hallazgo). Así la pasada 1 y la 2 tienen paginación idéntica y la
numeración es correcta aun con informes muy largos. (En la prueba la numeración
ya salía correcta; el cambio elimina un riesgo latente en bordes de página.)

## 4. Qué le falta para un informe comercial de primer nivel (mi lectura)

Lo que ya cumple: portada y control del documento, resumen ejecutivo y postura
de riesgo, alcance y metodología, resumen de hallazgos con gráfico, hallazgos
reproducibles con evidencia, narrativa del ataque, plan de remediación y
apéndices; catálogo canónico de secciones con obligatorias; ES/EN a un clic;
PDF/DOCX/MD consistentes.

Vacíos que yo cerraría, por prioridad:

1. Variables de plantilla (`{{ client }}`, `{{ assessor }}`, fechas). Hoy se
   escriben literales. Un informe comercial se reutiliza como plantilla; que se
   rellenen solas evita errores de copiar/pegar. Alto valor, bajo costo.
2. Apéndice de metodología de riesgo y definiciones de severidad/CVSS. Un
   informe comercial debe explicar cómo se calcula el riesgo. Bajo costo.
3. Consistencia severidad vs CVSS como verificación al generar: avisar si un
   hallazgo tiene severidad declarada distinta a la que implica su CVSS (puede
   pasar si se edita la severidad a mano sin tocar la calculadora). Bajo costo.
4. Numeración de figuras y "índice de figuras". Para trazabilidad de evidencia.
   Medio.
5. CVSS v4.0 y métricas temporales/ambientales (hoy solo Base). Medio.
6. TOC nativo de Word (campo TOC) y enlaces internos clicables en el PDF
   (referencias cruzadas hallazgo <-> resumen <-> narrativa). Medio.
7. Integridad de evidencia: hash por captura y export de anexos. Medio.
8. Lista de distribución y clasificación por página ya existen parcialmente
   (control del documento); conviene formalizarlas.

## Veredicto

La base es sólida y publicable: la calculadora CVSS es correcta y consistente,
la numeración aguanta informes largos, y los tres formatos salen alineados con
las secciones activas. Para un informe comercial de primer nivel, lo que más
suma a continuación son las variables de plantilla, el apéndice de metodología
de riesgo, y la verificación severidad/CVSS. CVSS v4.0 es la mejora de estándar
pendiente más relevante.

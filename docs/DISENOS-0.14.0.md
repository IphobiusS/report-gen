# Diseños y presets de report-gen 0.14.0

Un **tema** define el aspecto. Un **preset** proporciona las secciones iniciales.
Puedes combinar ambos: cambiar el tema no cambia los hallazgos ni las secciones
de un proyecto existente. La versión incluye seis temas y catorce presets.

## Qué diseño elegir

| Tema | Carácter y uso recomendado | Tratamiento |
| --- | --- | --- |
| `ejecutivo` | Nuevo. Entregas a dirección y clientes que prefieren sobriedad. | Portada blanca, banda azul marino, título serif y acentos petróleo. Cuerpo limpio, jerarquía sin subrayados gruesos. |
| `corporativo` | Consultoría y entregas técnicas convencionales. | Portada clara, tipografía azul marino y tablas compactas sobre papel blanco. |
| `serio` | Informe técnico general con identidad propia. | Tipografía monoespaciada en títulos, acento verde y cuerpo blanco. |
| `laboratorio` | Nuevo. Documentación de máquinas, prácticas y procedimientos reproducibles. | Portada verde muy claro, banda lateral, metadatos en caja, títulos mono y cuerpo apto para imprimir. |
| `offsec` | Documentación de máquinas y ejercicios con presentación sobria. | Portada centrada y acento azul, cuerpo blanco, procedimientos y evidencias. |
| `htb` | Lectura digital de laboratorios. | PDF oscuro completo y verde lima. En Word, portada oscura y cuerpo claro para edición e impresión. |

Son diseños propios. Los nombres HTB y OffSec identifican la orientación del
flujo, no una plantilla oficial ni una aprobación para presentar un examen.
Las instrucciones vigentes del proveedor prevalecen sobre cualquier preset.

## Revisión de los catorce presets

Todos se verificaron en español e inglés. Los textos de arranque son
instrucciones `TODO`: no afirman haber obtenido acceso, encontrado
vulnerabilidades ni capturado flags. La revisión de entrega señala esos TODO.
Se corrigieron títulos que permanecían en español y dos especialidades mal
asignadas: CWEE es explotación web experta y CWPE es pentesting Wi-Fi.
Referencia consultada: [catálogo de certificaciones de HTB](https://help.hackthebox.com/en/articles/12741732-academy-certifications).

| Preset | Tema inicial | Revisión / propósito |
| --- | --- | --- |
| `base` | serio | Conserva el flujo clásico; no introduce secciones personalizadas. |
| `client` | corporativo | Resumen ejecutivo, alcance, metodología, hallazgos y remediación. |
| `exam` | offsec | Procedimientos y evidencias de máquinas; instrucciones de preparación explícitas. |
| `cpts` | htb | Pentest general con alcance, recorrido técnico y remediación. |
| `cwes` | htb | Evaluación web; límites y remediación explícitos. |
| `cape` | htb | Active Directory; contexto, recorrido técnico y recomendaciones. |
| `coae` | htb | Aplicaciones de IA; contexto, alcance y hallazgos verificables. |
| `cwee` | htb | Explotación web avanzada; corrige la antigua asignación a Wi-Fi. |
| `cwpe` | htb | Evaluación Wi-Fi; corrige la antigua asignación a web. |
| `cjca` | htb | Práctica de análisis con explicación de objetivos y resultados. |
| `cdsa` | htb | Análisis defensivo, evidencias y recomendaciones. |
| `ctf` | serio | Máquinas, pasos y evidencia; elimina afirmaciones ficticias de éxito. |
| `executive` | ejecutivo | Nuevo. Estructura de cliente con presentación editorial. |
| `laboratory` | laboratorio | Nuevo. Cuaderno técnico de máquinas con alcance explícito. |

El inventario exacto de secciones figura en `preset-review-0.14.0.json`.
Las correcciones de presets afectan a proyectos nuevos; no migran los existentes.

## Cambios comunes de composición

- Portadas con ilustración: espacio reservado para la imagen y metadatos que
  pueden envolver. Se compactó el bloque de logos del tema HTB.
- Word: tabulaciones heredadas retiradas para alinear el extremo derecho de las
  cabeceras. Los bloques y fragmentos de código usan DejaVu Sans Mono.
- Los comandos se reproducen literalmente: ya no se añade un `$ ` decorativo a
  peticiones HTTP, PowerShell o comandos que no lo tenían.
- La IP de máquina y la etiqueta «Máquina» tienen contraste medido de al menos
  4,5:1 en los seis temas. Los enlaces heredan colores legibles del tema.

Los PDF y DOCX usan motores distintos. Se conserva el contenido, pero cambian
algunos saltos, tipografías y elementos decorativos. Las muestras tienen siete
páginas PDF y seis páginas Word renderizadas con LibreOffice; esto no indica
contenido perdido. No se ha probado Microsoft Word en esta entrega.

## Personalizar sin bifurcar el diseño

Desde Informe puedes cambiar título, subtítulo, cliente, evaluador, logos,
ilustración de portada y los campos de marca disponibles. Los colores de texto
se mantienen independientes del acento decorativo para conservar legibilidad.
Comprueba siempre el resultado si usas títulos o logos especialmente grandes.

Los temas PDF viven en `themes/`; Word usa los estilos y paletas de
`exporters/docx.py`. Modificar solo CSS no crea automáticamente el mismo cambio
de composición en Word. `themes/fonts/` incluye las fuentes nuevas y su licencia;
instálalas en el sistema si el visor de Word sustituye sus nombres.

## Reproducir las muestras

El proyecto `examples/design-sample/` es completamente ficticio y combina una
vulnerabilidad web con una máquina. Para generar un diseño, copia esa carpeta,
cambia `meta.theme` por uno de los seis identificadores y ejecuta:

```bash
python engine.py ruta/a/engagement.yaml --backend weasyprint -o muestra.pdf
python export.py ruta/a/engagement.yaml -f docx -o muestra.docx
```

El paquete de muestras contiene seis PDF, seis DOCX y las seis carpetas de
proyecto que se utilizaron. Los documentos se generaron con report-gen; no se
retocaron después de exportarlos.

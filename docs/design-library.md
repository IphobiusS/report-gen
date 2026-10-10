# Biblioteca de diseños y plantillas

La biblioteca reúne 22 perfiles de certificación, dos variantes por perfil y los seis diseños generales existentes. Los perfiles combinan una composición de portada con una estructura inicial de trabajo y una referencia de entrega. Son diseños independientes de report-gen, no plantillas oficiales ni una garantía de aceptación de un examen.

## Uso

Abre **Biblioteca de informes** desde el panel izquierdo, la pantalla inicial o **Nuevo proyecto**. Filtra por OffSec, HTB, generales o plantillas personales y busca por certificación o curso. Cada diseño del catálogo permite comparar una portada, un resumen y una página técnica exportados realmente por la herramienta. Las muestras se identifican como ficticias.

- **Crear proyecto** inicia un documento ES o EN con instrucciones `TODO`, sin hallazgos ni resultados inventados.
- **Aplicar apariencia** cambia exclusivamente `meta.theme` y `meta.design`. Conserva título, cliente, secciones, hallazgos, imágenes, evidencias y el resto de los datos. Antes de aplicar, se guarda el trabajo y se comprueba la revisión del proyecto.
- **Marca** utiliza el acento del perfil. **Sobria** utiliza una paleta gris azulada y reduce las superficies oscuras. El cuerpo de los perfiles nuevos permanece sobre blanco.
- **Duplicar y personalizar** permite cambiar nombre, colores, composición y títulos de las secciones. También puedes tomar los títulos del proyecto abierto, sin copiar sus datos privados ni su contenido. Los apartados generales se convierten en secciones propias para evitar que reaparezca texto predeterminado.
- **Mis plantillas** permite editar o eliminar esas variantes. Los proyectos guardan una copia de la apariencia; editar o borrar una plantilla no modifica los informes existentes.

Las plantillas personales se guardan en `webapp/library/designs.json`. Se comprueba la revisión de la biblioteca para evitar que una pestaña sobrescriba lo guardado en otra. El límite es de 200 plantillas y 40 secciones por plantilla, sujeto al límite general de lectura de archivos. Si una escritura excede ese límite, se rechaza antes de sustituir el archivo.

## Composición y fuentes

Hay cinco composiciones para los perfiles: banda lateral, dos zonas, marco, franja central y cronología. La biblioteca no presenta 22 recoloraciones como si fueran 22 composiciones diferentes: cada perfil aporta su especialidad, estructura, motivo geométrico y orientación de entrega. Los motivos son originales y no contienen logotipos ni insignias oficiales.

El título queda centrado en la zona central y los datos del cliente en el tercio inferior. Se han comprobado títulos largos, nombres de organización extensos, los seis campos de portada y los tres recursos opcionales: logotipo propio, logotipo de cliente e ilustración.

Word utiliza Calibri; PDF utiliza Carlito incrustada, una alternativa compatible en métricas. Los comandos conservan una fuente monoespaciada. Es una decisión editorial del producto, no una supuesta exigencia universal de OffSec o HTB. Las guías vigentes del examen prevalecen sobre la configuración del perfil.

Los acentos claros se oscurecen cuando se utilizan como texto sobre blanco, buscando al menos 4,5:1. El color original se conserva en elementos decorativos de portada. El texto de las superficies de portada elige tinta clara u oscura según su contraste, incluidas las variantes personalizadas.

## Catálogo y procedencia

Consulta de referencias: **3 de octubre de 2026**. Los colores OffSec proceden de los gráficos de curso publicados en su catálogo. Para HTB se utiliza la paleta compartida de sus diseños públicos de informe: verde `#9FEF00` y fondo `#161D2A`. No se atribuye a cada certificación HTB un color oficial diferente.

| Familia | Perfil | Curso o especialidad | Acento de portada | Composición |
|---|---|---|---|---|
| OffSec | OSCP / OSCP+ | PEN-200 | `#FF5500` | Banda lateral |
| OffSec | OSEP | PEN-300 | `#00B600` | Dos zonas |
| OffSec | OSWA | WEB-200 | `#FF0064` | Marco |
| OffSec | OSWE | WEB-300 | `#07C7C2` | Franja central |
| OffSec | OSWP | PEN-210 | `#0069FF` | Dos zonas |
| OffSec | OSED | EXP-301 | `#00B775` | Franja central |
| OffSec | OSEE | EXP-401 | `#F01A00` | Marco |
| OffSec | OSDA | SOC-200 | `#5CD6ED` | Cronología |
| OffSec | OSIR | IR-200 | `#06C68D` | Cronología |
| OffSec | OSTH | TH-200 | `#9869F5` | Banda lateral |
| OffSec | OSAI / OSAI+ | AI-300 | `#FB203B` | Marco |
| OffSec | OSCC SEC | SEC-100 | `#FFDF00` | Dos zonas |
| OffSec | OSCC SJD | SJD-100 | `#5B9EB3` | Franja central |
| OffSec | KLCP | PEN-103 | `#2777FF` | Banda lateral |
| HTB | CPTS | Pentesting | `#9FEF00` | Banda lateral |
| HTB | CWES | Explotación web | `#9FEF00` | Marco |
| HTB | CWEE | Explotación web experta | `#9FEF00` | Franja central |
| HTB | CAPE | Active Directory | `#9FEF00` | Banda lateral |
| HTB | CWPE | Pentesting Wi-Fi | `#9FEF00` | Dos zonas |
| HTB | CDSA | Defensa | `#9FEF00` | Cronología |
| HTB | CJCA | Fundamentos | `#9FEF00` | Dos zonas |
| HTB | COAE | IA ofensiva | `#9FEF00` | Marco |

Las estructuras de defensa incluyen cronología, fuentes, consultas y respuesta. Las de explotación priorizan entorno, causa raíz y reproducción. CAPE incluye dominios e identidades; los perfiles web, peticiones y trazado; los de IA, límites de confianza y casos de prueba. SEC-100, SJD-100 y KLCP se ofrecen como cuadernos de práctica sin presuponer que soliciten un informe de examen.

Los seis diseños generales son Serio, Corporativo, OffSec, HTB, Ejecutivo y Laboratorio. Los presets anteriores permanecen disponibles para compatibilidad.

La sección **Históricas** contiene referencias, no nuevos requisitos: CBBH remite a CWES, OSMR señala la pausa de emisión y OSCE³ se describe como reconocimiento conjunto de OSEP, OSWE y OSED. OSCP/OSCP+ y OSAI/OSAI+ comparten perfil.

Fuentes:

- [Catálogo OffSec](https://www.offsec.com/courses/).
- [Certificaciones HTB Academy y requisitos de entrega](https://help.hackthebox.com/en/articles/12741732-academy-certifications).
- [Diseños públicos HTB para SysReptor](https://docs.sysreptor.com/htb-reporting-with-sysreptor/). Se toma la referencia cromática, no su código de plantillas.
- [OSAI y OSAI+](https://help.offsec.com/hc/en-us/articles/46593095198740-OSAI-Advanced-AI-Red-Teaming-AI-300-FAQ).
- [Cambios de OSMR](https://help.offsec.com/hc/en-us/articles/41591722499604-OSMR-Certification-Exam-Changes-FAQ).
- [OSCE³](https://help.offsec.com/hc/en-us/articles/4403282452628-OSCE-FAQ).
- [Transición de CBBH a CWES](https://academy.hackthebox.com/news/the-transition-from-htb-cbbh-to-htb-cwes-has-officially-started).

## Preparar una entrega

Al abrir **Preparar entrega**, un proyecto con perfil muestra la referencia correspondiente y propone los formatos iniciales. Siempre puedes cambiarlos.

CWEE propone Markdown y explica el paso de crear un ZIP protegido con la contraseña indicada por el examen. **report-gen no cifra ese ZIP**. CPTS, CWES, CAPE y CDSA incluyen la referencia consultada de PDF o ZIP sin cifrar de hasta 20 MB. El tamaño, idioma, nomenclatura y detalles del examen requieren comprobación humana con la guía vigente.

El paquete de report-gen incluye documentos y archivos de verificación. No debe confundirse automáticamente con el paquete que solicita un examen. Selecciona los archivos que ese examen pida. La referencia consultada queda también registrada en `verificacion.json` y `LEEME.txt` de la entrega.

## Reproducir muestras

Desde la carpeta del programa, con sus dependencias instaladas:

```sh
python -m pip install -e '.[dev,previews]' -c requirements-audited.txt
python -m playwright install chromium
python scripts/build-design-previews.py --output muestras-biblioteca
python scripts/audit-design-library-0150.py --output comprobacion-biblioteca
pytest -q
```

El constructor genera 50 PDF, 50 Word y las 150 vistas WebP de la galería desde datos ficticios mediante la interfaz normal de exportación. Para limitar la generación, añade `--only offsec-oscp htb-cpts`. Esa opción también limita el registro de generación a la selección ejecutada.

Los estilos nativos de Word conservan el contenido y la jerarquía, aunque su paginación y algunos detalles de líneas pueden diferir del PDF. Revisa el resultado en el editor o visor que utilizará el destinatario.

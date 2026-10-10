# Portadas de report-gen 0.14.1

Esta revisión reorganiza los seis diseños existentes. Conserva sus identificadores
y los proyectos siguen abriendo con el tema elegido. No añade seis nombres para
variantes de color: cambia la composición de las portadas PDF y Word.

## Jerarquía

La marca y los logos quedan arriba. El título ocupa una zona central independiente,
con alineación óptica y espacio para un subtítulo o una ilustración. Los datos del
cliente y del evaluador quedan en el tercio inferior, separados del título.

| Tema | Composición de portada |
| --- | --- |
| Ejecutivo | Papel blanco, regla azul marino, título centrado y ficha inferior de dos columnas. |
| Corporativo | Banda central azul marino con título claro, acento lateral azul y ficha inferior segmentada. |
| Serio | Fondo oscuro, franja verde lateral, título alineado a la izquierda en la zona central y datos en filas. |
| Laboratorio | Papel verde muy claro, franja lateral ancha, título a la izquierda y ficha inferior blanca. |
| OffSec | Papel blanco, reglas finas, título centrado y bloque inferior estrecho con pares de etiqueta y valor. |
| HTB | Fondo oscuro, acento superior lima, título centrado entre dos líneas y datos inferiores alineados a la derecha. |

Centrar todos los elementos no es necesario: Serio y Laboratorio mantienen un eje
izquierdo, pero el título deja de competir con los datos del cliente. Todos comparten
una jerarquía legible; sus bandas, alineaciones y fichas distinguen los estilos.

## Tipografía

- Word declara **Calibri** para el cuerpo y la portada. En esta revisión la portada
  deja de usar títulos serif o monoespaciados decorativos.
- PDF incrusta **Carlito regular y negrita** en la portada. Carlito es una alternativa
  de métricas compatibles con Calibri. Se distribuye con su licencia OFL en
  `themes/fonts/`; no requiere instalar una fuente para ver correctamente el PDF.
- El cuerpo conserva las familias y tamaños profesionales del sistema existente.
  Al disponer de Carlito real, el motor PDF puede resolver esa familia en vez de
  sustituirla por DejaVu Sans. Esto cambia algunos cortes de línea respecto al
  entorno anterior; las páginas de las seis muestras se volvieron a revisar.
- Comandos, vectores y elementos técnicos conservan su fuente monoespaciada.
  No se usa la tipografía pixel del sitio web para el texto del informe.
- Word no incrusta Calibri. Si el equipo no la tiene, su visor puede sustituirla.
  LibreOffice utilizó Carlito al renderizar las muestras de esta entrega.

No hay una fuente universal obligatoria para todo informe de pentesting. Si una
organización o evaluación prescribe una familia y tamaño concretos, esos requisitos
prevalecen. Los temas OffSec y HTB son diseños propios, no plantillas oficiales.

## Muestras y personalización

El ZIP de muestras contiene seis PDF y seis DOCX, sus proyectos ficticios editables
y una comparativa de portadas. Todas las muestras salieron directamente de la
herramienta; no se retocaron los documentos exportados.

Cambia el tema desde **Informe → Tema**. Los campos de marca, título, subtítulo,
cliente, evaluador, logos e ilustración siguen siendo editables. Los metadatos
vacíos no generan filas de relleno. Los logos mantienen su proporción.

Para reproducir una muestra desde una copia de `examples/design-sample/`, establece
`meta.theme` y ejecuta:

```bash
python engine.py ruta/engagement.yaml --backend weasyprint -o muestra.pdf
python export.py ruta/engagement.yaml -f docx -o muestra.docx
```

PDF y DOCX mantienen el contenido, pero sus motores pueden producir distintos
saltos. Las muestras tienen siete páginas PDF y seis páginas DOCX renderizadas
con LibreOffice. Microsoft Word no estuvo disponible para una revisión visual.

La composición PDF vive en `templates/cover.html`, `themes/_common.css` y los seis
CSS de tema. Word tiene su composición nativa en `exporters/cover.py`.

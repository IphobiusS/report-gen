# Validación de report-gen 0.21.2

Fecha: 5 de octubre de 2026 (UTC). Caso: Grupo Ladera Logística, empresa ficticia. Base: ZIP 0.21.1, SHA-256 `d646c23af9aa9b1e6cf249474b8ae70ac99916ce82cd0f5258b5932fa728eb71`; sus 609 entradas de manifiesto coincidieron antes de editar.

## Resultado

Los cinco defectos se corrigieron y dejaron de reproducirse en el entorno disponible. Se repitió el informe largo sin cambiar el contenido original del proyecto. Las referencias, los metadatos, las evidencias, la visibilidad estática y la apertura de fichas en Word tienen pruebas de regresión. Esto no equivale a certificar todos los motores de documentos ni toda combinación posible de CSS.

| Hallazgo | Corrección | Comprobación |
| --- | --- | --- |
| RG-L01 | IDs estables; nuevas asignaciones sin reutilizar números; referencias huérfanas bloqueadas | Borrar F01, reordenar y duplicar conserva el UUID y el destino de F10; clic real en Chromium; borrar F10 devuelve 422 y deshacer restaura su identidad |
| RG-L02 | Metadatos, tablas nativas y destinos de enlaces en contrato v3 | Activo, severidad, historial y enlace alterados se rechazan; regresiones adicionales de CVSS, CWE, portada y máquinas |
| RG-L03 | Huella, pie, contexto y posición de cada evidencia | Intercambio, sustitución, duplicado y traslado entre pasos se rechazan en HTML, DOCX y Markdown, también sin comandos |
| RG-L04 | Contenido estáticamente oculto excluido; revisión visual explícita | Pruebas de hidden, display, visibility, opacidad y ancestros; exportación original sin filtrar válida |
| RG-L05 | Continuidad entre título, metadatos y comienzo del contenido en Word | 24 hallazgos y dos máquinas conservan el comienzo en la misma página en LibreOfficeDev; F04, F06, F10 y F21 ya no quedan aislados |

Los IDs visibles existentes se usan como anclas permanentes junto con el UUID de la ficha. No hay renumeración automática ni necesidad de migrar enlaces válidos. No es posible adivinar el destino de una referencia que una edición anterior ya hubiera desviado: los proyectos afectados por versiones anteriores requieren esa revisión.

## Pruebas ejecutadas

| Prueba | Resultado |
| --- | --- |
| Suite Python completa | 854 aprobadas, 0 fallos, 6 avisos; 67 casos nuevos de 0.21.2 |
| Ruff | Sin errores |
| JavaScript: guardado y borradores | 12 aprobadas |
| DOM con rutas reales de Flask | 29 comprobaciones aprobadas |
| Chromium 141.0.7390.37 | 26 comprobaciones aprobadas; creación de copias desde respaldo, edición, referencia, deshacer y descargas |
| Mutaciones del reproductor original | 8/8 rechazadas; en 0.21.1 se aceptaban 6/8 |
| Entrega conjunta | 4 formatos y 3 anexos; las 7 huellas y tamaños del manifiesto coinciden |
| Privacidad sintética | Tres marcadores privados ausentes del texto, ZIPs, flujos PDF e imágenes decodificados; 80 colocaciones/recursos examinados |
| Móvil, 390 × 844 | Sin desbordamiento horizontal en el editor examinado |
| Consola y red del recorrido | Sin errores JavaScript ni peticiones externas observadas |

Los seis avisos de pytest son uno de futura dependencia de HarfBuzz, cuatro de API de Pillow obsoleta en pruebas y uno por el ZIP duplicado generado deliberadamente en una prueba de rechazo. No se efectuó un nuevo análisis de vulnerabilidades de dependencias: el inventario auditado previo se conserva como tal.

## Repetición del informe largo

La fuente contiene 24 hallazgos, dos máquinas, 12 activos, 31 registros de cobertura, 26 evidencias, cinco retests y tres anexos. Dos hallazgos permanecen pendientes de valoración, sin inventar CVSS. Las cuatro advertencias del escenario se conservan: dos máquinas sin evidencia y dos actividades de cobertura pendientes o bloqueadas.

| Formato | Comprobación automática | Revisión adicional |
| --- | --- | --- |
| HTML | 262 párrafos, 26 bloques literales, 56 metadatos, 28 destinos de enlaces, 26 asociaciones de evidencia y 348 unidades estructurales | Navegación real y capturas en Chromium; controles estáticos de visibilidad |
| DOCX | Mismos conteos estructurados que HTML; 49 referencias internas y recursos íntegros | 65 páginas renderizadas; revisión de todas las páginas en láminas y ampliación de casos relevantes |
| Markdown | 261 párrafos; mismos 26 bloques, 56 metadatos, 28 destinos, 26 asociaciones y 348 unidades | Omite deliberadamente el gráfico de severidad y su leyenda; anclas explícitas |
| PDF | 78 páginas, 262 párrafos por presencia, 26 imágenes, 34 valores de metadatos por presencia y 21 destinos del índice | Revisión de todas las páginas en láminas; extracción no acredita espacios literales ni asociación de evidencia |

Los archivos de la entrega se volvieron a verificar independientemente de los botones del editor. El XML principal del Word entregado coincide con el renderizado; las páginas del PDF entregado coinciden píxel por píxel con las revisadas a la resolución de comparación. El proyecto editable de origen conserva sus bytes. Las copias con mutaciones no se incluyen como informes válidos.

## Límites y pendientes

- Motor de Word disponible: LibreOfficeDev 26.8.0.0.alpha0. Microsoft Word nativo y LibreOffice estable no se ejecutaron en este ciclo. La corrección de RG-L05 está verificada en el motor que reprodujo el defecto, con compatibilidad externa aún pendiente.
- Los números de página del índice DOCX requieren actualizar los campos en un editor compatible. Los enlaces y títulos sí se incluyen. No se copian números desde el PDF.
- Firefox no se volvió a ejecutar. Sigue pendiente la validación en un entorno que permita sus procesos, bloqueados por EPERM en la revisión anterior.
- La visibilidad estática no certifica geometría, oclusión, reglas condicionales arbitrarias ni todos los estados interactivos. PDF no acredita asociación de bloques ni comandos literales. `manual_review_required` es verdadero en todos los formatos.
- El comparador contrasta el artefacto con la representación pública común. No es una prueba independiente de la corrección de todo el proceso de renderizado ni una validación técnica de los hallazgos redactados por el usuario.
- La asociación de imagen incluye hash, pie, orden de código y contexto precedente. Contextos textuales idénticos no proporcionan por sí mismos una identidad única de paso; por eso sigue siendo necesaria la revisión visual.
- El análisis de privacidad de este ciclo busca tres marcadores sintéticos conocidos. No prueba ausencia de cualquier secreto posible.

## Mejoras conservadas para el siguiente ciclo

MEJ-01: mayor espacio útil de HTML; MEJ-02: paginación configurable; MEJ-04: diferenciar evidencia inicial y retest; MEJ-05: riesgo inicial frente a estado actual; MEJ-06: nombre de máquina consistente; MEJ-07: compatibilidad nativa de Word/LibreOffice estable; MEJ-08: ajuste de vista previa al panel. MEJ-03 queda parcialmente resuelta: todos los formatos exigen revisión visual explícita, pero aún no hay firma editorial de un revisor por formato. Estas propuestas no se presentan como implementadas en 0.21.2.

## Reproducir

```bash
python3 start.py --setup
.venv/bin/python -m pip install -e '.[dev]'
npm ci
.venv/bin/python -m pytest
npm test
RG_PYTHON="$PWD/.venv/bin/python" npm run test:workspace
npx playwright install chromium
RG_PYTHON="$PWD/.venv/bin/python" node scripts/audit-browser-0212.cjs \
  --project-zip /ruta/Grupo-Ladera-proyecto-editable.zip \
  --output out/ladera-0212
```

El proyecto ficticio y las capturas se distribuyen por separado del código. El paquete de pruebas contiene los JSON, los registros, el reproductor de mutaciones, la comparación independiente, las capturas de Chromium y la renderización de Word. No incluye datos de Fondos Cultura ni tokens de sesión reales.

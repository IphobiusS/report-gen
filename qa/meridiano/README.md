# Grupo Meridiano Logística — caso ficticio de aceptación

Plan y entradas del caso GML 1.0 para report-gen 0.38.0. Este documento describe
cobertura prevista: no es un recibo de pruebas ejecutadas.

El constructor escribe exclusivamente YAML, PNG fabricados y entradas inertes.
Todos los informes PDF, DOCX, Markdown y HTML deben producirse con exportadores,
colas y entregas nativas de report-gen. LibreOffice y otras herramientas externas
sólo pueden inspeccionar o representar documentos previamente generados.

## Caso

- 30 hallazgos: 3 críticos, 8 altos, 12 medios, 5 bajos y 2 informativos.
- 4 cuadernos de máquinas, cada uno con 5 fases; no se cuentan como vulnerabilidades.
- 16 activos, 32 evidencias, 90 contratos de cobertura, 16 secciones, 5 causas raíz
  y 10 registros de seguimiento.
- 5 anexos: 4 incluidos, 1 privado excluido; originales de imagen y nota no enlazada
  excluidos de la publicación. Redacción literal y metadatos sintéticos de control.
- 5 importadores válidos: CSV, Burp, Nuclei, Nmap y SARIF.
- ES, EN y PT localizan etiquetas y navegación. La prosa de autor permanece en
  español y esa limitación aparece en el propio informe.

La validación de esquema no debe producir errores ni avisos. La revisión previa
debe conservar 31 avisos deliberados: 30 estados de cobertura pendiente/bloqueada
y 1 anexo excluido. No deben borrarse para presentar una revisión artificialmente
limpia: constituyen parte de la prueba del consentimiento informado de exportación.

## Ejecución reproducible

```sh
python scripts/build-meridiano-case.py --output /tmp/meridiano/case
python scripts/audit-meridiano-exports.py \
  --projects /tmp/meridiano/case/projects --output /tmp/meridiano/exports --mode all
```

Usar directorios nuevos después de cada corrección; no sobrescribir un recibo
fallido. Congelar el productor antes de generar los resultados de entrega. Cada
trabajo registra hashes de fuentes, productor y archivos, y exige inmutabilidad.

La matriz contiene 40 salidas: 12 informes completos (3 idiomas × 4 formatos),
20 muestras de los otros 5 estilos generales y 8 muestras de 2 perfiles
especializados × 2 variantes × PDF/DOCX. Las muestras conservan F01, F12 y M01:
hallazgo convencional, figuras enlazadas/adyacentes en tablas y fases de máquina.
No se presenta esta selección como una repetición de todos los perfiles.

La inspección nativa se puede añadir con `--native-executable` y
`--require-stable`. Su resultado sólo acredita el motor identificado; nunca
Microsoft Word o Safari nativo. El navegador real se ejecuta en CI si el entorno
local no permite lanzar su proceso, sin eludir esa restricción.

## Nuevas funciones

1. Localizadores: importaciones con CSV multilínea y campos inválidos en cada
   formato; errores de exportación que identifiquen hallazgo, campo y tabla/fila
   cuando esa correspondencia sea comprobable. Verificar que no se copia el valor
   privado al localizador ni se aceptan entradas inválidas silenciosamente.
2. Vista previa DOCX: exportación nativa en cola, motor declarado, fuente y PDF con
   hashes, revisión congelada, descarga y limpieza; ausencia/fallo/cancelación
   explícitos. No confundir la representación de LibreOffice con Microsoft Word.
3. Privacidad PDF: subir un PDF generado por report-gen, inspeccionar estructura,
   límites, ubicaciones y hashes sin cambiar bytes ni inclusión/revisión del
   anexo; probar anotaciones, formularios, enlaces, adjuntos y cifrado mediante
   fixtures inertes separados. La revisión estructural nunca es garantía completa.

La aceptación conserva acciones ejecutadas, archivos, verificaciones, errores
inesperados y límites. Un plan, una simulación o una prueba duplicada no cuenta
como una nueva verificación realizada. Las capturas finales deben provenir de la
interfaz real, sin retoque, y la inspección visual se atribuye a su método real.

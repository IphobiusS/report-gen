# Auditoría de recuperación R16 - 0.35.0

El punto de partida fue la versión publicada 0.34.5 (`9a6443a1`) y la
candidata portuguesa 0.35.0 (`e615f0a2`). El respaldo parcial de R16 permitió
recuperar el corpus Estuario y las miniaturas originales. Los archivos no
recuperables no se declararon restaurados: los cambios necesarios se
reconstruyeron y comprobaron mediante regresiones nuevas.

## Defectos corregidos

| Área | Problema | Corrección y evidencia |
| --- | --- | --- |
| PDF multiescritura | Continuaciones de composición Unicode aparecían como caracteres espurios. | Se exige mapa explícito y corroboración independiente del glifo; las mutaciones de texto siguen rechazándose. |
| PDF nativo de LibreOffice | El verificador rechazaba guiones partidos en fuentes simples con mapas Unicode de un byte. | Se comprueban las asignaciones explícitas; un mapa parcial exige fuente TrueType incrustada con identidad binaria, código de glifo y posición corroborados. Se mantienen los rechazos de mapas ambiguos, glifos alterados y objetos Form ejecutados sin corroboración. |
| Tablas extensas | Valores repetidos agotaban la búsqueda de correspondencias. | Asignación completa de intervalos sin solapamiento, con el algoritmo exacto como respaldo. |
| Idioma | Datos antiguos o `pt-BR` no siempre seguían la misma normalización. | Captura, entrega y biblioteca de diseños usan el idioma normalizado del informe. |
| Errores PDF | Diez errores internos de composición y regiones no utilizaban el catálogo de idioma. | Mensajes ES/EN/PT explícitos mediante `backend_message`, sin modificar las condiciones de rechazo. |
| Causas raíz | Los rótulos generados podían quedar como párrafos aislados al final de una página. | «Causa raíz» y «Acción común» son encabezados semánticos de nivel 4; DOCX conserva `keep_with_next`. Las etiquetas en negrita escritas por el autor siguen siendo párrafos editables. |
| Apéndice | Un texto automático afirmaba que se había obtenido evidencia de acceso. | Referencias neutrales en ES/EN/PT, conservando las notas escritas por el autor. |
| Tutorial | Faltaban las imágenes portuguesas y algunos controles quedaban fuera de la captura. | Veintiuna capturas reales nuevas, revisadas y vinculadas a su ejecución de GitHub. |
| Nimbus | Crear la demostración ignoraba el idioma elegido. | Copias ES/EN/PT y ediciones localizadas reproducibles con los mismos datos técnicos y relaciones. |
| Pruebas de navegador | El entorno de ciclo de vida omitía los auxiliares de idioma reales. | Se carga el mismo bloque de auxiliares que utiliza la aplicación. |
| Pruebas Windows | La lectura de HTML UTF-8 dependía de la codificación del sistema. | Codificación explícita en las comprobaciones. |
| Publicación | Faltaba un control reproducible del caso Estuario completo. | Séptima condición obligatoria: exportaciones ES/EN/PT y apertura con LibreOffice estable del mismo commit. |

## Código muerto y compatibilidad

Se revisaron referencias Python y JavaScript, importaciones y entradas de
API/CLI. No se identificó una implementación eliminable con certeza sin
romper compatibilidad. `workflows.english_review` tiene una función de
compatibilidad documentada: la ausencia de llamadas internas no justifica
eliminarla. Se conserva. Esta revisión estática no prueba la ausencia de
código muerto ni de errores en todos los recorridos posibles.

## Comprobaciones reproducibles

```sh
python -m pytest tests/test_pdf_shaping_0350.py tests/test_pdf_simple_fonts_0350.py tests/test_pdf_hyphens_0315.py tests/test_pdf_repeated_cells_0350.py tests/test_root_cause_headings_0350.py tests/test_appendix_claims_0350.py tests/test_portuguese_exports_0350.py tests/test_nimbus_languages_0350.py
python -m pytest tests/test_backend_language_0234.py tests/test_backend_portuguese_0350.py
python scripts/build-nimbus-translations.py --check
python scripts/audit-estuario-r16.py --output out/estuario-r16
python scripts/audit-estuario-native-r16.py --input out/estuario-r16 --output out/estuario-r16-native
```

Los directorios de salida deben ser nuevos. El corpus original y los archivos
exportados se comparan por SHA-256 antes y después. La aceptación nativa
exige LibreOffice estable; una compilación de desarrollo solo puede usarse
con la opción explícita de diagnóstico y queda marcada como no elegible.
Las regresiones de composición requieren Noto Sans Devanagari y Noto Sans
CJK JP. CI instala esas fuentes y establece
`REPORT_GEN_REQUIRE_MULTISCRIPT_FONTS=1` para que su ausencia sea un fallo,
en lugar de omitir las pruebas dependientes de ellas.

El flujo `tests` distribuye todos los módulos entre cuatro trabajos y guarda
sus recibos de cobertura. Se ejecutan por separado navegadores, Windows,
macOS/Safari, renderizadores, instalación limpia del ZIP y aceptación R16.
La publicación comprueba los siete resultados contra el commit exacto de
`main`; no reutiliza éxitos de una revisión anterior.

## Alcance de las evidencias

Las comprobaciones de contenido, índice, enlaces y geometría se complementan
con revisión visual de los PDFs, DOCX renderizados y capturas. Las imágenes
del tutorial contienen datos ficticios. Sus hashes, versión del navegador,
commit y ejecución se conservan en `tutorial-capture-manifest.json`.

Los resultados de cada ejecución son artefactos de GitHub Actions y los
enlaces de aceptación de una versión publicada aparecen en su Release.
Microsoft Word de escritorio no se ha acreditado. La comparación PDF no
certifica una evaluación de seguridad; los autores deben revisar las
afirmaciones y evidencias antes de entregar un informe.

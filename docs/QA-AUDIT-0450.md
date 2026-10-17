# Auditoría de cierre 0.45.0

Base revisada: `84398094280fac3e5bf763c0e52c63100d1c22ee` (0.44.0).

Esta versión concentra correcciones y regresiones. El inventario combina lectura de código, seguimiento de referencias, reproducción de defectos, pruebas de contrato y aceptación de informes completos. Un análisis estático sin avisos no demuestra ausencia universal de código muerto o errores.

## Cobertura

| Área | Comprobación |
| --- | --- |
| Motor y cuatro exportadores | Portadas, valores vacíos y cero, anclas, paginación, imágenes, contenido, archivos temporales y conservación de salidas anteriores. |
| Editor y navegación | Módulos JavaScript/CSS, carga dinámica, idiomas, guardados, borradores, selección HAR, resultados tardíos y contratos con Flask. |
| Datos y privacidad | Bloqueos, historial, restauración, respaldos, límites de entrada, limpieza de trabajos, proyección compartible y sustituciones explícitas. |
| Evaluación | Hallazgos, instancias, evidencias, retests históricos, rutas, planes, biblioteca, reconciliación y remediación. |
| Importación e integración | Burp, ZAP, HAR, Unicode, CVSS, anexos, revisión PDF/DOCX y contratos de conectores. |
| Instalación y mantenimiento | Asistente terminal, actualizador, paquete reproducible, publicación y dependencias. |
| Código sin consumidores aparentes | AST, referencias, rutas registradas, callbacks, activos, compatibilidad documentada y pruebas. Sólo se retira código con evidencia de redundancia o inaccesibilidad. |

Los callbacks de Flask, analizadores, Montoya y UNO, los recursos cargados dinámicamente y las interfaces públicas documentadas se conservan aunque no tengan una llamada directa detectable por AST.

## Regresiones que deben ejecutarse

- `tests/test_engine_companion_atomic_0450.py`, `test_legacy_contact_links_0450.py` y `test_cover_role_only_0450.py`: salidas anteriores, destinos diferentes y paridad de portada/anclas entre formatos e idiomas.
- `tests/test_export_cancel_race_0450.py`: cancelación durante limpieza y reintentos al no poder eliminar temporales privados.
- `tests/test_import_integrity_0450.py`: codificación, referencias, CVSS y límites de importación Unicode/HTTP.
- `tests/test_workflow_audit_0450.py`: orden temporal, privacidad, asociaciones, entradas inválidas y aislamiento de datos mutables.
- `tests/test_ui_async_0450.cjs` y el recorrido nativo HTTP existente: respuestas fuera de orden, cambio de archivo y selección de comparación.
- Las regresiones adicionales de publicación y asistente se descubren junto al resto de módulos `test_*_0450.py`; no reemplazan las pruebas de versiones anteriores.

Los casos nuevos se incluyen en la colección global. El agregador de CI exige que la unión de las particiones coincida con la colección completa, sin omisiones ni duplicados inadvertidos.

## Aceptación del commit publicado

La publicación requiere siete workflows aprobados del **mismo commit actual de main**: tests, Browser acceptance, Windows compatibility, macOS compatibility, Additional renderer acceptance, Reproducible source package y R16 trilingual acceptance. No basta una ejecución anterior ni preparar archivos localmente.

Se mantienen los corpus Atlas, Aster y VEGA, las entregas PDF/DOCX/HTML/Markdown en ES/EN/PT, la inspección nativa de LibreOffice y las comprobaciones de Chromium/WebKit/Safari que ya forman parte de esos gates. Los constructores escriben entradas ficticias; los informes se generan con report-gen.

Los resultados, cantidades, capturas y límites de cada ejecución se acreditan mediante sus recibos y los enlaces de la release. Este protocolo no declara aprobadas ejecuciones pendientes.

## Dependencias y límites

El análisis de dependencias fijadas utiliza `pip-audit`; el árbol JavaScript utiliza `npm audit`. Se registran la fecha, las versiones y el resultado de la consulta. Cero avisos significa que no se encontraron vulnerabilidades conocidas en esos catálogos para las versiones examinadas en ese momento.

La revisión no certifica Microsoft Word de escritorio, una sesión humana junior/senior ni conexiones reales con Burp, Jira, DefectDojo u Ollama. Esos entornos requieren sus propios registros. Las pruebas automatizadas, el renderizado con LibreOffice y la compilación Montoya no acreditan dichas sesiones.

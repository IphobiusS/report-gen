# Aceptación del índice contextual — report-gen 0.40.0

Este protocolo verifica la navegación con el caso ficticio Atlas. La fuente del caso contiene 60 vulnerabilidades, siete cuadernos de máquinas y 23 secciones, redactados en español, inglés y portugués de Brasil. No incorpora datos de proyectos reales.

## Comportamiento esperado

- La barra general mantiene sus cinco grupos y sus rutas principales. Las listas extensas quedan en un panel contextual, con controles de búsqueda, filtro y paginación fuera del área desplazable de resultados.
- Buscar por identificador o título y cambiar filtros, idioma, ancho o visibilidad del panel no modifica el informe, su revisión guardada ni sus identidades.
- La selección se conserva por UID o clave estable. Un filtro no transforma la posición de un resultado en su identidad dentro del proyecto.
- El modo de ordenación hace explícita la edición del orden. Reutiliza el diálogo de movimiento y la recuperación de acciones del editor; cerrar el modo o cancelar el diálogo no reordena contenido.
- El diálogo utiliza el título traducido o personalizado de la sección. Al mover la sección seleccionada y al deshacer, su fila permanece visible sin desplazamiento asistido por la prueba.
- El estado del índice pertenece al espacio de trabajo y proyecto correspondientes. Los títulos y términos de búsqueda no se copian a claves globales compartidas por proyectos homónimos.
- El control de ancho es accesible con teclado. Los títulos extensos y los identificadores siguen siendo reconocibles.
- En móvil, la navegación y el índice no compiten simultáneamente por el espacio. Escape y la selección devuelven el foco a un control visible adecuado, sin interferir con diálogos abiertos.

## Verificación

1. `RG_PYTHON=python npm run test:sidebar` mantiene los contratos de navegación general.
2. `RG_PYTHON=python npm run test:context-index` comprueba el índice con el JavaScript real y el puente Flask, incluidos resultados vacíos, límites de página, invariancia del contenido, movimientos y aislamiento de preferencias.
3. La aceptación de navegador contextual usa Atlas en ES/EN/PT, dos temas y anchos de escritorio, tableta y móvil. Conserva capturas reales, geometría y errores de ejecución. Los controles se operan por sus rutas visibles, sin clics forzados.
4. Las pruebas históricas del editor y los recorridos extensos de Atlas verifican que las rutas, importaciones, ediciones y exportaciones siguen disponibles tras mover los índices.
5. Los siete controles de integración del repositorio se exigen sobre el commit exacto de MAIN antes de publicar la versión. El paquete fuente debe corresponder al mismo árbol de Git.

## Evidencia y límites

Las capturas deben revisarse visualmente además de comprobar su tamaño y hash. Una prueba DOM no acredita pintura, distribución ni comportamiento de un navegador nativo. Los archivos de resultado indican el motor y el alcance ejecutado.

La matriz histórica de Atlas distingue 12 exportaciones completas y 276 formatos de muestras; no representa todos los cruces posibles de opciones. Esta iteración cambia navegación y presentación del editor, sin componer o reparar documentos exportados mediante herramientas externas.

La auditoría debe distinguir pruebas ejecutadas, archivos efectivamente conservados y revisión visual. Los controles negativos esperados no se presentan como errores de generación. La ausencia de defectos observados se limita a los recorridos y motores comprobados.

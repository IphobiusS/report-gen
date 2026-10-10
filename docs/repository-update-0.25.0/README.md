# Actualización del repositorio a 0.25.0

La rama pública partía de 0.13.0, commit `6679a8bd9b43e31b6301e61896d68e2c1622c2a7`. Se incorpora la entrega validada de report-gen 0.25.0: código, pruebas, diseños, ejemplos, licencias y documentación.

## Procedencia

El ZIP de referencia `report-gen-0.25.0.zip` tiene SHA-256 `7c861222acc53e0342b1eee30e0b21c9b5a9a33d5c2dbc5ab80a0403c6d11e11`. Sus 816 entradas de manifiesto se comprobaron antes de integrar los archivos. El [manifiesto original](../history/MANIFEST-0.25.0-original.sha256) corresponde a ese ZIP y usa rutas relativas a su raíz; no describe las ediciones documentales posteriores de este repositorio.

Se conservan los siete archivos exclusivos de la rama anterior: sus guías y verificaciones históricas, las dos auditorías Markdown ya públicas y `webapp/projects/.gitkeep`. Se excluyen de esta publicación 137 registros técnicos nuevos de auditoría y datos de ejecución, conservados en el archivo local de la entrega. No se incorporaron proyectos privados ni entornos locales.

## Ajustes para GitHub

- Bienvenida nueva en español e inglés, con instalación temprana, el logo original y los cuatro formatos actuales.
- Guías operativas separadas del historial. Las tres bienvenidas anteriores se conservan con sus enlaces reubicados y una nota de archivo.
- Instrucciones activas de actualización corregidas a 0.25.0 y dependencias de desarrollo restringidas por la instantánea auditada.
- Dos excepciones precisas en `.gitignore` para incluir los PDF de ejemplo que pertenecen a la entrega.
- La lista alternativa `webapp/requirements.txt` incorpora `tinycss2`, `cssselect2` y `pypdf`, con los mismos rangos que `pyproject.toml`.
- El manifiesto de la raíz se regenera para los archivos de esta edición del repositorio. Las evidencias históricas conservan sus hashes originales y no se presentan como pruebas nuevas.

El código operativo y los recursos de la aplicación conservan los bytes de la entrega validada. La versión de la aplicación sigue siendo 0.25.0; esta sincronización no añade funciones posteriores a esa versión.

## Verificación local de publicación

Instalación editable en entorno limpio con restricciones auditadas, `pip check` y Ruff aprobados. Pasaron 162 pruebas Python, 12 pruebas Node y 67 controles de interfaz. Se generaron y abrieron PDF, DOCX, Markdown ZIP y HTML desde un ejemplo incluido. Las nuevas guías y bienvenidas pasaron 94 referencias locales y 53 comprobaciones de compatibilidad de anclas.

[Detalle y límites](PUBLICATION-QA.md). La ejecución usa Chromium/Linux; no acredita Windows nativo, Microsoft Word de escritorio ni una nueva auditoría completa de 0.25.0. La validación local es independiente de los workflows remotos que ejecute GitHub al publicar.

Se publican los resúmenes en Markdown de los resultados y sus límites. Los registros técnicos, JSON, inventarios de dependencias, capturas y exportaciones se conservan como evidencia archivada fuera de GitHub; no se adjuntan logs ni rutas internas del entorno. Las referencias de las actas históricas a esos archivos identifican la evidencia archivada y no enlaces a archivos disponibles en este repositorio. Esta selección documental no modifica los bytes del código operativo ni de los recursos de la aplicación. La [validación original de 0.25.0](../../VALIDACION-0.25.0.md) conserva el resumen y el alcance de la entrega de referencia; su publicación no implica una nueva ejecución de la auditoría histórica.

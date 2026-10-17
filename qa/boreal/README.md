# Boreal 1.0 — caso ficticio de aceptación

Boreal Redes y Energía es una organización inventada para revisar informes
extensos de report-gen 0.41.0. El corpus contiene 72 hallazgos y 6 cuadernos
separados, con 36 activos, 84 imágenes sintéticas, 216 contratos documentales,
36 seguimientos y 6 tablas extensas dentro de los hallazgos. La prosa, las
imágenes y los anexos se redactaron en español, inglés y portugués de Brasil.
Los dominios `.example` y las redes de documentación no son objetivos de prueba.

El constructor produce **entradas**, nunca documentos de informe:

```sh
python scripts/build-boreal-case.py --output /tmp/boreal-source
python scripts/audit-boreal-0410.py \
  --projects /tmp/boreal-source/projects --output /tmp/boreal-outputs
```

La segunda orden utiliza únicamente la captura, entrega y exportadores de
report-gen. Genera 12 informes completos: cuatro formatos por idioma. Las 578
filas de las tablas son criterios inventados; no se presentan como 578 pruebas
reales. La auditoría comprueba su presencia única en los cuatro formatos, el
orden de páginas y las cabeceras repetidas en PDF/DOCX. Se conservan los hashes
del productor, fuentes y salidas, incluso cuando una comprobación falla.

Para inspeccionar los DOCX ya generados mediante LibreOffice estable:

```sh
python scripts/audit-boreal-0410.py --mode native \
  --projects /tmp/boreal-source/projects --output /tmp/boreal-outputs \
  --native-executable soffice --require-stable
```

El motor externo solo convierte documentos existentes para inspección; no
compone el informe. La revisión visual y Microsoft Word necesitan sus propias
evidencias. `coverage-plan.json` es un plan, no un acta de aceptación. Los
recorridos de entrega guiada, borradores, revisión persistente e instalación
requieren pruebas independientes de sus interfaces y fallos reales.

El corpus conserva 73 advertencias deliberadas por idioma: 72 contratos con
estados pendientes o bloqueados y un anexo privado excluido. No son errores de
generación ni resultados de un pentest ejecutado. Los cinco ficheros de importación
son entradas inertes en inglés para los parsers existentes; no forman parte de
la prosa localizada de los informes.

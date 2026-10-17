# Aster 1.0 — caso bancario ficticio de aceptación

Grupo Financiero Aster es una organización inventada. Los datos, identidades,
peticiones, resultados, puntuaciones e imágenes son sintéticos. El constructor
no conecta con objetivos y no ejecuta pruebas de seguridad.

El caso amplía las primitivas de composición de tablas de Boreal con doce
dominios bancarios nuevos, narrativa ES/EN/pt-BR, identidades independientes y
modelos de trabajo incorporados en report-gen 0.42.0:

| Recurso | Cantidad por idioma |
| --- | ---: |
| Hallazgos de vulnerabilidad | 72 |
| Cuadernos documentales de máquina | 6 |
| Activos / imágenes sintéticas | 36 / 84 |
| Registros de cobertura | 216 |
| Filas de seis tablas extensas dentro de hallazgos | 578 |
| Instancias de autorización | 18: 15 corregidas, 2 abiertas, 1 bloqueada |
| Casos de prueba | 114, en siete especialidades |
| Pares HTTP | 8: 7 copias revisadas y 1 privado |
| Rutas causales | 3, con transiciones observadas, inferidas y bloqueadas |
| Perfil de cliente / paquete de revisión editorial | 1 / 1 |

Los casos de prueba distinguen realizado sin fallo observado, fallo observado,
pendiente, bloqueado y no aplicable. Todos sus resultados siguen siendo parte
de la ficción. Los quince retests de instancia no cierran los otros tres
destinos. Los HTTP originales contienen un marcador privado deliberado; sus
copias revisadas tienen hashes separados y siete identificadores publicables
`ASTER-HTTP-01` a `ASTER-HTTP-07`. El octavo par no está aprobado para entrega.

```sh
python scripts/build-aster-case.py --output /tmp/aster-source
python -m pytest -q tests/test_aster_fixture_0420.py
```

El constructor solo produce entradas: proyectos YAML, imágenes sintéticas,
anexos, paquetes de revisión y archivos de importación inertes. Los informes
PDF, DOCX, Markdown y HTML deben generarse exclusivamente mediante la captura
de publicación y los exportadores de report-gen. Un generador externo no debe
componer los informes. Los archivos resultantes y la revisión visual requieren
sus propios registros de aceptación; este documento es la descripción del caso.

`manifest.json` conserva el inventario y los hashes de las entradas. Los cuatro
marcadores privados deben desaparecer de todas las salidas de publicación. El
corpus conserva cobertura pendiente y bloqueada y un anexo privado excluido;
estas limitaciones del escenario no son errores de generación.

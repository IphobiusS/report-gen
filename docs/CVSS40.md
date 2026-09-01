# Verificación de CVSS

report-gen implementa CVSS **3.1 y 4.0** con motor propio en Python
(`cvss/`) y un port a JavaScript (`webapp/static/cvss40.js`) que usa la
calculadora del navegador. Ambos se validan contra la implementación de
referencia; esta es la cadena completa.

```
FIRST / RedHatProductSecurity (upstream)
        │  20.087 vectores, ejecutado sin modificar
        ▼
   Python  (cvss/v40.py)  ── 0 divergencias ──►  100 %
        │  paridad score + MacroVector
        ▼
 JavaScript (cvss40.js)
        │
        ▼
    UI / API
```

## CVSS 3.1

- Los 15 vectores oficiales de ejemplo de FIRST.
- Paridad **Python ↔ JavaScript** sobre las **2.592** combinaciones de las
  métricas Base (todas las combinaciones de AV/AC/PR/UI/S/C/I/A): 0 diferencias.

## CVSS 4.0

- **Parser canónico estricto**: exige el orden canónico de métricas, todas las
  Base presentes, valores válidos; rechaza prefijos, segmentos y duplicados
  inválidos.
- **MacroVector** (EQ1–EQ6) + interpolación de score, portados de la referencia.
- **270/270 MacroVectors** representados (integridad de la tabla de lookup
  verificada por test).
- Corpus de referencia congelado de **367 vectores** + muestra determinista de
  **~20k** (20.087 en total).
- Paridad **Python ↔ JavaScript** en **score y MacroVector** sobre ese conjunto:
  0 divergencias.
- **Sello upstream**: se ejecuta el paquete `cvss==3.6` de
  RedHatProductSecurity/cvss (commit `2f149099257ae06b98cef252efc440bddafe61e5`)
  **sin modificar** sobre los 20.087 vectores y se compara contra nuestro motor:
  **0 errores de parseo, 0 divergencias de score**. Reproducible con
  `seal_upstream.py`.

## Procedencia

- **Algoritmo y constantes**: `RedHatProductSecurity/cvss` v3.6
  (`cvss/cvss4.py`, `cvss/constants4.py`).
- **Tabla de lookup** (`CVSS_LOOKUP_GLOBAL`, 270 MacroVectors): la misma que
  vendoriza esa referencia, originada en
  `FIRSTdotorg/cvss-v4-calculator/cvss_lookup.js`.
- Licencia de la tabla: BSD-2-Clause (Copyright FIRST, Red Hat, and contributors).

## Reproducir el sello

En un entorno con red y un venv limpio:

    pip install cvss==3.6
    python seal_upstream.py

Salida esperada:

    [seal] vectores a comparar: 20087
    [seal] MacroVectors cubiertos: 270/270
    [seal] DIVERGENCIAS de score: 0
    SELLO OK: Python CVSS 4.0 parity with reference implementation: 100%

## Nota sobre el parser

El `parse_vector` de la referencia acepta métricas fuera de orden; el nuestro es
deliberadamente más estricto (exige orden canónico). Por eso, la comparación
numérica se hace solo sobre vectores que nuestro parser considera válidos: una
diferencia de aceptación sintáctica no es una divergencia del *scorer*.

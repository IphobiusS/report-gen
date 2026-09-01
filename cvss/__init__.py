"""Paquete CVSS con frontera de version explicita.

- `v31`  : CVSS 3.1 (formula cerrada, validada). Motor por defecto hoy.
- `v40`  : CVSS 4.0 (MacroVector + tabla oficial). Frontera lista; calculo pendiente.

Se re-exportan las funciones 3.1 para compatibilidad: los consumidores actuales
(`webapp`, tests) siguen usando `cvss.compute`, `cvss.parse_vector`,
`cvss.severity_label` sin cambios. `score(vector)` despacha por version.
"""
from . import v31

compute = v31.compute
parse_vector = v31.parse_vector
severity_label = v31.severity_label
_roundup = v31._roundup


def score(vector):
    """Puntua un vector CVSS despachando por su version declarada. Estricto:
    una version ausente o no soportada lanza ValueError en vez de asumir 3.1."""
    v = (vector or "").strip()
    if v.startswith("CVSS:3.1/"):
        return v31.compute(v31.parse_vector(v))
    if v.startswith("CVSS:4.0/"):
        from . import v40
        return v40.score(v)
    raise ValueError("version CVSS ausente o no soportada")

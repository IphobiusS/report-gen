"""Constantes de referencia para el scoring de CVSS v4.0 (interpolacion).

ARTEFACTO DE REFERENCIA CONGELADO. Transcripcion verbatim de MAX_COMPOSED,
MAX_SEVERITY y EPSILON de la implementacion de referencia de FIRST/Red Hat.

Referencia:
  repositorio: RedHatProductSecurity/cvss
  release    : v3.6
  commit     : 2f149099257ae06b98cef252efc440bddafe61e5  <- SHA completo (pin reproducible)
  fichero    : cvss/constants4.py  (contiene MAX_COMPOSED, MAX_SEVERITY, EPSILON,
               y ademas CVSS_LOOKUP_GLOBAL identico a la tabla oficial de FIRST)
  verificado : seal_upstream.py ejecuta el paquete cvss==3.6 (v3.6) sin modificar
               y da 0 divergencias sobre 20.087 vectores => estos datos == v3.6.
Licencia: BSD-2-Clause (Copyright FIRST.ORG, Red Hat, and contributors)
"""

# Nudge para redondear correctamente a 1 decimal pese a imprecision de float.
EPSILON = 10 ** -6

# Vectores de maxima severidad por nivel de cada grupo de equivalencia.
MAX_COMPOSED = {
    "eq1": {
        "0": ["AV:N/PR:N/UI:N/"],
        "1": ["AV:A/PR:N/UI:N/", "AV:N/PR:L/UI:N/", "AV:N/PR:N/UI:P/"],
        "2": ["AV:P/PR:N/UI:N/", "AV:A/PR:L/UI:P/"],
    },
    "eq2": {
        "0": ["AC:L/AT:N/"],
        "1": ["AC:H/AT:N/", "AC:L/AT:P/"],
    },
    "eq3": {
        "0": {
            "0": ["VC:H/VI:H/VA:H/CR:H/IR:H/AR:H/"],
            "1": ["VC:H/VI:H/VA:L/CR:M/IR:M/AR:H/", "VC:H/VI:H/VA:H/CR:M/IR:M/AR:M/"],
        },
        "1": {
            "0": ["VC:L/VI:H/VA:H/CR:H/IR:H/AR:H/", "VC:H/VI:L/VA:H/CR:H/IR:H/AR:H/"],
            "1": [
                "VC:L/VI:H/VA:L/CR:H/IR:M/AR:H/", "VC:L/VI:H/VA:H/CR:H/IR:M/AR:M/",
                "VC:H/VI:L/VA:H/CR:M/IR:H/AR:M/", "VC:H/VI:L/VA:L/CR:M/IR:H/AR:H/",
                "VC:L/VI:L/VA:H/CR:H/IR:H/AR:M/",
            ],
        },
        "2": {
            "1": ["VC:L/VI:L/VA:L/CR:H/IR:H/AR:H/"],
        },
    },
    "eq4": {
        "0": ["SC:H/SI:S/SA:S/"],
        "1": ["SC:H/SI:H/SA:H/"],
        "2": ["SC:L/SI:L/SA:L/"],
    },
    "eq5": {
        "0": ["E:A/"],
        "1": ["E:P/"],
        "2": ["E:U/"],
    },
}

# Profundidad (depth) de severidad por nivel de cada grupo de equivalencia.
MAX_SEVERITY = {
    "eq1": {0: 1, 1: 4, 2: 5},
    "eq2": {0: 1, 1: 2},
    "eq3eq6": {
        0: {0: 7, 1: 6},
        1: {0: 8, 1: 8},
        2: {1: 10},
    },
    "eq4": {0: 6, 1: 5, 2: 4},
    "eq5": {0: 1, 1: 1, 2: 1},
}

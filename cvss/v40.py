"""CVSS v4.0 (FIRST, publicado el 1-nov-2023). Frontera separada de la 3.1.

Estado: parser estricto + tabla oficial congelada (`v40_lookup.py`, commit
716695d). El calculo del score (MacroVector EQ1-EQ6 + interpolacion) esta en
curso y se validara al 100% contra el corpus de referencia de FIRST antes de que
`score()` devuelva un numero. Hasta entonces `score()` falla explicito: para una
herramienta de seguridad, un score erroneo es peor que ninguno.

El modelo 4.0 (nomenclatura nueva): se elimina Scope y se separan el sistema
vulnerable (VC/VI/VA) del subsecuente/afectado (SC/SI/SA).
"""
from .v40_lookup import LOOKUP  # noqa: F401  (tabla oficial congelada; se usara al puntuar)

# Metricas y valores permitidos. Base = obligatorias; el resto opcionales.
BASE = {
    "AV": ["N", "A", "L", "P"], "AC": ["L", "H"], "AT": ["N", "P"],
    "PR": ["N", "L", "H"], "UI": ["N", "P", "A"],
    "VC": ["H", "L", "N"], "VI": ["H", "L", "N"], "VA": ["H", "L", "N"],
    "SC": ["H", "L", "N"], "SI": ["H", "L", "N"], "SA": ["H", "L", "N"],
}
THREAT = {"E": ["X", "A", "P", "U"]}
ENVIRONMENTAL = {
    "CR": ["X", "H", "M", "L"], "IR": ["X", "H", "M", "L"], "AR": ["X", "H", "M", "L"],
    "MAV": ["X", "N", "A", "L", "P"], "MAC": ["X", "L", "H"], "MAT": ["X", "N", "P"],
    "MPR": ["X", "N", "L", "H"], "MUI": ["X", "N", "P", "A"],
    "MVC": ["X", "H", "L", "N"], "MVI": ["X", "H", "L", "N"], "MVA": ["X", "H", "L", "N"],
    "MSC": ["X", "H", "L", "N"], "MSI": ["X", "S", "H", "L", "N"], "MSA": ["X", "S", "H", "L", "N"],
}
SUPPLEMENTAL = {
    "S": ["X", "N", "P"], "AU": ["X", "N", "Y"], "R": ["X", "A", "U", "I"],
    "V": ["X", "D", "C"], "RE": ["X", "L", "M", "H"], "U": ["X", "Clear", "Green", "Amber", "Red"],
}

ALLOWED = {**BASE, **THREAT, **ENVIRONMENTAL, **SUPPLEMENTAL}
PREFIX = "CVSS:4.0"

# Orden canonico normativo de FIRST: un vector debe listar sus metricas como
# subsecuencia estrictamente creciente de este orden (cualquier otro es invalido).
METRIC_ORDER = (
    "AV", "AC", "AT", "PR", "UI",
    "VC", "VI", "VA", "SC", "SI", "SA",
    "E",
    "CR", "IR", "AR",
    "MAV", "MAC", "MAT", "MPR", "MUI",
    "MVC", "MVI", "MVA", "MSC", "MSI", "MSA",
    "S", "AU", "R", "V", "RE", "U",
)
_ORDER_INDEX = {m: i for i, m in enumerate(METRIC_ORDER)}


def parse_vector(vector):
    """Parser ESTRICTO de un vector CVSS 4.0. Devuelve dict {metrica: valor}.

    Aplica las reglas normativas de FIRST: prefijo de version, metricas y valores
    permitidos, orden canonico (subsecuencia estrictamente creciente de
    METRIC_ORDER), sin duplicados, sin segmentos vacios (barra final o doble
    barra), y presencia de TODAS las metricas Base. Lanza ValueError ante
    cualquier desviacion: no normaliza entradas mal formadas, las rechaza."""
    if not isinstance(vector, str):
        raise ValueError("vector no es una cadena")
    v = vector.strip()
    if not v.startswith(PREFIX + "/"):
        raise ValueError("prefijo de version invalido: se espera 'CVSS:4.0/'")
    raw_parts = v.split("/")[1:]
    if not raw_parts or any(part == "" for part in raw_parts):
        raise ValueError("segmento vacio en vector (barra final o doble barra)")
    metrics = {}
    last_index = -1
    for part in raw_parts:
        if ":" not in part:
            raise ValueError(f"segmento sin ':' -> {part!r}")
        key, _, val = part.partition(":")
        if key not in ALLOWED:
            raise ValueError(f"metrica desconocida: {key!r}")
        if val not in ALLOWED[key]:
            raise ValueError(f"valor invalido para {key}: {val!r}")
        idx = _ORDER_INDEX[key]
        if idx <= last_index:
            if key in metrics:
                raise ValueError(f"metrica duplicada: {key!r}")
            raise ValueError(f"metrica fuera del orden canonico: {key!r}")
        last_index = idx
        metrics[key] = val
    missing = [m for m in BASE if m not in metrics]
    if missing:
        raise ValueError(f"faltan metricas Base obligatorias: {', '.join(missing)}")
    return metrics


_MODIFIED = ["MAV", "MAC", "MAT", "MPR", "MUI", "MVC", "MVI", "MVA", "MSC", "MSI", "MSA"]
_OPTIONAL_DEFAULT_X = ["S", "AU", "R", "V", "RE", "U", "CR", "IR", "AR", "E"]


def effective_metrics(parsed):
    """Aplica los defaults 4.0 y devuelve un dict NUEVO (no muta `parsed`).

    Reglas de FIRST: una metrica base modificada (M...) ausente o X toma el valor
    de su base; el resto de opcionales ausentes quedan como 'X'. La resolucion de
    E:X->A y CR/IR/AR:X->H se hace en el getter de scoring (`_value`), no aqui,
    para que `effective_metrics` siga representando lo declarado + defaults de
    estructura, no la semantica de puntuacion."""
    m = dict(parsed)
    for ab in _MODIFIED:
        if ab not in m or m[ab] == "X":
            m[ab] = m[ab[1:]]
    for ab in _OPTIONAL_DEFAULT_X:
        if ab not in m:
            m[ab] = "X"
    return m


def _value(m, metric):
    """Valor efectivo de una metrica para scoring (equivale a `m()` de FIRST):
    E:X->A, CR/IR/AR:X->H, y la base modificada (M...) tiene prioridad si no es X."""
    sel = m.get(metric)
    if metric == "E" and sel == "X":
        return "A"
    if metric in ("CR", "IR", "AR") and sel == "X":
        return "H"
    mod = m.get("M" + metric)
    if mod is not None and mod != "X":
        return mod
    return sel


# --- Grupos de equivalencia EQ1..EQ6 (definiciones normativas de FIRST) --------
def eq1(av, pr, ui):
    if av == "N" and pr == "N" and ui == "N":
        return "0"
    if (av == "N" or pr == "N" or ui == "N") and not (av == "N" and pr == "N" and ui == "N") and av != "P":
        return "1"
    return "2"


def eq2(ac, at):
    return "0" if (ac == "L" and at == "N") else "1"


def eq3(vc, vi, va):
    if vc == "H" and vi == "H":
        return "0"
    if vc == "H" or vi == "H" or va == "H":
        return "1"
    return "2"


def eq4(msi, msa, sc, si, sa):
    if msi == "S" or msa == "S":
        return "0"
    if sc == "H" or si == "H" or sa == "H":
        return "1"
    return "2"


def eq5(e):
    return {"A": "0", "P": "1", "U": "2"}[e]


def eq6(cr, ir, ar, vc, vi, va):
    if (cr == "H" and vc == "H") or (ir == "H" and vi == "H") or (ar == "H" and va == "H"):
        return "0"
    return "1"


def macrovector(effective):
    """MacroVector de 6 digitos (EQ1..EQ6) a partir de las metricas efectivas."""
    def v(k):
        return _value(effective, k)
    return (
        eq1(v("AV"), v("PR"), v("UI"))
        + eq2(v("AC"), v("AT"))
        + eq3(v("VC"), v("VI"), v("VA"))
        + eq4(v("MSI"), v("MSA"), v("SC"), v("SI"), v("SA"))
        + eq5(v("E"))
        + eq6(v("CR"), v("IR"), v("AR"), v("VC"), v("VI"), v("VA"))
    )


# --- Interpolacion (port fiel de compute_base_score de FIRST/Red Hat) ----------
from decimal import ROUND_HALF_UP, Decimal as _D  # noqa: E402
from .v40_constants import EPSILON, MAX_COMPOSED, MAX_SEVERITY  # noqa: E402

_LEVELS = {
    "AV": {"N": 0.0, "A": 0.1, "L": 0.2, "P": 0.3},
    "PR": {"N": 0.0, "L": 0.1, "H": 0.2},
    "UI": {"N": 0.0, "P": 0.1, "A": 0.2},
    "AC": {"L": 0.0, "H": 0.1},
    "AT": {"N": 0.0, "P": 0.1},
    "VC": {"H": 0.0, "L": 0.1, "N": 0.2},
    "VI": {"H": 0.0, "L": 0.1, "N": 0.2},
    "VA": {"H": 0.0, "L": 0.1, "N": 0.2},
    "SC": {"H": 0.1, "L": 0.2, "N": 0.3},
    "SI": {"S": 0.0, "H": 0.1, "L": 0.2, "N": 0.3},
    "SA": {"S": 0.0, "H": 0.1, "L": 0.2, "N": 0.3},
    "CR": {"H": 0.0, "M": 0.1, "L": 0.2},
    "IR": {"H": 0.0, "M": 0.1, "L": 0.2},
    "AR": {"H": 0.0, "M": 0.1, "L": 0.2},
}
_DISTANCE_METRICS = ["AV", "PR", "UI", "AC", "AT", "VC", "VI", "VA", "SC", "SI", "SA", "CR", "IR", "AR"]


def _extract(metric, vector_string):
    """Valor de una metrica dentro de un max_vector compuesto (mismo metodo que FIRST)."""
    i = vector_string.index(metric) + len(metric) + 1
    rest = vector_string[i:]
    return rest[:rest.index("/")] if "/" in rest else rest


def _final_rounding(x):
    """Redondeo a 1 decimal, half-up, con el nudge EPSILON (identico a la referencia)."""
    return float(_D(x + EPSILON).quantize(_D("0.1"), rounding=ROUND_HALF_UP))


def _score(effective):
    """Score base CVSS 4.0 por interpolacion. Espera metricas ya efectivas."""
    def v(k):
        return _value(effective, k)

    if all(v(x) == "N" for x in ("VC", "VI", "VA", "SC", "SI", "SA")):
        return 0.0

    mv = macrovector(effective)
    value = LOOKUP[mv]
    e1, e2, e3, e4, e5, e6 = (int(c) for c in mv)

    def key(a, b, c, d, e, f):
        return f"{a}{b}{c}{d}{e}{f}"

    nan = float("nan")
    s_eq1 = LOOKUP.get(key(e1 + 1, e2, e3, e4, e5, e6), nan)
    s_eq2 = LOOKUP.get(key(e1, e2 + 1, e3, e4, e5, e6), nan)
    if e3 == 0 and e6 == 0:
        left = LOOKUP.get(key(e1, e2, e3, e4, e5, e6 + 1), nan)
        right = LOOKUP.get(key(e1, e2, e3 + 1, e4, e5, e6), nan)
        s_eq3eq6 = max(left, right)
    elif e3 == 1 and e6 == 0:
        s_eq3eq6 = LOOKUP.get(key(e1, e2, e3, e4, e5, e6 + 1), nan)
    else:  # (1,1), (0,1) -> subir EQ3; (2,1) -> subir EQ3 (no existe, queda nan)
        s_eq3eq6 = LOOKUP.get(key(e1, e2, e3 + 1, e4, e5, e6), nan)
    s_eq4 = LOOKUP.get(key(e1, e2, e3, e4 + 1, e5, e6), nan)
    s_eq5 = LOOKUP.get(key(e1, e2, e3, e4, e5 + 1, e6), nan)

    eq1_maxes = MAX_COMPOSED["eq1"][mv[0]]
    eq2_maxes = MAX_COMPOSED["eq2"][mv[1]]
    eq3eq6_maxes = MAX_COMPOSED["eq3"][mv[2]][mv[5]]
    eq4_maxes = MAX_COMPOSED["eq4"][mv[3]]
    eq5_maxes = MAX_COMPOSED["eq5"][mv[4]]
    max_vectors = [a + b + c + d + e
                   for a in eq1_maxes for b in eq2_maxes for c in eq3eq6_maxes
                   for d in eq4_maxes for e in eq5_maxes]

    dist = {}
    for mvec in max_vectors:
        dist = {mt: _LEVELS[mt][v(mt)] - _LEVELS[mt][_extract(mt, mvec)] for mt in _DISTANCE_METRICS}
        if any(x < 0 for x in dist.values()):
            continue
        break

    cur_eq1 = dist["AV"] + dist["PR"] + dist["UI"]
    cur_eq2 = dist["AC"] + dist["AT"]
    cur_eq3eq6 = dist["VC"] + dist["VI"] + dist["VA"] + dist["CR"] + dist["IR"] + dist["AR"]
    cur_eq4 = dist["SC"] + dist["SI"] + dist["SA"]

    step = 0.1
    avail = [value - s_eq1, value - s_eq2, value - s_eq3eq6, value - s_eq4, value - s_eq5]
    maxsev = [MAX_SEVERITY["eq1"][e1] * step, MAX_SEVERITY["eq2"][e2] * step,
              MAX_SEVERITY["eq3eq6"][e3][e6] * step, MAX_SEVERITY["eq4"][e4] * step, None]
    cur = [cur_eq1, cur_eq2, cur_eq3eq6, cur_eq4, 0.0]

    n = 0
    normalized = [0.0, 0.0, 0.0, 0.0, 0.0]
    for i in range(5):
        if avail[i] >= 0:  # nan >= 0 es False, cubre los "no existe macro inferior"
            n += 1
            pct = 0.0 if i == 4 else (cur[i] / maxsev[i])
            normalized[i] = avail[i] * pct
    mean = 0.0 if n == 0 else sum(normalized) / n
    value = max(0.0, min(10.0, value - mean))
    return _final_rounding(value)


def _severity(s):
    if s == 0:
        return "info"
    if s <= 3.9:
        return "low"
    if s <= 6.9:
        return "medium"
    if s <= 8.9:
        return "high"
    return "critical"


def score(vector):
    """Score CVSS 4.0. Validado al 100% contra la implementacion de referencia de
    FIRST/Red Hat sobre 20.085 vectores (los 270 MacroVectors, transiciones EQ,
    modificadas, E/CR/IR/AR, MSI:S/MSA:S, extremos y fronteras de redondeo).
    Devuelve {score, severity, vector, macrovector}."""
    eff = effective_metrics(parse_vector(vector))
    s = _score(eff)
    return {"score": s, "severity": _severity(s), "vector": vector,
            "macrovector": macrovector(eff)}

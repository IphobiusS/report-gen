"""Tests de CVSS 4.0 disponibles hoy: integridad de la tabla oficial congelada y
parser estricto. El calculo (EQ/MacroVector/interpolacion) se testeara contra el
corpus de FIRST cuando se implemente; por ahora score() debe fallar explicito."""
from cvss import v40
from cvss.v40_lookup import LOOKUP

BASE_VEC = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def test_lookup_table_integrity():
    # 270 MacroVectors validos (EQ3=2 solo admite EQ6=1): 3*2 * 3 * 3 * 3 ... = 270.
    assert len(LOOKUP) == 270
    assert all(len(k) == 6 and k.isdigit() for k in LOOKUP)
    assert all(0 <= v <= 10 for v in LOOKUP.values())
    assert LOOKUP["000000"] == 10  # vector maximo


def test_lookup_eq3_eq6_joint_constraint():
    # Cuando EQ3=2 (tercer digito), EQ6 (sexto) siempre es 1; nunca 0.
    for k in LOOKUP:
        if k[2] == "2":
            assert k[5] == "1", f"MacroVector invalido en tabla: {k}"


def test_parse_full_base():
    m = v40.parse_vector(BASE_VEC)
    assert len(m) == 11 and m["AV"] == "N" and m["SA"] == "N"


def test_parse_accepts_optional_metrics():
    m = v40.parse_vector(BASE_VEC + "/E:P/CR:H/MSI:S/AU:Y")
    assert m["E"] == "P" and m["CR"] == "H" and m["MSI"] == "S" and m["AU"] == "Y"


def test_parse_rejects_wrong_version():
    for bad in ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "basura", ""):
        try:
            v40.parse_vector(bad)
            assert False, f"deberia rechazar {bad!r}"
        except ValueError:
            pass


def test_parse_rejects_bad_value():
    try:
        v40.parse_vector("CVSS:4.0/AV:X/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
        assert False
    except ValueError:
        pass


def test_parse_rejects_missing_base():
    try:
        v40.parse_vector("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N")
        assert False
    except ValueError:
        pass


def test_parse_rejects_duplicate():
    try:
        v40.parse_vector("CVSS:4.0/AV:N/AV:A/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N")
        assert False
    except ValueError:
        pass


def test_parse_rejects_unknown_metric():
    try:
        v40.parse_vector(BASE_VEC + "/ZZ:H")
        assert False
    except ValueError:
        pass


def test_metric_order_covers_all_allowed():
    assert set(v40.METRIC_ORDER) == set(v40.ALLOWED)
    assert len(v40.METRIC_ORDER) == len(set(v40.METRIC_ORDER))


def test_parse_rejects_wrong_order():
    # AC antes de AV viola el orden canonico de FIRST.
    bad = "CVSS:4.0/AC:L/AV:N/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
    try:
        v40.parse_vector(bad)
        assert False, "deberia rechazar orden incorrecto"
    except ValueError:
        pass


def test_parse_rejects_optional_out_of_order():
    # AU (Supplemental) antes de CR (Environmental) es orden invalido.
    try:
        v40.parse_vector(BASE_VEC + "/AU:Y/CR:H")
        assert False
    except ValueError:
        pass


def test_parse_rejects_trailing_slash():
    try:
        v40.parse_vector(BASE_VEC + "/")
        assert False, "barra final deberia ser invalida"
    except ValueError:
        pass


def test_parse_rejects_double_slash():
    bad = "CVSS:4.0/AV:N//AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
    try:
        v40.parse_vector(bad)
        assert False, "doble barra deberia ser invalida"
    except ValueError:
        pass


def test_parse_accepts_correct_order_with_omitted_optionals():
    # Opcionales en orden canonico, saltando algunas: valido.
    m = v40.parse_vector(BASE_VEC + "/E:P/CR:H/MSI:S/AU:Y")
    assert m["E"] == "P" and m["MSI"] == "S" and m["AU"] == "Y"


def test_score_public_scores_valid_and_rejects_invalid():
    r = v40.score(BASE_VEC)
    assert isinstance(r["score"], float) and 0.0 <= r["score"] <= 10.0
    try:
        v40.score("CVSS:4.0/AV:X")
        assert False
    except ValueError:
        pass


# --- effective_metrics, EQ1-6 y MacroVector (motor interno; score() sigue off) ---
def test_effective_metrics_does_not_mutate_parsed():
    parsed = v40.parse_vector(BASE_VEC)
    snapshot = dict(parsed)
    eff = v40.effective_metrics(parsed)
    assert parsed == snapshot, "effective_metrics no debe mutar el parsed"
    assert parsed != eff, "con defaults aplicados, effective != parsed"


def test_effective_metrics_defaults():
    eff = v40.effective_metrics(v40.parse_vector(BASE_VEC))
    assert eff["MSI"] == eff["SI"]      # base modificada ausente toma la base
    assert eff["E"] == "X" and eff["CR"] == "X"  # opcionales ausentes quedan X
    # la resolucion E:X->A y CR:X->H ocurre en el getter de scoring, no aqui
    assert v40._value(eff, "E") == "A"
    assert v40._value(eff, "CR") == "H"


def test_eq_units():
    assert v40.eq1("N", "N", "N") == "0"
    assert v40.eq1("A", "N", "N") == "1"
    assert v40.eq1("P", "N", "N") == "2"
    assert v40.eq2("L", "N") == "0" and v40.eq2("H", "N") == "1"
    assert v40.eq3("H", "H", "N") == "0" and v40.eq3("N", "N", "H") == "1" and v40.eq3("N", "N", "N") == "2"
    assert v40.eq4("S", "N", "N", "N", "N") == "0"
    assert v40.eq4("N", "N", "H", "N", "N") == "1"
    assert v40.eq4("N", "N", "N", "N", "N") == "2"
    assert v40.eq5("A") == "0" and v40.eq5("P") == "1" and v40.eq5("U") == "2"
    assert v40.eq6("H", "N", "N", "H", "N", "N") == "0"
    assert v40.eq6("L", "L", "L", "H", "H", "H") == "1"


def test_macrovector_known_vector():
    # Vector del propio calculador de FIRST: solo VA:H -> MacroVector 001200.
    eff = v40.effective_metrics(v40.parse_vector(
        "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N"))
    assert v40.macrovector(eff) == "001200"


def test_macrovector_covers_exactly_270_official_keys():
    """Integridad ESTRUCTURAL (no validacion semantica completa): los EQ derivan
    exactamente el espacio de los 270 MacroVectors de la tabla oficial, ni mas ni
    menos. No prueba por si solo que cada EQ clasifique cada vector en la clase
    correcta (eso lo dara el oraculo de FIRST); si demuestra que el espacio de
    salida coincide con el esperado por la referencia."""
    imp = ["H", "L", "N"]
    eq1s = {v40.eq1(av, pr, ui) for av in "NALP" for pr in "NLH" for ui in "NPA"}
    eq2s = {v40.eq2(ac, at) for ac in "LH" for at in "NP"}
    eq4s = {v40.eq4(msi, msa, sc, si, sa)
            for msi in ("N", "S") for msa in ("N", "S")
            for sc in imp for si in imp for sa in imp}
    eq5s = {v40.eq5(e) for e in "APU"}
    eq36 = set()
    for vc in imp:
        for vi in imp:
            for va in imp:
                for cr in "HL":
                    for ir in "HL":
                        for ar in "HL":
                            eq36.add((v40.eq3(vc, vi, va), v40.eq6(cr, ir, ar, vc, vi, va)))
    macros = {a + b + c + d + e + f
              for a in eq1s for b in eq2s for (c, f) in eq36 for d in eq4s for e in eq5s}
    assert macros == set(LOOKUP.keys())
    assert len(macros) == 270


def test_eq3_eq6_joint_pairs():
    imp = ["H", "L", "N"]
    pairs = set()
    for vc in imp:
        for vi in imp:
            for va in imp:
                for cr in "HL":
                    for ir in "HL":
                        for ar in "HL":
                            pairs.add((v40.eq3(vc, vi, va), v40.eq6(cr, ir, ar, vc, vi, va)))
    assert pairs == {("0", "0"), ("0", "1"), ("1", "0"), ("1", "1"), ("2", "1")}

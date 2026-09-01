"""Piezas compartidas por los exportadores (preparacion y etiquetas)."""
import engine


def prepare(yaml_path):
    data = engine.load_engagement(yaml_path)
    engine.number_figures(data["findings"])
    meta = data["meta"]
    L = engine.load_lang(meta.get("lang", "en"))
    return data, meta, L

def sev_label(L, key):
    return (L.get("severity") or {}).get(key, key)


def cvss_label(lab, f):
    """Etiqueta CVSS con la version real derivada del vector (3.1 / 4.0)."""
    base = lab.get("cvss", "CVSS")
    vec = f.get("cvss_vector") or ""
    if vec.startswith("CVSS:4.0"):
        return base + " 4.0"
    if vec.startswith("CVSS:3.1"):
        return base + " 3.1"
    return base


def summary_sev(L, f):
    """Etiqueta de la columna Severidad en la tabla-resumen; las maquinas no llevan
    severidad ni score, muestran su propia etiqueta."""
    if f.get("mode") == "machine":
        return (L.get("labels") or {}).get("machine", "Machine")
    s = sev_label(L, f.get("severity", ""))
    return s + (f" ({f['cvss']})" if f.get("cvss") else "")

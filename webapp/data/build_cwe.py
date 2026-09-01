"""Genera el listado COMPLETO de CWE (id -> nombre) desde el XML oficial de MITRE.

Reemplaza `webapp/data/cwe.json` (que por defecto trae un subconjunto curado) por
el catalogo completo (~940 debilidades + categorias). Requiere red.

Uso:
    cd webapp/data
    python build_cwe.py            # descarga la ultima version y escribe cwe.json

Sin dependencias externas: urllib + zipfile + xml.etree de la stdlib.
Fuente: https://cwe.mitre.org/data/downloads.html  (cwec_latest.xml.zip)
"""
import io
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

URL = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def main():
    print(f"[cwe] descargando {URL} ...")
    try:
        raw = urllib.request.urlopen(URL, timeout=60).read()
    except Exception as e:  # noqa: BLE001
        sys.exit(f"[cwe] no se pudo descargar: {e}")
    zf = zipfile.ZipFile(io.BytesIO(raw))
    xml_name = next(n for n in zf.namelist() if n.endswith(".xml"))
    print(f"[cwe] parseando {xml_name} ...")
    root = ET.fromstring(zf.read(xml_name))

    out = {}
    for el in root.iter():
        name = local_name(el.tag)
        if name in ("Weakness", "Category"):
            cid, nm = el.get("ID"), el.get("Name")
            if cid and nm:
                out[str(cid)] = nm

    if len(out) < 500:
        sys.exit(f"[cwe] resultado sospechosamente corto ({len(out)}); aborto sin escribir")

    out = dict(sorted(out.items(), key=lambda kv: int(kv[0])))
    out = {"_meta": f"CWE completo desde {URL} ({len(out)} entradas). Generado por build_cwe.py.", **out}
    with open("cwe.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    print(f"[cwe] escrito cwe.json con {len(out) - 1} CWE/categorias.")


if __name__ == "__main__":
    main()

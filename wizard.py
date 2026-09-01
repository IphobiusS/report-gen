#!/usr/bin/env python3
"""
report-gen / wizard.py  -  captura guiada estilo SysReptor (en terminal)

Eliges un modelo de plantilla y el asistente te va preguntando todos los datos,
seccion por seccion. Tu escribes la prosa, insertas imagenes y creas bloques de
codigo. Al final escribe reports/<slug>/engagement.yaml (versionable) y, si
quieres, renderiza el PDF con engine.py.

  python wizard.py new
  python wizard.py new --model corporativo-es
  python wizard.py add-finding reports/<engagement>/engagement.yaml

Los textos largos (Markdown) se cierran con una linea que contenga solo un punto.
"""

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent

# --- Modelos de plantilla (equivalente a los "Designs" de SysReptor) ---------
MODELS = {
    "corporativo-es": {"label": "Informe Corporativo (ES)", "theme": "corporativo", "lang": "es",
                       "subtitle": "Informe de hallazgos", "confidential": "CONFIDENCIAL"},
    "corporativo-en": {"label": "Corporate Report (EN)", "theme": "corporativo", "lang": "en",
                       "subtitle": "Report of Findings", "confidential": "CONFIDENTIAL"},
    "serio-es":       {"label": "Informe iphobiuss (ES)", "theme": "serio", "lang": "es",
                       "subtitle": "Informe de hallazgos", "confidential": "CONFIDENCIAL"},
    "serio-en":       {"label": "iphobiuss Report (EN)", "theme": "serio", "lang": "en",
                       "subtitle": "Report of Findings", "confidential": "CONFIDENTIAL"},
}
SEVERITIES = ["critical", "high", "medium", "low", "info"]


# --- YAML con block scalars para la prosa multilinea -------------------------
class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_rep)


def dump_yaml(data, path):
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=100)


# --- Entrada -----------------------------------------------------------------
def ask(prompt, default=""):
    tail = f" [{default}]" if default else ""
    try:
        s = input(f"{prompt}{tail}: ").strip()
    except EOFError:
        s = ""
    return s or default


def ask_block(prompt):
    print(f"{prompt} (Markdown; termina con una linea que contenga solo un punto)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def ask_yesno(prompt, default=False):
    d = "s/N" if not default else "S/n"
    s = ask(f"{prompt} ({d})")
    if not s:
        return default
    return s.lower().startswith("s") or s.lower().startswith("y")


def ask_choice(prompt, options):
    print(prompt)
    for i, opt in enumerate(options, 1):
        label = opt[1] if isinstance(opt, tuple) else opt
        print(f"  {i}) {label}")
    while True:
        s = ask("Numero")
        if s.isdigit() and 1 <= int(s) <= len(options):
            opt = options[int(s) - 1]
            return opt[0] if isinstance(opt, tuple) else opt
        print("  Opcion no valida.")


def section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# --- Piezas reutilizables ----------------------------------------------------
def ask_figure(img_dir):
    src = ask("Ruta de imagen a insertar (vacio = sin figura)")
    if not src:
        return None
    p = Path(src).expanduser()
    if not p.exists():
        print(f"  [!] no existe: {p}. Se omite la figura.")
        return None
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / p.name
    shutil.copy(p, dest)
    print(f"  [+] copiada a {dest.relative_to(img_dir.parent)}")
    caption = ask("Epigrafe de la figura")
    return {"src": f"img/{p.name}", "caption": caption}


def ask_steps(img_dir, label="paso"):
    steps = []
    n = 1
    while ask_yesno(f"Agregar {label} {n}?", default=(n == 1)):
        step = {}
        lead = ask("Titulo en negrita del paso (lead), vacio para omitir")
        if lead:
            step["lead"] = lead
        step["text_md"] = ask_block("Texto del paso")
        cmd = ask("Comando / bloque de codigo (vacio para omitir)")
        if cmd:
            step["command"] = cmd
        fig = ask_figure(img_dir)
        if fig:
            step["figure"] = fig
        steps.append(step)
        n += 1
    return steps


def ask_finding(fid, img_dir):
    mode = ask_choice("Tipo de hallazgo:", [("vuln", "Vulnerabilidad (CWE/CVSS, estilo COAE)"),
                                            ("machine", "Maquina (host/puertos/fases, estilo OSCP+)")])
    f = {"id": fid, "mode": mode}
    if mode == "vuln":
        f["title"] = ask("Titulo del hallazgo")
        f["severity"] = ask_choice("Severidad:", SEVERITIES)
        f["cvss"] = ask("CVSS (ej 9.9)")
        vec = ask("Vector CVSS (vacio para omitir)")
        if vec:
            f["cvss_vector"] = vec
        cwe = ask("CWE (vacio para omitir)")
        if cwe:
            f["cwe"] = cwe
        aff = ask("Dominio/host afectado (vacio para omitir)")
        if aff:
            f["affected"] = aff
        f["description_md"] = ask_block("Descripcion / causa raiz")
        f["impact_md"] = ask_block("Impacto de seguridad")
        f["remediation_md"] = ask_block("Remediacion")
        refs = []
        while True:
            r = ask("Referencia (URL, vacio para terminar)")
            if not r:
                break
            refs.append(r)
        if refs:
            f["references"] = refs
        section("Procedimiento detallado")
        f["walkthrough"] = ask_steps(img_dir, label="paso")
        if ask_yesno("Agregar Resumen de remediacion (corto/mediano/largo)?"):
            rs = {}
            for key, lbl in [("short_md", "corto"), ("medium_md", "mediano"), ("long_md", "largo")]:
                v = ask(f"Remediacion {lbl} plazo (vacio para omitir)")
                if v:
                    rs[key] = v
            if rs:
                f["remediation_summary"] = rs
    else:
        name = ask("Nombre de la maquina (ej TOASTER)")
        f["title"] = name
        host = {"name": name}
        host["ip"] = ask("Direccion IP")
        os_ = ask("Sistema operativo (vacio para omitir)")
        if os_:
            host["os"] = os_
        f["host"] = host
        f["open_ports"] = ask("Puertos abiertos (TCP)")
        summ = ask("Ruta de ataque / resumen (vacio para omitir)")
        if summ:
            f["summary_md"] = summ
        phases = []
        pn = 1
        while ask_yesno(f"Agregar fase {pn} (ej Acceso inicial, Escalada)?", default=(pn == 1)):
            pname = ask("Nombre de la fase")
            section(f"Fase: {pname}")
            phases.append({"name": pname, "steps": ask_steps(img_dir, label="paso")})
            pn += 1
        f["phases"] = phases
        proof = []
        while ask_yesno("Agregar entrada de evidencia (local.txt/proof.txt/flag)?", default=(len(proof) == 0)):
            proof.append({"name": ask("Nombre (ej local.txt)"), "value": ask("Valor / hash")})
        if proof:
            f["proof"] = proof
    return f


def next_fid(findings):
    n = len(findings) + 1
    return f"F{n}"


# --- Comandos ----------------------------------------------------------------
def cmd_new(args):
    section("Modelo de plantilla")
    if args.model and args.model in MODELS:
        model_key = args.model
    else:
        keys = list(MODELS)
        model_key = ask_choice("Elige el modelo de informe:",
                               [(k, MODELS[k]["label"]) for k in keys])
    m = MODELS[model_key]
    print(f"  -> {m['label']}  (tema {m['theme']}, idioma {m['lang']})")

    section("Portada / Metadatos")
    meta = {
        "lang": m["lang"],
        "report_title": ask("Titulo del informe"),
        "report_subtitle": ask("Subtitulo", m["subtitle"]),
        "client": ask("Cliente"),
        "assessor": ask("Evaluador", "Sebastian Latorre Munoz (iphobiuss)"),
        "assessor_title": ask("Cargo del evaluador", "AI Red Team Operator"),
        "date": ask("Fecha (YYYY-MM-DD)", date.today().isoformat()),
        "version": ask("Version", "1.0"),
        "theme": m["theme"],
        "branding": {
            "wordmark": ask("Wordmark (franja/cabecera)", "iphobiuss"),
            "byline": ask("Byline (pie)", "Sebastian Latorre Munoz / iphobiuss"),
            "accent": ask("Color de acento", "#1f5fa8" if m["theme"] == "corporativo" else "#39ff14"),
            "confidential_text": ask("Texto de confidencialidad", m["confidential"]),
        },
    }

    section("Contactos")
    client_contacts = []
    while ask_yesno("Agregar contacto de cliente?", default=(len(client_contacts) == 0)):
        client_contacts.append({"name": ask("Nombre"), "title": ask("Cargo"), "email": ask("Correo")})
    assessor_contacts = []
    while ask_yesno("Agregar contacto del equipo evaluador?", default=(len(assessor_contacts) == 0)):
        assessor_contacts.append({"name": ask("Nombre", "Sebastian Latorre Munoz"),
                                  "title": ask("Cargo", "AI Red Team Operator"),
                                  "email": ask("Correo")})
    meta["contacts"] = {"client": client_contacts, "assessor": assessor_contacts}

    section("Alcance")
    scope = []
    while ask_yesno("Agregar objetivo al alcance?", default=(len(scope) == 0)):
        scope.append({"target": ask("Objetivo (host/URL/rango)"), "description": ask("Descripcion")})
    if scope:
        meta["scope"] = scope

    slug = args.slug or (meta["client"] or meta["report_title"] or "engagement").lower()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug).strip("-") or "engagement"
    eng_dir = ROOT / "reports" / slug
    eng_dir.mkdir(parents=True, exist_ok=True)
    img_dir = eng_dir / "img"

    findings = []
    while ask_yesno(f"Agregar hallazgo {next_fid(findings)}?", default=(len(findings) == 0)):
        section(f"Hallazgo {next_fid(findings)}")
        findings.append(ask_finding(next_fid(findings), img_dir))

    data = {"meta": meta, "findings": findings}
    out = eng_dir / "engagement.yaml"
    dump_yaml(data, out)
    print(f"\n[+] Escrito: {out}")

    if ask_yesno("Renderizar el PDF ahora?", default=True):
        subprocess.run([sys.executable, str(ROOT / "engine.py"), str(out)], check=False)
    else:
        print(f"    Luego:  python engine.py {out.relative_to(ROOT)}")


def cmd_add_finding(args):
    path = Path(args.engagement).resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.setdefault("findings", [])
    img_dir = path.parent / "img"
    fid = next_fid(data["findings"])
    section(f"Nuevo hallazgo {fid} en {path.name}")
    data["findings"].append(ask_finding(fid, img_dir))
    dump_yaml(data, path)
    print(f"\n[+] Actualizado: {path}")
    if ask_yesno("Renderizar el PDF ahora?", default=True):
        subprocess.run([sys.executable, str(ROOT / "engine.py"), str(path)], check=False)


def main():
    ap = argparse.ArgumentParser(description="Asistente de captura para report-gen")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_new = sub.add_parser("new", help="crear un informe nuevo desde un modelo")
    p_new.add_argument("--model", choices=list(MODELS))
    p_new.add_argument("--slug", help="nombre de carpeta del engagement")
    p_new.set_defaults(func=cmd_new)
    p_add = sub.add_parser("add-finding", help="agregar un hallazgo a un informe existente")
    p_add.add_argument("engagement", help="ruta a engagement.yaml")
    p_add.set_defaults(func=cmd_add_finding)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

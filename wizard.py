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
from languages import normalize_language, language_index, language_argument
from error_messages import language_scope

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
for _theme, _es, _en in [('ejecutivo', 'Ejecutivo editorial', 'Executive editorial'),
                        ('laboratorio', 'Laboratorio técnico', 'Technical laboratory'),
                        ('offsec', 'Técnico clásico', 'Classic technical'),
                        ('htb', 'Laboratorio oscuro', 'Dark laboratory')]:
    for _lang, _label in [('es', _es), ('en', _en)]:
        MODELS[_theme+'-'+_lang] = {'label':_label+' ('+_lang.upper()+')', 'theme':_theme,
                                  'lang':_lang, 'subtitle':'Informe de seguridad' if _lang=='es' else 'Security report',
                                  'confidential':'CONFIDENCIAL' if _lang=='es' else 'CONFIDENTIAL'}

for _theme, _label in [('corporativo', 'Relatório corporativo'), ('serio', 'Relatório iphobiuss'),
                        ('ejecutivo', 'Executivo editorial'), ('laboratorio', 'Laboratório técnico'),
                        ('offsec', 'Técnico clássico'), ('htb', 'Laboratório escuro')]:
    MODELS[_theme + '-pt'] = {'label': _label + ' (PT-BR)', 'theme': _theme, 'lang': 'pt',
                            'subtitle': 'Relatório de achados' if _theme in ('corporativo', 'serio') else 'Relatório de segurança',
                            'confidential': 'CONFIDENCIAL'}


UI_LANGUAGE = "es"
UI_TEXT = {'Numero': ('Number', 'Número'),
 'Opcion no valida.': ('Invalid option.', 'Opção inválida.'),
 'Ruta de imagen a insertar (vacio = sin figura)': ('Image path to insert (empty = no figure)',
                                                    'Caminho da imagem a inserir (vazio = sem figura)'),
 'Epigrafe de la figura': ('Figure caption', 'Legenda da figura'),
 'Titulo en negrita del paso (lead), vacio para omitir': ('Bold step heading (lead), empty to omit',
                                                          'Título do passo em negrito (lead), vazio para omitir'),
 'Texto del paso': ('Step text', 'Texto do passo'),
 'Comando / bloque de codigo (vacio para omitir)': ('Command / code block (empty to omit)',
                                                    'Comando / bloco de código (vazio para omitir)'),
 'Tipo de hallazgo:': ('Finding type:', 'Tipo de achado:'),
 'Vulnerabilidad (CWE/CVSS, estilo COAE)': ('Vulnerability (CWE/CVSS, COAE style)',
                                            'Vulnerabilidade (CWE/CVSS, estilo COAE)'),
 'Maquina (host/puertos/fases, estilo OSCP+)': ('Machine (host/ports/phases, OSCP+ style)',
                                                'Máquina (host/portas/fases, estilo OSCP+)'),
 'Titulo del hallazgo': ('Finding title', 'Título do achado'),
 'Severidad:': ('Severity:', 'Severidade:'),
 'CVSS (ej 9.9)': ('CVSS (e.g. 9.9)', 'CVSS (ex. 9.9)'),
 'Vector CVSS (vacio para omitir)': ('CVSS vector (empty to omit)', 'Vetor CVSS (vazio para omitir)'),
 'CWE (vacio para omitir)': ('CWE (empty to omit)', 'CWE (vazio para omitir)'),
 'Dominio/host afectado (vacio para omitir)': ('Affected domain/host (empty to omit)',
                                               'Domínio/host afetado (vazio para omitir)'),
 'Descripcion / causa raiz': ('Description / root cause', 'Descrição / causa raiz'),
 'Impacto de seguridad': ('Security impact', 'Impacto de segurança'),
 'Remediacion': ('Remediation', 'Remediação'),
 'Referencia (URL, vacio para terminar)': ('Reference (URL, empty to finish)', 'Referência (URL, vazio para terminar)'),
 'Procedimiento detallado': ('Detailed walkthrough', 'Procedimento detalhado'),
 'Agregar Resumen de remediacion (corto/mediano/largo)?': ('Add a remediation summary (short/medium/long term)?',
                                                           'Adicionar resumo de remediação (curto/médio/longo prazo)?'),
 'Nombre de la maquina (ej TOASTER)': ('Machine name (e.g. TOASTER)', 'Nome da máquina (ex. TOASTER)'),
 'Direccion IP': ('IP address', 'Endereço IP'),
 'Sistema operativo (vacio para omitir)': ('Operating system (empty to omit)',
                                           'Sistema operacional (vazio para omitir)'),
 'Puertos abiertos (TCP)': ('Open ports (TCP)', 'Portas abertas (TCP)'),
 'Ruta de ataque / resumen (vacio para omitir)': ('Attack path / summary (empty to omit)',
                                                  'Caminho de ataque / resumo (vazio para omitir)'),
 'Nombre de la fase': ('Phase name', 'Nome da fase'),
 'Agregar entrada de evidencia (local.txt/proof.txt/flag)?': ('Add an evidence entry (local.txt/proof.txt/flag)?',
                                                              'Adicionar uma evidência (local.txt/proof.txt/flag)?'),
 'Nombre (ej local.txt)': ('Name (e.g. local.txt)', 'Nome (ex. local.txt)'),
 'Valor / hash': ('Value / hash', 'Valor / hash'),
 'Modelo de plantilla': ('Template model', 'Modelo de template'),
 'Elige el modelo de informe:': ('Choose a report model:', 'Escolha o modelo de relatório:'),
 'Portada / Metadatos': ('Cover / metadata', 'Capa / metadados'),
 'Titulo del informe': ('Report title', 'Título do relatório'),
 'Subtitulo': ('Subtitle', 'Subtítulo'),
 'Cliente': ('Client', 'Cliente'),
 'Evaluador': ('Assessor', 'Avaliador'),
 'Cargo del evaluador': ('Assessor role', 'Cargo do avaliador'),
 'Fecha (YYYY-MM-DD)': ('Date (YYYY-MM-DD)', 'Data (YYYY-MM-DD)'),
 'Version': ('Version', 'Versão'),
 'Wordmark (franja/cabecera)': ('Wordmark (band/header)', 'Marca textual (faixa/cabeçalho)'),
 'Byline (pie)': ('Byline (footer)', 'Autoria (rodapé)'),
 'Color de acento': ('Accent color', 'Cor de destaque'),
 'Texto de confidencialidad': ('Confidentiality text', 'Texto de confidencialidade'),
 'Contactos': ('Contacts', 'Contatos'),
 'Agregar contacto de cliente?': ('Add a client contact?', 'Adicionar contato do cliente?'),
 'Nombre': ('Name', 'Nome'),
 'Cargo': ('Role', 'Cargo'),
 'Correo': ('Email', 'E-mail'),
 'Agregar contacto del equipo evaluador?': ('Add an assessment team contact?',
                                            'Adicionar contato da equipe avaliadora?'),
 'Alcance': ('Scope', 'Escopo'),
 'Agregar objetivo al alcance?': ('Add a scope target?', 'Adicionar um alvo ao escopo?'),
 'Objetivo (host/URL/rango)': ('Target (host/URL/range)', 'Alvo (host/URL/intervalo)'),
 'Descripcion': ('Description', 'Descrição'),
 'Renderizar el PDF ahora?': ('Render the PDF now?', 'Gerar o PDF agora?'),
 'paso': ('step', 'passo'),
 'corto': ('short', 'curto'),
 'mediano': ('medium', 'médio'),
 'largo': ('long', 'longo'),
 'Agregar {label} {n}?': ('Add {label} {n}?', 'Adicionar {label} {n}?'),
 'Remediacion {term} plazo (vacio para omitir)': ('{term}-term remediation (empty to omit)',
                                                  'Remediação de {term} prazo (vazio para omitir)'),
 'Agregar fase {n} (ej Acceso inicial, Escalada)?': ('Add phase {n} (e.g. Initial access, Escalation)?',
                                                     'Adicionar fase {n} (ex. Acesso inicial, Escalada)?'),
 'Fase: {name}': ('Phase: {name}', 'Fase: {name}'),
 'Agregar hallazgo {id}?': ('Add finding {id}?', 'Adicionar achado {id}?'),
 'Hallazgo {id}': ('Finding {id}', 'Achado {id}'),
 'Nuevo hallazgo {id} en {name}': ('New finding {id} in {name}', 'Novo achado {id} em {name}'),
 '[!] no existe: {path}. Se omite la figura.': ('[!] not found: {path}. The figure is omitted.',
                                                '[!] não encontrado: {path}. A figura será omitida.'),
 '[+] copiada a {path}': ('[+] copied to {path}', '[+] copiada para {path}'),
 '-> {label} (tema {theme}, idioma {lang})': ('-> {label} (theme {theme}, language {lang})',
                                              '-> {label} (tema {theme}, idioma {lang})'),
 '[+] Escrito: {path}': ('[+] Written: {path}', '[+] Gravado: {path}'),
 'Luego: python engine.py {path}': ('Later: python engine.py {path}', 'Depois: python engine.py {path}'),
 '[+] Actualizado: {path}': ('[+] Updated: {path}', '[+] Atualizado: {path}'),
 ' (Markdown; termina con una linea que contenga solo un punto)': (' (Markdown; end with a line containing only a '
                                                                   'period)',
                                                                   ' (Markdown; termine com uma linha contendo apenas '
                                                                   'um ponto)'),
 'Asistente de captura para report-gen': ('Guided report-gen data entry', 'Assistente de preenchimento do report-gen'),
 'crear un informe nuevo desde un modelo': ('create a new report from a model',
                                            'criar um relatório a partir de um modelo'),
 'nombre de carpeta del engagement': ('engagement folder name', 'nome da pasta da avaliação'),
 'agregar un hallazgo a un informe existente': ('add a finding to an existing report',
                                                'adicionar um achado a um relatório existente'),
 'ruta a engagement.yaml': ('path to engagement.yaml', 'caminho de engagement.yaml'),
 'idioma de la interfaz; no cambia el idioma del informe': ('interface language; does not change the report language',
                                                            'idioma da interface; não altera o idioma do relatório')}

def tr(text, **values):
    translated = text if UI_LANGUAGE == "es" else UI_TEXT.get(text, (text, text))[language_index(UI_LANGUAGE) - 1]
    return translated.format(**values) if values else translated


# --- YAML con block scalars para la prosa multilinea -------------------------
class _Dumper(yaml.SafeDumper):
    pass


def _str_rep(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_rep)


def dump_yaml(data, path):
    from storage import atomic_write
    from input_guard import load_yaml
    from incremental_save import serialized_yaml, already_validated
    blob = serialized_yaml(data)
    if not already_validated(data, blob):
        load_yaml(blob)  # A writer must never commit more than its reader accepts.
    atomic_write(path, blob, backup=True)


# --- Entrada -----------------------------------------------------------------
def ask(prompt, default=""):
    tail = f" [{default}]" if default else ""
    try:
        s = input(f"{tr(prompt)}{tail}: ").strip()
    except EOFError:
        s = ""
    return s or default


def ask_block(prompt):
    print(tr(prompt) + tr(" (Markdown; termina con una linea que contenga solo un punto)"))
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
    d = (("y/N" if not default else "Y/n") if UI_LANGUAGE == "en" else ("s/N" if not default else "S/n"))
    s = ask(f"{tr(prompt)} ({d})")
    if not s:
        return default
    return s.lower().startswith("s") or s.lower().startswith("y")


def ask_choice(prompt, options):
    print(tr(prompt))
    for i, opt in enumerate(options, 1):
        label = opt[1] if isinstance(opt, tuple) else opt
        print(f"  {i}) {tr(label)}")
    while True:
        s = ask("Numero")
        if s.isdigit() and 1 <= int(s) <= len(options):
            opt = options[int(s) - 1]
            return opt[0] if isinstance(opt, tuple) else opt
        print("  " + tr("Opcion no valida."))


def section(title):
    print("\n" + "=" * 60)
    print(f"  {tr(title)}")
    print("=" * 60)


# --- Piezas reutilizables ----------------------------------------------------
def ask_figure(img_dir):
    src = ask("Ruta de imagen a insertar (vacio = sin figura)")
    if not src:
        return None
    p = Path(src).expanduser()
    if not p.exists():
        print("  " + tr("[!] no existe: {path}. Se omite la figura.", path=p))
        return None
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / p.name
    shutil.copy(p, dest)
    print("  " + tr("[+] copiada a {path}", path=dest.relative_to(img_dir.parent)))
    caption = ask("Epigrafe de la figura")
    return {"src": f"img/{p.name}", "caption": caption}


def ask_steps(img_dir, label="paso"):
    steps = []
    n = 1
    while ask_yesno(tr("Agregar {label} {n}?", label=tr(label), n=n), default=(n == 1)):
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
        from engine import load_lang
        f["severity"] = ask_choice("Severidad:", list(load_lang(UI_LANGUAGE)["severity"].items()))
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
                v = ask(tr("Remediacion {term} plazo (vacio para omitir)", term=tr(lbl)))
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
        while ask_yesno(tr("Agregar fase {n} (ej Acceso inicial, Escalada)?", n=pn), default=(pn == 1)):
            pname = ask("Nombre de la fase")
            section(tr("Fase: {name}", name=pname))
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
    print("  " + tr("-> {label} (tema {theme}, idioma {lang})", label=m["label"], theme=m["theme"], lang=m["lang"]))

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
    while ask_yesno(tr("Agregar hallazgo {id}?", id=next_fid(findings)), default=(len(findings) == 0)):
        section(tr("Hallazgo {id}", id=next_fid(findings)))
        findings.append(ask_finding(next_fid(findings), img_dir))

    data = {"meta": meta, "findings": findings}
    out = eng_dir / "engagement.yaml"
    dump_yaml(data, out)
    print("\n" + tr("[+] Escrito: {path}", path=out))

    if ask_yesno("Renderizar el PDF ahora?", default=True):
        subprocess.run([sys.executable, str(ROOT / "engine.py"), str(out), "--error-language", UI_LANGUAGE], check=False)
    else:
        print("    " + tr("Luego: python engine.py {path}", path=out.relative_to(ROOT)))


def cmd_add_finding(args):
    path = Path(args.engagement).resolve()
    from engine import load_engagement
    data = load_engagement(path)
    data.setdefault("findings", [])
    img_dir = path.parent / "img"
    fid = next_fid(data["findings"])
    section(tr("Nuevo hallazgo {id} en {name}", id=fid, name=path.name))
    data["findings"].append(ask_finding(fid, img_dir))
    dump_yaml(data, path)
    print("\n" + tr("[+] Actualizado: {path}", path=path))
    if ask_yesno("Renderizar el PDF ahora?", default=True):
        subprocess.run([sys.executable, str(ROOT / "engine.py"), str(path), "--error-language", UI_LANGUAGE], check=False)


def main():
    global UI_LANGUAGE
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("--ui-language", type=language_argument, default="es")
    initial, _ = probe.parse_known_args()
    UI_LANGUAGE = normalize_language(initial.ui_language)
    ap = argparse.ArgumentParser(description=tr("Asistente de captura para report-gen"), parents=[probe])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_new = sub.add_parser("new", help=tr("crear un informe nuevo desde un modelo"))
    p_new.add_argument("--model", choices=list(MODELS))
    p_new.add_argument("--slug", help=tr("nombre de carpeta del engagement"))
    p_new.set_defaults(func=cmd_new)
    p_add = sub.add_parser("add-finding", help=tr("agregar un hallazgo a un informe existente"))
    p_add.add_argument("engagement", help=tr("ruta a engagement.yaml"))
    p_add.set_defaults(func=cmd_add_finding)
    for subparser in (p_new, p_add):
        subparser.add_argument("--ui-language", type=language_argument, default=argparse.SUPPRESS,
                              help=tr("idioma de la interfaz; no cambia el idioma del informe"))
    args = ap.parse_args()
    with language_scope(UI_LANGUAGE):
        args.func(args)


if __name__ == "__main__":
    main()

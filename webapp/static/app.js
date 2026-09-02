// ---- helpers ---------------------------------------------------------------
const $ = s => document.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "class") e.className = attrs[k];
    else if (k === "html") e.innerHTML = attrs[k];
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
  }
  for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
const api = {
  get: u => fetch(u).then(r => r.json()),
  post: (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }),
  put: (u, b) => fetch(u, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }),
  del: u => fetch(u, { method: "DELETE" }),
};

// ---- CVSS 3.1 (port de cvss.py) -------------------------------------------
const CV = {
  AV: { N: .85, A: .62, L: .55, P: .2 }, AC: { L: .77, H: .44 }, UI: { N: .85, R: .62 },
  CIA: { H: .56, L: .22, N: 0 }, PRU: { N: .85, L: .62, H: .27 }, PRC: { N: .85, L: .68, H: .5 },
  M: ["AV", "AC", "PR", "UI", "S", "C", "I", "A"],
  D: { AV: "N", AC: "L", PR: "N", UI: "N", S: "U", C: "N", I: "N", A: "N" },
  OPTS: {
    AV: [["N", "Network"], ["A", "Adjacent"], ["L", "Local"], ["P", "Physical"]],
    AC: [["L", "Low"], ["H", "High"]], PR: [["N", "None"], ["L", "Low"], ["H", "High"]],
    UI: [["N", "None"], ["R", "Required"]], S: [["U", "Unchanged"], ["C", "Changed"]],
    C: [["H", "High"], ["L", "Low"], ["N", "None"]], I: [["H", "High"], ["L", "Low"], ["N", "None"]],
    A: [["H", "High"], ["L", "Low"], ["N", "None"]],
  },
};
function roundup(x) { const i = Math.round(x * 100000); return i % 10000 === 0 ? i / 100000 : (Math.floor(i / 10000) + 1) / 10; }
function cvssSeverity(s) { return s === 0 ? "info" : s < 4 ? "low" : s < 7 ? "medium" : s < 9 ? "high" : "critical"; }
function cvssCompute(m) {
  const mm = Object.assign({}, CV.D, m || {});
  const ch = mm.S === "C";
  const pr = (ch ? CV.PRC : CV.PRU)[mm.PR];
  const expl = 8.22 * CV.AV[mm.AV] * CV.AC[mm.AC] * pr * CV.UI[mm.UI];
  const iss = 1 - (1 - CV.CIA[mm.C]) * (1 - CV.CIA[mm.I]) * (1 - CV.CIA[mm.A]);
  const impact = ch ? 7.52 * (iss - .029) - 3.25 * Math.pow(iss - .02, 15) : 6.42 * iss;
  let score = impact <= 0 ? 0 : ch ? roundup(Math.min(1.08 * (impact + expl), 10)) : roundup(Math.min(impact + expl, 10));
  score = Math.round(score * 10) / 10;
  return { score, severity: cvssSeverity(score), vector: "CVSS:3.1/" + CV.M.map(k => k + ":" + mm[k]).join("/"), metrics: mm };
}
function cvssParse(v) { const m = Object.assign({}, CV.D); (v || "").split("/").forEach(p => { const [k, val] = p.split(":"); if (CV.M.includes(k)) m[k] = val; }); return m; }

// ---- estado ----------------------------------------------------------------
const S = { designs: [], projects: [], slug: null, data: null, sel: { type: "report", idx: -1 }, owasp: {}, cwe: {}, presets: [], uiLang: "es", previewMode: "live", previewVisible: true };

// ---- i18n del sitio -------------------------------------------------------
const I18N = {
  es: {
    new_project:"Nuevo proyecto", delete:"Eliminar", delete_title:"Eliminar el proyecto actual",
    hide_preview:"Ocultar preview", show_preview:"Mostrar preview", preview_toggle_title:"Mostrar u ocultar la vista previa",
    ui_lang_title:"Idioma del sitio", update_preview:"Actualizar preview", export:"Exportar",
    rename:"Renombrar", rename_title:"Cambiar el nombre del proyecto (título del informe)", rename_prompt:"Nuevo nombre del proyecto:",
 credit_by:"Desarrollado por", recommended:"recomendada", sec_title:"Título de la sección", sec_body:"Contenido (Markdown)", lang_label:"Idioma", cert_label:"Certificación", htb_family:"HTB (certificación)", preset_label:"Plantilla", preset_note:"Los nombres «estilo OSCP/HTB» son descriptivos; no afiliado a OffSec ni Hack The Box.",
    search_ph:"Buscar en el proyecto\u2026", search_none:"Sin resultados",
    export_format_title:"Formato de exportacion", project_title:"Proyecto",
    saved:"guardado", saving:"guardando\u2026", ready:"listo", uptodate:"al dia", updating:"actualizando\u2026", err:"error",
    report:"Informe", sections_head:"Secciones del informe", manage_sections:"Gestionar secciones",
    findings_head:"Hallazgos", add_finding:"Anadir hallazgo", blank:"En blanco",
    empty:"Crea un proyecto con \u00abNuevo proyecto\u00bb (arriba) o elige uno del desplegable.",
    cover_meta:"Portada / Metadatos", report_title:"Titulo del informe", subtitle:"Subtitulo", client:"Cliente",
    subtitle_ph:"ej. Informe de hallazgos \u2014 App web", assessor_ph:"ej. Nombre Apellido",
    assessor_title_ph:"ej. Ethical Hacker / Pentester", version_ph:"ej. 1.0",
    wordmark_ph:"ej. tu marca", byline_ph:"ej. Nombre / marca", target_ph:"ej. https://app.cliente.com",
    date:"Fecha (YYYY-MM-DD)", assessor:"Evaluador", assessor_title:"Cargo del evaluador", version:"Version",
    design:"Diseno", report_lang:"Idioma", wordmark:"Wordmark", byline:"Byline (pie)",
    cover_image:"Imagen de portada", own_logo:"Tu logo", client_logo:"Logo del cliente", remove:"Quitar",
    conf_text:"Texto de confidencialidad", accent:"Color de acento",
    contacts_scope_note:"Los contactos y el alcance se editan en sus secciones (Contactos del engagement y Alcance y objetivos).",
    client_contacts:"Contactos del cliente", assessor_team:"Equipo evaluador", scope_targets:"Alcance (objetivos / targets)",
    name:"Nombre", role:"Cargo", email:"Correo", target:"Objetivo", description:"Descripcion", add_row:"+ Agregar",
    vuln:"Vulnerabilidad", machine:"Maquina", delete_finding:"Eliminar hallazgo", finding_data:"Datos del hallazgo",
    title:"Titulo", severity:"Severidad", cwe:"CWE", cwe_ph:"escribe un numero o nombre (p. ej. 312 o XSS)",
    cwe_notfound:"(no esta en el listado cargado)", affected:"Dominio/host afectado",
    content:"Contenido", desc_root:"Descripcion / causa raiz", impact:"Impacto de seguridad", remediation:"Remediacion",
    references:"Referencias", rem_summary:"Resumen de remediacion", calculator:"Calculadora ",
    untitled:"(sin titulo)", new_finding:"Nuevo hallazgo",
    host:"Host", machine_name:"Nombre de la maquina", attack_path:"Ruta de ataque / resumen",
    phase_name_ph:"ej. Acceso inicial",
    ip:"Direccion IP", ip_ph:"ej. 10.10.10.5",
    os:"Sistema operativo", os_ph:"ej. Windows Server 2019 / Ubuntu 22.04",
    ports:"Puertos abiertos (TCP)", ports_ph:"ej. 22, 80, 443, 445",
    attack_path_ph:"ej. Enumeracion -> acceso inicial -> escalada de privilegios",
    machine_hint:"Cada fase agrupa pasos. El comando de cada paso va en \u00abBloque de codigo\u00bb, no en el nombre de la fase.",
    step:"Paso", add_step:"+ Bloque / paso", lead:"Lead (negrita)", step_text:"Texto (Markdown)",
    code_block:"Bloque de codigo / comando", image:"Imagen", caption_ph:"Epigrafe", remove_image:"Quitar imagen",
    phase:"Fase", remove_phase:"\u2715 fase", add_phase:"+ Fase", procedure:"Procedimiento detallado",
    add_ref:"+ Referencia", evidence:"Evidencia (local.txt / proof.txt / flags)", ev_name:"Nombre", ev_value:"Valor / hash",
    note_summary:"Se genera automaticamente desde los hallazgos y sus severidades.",
    note_findings:"Los hallazgos se editan en el panel Hallazgos.",
    note_appendix:"La tabla de evidencias (hosts, flags, hashes) se genera desde los hallazgos; arriba puedes anadir apendices en texto.", report_title_ph:"Evaluacion de Seguridad ...", client_ph:"Cliente Ltd.",
    slug_label:"Nombre de carpeta (slug)", slug_ph:"cliente-2026", cancel:"Cancelar", create:"Crear", close:"Cerrar",
    sections_modal_h:"Secciones del informe", sections_hint:"Activa las secciones que necesites. Las obligatorias no se pueden desmarcar.",
    done:"Listo", preview_head:"Vista previa", live:"Vivo",
    delete_finding_confirm:"¿Eliminar este hallazgo?", copy_vector:"Copiar vector", copied:"Copiado",
    cvss_paste_label:"Pegar vector", cvss_paste_ph:"pega un vector completo (con o sin CVSS:x.x/) y calcula solo",
    cvss_paste_bad:"vector inválido para esta versión", duplicate_finding:"Duplicar",
    unsaved:"Hay cambios sin guardar. ¿Salir de todas formas?",
    create_fail:"No se pudo crear", delete_confirm:"Eliminar el proyecto \"{n}\"?\nEsto borra su informe y sus imagenes de forma permanente."
  },
  en: {
    new_project:"New project", delete:"Delete", delete_title:"Delete the current project",
    hide_preview:"Hide preview", show_preview:"Show preview", preview_toggle_title:"Show or hide the preview",
    ui_lang_title:"Site language", update_preview:"Refresh preview", export:"Export",
    rename:"Rename", rename_title:"Rename the project (report title)", rename_prompt:"New project name:",
 credit_by:"Developed by", recommended:"recommended", sec_title:"Section title", sec_body:"Content (Markdown)", lang_label:"Language", cert_label:"Certification", htb_family:"HTB (certification)", preset_label:"Template", preset_note:"«OSCP/HTB-style» names are descriptive; not affiliated with OffSec or Hack The Box.",
    search_ph:"Search the project\u2026", search_none:"No results",
    export_format_title:"Export format", project_title:"Project",
    saved:"saved", saving:"saving\u2026", ready:"ready", uptodate:"up to date", updating:"updating\u2026", err:"error",
    report:"Report", sections_head:"Report sections", manage_sections:"Manage sections",
    findings_head:"Findings", add_finding:"Add finding", blank:"Blank",
    empty:"Create a project with \u00abNew project\u00bb (top) or pick one from the dropdown.",
    cover_meta:"Cover / Metadata", report_title:"Report title", subtitle:"Subtitle", client:"Client",
    subtitle_ph:"e.g. Findings report \u2014 Web app", assessor_ph:"e.g. First Last",
    assessor_title_ph:"e.g. Ethical Hacker / Pentester", version_ph:"e.g. 1.0",
    wordmark_ph:"e.g. your brand", byline_ph:"e.g. Name / brand", target_ph:"e.g. https://app.client.com",
    date:"Date (YYYY-MM-DD)", assessor:"Assessor", assessor_title:"Assessor title", version:"Version",
    design:"Theme", report_lang:"Language", wordmark:"Wordmark", byline:"Byline (footer)",
    cover_image:"Cover image", own_logo:"Your logo", client_logo:"Client logo", remove:"Remove",
    conf_text:"Confidentiality text", accent:"Accent color",
    contacts_scope_note:"Contacts and scope are edited in their sections (Engagement contacts and Scope and objectives).",
    client_contacts:"Client contacts", assessor_team:"Assessment team", scope_targets:"Scope (objectives / targets)",
    name:"Name", role:"Title", email:"Email", target:"Target", description:"Description", add_row:"+ Add",
    vuln:"Vulnerability", machine:"Machine", delete_finding:"Delete finding", finding_data:"Finding data",
    title:"Title", severity:"Severity", cwe:"CWE", cwe_ph:"type a number or name (e.g. 312 or XSS)",
    cwe_notfound:"(not in the loaded list)", affected:"Affected domain/host",
    content:"Content", desc_root:"Description / root cause", impact:"Security impact", remediation:"Remediation",
    references:"References", rem_summary:"Remediation summary", calculator:"Calculator ",
    untitled:"(untitled)", new_finding:"New finding",
    host:"Host", machine_name:"Machine name", attack_path:"Attack path / summary",
    phase_name_ph:"e.g. Initial access",
    ip:"IP address", ip_ph:"e.g. 10.10.10.5",
    os:"Operating system", os_ph:"e.g. Windows Server 2019 / Ubuntu 22.04",
    ports:"Open ports (TCP)", ports_ph:"e.g. 22, 80, 443, 445",
    attack_path_ph:"e.g. Enumeration -> initial access -> privilege escalation",
    machine_hint:"Each phase groups steps. Each step's command goes in \u00abCode block\u00bb, not in the phase name.",
    step:"Step", add_step:"+ Block / step", lead:"Lead (bold)", step_text:"Text (Markdown)",
    code_block:"Code block / command", image:"Image", caption_ph:"Caption", remove_image:"Remove image",
    phase:"Phase", remove_phase:"\u2715 phase", add_phase:"+ Phase", procedure:"Detailed procedure",
    add_ref:"+ Reference", evidence:"Evidence (local.txt / proof.txt / flags)", ev_name:"Name", ev_value:"Value / hash",
    note_summary:"Auto-generated from the findings and their severities.",
    note_findings:"Findings are edited in the Findings panel.",
    note_appendix:"The evidence table (hosts, flags, hashes) is generated from the findings; above you can add text appendices.", report_title_ph:"Security Assessment ...", client_ph:"Client Ltd.",
    slug_label:"Folder name (slug)", slug_ph:"client-2026", cancel:"Cancel", create:"Create", close:"Close",
    sections_modal_h:"Report sections", sections_hint:"Enable the sections you need. Required ones cannot be unchecked.",
    done:"Done", preview_head:"Preview", live:"Live",
    delete_finding_confirm:"Delete this finding?", copy_vector:"Copy vector", copied:"Copied",
    cvss_paste_label:"Paste vector", cvss_paste_ph:"paste a full vector (with or without CVSS:x.x/) and it auto-calculates",
    cvss_paste_bad:"invalid vector for this version", duplicate_finding:"Duplicate",
    unsaved:"You have unsaved changes. Leave anyway?",
    create_fail:"Could not create", delete_confirm:"Delete project \"{n}\"?\nThis permanently removes its report and images."
  }
};
function t(key) { const L = S.uiLang || "es"; return (I18N[L] && I18N[L][key]) || I18N.es[key] || key; }
function applyStaticI18n() {
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.getAttribute("data-i18n")); });
  document.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.getAttribute("data-i18n-title")); });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.getAttribute("data-i18n-ph")); });
  document.documentElement.lang = S.uiLang || "es";
}
function setUiLang(lang) {
  S.uiLang = lang;
  try { localStorage.setItem("rg.uiLang", lang); } catch (_) {}
  const b = document.getElementById("langToggle"); if (b) b.textContent = lang.toUpperCase();
  applyStaticI18n();
  const pb = document.getElementById("previewToggle"); if (pb) pb.textContent = S.previewVisible ? t("hide_preview") : t("show_preview");
  if (S.data) { S.data.meta.lang = lang; scheduleSave(); }
  renderSidebar(); renderMain();
  if (S.previewVisible && S.previewMode === "live") refreshLivePreview();
}
function toggleUiLang() { setUiLang(S.uiLang === "en" ? "es" : "en"); }

const SEV = [["critical", "Crítica"], ["high", "Alta"], ["medium", "Media"], ["low", "Baja"], ["info", "Informativa"]];

// ---- reordenar arrastrando --------------------------------------------------
let dragCtx = null;
function dragHandle(arr, i) {
  return h("span", { class: "drag", draggable: "true", title: "Arrastrar para reordenar",
    ondragstart: e => { dragCtx = { arr, from: i }; e.dataTransfer.effectAllowed = "move"; e.stopPropagation(); } }, "\u283F");
}
function makeDropZone(el, arr, i) {
  el.addEventListener("dragover", e => { if (dragCtx && dragCtx.arr === arr) { e.preventDefault(); el.classList.add("dragover"); } });
  el.addEventListener("dragleave", () => el.classList.remove("dragover"));
  el.addEventListener("drop", e => {
    el.classList.remove("dragover");
    if (dragCtx && dragCtx.arr === arr && dragCtx.from !== i) {
      e.preventDefault();
      const it = arr.splice(dragCtx.from, 1)[0];
      arr.splice(i, 0, it);
      const wasFindings = arr === S.data.findings;
      dragCtx = null;
      if (wasFindings) { renumberFindings(); S.sel = { type: "finding", idx: i }; }
      scheduleSave(); renderSidebar(); renderMain();
    }
  });
}
function renumberFindings() { (S.data.findings || []).forEach((f, i) => { f.id = "F" + (i + 1); }); }

let saveTimer = null;
window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = t("unsaved"); return t("unsaved"); } });
function scheduleSave() {
  S.dirty = true;
  setSaveState(t("saving"));
  clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 700);
}
async function doSave() {
  if (!S.slug) return;
  setSaveState(t("saving"));
  await api.put(`/api/projects/${S.slug}`, S.data);
  S.dirty = false;
  const opt = [...$("#projectSelect").options].find(o => o.value === S.slug);
  if (opt && S.data) opt.textContent = `${(S.data.meta.report_title || S.slug)} [${S.data.meta.theme}/${S.data.meta.lang}]`;
  setSaveState(t("saved"));
  if (S.previewMode === "live") refreshLivePreview();
}
function setSaveState(t) { $("#saveState").textContent = t; }
function setPvStatus(t) { $("#pvStatus").textContent = t; }

function updateLangBtn() {
  $("#langToggle").textContent = (S.uiLang || "es").toUpperCase();
}

async function refreshLivePreview() {
  if (!S.slug) return;
  setPvStatus(t("updating"));
  try {
    const r = await fetch(`/api/projects/${S.slug}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
    const html = await r.text();
    const f = $("#pdfPreview");
    f.removeAttribute("src");
    f.setAttribute("sandbox", "allow-same-origin");  // el preview no ejecuta scripts del contenido
    f.srcdoc = html;
    setPvStatus(t("uptodate"));
  } catch (e) { setPvStatus(t("err")); }
}
function setPreviewVisible(vis) {
  S.previewVisible = vis;
  document.querySelector(".layout").classList.toggle("no-preview", !vis);
  const btn = $("#previewToggle");
  if (btn) btn.textContent = vis ? t("hide_preview") : t("show_preview");
  // el botón "Actualizar preview" no aplica cuando está oculto
  const pv = $("#previewBtn"); if (pv) pv.style.display = vis ? "" : "none";
  try { localStorage.setItem("rg.previewVisible", vis ? "1" : "0"); } catch (_) { /* sin storage */ }
  if (vis && S.previewMode === "live") refreshLivePreview();
}

function setPreviewMode(m) {
  S.previewMode = m;
  $("#pvLive").classList.toggle("primary", m === "live");
  $("#pvPdf").classList.toggle("primary", m === "pdf");
  if (m === "live") refreshLivePreview();
  else renderPdf(false);
}

// ---- carga -----------------------------------------------------------------

async function init() {
  S.designs = await api.get("/api/designs");
  S.owasp.web = await api.get("/api/owasp/web");
  S.owasp.llm = await api.get("/api/owasp/llm");
  S.catalog = await api.get("/api/sections/catalog");
  S.cwe = await api.get("/api/cwe");
  S.presets = await api.get("/api/presets");
  S.catBy = {};
  (S.catalog.sections || []).forEach(s => { S.catBy[s.key] = s; });
  await refreshProjects();
  bindUI();
  { let l = "es"; try { l = localStorage.getItem("rg.uiLang") || "es"; } catch (_) {} S.uiLang = l; }
  updateLangBtn(); applyStaticI18n();
  if (S.projects.length) loadProject(S.projects[0].slug);
  hideSplash();
}
const SPLASH_MIN_MS = 3000;
const _splashStart = Date.now();
function hideSplash() {
  const s = document.getElementById("splash");
  if (!s) return;
  const wait = Math.max(0, SPLASH_MIN_MS - (Date.now() - _splashStart));
  setTimeout(() => { s.classList.add("hide"); setTimeout(() => s.remove(), 500); }, wait);
}
async function refreshProjects() {
  S.projects = await api.get("/api/projects");
  const sel = $("#projectSelect");
  sel.innerHTML = "";
  S.projects.forEach(p => sel.append(h("option", { value: p.slug }, `${p.title} [${p.theme}/${p.lang}]`)));
}
async function loadProject(slug) {
  S.slug = slug;
  S.data = await api.get(`/api/projects/${slug}`);
  S.data.findings = S.data.findings || [];
  S.data.report = S.data.report || { sections: [] };
  S.data.report.sections = S.data.report.sections || [];
  $("#projectSelect").value = slug;
  S.sel = { type: "report", idx: -1 };
  renderSidebar(); renderMain();
  setSaveState(t("ready"));
  updateLangBtn();
  if (S.previewMode === "live") refreshLivePreview();
}

// ---- sidebar ---------------------------------------------------------------
function renderSidebar() {
  $("#navReport").classList.toggle("active", S.sel.type === "report");
  // secciones activas
  const sl = $("#sectionList"); sl.innerHTML = "";
  const secs = (S.data && S.data.report && S.data.report.sections) || [];
  secs.forEach((sec, i) => {
    const schema = S.catBy[sec.key] || {};
    const lang = (S.data.meta.lang || "es");
    const title = sec.title || schema["title_" + lang] || schema.title_es || sec.key;
    const li = h("li", { draggable: "true", class: S.sel.type === "section" && S.sel.key === sec.key ? "active" : "", onclick: () => select("section", sec.key) },
      h("span", { class: "ftitle" }, `${i + 1}. ${title}`),
      schema.special ? h("span", { class: "sect-badge" }, schema.special) : null);
    li.addEventListener("dragstart", e => { dragCtx = { arr: secs, from: i }; e.dataTransfer.effectAllowed = "move"; });
    makeDropZone(li, secs, i);
    sl.append(li);
  });
  // hallazgos
  const ul = $("#findingList"); ul.innerHTML = "";
  (S.data?.findings || []).forEach((f, i) => {
    const sev = f.severity || (f.mode === "machine" ? "info" : "info");
    const li = h("li", { draggable: "true", class: S.sel.type === "finding" && S.sel.idx === i ? "active" : "", onclick: () => select("finding", i) },
      h("span", { class: "sev-dot sev-" + sev }),
      h("span", { class: "fid" }, f.id || ""),
      h("span", { class: "ftitle" }, f.title || t("untitled"))
    );
    li.addEventListener("dragstart", e => { dragCtx = { arr: S.data.findings, from: i }; e.dataTransfer.effectAllowed = "move"; });
    makeDropZone(li, S.data.findings, i);
    ul.append(li);
  });
}
// ---- buscador global -------------------------------------------------------
function searchTargets() {
  const d = S.data, out = [];
  if (!d) return out;
  const m = d.meta || {}, rep = { type: "report" };
  [["report_title", "Titulo"], ["report_subtitle", "Subtitulo"], ["client", "Cliente"], ["assessor", "Evaluador"], ["assessor_title", "Cargo"], ["version", "Version"]]
    .forEach(([k, lab]) => { if (m[k]) out.push({ nav: rep, where: "Informe \u00b7 " + lab, text: String(m[k]) }); });
  ((m.contacts && m.contacts.client) || []).forEach(c => out.push({ nav: { type: "section", key: "contacts" }, where: "Contactos cliente", text: [c.name, c.title, c.email].filter(Boolean).join(" ") }));
  ((m.contacts && m.contacts.assessor) || []).forEach(c => out.push({ nav: { type: "section", key: "contacts" }, where: "Equipo evaluador", text: [c.name, c.title, c.email].filter(Boolean).join(" ") }));
  (m.scope || []).forEach(s => out.push({ nav: { type: "section", key: "scope" }, where: "Alcance", text: [s.target, s.description].filter(Boolean).join(" ") }));
  ((d.report && d.report.sections) || []).forEach(sec => {
    const schema = S.catBy[sec.key] || {};
    (schema.fields || []).forEach(f => { const v = sec[f.key]; if (typeof v === "string" && v) out.push({ nav: { type: "section", key: sec.key }, where: (schema["title_" + (S.uiLang || "es")] || schema.title_es || sec.key), text: v }); });
  });
  (d.findings || []).forEach((f, idx) => {
    const nav = { type: "finding", idx }, w = f.id + (f.title ? " " + f.title : "");
    [["title", "Titulo"], ["cwe", "CWE"], ["affected", "Host"], ["description_md", "Descripcion"], ["impact_md", "Impacto"], ["remediation_md", "Remediacion"]]
      .forEach(([k, lab]) => { if (f[k]) out.push({ nav, where: w + " \u00b7 " + lab, text: String(f[k]) }); });
    (f.references || []).forEach(r => { if (r) out.push({ nav, where: w + " \u00b7 Ref", text: r }); });
    if (f.host) [["name", "Maquina"], ["ip", "IP"], ["os", "SO"]].forEach(([k, lab]) => { if (f.host[k]) out.push({ nav, where: w + " \u00b7 " + lab, text: f.host[k] }); });
    if (f.open_ports) out.push({ nav, where: w + " \u00b7 Puertos", text: f.open_ports });
    if (f.summary_md) out.push({ nav, where: w + " \u00b7 Ruta", text: f.summary_md });
    (f.phases || []).forEach(ph => {
      if (ph.name) out.push({ nav, where: w + " \u00b7 Fase", text: ph.name });
      (ph.steps || []).forEach(st => ["lead", "text", "code"].forEach(k => { if (st[k]) out.push({ nav, where: w + " \u00b7 Paso", text: st[k] }); }));
    });
  });
  return out;
}
function searchSnippet(text, i, len) {
  const s = Math.max(0, i - 30), e = Math.min(text.length, i + len + 40);
  return { pre: (s > 0 ? "\u2026" : "") + text.slice(s, i), mid: text.slice(i, i + len), post: text.slice(i + len, e) + (e < text.length ? "\u2026" : "") };
}
function searchProject(q) {
  q = (q || "").trim().toLowerCase();
  if (!q) return [];
  const res = [];
  for (const tg of searchTargets()) {
    const i = tg.text.toLowerCase().indexOf(q);
    if (i >= 0) { res.push({ nav: tg.nav, where: tg.where, snippet: searchSnippet(tg.text.replace(/\s+/g, " "), tg.text.replace(/\s+/g, " ").toLowerCase().indexOf(q), q.length) }); if (res.length >= 40) break; }
  }
  return res;
}
function navTo(nav) {
  if (nav.type === "section") select("section", nav.key);
  else if (nav.type === "finding") select("finding", nav.idx);
  else select("report", -1);
}
function renderSearch(q) {
  const box = $("#searchResults");
  const results = searchProject(q);
  box.innerHTML = "";
  if (!q.trim()) { box.classList.remove("open"); return; }
  box.classList.add("open");
  if (!results.length) { box.append(h("div", { class: "search-none" }, t("search_none"))); return; }
  results.forEach(r => {
    const item = h("div", { class: "search-item", onmousedown: e => { e.preventDefault(); navTo(r.nav); $("#globalSearch").value = ""; box.classList.remove("open"); } },
      h("div", { class: "search-where" }, r.where),
      h("div", { class: "search-snip" }, r.snippet.pre, h("mark", {}, r.snippet.mid), r.snippet.post));
    box.append(item);
  });
}

function select(type, val) { S.sel = (type === "section") ? { type, key: val } : { type, idx: val }; renderSidebar(); renderMain(); }
function nextFid() { return "F" + ((S.data.findings.length) + 1); }

// ---- editor principal ------------------------------------------------------
function renderMain() {
  const el = $("#editor"); el.innerHTML = "";
  if (!S.data) { el.append(h("div", { class: "empty" }, t("empty"))); return; }
  if (S.sel.type === "report") el.append(reportEditor());
  else if (S.sel.type === "section") el.append(sectionEditor(S.sel.key));
  else el.append(findingEditor(S.data.findings[S.sel.idx]));
}

function noteCard(text) {
  return h("div", { class: "card" }, h("p", { style: "margin:0;color:var(--muted)" }, text));
}

function contactsEditor() {
  const cc = (S.data.meta.contacts = S.data.meta.contacts || { client: [], assessor: [] });
  cc.client = cc.client || []; cc.assessor = cc.assessor || [];
  const wrap = h("div", {});
  const mk = row => [inlineField(row, "name", t("name")), inlineField(row, "title", t("role")), inlineField(row, "email", t("email"))];
  wrap.append(listCard(t("client_contacts"), cc.client, () => ({ name: "", title: "", email: "" }), mk));
  wrap.append(listCard(t("assessor_team"), cc.assessor, () => ({ name: "", title: "", email: "" }), mk));
  return wrap;
}

function scopeListEditor() {
  const m = S.data.meta; m.scope = m.scope || [];
  return listCard(t("scope_targets"), m.scope, () => ({ target: "", description: "" }),
    row => [inlineField(row, "target", t("target_ph")), inlineField(row, "description", t("description"))]);
}

function sectionEditor(key) {
  const schema = S.catBy[key] || {};
  const lang = (S.data.meta.lang || "es");
  const sec = S.data.report.sections.find(s => s.key === key) || {};
  const wrap = h("div", {});
  const isGeneric = !S.catBy[key];
  wrap.append(h("h2", {}, sec.title || schema["title_" + lang] || schema.title_es || key));
  const sp = schema.special;
  if (isGeneric) {  // seccion a medida (apendice nombrado, etc.): titulo editable + cuerpo markdown
    const c = h("div", { class: "card" });
    c.append(field(t("sec_title"), sec, "title"));
    c.append(mdEditor(t("sec_body"), sec, "body", { rows: 10 }));
    wrap.append(c);
    return wrap;
  }

  if (sp === "contacts") { wrap.append(contactsEditor()); return wrap; }
  if (sp === "summary") { wrap.append(noteCard(t("note_summary"))); return wrap; }
  if (sp === "findings") { wrap.append(noteCard(t("note_findings"))); return wrap; }

  // Campos genéricos (resumen ejecutivo, metodología, objetivos del alcance, apéndices en texto…)
  const fields = schema.fields || [];
  if (fields.length) {
    const c = h("div", { class: "card" });
    fields.forEach(f => {
      const label = f["label_" + lang] || f.label_es || f.key;
      if (f.type === "markdown") c.append(mdEditor(label, sec, f.key, { rows: 8 }));
      else if (f.type === "text") c.append(field(label, sec, f.key));
      else if (f.type === "list") { sec[f.key] = sec[f.key] || []; c.append(listCard(label, sec[f.key], () => "", () => [])); }
      else if (f.type === "table") {
        sec[f.key] = sec[f.key] || [];
        const cols = f.columns || [];
        c.append(listCard(label, sec[f.key], () => ({}), row => cols.map(col => inlineField(row, col.key, col["label_" + lang] || col.label_es || col.key))));
      }
    });
    wrap.append(c);
  }

  if (sp === "scope") wrap.append(scopeListEditor());
  if (sp === "appendix") wrap.append(noteCard(t("note_appendix")));
  return wrap;
}

function autoGrow(ta) {
  ta.style.height = "auto";
  ta.style.height = (ta.scrollHeight + 2) + "px";
}
function colorField(label, obj, key) {
  const valid = v => /^#[0-9a-fA-F]{6}$/.test(v || "");
  const hex = h("input", { value: obj[key] || "", placeholder: "#39ff14", style: "flex:1",
    oninput: e => { obj[key] = e.target.value; if (valid(e.target.value)) sw.value = e.target.value; scheduleSave(); } });
  const sw = h("input", { type: "color", value: valid(obj[key]) ? obj[key] : "#39ff14",
    style: "width:46px;height:38px;padding:2px;flex:none;cursor:pointer",
    oninput: e => { obj[key] = e.target.value; hex.value = e.target.value; scheduleSave(); } });
  return h("label", {}, label, h("div", { style: "display:flex;gap:8px;align-items:center" }, sw, hex));
}
function field(label, obj, key, opts = {}) {
  if (opts.type === "color") return colorField(label, obj, key);
  let inp;
  if (opts.area) {
    inp = h("textarea", { rows: opts.rows || 4, class: "grow", oninput: e => { obj[key] = e.target.value; autoGrow(e.target); scheduleSave(); } });
    inp.value = obj[key] || ""; setTimeout(() => autoGrow(inp), 0);
  } else {
    inp = h("input", { type: opts.type || "text", value: obj[key] || "", oninput: e => { obj[key] = e.target.value; scheduleSave(); } });
  }
  if (opts.ph) inp.setAttribute("placeholder", opts.ph);
  return h("label", {}, label, inp);
}

// Editor Markdown estilo SysReptor: barra + Write/Preview + imagen + tabla.
function mdEditor(label, obj, key, opts = {}) {
  obj[key] = obj[key] || "";
  const ta = h("textarea", { rows: opts.rows || 10, class: "grow" });
  ta.value = obj[key];
  const prev = h("div", { class: "mded-prev", style: "display:none" });

  function apply() { obj[key] = ta.value; autoGrow(ta); scheduleSave(); }
  ta.addEventListener("input", apply);
  setTimeout(() => autoGrow(ta), 0);

  function insert(before, after, placeholder) {
    const s = ta.selectionStart, e = ta.selectionEnd;
    const sel = ta.value.slice(s, e) || placeholder || "";
    ta.value = ta.value.slice(0, s) + before + sel + after + ta.value.slice(e);
    ta.focus();
    ta.selectionStart = s + before.length;
    ta.selectionEnd = s + before.length + sel.length;
    apply();
  }
  function prefixLines(prefix) {
    const s = ta.selectionStart, e = ta.selectionEnd;
    const start = ta.value.lastIndexOf("\n", s - 1) + 1;
    const block = ta.value.slice(start, e);
    const replaced = block.split("\n").map(l => prefix + l).join("\n");
    ta.value = ta.value.slice(0, start) + replaced + ta.value.slice(e);
    ta.focus(); apply();
  }
  function insertAtCursor(text) {
    const s = ta.selectionStart;
    ta.value = ta.value.slice(0, s) + text + ta.value.slice(s);
    ta.focus(); ta.selectionStart = ta.selectionEnd = s + text.length; apply();
  }
  const fileInp = h("input", { type: "file", accept: "image/*", style: "display:none",
    onchange: async e => {
      const file = e.target.files[0]; if (!file) return;
      const fd = new FormData(); fd.append("file", file);
      setSaveState(t("saving"));
      const r = await fetch(`/api/projects/${S.slug}/image`, { method: "POST", body: fd }).then(x => x.json());
      insertAtCursor(`\n![epígrafe de la imagen](${r.src}){width="auto"}\n`);
      setSaveState(t("saved"));
    } });

  const tb = (txt, title, fn) => h("button", { class: "mded-btn", type: "button", title, onclick: fn }, txt);
  const bar = h("div", { class: "mded-bar" },
    tb("B", "Negrita", () => insert("**", "**", "texto")),
    tb("i", "Cursiva", () => insert("*", "*", "texto")),
    tb("</>", "Código en línea", () => insert("`", "`", "código")),
    tb("{ }", "Bloque de código", () => insert("```bash\n", "\n```", "comando")),
    tb("H", "Encabezado (negrita)", () => prefixLines("**") /* estilo del ejemplo: titulo en negrita */),
    tb("•", "Lista", () => prefixLines("- ")),
    tb("1.", "Lista numerada", () => prefixLines("1. ")),
    tb("❝", "Cita", () => prefixLines("> ")),
    tb("Enlace", "Enlace", () => insert("[", "](https://)", "texto")),
    tb("Imagen", "Subir imagen", () => fileInp.click()),
    tb("Tabla", "Insertar tabla", () => insertAtCursor("\n| Col1 | Col2 |\n|---|---|\n| a | b |\n")),
    h("span", { class: "mded-sp" }),
    (() => { const b = h("button", { class: "mded-tab active", type: "button" }, "Write"); b.dataset.role = "w"; return b; })(),
    (() => { const b = h("button", { class: "mded-tab", type: "button" }, "Preview"); b.dataset.role = "p"; return b; })(),
    fileInp
  );
  const wTab = bar.querySelector('[data-role="w"]'), pTab = bar.querySelector('[data-role="p"]');
  wTab.addEventListener("click", () => { ta.style.display = ""; prev.style.display = "none"; wTab.classList.add("active"); pTab.classList.remove("active"); });
  pTab.addEventListener("click", async () => {
    prev.innerHTML = "…";
    ta.style.display = "none"; prev.style.display = ""; pTab.classList.add("active"); wTab.classList.remove("active");
    try {
      const r = await api.post("/api/md", { text: ta.value, slug: S.slug }).then(x => x.json());
      prev.innerHTML = r.html || "<em>(vacío)</em>";
    } catch (_) { prev.innerHTML = "<em>error al renderizar</em>"; }
  });
  const box = h("div", { class: "mded" }, bar, ta, prev);
  return h("label", { class: "mdedlabel" }, label, box);
}

function reportEditor() {
  const m = S.data.meta;
  const wrap = h("div", {});
  wrap.append(h("h2", {}, t("report")));

  const c1 = h("div", { class: "card" }, h("h4", {}, t("cover_meta")));
  c1.append(field(t("report_title"), m, "report_title", { ph: t("report_title_ph") }));
  c1.append(field(t("subtitle"), m, "report_subtitle", { ph: t("subtitle_ph") }));
  const g = h("div", { class: "grid2" });
  g.append(field(t("client"), m, "client", { ph: t("client_ph") }), field(t("date"), m, "date", { type: "date" }),
           field(t("assessor"), m, "assessor", { ph: t("assessor_ph") }), field(t("assessor_title"), m, "assessor_title", { ph: t("assessor_title_ph") }),
           field(t("version"), m, "version", { ph: t("version_ph") }),
           field(t("osid"), m, "osid", { ph: t("osid_ph") }), field(t("email"), m, "email", { ph: t("email_ph") }));
  // diseño (theme) e idioma
  const themeSel = h("select", { onchange: e => { m.theme = e.target.value; scheduleSave(); } },
    ["serio", "corporativo", "offsec", "htb"].map(t => h("option", { value: t, selected: m.theme === t ? "" : null }, t)));
  const langSel = h("select", { onchange: e => { m.lang = e.target.value; scheduleSave(); } },
    ["es", "en"].map(t => h("option", { value: t, selected: m.lang === t ? "" : null }, t)));
  g.append(h("label", {}, t("design"), themeSel), h("label", {}, t("report_lang"), langSel));
  c1.append(g);
  const b = m.branding = m.branding || {};
  const g2 = h("div", { class: "grid2" });
  g2.append(field(t("wordmark"), b, "wordmark", { ph: t("wordmark_ph") }), field(t("byline"), b, "byline", { ph: t("byline_ph") }),
            field(t("conf_text"), b, "confidential_text"), field(t("accent"), b, "accent", { type: "color" }));
  g2.append(coverImgField(b, "cover_image", t("cover_image")), coverImgField(b, "logo", t("own_logo")), coverImgField(b, "client_logo", t("client_logo")));
  c1.append(g2);
  wrap.append(c1);
  wrap.append(noteCard(t("contacts_scope_note")));
  return wrap;
}

function inlineField(obj, key, ph) {
  return h("input", { value: obj[key] || "", placeholder: ph, oninput: e => { obj[key] = e.target.value; scheduleSave(); } });
}
function listCard(title, arr, factory, rowFields) {
  const card = h("div", { class: "card" }, h("h4", {}, title));
  arr.forEach((row, i) => {
    const r = h("div", { class: "row" });
    rowFields(row).forEach(x => r.append(x));
    r.append(h("button", { class: "btn sm danger", onclick: () => { arr.splice(i, 1); scheduleSave(); renderMain(); } }, "✕"));
    card.append(r);
  });
  card.append(h("button", { class: "btn sm", onclick: () => { arr.push(factory()); scheduleSave(); renderMain(); } }, t("add_row")));
  return card;
}

// ---- finding editor --------------------------------------------------------
function findingEditor(f) {
  const wrap = h("div", {});
  const head = h("h2", {}, `${f.id} `);
  const modeSel = h("select", { style: "width:auto;display:inline-block;margin-left:8px", onchange: e => { f.mode = e.target.value; scheduleSave(); renderMain(); } },
    [["vuln", t("vuln")], ["machine", t("machine")]].map(o => h("option", { value: o[0], selected: f.mode === o[0] ? "" : null }, o[1])));
  head.append(modeSel);
  head.append(h("button", { class: "btn sm", style: "float:right;margin-left:8px", onclick: () => {
    const copy = JSON.parse(JSON.stringify(f)); copy.id = nextFid();
    S.data.findings.splice(S.sel.idx + 1, 0, copy); renumberFindings(); scheduleSave(); select("finding", S.sel.idx + 1);
  } }, t("duplicate_finding")));
  head.append(h("button", { class: "btn sm danger", style: "float:right", onclick: () => { if (!confirm(t("delete_finding_confirm"))) return; S.data.findings.splice(S.sel.idx, 1); renumberFindings(); S.sel = { type: "report", idx: -1 }; scheduleSave(); renderSidebar(); renderMain(); } }, t("delete_finding")));
  wrap.append(head);
  wrap.append(f.mode === "machine" ? machineEditor(f) : vulnEditor(f));
  if (S.focusTitle) { S.focusTitle = false; setTimeout(() => { const el = document.querySelector("#editor .card input"); if (el) el.focus(); }, 0); }
  return wrap;
}

function parseCweId(s) { const m = String(s || "").match(/(\d+)/); return m ? m[1] : null; }
function cweField(f) {
  const wrap = h("label", { style: "position:relative" }, t("cwe"));
  const help = h("div", { class: "cwe-help" });
  const menu = h("div", { class: "cwe-ac" });
  function detect() {
    const id = parseCweId(f.cwe), name = id && S.cwe ? S.cwe[id] : null;
    help.textContent = id ? (name ? `CWE-${id}: ${name}` : `CWE-${id}: ${t("cwe_notfound")}`) : "";
  }
  function closeMenu() { menu.innerHTML = ""; menu.style.display = "none"; }
  function openMatches(q) {
    q = (q || "").trim().toLowerCase();
    if (!q) { closeMenu(); return; }
    const matches = Object.entries(S.cwe || {})
      .filter(([id, name]) => id.includes(q) || name.toLowerCase().includes(q)).slice(0, 12);
    menu.innerHTML = "";
    if (!matches.length) { closeMenu(); return; }
    matches.forEach(([id, name]) => {
      const it = h("div", { class: "cwe-ac-item",
        onmousedown: e => { e.preventDefault(); f.cwe = `CWE-${id} \u2014 ${name}`; inp.value = f.cwe; closeMenu(); detect(); scheduleSave(); } },
        h("span", { class: "cwe-ac-id" }, `CWE-${id}`), " ", name);
      menu.append(it);
    });
    menu.style.display = "block";
  }
  const inp = h("input", { value: f.cwe || "", placeholder: t("cwe_ph"),
    oninput: e => { f.cwe = e.target.value; scheduleSave(); detect(); openMatches(e.target.value); },
    onblur: () => setTimeout(closeMenu, 120),
    onchange: e => { const id = parseCweId(e.target.value), name = id && S.cwe ? S.cwe[id] : null;
      if (id && name) { f.cwe = `CWE-${id} \u2014 ${name}`; e.target.value = f.cwe; } scheduleSave(); detect(); } });
  wrap.append(inp, menu, help); detect(); closeMenu();
  return wrap;
}

function vulnEditor(f) {
  const box = h("div", {});
  const c = h("div", { class: "card" }, h("h4", {}, t("finding_data")));
  c.append(field(t("title"), f, "title"));
  // severidad + cvss
  const sevSel = h("select", { onchange: e => { f.severity = e.target.value; scheduleSave(); renderSidebar(); } },
    SEV.map(o => h("option", { value: o[0], selected: f.severity === o[0] ? "" : null }, o[1])));
  const g = h("div", { class: "grid2" });
  g.append(h("label", {}, "Severidad", sevSel), cweField(f), field(t("affected"), f, "affected"));
  c.append(g);
  c.append(cvssWidget(f, sevSel));
  box.append(c);

  const c2 = h("div", { class: "card" }, h("h4", {}, t("content")));
  c2.append(field(t("desc_root"), f, "description_md", { area: true, rows: 4 }));
  c2.append(field(t("impact"), f, "impact_md", { area: true, rows: 3 }));
  c2.append(field(t("remediation"), f, "remediation_md", { area: true, rows: 3 }));
  f.references = f.references || [];
  const refCard = h("div", {}, h("h4", {}, t("references")));
  f.references.forEach((r, i) => {
    const row = h("div", { class: "row" },
      h("input", { value: r, oninput: e => { f.references[i] = e.target.value; scheduleSave(); } }),
      h("button", { class: "btn sm danger", onclick: () => { f.references.splice(i, 1); scheduleSave(); renderMain(); } }, "✕"));
    refCard.append(row);
  });
  refCard.append(h("button", { class: "btn sm", onclick: () => { f.references.push(""); scheduleSave(); renderMain(); } }, t("add_ref")));
  c2.append(refCard);
  box.append(c2);

  // walkthrough
  f.walkthrough = f.walkthrough || [];
  box.append(stepsCard(t("procedure"), f.walkthrough));

  // remediation summary
  const rs = f.remediation_summary = f.remediation_summary || {};
  const c3 = h("div", { class: "card" }, h("h4", {}, t("rem_summary")));
  c3.append(field("Corto plazo", rs, "short_md"), field("Mediano plazo", rs, "medium_md"), field("Largo plazo", rs, "long_md"));
  box.append(c3);
  return box;
}

// Etiquetas de metricas 4.0 (solo UI; la logica vive en cvss40.js).
const CVSS_TIP = {
  AV: "Attack Vector: por donde se explota (Red/Adyacente/Local/Fisico)",
  AC: "Attack Complexity: condiciones para explotar (Baja/Alta)",
  AT: "Attack Requirements: prerrequisitos del ataque (Ninguno/Presente)",
  PR: "Privileges Required: privilegios previos (Ninguno/Bajo/Alto)",
  UI: "User Interaction: interaccion de la victima (Ninguna/Pasiva/Activa)",
  VC: "Confidencialidad del sistema vulnerable", VI: "Integridad del sistema vulnerable",
  VA: "Disponibilidad del sistema vulnerable", SC: "Confidencialidad de sistemas posteriores",
  SI: "Integridad de sistemas posteriores", SA: "Disponibilidad de sistemas posteriores",
  S: "Scope: cambio de alcance (Unchanged/Changed)", C: "Impacto en Confidencialidad",
  I: "Impacto en Integridad", A: "Impacto en Disponibilidad"
};
const CVSS4_BASE = ["AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA"];
const CVSS4_OPTS = {
  AV: [["N", "Network"], ["A", "Adjacent"], ["L", "Local"], ["P", "Physical"]],
  AC: [["L", "Low"], ["H", "High"]], AT: [["N", "None"], ["P", "Present"]],
  PR: [["N", "None"], ["L", "Low"], ["H", "High"]],
  UI: [["N", "None"], ["P", "Passive"], ["A", "Active"]],
  VC: [["H", "High"], ["L", "Low"], ["N", "None"]], VI: [["H", "High"], ["L", "Low"], ["N", "None"]],
  VA: [["H", "High"], ["L", "Low"], ["N", "None"]], SC: [["H", "High"], ["L", "Low"], ["N", "None"]],
  SI: [["H", "High"], ["L", "Low"], ["N", "None"]], SA: [["H", "High"], ["L", "Low"], ["N", "None"]],
};

function copyVectorBtn(vector) {
  const b = h("button", { class: "btn sm", style: "padding:3px 9px;flex:none", title: t("copy_vector"),
    onclick: () => { if (navigator.clipboard) navigator.clipboard.writeText(vector);
      const o = b.textContent; b.textContent = "\u2713"; setTimeout(() => { b.textContent = o; }, 1000); } }, "\u29C9");
  return b;
}
function applyPastedVector(f, raw, errEl) {
  let v = (raw || "").trim().replace(/\s+/g, "");  // admite espacios: "AV:N / AC:H" -> "AV:N/AC:H"
  if (!v) { errEl.textContent = ""; return; }
  let ver = f.cvss_version || "3.1";
  const mpref = v.match(/^CVSS:([0-9.]+)\//i);
  if (mpref) { ver = (mpref[1] === "4.0") ? "4.0" : (mpref[1].indexOf("3.") === 0 ? "3.1" : ver); v = v.slice(mpref[0].length); }
  const full = "CVSS:" + ver + "/" + v;
  try {
    if (ver === "4.0") {
      const r = window.CVSS40.score(full);
      f.cvss_version = "4.0"; f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity; f.macrovector = r.macrovector;
    } else {
      const r = cvssCompute(cvssParse(full));
      f.cvss_version = "3.1"; f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity;
    }
    errEl.textContent = ""; scheduleSave(); renderMain();
  } catch (_) { errEl.textContent = t("cvss_paste_bad"); }
}

function cvssWidget(f, sevSel) {
  f.cvss_version = f.cvss_version || "3.1";
  const wrap = h("div", { style: "margin-top:10px" });
  const verSel = h("select", { style: "width:auto;display:inline-block;margin-left:8px",
    onchange: e => {
      f.cvss_version = e.target.value;
      f.cvss = ""; f.cvss_vector = ""; f.macrovector = "";  // estado incompatible entre versiones
      scheduleSave(); renderMain();
    } },
    ["3.1", "4.0"].map(v => h("option", { value: v, selected: f.cvss_version === v ? "" : null }, "CVSS " + v)));
  wrap.append(h("h4", {}, t("calculator"), verSel));
  const pasteErr = h("span", { class: "cvss-paste-err" });
  const paste = h("input", { class: "cvss-paste", placeholder: t("cvss_paste_ph"), value: f.cvss_vector || "",
    onchange: e => applyPastedVector(f, e.target.value, pasteErr),
    onkeydown: e => { if (e.key === "Enter") applyPastedVector(f, e.target.value, pasteErr); } });
  wrap.append(h("label", { style: "margin-top:6px" }, t("cvss_paste_label"), h("div", { style: "display:flex;gap:8px;align-items:center" }, paste, pasteErr)));
  wrap.append(f.cvss_version === "4.0" ? cvss4Widget(f, sevSel) : cvss31Widget(f, sevSel));
  return wrap;
}

function cvss31Widget(f, sevSel) {
  const c = h("div", {});
  const bx = h("div", { class: "cvssbox" });
  const metrics = cvssParse(f.cvss_vector || "");
  const out = h("div", { class: "cvssout" });
  function refresh() {
    const r = cvssCompute(metrics);
    f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity;
    if (sevSel) sevSel.value = r.severity;
    out.innerHTML = "";
    out.append(h("span", { class: "cvss-score" }, r.score.toFixed(1)),
      h("span", { class: "tag sev-" + r.severity }, r.severity),
      h("span", { class: "cvss-vec" }, r.vector), copyVectorBtn(r.vector));
    scheduleSave(); renderSidebar();
  }
  CV.M.forEach(k => {
    const sel = h("select", { title: CVSS_TIP[k] || "", onchange: e => { metrics[k] = e.target.value; refresh(); } },
      CV.OPTS[k].map(o => h("option", { value: o[0], selected: metrics[k] === o[0] ? "" : null }, `${k}: ${o[1]}`)));
    bx.append(h("div", { class: "m" }, sel));
  });
  c.append(bx, out);
  const r0 = cvssCompute(metrics);
  out.append(h("span", { class: "cvss-score" }, r0.score.toFixed(1)),
    h("span", { class: "tag sev-" + r0.severity }, r0.severity),
    h("span", { class: "cvss-vec" }, r0.vector), copyVectorBtn(r0.vector));
  return c;
}

function cvss4Widget(f, sevSel) {
  const c = h("div", {});
  if (!window.CVSS40) { c.append(h("p", { class: "cvss-vec" }, "cvss40.js no cargado")); return c; }
  const C = window.CVSS40;
  const base = {};
  if ((f.cvss_vector || "").startsWith("CVSS:4.0/")) {
    try { const p = C.parseVector(f.cvss_vector); CVSS4_BASE.forEach(k => { base[k] = p[k]; }); } catch (_) { /* re-init */ }
  }
  CVSS4_BASE.forEach(k => { if (!base[k]) base[k] = CVSS4_OPTS[k][0][0]; });
  const bx = h("div", { class: "cvssbox" });
  const out = h("div", { class: "cvssout" });
  function draw(r) {
    out.innerHTML = "";
    out.append(h("span", { class: "cvss-score" }, r.score.toFixed(1)),
      h("span", { class: "tag sev-" + r.severity }, r.severity),
      h("span", { class: "cvss-vec" }, r.vector),
      h("span", { class: "cvss-vec" }, "MV " + r.macrovector), copyVectorBtn(r.vector));
  }
  function refresh() {
    const r = C.score(C.buildVector(base));  // toda la logica 4.0 en cvss40.js
    f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity; f.macrovector = r.macrovector;
    if (sevSel) sevSel.value = r.severity;
    draw(r); scheduleSave(); renderSidebar();
  }
  CVSS4_BASE.forEach(k => {
    const sel = h("select", { title: CVSS_TIP[k] || "", onchange: e => { base[k] = e.target.value; refresh(); } },
      CVSS4_OPTS[k].map(o => h("option", { value: o[0], selected: base[k] === o[0] ? "" : null }, `${k}: ${o[1]}`)));
    bx.append(h("div", { class: "m" }, sel));
  });
  c.append(bx, out);
  draw(C.score(C.buildVector(base)));
  return c;
}

function machineEditor(f) {
  const box = h("div", {});
  f.host = f.host || {};
  const c = h("div", { class: "card" }, h("h4", {}, t("host")));
  c.append(field(t("machine_name"), f, "title"));
  const g = h("div", { class: "grid2" });
  g.append(field(t("ip"), f.host, "ip", { ph: t("ip_ph") }), field(t("os"), f.host, "os", { ph: t("os_ph") }), field(t("ports"), f, "open_ports", { ph: t("ports_ph") }));
  c.append(g);
  c.append(field(t("attack_path"), f, "summary_md", { area: true, rows: 3, ph: t("attack_path_ph") }));
  c.append(h("p", { style: "color:var(--muted);font-size:13px;margin:8px 2px 0" }, t("machine_hint")));
  box.append(c);

  f.phases = f.phases || [];
  f.phases.forEach((ph, i) => {
    const pc = h("div", { class: "card" });
    const head = h("h4", {}, "");
    const nameInp = h("input", { value: ph.name || "", placeholder: t("phase_name_ph"), style: "max-width:60%;display:inline-block", oninput: e => { ph.name = e.target.value; scheduleSave(); } });
    head.append(t("phase") + " ", nameInp, h("button", { class: "btn sm danger", style: "float:right", onclick: () => { f.phases.splice(i, 1); scheduleSave(); renderMain(); } }, t("remove_phase")));
    pc.append(head);
    ph.steps = ph.steps || [];
    pc.append(stepsInner(ph.steps));
    box.append(pc);
  });
  box.append(h("button", { class: "btn sm", onclick: () => { f.phases.push({ name: "", steps: [] }); scheduleSave(); renderMain(); } }, t("add_phase")));

  f.proof = f.proof || [];
  box.append(listCard(t("evidence"), f.proof, () => ({ name: "", value: "" }),
    row => [inlineField(row, "name", t("ev_name")), inlineField(row, "value", t("ev_value"))]));
  return box;
}

function stepsCard(title, steps) {
  const card = h("div", { class: "card" }, h("h4", {}, title));
  card.append(stepsInner(steps));
  return card;
}
function stepsInner(steps) {
  const wrap = h("div", {});
  steps.forEach((s, i) => wrap.append(stepBlock(steps, s, i)));
  wrap.append(h("button", { class: "btn sm", onclick: () => { steps.push({}); scheduleSave(); renderMain(); } }, t("add_step")));
  return wrap;
}
function stepBlock(steps, s, i) {
  const b = h("div", { class: "block" });
  const head = h("div", { class: "block-head" },
    h("span", { class: "lbl" }, dragHandle(steps, i), " " + t("step") + " " + (i + 1)),
    h("span", {},
      h("button", { class: "btn sm", onclick: () => { if (i > 0) { steps.splice(i - 1, 0, steps.splice(i, 1)[0]); scheduleSave(); renderMain(); } } }, "↑"),
      h("button", { class: "btn sm", onclick: () => { if (i < steps.length - 1) { steps.splice(i + 1, 0, steps.splice(i, 1)[0]); scheduleSave(); renderMain(); } } }, "↓"),
      h("button", { class: "btn sm danger", onclick: () => { steps.splice(i, 1); scheduleSave(); renderMain(); } }, "✕")));
  b.append(head);
  makeDropZone(b, steps, i);
  b.append(field(t("lead"), s, "lead"));
  b.append(field(t("step_text"), s, "text_md", { area: true, rows: 3 }));
  b.append(field(t("code_block"), s, "command", { area: true, rows: 2 }));
  // figura
  const fig = s.figure || {};
  const figWrap = h("div", {});
  const file = h("input", { type: "file", accept: "image/*", onchange: e => uploadImage(e, s) });
  figWrap.append(h("label", {}, t("image"), file));
  if (fig.src) {
    figWrap.append(h("img", { class: "imgprev", src: `/api/projects/${S.slug}/${fig.src}` }));
    figWrap.append(h("input", { value: fig.caption || "", placeholder: t("caption_ph"), oninput: e => { s.figure.caption = e.target.value; scheduleSave(); } }));
    figWrap.append(h("button", { class: "btn sm danger", onclick: () => { delete s.figure; scheduleSave(); renderMain(); } }, t("remove_image")));
  }
  b.append(figWrap);
  return b;
}
async function uploadCover(e, b, key) {
  const file = e.target.files[0]; if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  setSaveState(t("saving"));
  const r = await fetch(`/api/projects/${S.slug}/image`, { method: "POST", body: fd }).then(x => x.json());
  b[key] = r.src; scheduleSave(); renderMain();
}
function coverImgField(b, key, label) {
  const wrap = h("label", {}, label);
  wrap.append(h("input", { type: "file", accept: "image/*", onchange: e => uploadCover(e, b, key) }));
  if (b[key]) wrap.append(h("button", { class: "btn sm danger", style: "margin-top:6px", onclick: () => { delete b[key]; scheduleSave(); renderMain(); } }, t("remove") + " · " + b[key].split("/").pop()));
  return wrap;
}
async function uploadImage(e, s) {
  const file = e.target.files[0]; if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  setSaveState(t("saving"));
  const r = await fetch(`/api/projects/${S.slug}/image`, { method: "POST", body: fd }).then(x => x.json());
  s.figure = { src: r.src, caption: (s.figure && s.figure.caption) || "" };
  scheduleSave(); renderMain();
}

// ---- OWASP + nuevo hallazgo ------------------------------------------------
function addFinding(kind) {
  if (!S.data) return;
  if (kind === "blank") {
    S.data.findings.push({ id: nextFid(), mode: "vuln", title: "", severity: "medium", cvss: "", cvss_vector: "" });
    S.focusTitle = true; finishAdd(); return;
  }
  openOwasp(kind);
}
function finishAdd() { renumberFindings(); scheduleSave(); const i = S.data.findings.length - 1; select("finding", i); }
function openOwasp(kind) {
  const cat = S.owasp[kind];
  $("#owaspTitle").textContent = cat.catalog;
  const list = $("#owaspList"); list.innerHTML = "";
  const es = (S.data.meta.lang || "es") === "es";
  cat.items.forEach(it => {
    list.append(h("li", {},
      h("div", { class: "oid" }, `${it.id}  ${es ? it.name_es : it.name}`),
      h("div", { class: "osum" }, es ? it.summary_es : it.summary),
      h("button", { class: "btn sm primary", onclick: () => insertOwasp(it) }, "Insertar como hallazgo")));
  });
  $("#owaspModal").classList.add("open");
}
function insertOwasp(it) {
  const es = (S.data.meta.lang || "es") === "es";
  S.data.findings.push({
    id: nextFid(), mode: "vuln",
    title: `${it.id} ${es ? it.name_es : it.name}`,
    severity: "high", cvss: "", cvss_vector: "",
    cwe: it.cwe || "", description_md: es ? it.summary_es : it.summary,
    references: it.ref ? [it.ref] : [],
  });
  $("#owaspModal").classList.remove("open");
  finishAdd();
}

// ---- preview / descarga ----------------------------------------------------
async function renderPdf(download) {
  if (!S.slug) return;
  setSaveState(t("updating"));
  const r = await fetch(`/api/projects/${S.slug}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
  if (!r.ok) { setSaveState(t("err")); const t = await r.json().catch(() => ({})); alert("Render: " + (t.error || r.status)); return; }
  const blob = await r.blob(); const url = URL.createObjectURL(blob);
  if (download) { const a = h("a", { href: url, download: (S.slug || "informe") + ".pdf" }); a.click(); }
  else { const f = $("#pdfPreview"); f.removeAttribute("sandbox"); f.removeAttribute("srcdoc"); f.setAttribute("src", url); }
  setSaveState(t("saved"));
}

async function exportFile() {
  if (!S.slug) return;
  const fmt = $("#exportFormat").value;
  setSaveState("exportando " + fmt + "…");
  const r = await fetch(`/api/projects/${S.slug}/export/${fmt}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
  if (!r.ok) { setSaveState(t("err")); const t = await r.json().catch(() => ({})); alert("Export: " + (t.error || r.status)); return; }
  const blob = await r.blob(); const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: (S.slug || "informe") + "." + fmt }); a.click();
  setSaveState("exportado (" + fmt + ")");
}

// ---- UI binding ------------------------------------------------------------
function sectionOrder(key) { return (S.catBy[key] || {}).order || 999; }
function enableSection(key) {
  const secs = S.data.report.sections;
  if (secs.find(s => s.key === key)) return;
  const ord = sectionOrder(key);
  let idx = secs.findIndex(s => sectionOrder(s.key) > ord);
  if (idx < 0) idx = secs.length;
  secs.splice(idx, 0, { key });
}
function disableSection(key) {
  const secs = S.data.report.sections;
  const i = secs.findIndex(s => s.key === key);
  if (i >= 0) secs.splice(i, 1);
  if (S.sel.type === "section" && S.sel.key === key) S.sel = { type: "report", idx: -1 };
}
function toggleSection(key, on) { on ? enableSection(key) : disableSection(key); scheduleSave(); renderSidebar(); openSectionsModal(); renderMain(); }
function openSectionsModal() {
  const cat = S.catalog, box = $("#sectionCatalog"); box.innerHTML = "";
  const lang = (S.data.meta.lang || "es");
  const enabled = new Set(S.data.report.sections.map(s => s.key));
  const groups = cat.groups || [...new Set(cat.sections.map(s => s.group))];
  groups.forEach(g => {
    const secs = cat.sections.filter(s => s.group === g).sort((a, b) => (a.order || 999) - (b.order || 999));
    if (!secs.length) return;
    box.append(h("div", { class: "grp" }, g));
    secs.forEach(s => {
      const cb = h("input", { type: "checkbox" });
      cb.checked = enabled.has(s.key);
      cb.addEventListener("change", () => toggleSection(s.key, cb.checked));
      box.append(h("label", { class: "optrow" }, cb,
        s["title_" + lang] || s.title_es,
        s.required ? h("span", { class: "req-badge" }, t("recommended")) : null,
        s.special ? h("span", { class: "sect-badge" }, " " + s.special) : null));
    });
  });
  $("#sectionsModal").classList.add("open");
}

function fillCertOptions(fam) {
  const cm = $("#mCert"); cm.innerHTML = "";
  const lg = S.uiLang || "es";
  (S.presets || []).filter(p => p.family === fam).forEach(p => cm.append(h("option", { value: p.id }, p["cert_" + lg] || p.cert_es || p.id)));
}
function selectedPresetId() {
  const v = $("#mPreset").value;
  return v.startsWith("family:") ? $("#mCert").value : v;
}
function refreshPresetDesc() {
  const v = $("#mPreset").value, fam = v.startsWith("family:") ? v.slice(7) : null;
  $("#mCertRow").style.display = fam ? "" : "none";
  if (fam && !$("#mCert").options.length) fillCertOptions(fam);
  const sel = (S.presets || []).find(p => p.id === selectedPresetId());
  const lg = S.uiLang || "es";
  const d = sel ? (sel["desc_" + lg] || sel.desc_es || "") : "";
  $("#mPresetDesc").textContent = d ? d + "  —  " + t("preset_note") : t("preset_note");
}
function populatePresetSelector() {
  const pm = $("#mPreset"); if (!pm) return;
  const lg = S.uiLang || "es";
  pm.innerHTML = ""; const seen = new Set();
  (S.presets || []).forEach(p => {
    if (p.family) { if (!seen.has(p.family)) { seen.add(p.family); pm.append(h("option", { value: "family:" + p.family }, t(p.family + "_family"))); } }
    else pm.append(h("option", { value: p.id }, p["name_" + lg] || p.name_es));
  });
  $("#mCert").innerHTML = "";
  refreshPresetDesc();
}
function bindUI() {
  $("#projectSelect").addEventListener("change", e => loadProject(e.target.value));
  $("#navReport").addEventListener("click", () => select("report", -1));
  document.querySelectorAll("[data-add]").forEach(b => b.addEventListener("click", () => addFinding(b.dataset.add)));
  {
    const si = $("#globalSearch"); let st = null;
    si.addEventListener("input", e => { clearTimeout(st); st = setTimeout(() => renderSearch(e.target.value), 120); });
    si.addEventListener("keydown", e => { if (e.key === "Escape") { si.value = ""; renderSearch(""); si.blur(); } });
    si.addEventListener("blur", () => setTimeout(() => $("#searchResults").classList.remove("open"), 150));
    si.addEventListener("focus", e => { if (e.target.value) renderSearch(e.target.value); });
  }
  $("#previewBtn").addEventListener("click", () => S.previewMode === "live" ? refreshLivePreview() : renderPdf(false));
  $("#previewToggle").addEventListener("click", () => setPreviewVisible(!S.previewVisible));
  { let v = true; try { v = localStorage.getItem("rg.previewVisible") !== "0"; } catch (_) {} setPreviewVisible(v); }
  $("#pvLive").addEventListener("click", () => setPreviewMode("live"));
  $("#pvPdf").addEventListener("click", () => setPreviewMode("pdf"));
  $("#langToggle").addEventListener("click", toggleUiLang);
  $("#downloadBtn").addEventListener("click", exportFile);
  $("#owaspCancel").addEventListener("click", () => $("#owaspModal").classList.remove("open"));
  $("#manageSections").addEventListener("click", openSectionsModal);
  $("#sectionsClose").addEventListener("click", () => $("#sectionsModal").classList.remove("open"));
  // nuevo proyecto
  $("#mPreset").addEventListener("change", () => { const v = $("#mPreset").value; if (v.startsWith("family:")) fillCertOptions(v.slice(7)); refreshPresetDesc(); });
  $("#mCert").addEventListener("change", refreshPresetDesc);
  populatePresetSelector();
  $("#newProjectBtn").addEventListener("click", () => { populatePresetSelector(); $("#newModal").classList.add("open"); });
  $("#deleteProjectBtn").addEventListener("click", deleteProject);
  $("#renameProjectBtn").addEventListener("click", renameProject);
  $("#mCancel").addEventListener("click", () => $("#newModal").classList.remove("open"));
  $("#mCreate").addEventListener("click", createProject);
  ["#mTitle", "#mClient", "#mSlug"].forEach(s => $(s).addEventListener("keydown", e => { if (e.key === "Enter") createProject(); }));
}
async function renameProject() {
  if (!S.slug || !S.data) return;
  const cur = (S.data.meta && S.data.meta.report_title) || "";
  const name = prompt(t("rename_prompt"), cur);
  if (name === null) return;
  const nm = name.trim();
  if (!nm) return;
  S.data.meta.report_title = nm;
  await api.put(`/api/projects/${S.slug}`, S.data);
  S.dirty = false;
  await refreshProjects();
  $("#projectSelect").value = S.slug;
  renderMain();
  if (S.previewVisible && S.previewMode === "live") refreshLivePreview();
}

async function deleteProject() {
  if (!S.slug) return;
  const proj = S.projects.find(p => p.slug === S.slug);
  const name = proj ? proj.title : S.slug;
  if (!confirm(t("delete_confirm").replace("{n}", name))) return;
  await api.del(`/api/projects/${S.slug}`);
  await refreshProjects();
  if (S.projects.length) {
    loadProject(S.projects[0].slug);
  } else {
    S.slug = null; S.data = null; S.sel = { type: "report", idx: -1 };
    $("#projectSelect").innerHTML = "";
    renderSidebar(); renderMain();
    updateDeleteBtn();
  }
}

function updateDeleteBtn() {
  const b = $("#deleteProjectBtn"); if (b) b.disabled = !S.slug;
  const r = $("#renameProjectBtn"); if (r) r.disabled = !S.slug;
}

async function createProject() {
  const body = { model: $("#mLang").value, preset: selectedPresetId(), title: $("#mTitle").value, client: $("#mClient").value, slug: $("#mSlug").value };
  const r = await api.post("/api/projects", body);
  if (!r.ok) { const resp = await r.json().catch(() => ({})); alert(resp.error || t("create_fail")); return; }
  const { slug } = await r.json();
  $("#newModal").classList.remove("open");
  $("#mTitle").value = $("#mClient").value = $("#mSlug").value = "";
  await refreshProjects(); loadProject(slug);
}

init().catch(e => { console.error(e); }).finally(() => { try { hideSplash(); } catch (_) {} });

// ---- helpers ---------------------------------------------------------------
const $ = s => document.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const k in (attrs || {})) {
    if (k === "class") e.className = attrs[k];
    else if (k === "html") e.innerHTML = attrs[k];
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
    else if (attrs[k] != null) e.setAttribute(k, (k==='src'||k==='href')?scopedResourceURL(attrs[k]):attrs[k]);
  }
  for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
// ---- shared transport and preview interfaces -------------------------------
const transport = ReportTransport.create({
  fetch: (...args) => fetch(...args), workspace: BrowserWorkspace,
  getLanguage: () => S.uiLang, getETag: () => projectStore.etag,
  baseURL: () => location.href,
  onWorkspaceChanged(message) {
    let notice = document.querySelector('[data-workspace-changed]');
    if (!notice) {
      notice = h('p', {'data-workspace-changed':'', class:'wf-error', role:'alert'});
      document.querySelector('.workspace-toolbar')?.append(notice);
    }
    notice.textContent = message;
  },
});
const {request: appFetch, scopedResourceURL, requireOk, api} = transport;
const {invalidateLivePreview, previewPaneVisible, ensureLivePreview, refreshLivePreview,
  setPreviewVisible, setPreviewMode, renderPdf} = PreviewController;

// ---- estado ----------------------------------------------------------------
const S = { designs: [], projects: [], slug: null, data: null, sel: { type: "report", idx: -1 }, owasp: {}, cwe: {}, presets: [], uiLang: "es", previewMode: "live", previewVisible: true };

// ---- i18n del sitio -------------------------------------------------------
const I18N = {
  es: {
    new_project:"Nuevo proyecto", new_project_start:"Paso 2 de 2. Revisa la plantilla y completa los datos del proyecto.", new_project_options:"Cambiar la estructura inicial", new_project_library:"Volver a la galería", delete:"Eliminar", delete_title:"Eliminar el proyecto actual",
    hide_preview:"Ocultar vista previa", show_preview:"Mostrar vista previa", preview_toggle_title:"Mostrar u ocultar la vista previa",
    ui_lang_title:"Idioma del sitio", validate_title:"Validar informe", translating:"Actualizando\u2026", toast_created:"Proyecto creado", toast_exported:"Exportado", toast_copied:"Copiado", exporting:"Generando", validate_ok:"Sin avisos", validate_issues:"aviso(s)", dash_sort_sev:"Severidad", dash_sort_manual:"Manual", dash_incomplete:"CVSS o CWE sin registrar (opcionales). No impide exportar.", theme_light:"Tema claro", theme_dark:"Tema oscuro", update_preview:"Actualizar vista previa", export:"Exportar",
    rename:"Renombrar", rename_title:"Cambiar el nombre del proyecto (título del informe)", rename_prompt:"Nuevo nombre del proyecto:",
 credit_by:"Desarrollado por", recommended:"recomendada", sec_title:"Título de la sección", sec_body:"Contenido (Markdown)", lang_label:"Idioma", cert_label:"Certificación", htb_family:"HTB (certificación)", preset_label:"Plantilla", preset_note:"Los nombres «estilo OSCP/HTB» son descriptivos; no afiliado a OffSec ni Hack The Box.",
    search_ph:"Buscar en el proyecto\u2026", search_none:"Sin resultados",
    export_format_title:"Formato de exportacion", project_title:"Proyecto",
    loading:"cargando…", restore:"Restaurar", restore_title:"Restaurar la versión anterior", restore_pending:"Guarda tus cambios antes de restaurar", markdown_bundle:"Markdown + imágenes (ZIP)", saved:"guardado", saving:"guardando\u2026", ready:"listo", uptodate:"al dia", updating:"actualizando\u2026", err:"error",
    report:"Informe", sections_head:"Secciones del informe", manage_sections:"Gestionar secciones",
    findings_head:"Hallazgos", add_finding:"Anadir hallazgo", blank:"En blanco",
    empty:"Crea un proyecto con \u00abNuevo proyecto\u00bb (arriba) o elige uno del desplegable.",
    cover_meta:"Portada / Metadatos", report_title:"Titulo del informe", subtitle:"Subtitulo", client:"Cliente",
    subtitle_ph:"ej. Informe de hallazgos \u2014 App web", assessor_ph:"ej. Nombre Apellido",
    assessor_title_ph:"ej. Ethical Hacker / Pentester", version_ph:"ej. 1.0",
    osid:"ID del evaluador", osid_ph:"ej. OS-12345 (opcional)", email_ph:"ej. nombre@ejemplo.com",
    wordmark_ph:"ej. tu marca", byline_ph:"ej. Nombre / marca", target_ph:"ej. https://app.cliente.com",
    date:"Fecha (YYYY-MM-DD)", assessor:"Evaluador", assessor_title:"Cargo del evaluador", version:"Version",
    design:"Diseño", report_lang:"Idioma", wordmark:"Marca de texto", byline:"Autoría (pie)",
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
    dash_sev:"Severidad", dash_finding:"Hallazgo", dash_cwe:"CWE", dash_cvss:"CVSS", dash_empty:"Aún no hay hallazgos. Añade uno desde «Añadir hallazgo».", dash_machine:"Máquina",
    note_appendix:"La tabla de evidencias (hosts, flags, hashes) se genera desde los hallazgos; arriba puedes anadir apendices en texto.", report_title_ph:"Evaluacion de Seguridad ...", client_ph:"Cliente Ltd.",
    slug_label:"Nombre de carpeta (slug)", slug_ph:"cliente-2026", cancel:"Cancelar", create:"Crear", close:"Cerrar",
    sections_modal_h:"Secciones del informe", sections_hint:"Activa las secciones que necesites. Las obligatorias no se pueden desmarcar.",
    done:"Listo", preview_head:"Vista previa", live:"HTML",
    delete_finding_confirm:"¿Eliminar este hallazgo?", copy_vector:"Copiar vector", copied:"Copiado",
    copy_vector_failed:"No se pudo copiar. Selecciona el vector y cópialo manualmente.",
    cvss_paste_label:"Pegar vector", cvss_paste_ph:"pega un vector completo (con o sin CVSS:x.x/) y calcula solo",
    cvss_paste_bad:"vector inválido para esta versión", duplicate_finding:"Duplicar", save_to_lib:"\u2605 Plantilla", lib_open:"\u2605 Biblioteca", lib_title:"Biblioteca de hallazgos", lib_empty:"No hay plantillas guardadas. Usa \u201c\u2605 Plantilla\u201d en un hallazgo.", lib_insert:"Insertar", lib_delete:"Eliminar", lib_saved:"Guardado en biblioteca", export_findings:"\u21e3 Exportar", import_findings:"\u21e1 Importar", findings_imported:"hallazgo(s) importado(s)", lib_name_prompt:"Nombre de la plantilla:",
    unsaved:"Hay cambios sin guardar. ¿Salir de todas formas?",
    create_fail:"No se pudo crear", delete_confirm:"Eliminar el proyecto \"{n}\"?\nEsto borra su informe y sus imagenes de forma permanente."
  },
  en: {
    new_project:"New project", new_project_start:"Step 2 of 2. Review your design and enter the project details.", new_project_options:"Change the starter structure", new_project_library:"Back to gallery", delete:"Delete", delete_title:"Delete the current project",
    hide_preview:"Hide preview", show_preview:"Show preview", preview_toggle_title:"Show or hide the preview",
    ui_lang_title:"Site language", validate_title:"Validate report", translating:"Updating\u2026", toast_created:"Project created", toast_exported:"Exported", toast_copied:"Copied", exporting:"Generating", validate_ok:"No warnings", validate_issues:"warning(s)", dash_sort_sev:"Severity", dash_sort_manual:"Manual", dash_incomplete:"CVSS or CWE not recorded (optional). Export remains available.", theme_light:"Light theme", theme_dark:"Dark theme", update_preview:"Refresh preview", export:"Export",
    rename:"Rename", rename_title:"Rename the project (report title)", rename_prompt:"New project name:",
 credit_by:"Developed by", recommended:"recommended", sec_title:"Section title", sec_body:"Content (Markdown)", lang_label:"Language", cert_label:"Certification", htb_family:"HTB (certification)", preset_label:"Template", preset_note:"«OSCP/HTB-style» names are descriptive; not affiliated with OffSec or Hack The Box.",
    search_ph:"Search the project\u2026", search_none:"No results",
    export_format_title:"Export format", project_title:"Project",
    loading:"loading…", restore:"Restore", restore_title:"Restore the previous version", restore_pending:"Save your changes before restoring", markdown_bundle:"Markdown + images (ZIP)", saved:"saved", saving:"saving\u2026", ready:"ready", uptodate:"up to date", updating:"updating\u2026", err:"error",
    report:"Report", sections_head:"Report sections", manage_sections:"Manage sections",
    findings_head:"Findings", add_finding:"Add finding", blank:"Blank",
    empty:"Create a project with \u00abNew project\u00bb (top) or pick one from the dropdown.",
    cover_meta:"Cover / Metadata", report_title:"Report title", subtitle:"Subtitle", client:"Client",
    subtitle_ph:"e.g. Findings report \u2014 Web app", assessor_ph:"e.g. First Last",
    assessor_title_ph:"e.g. Ethical Hacker / Pentester", version_ph:"e.g. 1.0",
    osid:"Assessor ID", osid_ph:"e.g. OS-12345 (optional)", email_ph:"e.g. name@example.com",
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
    dash_sev:"Severity", dash_finding:"Finding", dash_cwe:"CWE", dash_cvss:"CVSS", dash_empty:"No findings yet. Add one from \u00abAdd finding\u00bb.", dash_machine:"Machine",
    note_appendix:"The evidence table (hosts, flags, hashes) is generated from the findings; above you can add text appendices.", report_title_ph:"Security Assessment ...", client_ph:"Client Ltd.",
    slug_label:"Folder name (slug)", slug_ph:"client-2026", cancel:"Cancel", create:"Create", close:"Close",
    sections_modal_h:"Report sections", sections_hint:"Enable the sections you need. Required ones cannot be unchecked.",
    done:"Done", preview_head:"Preview", live:"Live",
    delete_finding_confirm:"Delete this finding?", copy_vector:"Copy vector", copied:"Copied",
    copy_vector_failed:"Could not copy. Select the vector and copy it manually.",
    cvss_paste_label:"Paste vector", cvss_paste_ph:"paste a full vector (with or without CVSS:x.x/) and it auto-calculates",
    cvss_paste_bad:"invalid vector for this version", duplicate_finding:"Duplicate", save_to_lib:"\u2605 Template", lib_open:"\u2605 Library", lib_title:"Findings library", lib_empty:"No saved templates yet. Use \u201c\u2605 Template\u201d on a finding.", lib_insert:"Insert", lib_delete:"Delete", lib_saved:"Saved to library", export_findings:"\u21e3 Export", import_findings:"\u21e1 Import", findings_imported:"finding(s) imported", lib_name_prompt:"Template name:",
    unsaved:"You have unsaved changes. Leave anyway?",
    create_fail:"Could not create", delete_confirm:"Delete project \"{n}\"?\nThis permanently removes its report and images."
  }
};
function t(key) { const L = S.uiLang || "es"; return (I18N[L] && I18N[L][key]) || I18N.es[key] || key; }
function applyStaticI18n() {
  WorkflowUI.updateNav();
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.getAttribute("data-i18n")); });
  document.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.getAttribute("data-i18n-title")); });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.getAttribute("data-i18n-ph")); });
  document.documentElement.lang = S.uiLang || "es";
  renderProjectSelect();
  if (S.formats) {
    const format = $("#exportFormat"), selected = format.value;
    format.replaceChildren(...S.formats.map(spec => h("option", {value:spec.key}, spec["label_"+(S.uiLang === "en" ? "en" : "es")])));
    if (S.formats.some(spec => spec.key === selected)) format.value = selected;
  }
}
function setUiLang(lang) {
  invalidateValidation();
  S.uiLang = lang;
  try { localStorage.setItem("rg.uiLang", lang); } catch (_) {}
  const b = document.getElementById("langToggle"); if (b) b.textContent = lang.toUpperCase();
  applyStaticI18n();
  if(typeof PreviewZoomUI!=="undefined")PreviewZoomUI.update();
  const pb = document.getElementById("previewToggle"); if (pb) pb.textContent = S.previewVisible ? t("hide_preview") : t("show_preview");
  // Interface language is a preference. Report language is edited explicitly in metadata.
  renderSidebar(); renderMain();
  if (S.previewVisible && S.previewMode === "live") refreshLivePreview();
}
function toggleUiLang() { setUiLang(S.uiLang === "en" ? "es" : "en"); }

const SEV_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
const SEV = [["critical", "Crítica"], ["high", "Alta"], ["medium", "Media"], ["low", "Baja"], ["info", "Informativa"]];
function severityLabel(key) {
  if (!key) return S.uiLang === "en" ? "Pending assessment" : "Pendiente de valoración";
  return S.uiLang === "en" ? ({critical:"Critical",high:"High",medium:"Medium",low:"Low",info:"Informational"}[key] || key) : (SEV.find(s=>s[0]===key)?.[1] || key);
}

// ---- reordenar arrastrando --------------------------------------------------
let dragCtx = null;
function dragHandle(arr, i) {
  return h("span", { class: "drag", draggable: "true", title: S.uiLang==="en"?"Drag to reorder":"Arrastrar para reordenar",
    ondragstart: e => { dragCtx = { arr, from: i }; e.dataTransfer.effectAllowed = "move"; e.stopPropagation(); } }, "\u283F");
}
function makeDropZone(el, arr, i) {
  el.addEventListener("dragover", e => { if (dragCtx && dragCtx.arr === arr) { e.preventDefault(); el.classList.add("dragover"); } });
  el.addEventListener("dragleave", () => el.classList.remove("dragover"));
  el.addEventListener("drop", e => {
    el.classList.remove("dragover");
    if (dragCtx && dragCtx.arr === arr && dragCtx.from !== i) {
      e.preventDefault();
      UndoUI.move(arr,dragCtx.from,i);
      const wasFindings = arr === S.data.findings;
      dragCtx = null;
      if (wasFindings) { ensureFindingIds(); S.sel = { type: "finding", idx: i }; }
      scheduleSave(); renderSidebar(); renderMain();
    }
  });
}
function ensureFindingIds() {
  const rows=S.data.findings||[];
  const sequence=findingSequence(S.data), missing=rows.filter(f=>!f.id).length;
  if (missing > Number.MAX_SAFE_INTEGER-sequence) throw findingSequenceError();
  S.data.finding_sequence=sequence;
  rows.forEach(f=>{if(!f.id)f.id=nextFid();f.uid=f.uid||WorkflowUI.uid();});
}

const projectStore = new ProjectStore(appFetch, (state, error) => {
  S.dirty = projectStore.dirty;
  if (state === "loaded") return;
  if(typeof ProgressUI!=="undefined")ProgressUI.saveState(state,error);
  else setSaveState(t(state === "error" ? "err" : state));
  if (state === "saved" && !projectStore.loading) {
    const opt = [...$("#projectSelect").options].find(o => o.value === S.slug);
    if (opt && S.data) opt.textContent = S.data.meta.report_title || S.slug;
    if (S.previewVisible && S.previewMode === "live") refreshLivePreview();
  }
  if (error) toast(error.message, "err");
});
window.addEventListener("beforeunload", e => { if (projectStore.dirty) { e.preventDefault(); e.returnValue = t("unsaved"); } });
function scheduleSave() {
  invalidateValidation();
  if(typeof WorkbenchUI!=="undefined")WorkbenchUI.dirty();
  projectStore.data = S.data;
  projectStore.changed();
  if(typeof RetestMatrixUI!=="undefined")RetestMatrixUI.invalidate();
  if(typeof RemediationUI!=="undefined")RemediationUI.invalidate();
  if(typeof RetestDiffUI!=="undefined")RetestDiffUI.invalidate();
}
async function doSave() {
  try {
    await projectStore.save();
    const opt = [...$("#projectSelect").options].find(o => o.value === S.slug);
    if (opt && S.data) opt.textContent = S.data.meta.report_title || S.slug;
    if (S.previewMode === "live") refreshLivePreview();
    return true;
  } catch (_) { return false; }
}
let projectBusyCount = 0;
function busyProject(busy) {
  projectBusyCount = Math.max(0, projectBusyCount + (busy ? 1 : -1));
  const active = projectBusyCount > 0;
  document.querySelector(".layout").inert = active;
  ["#projectSelect", "#newProjectBtn", "#renameProjectBtn", "#deleteProjectBtn", "#restoreProjectBtn", "#importProjectBtn", "#langToggle", "#demoBtn", "#deliveryBtn", "#designLibraryBtn", "#workspaceBackupBtn", "#previewBtn", "#previewToggle", "#validateBtn", "#downloadBtn", "#exportFormat"].forEach(id => { const el = $(id); if (el) el.disabled = active; });
  if(typeof WorkspaceUI!=='undefined')WorkspaceUI.update();
}
function setSaveState(t) { if(typeof ProgressUI==="undefined")$("#saveState").textContent = t; }
function toast(msg, kind) {
  let host = document.getElementById("toastHost");
  if (!host) { host = h("div", { id: "toastHost" }); document.body.append(host); }
  const el = h("div", { class: "toast" + (kind ? " toast-" + kind : ""), role: kind === "err" ? "alert" : "status" }, msg);
  host.append(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => { el.classList.add("hide"); setTimeout(() => el.remove(), 320); }, 2200);
}
function openModal(modal) {
  if (modal.open) return;
  modal._opener = document.activeElement;
  if (!modal._focusBound) {
    modal._focusBound = true;
    modal.addEventListener("close", () => {
      modal.classList.remove("open");
      const previous = modal._opener;
      const target = previous?.closest("details:not([open])")?.querySelector("summary") || previous;
      (target?.isConnected && !target.disabled ? target : $("#editor"))?.focus({preventScroll:true});
    });
    modal.closeModal = () => modal.close();
  }
  modal.classList.add("open");
  modal.showModal();
}
function closeModal(modal) { if (modal.open) modal.close(); }
function applyUiTheme(mode) {
  document.documentElement.setAttribute("data-theme", mode);
  try { localStorage.setItem("rg.uiTheme", mode); } catch (_) {}
  const b = $("#themeToggle"); if (b) { b.textContent = mode === "light" ? "\u2600" : "\u263e"; b.title = t(mode === "light" ? "theme_dark" : "theme_light"); b.setAttribute("aria-label",b.title); }
}
function toggleUiTheme() {
  const cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  applyUiTheme(cur === "light" ? "dark" : "light");
}
let validationGeneration = 0;
function invalidateValidation() {
  validationGeneration++;
  const badge = $("#validateBtn");
  if (badge) { badge.classList.remove("has-err", "has-warn", "ok"); badge.textContent = "\u2713"; badge.removeAttribute('aria-busy'); }
  const modal = $("#validateModal");
  if (modal) { closeModal(modal); modal.remove(); }
}
async function runValidation() {
  if (!S.data) return;
  const badge = $("#validateBtn"), generation = ++validationGeneration;
  const slug = S.slug, data = S.data, revision = projectStore.revision, language = S.uiLang;
  const current = () => generation === validationGeneration && slug === S.slug && data === S.data && revision === projectStore.revision && language === S.uiLang;
  badge.setAttribute('aria-busy', 'true');
  try {
    const r = await appFetch("/api/validate?lang=" + (S.uiLang || "es"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
    await requireOk(r);
    const d = await r.json(); const issues = d.issues || [];
    if (!current()) return;
    badge.classList.remove("has-err", "has-warn", "ok");
    if (!issues.length) { badge.classList.add("ok"); badge.textContent = "\u2713"; toast(t("validate_ok"), "ok"); return; }
    const errs = issues.filter(i => i.level === "error").length;
    badge.classList.add(errs ? "has-err" : "has-warn");
    badge.textContent = String(issues.length);
    showValidationPanel(issues);
  } catch (error) { if (current()) toast(error.message, "err"); }
  finally { if (current()) badge.removeAttribute('aria-busy'); }
}
function showValidationPanel(issues) {
  let m = document.getElementById("validateModal");
  if (m) { closeModal(m); m.remove(); }
  const list = h("div", { class: "val-list" });
  issues.forEach(i => list.append(h("div", { class: "val-item val-" + i.level },
    h("span", { class: "val-lvl" }, i.level === "error" ? "\u2715" : "!"),
    h("span", {}, i.message))));
  m = h("dialog", { id: "validateModal", class: "modal", "aria-labelledby":"validateModalTitle", onclick: e => { if (e.target === m) closeModal(m); } },
    h("div", { class: "modal-box" },
      h("div", { id:"validateModalTitle", class: "modal-title" }, issues.length + " " + t("validate_issues")),
      list,
      h("div", { class: "modal-actions" }, h("button", { class: "btn", onclick: () => closeModal(m) }, "OK"))));
  m.addEventListener("close", () => m.remove());
  document.body.append(m);
  openModal(m);
}
function setPvStatus(t) { $("#pvStatus").textContent = t; }

function updateLangBtn() {
  $("#langToggle").textContent = (S.uiLang || "es").toUpperCase();
}

// ---- carga -----------------------------------------------------------------

async function init() {
  const sessionInfo = await api.get("/api/session");
  S.workspace_id=transport.bindSession(sessionInfo);
  S.version=sessionInfo.version;
  $(".brand-caption").textContent="Pentest reporting / v"+S.version;
  S.formats = await api.get("/api/export-formats");
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
  if(typeof ProgressUI!=="undefined")ProgressUI.bind();
  if(typeof WorkbenchUI!=="undefined")WorkbenchUI.bind();
  StudioUI.bind();
  if(typeof GuideUI!=="undefined")GuideUI.bind();
  if(typeof InsightsUI!=="undefined")InsightsUI.bind();
  if(typeof PreviewZoomUI!=="undefined")PreviewZoomUI.bind();
  { let l = ["es","en"].includes(sessionInfo.ui_language) ? sessionInfo.ui_language : "es"; try { const stored = localStorage.getItem("rg.uiLang"); if (["es","en"].includes(stored)) l = stored; } catch (_) {} S.uiLang = l; }
  { let th = "dark"; try { th = localStorage.getItem("rg.uiTheme") || "dark"; } catch (_) {} applyUiTheme(th); }
  updateLangBtn(); applyStaticI18n();
  if(typeof PreviewZoomUI!=="undefined")PreviewZoomUI.update();
  if(typeof ProgressUI!=="undefined")ProgressUI.update();
  const firstActiveProject = S.projects.find(project => !project.archived);
  if (firstActiveProject) loadProject(firstActiveProject.slug);
  else renderMain();
  hideSplash();
}
function hideSplash() {
  document.querySelectorAll('.topbar[inert],.layout[inert],.skip-link[inert],.app-credit[inert]').forEach(node=>node.removeAttribute('inert'));
  const s = document.getElementById("splash");
  if (!s) return;
  s.remove();
}
async function refreshProjects() {
  S.projects = await api.get("/api/projects");
  renderProjectSelect();
}
function renderProjectSelect() {
  const sel = $("#projectSelect");
  if (!sel) return;
  const selected = S.slug || sel.value;
  sel.innerHTML = "";
  S.projects.forEach(p => sel.append(h("option", { value: p.slug }, (p.title || p.slug)+(p.archived?" ["+(S.uiLang==='en'?'Archived':'Archivado')+"]":""))));
  if (S.projects.some(project => project.slug === selected)) sel.value = selected;
}
async function loadProject(slug) {
  if (projectStore.loading) return;
  invalidateValidation();
  if(typeof WorkbenchUI!=="undefined")WorkbenchUI.position();
  invalidateLivePreview();
  busyProject(true);
  try {
    if (!await projectStore.load(slug)) return;
    S.slug = projectStore.slug; S.data = projectStore.data; S.dashFilter = null;
    S.data.findings ||= []; S.data.report ||= { sections: [] }; S.data.report.sections ||= [];
    if(typeof WorkbenchUI!=="undefined")WorkbenchUI.projectChanged();
    S.sel = { type: typeof WorkspaceUI!=='undefined' ? "home" : "report", idx: -1 };
    $("#projectSelect").value = S.slug;
    renderSidebar(); renderMain(); updateLangBtn();
    PreviewController.clearDocument();
    if (S.previewMode === "live") refreshLivePreview();
    else renderPdf(false);
  } catch (_) { $("#projectSelect").value = S.slug || ""; }
  finally { busyProject(false); updateDeleteBtn(); StudioUI.recovery(); }
}

// ---- sidebar ---------------------------------------------------------------
const findingPageState = { slug:null, sidebar:0, board:0, boardKey:"" };
function workspacePageBar(area, total, page, size, change) {
  const pages=Math.max(1,Math.ceil(total/size)), english=S.uiLang==="en";
  const nav=h("nav",{class:"workspace-pagebar","data-workspace-pagination":area,"aria-label":english?"Pagination":"Paginación"});
  const update=next=>{change(Math.max(0,Math.min(pages-1,next)));requestAnimationFrame(()=>document.querySelector('[data-workspace-pagination="'+area+'"] select')?.focus({preventScroll:true}));};
  const selectPage=h("select",{"aria-label":english?"Choose page":"Elegir página",onchange:e=>update(Number(e.target.value))},Array.from({length:pages},(_,index)=>h("option",{value:index,selected:index===page?"":null},String(index+1)+" / "+pages)));
  nav.append(h("span",{class:"workspace-pagebar-count",role:"status"},total?String(page*size+1)+"–"+Math.min(total,(page+1)*size)+(english?" of ":" de ")+total:(english?"0 items":"0 elementos")),
    h("button",{type:"button",class:"btn sm","aria-label":english?"Previous page":"Página anterior",disabled:page===0?"":null,onclick:()=>update(page-1)},"‹"),selectPage,
    h("button",{type:"button",class:"btn sm","aria-label":english?"Next page":"Página siguiente",disabled:page===pages-1?"":null,onclick:()=>update(page+1)},"›"));
  return nav;
}
function renderSidebar(pageOverride) {
  WorkflowUI.updateNav();
  $("#navReport").classList.toggle("active", S.sel.type === "report");
  // secciones activas
  const sl = $("#sectionList"); sl.innerHTML = "";
  const secs = (S.data && S.data.report && S.data.report.sections) || [];
  secs.forEach((sec, i) => {
    const schema = S.catBy[sec.key] || {};
    const lang = (S.data.meta.lang || "en");
    const title = sec.title || schema["title_" + lang] || schema.title_es || sec.key;
    const active = S.sel.type === "section" && S.sel.key === sec.key;
    const li = h("li", { draggable: "true", class: active ? "active" : "" },
      h("button", {type:"button",class:"finding-nav","aria-current":active?"page":null,onclick:()=>select("section",sec.key)},
      h("span", { class: "ftitle" }, `${i + 1}. ${title}`),
      schema.special ? h("span", { class: "sect-badge" }, schema.special) : null));
    li.addEventListener("dragstart", e => { dragCtx = { arr: secs, from: i }; e.dataTransfer.effectAllowed = "move"; });
    makeDropZone(li, secs, i);
    if(secs.length>1)li.append(h("button",{type:"button",class:"btn sm","data-section-move":sec.key,"aria-label":(S.uiLang==="en"?"Move ":"Mover ")+title,onclick:()=>moveFindingDialog(sec.key,true)},S.uiLang==="en"?"Move":"Mover"));
    sl.append(li);
  });
  // hallazgos
  const ul = $("#findingList"); ul.innerHTML = "";
  ul.parentElement.querySelector('[data-workspace-pagination="sidebar"]')?.remove();
  const findings=S.data?.findings||[], pageSize=50;
  if(findingPageState.slug!==S.slug){findingPageState.slug=S.slug;findingPageState.sidebar=0;findingPageState.board=0;findingPageState.boardKey="";}
  if(Number.isInteger(pageOverride))findingPageState.sidebar=pageOverride;
  else if(S.sel.type==="finding")findingPageState.sidebar=Math.floor(S.sel.idx/pageSize);
  findingPageState.sidebar=Math.max(0,Math.min(Math.max(0,Math.ceil(findings.length/pageSize)-1),findingPageState.sidebar));
  const start=findings.length>pageSize?findingPageState.sidebar*pageSize:0;
  findings.slice(start,start+pageSize).forEach((f, offset) => {
    const i=start+offset;
    const sev = f.severity || (f.mode === "machine" ? "info" : "info");
    const active = S.sel.type === "finding" && S.sel.idx === i;
    const li = h("li", { draggable: "true", class: active ? "active" : "", "data-finding-uid":f.uid },
      h("button",{type:"button",class:"finding-nav","aria-current":active?"page":null,onclick:()=>select("finding",i)},
      h("span", { class: "sev-dot sev-" + sev }),
      h("span", { class: "fid" }, f.id || ""),
      h("span", { class: "ftitle" }, f.title || t("untitled")))
    );
    li.addEventListener("dragstart", e => { dragCtx = { arr: S.data.findings, from: i }; e.dataTransfer.effectAllowed = "move"; });
    makeDropZone(li, S.data.findings, i);
    ul.append(li);
  });
  if(findings.length>pageSize)ul.after(workspacePageBar("sidebar",findings.length,findingPageState.sidebar,pageSize,page=>renderSidebar(page)));
}
// ---- buscador global -------------------------------------------------------
function searchTargets() {
  const d = S.data, out = [];
  const w = (es,en) => S.uiLang === "en" ? en : es;
  if (!d) return out;
  const m = d.meta || {}, rep = { type: "report" };
  [["report_title", w("Título", "Title")], ["report_subtitle", w("Subtítulo", "Subtitle")], ["client", w("Cliente", "Client")], ["assessor", w("Evaluador", "Assessor")], ["assessor_title", w("Cargo", "Role")], ["version", w("Versión", "Version")]]
    .forEach(([k, lab]) => { if (m[k]) out.push({ nav: rep, where: w("Informe", "Report") + " / " + lab, text: String(m[k]) }); });
  ((m.contacts && m.contacts.client) || []).forEach(c => out.push({ nav: { type: "section", key: "contacts" }, where: w("Contactos del cliente", "Client contacts"), text: [c.name, c.title, c.email].filter(Boolean).join(" ") }));
  ((m.contacts && m.contacts.assessor) || []).forEach(c => out.push({ nav: { type: "section", key: "contacts" }, where: w("Equipo evaluador", "Assessment team"), text: [c.name, c.title, c.email].filter(Boolean).join(" ") }));
  (m.scope || []).forEach(s => out.push({ nav: { type: "section", key: "scope" }, where: w("Alcance", "Scope"), text: [s.target, s.description].filter(Boolean).join(" ") }));
  ((d.report && d.report.sections) || []).forEach(sec => {
    const schema = S.catBy[sec.key] || {};
    const nav = { type: "section", key: sec.key }, where = sec.title || schema["title_" + (S.uiLang || "es")] || schema.title_es || sec.key;
    if (sec.title) out.push({ nav, where, text: sec.title });
    const fields = S.catBy[sec.key] ? (schema.fields || []) : [{key: "body"}];
    fields.forEach(f => { const v = sec[f.key]; if (typeof v === "string" && v) out.push({ nav, where, text: v }); });
  });
  (d.findings || []).forEach((f, idx) => {
    const nav = { type: "finding", idx }, location = f.id + (f.title ? " " + f.title : "");
    if (f.id) out.push({ nav, where: location + " \u00b7 ID", text: String(f.id), findingId: true });
    [["title", w("Título", "Title")], ["cwe", "CWE"], ["affected", "Host"], ["description_md", w("Descripción", "Description")], ["impact_md", w("Impacto", "Impact")], ["remediation_md", w("Remediación", "Remediation")]]
      .forEach(([k, lab]) => { if (f[k]) out.push({ nav, where: location + " \u00b7 " + lab, text: String(f[k]) }); });
    (f.references || []).forEach(r => { if (r) out.push({ nav, where: location + " \u00b7 Ref", text: r }); });
    if (f.host) [["name", w("Máquina", "Machine")], ["ip", "IP"], ["os", w("SO", "OS")]].forEach(([k, lab]) => { if (f.host[k]) out.push({ nav, where: location + " \u00b7 " + lab, text: f.host[k] }); });
    if (f.open_ports) out.push({ nav, where: location + " / " + w("Puertos", "Ports"), text: f.open_ports });
    if (f.summary_md) out.push({ nav, where: location + " / " + w("Ruta", "Path"), text: f.summary_md });
    const addStep = st => ["lead", "text_md", "command"].forEach(k => { if(st[k])out.push({nav,where:location+" / "+w("Paso","Step"),text:String(st[k])}); });
    (f.walkthrough || []).forEach(addStep);
    (f.phases || []).forEach(ph => {
      if (ph.name) out.push({ nav, where: location + " / " + w("Fase", "Phase"), text: ph.name });
      (ph.steps || []).forEach(addStep);
    });
  });
  return out;
}
function searchText(text) {
  return String(text).normalize("NFC").replace(/\s+/g, " ");
}
function searchSpan(text, folded, query) {
  const index = folded.indexOf(query);
  if (index < 0) return null;
  if (text.length === folded.length) return { start: index, end: index + query.length };
  // Some case conversions expand a character (for example, İ becomes i + dot).
  // Translate the folded offsets back before slicing the displayed text.
  let position = 0, offset = 0, start = 0;
  for (const character of text) {
    const next = offset + character.toLowerCase().length;
    if (offset <= index && index < next) start = position;
    position += character.length;
    if (next >= index + query.length) return { start, end: position };
    offset = next;
  }
  return null;
}
function searchSnippet(text, i, len) {
  const segments = new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text);
  const start = segments.containing(i).index, last = segments.containing(i + len - 1);
  const end = last.index + last.segment.length;
  const s = segments.containing(Math.max(0, start - 30)).index;
  const tail = segments.containing(Math.min(text.length - 1, end + 39));
  const e = tail.index + tail.segment.length;
  return { pre: (s > 0 ? "\u2026" : "") + text.slice(s, start), mid: text.slice(start, end), post: text.slice(end, e) + (e < text.length ? "\u2026" : "") };
}
function searchProject(q) {
  q = searchText(q || "").trim().toLowerCase();
  if (!q) return [];
  const res = [];
  // A stable ID is a navigation target even when it is never mentioned in the
  // prose. Exact ID matches must survive a long report's cross-reference limit.
  const targets = searchTargets().map(tg => {
    const text = searchText(tg.text);
    return { ...tg, text, folded: text.toLowerCase() };
  }), exact = tg => tg.findingId && tg.folded === q;
  for (const tg of [...targets.filter(exact), ...targets.filter(tg => !exact(tg))]) {
    const span = searchSpan(tg.text, tg.folded, q);
    if (span) { res.push({ nav: tg.nav, where: tg.where, snippet: searchSnippet(tg.text, span.start, span.end - span.start) }); if (res.length >= 40) break; }
  }
  return res;
}
function navTo(nav) {
  if (nav.type === "section") select("section", nav.key);
  else if (nav.type === "finding") select("finding", nav.idx);
  else select("report", -1);
}
function renderSearch(q) {
  if(typeof WorkbenchUI!=="undefined")return WorkbenchUI.search(q);
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

function select(type, val) { if(typeof WorkbenchUI!=="undefined")WorkbenchUI.position(); S.sel = (type === "section") ? { type, key: val } : { type, idx: val }; renderSidebar(); renderMain(); }
function findingSequenceError() {
  return Error(S.uiLang === "en" ? "The finding identifier counter is exhausted. Existing findings can still be edited and exported." : "Se agotó el contador de identificadores de hallazgos. Puedes seguir editando y exportando los hallazgos existentes.");
}
function findingSequence(data) {
  let sequence=data.finding_sequence||0;
  if (!Number.isSafeInteger(sequence) || sequence < 0) throw findingSequenceError();
  const reserve=value=>{
    const number=Number(value);
    if (!Number.isSafeInteger(number) || number < 0) throw findingSequenceError();
    sequence=Math.max(sequence,number);
  };
  for (const finding of data.findings||[]) if (/^F[0-9]+$/.test(finding.id||'')) reserve(finding.id.slice(1));
  for (const match of JSON.stringify(data).matchAll(/#F([0-9]+)\b/g)) reserve(match[1]);
  const pending=[data];
  while (pending.length) {
    const value=pending.pop();
    if (typeof value === 'string') {
      for (const match of value.matchAll(/#([^\s<>()\[\]{}"'`]+)/g)) {
        let fragment;
        try { fragment=decodeURIComponent(match[1]); } catch (_) { continue; }
        if (/^F[0-9]+$/.test(fragment)) reserve(fragment.slice(1));
      }
    } else if (value && typeof value === 'object') {
      for (const child of Object.values(value)) pending.push(child);
    }
  }
  return sequence;
}
function nextFid(data=S.data) {
  // Public IDs are permanent anchors, not positions. Reserve removed numbers
  // across saves so a later addition cannot revive a link to a different item.
  const sequence=findingSequence(data);
  if (sequence >= Number.MAX_SAFE_INTEGER) throw findingSequenceError();
  data.finding_sequence=sequence+1;
  return 'F'+data.finding_sequence;
}
function requestedFindingId() {
  try { return nextFid(); }
  catch (error) { toast(error.message,"err"); return null; }
}

// ---- editor principal ------------------------------------------------------
function renderMain() {
  const el = $("#editor"); el.innerHTML = "";
  if(typeof WorkspaceUI!=='undefined') {
    WorkspaceUI.update();
    ExperienceUI.update();
    if(S.sel.type==='insights'&&typeof InsightsUI!=='undefined'){InsightsUI.render(el);if(typeof WorkbenchUI!=="undefined")WorkbenchUI.afterRender();return;}
    if(S.sel.type==='guide'&&typeof GuideUI!=='undefined'){GuideUI.render(el);if(typeof WorkbenchUI!=="undefined")WorkbenchUI.afterRender();return;}
    if(!S.data||S.sel.type==='home'){WorkspaceUI.render(el);if(typeof WorkbenchUI!=="undefined")WorkbenchUI.afterRender();return;}
  }
  if(typeof ExperienceUI!=='undefined') {
    ExperienceUI.update();
    if(!S.data){ExperienceUI.welcome(el);return;}
  }
  if (!S.data) { el.append(h("div", { class: "empty" }, t("empty"))); return; }
  if(S.sel.type === "studio")StudioUI.render(el,S.sel.idx);
  else if (S.sel.type === "findings") el.append(h("h2",{},S.uiLang==="en"?"Findings":"Hallazgos"),findingsDashboard());
  else if (S.sel.type === "capture") WorkbenchUI.inbox(el);
  else if (S.sel.type === "report") el.append(reportEditor());
  else if (S.sel.type === "section") el.append(sectionEditor(S.sel.key));
  else if (S.sel.type === "workflow") WorkflowUI.render(S.sel.idx, el);
  else if(S.data.findings[S.sel.idx])el.append(findingEditor(S.data.findings[S.sel.idx]));
  if(typeof WorkbenchUI!=="undefined")WorkbenchUI.afterRender();
}

// Successful server mutations must advance the local revision too: otherwise
// a cached preview could incorrectly keep its "Current revision" label.
async function adoptSavedProject(data, etag) {
  invalidateValidation();
  S.data=data;projectStore.data=data;projectStore.base=JSON.parse(JSON.stringify(data));projectStore.etag=etag;
  projectStore.revision++;projectStore.savedRevision=projectStore.revision;projectStore.lastSavedAt=new Date();projectStore.lastError=null;
  let draftCleanupFailed=false;
  try{if(projectStore.journal)await projectStore.journal.clearOwn(S.slug);projectStore.recoverableRevision=0;projectStore.draftError=null;}
  catch(error){projectStore.draftError=error;draftCleanupFailed=true;toast(S.uiLang==='en'?'Saved. An older browser draft could not be removed; review Stored private data.':'Guardado. No se pudo eliminar un borrador anterior del navegador; revisa Datos privados guardados.','err');}
  UndoUI.clear();WorkbenchUI.dirty();WorkflowUI.resetReview?.();ProgressUI.saveState('saved');
  return {draftCleanupFailed};
}
function moveFindingDialog(identity, section=false) {
  const findings=(section?S.data?.report?.sections:S.data?.findings)||[], idKey=section?"key":"uid", index=findings.findIndex(f=>f[idKey]===identity);
  if(index<0)return;
  const previous=document.activeElement, slug=S.slug, titleId="finding-move-"+WorkflowUI.uid();
  const dialog=h("dialog",{class:"experience-dialog","aria-labelledby":titleId}),body=h("div",{class:"experience-body"});
  const close=h("button",{type:"button",class:"btn",onclick:()=>dialog.close()},S.uiLang==="en"?"Close":"Cerrar");
  const position=h("input",{type:"number",min:1,max:findings.length,value:index+1,"data-finding-position":section?null:"","data-section-position":section?"":null});
  const label=S.uiLang==="en"?"Destination position":"Posición de destino";
  const error=h("p",{role:"alert"});
  body.append(h("p",{},S.uiLang==="en"?(section?"Change section order without changing its content.":"Change the manual order across pages. Finding IDs and evidence links stay unchanged."):(section?"Cambia el orden de las secciones sin modificar su contenido.":"Cambia el orden manual entre páginas. Los IDs y vínculos de evidencia se conservan.")),h("label",{},label,position),error,
    h("button",{type:"button",class:"btn primary","data-finding-move-apply":section?null:"","data-section-move-apply":section?"":null,onclick:()=>{
      if(S.slug!==slug||(section?S.data?.report?.sections:S.data?.findings)!==findings||projectBusyCount>0){error.textContent=S.uiLang==="en"?"The project changed. Reopen the move dialog.":"El proyecto cambió. Vuelve a abrir el diálogo de orden.";return;}
      const to=Number(position.value), from=findings.findIndex(f=>f[idKey]===identity);
      if(!position.value.trim()||!Number.isInteger(to)||to<1||to>findings.length||from<0){error.textContent=S.uiLang==="en"?"Choose an existing position.":"Elige una posición existente.";position.focus();return;}
      if(from===to-1){dialog.close();return;}
      const selected=!section&&S.sel.type==="finding"?findings[S.sel.idx]?.uid:null;
      UndoUI.move(findings,from,to-1);
      if(selected)S.sel.idx=findings.findIndex(f=>f.uid===selected);
      scheduleSave();renderSidebar();renderMain();
      if(!section&&S.sel.type==="findings"){findingPageState.board=Math.floor((to-1)/50);renderMain();}
      dialog.close();
    }},S.uiLang==="en"?(section?"Move section":"Move finding"):(section?"Mover sección":"Mover hallazgo")));
  dialog.append(h("div",{class:"experience-heading"},h("h2",{id:titleId},(section?(findings[index].title||findings[index].key):findings[index].id)+" · "+(S.uiLang==="en"?"Manual order":"Orden manual")),close),body);
  dialog.addEventListener("close",()=>{dialog.remove();const replacement=document.querySelector('['+(section?'data-section-move':'data-finding-move')+'="'+CSS.escape(identity)+'"]');(previous?.isConnected?previous:replacement||$("#editor")).focus({preventScroll:true});});
  document.body.append(dialog);dialog.showModal();position.focus();position.select();
}
function findingsDashboard() {
  const box = h("div", {});
  const actions=h("div",{class:"finding-create-actions"},
    h("button",{type:"button",class:"btn primary","data-finding-create":"blank",onclick:()=>{addFinding("blank");$("#editor").focus({preventScroll:true});}},t("add_finding")),
    h("button",{type:"button",class:"btn","data-finding-create":"library",onclick:()=>$("#libBtn").click()},S.uiLang==="en"?"Use finding library":"Usar biblioteca de hallazgos"));
  if(typeof BulkUI!=="undefined")actions.append(h("button",{type:"button",class:"btn","data-bulk-open":"",onclick:()=>BulkUI.open()},S.uiLang==="en"?"Bulk edit":"Editar por lotes"));
  box.append(actions);
  const all = (S.data.findings || []);
  const vulns = all.filter(f => f.mode !== "machine");
  const machines = all.filter(f => f.mode === "machine");
  const counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0, pending: 0 };
  vulns.forEach(f => { if (counts[f.severity] != null) counts[f.severity]++; else counts.pending++; });
  const dashboardSeverities = [...SEV, ["pending", severityLabel("")]];
  const totalV = vulns.length;
  // barra de distribución
  if (totalV) {
    const bar = h("div", { class: "dash-bar" });
    dashboardSeverities.forEach(([k]) => { if (counts[k]) bar.append(h("span", { class: "dash-bar-seg sev-" + k, style: "flex:" + counts[k] })); });
    box.append(bar);
  }
  // píldoras clicables (filtro por severidad)
  const sumBar = h("div", { class: "dash-summary" });
  dashboardSeverities.forEach(([k]) => sumBar.append(h("button", {
    class: "dash-pill sev-" + k + (S.dashFilter === k ? " active" : ""),
    onclick: () => { S.dashFilter = S.dashFilter === k ? null : k; renderMain(); }
  }, String(counts[k]), h("small", {}, severityLabel(k === "pending" ? "" : k)))));
  if (machines.length) sumBar.append(h("button", {
    class: "dash-pill sev-machine" + (S.dashFilter === "machine" ? " active" : ""),
    onclick: () => { S.dashFilter = S.dashFilter === "machine" ? null : "machine"; renderMain(); }
  }, String(machines.length), h("small", {}, t("dash_machine"))));
  box.append(sumBar);
  if (!all.length) { box.append(h("p", { class: "dash-empty" }, t("dash_empty"))); return box; }
  // conmutador de orden: severidad (defecto) o manual (arrastrable)
  const sortMode = S.dashSort || "sev";
  const toolbar = h("div", { class: "dash-toolbar" },
    h("button", { class: "dash-tab" + (sortMode === "sev" ? " active" : ""), onclick: () => { S.dashSort = "sev"; renderMain(); } }, t("dash_sort_sev")),
    h("button", { class: "dash-tab" + (sortMode === "manual" ? " active" : ""), onclick: () => { S.dashSort = "manual"; renderMain(); } }, t("dash_sort_manual")));
  box.append(toolbar);
  box.append(WorkbenchUI.filterBar());
  let rows = WorkbenchUI.filterRows(all.map((f, idx) => ({ f, idx })));
  if (sortMode === "sev") {
    rows.sort((a, b) => {
      const am = a.f.mode === "machine", bm = b.f.mode === "machine";
      if (am !== bm) return am ? 1 : -1;
      if (am) return 0;
      return (SEV_RANK[a.f.severity] ?? 9) - (SEV_RANK[b.f.severity] ?? 9);
    });
  }
  if (S.dashFilter) rows = rows.filter(({ f }) => S.dashFilter === "machine" ? f.mode === "machine" : (f.mode !== "machine" && (f.severity || "pending") === S.dashFilter));
  const canDrag = sortMode === "manual" && !S.dashFilter;
  const pageSize=50, key=JSON.stringify([S.slug,sortMode,S.dashFilter,rows.map(({f})=>f.uid||f.id)]);
  if(findingPageState.boardKey!==key){findingPageState.boardKey=key;findingPageState.board=0;}
  findingPageState.board=Math.max(0,Math.min(Math.max(0,Math.ceil(rows.length/pageSize)-1),findingPageState.board));
  if(rows.length>pageSize)box.append(workspacePageBar("board",rows.length,findingPageState.board,pageSize,page=>{findingPageState.board=page;renderMain();}));
  const visibleRows=rows.slice(findingPageState.board*pageSize,(findingPageState.board+1)*pageSize);
  const tbl = h("table", { class: "dash-table" });
  tbl.append(h("thead", {}, h("tr", {},
    canDrag ? h("th", { class: "c-drag" }, "") : null,
    h("th", { class: "c-n" }, "#"), h("th", {}, t("dash_sev")), h("th", {}, t("dash_finding")),
    h("th", {}, t("dash_cwe")), h("th", { class: "c-cvss" }, t("dash_cvss")))));
  const tb = h("tbody", {});
  visibleRows.forEach(({ f, idx }) => {
    const isM = f.mode === "machine";
    const sevCell = isM
      ? h("span", { class: "tag sev-machine" }, t("dash_machine"))
      : h("span", { class: "tag sev-" + (f.severity || "pending") }, severityLabel(f.severity));
    const cwe = (f.cwe || "").split(" —")[0].split(" -")[0].trim();
    const cvss = isM ? "—" : (f.cvss != null && f.cvss !== "" ? f.cvss + (f.cvss_version ? "  (" + f.cvss_version + ")" : "") : "—");
    const host = isM && f.host ? (f.host.name || f.host.ip || "") : "";
    const incomplete = !isM && (f.cvss == null || f.cvss === "" || !cwe);
    const title = h("td", { class: "c-title" }, h("button",{type:"button",class:"finding-row-open",onclick:e=>{e.stopPropagation();select("finding",idx);}},f.title || (isM ? host : "—")));
    title.append(WorkbenchUI.findingChips(f));
    if (incomplete) title.append(h("span", { class: "dash-warn", title: t("dash_incomplete") }, "!"));
    const tr = h("tr", { class: "dash-row", "data-finding-uid":f.uid, onclick: e => { if (!e.target.closest(".drag")) select("finding", idx); } },
      canDrag ? h("td", { class: "c-drag" }, dragHandle(S.data.findings, idx),h("button",{type:"button",class:"btn sm","data-finding-move":f.uid,"aria-label":(S.uiLang==="en"?"Move ":"Mover ")+f.id,onclick:event=>{event.stopPropagation();moveFindingDialog(f.uid);}},S.uiLang==="en"?"Move":"Mover")) : null,
      h("td", { class: "c-n" }, f.id || ("F" + (idx + 1))),
      h("td", {}, sevCell), title,
      h("td", { class: "c-cwe" }, isM ? host : (cwe || "—")),
      h("td", { class: "c-cvss" }, cvss));
    if (canDrag) makeDropZone(tr, S.data.findings, idx);
    tb.append(tr);
  });
  tbl.append(tb);
  if(!rows.length)box.append(h("p",{role:"status"},S.uiLang==="en"?"No findings match these filters. Use Clear filters to see all findings.":"No hay hallazgos con estos filtros. Usa Limpiar filtros para verlos todos."));
  box.append(h("div",{class:"findings-table-scroll",role:"region",tabindex:"0","aria-label":S.uiLang==="en"?"Findings table. Scroll horizontally on small screens.":"Tabla de hallazgos. Desplazamiento horizontal en pantallas pequeñas."},tbl));
  return box;
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
  const lang = (S.data.meta.lang || "en");
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
  if (sp === "findings") { wrap.append(findingsDashboard()); return wrap; }

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
    inp = h("textarea", { rows: opts.rows || 4, class: "grow", oninput: e => { obj[key] = e.target.value; autoGrow(e.target); if(opts.onChange)opts.onChange(); scheduleSave(); } });
    inp.value = obj[key] || ""; setTimeout(() => autoGrow(inp), 0);
  } else {
    inp = h("input", { type: opts.type || "text", value: obj[key] || "", oninput: e => {
      obj[key] = e.target.value; if(opts.onChange)opts.onChange(); scheduleSave();
      if(key==="title"&&S.sel.type==="finding"&&S.data?.findings[S.sel.idx]===obj){
        const item=Array.from(document.querySelectorAll("#findingList [data-finding-uid]")).find(el=>el.dataset.findingUid===obj.uid);
        const title=item?.querySelector(".ftitle");if(title)title.textContent=obj.title||t("untitled");
      }
    } });
  }
  inp.dataset.field = key;
  if (opts.ph) inp.setAttribute("placeholder", opts.ph);
  const control=h("label", {}, label, inp);
  if(opts.area&&key.endsWith('_md'))return h('div',{class:'markdown-field'},control,
    h('button',{type:'button',class:'btn sm','data-markdown-link':key,onclick:()=>openMarkdownLink(inp,()=>inp.dispatchEvent(new Event('input',{bubbles:true})))},S.uiLang==='en'?'Link':'Enlace'));
  return control;
}

function openMarkdownLink(ta, apply, onInserted = () => {}) {
const w = (es, en) => S.uiLang === "en" ? en : es;
  const start=ta.selectionStart,end=ta.selectionEnd,original=ta.value,slug=S.slug;
  const selected=original.slice(start,end),isUrl=/^https?:\/\/\S+$/i.test(selected);
  const name=h('input',{type:'text',required:'','data-link-name':'',value:isUrl?'':selected,maxlength:500});
  const target=h('input',{type:'url',required:'','data-link-url':'',value:isUrl?selected:'',placeholder:'https://'});
  const status=h('p',{role:'alert','data-link-error':''});
  const cancel=h('button',{type:'button',class:'btn'},w('Cancelar','Cancel'));
  const submit=h('button',{type:'submit',class:'btn primary'},w('Insertar enlace','Insert link'));
  const form=h('form',{class:'modal-box'},h('h3',{},w('Insertar enlace','Insert link')),
    h('p',{},w('Escribe el texto que verá el lector. El destino conserva la URL completa.','Enter the text the reader will see. The destination retains the complete URL.')),
    h('label',{},w('Nombre descriptivo','Descriptive name'),name),h('label',{},'URL',target),status,
    h('div',{class:'row'},cancel,submit));
  const dialog=h('dialog',{class:'modal','aria-label':w('Insertar enlace','Insert link'),'data-link-dialog':''},form);
  for(const input of [name,target])input.addEventListener('input',()=>{status.textContent='';});
  cancel.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{dialog.remove();if(ta.isConnected)ta.focus({preventScroll:true});});
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const label=name.value,url=target.value;
    let valid=false;
    try{const parsed=new URL(url);valid=/^https?:\/\//i.test(url)&&['http:','https:'].includes(parsed.protocol)&&!/[\s<>\\]/.test(url);}catch(_){}
    if(!label.trim()||/[\r\n]/.test(label)||!valid){
      status.textContent=w('Escribe un nombre y una URL HTTP o HTTPS completa, sin espacios.','Enter a name and a complete HTTP or HTTPS URL without spaces.');
      (!label.trim()?name:target).focus();return;
    }
    if(S.slug!==slug||!ta.isConnected||ta.value!==original){
      status.textContent=w('El texto o el proyecto cambió. Cierra el diálogo y vuelve a insertar el enlace.','The text or project changed. Close this dialog and insert the link again.');return;
    }
    // Angle-delimited Markdown destinations retain parentheses, query
    // strings and percent escapes. Never normalize through URL.href.
    const escaped=label.replace(/[\\`*_{}\[\]()#+.!|<>]/g,'\\$&');
    const markdown='['+escaped+'](<'+url+'>)';
    ta.value=original.slice(0,start)+markdown+original.slice(end);
    ta.selectionStart=ta.selectionEnd=start+markdown.length;
    apply();onInserted();dialog.close();
  });
  document.body.append(dialog);dialog.showModal();(!selected||isUrl?name:target).focus();
}

// Editor Markdown estilo SysReptor: barra + Write/Preview + imagen + tabla.
function mdEditor(label, obj, key, opts = {}) {
  const w = (es, en) => S.uiLang === "en" ? en : es;
  const ta = h("textarea", { rows: opts.rows || 10, class: "grow", "aria-label":label });
  ta.id = "markdown-" + WorkflowUI.uid(); ta.value = obj[key] || ""; ta.dataset.field = key;
  const prev = h("div", { class: "mded-prev", style: "display:none" });
  let previewGeneration = 0;

  function apply() { previewGeneration++; obj[key] = ta.value; autoGrow(ta); scheduleSave(); }
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
      const r = await sendImage(file);
      if (!r) return;
      insertAtCursor(`\n![${w("epígrafe de la imagen", "image caption")}](${r.src}){width="auto"}\n`);
      setSaveState(t("saved"));
    } });

  const tb = (txt, title, fn) => h("button", { class: "mded-btn", type: "button", title, "aria-label":title, onclick: fn }, txt);
  const bar = h("div", { class: "mded-bar" },
    tb("B", w("Negrita", "Bold"), () => insert("**", "**", w("texto", "text"))),
    tb("i", w("Cursiva", "Italic"), () => insert("*", "*", w("texto", "text"))),
    tb("</>", w("Código en línea", "Inline code"), () => insert("`", "`", w("código", "code"))),
    tb("{ }", w("Bloque de código", "Code block"), () => insert("```bash\n", "\n```", w("comando", "command"))),
    tb("H", w("Encabezado en negrita", "Bold heading"), () => insert("**", "**", w("encabezado", "heading"))),
    tb("•", w("Lista", "List"), () => prefixLines("- ")),
    tb("1.", w("Lista numerada", "Numbered list"), () => prefixLines("1. ")),
    tb("❝", w("Cita", "Quote"), () => prefixLines("> ")),
    tb(w("Enlace", "Link"), w("Enlace", "Link"), () => openMarkdownLink(ta,apply,()=>{if(ta.style.display==='none')wTab.click();})),
    tb(w("Imagen", "Image"), w("Subir imagen", "Upload image"), () => fileInp.click()),
    tb(w("Tabla", "Table"), w("Insertar tabla", "Insert table"), () => insertAtCursor("\n| Col1 | Col2 |\n|---|---|\n| a | b |\n")),
    h("span", { class: "mded-sp" }),
    (() => { const b = h("button", { class: "mded-tab active", type: "button" }, w("Editar", "Write")); b.dataset.role = "w"; return b; })(),
    (() => { const b = h("button", { class: "mded-tab", type: "button" }, w("Vista previa", "Preview")); b.dataset.role = "p"; return b; })(),
    fileInp
  );
  const wTab = bar.querySelector('[data-role="w"]'), pTab = bar.querySelector('[data-role="p"]');
  wTab.addEventListener("click", () => { previewGeneration++; ta.style.display = ""; prev.style.display = "none"; wTab.classList.add("active"); pTab.classList.remove("active"); });
  pTab.addEventListener("click", async () => {
    const generation = ++previewGeneration, text = ta.value, slug = S.slug;
    const current = () => generation === previewGeneration && ta.value === text && S.slug === slug && box.isConnected;
    prev.innerHTML = "…";
    ta.style.display = "none"; prev.style.display = ""; pTab.classList.add("active"); wTab.classList.remove("active");
    try {
      const r = await api.post("/api/md", { text, slug }).then(requireOk).then(x => x.json());
      if (!current()) return;
      prev.innerHTML = r.html || "<em>" + w("(vacío)", "(empty)") + "</em>";
    } catch (_) { if (current()) prev.innerHTML = "<em>" + w("error al renderizar", "rendering failed") + "</em>"; }
  });
  const box = h("div", { class: "mded" }, bar, ta, prev);
  return h("div", { class: "mdedlabel" }, h("label", { for: ta.id }, label), box);
}

function reportEditor() {
  const m = S.data.meta;
  const wrap = h("div", {});
  wrap.append(h("h2", {}, t("report")));
  wrap.append(DesignLibraryUI.panel());

  const c1 = h("div", { class: "card" }, h("h4", {}, t("cover_meta")));
  c1.append(field(t("report_title"), m, "report_title", { ph: t("report_title_ph") }));
  c1.append(field(t("subtitle"), m, "report_subtitle", { ph: t("subtitle_ph") }));
  const g = h("div", { class: "grid2" });
  g.append(field(t("client"), m, "client", { ph: t("client_ph") }), field(t("date"), m, "date", { type: "date" }),
           field(t("assessor"), m, "assessor", { ph: t("assessor_ph") }), field(t("assessor_title"), m, "assessor_title", { ph: t("assessor_title_ph") }),
           field(t("version"), m, "version", { ph: t("version_ph") }),
           field(t("osid"), m, "osid", { ph: t("osid_ph") }), field(t("email"), m, "email", { ph: t("email_ph") }));
  // diseño (theme) e idioma
  const themeSel = h("select", { "data-field":"theme", onchange: e => { m.theme = e.target.value; delete m.design; scheduleSave(); renderMain(); } },
    ["serio", "corporativo", "offsec", "htb", "ejecutivo", "laboratorio"].map(t => h("option", { value: t, selected: m.theme === t ? "" : null }, t)));
  const langSel = h("select", { onchange: e => { m.lang = e.target.value; scheduleSave(); } },
    ["es", "en"].map(t => h("option", { value: t, selected: (m.lang || "en") === t ? "" : null }, t)));
  g.append(h("label", {}, t("design"), themeSel), h("label", {}, t("report_lang"), langSel));
  const density=h("select", {"data-field":"report_density", onchange:e=>{m.report_density=e.target.value;scheduleSave();}},
    [ ["comfortable",S.uiLang==="en"?"Comfortable":"Cómoda"], ["compact",S.uiLang==="en"?"Compact":"Compacta"] ].map(([v,label])=>h("option",{value:v,selected:(m.report_density||"comfortable")===v?"":null},label)));
  g.append(h("label",{},S.uiLang==="en"?"Report spacing":"Espaciado del informe",density));
  c1.append(g);
  const b = m.branding = m.branding || {};
  const g2 = h("div", { class: "grid2" });
  g2.append(field(t("wordmark"), b, "wordmark", { ph: t("wordmark_ph") }), field(t("byline"), b, "byline", { ph: t("byline_ph") }),
            field(t("conf_text"), b, "confidential_text"), field(t("accent"), m.design || b, "accent", { type: "color" }));
  g2.append(coverImgField(b, "cover_image", t("cover_image")), coverImgField(b, "logo", t("own_logo")), coverImgField(b, "client_logo", t("client_logo")));
  c1.append(g2);
  wrap.append(c1);
  wrap.append(noteCard(t("contacts_scope_note")));
  return wrap;
}

function inlineField(obj, key, ph) {
  return h("input", { value: obj[key] || "", placeholder: ph, "aria-label":ph||key, oninput: e => { obj[key] = e.target.value; scheduleSave(); } });
}
function listCard(title, arr, factory, rowFields, beforeEdit=()=>{}) {
  const card = h("div", { class: "card" }, h("h4", {}, title));
  arr.forEach((row, i) => {
    const r = h("div", { class: "row" });
    rowFields(row).forEach(x => r.append(x));
    r.append(h("button", { class: "btn sm danger", onclick: () => { beforeEdit();UndoUI.remove(arr,i); scheduleSave(); renderMain(); } }, "✕"));
    card.append(r);
  });
  card.append(h("button", { class: "btn sm", onclick: () => { beforeEdit();arr.push(factory()); scheduleSave(); renderMain(); } }, t("add_row")));
  return card;
}

// ---- finding editor --------------------------------------------------------
function findingEditor(f) {
  const wrap = h("div", {});
  const head = h("h2", {}, `${f.id} `);
  const modeSel = h("select", { "aria-label":S.uiLang === "en" ? "Finding type" : "Tipo de hallazgo", style: "width:auto;display:inline-block;margin-left:8px", onchange: e => { f.mode = e.target.value; scheduleSave(); renderMain(); } },
    [["vuln", t("vuln")], ["machine", t("machine")]].map(o => h("option", { value: o[0], selected: f.mode === o[0] ? "" : null }, o[1])));
  head.append(modeSel);
  head.append(h("button", { class: "btn sm", style: "float:right;margin-left:8px", onclick: () => {
    const id=requestedFindingId(); if (!id) return;
    const copy = JSON.parse(JSON.stringify(f)); copy.id = id; copy.uid = WorkflowUI.uid(); delete copy.retests; delete copy.reported_remediation; copy.status = "open"; copy.verification = "unverified"; if(copy.import_source)copy.import_source.reviewed=false;
    S.data.findings.splice(S.sel.idx + 1, 0, copy); ensureFindingIds(); scheduleSave(); select("finding", S.sel.idx + 1);
  } }, t("duplicate_finding")));
  head.append(h("button", { class: "btn sm", style: "float:right;margin-left:8px", onclick: () => saveToLibrary(f) }, t("save_to_lib")));
  head.append(h("button", { class: "btn sm danger", style: "float:right", onclick: () => { if (!confirm(t("delete_finding_confirm"))) return; UndoUI.remove(S.data.findings,S.sel.idx); ensureFindingIds(); S.sel = { type: "report", idx: -1 }; scheduleSave(); renderSidebar(); renderMain(); } }, t("delete_finding")));
  wrap.append(head);
  wrap.append(f.mode === "machine" ? machineEditor(f) : vulnEditor(f));
  const tracking=WorkflowUI.findingPanel(f);
  const evidencePart=h("section",{"data-workpart":"evidence",class:"finding-part"},h("h3",{},S.uiLang==="en"?"Evidence":"Evidencias"));
  const evidenceLinks=tracking.querySelector('[data-field="evidence_uids"]');if(evidenceLinks)evidencePart.append(evidenceLinks);
  evidencePart.append(h("button",{type:"button",class:"btn",onclick:()=>select("workflow","evidence")},S.uiLang==="en"?"Open evidence gallery":"Abrir galería de evidencias"));
  WorkbenchUI.findingWorkspace(evidencePart,f);
  const remediationPart=wrap.querySelector('[data-workpart="remediation"]');
  if(remediationPart)remediationPart.before(evidencePart);else wrap.append(evidencePart);
  wrap.append(tracking);
  if(f.mode==="machine"){const m=wrap.children[1];m.firstElementChild.dataset.workpart="description";const phase=m.querySelector(".card:nth-child(2)");if(phase)phase.dataset.workpart="reproduction";tracking.dataset.workpart="remediation";}
  WorkbenchUI.findingNavigation(wrap,f);
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
  const sevSel = h("select", { onchange: e => { if(e.target.value)f.severity=e.target.value;else delete f.severity; scheduleSave(); renderSidebar(); } },
    [[""], ...SEV].map(o => h("option", { value: o[0], selected: (f.severity || "") === o[0] ? "" : null }, severityLabel(o[0]))));
  const g = h("div", { class: "grid2" });
  g.append(h("label", {}, t("dash_sev"), sevSel), cweField(f), field(t("affected"), f, "affected"));
  c.append(g);
  c.append(h("details",{class:"cvss-details"},h("summary",{},"CVSS / "+(f.cvss||"—")),CVSSEditor.widget(f, sevSel)));
  const description=h("section",{"data-workpart":"description",class:"finding-part"});description.append(c);box.append(description);

  const c2 = h("div", { class: "card" }, h("h4", {}, t("content")));
  c2.append(field(t("desc_root"), f, "description_md", { area: true, rows: 4 }));
  c2.append(field(t("impact"), f, "impact_md", { area: true, rows: 3 }));

  const references=f.references||[];
  const refCard = h("div", {}, h("h4", {}, t("references")));
  references.forEach((r, i) => {
    const row = h("div", { class: "row" },
      h("input", { value: r, "aria-label":t("references")+" "+(i+1), oninput: e => { references[i] = e.target.value;f.references=references; scheduleSave(); } }),
      h("button", { class: "btn sm danger", onclick: () => { f.references=references;UndoUI.remove(references,i); scheduleSave(); renderMain(); } }, "✕"));
    refCard.append(row);
  });
  refCard.append(h("button", { class: "btn sm", onclick: () => { f.references=references;references.push(""); scheduleSave(); renderMain(); } }, t("add_ref")));
  c2.append(refCard);
  description.append(c2);

  // walkthrough
  const walkthrough=f.walkthrough||[];
  box.append(h("section",{"data-workpart":"reproduction",class:"finding-part"},stepsCard(t("procedure"),walkthrough,()=>f.walkthrough=walkthrough)));

  // remediation summary
  const rs=f.remediation_summary||{}, persistRemediation=()=>f.remediation_summary=rs;
  const c3 = h("div", { class: "card" }, h("h4", {}, t("rem_summary")));
  c3.append(field(t("remediation"),f,"remediation_md",{area:true,rows:4}));
  c3.append(field(S.uiLang==="en"?"Short term":"Corto plazo", rs, "short_md",{onChange:persistRemediation}), field(S.uiLang==="en"?"Medium term":"Mediano plazo", rs, "medium_md",{onChange:persistRemediation}), field(S.uiLang==="en"?"Long term":"Largo plazo", rs, "long_md",{onChange:persistRemediation}));
  box.append(h("section",{"data-workpart":"remediation",class:"finding-part"},c3));
  return box;
}

function machineEditor(f) {
  const box = h("div", {});
  const host=f.host||{};
  const c = h("div", { class: "card" }, h("h4", {}, t("host")));
  c.append(field(t("machine_name"), f, "title"));
  const g = h("div", { class: "grid2" });
  g.append(field(t("ip"),host,"ip",{ph:t("ip_ph"),onChange:()=>f.host=host}),field(t("os"),host,"os",{ph:t("os_ph"),onChange:()=>f.host=host}), field(t("ports"), f, "open_ports", { ph: t("ports_ph") }));
  c.append(g);
  c.append(field(t("attack_path"), f, "summary_md", { area: true, rows: 3, ph: t("attack_path_ph") }));
  c.append(h("p", { style: "color:var(--muted);font-size:13px;margin:8px 2px 0" }, t("machine_hint")));
  box.append(c);

  const phases=f.phases||[];
  phases.forEach((ph, i) => {
    const pc = h("div", { class: "card" });
    const head = h("h4", {}, "");
    const nameInp = h("input", { value: ph.name || "", placeholder: t("phase_name_ph"), style: "max-width:60%;display:inline-block", oninput: e => { ph.name = e.target.value; scheduleSave(); } });
    head.append(t("phase") + " ", nameInp, h("button", { class: "btn sm danger", style: "float:right", onclick: () => { f.phases=phases;UndoUI.remove(phases,i); scheduleSave(); renderMain(); } }, t("remove_phase")));
    pc.append(head);
    const steps=ph.steps||[];
    pc.append(stepsInner(steps,()=>ph.steps=steps));
    box.append(pc);
  });
  box.append(h("button", { class: "btn sm", onclick: () => { f.phases=phases;phases.push({ name: "", steps: [] }); scheduleSave(); renderMain(); } }, t("add_phase")));

  const proof=f.proof||[];
  box.append(listCard(t("evidence"),proof,()=>({name:"",value:""}),
    row=>[inlineField(row,"name",t("ev_name")),inlineField(row,"value",t("ev_value"))],()=>f.proof=proof));
  return box;
}

function stepsCard(title, steps, beforeEdit=()=>{}) {
  const card = h("div", { class: "card" }, h("h4", {}, title));
  card.append(stepsInner(steps,beforeEdit));
  return card;
}
function stepsInner(steps,beforeEdit=()=>{}) {
  const wrap = h("div", {});
  steps.forEach((s, i) => wrap.append(stepBlock(steps, s, i)));
  wrap.append(h("button", { class: "btn sm", "data-add-step": "", onclick: () => { beforeEdit();steps.push({}); scheduleSave(); renderMain(); } }, t("add_step")));
  return wrap;
}
function stepBlock(steps, s, i) {
  const b = h("div", { class: "block", "data-step-index": i });
  const head = h("div", { class: "block-head" },
    h("span", { class: "lbl" }, dragHandle(steps, i), " " + t("step") + " " + (i + 1)),
    h("span", {},
      h("button", { class: "btn sm", onclick: () => { if (i > 0) { UndoUI.move(steps,i,i-1); scheduleSave(); renderMain(); } } }, "↑"),
      h("button", { class: "btn sm", onclick: () => { if (i < steps.length - 1) { UndoUI.move(steps,i,i+1); scheduleSave(); renderMain(); } } }, "↓"),
      h("button", { class: "btn sm danger", onclick: () => { UndoUI.remove(steps,i); scheduleSave(); renderMain(); } }, "✕")));
  b.append(head);
  makeDropZone(b, steps, i);
  b.append(field(t("lead"), s, "lead"));
  b.append(field(t("step_text"), s, "text_md", { area: true, rows: 3 }));
  b.append(field(t("code_block"), s, "command", { area: true, rows: 2 }));
  // figura
  const fig = s.figure || {};
  const figWrap = h("div", {});
  const file = h("input", { type: "file", "data-field": "src", accept: "image/*", onchange: e => uploadImage(e, s) });
  figWrap.append(h("label", {}, t("image"), file));
  if (fig.src) {
    figWrap.append(h("img", { class: "imgprev", src: `/api/projects/${S.slug}/${fig.src}`, alt:fig.caption || t("image")+" "+(i+1) }));
    figWrap.append(h("input", { value: fig.caption || "", placeholder: t("caption_ph"), "aria-label":t("caption_ph"), oninput: e => { s.figure.caption = e.target.value; scheduleSave(); } }));
    figWrap.append(h("button", { class: "btn sm danger", onclick: () => { delete s.figure; scheduleSave(); renderMain(); } }, t("remove_image")));
  }
  b.append(figWrap);
  return b;
}
async function sendImage(file) {
  busyProject(true); setSaveState(t("saving"));
  try {
    const fd = new FormData(); fd.append("file", file);
    return await appFetch(`/api/projects/${S.slug}/image`, {method: "POST", body: fd}).then(requireOk).then(r => r.json());
  } catch (error) { toast(error.message, "err"); setSaveState(t("err")); return null; }
  finally { busyProject(false); updateDeleteBtn(); }
}
async function uploadCover(e, b, key) {
  const file = e.target.files[0]; if (!file) return;
  const r = await sendImage(file);
  if (!r) return;
  b[key] = r.src; scheduleSave(); renderMain();
}
function coverImgField(b, key, label) {
  const wrap = h("label", {}, label);
  wrap.append(h("input", { type: "file", "data-field": key, accept: "image/*", onchange: e => uploadCover(e, b, key) }));
  if (b[key]) wrap.append(h("button", { class: "btn sm danger", style: "margin-top:6px", onclick: () => { delete b[key]; scheduleSave(); renderMain(); } }, t("remove") + " · " + b[key].split("/").pop()));
  return wrap;
}
async function uploadImage(e, s) {
  const file = e.target.files[0]; if (!file) return;
  const r = await sendImage(file);
  if (!r) return;
  s.figure = { src: r.src, caption: (s.figure && s.figure.caption) || "" };
  scheduleSave(); renderMain();
}

// ---- OWASP + nuevo hallazgo ------------------------------------------------
function saveToLibrary(f) { WorkflowUI.saveTemplate(f).catch(error => toast(error.message, "err")); }
function openLibrary() { WorkflowUI.openLibrary(); }
function exportFindings() {
  if (!S.data) return;
  if ((S.data.findings || []).some(f => f.root_cause_uid) && !confirm(S.uiLang === "en"
    ? "This JSON contains individual findings, without their root-cause groups or shared actions. Finding-specific remediation stays unchanged. Use a full project backup to preserve those relationships, or Remediation tasks to export resolved actions. Continue?"
    : "Este JSON contiene los hallazgos individuales, sin sus grupos de causa raíz ni acciones comunes. La remediación específica se conserva sin cambios. Usa un respaldo completo del proyecto para conservar los vínculos, o Tareas de remediación para exportar las acciones resueltas. ¿Continuar?")) return;
  const blob = new Blob([JSON.stringify(S.data.findings || [], null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: (S.slug || "hallazgos") + "-findings.json" }); a.click(); URL.revokeObjectURL(url);
}
async function importFindings(ev) {
  const file = ev.target.files[0]; if (!file || !S.data) return;
  const slug=S.slug, current=S.data, revision=projectStore.revision, etag=projectStore.etag, snapshot=JSON.stringify(current);
  const unchanged=()=>S.slug===slug && S.data===current && projectStore.revision===revision && projectStore.etag===etag && JSON.stringify(S.data)===snapshot;
  try {
    if (file.size>24*1024*1024) throw Error(S.uiLang === "en" ? "The file exceeds 24 MiB." : "El archivo supera 24 MiB.");
    const text=await new Promise((resolve,reject)=>{const rd=new FileReader();rd.onload=()=>resolve(rd.result);rd.onerror=()=>reject(Error(S.uiLang === "en" ? "Could not read the file." : "No se pudo leer el archivo."));rd.readAsText(file);});
    const parsed=JSON.parse(text), arr=Array.isArray(parsed)?parsed:parsed && typeof parsed==='object' && Array.isArray(parsed.findings)?parsed.findings:null;
    if (!arr || arr.some(f=>!f || typeof f!=='object' || Array.isArray(f) || (f.mode!==undefined && !['vuln','machine'].includes(f.mode)))) throw Error(S.uiLang === "en" ? "Use an array of findings or an object with a findings array. Each finding must be an object with type vuln or machine." : "Usa una lista de hallazgos o un objeto con la lista findings. Cada hallazgo debe ser un objeto de tipo vuln o machine.");
    if (!arr.length) { toast("0 "+t("findings_imported"),"ok"); return; }
    if (arr.some(f=>f.root_cause_uid) && !confirm(S.uiLang === "en"
      ? "These findings reference root-cause groups from their original project. This import removes those links and does not transfer groups or shared actions. Finding-specific remediation stays unchanged. To preserve everything, import a full project backup. Continue?"
      : "Estos hallazgos contienen vínculos a grupos de causa raíz del proyecto de origen. Esta importación retira esos vínculos y no incorpora grupos ni acciones comunes. La remediación específica se conserva sin cambios. Para conservar todo, importa un respaldo completo del proyecto. ¿Continuar?")) return;
    const candidate=JSON.parse(snapshot);
    for (const f of arr) {
      const g=JSON.parse(JSON.stringify(f));g.id='F'+nextFid(candidate).slice(1).padStart(2,'0');g.uid=WorkflowUI.uid();g.mode ??= 'vuln';
      delete g.__name;delete g.asset_uids;delete g.evidence_uids;delete g.retests;delete g.root_cause_uid;delete g.reported_remediation;
      g.status='open';g.verification='unverified';if(g.import_source)g.import_source.reviewed=false;candidate.findings.push(g);
    }
    if (!unchanged()) throw Error(S.uiLang === "en" ? "The project changed. Import the file again." : "El proyecto cambió. Importa el archivo otra vez.");
    const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/draft-check',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(candidate)}));
    const accepted=(await response.json()).data;
    if (!unchanged()) throw Error(S.uiLang === "en" ? "The project changed. Import the file again." : "El proyecto cambió. Importa el archivo otra vez.");
    // Undo records refer to the existing model arrays; adopt only the approved additions.
    current.findings.push(...accepted.findings.slice(current.findings.length));
    current.finding_sequence=accepted.finding_sequence;
    scheduleSave();renderSidebar();renderMain();toast(arr.length+" "+t("findings_imported"),"ok");
  } catch (error) { toast(error instanceof SyntaxError ? (S.uiLang === "en" ? "Invalid JSON file." : "Archivo JSON inválido.") : error.message,"err"); }
  finally { ev.target.value=""; }
}
function addFinding(kind) {
  if (!S.data) return;
  if (kind === "blank") {
    const id=requestedFindingId(); if (!id) return;
    S.data.findings.push({ id, mode: "vuln", title: "", cvss: "", cvss_vector: "" });
    S.focusTitle = true; finishAdd(); return;
  }
  openOwasp(kind);
}
function finishAdd() { ensureFindingIds(); scheduleSave(); const i = S.data.findings.length - 1; select("finding", i); }
function openOwasp(kind) {
  const cat = S.owasp[kind];
  $("#owaspTitle").textContent = cat.catalog;
  const list = $("#owaspList"); list.innerHTML = "";
  const es = (S.data.meta.lang || "en") === "es";
  cat.items.forEach(it => {
    list.append(h("li", {},
      h("div", { class: "oid" }, `${it.id}  ${es ? it.name_es : it.name}`),
      h("div", { class: "osum" }, es ? it.summary_es : it.summary),
      h("button", { class: "btn sm primary", onclick: () => insertOwasp(it) }, S.uiLang === "en" ? "Insert as finding" : "Insertar como hallazgo")));
  });
  openModal($("#owaspModal"));
}
function insertOwasp(it) {
  const es = (S.data.meta.lang || "en") === "es";
  const id=requestedFindingId(); if (!id) return;
  S.data.findings.push({
    id, mode: "vuln",
    title: `${it.id} ${es ? it.name_es : it.name}`,
    severity: "high", cvss: "", cvss_vector: "",
    cwe: it.cwe || "", description_md: es ? it.summary_es : it.summary,
    references: it.ref ? [it.ref] : [],
  });
  closeModal($("#owaspModal"));
  finishAdd();
}

// ---- preview / descarga ----------------------------------------------------
async function exportFile() {
  if (!S.slug || !await doSave()) return;
  try { await ProgressUI.enqueue(S.slug,projectStore.etag,{kind:'export',formats:[$('#exportFormat').value],label:(S.data.meta.report_title||S.slug).slice(0,120)}); }
  catch(error){toast(error.message,'err');}
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
  const focusedKey=document.activeElement?.dataset.sectionKey;
  const cat = S.catalog, box = $("#sectionCatalog"); box.innerHTML = "";
  const lang = (S.data.meta.lang || "en");
  const enabled = new Set(S.data.report.sections.map(s => s.key));
  const groups = cat.groups || [...new Set(cat.sections.map(s => s.group))];
  groups.forEach(g => {
    const secs = cat.sections.filter(s => s.group === g).sort((a, b) => (a.order || 999) - (b.order || 999));
    if (!secs.length) return;
    box.append(h("div", { class: "grp" }, g));
    secs.forEach(s => {
      const cb = h("input", { type: "checkbox", "data-section-key":s.key });
      cb.checked = enabled.has(s.key);
      cb.addEventListener("change", () => toggleSection(s.key, cb.checked));
      box.append(h("label", { class: "optrow" }, cb,
        s["title_" + lang] || s.title_es,
        s.required ? h("span", { class: "req-badge" }, t("recommended")) : null,
        s.special ? h("span", { class: "sect-badge" }, " " + s.special) : null));
    });
  });
  openModal($("#sectionsModal"));
  if(focusedKey) [...box.querySelectorAll('input')].find(cb=>cb.dataset.sectionKey===focusedKey)?.focus();
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
  const label=sel?(sel["name_"+lg]||sel.name_es||sel.id):selectedPresetId();
  $("#mPresetSelected").textContent=(lg==='en'?'Selected structure: ':'Estructura seleccionada: ')+label+(sel?.id==='base'?(lg==='en'?' · Recommended starting point':' · Inicio recomendado'):'');
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
  WorkflowUI.bind();
  if(typeof ExperienceUI!=='undefined')ExperienceUI.bind();
  DesignLibraryUI.bind();
  if(typeof WorkspaceUI!=='undefined')WorkspaceUI.bind();
  $("#projectSelect").addEventListener("change", e => loadProject(e.target.value));
  $("#navReport").addEventListener("click", () => select("report", -1));
  document.querySelectorAll("[data-add]").forEach(b => b.addEventListener("click", () => addFinding(b.dataset.add)));
  { const lb = $("#libBtn"); if (lb) lb.addEventListener("click", openLibrary); }
  { const eb = $("#exportFindingsBtn"); if (eb) eb.addEventListener("click", exportFindings); }
  { const ib = $("#importFindingsBtn"); if (ib) ib.addEventListener("click", () => $("#importFindingsInput").click()); }
  { const ii = $("#importFindingsInput"); if (ii) ii.addEventListener("change", importFindings); }
  {
    const si = $("#globalSearch"); let st = null;
    si.addEventListener("input", e => { clearTimeout(st); st = setTimeout(() => renderSearch(e.target.value), 120); });
    si.addEventListener("keydown", e => { if (e.key === "Escape") { si.value = ""; renderSearch(""); si.blur(); } });
    si.addEventListener("blur", () => setTimeout(() => {if(!$(".search-wrap").contains(document.activeElement))$("#searchResults").classList.remove("open");}, 150));
    si.addEventListener("focus", e => {
      // Desktop search sits outside More; dismiss the overlapping menu before
      // showing results. Mobile search lives inside it and must stay visible.
      const more = $("#studioMore"); if (more && !more.contains(si)) more.open = false;
      if (e.target.value) renderSearch(e.target.value);
    });
  }
  $("#previewBtn").addEventListener("click", () => S.previewMode === "live" ? refreshLivePreview() : renderPdf(false));
  $("#previewToggle").addEventListener("click", () => setPreviewVisible(!S.previewVisible));
  { let v = true; try { v = localStorage.getItem("rg.previewVisible") !== "0"; } catch (_) {} setPreviewVisible(v); }
  $("#pvLive").addEventListener("click", () => setPreviewMode("live"));
  $("#pvPdf").addEventListener("click", () => setPreviewMode("pdf"));
  $("#langToggle").addEventListener("click", toggleUiLang);
  $("#themeToggle").addEventListener("click", toggleUiTheme);
  $("#validateBtn").addEventListener("click", runValidation);
  document.addEventListener("keydown", e => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "k" && !document.querySelector('dialog[open],.modal.open:not(dialog)')) { e.preventDefault(); const s = $("#globalSearch"); if (s) { const menu=s.closest('details')||(window.matchMedia('(max-width:760px)').matches?$('#studioMore'):null);if(menu)menu.open=true;s.focus();requestAnimationFrame(()=>s.focus());renderSearch(s.value); } }
    else if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); if (S.slug) { doSave().then(ok => { if (ok) toast(t("saved"), "ok"); }); } }
    else if (e.key === "Escape") {
      document.querySelectorAll(".modal.open:not(dialog)").forEach(m => m.closeModal ? m.closeModal() : m.classList.remove("open"));
      const sr = $("#searchResults"); if (sr) sr.classList.remove("open");
    }
  });
  $("#downloadBtn").addEventListener("click", exportFile);
  $("#owaspCancel").addEventListener("click", () => closeModal($("#owaspModal")));
  $("#manageSections").addEventListener("click", openSectionsModal);
  $("#sectionsClose").addEventListener("click", () => closeModal($("#sectionsModal")));
  // nuevo proyecto
  $("#mPreset").addEventListener("change", () => { const v = $("#mPreset").value; if (v.startsWith("family:")) fillCertOptions(v.slice(7)); refreshPresetDesc(); });
  $("#mCert").addEventListener("change", refreshPresetDesc);
  populatePresetSelector();
  $("#newProjectBtn").addEventListener("click", () => DesignLibraryUI.newProject($("#newProjectBtn")));
  $("#deleteProjectBtn").addEventListener("click", deleteProject);
  $("#renameProjectBtn").addEventListener("click", renameProject);
  $("#restoreProjectBtn").addEventListener("click", restoreProject);
  $("#mCancel").addEventListener("click", () => closeModal($("#newModal")));
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
  scheduleSave();
  if (!await doSave()) return;
  await refreshProjects();
  $("#projectSelect").value = S.slug;
  renderMain();
  if (S.previewVisible && S.previewMode === "live") refreshLivePreview();
}

async function deleteProject() {
  if (!S.slug) return;
  const slug = S.slug;
  const proj = S.projects.find(p => p.slug === S.slug);
  const name = proj ? proj.title : S.slug;
  if (!confirm(t("delete_confirm").replace("{n}", name))) return;
  busyProject(true);
  try {
    if (!await doSave()) return;
    await api.del(`/api/projects/${encodeURIComponent(slug)}`);
    if(typeof InsightsUI!=="undefined")InsightsUI.projectDeleted(slug);
    projectStore.reset();
    S.slug = null; S.data = null; S.sel = { type: "report", idx: -1 };
    PreviewController.clearDocument();
    await refreshProjects();
    if (S.projects.length) await loadProject(S.projects[0].slug);
    else { $("#projectSelect").innerHTML = ""; renderSidebar(); renderMain(); }
  } catch (error) { toast(error.message, "err"); }
  finally { busyProject(false); updateDeleteBtn(); }
}

async function restoreProject() {
  if (!S.slug || projectStore.dirty) { toast(t("restore_pending"), "err"); return; }
  if (!confirm(S.uiLang === "en" ? "Restore the previous saved version?" : "¿Restaurar la versión anterior guardada?")) return;
  const slug = S.slug;
  busyProject(true);
  try {
    await appFetch(`/api/projects/${encodeURIComponent(slug)}/restore`, {method: "POST", headers: {"Content-Type": "application/json", "If-Match": projectStore.etag}, body: "{}"}).then(requireOk);
    await loadProject(slug);
  } catch (error) { toast(error.message, "err"); }
  finally { busyProject(false); updateDeleteBtn(); }
}

function updateDeleteBtn() {
  const restore = $("#restoreProjectBtn"); if (restore) restore.disabled = !S.slug || projectBusyCount > 0;
  const b = $("#deleteProjectBtn"); if (b) b.disabled = !S.slug || projectBusyCount > 0;
  const r = $("#renameProjectBtn"); if (r) r.disabled = !S.slug || projectBusyCount > 0;
}

let creatingProject=false;
async function createProject() {
  if(creatingProject)return;
  $("#newProjectError")?.remove();
  creatingProject=true;$("#mCreate").disabled=true;
  try {
    if(S.slug&&!await doSave())throw Error(S.uiLang==='en'?'The open project could not be saved. Resolve its save warning before creating another project.':'No se pudo guardar el proyecto abierto. Resuelve su aviso de guardado antes de crear otro proyecto.');
    const request = DesignLibraryUI.projectRequest();
    const r = await requireOk(await api.post(request.url, request.body));
    const { slug } = await r.json();
    if(typeof InsightsUI!=="undefined")InsightsUI.projectCreated(slug);
    closeModal($("#newModal"));
    $("#mTitle").value = $("#mClient").value = $("#mSlug").value = "";
    DesignLibraryUI.resetCreation();
    await refreshProjects();await loadProject(slug);$("#editor").focus({preventScroll:true});toast(t("toast_created"), "ok");
  } catch(error) {
    const message=error.message || t("create_fail"),modal=$("#newModal");
    if(modal.open)modal.querySelector('.modal-actions').before(h('p',{id:'newProjectError',role:'alert'},message));
    else toast(message,"err");
  }
  finally {creatingProject=false;$("#mCreate").disabled=false;}
}

function startupFailed(error) {
  hideSplash();
  let language=S.uiLang;
  try { language=localStorage.getItem("rg.uiLang")||language; } catch (_) {}
  const english=language==="en";
  document.querySelectorAll("button,select,input,textarea").forEach(control=>{control.disabled=true;});
  const editor=$("#editor");
  editor.replaceChildren(h("section",{class:"card",role:"alert"},
    h("h2",{},english?"report-gen could not start":"No se pudo iniciar report-gen"),
    h("p",{},english?"The local application did not finish loading. Reload it to retry. Your saved projects and browser drafts have not been replaced.":"La aplicación local no terminó de cargar. Recárgala para reintentar. Tus proyectos guardados y borradores del navegador no se han reemplazado."),
    h("p",{},error.message),
    h("button",{type:"button",class:"btn primary",onclick:()=>location.reload()},english?"Reload application":"Recargar aplicación")));
  $("#saveState").textContent=english?"startup error":"error de inicio";
  editor.focus({preventScroll:true});
}
init().catch(error => { console.error(error); startupFailed(error); }).finally(() => { try { hideSplash(); } catch (_) {} });

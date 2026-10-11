/* CVSS editor presentation. Scores come from CVSS31/CVSS40; project writes
 * continue through the shared editor save manager. */
const CVSSEditor = (() => {
'use strict';
const {metrics: CV, compute: cvssCompute, parse: cvssParse} = CVSS31;
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

const METRIC_NAME = {
  es: { AV:"Vector de ataque", AC:"Complejidad", AT:"Requisitos", PR:"Privilegios", UI:"Interacción",
        VC:"Confidencialidad", VI:"Integridad", VA:"Disponibilidad",
        SC:"Conf. posterior", SI:"Integr. posterior", SA:"Disp. posterior",
        S:"Alcance", C:"Confidencialidad", I:"Integridad", A:"Disponibilidad" },
  en: { AV:"Attack vector", AC:"Complexity", AT:"Requirements", PR:"Privileges", UI:"Interaction",
        VC:"Confidentiality", VI:"Integrity", VA:"Availability",
        SC:"Subseq. conf.", SI:"Subseq. integ.", SA:"Subseq. avail.",
        S:"Scope", C:"Confidentiality", I:"Integrity", A:"Availability" }
};
function cvssMetricLabel(k, val, version) {
  const opts = version === "4.0" ? CVSS4_OPTS[k] : (CV.OPTS || {})[k];
  const o = (opts || []).find(x => x[0] === val);
  return o ? o[1] : (val || "—");
}
function cvssPanel(r, dict, version) {
  const lang = S.uiLang || "es";
  const nm = METRIC_NAME[lang] || METRIC_NAME.es;
  const wrap = h("div", { class: "cvss-panel" });
  const top = h("div", { class: "cvss-panel-top" });
  top.append(h("div", { class: "cvss-scorecard sc-" + r.severity },
    h("div", { class: "cvss-score-big" }, r.score.toFixed(1)),
    h("div", { class: "tag sev-" + r.severity }, r.severity)));
  if (version === "4.0" && r.macrovector) {
    top.append(h("div", { class: "cvss-mvcard" },
      h("div", { class: "cvss-mv-lbl" }, "MacroVector"),
      h("div", { class: "cvss-mv-val" }, r.macrovector),
      h("div", { class: "cvss-mv-sub" }, "CVSS 4.0")));
  } else {
    top.append(h("div", { class: "cvss-mvcard" },
      h("div", { class: "cvss-mv-lbl" }, lang === "es" ? "Versión" : "Version"),
      h("div", { class: "cvss-mv-val" }, "CVSS " + version)));
  }
  wrap.append(top);
  const keys = version === "4.0" ? CVSS4_BASE : CV.M;
  const grid = h("div", { class: "cvss-metrics" });
  keys.forEach(k => grid.append(h("div", { class: "cvss-metric" },
    h("span", { class: "cm-k" }, nm[k] || k),
    h("span", { class: "cm-v" }, cvssMetricLabel(k, dict[k], version)))));
  wrap.append(h("div", { class: "cvss-metrics-title" }, lang === "es" ? "Métricas principales" : "Key metrics"), grid);
  wrap.append(h("div", { class: "cvss-vecrow" }, h("code", { class: "cvss-vec" }, r.vector), copyVectorBtn(r.vector)));
  return wrap;
}
function copyVectorBtn(vector) {
  let restoreTimer;
  const b = h("button", { type: "button", class: "btn sm", style: "padding:3px 9px;flex:none",
    title: t("copy_vector"), "aria-label": t("copy_vector"),
    onclick: async () => {
      clearTimeout(restoreTimer);
      b.disabled = true; b.setAttribute("aria-busy", "true"); b.textContent = "\u2026";
      try {
        if (typeof navigator.clipboard?.writeText !== "function") throw new Error("Clipboard unavailable");
        await navigator.clipboard.writeText(vector);
        b.textContent = "\u2713"; toast(t("copied"), "ok");
        restoreTimer = setTimeout(() => { b.textContent = "\u29C9"; }, 1000);
      } catch (_) {
        b.textContent = "\u29C9"; toast(t("copy_vector_failed"), "err");
      } finally {
        b.disabled = false; b.removeAttribute("aria-busy");
      }
    } }, "\u29C9");
  return b;
}
function applyPastedVector(f, raw, errEl) {
  let v = (raw || "").trim().replace(/\s+/g, "");  // admite espacios: "AV:N / AC:H" -> "AV:N/AC:H"
  if (!v) { errEl.textContent = ""; return; }
  let ver = f.cvss_version || "3.1";
  const mpref = v.match(/^CVSS:([0-9.]+)\//i);
  if (mpref) {
    if (!['3.1', '4.0'].includes(mpref[1])) { errEl.textContent = t('cvss_paste_bad'); return; }
    ver = mpref[1]; v = v.slice(mpref[0].length);
  }
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
  const version=f.cvss_version||"3.1";
  const wrap = h("div", { style: "margin-top:10px" });
  const verSel = h("select", { "aria-label":S.uiLang==="en"?"CVSS version":"Versión de CVSS", style: "width:auto;display:inline-block;margin-left:8px",
    onchange: e => {
      f.cvss_version = e.target.value;
      f.cvss = ""; f.cvss_vector = ""; f.macrovector = "";  // estado incompatible entre versiones
      scheduleSave(); renderMain();
    } },
    ["3.1", "4.0"].map(v => h("option", { value: v, selected: version === v ? "" : null }, "CVSS " + v)));
  wrap.append(h("h4", {}, t("calculator"), verSel));
  const pasteErr = h("span", { class: "cvss-paste-err" });
  const paste = h("input", { class: "cvss-paste", placeholder: t("cvss_paste_ph"), value: f.cvss_vector || "",
    onchange: e => applyPastedVector(f, e.target.value, pasteErr),
    onkeydown: e => { if (e.key === "Enter") applyPastedVector(f, e.target.value, pasteErr); } });
  wrap.append(h("label", { style: "margin-top:6px" }, t("cvss_paste_label"), h("div", { style: "display:flex;gap:8px;align-items:center" }, paste, pasteErr)));
  wrap.append(version === "4.0" ? cvss4Widget(f, sevSel) : cvss31Widget(f, sevSel));
  return wrap;
}

function cvss31Widget(f, sevSel) {
  const c = h("div", {});
  const bx = h("div", { class: "cvssbox" });
  let metrics = { ...CV.D };
  if (f.cvss_vector) {
    try { metrics = cvssParse(f.cvss_vector); }
    catch (_) { c.append(h('p', {class:'cvss-paste-err', role:'status'}, t('cvss_paste_bad'))); }
  }
  const out = h("div", { class: "cvssout" });
  function refresh() {
    const r = cvssCompute(metrics);
    f.cvss_version="3.1"; f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity;
    if (sevSel) sevSel.value = r.severity;
    out.innerHTML = "";
    out.append(cvssPanel(r, metrics, "3.1"));
    scheduleSave(); renderSidebar();
  }
  CV.M.forEach(k => {
    const sel = h("select", { title: (S.uiLang==="en"?METRIC_NAME.en[k]:CVSS_TIP[k]) || "", onchange: e => { metrics[k] = e.target.value; refresh(); } },
      CV.OPTS[k].map(o => h("option", { value: o[0], selected: metrics[k] === o[0] ? "" : null }, `${k}: ${o[1]}`)));
    bx.append(h("div", { class: "m" }, sel));
  });
  c.append(bx, out);
  const r0 = cvssCompute(metrics);
  out.append(cvssPanel(r0, metrics, "3.1"));
  return c;
}

function cvss4Widget(f, sevSel) {
  const c = h("div", {});
  if (!window.CVSS40) { c.append(h("p", { class: "cvss-vec" }, S.uiLang==="en"?"CVSS 4.0 calculator could not load":"No se pudo cargar la calculadora CVSS 4.0")); return c; }
  const C = window.CVSS40;
  const base = {};
  // The controls edit base metrics, but the score and saved vector must retain
  // every threat, environmental and supplemental metric supplied by the user.
  if (f.cvss_vector) {
    try { Object.assign(base, C.parseVector(f.cvss_vector)); }
    catch (_) { c.append(h('p', {class:'cvss-paste-err', role:'status'}, t('cvss_paste_bad'))); }
  }
  CVSS4_BASE.forEach(k => { if (!base[k]) base[k] = CVSS4_OPTS[k][0][0]; });
  if (Object.keys(base).some(k => !CVSS4_BASE.includes(k))) {
    c.append(h('p', {class:'field-hint'}, S.uiLang === 'en'
      ? 'Optional metrics in the pasted vector are included in the score and preserved when editing base metrics. Edit the full vector to change them.'
      : 'Las métricas opcionales del vector pegado se incluyen en la puntuación y se conservan al editar las métricas base. Modifica el vector completo para cambiarlas.'));
  }
  const bx = h("div", { class: "cvssbox" });
  const out = h("div", { class: "cvssout" });
  function draw(r) {
    out.innerHTML = "";
    out.append(cvssPanel(r, base, "4.0"));
  }
  function refresh() {
    const r = C.score(C.buildVector(base));  // toda la logica 4.0 en cvss40.js
    f.cvss = String(r.score); f.cvss_vector = r.vector; f.severity = r.severity; f.macrovector = r.macrovector;
    if (sevSel) sevSel.value = r.severity;
    draw(r); scheduleSave(); renderSidebar();
  }
  CVSS4_BASE.forEach(k => {
    const sel = h("select", { title: (S.uiLang==="en"?METRIC_NAME.en[k]:CVSS_TIP[k]) || "", onchange: e => { base[k] = e.target.value; refresh(); } },
      CVSS4_OPTS[k].map(o => h("option", { value: o[0], selected: base[k] === o[0] ? "" : null }, `${k}: ${o[1]}`)));
    bx.append(h("div", { class: "m" }, sel));
  });
  c.append(bx, out);
  draw(C.score(C.buildVector(base)));
  return c;
}

return Object.freeze({widget: cvssWidget, copyVectorButton: copyVectorBtn});
})();

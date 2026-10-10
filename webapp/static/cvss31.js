/* CVSS 3.1 Base scoring. Keep formula/validation in parity with cvss/v31.py. */
(function(root, factory) {
  const calculator = factory();
  if (typeof module === 'object' && module.exports) module.exports = calculator;
  else root.CVSS31 = calculator;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
'use strict';
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
  const mm = { ...CV.D };
  for (const key of CV.M) if (m?.[key]) mm[key] = m[key];
  if (CV.M.some(key => typeof mm[key] !== 'string' || !CV.OPTS[key].some(([value]) => value === mm[key]))) {
    throw Error('Métricas CVSS 3.1 inválidas / Invalid CVSS 3.1 metrics');
  }
  const ch = mm.S === "C";
  const pr = (ch ? CV.PRC : CV.PRU)[mm.PR];
  const expl = 8.22 * CV.AV[mm.AV] * CV.AC[mm.AC] * pr * CV.UI[mm.UI];
  const iss = 1 - (1 - CV.CIA[mm.C]) * (1 - CV.CIA[mm.I]) * (1 - CV.CIA[mm.A]);
  const impact = ch ? 7.52 * (iss - .029) - 3.25 * Math.pow(iss - .02, 15) : 6.42 * iss;
  let score = impact <= 0 ? 0 : ch ? roundup(Math.min(1.08 * (impact + expl), 10)) : roundup(Math.min(impact + expl, 10));
  score = Math.round(score * 10) / 10;
  return { score, severity: cvssSeverity(score), vector: "CVSS:3.1/" + CV.M.map(k => k + ":" + mm[k]).join("/"), metrics: mm };
}
function cvssParse(vector) {
  if (typeof vector !== 'string' || !vector.startsWith('CVSS:3.1/')) {
    throw Error('Se esperaba CVSS 3.1 Base completo / Expected a complete CVSS 3.1 Base vector');
  }
  const metrics = {};
  for (const item of vector.split('/').slice(1)) {
    const parts = item.split(':'), [key, value] = parts;
    if (parts.length !== 2 || !CV.M.includes(key) || Object.hasOwn(metrics, key) ||
        !CV.OPTS[key].some(([option]) => value === option)) {
      throw Error('Métrica CVSS inválida o duplicada / Invalid or duplicate CVSS metric');
    }
    metrics[key] = value;
  }
  if (Object.keys(metrics).length !== CV.M.length) throw Error('Vector CVSS incompleto / Incomplete CVSS vector');
  return metrics;
}
function deepFreeze(value) {
  for (const child of Object.values(value)) if (child && typeof child === 'object') deepFreeze(child);
  return Object.freeze(value);
}
return Object.freeze({ metrics: deepFreeze(CV), compute: cvssCompute, parse: cvssParse });
});

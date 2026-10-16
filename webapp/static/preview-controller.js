/* HTML/PDF preview lifecycle. Owns asynchronous generations and object URLs,
 * never a second copy of the project or its saved revision. */
const PreviewController = (() => {
'use strict';
let _plTimer = null, _plStart = 0;
function showPreviewLoading() {
  const el = document.getElementById("previewLoading");
  if (!el || !S.previewVisible) return;
  _plStart = Date.now(); clearTimeout(_plTimer); el.classList.add("show");
}
function hidePreviewLoading() {
  const el = document.getElementById("previewLoading");
  if (!el) return;
  const wait = Math.max(0, 480 - (Date.now() - _plStart));  // patita visible un mínimo
  clearTimeout(_plTimer); _plTimer = setTimeout(() => el.classList.remove("show"), wait);
}
let previewGeneration = 0;
let previewPdfUrl = null;
let livePreviewRequest = null;
function invalidateLivePreview() {
  previewGeneration++;livePreviewRequest=null;
  const frame=$("#pdfPreview");if(frame)frame.onload=null;
  hidePreviewLoading();
}
function previewPaneVisible() {
  return !!S.previewVisible && !!$("#pdfPreview")?.getClientRects().length;
}
function ensureLivePreview() {
  if (S.previewMode === 'live' && previewPaneVisible() && !projectStore.loading &&
      livePreviewRequest === null && !WorkbenchUI.hasLivePreview()) refreshLivePreview();
}
function releasePdfPreview() {
  if (previewPdfUrl) URL.revokeObjectURL(previewPdfUrl);
  previewPdfUrl = null;
}
async function refreshLivePreview() {
  if (!S.slug || !previewPaneVisible() || projectStore.loading || S.previewMode !== 'live') return;
  const slug = S.slug, generation = ++previewGeneration, snapshotRevision=projectStore.revision;
  const findingIds = new Map((S.data.findings || []).map(f => [f.uid, f.id]));
  livePreviewRequest = generation;
  let waitingForDocument = false;
  setPvStatus(t("updating")); showPreviewLoading();
  try {
    const r = await appFetch(`/api/projects/${S.slug}/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
    await requireOk(r);
    const html = await r.text();
    if (slug !== S.slug || generation !== previewGeneration || !previewPaneVisible() || S.previewMode !== 'live') return;
    const f = $("#pdfPreview");
    f.removeAttribute("src");
    f.setAttribute("sandbox", "allow-same-origin");  // el preview no ejecuta scripts del contenido
    waitingForDocument = true;
    f.onload = () => {
      if (slug !== S.slug || generation !== previewGeneration || S.previewMode !== 'live') return;
      const doc=f.contentDocument;
      // A queued load from an older srcdoc cannot claim the newer snapshot.
      if(doc?.querySelector('meta[name="rg-preview-generation"]')?.content!==String(generation))return;
      if (livePreviewRequest === generation) livePreviewRequest = null;
      if(typeof PreviewZoomUI!=="undefined")PreviewZoomUI.ready(doc);
      if(typeof WorkbenchUI!=="undefined")WorkbenchUI.previewReady(snapshotRevision,{slug,findingIds,document:doc});
    };
    f.srcdoc = html.replace(/<head(?:\s[^>]*)?>/i,head=>head+'<meta name="rg-preview-generation" content="'+generation+'">');
    releasePdfPreview();
    setPvStatus(t("uptodate"));
  } catch { if (generation === previewGeneration) setPvStatus(t("err")); }
  finally {
    if (!waitingForDocument && livePreviewRequest === generation) livePreviewRequest = null;
    if (generation === previewGeneration) hidePreviewLoading();
  }
}
function setPreviewVisible(vis) {
  S.previewVisible = vis;
  document.querySelector(".layout").classList.toggle("no-preview", !vis);
  const btn = $("#previewToggle");
  if (btn) btn.textContent = vis ? t("hide_preview") : t("show_preview");
  // el botón "Actualizar preview" no aplica cuando está oculto
  const pv = $("#previewBtn"); if (pv) pv.style.display = vis ? "" : "none";
  try { localStorage.setItem("rg.previewVisible", vis ? "1" : "0"); } catch (_) { /* sin storage */ }
  if(typeof ContextIndexUI!=="undefined")ContextIndexUI.update();
  if (vis && S.previewMode === "live") refreshLivePreview();
}

function setPreviewMode(m) {
  invalidateLivePreview();
  S.previewMode = m;
  if(typeof PreviewZoomUI!=="undefined")PreviewZoomUI.update();
  $("#pvLive").classList.toggle("primary", m === "live");
  $("#pvPdf").classList.toggle("primary", m === "pdf");
  if (m === "live") refreshLivePreview();
  else renderPdf(false);
}

async function renderPdf(download) {
  const generation = download ? previewGeneration : ++previewGeneration;
  if (!S.slug || !await doSave()) return;
  const slug = S.slug, snapshotRevision=projectStore.revision;
  if (!download && (generation !== previewGeneration || S.previewMode !== 'pdf')) return;
  setSaveState(t("updating")); if (!download) showPreviewLoading();
  try {
    const r = await appFetch(`/api/projects/${S.slug}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.data) });
    if (!r.ok) { const e = await r.json().catch(() => ({})); setSaveState(t("err")); toast("Render: " + (e.error || r.status), "err"); return; }
    const blob = await r.blob();
    if (!download && (slug !== S.slug || generation !== previewGeneration || S.previewMode !== 'pdf')) return;
    const url = URL.createObjectURL(blob);
    if (download) { const a = h("a", { href: url, download: (slug || "informe") + ".pdf" }); a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
    else { const f = $("#pdfPreview"); f.removeAttribute("sandbox"); f.removeAttribute("srcdoc"); f.setAttribute("src", url); releasePdfPreview(); previewPdfUrl = url; }
    if (slug === S.slug) {setSaveState(t(projectStore.dirty ? "saving" : "saved"));if(!download)WorkbenchUI.previewReady(snapshotRevision); }
  } catch (error) { if (download || generation === previewGeneration) toast(error.message, "err"); }
  finally { if (!download && generation === previewGeneration) hidePreviewLoading(); }
}

function clearDocument() {
  invalidateLivePreview(); releasePdfPreview();
  const frame = $('#pdfPreview');
  if (frame) { frame.removeAttribute('src'); frame.removeAttribute('srcdoc'); }
}
return Object.freeze({invalidateLivePreview, previewPaneVisible, ensureLivePreview,
  refreshLivePreview, setPreviewVisible, setPreviewMode, renderPdf, clearDocument});
})();

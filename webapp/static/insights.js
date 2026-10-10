/* Optional decision workspace. Reading never writes project data; every write is explicit and revision guarded. */
const InsightsUI = (() => {
  'use strict';
  const w = (es, en) => S.uiLang === 'en' ? en : es;
  const names = {
    claims: ['Afirmaciones y evidencia', 'Claims and evidence'], risk: ['Decisiones de negocio', 'Business decisions'],
    review: ['Mesa de revisión', 'Review desk'], audiences: ['Entregas por destinatario', 'Audience deliveries'],
    visual: ['Revisión visual', 'Visual review'], editorial: ['Ayuda editorial', 'Editorial assistance']
  };
  let generation = 0, state = null, currentSlug = null, publicationKey=null,publicationRequest=null;
  const drafts=new Map(),assistantProposals=new Map();
  function draft(key,initial){const id=S.slug+'|'+key;if(!drafts.has(id)){Object.defineProperty(initial,'_draftkey',{value:id,enumerable:false});drafts.set(id,initial);}return drafts.get(id);}
  const url = path => '/api/projects/' + encodeURIComponent(S.slug) + path;
  const clone = value => JSON.parse(JSON.stringify(value));
  function notice(es, en) { return h('p', {class: 'insights-note'}, w(es, en)); }
  function actions(...nodes) { return h('div', {class: 'insights-actions'}, ...nodes); }
  function card(...nodes) { return h('section', {class: 'insights-card'}, ...nodes); }
  function button(es, en, run, id, primary = false) {
    const b = h('button', {type: 'button', class: 'btn' + (primary ? ' primary' : ''), 'data-insights-action': id}, w(es, en));
    if(id&&(/-(previous|next)$/.test(id))){b.addEventListener('click',()=>{if(projectBusyCount>0)return;try{run(b);}catch(error){toast(error.message,'err');}});return b;}
    b.addEventListener('click', async () => {
      if (projectBusyCount > 0) return;
      b.disabled = true;
      try { await run(b); } catch (error) { toast(error.message, 'err'); }
      finally { if (b.isConnected) b.disabled = projectBusyCount > 0; }
    });
    return b;
  }
  function field(es, en, object, key, options = {}) {
    const tag = options.rows ? 'textarea' : 'input';
    const input = h(tag, {type: options.rows ? null : 'text', rows: options.rows, maxlength: options.maxlength || 4000, 'data-insights-field': key});
    input.value = object[key] ?? '';
    input.addEventListener('input', () => { object[key] = input.value; });
    return h('label', {class: 'insights-field'}, h('span', {}, w(es, en)), input);
  }
  function choose(es, en, object, key, choices) {
    const input = h('select', {'data-insights-field': key}, choices.map(([value, a, b]) => h('option', {value}, w(a, b ?? a))));
    if(key==='finding_uid'&&object[key]&&!choices.some(row=>row[0]===object[key]))object[key]='';
    input.value = object[key] ?? choices[0]?.[0] ?? '';
    input.addEventListener('change', () => { object[key] = input.value; input.dispatchEvent(new Event('insights-change', {bubbles: true})); });
    return h('label', {class: 'insights-field'}, h('span', {}, w(es, en)), input);
  }
  function checkbox(es, en, checked, run, key) {
    const input = h('input', {type: 'checkbox', checked: checked ? '' : null, 'data-insights-check': key});
    input.addEventListener('change', () => run(input.checked));
    return h('label', {class: 'insights-check'}, input, w(es, en));
  }
  function findingChoices(optional = false) {
    return (optional ? [['', w('Todo el informe', 'Whole report')]] : [['', w('Elige un hallazgo', 'Choose a finding')]])
      .concat((state?.map?.findings || []).map(f => [f.uid, (f.id || '') + ' · ' + (f.title || w('Sin título', 'Untitled'))]));
  }
  function titleFor(uid) { const f = state?.map?.findings?.find(row => row.uid === uid); return f ? (f.id || '') + ' · ' + f.title : uid || w('Informe', 'Report'); }
  function reveal(node) {
    if (!node) return;
    if(!node.matches('button,a,input,select,textarea,summary,[tabindex]'))node.setAttribute('tabindex','-1');
    node.focus({preventScroll: true});
    const rect = node.getBoundingClientRect(), editor = $('#editor').getBoundingClientRect();
    if (rect.top < Math.max(0, editor.top) || rect.bottom > Math.min(innerHeight, editor.bottom)) node.scrollIntoView({block: 'start', behavior: 'instant'});
  }
  function open(tab = 'claims') {
    if (projectBusyCount > 0 || !S.slug) return;
    $('#studioMore')?.removeAttribute('open');
    select('insights', names[tab] ? tab : 'claims');
    reveal($('#insightsTitle'));
  }
  async function saved() {
    if (!S.slug) throw Error(w('Abre un proyecto primero.', 'Open a project first.'));
    const slug = S.slug;
    if (!await doSave()) throw Error(w('Guarda el proyecto antes de continuar.', 'Save the project before continuing.'));
    if (S.slug !== slug) throw Error(w('El proyecto cambió. Abre de nuevo esta pantalla.', 'The project changed. Reopen this screen.'));
    return {slug, etag: projectStore.etag};
  }
  async function request(path, body, method = 'POST') {
    busyProject(true);
    try {
      const snapshot = await saved();
      const response = await requireOk(await appFetch('/api/projects/' + encodeURIComponent(snapshot.slug) + path, {
        method, headers: {'Content-Type': 'application/json', 'If-Match': snapshot.etag}, body: JSON.stringify(body)
      }));
      if (S.slug !== snapshot.slug) throw Error(w('La operación pertenece al proyecto anterior.', 'The operation belongs to the previous project.'));
      return response;
    } finally { busyProject(false); }
  }
  async function mutate(body,form,context = null) {
    const slug = S.slug;let locked=!!context;
    if(context)busyProject(true);
    try {
      const response = await request('/insights', body);
      await response.json();
      if(form?._draftkey)drafts.delete(form._draftkey);
      if (S.slug !== slug) return;
      await projectStore.load(slug);
      if(S.slug!==slug)return;
      const selectedUid=context&&S.sel.type==='finding'?WorkbenchUI.renderedFindingUid():null;
      S.data = projectStore.data;
      if (selectedUid && S.sel.type === 'finding') {
        const index = S.data.findings.findIndex(item => item.uid === selectedUid);
        S.sel = index < 0 ? {type:'report',idx:-1} : {type:'finding',idx:index};
      }
      renderSidebar(); renderMain();
      if(locked){busyProject(false);locked=false;}
      if(!context)reveal($('#insightsTitle'));
      else if(selectedUid===context.uid)reveal($('#editor [data-finding-tab="decisions"]') || $('#editor .finding-context-title strong'));
      toast(w('Decisión guardada en esta revisión.', 'Decision saved in this revision.'));
    } finally {
      if(locked)busyProject(false);
    }
  }
  async function downloadResponse(response, fallback) {
    const blob = await response.blob(), target = URL.createObjectURL(blob);
    const disposition = response.headers.get('Content-Disposition') || '';
    const name = disposition.match(/filename="?([^";]+)"?/)?.[1] || fallback;
    const a = h('a', {href: target, download: name}); document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(target), 30000);
  }
  function evidenceList(object, key = 'evidence_uids') {
    const set = new Set(object[key] || []), group = h('fieldset', {class: 'insights-evidence-select'}, h('legend', {}, w('Evidencia que sostiene esta afirmación', 'Evidence supporting this claim')));
    for (const e of state?.map?.evidence || []) group.append(checkbox(e.title || e.uid, e.title || e.uid, set.has(e.uid), checked => {
      if (checked) set.add(e.uid); else set.delete(e.uid); object[key] = [...set];
    }, e.uid));
    if (!state?.map?.evidence?.length) group.append(notice('Todavía no hay evidencias registradas. Puedes documentar una hipótesis sin presentarla como observación.', 'No evidence is registered yet. You can document a hypothesis without presenting it as an observation.'));
    return group;
  }
  function evidenceContext(uid) {
    const evidence = state?.map?.evidence?.find(e => e.uid === uid);
    if (!evidence) return h('p', {}, w('Referencia de evidencia ausente: ', 'Missing evidence reference: ') + uid);
    const wrapper = h('details', {class: 'insights-evidence'}, h('summary', {}, evidence.title || uid));
    wrapper.addEventListener('toggle', async () => {
      if (!wrapper.open || wrapper.dataset.loaded || !S.slug) return;
      wrapper.dataset.loaded = 'true';
      const slug = S.slug, revision = projectStore.etag;
      const content = h('div', {class: 'insights-evidence-content'}, h('p', {}, evidence.caption || ''), notice('Copia de publicación con el procesamiento y las censuras registrados; no es el archivo original privado.', 'Publication derivative with recorded processing and redactions; this is not the private original.'));
      wrapper.append(content);
      try {
        const key=slug+'|'+revision;if(publicationKey!==key||!publicationRequest){publicationKey=key;publicationRequest=api.get('/api/projects/'+encodeURIComponent(slug)+'/publication').catch(error=>{publicationRequest=null;throw error;});}
        const report=await publicationRequest;
        if (S.slug !== slug || projectStore.etag !== revision || !content.isConnected) return;
        const name = evidence.src?.replace(/^images\//, '');
        const image = (report.images || []).find(item => item.name === name || item.name === evidence.src);
        if (image) content.append(h('img', {src: '/api/projects/' + encodeURIComponent(slug) + '/publication/image?name=' + encodeURIComponent(image.name) + '&revision=' + encodeURIComponent(report.revision), alt: evidence.caption || evidence.title || w('Evidencia publicada', 'Published evidence'), loading: 'lazy'}));
        else content.append(notice('La copia publicada no contiene esta imagen. Revisa la evidencia y el inspector.', 'The publication copy does not contain this image. Review the evidence and publication inspector.'));
      } catch (error) { if (content.isConnected) content.append(h('p', {role: 'alert'}, error.message)); }
    });
    return wrapper;
  }
  function paged(host, rows, build, size=30) {
    const listing=h('div',{}),nav=actions(),count=h('span',{role:'status'});let page=0;
    const previous=button('Anterior','Previous',()=>{page--;paint();reveal(listing.querySelector('summary,button,h3')||count);},'collection-previous'),next=button('Siguiente','Next',()=>{page++;paint();reveal(listing.querySelector('summary,button,h3')||count);},'collection-next');
    nav.append(previous,count,next);host.append(listing);if(rows.length>size)host.append(nav);
    function paint(){listing.replaceChildren(...rows.slice(page*size,page*size+size).map(build));count.textContent=(rows.length?page*size+1:0)+'–'+Math.min(rows.length,page*size+size)+' / '+rows.length;previous.disabled=page===0;next.disabled=(page+1)*size>=rows.length;}
    paint();
  }
  function claims(box) {
    box.append(notice('Distingue lo observado de una inferencia o hipótesis. Vincula el contenido exacto que sostiene tu conclusión y registra sus límites.', 'Distinguish observations from inferences or hypotheses. Link the specific evidence supporting the conclusion and record its limits.'));
    const map = card(h('h2', {}, w('Mapa de trabajo', 'Work map'))), grid = h('div', {class: 'insights-map'});
    const source = state.map?.findings || []; let page = 0;
    const listing = h('div', {}), controls = actions(), counter = h('span', {role: 'status'});
    const previous = button('Anterior', 'Previous', () => { page--; draw(); }, 'map-previous');
    const next = button('Siguiente', 'Next', () => { page++; draw(); }, 'map-next');
    function draw() {
      listing.replaceChildren(); grid.replaceChildren();
      for (const f of source.slice(page * 20, page * 20 + 20)) {
        const row = card(h('h3', {}, f.id + ' · ' + f.title), button('Abrir hallazgo', 'Open finding', () => {
          const index = S.data.findings.findIndex(item => item.uid === f.uid); if (index < 0) throw Error(w('Hallazgo no disponible.', 'Finding unavailable.'));
          select('finding', index); reveal($('#editor'));
        }, 'open-finding'));
        const assets = (f.asset_uids || []).map(uid => state.map.assets.find(a => a.uid === uid)?.name || uid);
        row.append(h('p', {}, w('Activos: ', 'Assets: ') + (assets.join(', ') || w('Sin vincular', 'Not linked'))), h('p', {}, w('Evidencias: ', 'Evidence: ') + (f.evidence_uids || []).length));
        for (const uid of f.evidence_uids || []) row.append(evidenceContext(uid));
        for (const c of state.claims.filter(c => c.finding_uid === f.uid)) row.append(h('p', {class: 'insights-map-claim'}, w(...({observed:['Observación','Observation'],inference:['Inferencia','Inference'],hypothesis:['Hipótesis','Hypothesis']}[c.kind]||[c.kind,c.kind])) + ': ' + c.statement));
        if (f.retests?.length) row.append(h('p', {}, w('Retests registrados: ', 'Recorded retests: ') + f.retests.map(r => r.result + ' (' + r.tested_on + ')').join(', ')));
        grid.append(row);
      }
      counter.textContent = source.length ? (page * 20 + 1) + '–' + Math.min(source.length, page * 20 + 20) + ' / ' + source.length : w('Sin hallazgos', 'No findings');
      previous.disabled = page === 0; next.disabled = (page + 1) * 20 >= source.length; listing.append(grid);
    }
    controls.append(previous, counter, next); draw(); map.append(listing, controls); box.append(map);
    const collection = card(h('h2', {}, w('Afirmaciones registradas', 'Recorded claims')));
    const editor = card(h('h2', {}, w('Añadir afirmación', 'Add claim')), claimForm({finding_uid: '', statement: '', kind: 'observed', demonstrates: '', does_not_demonstrate: '', evidence_uids: []}));
    if (!state.claims.length) collection.append(notice('Escribe tu primera afirmación. Ninguna se genera automáticamente.', 'Write your first claim. None is generated automatically.'));
    paged(collection,state.claims,item=>claimRow(item,editor));
    box.append(collection, editor);
  }
  function findingFormContext(form, context) {
    return context ? h('p', {class:'insights-note','data-decision-finding-uid':context.uid}, w('Hallazgo: ', 'Finding: ') + titleFor(context.uid)) : choose('Hallazgo', 'Finding', form, 'finding_uid', findingChoices());
  }
  function claimRow(item, editor, context = null) {
    const row = h('details', {'data-claim-uid':item.uid}, h('summary', {}, titleFor(item.finding_uid) + ': ' + item.statement));
    row.append(h('p', {}, w('Tipo de afirmación: ', 'Claim type: ') + w(...({observed:['Observación','Observation'],inference:['Inferencia','Inference'],hypothesis:['Hipótesis','Hypothesis']}[item.kind]||[item.kind,item.kind]))), h('p', {}, w('Demuestra: ', 'Demonstrates: ') + item.demonstrates), h('p', {}, w('No demuestra: ', 'Does not demonstrate: ') + item.does_not_demonstrate));
    for (const uid of item.evidence_uids || []) row.append(evidenceContext(uid));
    row.append(actions(button('Editar', 'Edit', () => { editor.replaceChildren(claimForm(clone(item),context)); reveal(editor.querySelector('input,textarea,select')); }, 'edit-claim'), button('Eliminar esta afirmación', 'Remove this claim', () => mutate({action: 'delete_claim', uid: item.uid},null,context), 'delete-claim')));
    return row;
  }
  function claimForm(form, context = null) {
    form=draft('claim-'+(form.uid||(context?'new-'+context.uid:'new')),form);
    return h('div', {class: 'insights-form'}, findingFormContext(form, context),
      choose('Tipo de afirmación', 'Claim type', form, 'kind', [['observed','Observación','Observation'],['inference','Inferencia','Inference'],['hypothesis','Hipótesis','Hypothesis']]),
      field('Afirmación', 'Claim', form, 'statement', {rows: 3}), field('Qué demuestra', 'What it demonstrates', form, 'demonstrates', {rows: 3}),
      field('Qué no demuestra', 'What it does not demonstrate', form, 'does_not_demonstrate', {rows: 3}), evidenceList(form),
      button('Guardar afirmación', 'Save claim', () => mutate({action: 'set_claim', ...form},form,context), 'save-claim', true));
  }
  function risk(box) {
    box.append(notice('La prioridad de negocio es una decisión documentada, separada de CVSS y de la severidad técnica. La herramienta no inventa apetito de riesgo ni aprueba tolerancias.', 'Business priority is a documented decision, separate from CVSS and technical severity. The tool does not invent risk appetite or approve tolerances.'));
    const list = card(h('h2', {}, w('Decisiones registradas', 'Recorded decisions')));
    const editor = card(h('h2', {}, w('Documentar prioridad', 'Document priority')), riskForm({finding_uid: '', service: '', objective: '', consequence: '', tolerance: '', source: '', assumptions: '', priority: 'unassigned', rationale: '', owner: ''}));
    paged(list,state.risks,item=>riskRow(item,editor));
    if (!state.risks.length) list.append(notice('Sin decisiones de negocio registradas.', 'No business decisions recorded.'));
    box.append(list, editor);
  }
  const riskNames = {objective:['Objetivo de negocio','Business objective'], consequence:['Consecuencia','Consequence'], tolerance:['Tolerancia acordada (vacío: no acordada)','Agreed tolerance (empty: not agreed)'], source:['Fuente o acuerdo','Source or agreement'], assumptions:['Supuestos y límites','Assumptions and limits'], rationale:['Justificación de prioridad','Priority rationale'], owner:['Responsable de la decisión','Decision owner']};
  function riskRow(item, editor, context = null) {
    return h('details', {'data-risk-uid':item.uid}, h('summary', {}, (item.priority==='unassigned'?w('Sin prioridad asignada','Priority unassigned'):item.priority) + ' · ' + item.service + ' · ' + titleFor(item.finding_uid)),
      h('dl', {class: 'insights-definition'}, ...['objective','consequence','tolerance','source','assumptions','rationale','owner'].flatMap(key => [h('dt', {}, w(...riskNames[key])), h('dd', {}, item[key] || (key === 'tolerance' ? w('No acordada', 'Not agreed') : w('No registrado', 'Not recorded')))])),
      actions(button('Editar decisión', 'Edit decision', () => { editor.replaceChildren(riskForm(clone(item),context)); reveal(editor.querySelector('input,textarea,select')); }, 'edit-risk'), button('Eliminar decisión', 'Remove decision', () => mutate({action: 'delete_risk', uid: item.uid},null,context), 'delete-risk')));
  }
  function riskForm(form, context = null) {
    form=draft('risk-'+(form.uid||(context?'new-'+context.uid:'new')),form);
    return h('div', {class: 'insights-form'}, findingFormContext(form, context), field('Servicio afectado', 'Affected service', form, 'service'),
      ...Object.entries(riskNames).map(([key, labels]) => field(...labels, form, key, {rows: ['consequence','rationale','assumptions'].includes(key) ? 3 : null})),
      choose('Prioridad acordada', 'Agreed priority', form, 'priority', [['unassigned','Sin asignar','Unassigned'],['P1','P1','P1'],['P2','P2','P2'],['P3','P3','P3']]),
      button('Guardar decisión', 'Save decision', () => mutate({action: 'set_risk', ...form},form,context), 'save-risk', true));
  }
  function review(box) {
    const names = {not_reviewed:['Sin revisión editorial','Not editorially reviewed'],approved:['Revisión editorial aprobada','Editorial review approved'],changes_requested:['Cambios solicitados','Changes requested'],stale:['Revisión anterior: el contenido cambió','Previous review: content has changed']};
    box.append(card(h('h2', {}, w(...(names[state.review_status?.state] || names.not_reviewed))), notice('Las firmas de autor son declaraciones locales. Aprobar una revisión editorial no verifica una vulnerabilidad ni autoriza una publicación.', 'Author identities are local declarations. Editorial approval does not verify a vulnerability or authorize publication.'), h('p', {class: 'insights-hash'}, w('Contenido revisado: ', 'Reviewed content: ') + state.digest)));
    const form = draft('comment-new',{finding_uid: '', field: 'report', body: '', author: '', visibility: 'private'});
    const context = h('pre', {class: 'insights-context', tabindex: 0}), pane = h('div', {class: 'insights-split'});
    const editor = card(h('h2', {}, w('Añadir observación', 'Add observation')),
      choose('Contexto', 'Context', form, 'finding_uid', findingChoices(true)), choose('Campo', 'Field', form, 'field', [['report','Informe','Report'],['description_md','Descripción','Description'],['impact_md','Impacto','Impact'],['remediation_md','Remediación','Remediation']]),
      field('Observación', 'Comment', form, 'body', {rows: 4}), field('Autor (declaración local)', 'Author (local declaration)', form, 'author'), choose('Visibilidad del comentario', 'Comment visibility', form, 'visibility', [['private','Privado','Private'],['public','Apto para revisión pública','Suitable for public review']]),
      notice('La visibilidad del comentario no publica nada. Las entregas por destinatario excluyen los comentarios internos.', 'Comment visibility does not publish anything. Audience deliveries exclude internal comments.'), button('Guardar observación', 'Save comment', () => mutate({action:'add_comment',field:form.field,body:form.body,author:form.author,visibility:form.visibility,...(form.finding_uid?{finding_uid:form.finding_uid}:{})},form), 'add-comment', true));
    function showContext() { const f = S.data.findings?.find(f => f.uid === form.finding_uid); context.textContent = f ? (f[form.field] || w('Este campo no tiene texto.', 'This field has no text.')) : (S.data.meta.report_title || S.slug); }
    editor.addEventListener('insights-change', showContext); showContext(); pane.append(editor, card(h('h2', {}, w('Texto de contexto (solo lectura)', 'Context text (read only)')), context)); box.append(pane);
    const comments = card(h('h2', {}, w('Observaciones por revisión', 'Revision comments')));
    paged(comments,state.comments,comment=>{
      const resolution = draft('resolve-'+comment.uid,{resolution: '', author: ''});
      const row = h('details', {open: comment.status === 'open' ? '' : null}, h('summary', {}, (comment.status==='open'?w('Abierta','Open'):w('Resuelta','Resolved')) + ' · ' + titleFor(comment.finding_uid) + ' · ' + comment.field), h('p', {}, comment.body),
        h('p', {}, comment.author + ' · ' + (comment.visibility==='private'?w('Privada','Private'):w('Pública declarada','Self-declared public')) + ' · ' + comment.created), h('p', {class:'insights-hash'}, w('Revisión: ', 'Revision: ') + comment.revision));
      if (comment.status === 'open') row.append(field('Cómo se resolvió', 'How it was resolved', resolution, 'resolution', {rows: 2}), field('Autor de la resolución', 'Resolution author', resolution, 'author'), button('Registrar resolución', 'Record resolution', () => mutate({action:'resolve_comment',uid:comment.uid,...resolution},resolution), 'resolve-comment'));
      else row.append(h('p', {}, comment.resolution || ''));
      return row;
    });
    if (!state.comments.length) comments.append(notice('No hay observaciones registradas.', 'No comments recorded.'));
    const decision = draft('review-new',{decision: 'changes_requested', author: '', notes: ''});
    box.append(comments, card(h('h2', {}, w('Registrar revisión de este contenido', 'Record review of this content')), choose('Decisión editorial', 'Editorial decision', decision, 'decision', [['changes_requested','Solicitar cambios','Request changes'],['approved','Aprobación editorial','Editorial approval']]), field('Autor de la revisión', 'Review author', decision, 'author'), field('Notas de revisión', 'Review notes', decision, 'notes', {rows:3}), button('Registrar revisión', 'Record review', () => mutate({action:'review',...decision},decision), 'record-review', true)));
  }
  const planLabels={originals:['Archivos originales privados','Private original files'],capture_inbox:['Bandeja de captura','Capture inbox'],private_backup:['Respaldo editable privado','Private editable backup'],private_history:['Historial privado','Private history'],review_comments:['Comentarios internos de revisión','Internal review comments'],editorial_reviews:['Decisiones editoriales internas','Internal editorial decisions'],selected_findings_full_content:['Contenido completo de los hallazgos seleccionados','Full content of selected findings'],selected_sections:['Secciones seleccionadas','Selected sections'],enabled_assets_coverage_retest:['Activos, cobertura y retest habilitados','Enabled assets, coverage and retest'],cleaned_rendered_images:['Imágenes procesadas y sin metadatos','Processed metadata-free images'],included_attachments:['Anexos habilitados','Enabled attachments'],report_identity:['Identidad del informe','Report identity'],unselected_findings:['Hallazgos no seleccionados','Unselected findings'],unselected_sections:['Secciones no seleccionadas','Unselected sections'],commands:['Comandos','Commands'],raw_targets_paths:['Objetivos y rutas técnicas originales','Raw technical targets and paths'],images:['Imágenes','Images'],attachments:['Anexos','Attachments'],contacts:['Contactos','Contacts'],assets:['Activos detallados','Detailed assets'],coverage:['Cobertura detallada','Detailed coverage'],retests:['Retests detallados','Detailed retests'],raw_evidence:['Evidencia técnica original','Raw technical evidence'],source_sections:['Secciones de origen','Source sections'],custom_metadata:['Metadatos personalizados','Custom metadata'],authored_public_title_alias:['Título y alias público redactados','Authored public title and alias'],explicitly_approved_public_text:['Texto público redactado y revisado explícitamente','Explicitly authored and reviewed public text'],declared_publication_basis:['Procedencia y permiso declarados','Declared provenance and permission'],source_titles:['Títulos técnicos de origen','Source technical titles'],source_descriptions:['Descripciones de origen','Source descriptions'],source_impacts:['Impactos de origen','Source impacts'],source_remediations:['Remediaciones de origen','Source remediations'],technical_scores:['Puntuaciones técnicas','Technical scores'],source_finding_ids_uids:['Identificadores originales de hallazgo','Original finding identifiers'],all_insights:['Todo el espacio de decisiones internas','All internal decision workspace content'],prose_titles_descriptions_impacts_remediation:['Título, descripción, impacto y mitigación en prosa','Prose title, description, impact and remediation'],technical_severity_cvss:['Severidad técnica y CVSS registrados','Recorded technical severity and CVSS'],structured_business_decisions:['Decisiones de negocio documentadas','Documented business decisions'],selected_client_alias_or_client:['Alias o nombre de cliente elegido','Selected client alias or name'],inline_code:['Código en línea','Inline code'],code_blocks:['Bloques de código','Code blocks'],link_targets:['Destinos de enlaces','Link destinations'],claims:['Afirmaciones técnicas detalladas','Detailed technical claims']};
  function audiences(box) {
    box.append(notice('Cada perfil genera archivos independientes. Un filtro de pantalla no elimina contenido de un HTML. Comprueba el plan y el archivo final antes de compartir.', 'Each profile generates independent files. A screen filter does not remove HTML content. Review the plan and final file before sharing.'));
    const source = state.map?.findings || [], settings=draft('audience-new',{selected:new Set((state.map?.findings||[]).map(f=>f.uid)),form:{profile:'technical',title:'',client_alias:'',provenance_label:'simulation',review_confirmed:false,publish_consent:false},alias:{needle:S.data.meta.client||'',replacement:''},authored:new Map(),selectedSections:new Set((S.data.report?.sections||[]).map(s=>s.key)),sectionsChanged:false,formats:new Set(['pdf','docx','md','html'])}),selected=settings.selected;
    const form = settings.form;
    
    const alias=settings.alias,authored=settings.authored,selectedSections=settings.selectedSections,formats=settings.formats;
    const live=new Set(source.map(f=>f.uid));for(const uid of selected)if(!live.has(uid))selected.delete(uid);for(const uid of authored.keys())if(!live.has(uid))authored.delete(uid);const liveSections=new Set([...(S.data.report?.sections||[]).map(row=>row.key),'rg_assets','rg_coverage','rg_retest']);for(const key of selectedSections)if(!liveSections.has(key))selectedSections.delete(key);
    const editor = card(h('h2', {}, w('Configurar destinatario', 'Configure audience'))), contents = h('div', {}), results = card(h('h2', {}, w('Plan de publicación', 'Publication plan'))), resultStatus = h('p', {role:'status'});
    const profile = choose('Perfil', 'Profile', form, 'profile', [['technical','Informe técnico','Technical report'],['executive','Resumen de dirección','Executive summary'],['public','Caso público revisado','Reviewed public case']]);
    editor.append(profile, field('Título de la entrega (opcional)', 'Delivery title (optional)', form, 'title'), contents);
    let sectionsChanged=settings.sectionsChanged;
    const sectionBox = h('fieldset', {}, h('legend', {}, w('Secciones técnicas incluidas', 'Included technical sections')));
    const shownSections=new Set((S.data.report?.sections||[]).map(s=>s.key));
    for (const s of S.data.report?.sections || []) sectionBox.append(checkbox(S.catBy?.[s.key]?.['title_'+S.uiLang] || s.title || s.key, S.catBy?.[s.key]?.['title_'+S.uiLang] || s.title || s.key, selectedSections.has(s.key), checked => {sectionsChanged=true;settings.sectionsChanged=true;if(checked)selectedSections.add(s.key);else selectedSections.delete(s.key);}, s.key));
    const selection = h('fieldset', {}, h('legend', {}, w('Hallazgos incluidos', 'Included findings'))), list = h('div', {}), search = h('input', {type:'search',placeholder:w('Buscar por título o ID', 'Search title or ID'),'aria-label':w('Buscar hallazgos para la entrega', 'Search delivery findings')});
    let page = 0;
    const count = h('p', {role:'status'}), paging = actions();
    const previous = button('Anterior', 'Previous', () => {page--; paintSelection();}, 'audience-previous'), next = button('Siguiente', 'Next', () => {page++; paintSelection();}, 'audience-next');
    paging.append(previous, next); selection.append(search, count, list, paging);
    function paintSelection() {
      list.replaceChildren(); const query = search.value.toLocaleLowerCase(), matching = source.filter(f => (f.id+' '+f.title).toLocaleLowerCase().includes(query));
      const maxPage = Math.max(0, Math.ceil(matching.length/30)-1); page = Math.min(page,maxPage);
      for (const f of matching.slice(page*30,page*30+30)) list.append(checkbox(f.id+' · '+f.title, f.id+' · '+f.title, selected.has(f.uid), checked => {
        if(checked)selected.add(f.uid);else selected.delete(f.uid);count.textContent=selected.size+' '+w('seleccionados','selected')+' / '+source.length;paintPublic();invalidate();
      }, f.uid));
      count.textContent = selected.size+' '+w('seleccionados','selected')+' / '+source.length+' · '+matching.length+' '+w('coincidencias','matches'); previous.disabled=page===0;next.disabled=page===maxPage;
    }
    search.addEventListener('input',()=>{page=0;paintSelection();});
    const publicBox = h('div', {}), safeBox = h('div', {});
    safeBox.append(field('Alias de cliente', 'Client alias', form, 'client_alias'), field('Nombre literal a sustituir', 'Literal name to replace', alias, 'needle'), field('Sustitución explícita', 'Explicit replacement', alias, 'replacement'));
    let publicPage=settings.publicPage||0;
    function paintPublic() {
      publicBox.replaceChildren(); if(form.profile!=='public')return;
      publicBox.append(notice('Redacta contenido público nuevo para cada hallazgo seleccionado. Los campos empiezan vacíos; no copiamos texto técnico ni evidencias privadas.', 'Author new public content for each selected finding. Fields begin empty; technical text and private evidence are not copied.'));
      const publicRows=source.filter(f=>selected.has(f.uid));publicPage=Math.min(publicPage,Math.max(0,Math.ceil(publicRows.length/20)-1));settings.publicPage=publicPage;
      for(const f of publicRows)if(!authored.has(f.uid))authored.set(f.uid,{finding_uid:f.uid,title:'',summary:'',impact:'',remediation:''});
      const publicHeading=h('h3',{tabindex:'-1','data-public-page-title':''},w('Texto público seleccionado: ','Selected public text: ')+(publicRows.length?publicPage*20+1:0)+'–'+Math.min(publicRows.length,publicPage*20+20)+' / '+publicRows.length);publicBox.append(publicHeading);
      if(publicRows.length>20){const previous=button('Texto anterior','Previous text',()=>{publicPage--;paintPublic();reveal(publicBox.querySelector('[data-public-page-title]'));},'public-previous'),next=button('Texto siguiente','Next text',()=>{publicPage++;paintPublic();reveal(publicBox.querySelector('[data-public-page-title]'));},'public-next');previous.disabled=publicPage===0;next.disabled=(publicPage+1)*20>=publicRows.length;publicBox.append(actions(previous,next));}
      for(const f of publicRows.slice(publicPage*20,publicPage*20+20)) {
        const content=authored.get(f.uid);
        publicBox.append(h('details',{open:''},h('summary',{},f.id+' · '+f.title),field('Título público','Public title',content,'title'),field('Resumen público','Public summary',content,'summary',{rows:3}),field('Impacto público','Public impact',content,'impact',{rows:3}),field('Mitigación pública','Public remediation',content,'remediation',{rows:3})));
      }
      publicBox.append(choose('Procedencia declarada', 'Declared provenance', form, 'provenance_label', [['simulation','Simulación: caso ficticio','Simulation: fictional case'],['authorized','Evaluación autorizada: autorización propia','Authorized assessment: your own authorization']]),
        checkbox('Revisé el texto, las sustituciones y los límites del caso.','I reviewed the text, replacements and case limitations.',form.review_confirmed,v=>{form.review_confirmed=v;invalidate();},'review-confirmed'),
        checkbox('Tengo autorización para publicar este contenido.','I am authorized to publish this content.',form.publish_consent,v=>{form.publish_consent=v;invalidate();},'publish-consent'));
    }
    let preview = null;
    function invalidate(){preview=null;resultStatus.textContent=w('Configuración cambiada. Vuelve a comprobar el plan antes de generar.','Configuration changed. Check the plan again before generating.');exportButton.disabled=true;}
    function options(){return {profile:form.profile,finding_uids:[...selected],...(form.profile==='technical'&&sectionsChanged?{section_keys:[...selectedSections]}:{}),...(form.title?{title:form.title}:{}),...(form.client_alias?{client_alias:form.client_alias}:{}),aliases:alias.needle&&alias.replacement?[{...alias}]:[],...(form.profile==='public'?{review_confirmed:form.review_confirmed,publish_consent:form.publish_consent,provenance_label:form.provenance_label,approved_content:source.filter(f=>selected.has(f.uid)).map(f=>({...authored.get(f.uid)}))}:{})};}
    function paintProfile(){sectionBox.hidden=form.profile!=='technical';safeBox.hidden=form.profile==='technical';paintSelection();paintPublic();invalidate();}
    profile.querySelector('select').addEventListener('change',()=>{selected.clear();if(form.profile!=='public')source.forEach(f=>selected.add(f.uid));paintProfile();});
    const formatBox=h('fieldset',{},h('legend',{},w('Formatos independientes','Independent formats')));
    for(const name of ['pdf','docx','md','html'])formatBox.append(checkbox(name.toUpperCase(),name.toUpperCase(),formats.has(name),v=>v?formats.add(name):formats.delete(name),'format-'+name));
    const ack={value:false};
    const ackLabel=checkbox('He revisado los avisos del plan y acepto incluirlos en la entrega.','I reviewed the plan warnings and agree to include them in the delivery.',false,v=>ack.value=v,'audience-ack');
    const exportButton=button('Generar y descargar ZIP','Generate and download ZIP',async()=>{
      if(!preview||preview.options!==JSON.stringify(options())||preview.etag!==projectStore.etag||projectStore.dirty)throw Error(w('Vuelve a comprobar el plan de esta revisión.','Check the plan again for this revision.'));
      if(!formats.size)throw Error(w('Elige al menos un formato.','Select at least one format.'));
      resultStatus.textContent=w('Generando los formatos desde la copia revisada…','Generating formats from the reviewed snapshot…');
      await downloadResponse(await request('/audiences/export',{...options(),formats:[...formats],label:form.title||w('Entrega por destinatario','Audience delivery'),acknowledge_warnings:ack.value}),'audience-report.zip');
      resultStatus.textContent=w('Paquete descargado. Revisa los archivos antes de compartir.','Package downloaded. Review the files before sharing.');
    },'export-audience',true); exportButton.disabled=true;
    const previewButton=button('Comprobar qué se incluirá','Check what will be included',async()=>{
      const sent=options(), snapshot=await saved(), response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/audiences/preview',{method:'POST',headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(sent)})), data=await response.json();
      if(!results.isConnected||S.slug!==snapshot.slug||projectStore.etag!==snapshot.etag)return;
      for(const section of data.available_sections||[])if(!shownSections.has(section.key)){shownSections.add(section.key);const enabled=!sectionsChanged&&(data.plan?.section_keys||[]).includes(section.key);if(enabled)selectedSections.add(section.key);sectionBox.append(checkbox(section.title,section.title,selectedSections.has(section.key),checked=>{sectionsChanged=true;settings.sectionsChanged=true;if(checked)selectedSections.add(section.key);else selectedSections.delete(section.key);},section.key));}
      results.replaceChildren(h('h2',{},w('Plan de publicación','Publication plan')),resultStatus,h('p',{class:'insights-hash'},w('Revisión: ','Revision: ')+data.revision));
      for(const [key,label] of [['included',w('Incluido','Included')],['excluded',w('Excluido realmente','Actually excluded')]])results.append(h('details',{open:key==='included'?'':null},h('summary',{},label+' · '+(data.plan?.[key]||[]).length),h('ul',{},...(data.plan?.[key]||[]).map(text=>h('li',{},planLabels[text]?w(...planLabels[text]):String(text).replaceAll('_',' '))))));
      results.append(h('p',{},(data.plan?.finding_count||0)+' '+((data.plan?.finding_count||0)===1?w('hallazgo; originales privados excluidos','finding; private originals excluded'):w('hallazgos; originales privados excluidos','findings; private originals excluded'))));
      if(data.content_text)results.append(h('details',{open:''},h('summary',{},w('Contenido real que saldrá en esta entrega','Actual outgoing delivery content')),h('pre',{class:'insights-context',tabindex:0},data.content_text)));
      for(const issue of data.issues||[])results.append(h('p',{class:issue.level==='error'?'wf-error':'wf-warning'},issue.message));
      const errors=(data.issues||[]).some(i=>i.level==='error');preview={options:JSON.stringify(sent),etag:snapshot.etag};
      resultStatus.textContent=errors?w('Corrige los errores del plan.','Fix the plan errors.'):w('Plan listo para tu revisión.','Plan ready for your review.');
      results.append(ackLabel,formatBox,exportButton);exportButton.disabled=errors;
    },'preview-audience',true);
    contents.append(selection,sectionBox,safeBox,publicBox,previewButton);
    editor.addEventListener('input',event=>{if(event.target!==search)invalidate();});editor.addEventListener('change',invalidate); results.append(resultStatus);box.append(editor,results);paintProfile();
  }
  async function visual(box, slug) {
    box.append(notice('Revisa las páginas del PDF real, ligado a su SHA-256. Es una revisión visual manual, no una verificación técnica. Las descargas de cola duran una hora; las vistas temporales de PDF y sus registros duran 30 minutos.', 'Review actual PDF pages, tied to their SHA-256. This is manual visual review, not technical verification. Queue downloads last one hour; temporary PDF views and their records expire after 30 minutes.'));
    const capability=await api.get('/api/visual/capabilities');if(!box.isConnected||S.slug!==slug)return;if(!capability.available){box.append(card(h('h2',{},w('Preparar vistas reales de PDF','Prepare actual PDF previews')),notice('Instala el complemento local de vistas previas para abrir las páginas reales del PDF. Los demás módulos y la exportación siguen disponibles.','Install the local preview extra to open actual PDF pages. Other modules and exports remain available.'),h('code',{},capability.install)));return;}
    const output=card(h('h2',{},w('Documento que revisarás','Document to review'))),pages=h('div',{});box.append(output,pages);
    const choice={id:''},selectJob=h('select',{'aria-label':w('PDF o paquete de esta sesión','PDF or package from this session'),'data-insights-field':'visual-job'},h('option',{value:''},w('Consulta resultados de la sesión','Query session results')));
    selectJob.addEventListener('change',()=>choice.id=selectJob.value);
    let run=0;
    async function populateJobs(){const rows=await api.get('/api/jobs');if(!selectJob.isConnected||S.slug!==slug)return;
      const jobs=rows.filter(job=>job.stage==='done'&&(/\.pdf$|\.zip$/i.test(job.filename||'')||job.formats?.includes('pdf')));selectJob.replaceChildren(h('option',{value:''},w('Elige una exportación de la sesión','Choose a session export')),...jobs.map(job=>h('option',{value:job.id},job.label+' · '+job.revision.slice(0,12))));
      choice.id='';if(!jobs.length)toast(w('Todavía no hay exportaciones PDF. Usa Entrega o sube un PDF generado.','No PDF exports yet. Use Deliver or upload a generated PDF.'));
    }
    output.append(h('label',{class:'insights-field'},w('Exportación final de la sesión (identifica el proyecto por su etiqueta)','Final session export (identify the project by its label)'),selectJob),actions(button('Actualizar resultados','Refresh results',populateJobs,'visual-refresh'),button('Abrir páginas reales','Open actual pages',async()=>{
      if(!choice.id)throw Error(w('Selecciona una exportación con PDF.','Select an export containing PDF.'));
      const token=++run,jobId=choice.id;pages.replaceChildren(h('p',{role:'status'},w('Rasterizando el PDF generado…','Rasterizing the generated PDF…')));
      const data=await api.get('/api/jobs/'+encodeURIComponent(jobId)+'/visual');if(token!==run||!pages.isConnected||S.slug!==slug)return;
      display(data,'/api/jobs/'+encodeURIComponent(jobId)+'/visual',false);
    },'visual-generate',true),button('Abrir entrega','Open delivery',()=>{select('studio','deliver');reveal($('#editor'));},'open-delivery')));
    const upload=h('input',{type:'file',accept:'application/pdf,.pdf','aria-label':w('Archivo PDF para revisar','PDF file to review'),'data-insights-field':'visual-file'});
    output.append(h('details',{},h('summary',{},w('Revisar PDF descargado de destinatario','Review downloaded audience PDF')),notice('Elige el PDF extraído de tu ZIP o un PDF existente. El hash identifica el archivo; asociarlo a la revisión activa no demuestra que haya sido generado desde ella. No se incorpora al informe ni al respaldo del proyecto.', 'Choose the PDF extracted from your ZIP or an existing PDF. The hash identifies the file; linking it to the active revision does not prove it was generated from that revision. It is not included in the report or project backup.'),h('label',{class:'insights-field'},w('PDF real (máximo 16 MiB)','Actual PDF (maximum 16 MiB)'),upload),button('Subir y revisar este PDF','Upload and review this PDF',async()=>{
      const file=upload.files?.[0];if(!file)throw Error(w('Elige un archivo PDF.','Choose a PDF file.'));
      if(file.size>16*1024*1024)throw Error(w('El PDF supera 16 MiB.','The PDF exceeds 16 MiB.'));
      const token=++run;busyProject(true);
      try{const snapshot=await saved(),body=new FormData();body.append('file',file,file.name);
        const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/visual',{method:'POST',headers:{'If-Match':snapshot.etag},body})),data=await response.json();
        if(token!==run||!pages.isConnected||S.slug!==slug)return;upload.value='';display(data,'/api/visual/'+encodeURIComponent(data.id),true);
      }finally{busyProject(false);}
    },'visual-upload')));
    function display(data,base,uploaded){
      pages.replaceChildren();if(data.available===false){pages.append(h('p',{role:'status'},data.message||w('Instala el extra de vistas previas para rasterizar PDF reales.','Install the preview extra to rasterize actual PDFs.')));return;}
      pages.append(h('p',{class:'insights-hash'},'SHA-256: '+data.pdf_sha256),h('p',{},w('Revisión asociada: ','Linked revision: ')+data.revision),h('p',{},w('Archivo: ','File: ')+(data.filename||'')));
      const frame=h('div',{class:'insights-pdf-preview'}),nav=actions(),position=h('span',{role:'status'});let index=0;
      const previous=button('Página anterior','Previous page',()=>{index--;paintPage();},'visual-previous'),next=button('Página siguiente','Next page',()=>{index++;paintPage();},'visual-next');nav.append(previous,position,next);pages.append(nav,frame);
      function paintPage(){const page=data.pages[index];frame.replaceChildren(h('img',{src:page.image_url||base+'/page/'+page.number,alt:w('Página real ','Actual page ')+page.number,width:page.width,height:page.height,loading:'eager'}));position.textContent=w('Página ','Page ')+(index+1)+' / '+data.pages.length;previous.disabled=index===0;next.disabled=index===data.pages.length-1;}
      if(!data.pages?.length){pages.append(notice('El resultado no contiene un PDF disponible.','The result does not contain an available PDF.'));return;}paintPage();
      const form={author:'',decision:'issues',note:''},items=[],item={number:'1',issue:'table_cut',note:''},observations=h('div',{});
      function paintItems(){observations.replaceChildren(...items.map((row,i)=>h('p',{},w('Página ','Page ')+row.number+': '+row.note+' ',button('Retirar','Remove',()=>{items.splice(i,1);paintItems();},'remove-visual-issue'))));}
      pages.append(card(h('h3',{},w('Observación de una página','Page observation')),choose('Página','Page',item,'number',data.pages.map(p=>[String(p.number),String(p.number)])),choose('Problema observado','Observed problem',item,'issue',[['table_cut','Tabla cortada','Cut table'],['orphan_title','Título aislado','Orphan title'],['unreadable_image','Captura ilegible','Unreadable image'],['other','Otro','Other']]),field('Descripción del problema','Problem description',item,'note',{rows:2}),button('Añadir observación','Add observation',()=>{if(!item.note.trim())throw Error(w('Describe lo observado.','Describe what you observed.'));items.push({number:Number(item.number),issue:item.issue,note:item.note});paintItems();},'add-visual-issue'),observations),
        card(h('h3',{},w('Registrar revisión visual','Record visual review')),field('Autor (declaración local)','Author (local declaration)',form,'author'),choose('Decisión','Decision',form,'decision',[['issues','Encontré problemas','I found issues'],['accepted','Aceptación visual manual','Manual visual acceptance']]),field('Nota general','General note',form,'note',{rows:2}),button('Guardar registro de este PDF','Save record for this PDF',async()=>{
          const response=await requireOk(await appFetch(base+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:data.revision,pdf_sha256:data.pdf_sha256,...form,pages:items})})),record=await response.json();
          toast(w('Revisión visual registrada para este PDF.','Visual review recorded for this PDF.'));pages.append(h('details',{},h('summary',{},w('Registro guardado','Saved record')),h('pre',{class:'insights-context'},JSON.stringify(record,null,2))),button('Descargar registro JSON','Download review JSON',async()=>{
            const blob=new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),object=URL.createObjectURL(blob),a=h('a',{href:object,download:'visual-review-'+data.pdf_sha256.slice(0,12)+'.json'});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(object),30000);
          },'download-visual-review'));
        },'record-visual-review',true)));
      if(data.review)pages.append(h('details',{},h('summary',{},w('Revisión anterior de este PDF','Previous review of this PDF')),h('pre',{class:'insights-context'},JSON.stringify(data.review,null,2))));
      if(uploaded)pages.append(button('Eliminar este PDF temporal y su registro','Delete this temporary PDF and its record',async()=>{await requireOk(await appFetch(base,{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'}));pages.replaceChildren(h('p',{role:'status'},w('PDF temporal eliminado.','Temporary PDF deleted.')));},'delete-visual-file'));
    }
    await populateJobs();
  }
  async function editorial(box, slug) {
    box.append(notice('Las reglas señalan redacciones que merecen revisión. No verifican vulnerabilidades, pruebas ni resultados. Ninguna sugerencia modifica el informe automáticamente.', 'Rules flag wording that deserves review. They do not verify vulnerabilities, tests or results. No suggestion changes the report automatically.'));
    const rules=await api.get('/api/projects/'+encodeURIComponent(slug)+'/insights/editorial?lang='+encodeURIComponent(S.uiLang));if(!box.isConnected||S.slug!==slug)return;
    const transparent=card(h('h2',{},w('Reglas transparentes','Transparent rules')));
    for(const rule of rules.rules||[])transparent.append(h('details',{},h('summary',{},rule.name||rule.rule||rule.id),h('p',{},rule[S.uiLang==='en'?'en':'es']||rule.description||rule.message||JSON.stringify(rule))));
    const issues=card(h('h2',{},w('Observaciones editoriales','Editorial observations')));
    paged(issues,rules.issues||[],issue=>h('article',{class:'insights-editorial-issue'},h('h3',{},titleFor(issue.finding_uid)),h('p',{},issue.message),h('p',{},issue.help),h('code',{},issue.path),issue.finding_uid?button('Abrir el texto original','Open original text',()=>{const index=S.data.findings.findIndex(f=>f.uid===issue.finding_uid);if(index<0)throw Error(w('Hallazgo ausente.','Finding missing.'));select('finding',index);reveal($('#editor'));},'open-editorial-finding'):null));
    if(!rules.issues?.length)issues.append(notice('No se encontraron coincidencias de estas reglas. Esto no sustituye una revisión humana.', 'No matches were found for these rules. This does not replace human review.'));
    box.append(transparent,issues);
    if(typeof localAssistant==='function')await localAssistant(box,slug);
  }
  async function localAssistant(box, slug) {
    const assistant=card(h('h2',{},w('Asistencia opcional con IA local','Optional local AI assistance')));
    assistant.append(notice('Selecciona un único campo y revisa exactamente qué texto enviarás a un modelo local. La herramienta solo usa loopback; comprueba también que tu servidor Ollama tenga la nube desactivada. No podemos verificar el aislamiento de red de otro proceso.', 'Select one field and review exactly which text will be sent to a local model. The tool only uses loopback; also ensure your Ollama server has cloud features disabled. We cannot verify another process’s network isolation.'));
    const capability=await api.get('/api/assistant/capabilities');if(!assistant.isConnected&&box.isConnected)box.append(assistant);if(!box.isConnected||S.slug!==slug)return;
    if(!capability.available){assistant.append(h('p',{},capability.message||w('No hay asistencia local disponible. Las reglas editoriales siguen operativas.','Local assistance is not available. Editorial rules remain usable.')));return;}
    async function discardProposal(){const id=assistantProposals.get(slug);if(!id)return;const response=await appFetch('/api/projects/'+encodeURIComponent(slug)+'/assistant/discard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proposal_id:id})});if(response.status!==404)await requireOk(response);assistantProposals.delete(slug);}
    if(assistantProposals.has(slug))assistant.append(button('Descartar propuesta pendiente anterior','Discard previous pending proposal',async()=>{await discardProposal();toast(w('Propuesta temporal descartada.','Temporary proposal discarded.'));},'assistant-discard-pending'));
    assistant.append(h('p',{},w('Servidor fijo: ','Fixed server: ')+capability.endpoint));
    const form={finding_uid:'',field:'description_md',model:'',task:'improve_clarity',confirmed_local:false},source=h('pre',{class:'insights-context',tabindex:0}),proposal=h('div',{}),models=h('select',{'aria-label':w('Modelo local instalado','Installed local model'),'data-insights-field':'model'},h('option',{value:''},w('Consulta modelos instalados','Query installed models')));
    models.addEventListener('change',()=>{form.model=models.value;proposal.replaceChildren();});
    const selected=choose('Hallazgo','Finding',form,'finding_uid',findingChoices());
    const choice=choose('Único campo que se enviará','Only field that will be sent',form,'field',[['description_md','Descripción','Description'],['impact_md','Impacto','Impact'],['remediation_md','Remediación','Remediation']]);
    let original='';
    function updateText(){const finding=S.data.findings.find(f=>f.uid===form.finding_uid);original=finding?.[form.field]||'';source.textContent=original||w('Elige un hallazgo con contenido en este campo.','Choose a finding with content in this field.');proposal.replaceChildren();}
    assistant.append(actions(button('Consultar modelos locales','Query local models',async()=>{
      const response=await requireOk(await appFetch('/api/assistant/models',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})),data=await response.json();
      if(!models.isConnected||S.slug!==slug)return;const rows=data.models||data;
      models.replaceChildren(h('option',{value:''},w('Elige un modelo local','Choose a local model')),...rows.map(item=>h('option',{value:typeof item==='string'?item:item.name||item.model},typeof item==='string'?item:item.name||item.model)));
      if(!rows.length)toast(w('Instala un modelo GGUF local en Ollama y vuelve a consultar.','Install a local GGUF model in Ollama, then query again.'));
    },'assistant-models')),h('label',{class:'insights-field'},w('Modelo local instalado','Installed local model'),models),selected,choice,
      choose('Tarea editorial','Editorial task',form,'task',[['improve_clarity','Mejorar claridad sin añadir hechos','Improve clarity without adding facts'],['review_limits','Revisar límites de la conclusión','Review conclusion limits']]),h('h3',{},w('Texto exacto seleccionado (solo lectura)','Exact selected text (read only)')),source,
      checkbox('Autorizo enviar solamente este campo al modelo local configurado.','I authorize sending only this field to the configured local model.',false,v=>form.confirmed_local=v,'assistant-confirm'));
    selected.addEventListener('insights-change',updateText);choice.addEventListener('insights-change',updateText);updateText();
    assistant.append(button('Obtener propuesta editorial','Get editorial proposal',async()=>{
      if(!form.finding_uid||!original.trim())throw Error(w('Selecciona un campo con contenido.','Select a field with content.'));
      if(!form.confirmed_local||!form.model)throw Error(w('Elige un modelo local y confirma el campo que se enviará.','Choose a local model and confirm the field to send.'));
      await discardProposal();
      const snapshot=await saved(),selection={finding_uid:form.finding_uid,fields:[form.field],model:form.model,confirmed_local:true,task:form.task};
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/assistant',{method:'POST',headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(selection)})),data=await response.json();
      if(!proposal.isConnected||S.slug!==snapshot.slug)return;
      assistantProposals.set(slug,data.proposal_id);
      proposal.replaceChildren(h('h3',{},w('Comparación antes de aceptar','Comparison before acceptance')));
      for(const warning of data.warnings||[])proposal.append(h('p',{class:'wf-warning'},typeof warning==='string'?warning:warning.message));
      const accepted=new Set();
      for(const item of data.proposals||[]){const compare=h('div',{class:'insights-split'},card(h('h4',{},w('Original','Original')),h('pre',{class:'insights-context'},item.before)),card(h('h4',{},w('Propuesta editorial','Editorial proposal')),h('pre',{class:'insights-context'},item.after)));
        proposal.append(h('h4',{},item.field),compare,checkbox('Selecciono esta propuesta para aplicar.','I select this proposal to apply.',false,v=>v?accepted.add(item.field):accepted.delete(item.field),'accept-'+item.field));}
      proposal.append(notice('Comprueba hechos, nombres, comandos y límites. Puedes ignorar la propuesta o editar el texto desde el hallazgo. Aceptar no verifica ninguna afirmación.', 'Check facts, names, commands and limitations. You can discard the proposal or edit text in the finding editor. Acceptance does not verify any claim.'),
        button('Aplicar únicamente las propuestas seleccionadas','Apply only selected proposals',async()=>{
          if(!accepted.size)throw Error(w('Selecciona explícitamente una propuesta.','Explicitly select a proposal.'));
          if(projectStore.etag!==snapshot.etag||projectStore.dirty)throw Error(w('La revisión cambió. Obtén una nueva propuesta.','The revision changed. Obtain a new proposal.'));
          const applied=await request('/assistant/apply',{proposal_id:data.proposal_id,fields:[...accepted]});await applied.json();assistantProposals.delete(slug);await projectStore.load(snapshot.slug);S.data=projectStore.data;renderSidebar();renderMain();reveal($('#insightsTitle'));toast(w('Propuestas seleccionadas guardadas.','Selected proposals saved.'));
        },'assistant-apply',true),button('Descartar esta propuesta','Discard this proposal',async()=>{await discardProposal();proposal.replaceChildren(h('p',{role:'status'},w('Propuesta descartada; el informe sigue intacto.','Proposal discarded; the report remains unchanged.')));},'assistant-discard'));
    },'assistant-propose',true),proposal);
  }
  async function renderFinding(box, uid) {
    const slug=S.slug, lang=S.uiLang, etag=projectStore.etag;
    delete box.dataset.findingDecisionsReady;
    const status=h('p',{class:'insights-status',role:'status'},w('Leyendo las decisiones guardadas de este hallazgo…','Reading the saved decisions for this finding…'));
    box.append(status);
    const active=()=>box.isConnected && S.slug===slug && S.uiLang===lang && WorkbenchUI.renderedFindingUid()===uid;
    try {
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/insights?lang='+encodeURIComponent(lang))), responseTag=response.headers.get('ETag');
      const data=await response.json();
      if(!active())return;
      if(!etag||responseTag!==etag||projectStore.etag!==etag)throw Error(w('La revisión guardada cambió o no coincide con el editor. Conserva tu borrador y recarga el proyecto antes de consultar las decisiones.','The saved revision changed or differs from the editor. Keep your draft and reload the project before reading decisions.'));
      status.remove(); state=data; currentSlug=slug;
      box.dataset.findingDecisionsReady='true';
      box.append(notice('Este panel lee las decisiones guardadas. Abrirlo o cambiar de pestaña no guarda el informe ni registra decisiones. Los formularios se conservan por hallazgo en esta sesión hasta usar su botón de guardar.','This panel reads saved decisions. Opening it or switching tabs does not save the report or record decisions. Form drafts stay with each finding in this session until you use their save button.'));
      if(projectStore.dirty)box.append(notice('El editor tiene cambios sin guardar. Las decisiones mostradas corresponden a la revisión guardada; guardar una decisión guarda primero el borrador del informe.','The editor has unsaved changes. The displayed decisions belong to the saved revision; saving a decision first saves the report draft.'));
      box.append(h('details',{},h('summary',{},w('Identidad de la revisión leída','Identity of the reviewed revision')),h('p',{class:'insights-hash'},'SHA-256: '+data.digest)));
      if(!(data.map?.findings||[]).some(item=>item.uid===uid)){
        box.append(notice('Este hallazgo no consta en la revisión guardada. Guarda el informe y vuelve a consultar para documentar decisiones.','This finding is absent from the saved revision. Save the report and read again to document decisions.'),button('Volver a consultar','Read again',()=>{box.replaceChildren();return renderFinding(box,uid);},'finding-decisions-refresh'));
        return;
      }
      const context={uid}, selectedClaims=(data.claims||[]).filter(item=>item.finding_uid===uid), selectedRisks=(data.risks||[]).filter(item=>item.finding_uid===uid);
      const claimEditor=card(h('h3',{},w('Añadir afirmación de este hallazgo','Add a claim for this finding')),claimForm({finding_uid:uid,statement:'',kind:'observed',demonstrates:'',does_not_demonstrate:'',evidence_uids:[]},context));
      const claimsList=card(h('h3',{},w('Afirmaciones registradas','Recorded claims')));
      if(!selectedClaims.length)claimsList.append(notice('Sin afirmaciones registradas para este hallazgo. No se generan automáticamente.','No claims are recorded for this finding. None are generated automatically.'));
      paged(claimsList,selectedClaims,item=>claimRow(item,claimEditor,context));
      const riskEditor=card(h('h3',{},w('Documentar prioridad de este hallazgo','Document priority for this finding')),riskForm({finding_uid:uid,service:'',objective:'',consequence:'',tolerance:'',source:'',assumptions:'',priority:'unassigned',rationale:'',owner:''},context));
      const risksList=card(h('h3',{},w('Decisiones de negocio registradas','Recorded business decisions')));
      if(!selectedRisks.length)risksList.append(notice('Sin decisiones de negocio registradas para este hallazgo. La prioridad, la tolerancia y la verificación técnica no se deducen de abrir este panel.','No business decisions are recorded for this finding. Priority, tolerance and technical verification are not inferred by opening this panel.'));
      paged(risksList,selectedRisks,item=>riskRow(item,riskEditor,context));
      box.append(notice('Una afirmación distingue observación, inferencia e hipótesis. La prioridad de negocio es una decisión documentada, separada de la severidad técnica y CVSS.','A claim distinguishes observation, inference and hypothesis. Business priority is a documented decision, separate from technical severity and CVSS.'),claimsList,claimEditor,risksList,riskEditor);
    } catch(error) {
      if(!active())return;
      status.remove();box.append(h('p',{role:'alert'},error.message),button('Reintentar','Retry',()=>{box.replaceChildren();return renderFinding(box,uid);},'finding-decisions-retry'));
    }
  }
  function render(el) {
    const tab=names[S.sel.idx]?S.sel.idx:'claims',token=++generation,slug=S.slug;
    const shell=h('section',{class:'insights-shell','data-insights-page':tab,'aria-labelledby':'insightsTitle'});
    shell.append(h('header',{},h('p',{class:'insights-eyebrow'},w('EVIDENCIA · DECISIÓN · ENTREGA','EVIDENCE · DECISION · DELIVERY')),h('h1',{id:'insightsTitle',tabindex:'-1'},w('Evidencia y decisiones','Evidence and decisions')),notice('Conecta evidencia, conclusiones y prioridades. Revisa el contenido y prepara una entrega para cada lector.', 'Connect evidence, conclusions and priorities. Review content and prepare a delivery for each reader.')),h('details',{},h('summary',{},w('Cómo se guardan estas decisiones','How these decisions are saved')),notice('Abrir estas pantallas no cambia el proyecto. Los formularios se conservan en esta pestaña hasta pulsar su botón de guardar; no se incorporan al informe mientras los editas.','Opening these screens does not change the project. Form drafts stay in this tab until you press their save button; editing them does not add them to the report.')));
    const nav=h('nav',{class:'insights-nav','aria-label':w('Herramientas de revisión','Review tools')});
    for(const [key,labels]of Object.entries(names)){const b=h('button',{type:'button','data-insights-tab':key,'aria-current':tab===key?'page':null},w(...labels));b.addEventListener('click',()=>open(key));nav.append(b);}
    const box=h('div',{'data-insights-content':tab}),status=h('p',{class:'insights-status',role:'status'},w('Leyendo la revisión guardada…','Reading the saved revision…'));box.append(status);shell.append(nav,box);el.append(shell);
    if(!slug){status.textContent=w('Abre un proyecto para usar estas herramientas.','Open a project to use these tools.');return;}
    api.get('/api/projects/'+encodeURIComponent(slug)+'/insights?lang='+encodeURIComponent(S.uiLang)).then(async data=>{
      if(token!==generation||S.slug!==slug||!box.isConnected)return;state=data;currentSlug=slug;status.remove();
      if(projectStore.dirty)box.append(notice('Hay cambios en el borrador. Este mapa muestra lo guardado; una acción explícita guarda antes de continuar.', 'There are draft changes. This map shows saved data; an explicit action saves before continuing.'));
      box.append(h('details',{},h('summary',{},w('Identidad de la revisión leída','Identity of the reviewed revision')),h('p',{class:'insights-hash'},'SHA-256: '+data.digest)));
      if(tab==='claims')claims(box);else if(tab==='risk')risk(box);else if(tab==='review')review(box);else if(tab==='audiences')audiences(box);else if(tab==='visual')await visual(box,slug);else await editorial(box,slug);
    }).catch(error=>{if(box.isConnected&&token===generation){status.remove();box.append(h('p',{role:'alert'},error.message),button('Reintentar','Retry',()=>renderMain(),'retry'));}});
  }
  function entry() {
    if(!S.slug)return h('span',{hidden:''});
    return h('section',{class:'insights-entry'},h('div',{},h('h2',{},w('Conecta tu evidencia con la decisión','Connect evidence to the decision')),h('p',{},w('Documenta límites, prioriza con contexto, recibe observaciones y revisa tus entregas.','Document limitations, prioritize with context, receive review comments and inspect your deliverables.'))),button('Evidencia y decisiones','Evidence and decisions',()=>open(),'open-insights'));
  }
  function bind() {
    if($('#insightsBtn'))return;const b=button('Evidencia y decisiones','Evidence and decisions',()=>open(),'open-insights');b.id='insightsBtn';
    const utilities=$('.workspace-utilities')||$('.sidebar'),more=$('#studioMore .studio-more-body'),media=matchMedia('(max-width:760px)');
    function place(){const focused=document.activeElement===b,destination=media.matches&&more?more:utilities;if(b.parentElement!==destination)destination.append(b);if(focused){if(media.matches&&more)$('#studioMore').open=true;else if(document.body.classList.contains('focus-mode')){$('#studioMore summary')?.focus({preventScroll:true});return;}b.focus({preventScroll:true});}}
    place();media.addEventListener?.('change',place);update();
  }
  function update() {
    const active=S.sel.type==='insights',b=$('#insightsBtn');$('.layout')?.classList.toggle('workspace-insights',active);
    if(b){b.textContent=w('Evidencia y decisiones','Evidence and decisions');b.disabled=!S.slug||projectBusyCount>0;b.setAttribute('aria-current',active?'page':'false');b.classList.toggle('active',active);}
    if(active&&$('#workspaceContext'))$('#workspaceContext').textContent=w(...(names[S.sel.idx]||names.claims));
    if(currentSlug!==S.slug)state=null;
  }
  function resetProject(slug){for(const key of drafts.keys())if(key.startsWith(slug+'|'))drafts.delete(key);assistantProposals.delete(slug);if(currentSlug===slug){state=null;currentSlug=null;generation++;}publicationKey=null;publicationRequest=null;}
  return{bind,update,render,renderFinding,entry,open,projectDeleted:resetProject,projectCreated:resetProject};
})();

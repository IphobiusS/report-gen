/* Optional decision workspace. Reading never writes project data; every write is explicit and revision guarded. */
const InsightsUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const names = {
    claims: ['Afirmaciones y evidencia', 'Claims and evidence', "Afirmações e evidências"], risk: ['Decisiones de negocio', 'Business decisions', "Decisões de negócio"],
    review: ['Mesa de revisión', 'Review desk', "Mesa de revisão"], audiences: ['Entregas por destinatario', 'Audience deliveries', "Entregas por público"],
    visual: ['Revisión visual', 'Visual review', "Revisão visual"], editorial: ['Ayuda editorial', 'Editorial assistance', "Assistência editorial"]
  };
  let generation = 0, state = null, currentSlug = null, publicationKey=null,publicationRequest=null;
  const drafts=new Map(),assistantProposals=new Map(),pendingSignatures=new Map();let restoring=null;
  function draft(key,initial){const id=S.slug+'|'+key;if(!drafts.has(id)){Object.defineProperty(initial,'_draftkey',{value:id,enumerable:false});drafts.set(id,initial);if(typeof PendingUI!=='undefined')pendingSignatures.set(id,JSON.stringify(PendingUI.pack(initial)));}return drafts.get(id);}
  function pendingLabel(key,form){const labels=key.startsWith('claim-')?['Afirmación pendiente','Pending claim', "Afirmação pendente"]:key.startsWith('risk-')?['Decisión de negocio pendiente','Pending business decision', "Decisão de negócio pendente"]:key.startsWith('comment-')?['Observación pendiente','Pending comment', "Comentário pendente"]:key.startsWith('resolve-')?['Resolución pendiente','Pending resolution', "Resolução pendente"]:key==='review-new'?['Revisión editorial pendiente','Pending editorial review', "Revisão editorial pendente"]:['Entrega por destinatario pendiente','Pending audience delivery', "Entrega por público pendente"];const finding=(S.data.findings||[]).find(row=>row.uid===form.finding_uid);return w(...labels)+(finding?' · '+finding.id+' · '+finding.title:'');}
  function protectForms(){
    if(typeof PendingUI==='undefined'||!S.slug)return;
    for(const [id,form]of drafts){if(!id.startsWith(S.slug+'|'))continue;const signature=JSON.stringify(PendingUI.pack(form));if(pendingSignatures.get(id)===signature)continue;pendingSignatures.set(id,signature);
      const key=id.slice(S.slug.length+1),handle=PendingUI.track('insights:'+key,pendingLabel(key,form),()=>({data:form}));PendingUI.changed(handle);showPending(handle);
    }
  }
  function showPending(handle){
    const target=$('[data-insights-content]')||$('[data-finding-panel="decisions"]')||$('#editor');if(!target||target.querySelector('[data-pending-status="'+handle.key+'"]'))return;
    const block=h('div',{class:'card'},h('strong',{},handle.label),PendingUI.status(handle),button('Descartar formulario pendiente','Discard pending form', "Descartar formulário pendente",async()=>{if(!confirm(w('¿Descartar este formulario? Los datos guardados se conservan.','Discard this form? Saved data is retained.', "Descartar este formulário? Os dados salvos serão mantidos.")))return;if(await PendingUI.clear(handle)){drafts.delete(handle.slug+'|'+handle.key.slice(9));pendingSignatures.delete(handle.slug+'|'+handle.key.slice(9));renderMain();}},'discard-pending'));target.append(block);
  }
  function restorePending(row){
    if(row.slug!==S.slug)throw Error(w('Abre el proyecto original.','Open the original project.', "Abra o projeto original."));
    const key=row.key.slice(9),value=PendingUI.unpack(row.data);if(!/^(claim-|risk-|comment-new$|resolve-|review-new$|audience-new$)/.test(key))throw Error(w('Formulario no compatible.','Unsupported form.', "Formulário não compatível."));
    // A recovered configuration is never a fresh consent to publish or send data.
    if(value.form){value.form.review_confirmed=false;value.form.publish_consent=false;}
    drafts.delete(S.slug+'|'+key);const form=draft(key,value),handle=PendingUI.track(row.key,row.label,()=>({data:form}),{origin:row});pendingSignatures.set(S.slug+'|'+key,JSON.stringify(PendingUI.pack(form)));PendingUI.changed(handle);
    restoring={slug:S.slug,key,form};open(key.startsWith('claim-')?'claims':key.startsWith('risk-')?'risk':key==='audience-new'?'audiences':'review');
  }
  document.addEventListener('input',event=>{if(event.target.matches('[data-insights-field]'))protectForms();});
  document.addEventListener('change',event=>{if(event.target.matches('[data-insights-field],[data-insights-check]'))protectForms();});
  const clone = value => JSON.parse(JSON.stringify(value));
  function notice(es, en, pt) { return h('p', {class: 'insights-note'}, w(es, en, pt)); }
  function actions(...nodes) { return h('div', {class: 'insights-actions'}, ...nodes); }
  function card(...nodes) { return h('section', {class: 'insights-card'}, ...nodes); }
  function button(es, en, pt, run, id, primary = false) {
    const b = h('button', {type: 'button', class: 'btn' + (primary ? ' primary' : ''), 'data-insights-action': id}, w(es, en, pt));
    if(id&&(/-(previous|next)$/.test(id))){b.addEventListener('click',()=>{if(projectBusyCount>0)return;try{run(b);}catch(error){toast(error.message,'err');}});return b;}
    b.addEventListener('click', async () => {
      if (projectBusyCount > 0) return;
      b.disabled = true;
      try { await run(b); } catch (error) { toast(error.message, 'err'); }
      finally { if (b.isConnected) b.disabled = projectBusyCount > 0; }
    });
    return b;
  }
  function field(es, en, pt, object, key, options = {}) {
    const tag = options.rows ? 'textarea' : 'input';
    const input = h(tag, {type: options.rows ? null : 'text', rows: options.rows, maxlength: options.maxlength || 4000, 'data-insights-field': key});
    input.value = object[key] ?? '';
    input.addEventListener('input', () => { object[key] = input.value; });
    return h('label', {class: 'insights-field'}, h('span', {}, w(es, en, pt)), input);
  }
  function choose(es, en, pt, object, key, choices) {
    const input = h('select', {'data-insights-field': key}, choices.map(([value, a, b, c]) => h('option', {value}, b === undefined ? a : w(a, b, c))));
    if(key==='finding_uid'&&object[key]&&!choices.some(row=>row[0]===object[key]))object[key]='';
    input.value = object[key] ?? choices[0]?.[0] ?? '';
    input.addEventListener('change', () => { object[key] = input.value; input.dispatchEvent(new Event('insights-change', {bubbles: true})); });
    return h('label', {class: 'insights-field'}, h('span', {}, w(es, en, pt)), input);
  }
  function checkbox(es, en, pt, checked, run, key) {
    const input = h('input', {type: 'checkbox', checked: checked ? '' : null, 'data-insights-check': key});
    input.addEventListener('change', () => run(input.checked));
    return h('label', {class: 'insights-check'}, input, w(es, en, pt));
  }
  function findingChoices(optional = false) {
    return (optional ? [['', w('Todo el informe', 'Whole report', "Relatório completo")]] : [['', w('Elige un hallazgo', 'Choose a finding', "Escolha um achado")]])
      .concat((state?.map?.findings || []).map(f => [f.uid, (f.id || '') + ' · ' + (f.title || w('Sin título', 'Untitled', "Sem título"))]));
  }
  function titleFor(uid) { const f = state?.map?.findings?.find(row => row.uid === uid); return f ? (f.id || '') + ' · ' + f.title : uid || w('Informe', 'Report', "Relatório"); }
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
    if (!S.slug) throw Error(w('Abre un proyecto primero.', 'Open a project first.', "Abra um projeto primeiro."));
    const slug = S.slug;
    if (!await doSave()) throw Error(w('Guarda el proyecto antes de continuar.', 'Save the project before continuing.', "Salve o projeto antes de continuar."));
    if (S.slug !== slug) throw Error(w('El proyecto cambió. Abre de nuevo esta pantalla.', 'The project changed. Reopen this screen.', "O projeto mudou. Reabra esta tela."));
    return {slug, etag: projectStore.etag};
  }
  async function request(path, body, method = 'POST') {
    busyProject(true);
    try {
      const snapshot = await saved();
      const response = await requireOk(await appFetch('/api/projects/' + encodeURIComponent(snapshot.slug) + path, {
        method, headers: {'Content-Type': 'application/json', 'If-Match': snapshot.etag}, body: JSON.stringify(body)
      }));
      if (S.slug !== snapshot.slug) throw Error(w('La operación pertenece al proyecto anterior.', 'The operation belongs to the previous project.', "A operação pertence ao projeto anterior."));
      return response;
    } finally { busyProject(false); }
  }
  async function mutate(body,form,context = null) {
    const slug = S.slug, pending=typeof PendingUI!=='undefined'&&form?PendingUI.active.get(slug+'|insights:'+form._draftkey?.slice(slug.length+1)):null, pendingRevision=pending?.revision;let locked=true,cleanupWarning=null;
    busyProject(true);
    try {
      const response = await request('/insights', body);
      await response.json();WorkbenchUI.dirty();
      if(form?._draftkey){const cleanup=pending?await PendingUI.committed(pending,pendingRevision):{finished:true};cleanupWarning=cleanup.warning;if(cleanup.finished)drafts.delete(form._draftkey);}
      if (S.slug !== slug) return;
      await projectStore.load(slug);
      if(S.slug!==slug)return;
      const selectedUid=context&&S.sel.type==='finding'?WorkbenchUI.renderedFindingUid():null;
      S.data = projectStore.data;
      WorkbenchUI.dirty();
      if (selectedUid && S.sel.type === 'finding') {
        const index = S.data.findings.findIndex(item => item.uid === selectedUid);
        S.sel = index < 0 ? {type:'report',idx:-1} : {type:'finding',idx:index};
      }
      renderSidebar(); renderMain();
      if(locked){busyProject(false);locked=false;}
      if(!context)reveal($('#insightsTitle'));
      else if(selectedUid===context.uid)reveal($('#editor [data-finding-tab="decisions"]') || $('#editor .finding-context-title strong'));
      toast(cleanupWarning?w('Decisión guardada. No se pudo eliminar su copia local; revísala en Datos privados guardados.','Decision saved. Its local copy could not be deleted; review Stored private data.', "Decisão salva. Não foi possível excluir a cópia local; revise os Dados privados armazenados."):w('Decisión guardada en esta revisión.', 'Decision saved in this revision.', "Decisão salva nesta revisão."));
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
    const set = new Set(object[key] || []), group = h('fieldset', {class: 'insights-evidence-select'}, h('legend', {}, w('Evidencia que sostiene esta afirmación', 'Evidence supporting this claim', "Evidência que sustenta esta afirmação")));
    for (const e of state?.map?.evidence || []) group.append(checkbox(e.title || e.uid, e.title || e.uid, e.title || e.uid, set.has(e.uid), checked => {
      if (checked) set.add(e.uid); else set.delete(e.uid); object[key] = [...set];
    }, e.uid));
    if (!state?.map?.evidence?.length) group.append(notice('Todavía no hay evidencias registradas. Puedes documentar una hipótesis sin presentarla como observación.', 'No evidence is registered yet. You can document a hypothesis without presenting it as an observation.', "Ainda não há evidências cadastradas. Você pode documentar uma hipótese sem apresentá-la como observação."));
    return group;
  }
  function evidenceContext(uid) {
    const evidence = state?.map?.evidence?.find(e => e.uid === uid);
    if (!evidence) return h('p', {}, w('Referencia de evidencia ausente: ', 'Missing evidence reference: ', "Referência de evidência ausente: ") + uid);
    const wrapper = h('details', {class: 'insights-evidence'}, h('summary', {}, evidence.title || uid));
    wrapper.addEventListener('toggle', async () => {
      if (!wrapper.open || wrapper.dataset.loaded || !S.slug) return;
      wrapper.dataset.loaded = 'true';
      const slug = S.slug, revision = projectStore.etag;
      const content = h('div', {class: 'insights-evidence-content'}, h('p', {}, evidence.caption || ''), notice('Copia de publicación con el procesamiento y las censuras registrados; no es el archivo original privado.', 'Publication derivative with recorded processing and redactions; this is not the private original.', "Cópia para publicação com o processamento e as ocultações registrados; este não é o original privado."));
      wrapper.append(content);
      try {
        const key=slug+'|'+revision;if(publicationKey!==key||!publicationRequest){publicationKey=key;publicationRequest=api.get('/api/projects/'+encodeURIComponent(slug)+'/publication').catch(error=>{publicationRequest=null;throw error;});}
        const report=await publicationRequest;
        if (S.slug !== slug || projectStore.etag !== revision || !content.isConnected) return;
        const name = evidence.src?.replace(/^images\//, '');
        const image = (report.images || []).find(item => item.name === name || item.name === evidence.src);
        if (image) content.append(h('img', {src: '/api/projects/' + encodeURIComponent(slug) + '/publication/image?name=' + encodeURIComponent(image.name) + '&revision=' + encodeURIComponent(report.revision), alt: evidence.caption || evidence.title || w('Evidencia publicada', 'Published evidence', "Evidência publicada"), loading: 'lazy'}));
        else content.append(notice('La copia publicada no contiene esta imagen. Revisa la evidencia y el inspector.', 'The publication copy does not contain this image. Review the evidence and publication inspector.', "A cópia publicada não contém esta imagem. Revise a evidência e o inspetor de publicação."));
      } catch (error) { if (content.isConnected) content.append(h('p', {role: 'alert'}, error.message)); }
    });
    return wrapper;
  }
  function paged(host, rows, build, size=30) {
    const listing=h('div',{}),nav=actions(),count=h('span',{role:'status'});let page=0;
    const previous=button('Anterior','Previous', "Anterior",()=>{page--;paint();reveal(listing.querySelector('summary,button,h3')||count);},'collection-previous'),next=button('Siguiente','Next', "Próximo",()=>{page++;paint();reveal(listing.querySelector('summary,button,h3')||count);},'collection-next');
    nav.append(previous,count,next);host.append(listing);if(rows.length>size)host.append(nav);
    function paint(){listing.replaceChildren(...rows.slice(page*size,page*size+size).map(build));count.textContent=(rows.length?page*size+1:0)+'–'+Math.min(rows.length,page*size+size)+' / '+rows.length;previous.disabled=page===0;next.disabled=(page+1)*size>=rows.length;}
    paint();
  }
  function claims(box) {
    box.append(notice('Distingue lo observado de una inferencia o hipótesis. Vincula el contenido exacto que sostiene tu conclusión y registra sus límites.', 'Distinguish observations from inferences or hypotheses. Link the specific evidence supporting the conclusion and record its limits.', "Distinga observações de inferências ou hipóteses. Vincule a evidência específica que sustenta a conclusão e registre seus limites."));
    const map = card(h('h2', {}, w('Mapa de trabajo', 'Work map', "Mapa do trabalho"))), grid = h('div', {class: 'insights-map'});
    const source = state.map?.findings || []; let page = 0;
    const listing = h('div', {}), controls = actions(), counter = h('span', {role: 'status'});
    const previous = button('Anterior', 'Previous', "Anterior", () => { page--; draw(); }, 'map-previous');
    const next = button('Siguiente', 'Next', "Próximo", () => { page++; draw(); }, 'map-next');
    function draw() {
      listing.replaceChildren(); grid.replaceChildren();
      for (const f of source.slice(page * 20, page * 20 + 20)) {
        const row = card(h('h3', {}, f.id + ' · ' + f.title), button('Abrir hallazgo', 'Open finding', "Abrir achado", () => {
          const index = S.data.findings.findIndex(item => item.uid === f.uid); if (index < 0) throw Error(w('Hallazgo no disponible.', 'Finding unavailable.', "Achado indisponível."));
          select('finding', index); reveal($('#editor'));
        }, 'open-finding'));
        const assets = (f.asset_uids || []).map(uid => state.map.assets.find(a => a.uid === uid)?.name || uid);
        row.append(h('p', {}, w('Activos: ', 'Assets: ', "Ativos: ") + (assets.join(', ') || w('Sin vincular', 'Not linked', "Sem vínculo"))), h('p', {}, w('Evidencias: ', 'Evidence: ', "Evidência: ") + (f.evidence_uids || []).length));
        for (const uid of f.evidence_uids || []) row.append(evidenceContext(uid));
        for (const c of state.claims.filter(c => c.finding_uid === f.uid)) row.append(h('p', {class: 'insights-map-claim'}, w(...({observed:['Observación','Observation', "Observação"],inference:['Inferencia','Inference', "Inferência"],hypothesis:['Hipótesis','Hypothesis', "Hipótese"]}[c.kind]||[c.kind,c.kind,c.kind])) + ': ' + c.statement));
        if (f.retests?.length) row.append(h('p', {}, w('Retests registrados: ', 'Recorded retests: ', "Retestes registrados: ") + f.retests.map(r => r.result + ' (' + r.tested_on + ')').join(', ')));
        grid.append(row);
      }
      counter.textContent = source.length ? (page * 20 + 1) + '–' + Math.min(source.length, page * 20 + 20) + ' / ' + source.length : w('Sin hallazgos', 'No findings', "Sem achados");
      previous.disabled = page === 0; next.disabled = (page + 1) * 20 >= source.length; listing.append(grid);
    }
    controls.append(previous, counter, next); draw(); map.append(listing, controls); box.append(map);
    const collection = card(h('h2', {}, w('Afirmaciones registradas', 'Recorded claims', "Afirmações registradas")));
    const editor = card(h('h2', {}, w('Añadir afirmación', 'Add claim', "Adicionar afirmação")), claimForm({finding_uid: '', statement: '', kind: 'observed', demonstrates: '', does_not_demonstrate: '', evidence_uids: []}));
    if (!state.claims.length) collection.append(notice('Escribe tu primera afirmación. Ninguna se genera automáticamente.', 'Write your first claim. None is generated automatically.', "Escreva sua primeira afirmação. Nenhuma é gerada automaticamente."));
    paged(collection,state.claims,item=>claimRow(item,editor));
    box.append(collection, editor);
  }
  function findingFormContext(form, context) {
    return context ? h('p', {class:'insights-note','data-decision-finding-uid':context.uid}, w('Hallazgo: ', 'Finding: ', "Achado: ") + titleFor(context.uid)) : choose('Hallazgo', 'Finding', "Achado", form, 'finding_uid', findingChoices());
  }
  function claimRow(item, editor, context = null) {
    const row = h('details', {'data-claim-uid':item.uid}, h('summary', {}, titleFor(item.finding_uid) + ': ' + item.statement));
    row.append(h('p', {}, w('Tipo de afirmación: ', 'Claim type: ', "Tipo de afirmação: ") + w(...({observed:['Observación','Observation', "Observação"],inference:['Inferencia','Inference', "Inferência"],hypothesis:['Hipótesis','Hypothesis', "Hipótese"]}[item.kind]||[item.kind,item.kind,item.kind]))), h('p', {}, w('Demuestra: ', 'Demonstrates: ', "Demonstra: ") + item.demonstrates), h('p', {}, w('No demuestra: ', 'Does not demonstrate: ', "Não demonstra: ") + item.does_not_demonstrate));
    for (const uid of item.evidence_uids || []) row.append(evidenceContext(uid));
    row.append(actions(button('Editar', 'Edit', "Editar", () => { editor.replaceChildren(claimForm(clone(item),context)); reveal(editor.querySelector('input,textarea,select')); }, 'edit-claim'), button('Eliminar esta afirmación', 'Remove this claim', "Remover esta afirmação", () => mutate({action: 'delete_claim', uid: item.uid},null,context), 'delete-claim')));
    return row;
  }
  function claimForm(form, context = null) {
    if(restoring?.slug===S.slug&&restoring.key.startsWith('claim-')){form=restoring.form;restoring=null;}else form=draft('claim-'+(form.uid||(context?'new-'+context.uid:'new')),form);
    return h('div', {class: 'insights-form'}, findingFormContext(form, context),
      choose('Tipo de afirmación', 'Claim type', "Tipo de afirmação", form, 'kind', [['observed','Observación','Observation', "Observação"],['inference','Inferencia','Inference', "Inferência"],['hypothesis','Hipótesis','Hypothesis', "Hipótese"]]),
      field('Afirmación', 'Claim', "Afirmação", form, 'statement', {rows: 3}), field('Qué demuestra', 'What it demonstrates', "O que demonstra", form, 'demonstrates', {rows: 3}),
      field('Qué no demuestra', 'What it does not demonstrate', "O que não demonstra", form, 'does_not_demonstrate', {rows: 3}), evidenceList(form),
      button('Guardar afirmación', 'Save claim', "Salvar afirmação", () => mutate({action: 'set_claim', ...form},form,context), 'save-claim', true));
  }
  function risk(box) {
    box.append(notice('La prioridad de negocio es una decisión documentada, separada de CVSS y de la severidad técnica. La herramienta no inventa apetito de riesgo ni aprueba tolerancias.', 'Business priority is a documented decision, separate from CVSS and technical severity. The tool does not invent risk appetite or approve tolerances.', "A prioridade de negócio é uma decisão documentada, separada do CVSS e da severidade técnica. A ferramenta não inventa o apetite a risco nem aprova tolerâncias."));
    const list = card(h('h2', {}, w('Decisiones registradas', 'Recorded decisions', "Decisões registradas")));
    const editor = card(h('h2', {}, w('Documentar prioridad', 'Document priority', "Documentar prioridade")), riskForm({finding_uid: '', service: '', objective: '', consequence: '', tolerance: '', source: '', assumptions: '', priority: 'unassigned', rationale: '', owner: ''}));
    paged(list,state.risks,item=>riskRow(item,editor));
    if (!state.risks.length) list.append(notice('Sin decisiones de negocio registradas.', 'No business decisions recorded.', "Nenhuma decisão de negócio registrada."));
    box.append(list, editor);
  }
  const riskNames = {objective:['Objetivo de negocio','Business objective', "Objetivo de negócio"], consequence:['Consecuencia','Consequence', "Consequência"], tolerance:['Tolerancia acordada (vacío: no acordada)','Agreed tolerance (empty: not agreed)', "Tolerância acordada (vazio: não acordada)"], source:['Fuente o acuerdo','Source or agreement', "Fonte ou acordo"], assumptions:['Supuestos y límites','Assumptions and limits', "Premissas e limites"], rationale:['Justificación de prioridad','Priority rationale', "Justificativa da prioridade"], owner:['Responsable de la decisión','Decision owner', "Responsável pela decisão"]};
  function riskRow(item, editor, context = null) {
    return h('details', {'data-risk-uid':item.uid}, h('summary', {}, (item.priority==='unassigned'?w('Sin prioridad asignada','Priority unassigned', "Prioridade não atribuída"):item.priority) + ' · ' + item.service + ' · ' + titleFor(item.finding_uid)),
      h('dl', {class: 'insights-definition'}, ...['objective','consequence','tolerance','source','assumptions','rationale','owner'].flatMap(key => [h('dt', {}, w(...riskNames[key])), h('dd', {}, item[key] || (key === 'tolerance' ? w('No acordada', 'Not agreed', "Não acordado") : w('No registrado', 'Not recorded', "Não registrado")))])),
      actions(button('Editar decisión', 'Edit decision', "Editar decisão", () => { editor.replaceChildren(riskForm(clone(item),context)); reveal(editor.querySelector('input,textarea,select')); }, 'edit-risk'), button('Eliminar decisión', 'Remove decision', "Remover decisão", () => mutate({action: 'delete_risk', uid: item.uid},null,context), 'delete-risk')));
  }
  function riskForm(form, context = null) {
    if(restoring?.slug===S.slug&&restoring.key.startsWith('risk-')){form=restoring.form;restoring=null;}else form=draft('risk-'+(form.uid||(context?'new-'+context.uid:'new')),form);
    return h('div', {class: 'insights-form'}, findingFormContext(form, context), field('Servicio afectado', 'Affected service', "Serviço afetado", form, 'service'),
      ...Object.entries(riskNames).map(([key, labels]) => field(...labels, form, key, {rows: ['consequence','rationale','assumptions'].includes(key) ? 3 : null})),
      choose('Prioridad acordada', 'Agreed priority', "Prioridade acordada", form, 'priority', [['unassigned','Sin asignar','Unassigned', "Não atribuído"],['P1','P1','P1', "P1"],['P2','P2','P2', "P2"],['P3','P3','P3', "P3"]]),
      button('Guardar decisión', 'Save decision', "Salvar decisão", () => mutate({action: 'set_risk', ...form},form,context), 'save-risk', true));
  }
  function review(box) {
    const names = {not_reviewed:['Sin revisión editorial','Not editorially reviewed', "Sem revisão editorial"],approved:['Revisión editorial aprobada','Editorial review approved', "Revisão editorial aprovada"],changes_requested:['Cambios solicitados','Changes requested', "Alterações solicitadas"],stale:['Revisión anterior: el contenido cambió','Previous review: content has changed', "Revisão anterior: o conteúdo mudou"]};
    box.append(card(h('h2', {}, w(...(names[state.review_status?.state] || names.not_reviewed))), notice('Las firmas de autor son declaraciones locales. Aprobar una revisión editorial no verifica una vulnerabilidad ni autoriza una publicación.', 'Author identities are local declarations. Editorial approval does not verify a vulnerability or authorize publication.', "As identidades dos autores são declarações locais. A aprovação editorial não verifica uma vulnerabilidade nem autoriza a publicação."), h('p', {class: 'insights-hash'}, w('Contenido revisado: ', 'Reviewed content: ', "Conteúdo revisado: ") + state.digest)));
    const form = draft('comment-new',{finding_uid: '', field: 'report', body: '', author: '', visibility: 'private'});
    const context = h('pre', {class: 'insights-context', tabindex: 0}), pane = h('div', {class: 'insights-split'});
    const editor = card(h('h2', {}, w('Añadir observación', 'Add observation', "Adicionar observação")),
      choose('Contexto', 'Context', "Contexto", form, 'finding_uid', findingChoices(true)), choose('Campo', 'Field', "Campo", form, 'field', [['report','Informe','Report', "Relatório"],['description_md','Descripción','Description', "Descrição"],['impact_md','Impacto','Impact', "Impacto"],['remediation_md','Remediación','Remediation', "Correção"]]),
      field('Observación', 'Comment', "Comentário", form, 'body', {rows: 4}), field('Autor (declaración local)', 'Author (local declaration)', "Autor (declaração local)", form, 'author'), choose('Visibilidad del comentario', 'Comment visibility', "Visibilidade do comentário", form, 'visibility', [['private','Privado','Private', "Privado"],['public','Apto para revisión pública','Suitable for public review', "Adequado para revisão pública"]]),
      notice('La visibilidad del comentario no publica nada. Las entregas por destinatario excluyen los comentarios internos.', 'Comment visibility does not publish anything. Audience deliveries exclude internal comments.', "A visibilidade do comentário não publica nada. Entregas por público excluem comentários internos."), button('Guardar observación', 'Save comment', "Salvar comentário", () => mutate({action:'add_comment',field:form.field,body:form.body,author:form.author,visibility:form.visibility,...(form.finding_uid?{finding_uid:form.finding_uid}:{})},form), 'add-comment', true));
    function showContext() { const f = S.data.findings?.find(f => f.uid === form.finding_uid); context.textContent = f ? (f[form.field] || w('Este campo no tiene texto.', 'This field has no text.', "Este campo não contém texto.")) : (S.data.meta.report_title || S.slug); }
    editor.addEventListener('insights-change', showContext); showContext(); pane.append(editor, card(h('h2', {}, w('Texto de contexto (solo lectura)', 'Context text (read only)', "Texto de contexto (somente leitura)")), context)); box.append(pane);
    const comments = card(h('h2', {}, w('Observaciones por revisión', 'Revision comments', "Comentários da revisão")));
    paged(comments,state.comments,comment=>{
      const resolution = draft('resolve-'+comment.uid,{resolution: '', author: ''});
      const row = h('details', {open: comment.status === 'open' ? '' : null}, h('summary', {}, (comment.status==='open'?w('Abierta','Open', "Aberto"):w('Resuelta','Resolved', "Resolvido")) + ' · ' + titleFor(comment.finding_uid) + ' · ' + comment.field), h('p', {}, comment.body),
        h('p', {}, comment.author + ' · ' + (comment.visibility==='private'?w('Privada','Private', "Privado"):w('Pública declarada','Self-declared public', "Autodeclarado público")) + ' · ' + comment.created), h('p', {class:'insights-hash'}, w('Revisión: ', 'Revision: ', "Revisão: ") + comment.revision));
      if (comment.status === 'open') row.append(field('Cómo se resolvió', 'How it was resolved', "Como foi resolvido", resolution, 'resolution', {rows: 2}), field('Autor de la resolución', 'Resolution author', "Autor da resolução", resolution, 'author'), button('Registrar resolución', 'Record resolution', "Registrar resolução", () => mutate({action:'resolve_comment',uid:comment.uid,...resolution},resolution), 'resolve-comment'));
      else row.append(h('p', {}, comment.resolution || ''));
      return row;
    });
    if (!state.comments.length) comments.append(notice('No hay observaciones registradas.', 'No comments recorded.', "Nenhum comentário registrado."));
    const decision = draft('review-new',{decision: 'changes_requested', author: '', notes: ''});
    box.append(comments, card(h('h2', {}, w('Registrar revisión de este contenido', 'Record review of this content', "Registrar revisão deste conteúdo")), choose('Decisión editorial', 'Editorial decision', "Decisão editorial", decision, 'decision', [['changes_requested','Solicitar cambios','Request changes', "Solicitar alterações"],['approved','Aprobación editorial','Editorial approval', "Aprovação editorial"]]), field('Autor de la revisión', 'Review author', "Autor da revisão", decision, 'author'), field('Notas de revisión', 'Review notes', "Notas da revisão", decision, 'notes', {rows:3}), button('Registrar revisión', 'Record review', "Registrar revisão", () => mutate({action:'review',...decision},decision), 'record-review', true)));
  }
  const planLabels={originals:['Archivos originales privados','Private original files', "Arquivos originais privados"],capture_inbox:['Bandeja de captura','Capture inbox', "Caixa de capturas"],private_backup:['Respaldo editable privado','Private editable backup', "Backup editável privado"],private_history:['Historial privado','Private history', "Histórico privado"],review_comments:['Comentarios internos de revisión','Internal review comments', "Comentários internos da revisão"],editorial_reviews:['Decisiones editoriales internas','Internal editorial decisions', "Decisões editoriais internas"],selected_findings_full_content:['Contenido completo de los hallazgos seleccionados','Full content of selected findings', "Conteúdo completo dos achados selecionados"],selected_sections:['Secciones seleccionadas','Selected sections', "Seções selecionadas"],enabled_assets_coverage_retest:['Activos, cobertura y retest habilitados','Enabled assets, coverage and retest', "Ativos, cobertura e retestes habilitados"],cleaned_rendered_images:['Imágenes procesadas y sin metadatos','Processed metadata-free images', "Imagens processadas sem metadados"],included_attachments:['Anexos habilitados','Enabled attachments', "Anexos habilitados"],report_identity:['Identidad del informe','Report identity', "Identidade do relatório"],unselected_findings:['Hallazgos no seleccionados','Unselected findings', "Achados não selecionados"],unselected_sections:['Secciones no seleccionadas','Unselected sections', "Seções não selecionadas"],commands:['Comandos','Commands', "Comandos"],raw_targets_paths:['Objetivos y rutas técnicas originales','Raw technical targets and paths', "Alvos e caminhos técnicos originais"],images:['Imágenes','Images', "Imagens"],attachments:['Anexos','Attachments', "Anexos"],contacts:['Contactos','Contacts', "Contatos"],assets:['Activos detallados','Detailed assets', "Ativos detalhados"],coverage:['Cobertura detallada','Detailed coverage', "Cobertura detalhada"],retests:['Retests detallados','Detailed retests', "Retestes detalhados"],raw_evidence:['Evidencia técnica original','Raw technical evidence', "Evidência técnica original"],source_sections:['Secciones de origen','Source sections', "Seções de origem"],custom_metadata:['Metadatos personalizados','Custom metadata', "Metadados personalizados"],authored_public_title_alias:['Título y alias público redactados','Authored public title and alias', "Título e alias públicos redigidos"],explicitly_approved_public_text:['Texto público redactado y revisado explícitamente','Explicitly authored and reviewed public text', "Texto público redigido e revisado explicitamente"],declared_publication_basis:['Procedencia y permiso declarados','Declared provenance and permission', "Proveniência e permissão declaradas"],source_titles:['Títulos técnicos de origen','Source technical titles', "Títulos técnicos de origem"],source_descriptions:['Descripciones de origen','Source descriptions', "Descrições de origem"],source_impacts:['Impactos de origen','Source impacts', "Impactos de origem"],source_remediations:['Remediaciones de origen','Source remediations', "Correções de origem"],technical_scores:['Puntuaciones técnicas','Technical scores', "Pontuações técnicas"],source_finding_ids_uids:['Identificadores originales de hallazgo','Original finding identifiers', "Identificadores originais dos achados"],all_insights:['Todo el espacio de decisiones internas','All internal decision workspace content', "Todo o conteúdo interno do espaço de decisões"],prose_titles_descriptions_impacts_remediation:['Título, descripción, impacto y mitigación en prosa','Prose title, description, impact and remediation', "Título, descrição, impacto e correção em prosa"],technical_severity_cvss:['Severidad técnica y CVSS registrados','Recorded technical severity and CVSS', "Severidade técnica e CVSS registrados"],structured_business_decisions:['Decisiones de negocio documentadas','Documented business decisions', "Decisões de negócio documentadas"],selected_client_alias_or_client:['Alias o nombre de cliente elegido','Selected client alias or name', "Alias ou nome de cliente selecionado"],inline_code:['Código en línea','Inline code', "Código em linha"],code_blocks:['Bloques de código','Code blocks', "Blocos de código"],link_targets:['Destinos de enlaces','Link destinations', "Destinos dos links"],claims:['Afirmaciones técnicas detalladas','Detailed technical claims', "Afirmações técnicas detalhadas"]};
  function audiences(box, hooks = {}) {
    box.append(notice('Cada perfil genera archivos independientes. Un filtro de pantalla no elimina contenido de un HTML. Comprueba el plan y el archivo final antes de compartir.', 'Each profile generates independent files. A screen filter does not remove HTML content. Review the plan and final file before sharing.', "Cada perfil gera arquivos independentes. Um filtro de tela não remove conteúdo do HTML. Revise o plano e o arquivo final antes de compartilhar."));
    const source = hooks.findings || state?.map?.findings || [], settings=draft('audience-new',{selected:new Set(source.map(f=>f.uid)),form:{profile:'technical',title:'',client_alias:'',provenance_label:'simulation',review_confirmed:false,publish_consent:false},alias:{needle:S.data.meta.client||'',replacement:''},authored:new Map(),selectedSections:new Set((S.data.report?.sections||[]).map(s=>s.key)),sectionsChanged:false,formats:new Set(['pdf','docx','md','html'])}),selected=settings.selected;
    const form = settings.form;
    
    const alias=settings.alias,authored=settings.authored,selectedSections=settings.selectedSections,formats=settings.formats;
    const live=new Set(source.map(f=>f.uid));for(const uid of selected)if(!live.has(uid))selected.delete(uid);for(const uid of authored.keys())if(!live.has(uid))authored.delete(uid);const liveSections=new Set([...(S.data.report?.sections||[]).map(row=>row.key),'rg_assets','rg_coverage','rg_retest']);for(const key of selectedSections)if(!liveSections.has(key))selectedSections.delete(key);
    const editor = card(h('h2', {}, w('Configurar destinatario', 'Configure audience', "Configurar público"))), contents = h('div', {}), results = card(h('h2', {}, w('Plan de publicación', 'Publication plan', "Plano de publicação"))), resultStatus = h('p', {role:'status'});
    const profile = choose('Perfil', 'Profile', "Perfil", form, 'profile', [['technical','Informe técnico','Technical report', "Relatório técnico"],['executive','Resumen de dirección','Executive summary', "Resumo executivo"],['public','Caso público revisado','Reviewed public case', "Caso público revisado"]]);
    editor.append(profile, field('Título de la entrega (opcional)', 'Delivery title (optional)', "Título da entrega (opcional)", form, 'title'), contents);
    let sectionsChanged=settings.sectionsChanged;
    const sectionBox = h('fieldset', {}, h('legend', {}, w('Secciones técnicas incluidas', 'Included technical sections', "Seções técnicas incluídas")));
    const shownSections=new Set((S.data.report?.sections||[]).map(s=>s.key));
    for (const s of S.data.report?.sections || []) sectionBox.append(checkbox(S.catBy?.[s.key]?.['title_'+S.uiLang] || s.title || s.key, S.catBy?.[s.key]?.['title_'+S.uiLang] || s.title || s.key, S.catBy?.[s.key]?.['title_'+S.uiLang] || s.title || s.key, selectedSections.has(s.key), checked => {sectionsChanged=true;settings.sectionsChanged=true;if(checked)selectedSections.add(s.key);else selectedSections.delete(s.key);}, s.key));
    const selection = h('fieldset', {}, h('legend', {}, w('Hallazgos incluidos', 'Included findings', "Achados incluídos"))), list = h('div', {}), search = h('input', {type:'search',placeholder:w('Buscar por título o ID', 'Search title or ID', "Pesquisar título ou ID"),'aria-label':w('Buscar hallazgos para la entrega', 'Search delivery findings', "Pesquisar achados da entrega")});
    let page = 0;
    const count = h('p', {role:'status'}), paging = actions();
    const previous = button('Anterior', 'Previous', "Anterior", () => {page--; paintSelection();}, 'audience-previous'), next = button('Siguiente', 'Next', "Próximo", () => {page++; paintSelection();}, 'audience-next');
    paging.append(previous, next); selection.append(search, count, list, paging);
    function paintSelection() {
      list.replaceChildren(); const query = search.value.toLocaleLowerCase(), matching = source.filter(f => (f.id+' '+f.title).toLocaleLowerCase().includes(query));
      const maxPage = Math.max(0, Math.ceil(matching.length/30)-1); page = Math.min(page,maxPage);
      for (const f of matching.slice(page*30,page*30+30)) list.append(checkbox(f.id+' · '+f.title, f.id+' · '+f.title, f.id+' · '+f.title, selected.has(f.uid), checked => {
        if(checked)selected.add(f.uid);else selected.delete(f.uid);count.textContent=selected.size+' '+w('seleccionados','selected', "selecionados")+' / '+source.length;paintPublic();invalidate();
      }, f.uid));
      count.textContent = selected.size+' '+w('seleccionados','selected', "selecionados")+' / '+source.length+' · '+matching.length+' '+w('coincidencias','matches', "resultados"); previous.disabled=page===0;next.disabled=page===maxPage;
    }
    search.addEventListener('input',()=>{page=0;paintSelection();});
    const publicBox = h('div', {}), safeBox = h('div', {});
    safeBox.append(field('Alias de cliente', 'Client alias', "Alias do cliente", form, 'client_alias'), field('Nombre literal a sustituir', 'Literal name to replace', "Nome literal a substituir", alias, 'needle'), field('Sustitución explícita', 'Explicit replacement', "Substituição explícita", alias, 'replacement'));
    let publicPage=settings.publicPage||0;
    function paintPublic() {
      publicBox.replaceChildren(); if(form.profile!=='public')return;
      publicBox.append(notice('Redacta contenido público nuevo para cada hallazgo seleccionado. Los campos empiezan vacíos; no copiamos texto técnico ni evidencias privadas.', 'Author new public content for each selected finding. Fields begin empty; technical text and private evidence are not copied.', "Redija novo conteúdo público para cada achado selecionado. Os campos começam vazios; textos técnicos e evidências privadas não são copiados."));
      const publicRows=source.filter(f=>selected.has(f.uid));publicPage=Math.min(publicPage,Math.max(0,Math.ceil(publicRows.length/20)-1));settings.publicPage=publicPage;
      for(const f of publicRows)if(!authored.has(f.uid))authored.set(f.uid,{finding_uid:f.uid,title:'',summary:'',impact:'',remediation:''});
      const publicHeading=h('h3',{tabindex:'-1','data-public-page-title':''},w('Texto público seleccionado: ','Selected public text: ', "Texto público selecionado: ")+(publicRows.length?publicPage*20+1:0)+'–'+Math.min(publicRows.length,publicPage*20+20)+' / '+publicRows.length);publicBox.append(publicHeading);
      if(publicRows.length>20){const previous=button('Texto anterior','Previous text', "Texto anterior",()=>{publicPage--;paintPublic();reveal(publicBox.querySelector('[data-public-page-title]'));},'public-previous'),next=button('Texto siguiente','Next text', "Próximo texto",()=>{publicPage++;paintPublic();reveal(publicBox.querySelector('[data-public-page-title]'));},'public-next');previous.disabled=publicPage===0;next.disabled=(publicPage+1)*20>=publicRows.length;publicBox.append(actions(previous,next));}
      for(const f of publicRows.slice(publicPage*20,publicPage*20+20)) {
        const content=authored.get(f.uid);
        publicBox.append(h('details',{open:''},h('summary',{},f.id+' · '+f.title),field('Título público','Public title', "Título público",content,'title'),field('Resumen público','Public summary', "Resumo público",content,'summary',{rows:3}),field('Impacto público','Public impact', "Impacto público",content,'impact',{rows:3}),field('Mitigación pública','Public remediation', "Correção pública",content,'remediation',{rows:3})));
      }
      publicBox.append(choose('Procedencia declarada', 'Declared provenance', "Proveniência declarada", form, 'provenance_label', [['simulation','Simulación: caso ficticio','Simulation: fictional case', "Simulação: caso fictício"],['authorized','Evaluación autorizada: autorización propia','Authorized assessment: your own authorization', "Avaliação autorizada: sua própria autorização"]]),
        checkbox('Revisé el texto, las sustituciones y los límites del caso.','I reviewed the text, replacements and case limitations.', "Revisei o texto, as substituições e as limitações do caso.",form.review_confirmed,v=>{form.review_confirmed=v;invalidate();},'review-confirmed'),
        checkbox('Tengo autorización para publicar este contenido.','I am authorized to publish this content.', "Tenho autorização para publicar este conteúdo.",form.publish_consent,v=>{form.publish_consent=v;invalidate();},'publish-consent'));
    }
    let preview = null, previewGeneration = 0;
    function invalidate(){preview=null;previewGeneration++;ack.value=false;ackLabel.querySelector('input').checked=false;resultStatus.textContent=w('Configuración cambiada. Vuelve a comprobar el plan antes de generar.','Configuration changed. Check the plan again before generating.', "A configuração mudou. Verifique o plano novamente antes de gerar.");exportButton.disabled=true;hooks.onInvalidate?.();}
    function options(){return {profile:form.profile,finding_uids:[...selected],...(form.profile==='technical'&&sectionsChanged?{section_keys:[...selectedSections]}:{}),...(form.title?{title:form.title}:{}),...(form.client_alias?{client_alias:form.client_alias}:{}),aliases:alias.needle&&alias.replacement?[{...alias}]:[],...(form.profile==='public'?{review_confirmed:form.review_confirmed,publish_consent:form.publish_consent,provenance_label:form.provenance_label,approved_content:source.filter(f=>selected.has(f.uid)).map(f=>({...authored.get(f.uid)}))}:{})};}
    function paintProfile(){sectionBox.hidden=form.profile!=='technical';safeBox.hidden=form.profile==='technical';paintSelection();paintPublic();invalidate();}
    profile.querySelector('select').addEventListener('change',()=>{selected.clear();if(form.profile!=='public')source.forEach(f=>selected.add(f.uid));paintProfile();});
    const formatBox=h('fieldset',{},h('legend',{},w('Formatos independientes','Independent formats', "Formatos independentes")));
    for(const name of ['pdf','docx','md','html'])formatBox.append(checkbox(name.toUpperCase(),name.toUpperCase(), name.toUpperCase(),formats.has(name),v=>v?formats.add(name):formats.delete(name),'format-'+name));
    const ack={value:false};
    const ackLabel=checkbox('He revisado los avisos del plan y acepto incluirlos en la entrega.','I reviewed the plan warnings and agree to include them in the delivery.', "Revisei os avisos do plano e aceito incluí-los na entrega.",false,v=>ack.value=v,'audience-ack');
    const exportButton=button('Generar y descargar ZIP','Generate and download ZIP', "Gerar e baixar ZIP",async()=>{
      if(!preview||preview.options!==JSON.stringify(options())||preview.etag!==projectStore.etag||projectStore.dirty)throw Error(w('Vuelve a comprobar el plan de esta revisión.','Check the plan again for this revision.', "Verifique o plano novamente para esta revisão."));
      hooks.beforeExport?.();
      if(!formats.size)throw Error(w('Elige al menos un formato.','Select at least one format.', "Selecione pelo menos um formato."));
      if(preview.errors)throw Error(w('Corrige los errores del plan.','Fix the plan errors.', "Corrija os erros do plano."));
      if(preview.warnings&&!ack.value)throw Error(w('Revisa y confirma los avisos.','Review and acknowledge the warnings.', "Revise e reconheça os avisos."));
      resultStatus.textContent=w('Generando los formatos desde la copia revisada…','Generating formats from the reviewed snapshot…', "Gerando formatos a partir da cópia revisada…");
      // Export the exact reviewed revision. Saving again here could silently
      // switch snapshots while another form or tab changes the project.
      const snapshot={slug:S.slug,etag:preview.etag},payload={...options(),formats:[...formats],label:form.title||w('Entrega por destinatario','Audience delivery', "Entrega por público"),acknowledge_warnings:ack.value};
      busyProject(true);
      try {await downloadResponse(await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/audiences/export',{method:'POST',headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(payload)})),'audience-report.zip');}
      finally {busyProject(false);}
      resultStatus.textContent=w('Paquete descargado. Revisa los archivos antes de compartir.','Package downloaded. Review the files before sharing.', "Pacote baixado. Revise os arquivos antes de compartilhar.");
      hooks.onExported?.(snapshot);
    },'export-audience',true); exportButton.disabled=true;
    const previewButton=button('Comprobar qué se incluirá','Check what will be included', "Verificar o que será incluído",async()=>{
      invalidate();const generation=previewGeneration;
      const sent=options(), snapshot=await saved(), response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/audiences/preview',{method:'POST',headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(sent)})), data=await response.json();
      if(!results.isConnected||S.slug!==snapshot.slug||projectStore.etag!==snapshot.etag||projectStore.dirty||generation!==previewGeneration||JSON.stringify(sent)!==JSON.stringify(options())||data.revision!==snapshot.etag?.replace(/^"|"$/g,''))return;
      for(const section of data.available_sections||[])if(!shownSections.has(section.key)){shownSections.add(section.key);const enabled=!sectionsChanged&&(data.plan?.section_keys||[]).includes(section.key);if(enabled)selectedSections.add(section.key);sectionBox.append(checkbox(section.title,section.title, section.title,selectedSections.has(section.key),checked=>{sectionsChanged=true;settings.sectionsChanged=true;if(checked)selectedSections.add(section.key);else selectedSections.delete(section.key);},section.key));}
      results.replaceChildren(h('h2',{},w('Plan de publicación','Publication plan', "Plano de publicação")),resultStatus,h('p',{class:'insights-hash'},w('Revisión: ','Revision: ', "Revisão: ")+data.revision));
      for(const [key,label] of [['included',w('Incluido','Included', "Incluído")],['excluded',w('Excluido realmente','Actually excluded', "Efetivamente excluído")]])results.append(h('details',{open:key==='included'?'':null},h('summary',{},label+' · '+(data.plan?.[key]||[]).length),h('ul',{},...(data.plan?.[key]||[]).map(text=>h('li',{},planLabels[text]?w(...planLabels[text]):String(text).replaceAll('_',' '))))));
      results.append(h('p',{},(data.plan?.finding_count||0)+' '+((data.plan?.finding_count||0)===1?w('hallazgo; originales privados excluidos','finding; private originals excluded', "achado; originais privados excluídos"):w('hallazgos; originales privados excluidos','findings; private originals excluded', "achados; originais privados excluídos"))));
      if(data.content_text)results.append(h('details',{open:''},h('summary',{},w('Contenido real que saldrá en esta entrega','Actual outgoing delivery content', "Conteúdo efetivo da entrega de saída")),h('pre',{class:'insights-context',tabindex:0},data.content_text)));
      for(const issue of data.issues||[])results.append(hooks.issueNode?hooks.issueNode(issue):h('p',{class:issue.level==='error'?'wf-error':'wf-warning'},issue.message));
      const errors=(data.issues||[]).some(i=>i.level==='error'),warnings=(data.issues||[]).some(i=>i.level!=='error');preview={options:JSON.stringify(sent),etag:snapshot.etag,errors,warnings};
      resultStatus.textContent=errors?w('Corrige los errores del plan.','Fix the plan errors.', "Corrija os erros do plano."):w('Plan listo para tu revisión.','Plan ready for your review.', "Plano pronto para sua revisão.");
      results.append(ackLabel,formatBox,exportButton);exportButton.disabled=errors;
      hooks.onPreview?.({data,revision:snapshot.etag,errors,warnings});
    },'preview-audience',true);
    contents.append(selection,sectionBox,safeBox,publicBox,previewButton);
    editor.addEventListener('input',event=>{if(event.target!==search)invalidate();});editor.addEventListener('change',invalidate); results.append(resultStatus);box.append(editor,results);paintProfile();
    return {editor,results,formatBox,ackLabel,exportButton,previewButton,invalidate,
      isCurrent:()=>!!preview&&preview.options===JSON.stringify(options())&&preview.etag===projectStore.etag&&!projectStore.dirty,
      options,profile:()=>form.profile};
  }
  async function visual(box, slug) {
    box.append(notice('Revisa las páginas del PDF real, ligado a su SHA-256. Es una revisión visual manual, no una verificación técnica. Las descargas de cola duran una hora; las vistas temporales de PDF y sus registros duran 30 minutos.', 'Review actual PDF pages, tied to their SHA-256. This is manual visual review, not technical verification. Queue downloads last one hour; temporary PDF views and their records expire after 30 minutes.', "Revise as páginas do PDF real, vinculadas ao seu SHA-256. Esta é uma revisão visual manual, não uma verificação técnica. Os downloads da fila duram uma hora; as prévias temporárias de PDF e seus registros expiram após 30 minutos."));
    const capability=await api.get('/api/visual/capabilities');if(!box.isConnected||S.slug!==slug)return;if(!capability.available){box.append(card(h('h2',{},w('Preparar vistas reales de PDF','Prepare actual PDF previews', "Preparar prévias reais em PDF")),notice('Instala el complemento local de vistas previas para abrir las páginas reales del PDF. Los demás módulos y la exportación siguen disponibles.','Install the local preview extra to open actual PDF pages. Other modules and exports remain available.', "Instale o extra local de prévia para abrir as páginas reais do PDF. Os demais módulos e as exportações continuam disponíveis."),h('code',{},capability.install)));return;}
    const output=card(h('h2',{},w('Documento que revisarás','Document to review', "Documento a revisar"))),pages=h('div',{});box.append(output,pages);
    const retained=VisualReviewUI.mount({box,slug,display,saved});
    const choice={id:''},selectJob=h('select',{'aria-label':w('PDF o paquete de esta sesión','PDF or package from this session', "PDF ou pacote desta sessão"),'data-insights-field':'visual-job'},h('option',{value:''},w('Consulta resultados de la sesión','Query session results', "Consultar resultados da sessão")));
    selectJob.addEventListener('change',()=>choice.id=selectJob.value);
    let run=0;
    async function populateJobs(){const rows=await api.get('/api/jobs');if(!selectJob.isConnected||S.slug!==slug)return;
      const jobs=rows.filter(job=>job.stage==='done'&&(/\.pdf$|\.zip$/i.test(job.filename||'')||job.formats?.includes('pdf')));selectJob.replaceChildren(h('option',{value:''},w('Elige una exportación de la sesión','Choose a session export', "Escolha uma exportação da sessão")),...jobs.map(job=>h('option',{value:job.id},job.label+' · '+job.revision.slice(0,12))));
      choice.id='';if(!jobs.length)toast(w('Todavía no hay exportaciones PDF. Usa Entrega o sube un PDF generado.','No PDF exports yet. Use Deliver or upload a generated PDF.', "Ainda não há exportações em PDF. Use Entregar ou envie um PDF gerado."));
    }
    output.append(h('label',{class:'insights-field'},w('Exportación final de la sesión (identifica el proyecto por su etiqueta)','Final session export (identify the project by its label)', "Exportação final da sessão (identifique o projeto pelo rótulo)"),selectJob),actions(button('Actualizar resultados','Refresh results', "Atualizar resultados",populateJobs,'visual-refresh'),button('Abrir páginas reales','Open actual pages', "Abrir páginas reais",async()=>{
      if(!choice.id)throw Error(w('Selecciona una exportación con PDF.','Select an export containing PDF.', "Selecione uma exportação que contenha PDF."));
      if(!retained.allowSwitch())return;
      const token=++run,jobId=choice.id;pages.replaceChildren(h('p',{role:'status'},w('Rasterizando el PDF generado…','Rasterizing the generated PDF…', "Rasterizando o PDF gerado…")));
      const data=await api.get('/api/jobs/'+encodeURIComponent(jobId)+'/visual');if(token!==run||!pages.isConnected||S.slug!==slug)return;
      display(data,'/api/jobs/'+encodeURIComponent(jobId)+'/visual',false);
    },'visual-generate',true),button('Abrir entrega','Open delivery', "Abrir entrega",()=>{select('studio','deliver');reveal($('#editor'));},'open-delivery')));
    const upload=h('input',{type:'file',accept:'application/pdf,.pdf','aria-label':w('Archivo PDF para revisar','PDF file to review', "Arquivo PDF a revisar"),'data-insights-field':'visual-file'});
    output.append(h('details',{},h('summary',{},w('Revisar PDF descargado de destinatario','Review downloaded audience PDF', "Revisar PDF baixado por público")),notice('Elige el PDF extraído de tu ZIP o un PDF existente. El hash identifica el archivo; asociarlo a la revisión activa no demuestra que haya sido generado desde ella. Permanece temporal salvo que guardes el progreso o una copia privada de forma explícita.', 'Choose the PDF extracted from your ZIP or an existing PDF. The hash identifies the file; linking it to the active revision does not prove it was generated from that revision. It remains temporary unless you explicitly save progress or a private copy.', "Escolha o PDF extraído do seu ZIP ou um PDF existente. O hash identifica o arquivo; vinculá-lo à revisão ativa não comprova que ele foi gerado a partir dela. Ele permanece temporário, a menos que você salve explicitamente o progresso ou uma cópia privada."),h('label',{class:'insights-field'},w('PDF real (máximo 16 MiB)','Actual PDF (maximum 16 MiB)', "PDF real (máximo de 16 MiB)"),upload),button('Subir y revisar este PDF','Upload and review this PDF', "Enviar e revisar este PDF",async()=>{
      const file=upload.files?.[0];if(!file)throw Error(w('Elige un archivo PDF.','Choose a PDF file.', "Escolha um arquivo PDF."));
      if(file.size>16*1024*1024)throw Error(w('El PDF supera 16 MiB.','The PDF exceeds 16 MiB.', "O PDF excede 16 MiB."));
      if(!retained.allowSwitch())return;
      const token=++run;busyProject(true);
      try{const snapshot=await saved(),body=new FormData();body.append('file',file,file.name);
        const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/visual',{method:'POST',headers:{'If-Match':snapshot.etag},body})),data=await response.json();
        if(token!==run||!pages.isConnected||S.slug!==slug)return;upload.value='';display(data,'/api/visual/'+encodeURIComponent(data.id),true);
      }finally{busyProject(false);}
    },'visual-upload')));
    function display(data,base,uploaded){
      pages.replaceChildren();if(data.available===false){pages.append(h('p',{role:'status'},data.message||w('Instala el extra de vistas previas para rasterizar PDF reales.','Install the preview extra to rasterize actual PDFs.', "Instale o extra de prévia para rasterizar PDFs reais.")));return;}
      pages.append(h('p',{class:'insights-hash'},'SHA-256: '+data.pdf_sha256),h('p',{},w('Revisión asociada: ','Linked revision: ', "Revisão vinculada: ")+data.revision),h('p',{},w('Archivo: ','File: ', "Arquivo: ")+(data.filename||'')));
      const frame=h('div',{class:'insights-pdf-preview'}),nav=actions(),position=h('span',{role:'status'});let index=(data.saved?.progress.page||1)-1;
      const previous=button('Página anterior','Previous page', "Página anterior",()=>{index--;paintPage();},'visual-previous'),next=button('Página siguiente','Next page', "Próxima página",()=>{index++;paintPage();},'visual-next');nav.append(previous,position,next);pages.append(nav,frame);
      function paintPage(){const page=data.pages[index];frame.replaceChildren(h('img',{src:page.image_url||base+'/page/'+page.number,alt:w('Página real ','Actual page ', "Página real ")+page.number,width:page.width,height:page.height,loading:'eager'}));position.textContent=w('Página ','Page ', "Página ")+(index+1)+' / '+data.pages.length;previous.disabled=index===0;next.disabled=index===data.pages.length-1;}
      if(!data.pages?.length){pages.append(notice('El resultado no contiene un PDF disponible.','The result does not contain an available PDF.', "O resultado não contém um PDF disponível."));return;}paintPage();
      const progress=data.saved?.progress,form={author:progress?.author||'',decision:progress?.decision||'issues',note:progress?.note||''},items=clone(progress?.pages||[]),item={...(progress?.draft||{number:1,issue:'table_cut',note:''}),number:String(progress?.draft?.number||1)},observations=h('div',{});
      function paintItems(){observations.replaceChildren(...items.map((row,i)=>h('div',{class:'visual-review-observation'},h('p',{},w('Página ','Page ', "Página ")+row.number+': '+row.note+' '),checkbox('Resuelto','Resolved','Resolvido',row.resolved,value=>{row.resolved=value;},'visual-resolved'),button('Retirar','Remove', "Remover",()=>{items.splice(i,1);paintItems();},'remove-visual-issue'))));}
      pages.append(card(h('h3',{},w('Observación de una página','Page observation', "Observação da página")),choose('Página','Page', "Página",item,'number',data.pages.map(p=>[String(p.number),String(p.number)])),choose('Problema observado','Observed problem', "Problema observado",item,'issue',[['table_cut','Tabla cortada','Cut table', "Tabela cortada"],['orphan_title','Título aislado','Orphan title', "Título isolado"],['unreadable_image','Captura ilegible','Unreadable image', "Imagem ilegível"],['other','Otro','Other', "Outro"]]),field('Descripción del problema','Problem description', "Descrição do problema",item,'note',{rows:2}),button('Añadir observación','Add observation', "Adicionar observação",()=>{if(!item.note.trim())throw Error(w('Describe lo observado.','Describe what you observed.', "Descreva o que observou."));items.push({number:Number(item.number),issue:item.issue,note:item.note,resolved:false});item.note='';pages.querySelector('[data-insights-field=note]').value='';paintItems();},'add-visual-issue'),observations),
        card(h('h3',{},w('Registrar revisión visual','Record visual review', "Registrar revisão visual")),field('Autor (declaración local)','Author (local declaration)', "Autor (declaração local)",form,'author',{maxlength:120}),choose('Decisión','Decision', "Decisão",form,'decision',[['pending','Pendiente de revisión','Review pending','Revisão pendente'],['issues','Encontré problemas','I found issues', "Encontrei problemas"],['accepted','Aceptación visual manual','Manual visual acceptance', "Aceitação visual manual"]]),field('Nota general','General note', "Nota geral",form,'note',{rows:2}),button('Guardar registro de este PDF','Save record for this PDF', "Salvar registro deste PDF",async()=>{
          if(form.decision==='pending'){toast(w('Usa Guardar progreso para retomar una revisión pendiente.','Use Save progress to resume a pending review.','Use Salvar progresso para retomar uma revisão pendente.'));return;}
          const response=await requireOk(await appFetch(base+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:data.revision,pdf_sha256:data.pdf_sha256,...form,pages:items.filter(row=>!row.resolved).map(({number,issue,note})=>({number,issue,note}))})})),record=await response.json();
          toast(w('Revisión visual registrada para este PDF.','Visual review recorded for this PDF.', "Revisão visual registrada para este PDF."));pages.append(h('details',{},h('summary',{},w('Registro guardado','Saved record', "Registro salvo")),h('pre',{class:'insights-context'},JSON.stringify(record,null,2))),button('Descargar registro JSON','Download review JSON', "Baixar JSON da revisão",async()=>{
            const blob=new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),object=URL.createObjectURL(blob),a=h('a',{href:object,download:'visual-review-'+data.pdf_sha256.slice(0,12)+'.json'});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(object),30000);
          },'download-visual-review'));
        },'record-visual-review',true)));
      paintItems();retained.setCurrent(data,()=>({...form,page:index+1,pages:items,draft:{number:Number(item.number),issue:item.issue,note:item.note}}),pages);
      if(data.review)pages.append(h('details',{},h('summary',{},w('Revisión anterior de este PDF','Previous review of this PDF', "Revisão anterior deste PDF")),h('pre',{class:'insights-context'},JSON.stringify(data.review,null,2))));
      if(uploaded)pages.append(button('Eliminar este PDF temporal y su registro','Delete this temporary PDF and its record', "Excluir este PDF temporário e seu registro",async()=>{await requireOk(await appFetch(base,{method:'DELETE',headers:{'Content-Type':'application/json'},body:'{}'}));retained.clearCurrent();pages.replaceChildren(h('p',{role:'status'},w('PDF temporal eliminado.','Temporary PDF deleted.', "PDF temporário excluído.")));},'delete-visual-file'));
    }
    await populateJobs();
  }
  async function editorial(box, slug) {
    box.append(notice('Las reglas señalan redacciones que merecen revisión. No verifican vulnerabilidades, pruebas ni resultados. Ninguna sugerencia modifica el informe automáticamente.', 'Rules flag wording that deserves review. They do not verify vulnerabilities, tests or results. No suggestion changes the report automatically.', "As regras sinalizam redações que merecem revisão. Não verificam vulnerabilidades, testes nem resultados. Nenhuma sugestão altera o relatório automaticamente."));
    const rules=await api.get('/api/projects/'+encodeURIComponent(slug)+'/insights/editorial?lang='+encodeURIComponent(S.uiLang));if(!box.isConnected||S.slug!==slug)return;
    const transparent=card(h('h2',{},w('Reglas transparentes','Transparent rules', "Regras transparentes")));
    for(const rule of rules.rules||[])transparent.append(h('details',{},h('summary',{},rule.name||rule.rule||rule.id),h('p',{},rule[S.uiLang]||rule.description||rule.message||JSON.stringify(rule))));
    const issues=card(h('h2',{},w('Observaciones editoriales','Editorial observations', "Observações editoriais")));
    paged(issues,rules.issues||[],issue=>h('article',{class:'insights-editorial-issue'},h('h3',{},titleFor(issue.finding_uid)),h('p',{},issue.message),h('p',{},issue.help),h('code',{},issue.path),issue.finding_uid?button('Abrir el texto original','Open original text', "Abrir texto original",()=>{const index=S.data.findings.findIndex(f=>f.uid===issue.finding_uid);if(index<0)throw Error(w('Hallazgo ausente.','Finding missing.', "Achado ausente."));select('finding',index);reveal($('#editor'));},'open-editorial-finding'):null));
    if(!rules.issues?.length)issues.append(notice('No se encontraron coincidencias de estas reglas. Esto no sustituye una revisión humana.', 'No matches were found for these rules. This does not replace human review.', "Nenhuma correspondência destas regras foi encontrada. Isso não substitui uma revisão humana."));
    box.append(transparent,issues);
    if(typeof localAssistant==='function')await localAssistant(box,slug);
  }
  async function localAssistant(box, slug) {
    const assistant=card(h('h2',{},w('Asistencia opcional con IA local','Optional local AI assistance', "Assistência opcional de IA local")));
    assistant.append(notice('Selecciona un único campo y revisa exactamente qué texto enviarás a un modelo local. La herramienta solo usa loopback; comprueba también que tu servidor Ollama tenga la nube desactivada. No podemos verificar el aislamiento de red de otro proceso.', 'Select one field and review exactly which text will be sent to a local model. The tool only uses loopback; also ensure your Ollama server has cloud features disabled. We cannot verify another process’s network isolation.', "Selecione um campo e revise exatamente o texto que será enviado a um modelo local. A ferramenta usa somente loopback; verifique também se os recursos de nuvem do seu servidor Ollama estão desativados. Não podemos verificar o isolamento de rede de outro processo."));
    const capability=await api.get('/api/assistant/capabilities');if(!assistant.isConnected&&box.isConnected)box.append(assistant);if(!box.isConnected||S.slug!==slug)return;
    if(!capability.available){assistant.append(h('p',{},capability.message||w('No hay asistencia local disponible. Las reglas editoriales siguen operativas.','Local assistance is not available. Editorial rules remain usable.', "A assistência local não está disponível. As regras editoriais continuam disponíveis.")));return;}
    async function discardProposal(){const id=assistantProposals.get(slug);if(!id)return;const response=await appFetch('/api/projects/'+encodeURIComponent(slug)+'/assistant/discard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({proposal_id:id})});if(response.status!==404)await requireOk(response);assistantProposals.delete(slug);}
    if(assistantProposals.has(slug))assistant.append(button('Descartar propuesta pendiente anterior','Discard previous pending proposal', "Descartar proposta pendente anterior",async()=>{await discardProposal();toast(w('Propuesta temporal descartada.','Temporary proposal discarded.', "Proposta temporária descartada."));},'assistant-discard-pending'));
    assistant.append(h('p',{},w('Servidor fijo: ','Fixed server: ', "Servidor fixo: ")+capability.endpoint));
    const form={finding_uid:'',field:'description_md',model:'',task:'improve_clarity',confirmed_local:false},source=h('pre',{class:'insights-context',tabindex:0}),proposal=h('div',{}),models=h('select',{'aria-label':w('Modelo local instalado','Installed local model', "Modelo local instalado"),'data-insights-field':'model'},h('option',{value:''},w('Consulta modelos instalados','Query installed models', "Consultar modelos instalados")));
    models.addEventListener('change',()=>{form.model=models.value;proposal.replaceChildren();});
    const selected=choose('Hallazgo','Finding', "Achado",form,'finding_uid',findingChoices());
    const choice=choose('Único campo que se enviará','Only field that will be sent', "Único campo que será enviado",form,'field',[['description_md','Descripción','Description', "Descrição"],['impact_md','Impacto','Impact', "Impacto"],['remediation_md','Remediación','Remediation', "Correção"]]);
    let original='';
    function updateText(){const finding=S.data.findings.find(f=>f.uid===form.finding_uid);original=finding?.[form.field]||'';source.textContent=original||w('Elige un hallazgo con contenido en este campo.','Choose a finding with content in this field.', "Escolha um achado com conteúdo neste campo.");proposal.replaceChildren();}
    assistant.append(actions(button('Consultar modelos locales','Query local models', "Consultar modelos locais",async()=>{
      const response=await requireOk(await appFetch('/api/assistant/models',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})),data=await response.json();
      if(!models.isConnected||S.slug!==slug)return;const rows=data.models||data;
      models.replaceChildren(h('option',{value:''},w('Elige un modelo local','Choose a local model', "Escolha um modelo local")),...rows.map(item=>h('option',{value:typeof item==='string'?item:item.name||item.model},typeof item==='string'?item:item.name||item.model)));
      if(!rows.length)toast(w('Instala un modelo GGUF local en Ollama y vuelve a consultar.','Install a local GGUF model in Ollama, then query again.', "Instale um modelo GGUF local no Ollama e consulte novamente."));
    },'assistant-models')),h('label',{class:'insights-field'},w('Modelo local instalado','Installed local model', "Modelo local instalado"),models),selected,choice,
      choose('Tarea editorial','Editorial task', "Tarefa editorial",form,'task',[['improve_clarity','Mejorar claridad sin añadir hechos','Improve clarity without adding facts', "Melhorar a clareza sem adicionar fatos"],['review_limits','Revisar límites de la conclusión','Review conclusion limits', "Revisar os limites da conclusão"]]),h('h3',{},w('Texto exacto seleccionado (solo lectura)','Exact selected text (read only)', "Texto selecionado exato (somente leitura)")),source,
      checkbox('Autorizo enviar solamente este campo al modelo local configurado.','I authorize sending only this field to the configured local model.', "Autorizo o envio somente deste campo ao modelo local configurado.",false,v=>form.confirmed_local=v,'assistant-confirm'));
    selected.addEventListener('insights-change',updateText);choice.addEventListener('insights-change',updateText);updateText();
    assistant.append(button('Obtener propuesta editorial','Get editorial proposal', "Obter proposta editorial",async()=>{
      if(!form.finding_uid||!original.trim())throw Error(w('Selecciona un campo con contenido.','Select a field with content.', "Selecione um campo com conteúdo."));
      if(!form.confirmed_local||!form.model)throw Error(w('Elige un modelo local y confirma el campo que se enviará.','Choose a local model and confirm the field to send.', "Escolha um modelo local e confirme o campo a enviar."));
      await discardProposal();
      const snapshot=await saved(),selection={finding_uid:form.finding_uid,fields:[form.field],model:form.model,confirmed_local:true,task:form.task};
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(snapshot.slug)+'/assistant',{method:'POST',headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(selection)})),data=await response.json();
      if(!proposal.isConnected||S.slug!==snapshot.slug)return;
      assistantProposals.set(slug,data.proposal_id);
      proposal.replaceChildren(h('h3',{},w('Comparación antes de aceptar','Comparison before acceptance', "Comparação antes da aceitação")));
      for(const warning of data.warnings||[])proposal.append(h('p',{class:'wf-warning'},typeof warning==='string'?warning:warning.message));
      const accepted=new Set();
      for(const item of data.proposals||[]){const compare=h('div',{class:'insights-split'},card(h('h4',{},w('Original','Original', "Original")),h('pre',{class:'insights-context'},item.before)),card(h('h4',{},w('Propuesta editorial','Editorial proposal', "Proposta editorial")),h('pre',{class:'insights-context'},item.after)));
        proposal.append(h('h4',{},item.field),compare,checkbox('Selecciono esta propuesta para aplicar.','I select this proposal to apply.', "Seleciono esta proposta para aplicar.",false,v=>v?accepted.add(item.field):accepted.delete(item.field),'accept-'+item.field));}
      proposal.append(notice('Comprueba hechos, nombres, comandos y límites. Puedes ignorar la propuesta o editar el texto desde el hallazgo. Aceptar no verifica ninguna afirmación.', 'Check facts, names, commands and limitations. You can discard the proposal or edit text in the finding editor. Acceptance does not verify any claim.', "Verifique fatos, nomes, comandos e limitações. Você pode descartar a proposta ou editar o texto no editor do achado. A aceitação não verifica nenhuma afirmação."),
        button('Aplicar únicamente las propuestas seleccionadas','Apply only selected proposals', "Aplicar somente as propostas selecionadas",async()=>{
          if(!accepted.size)throw Error(w('Selecciona explícitamente una propuesta.','Explicitly select a proposal.', "Selecione uma proposta explicitamente."));
          if(projectStore.etag!==snapshot.etag||projectStore.dirty)throw Error(w('La revisión cambió. Obtén una nueva propuesta.','The revision changed. Obtain a new proposal.', "A revisão mudou. Obtenha uma nova proposta."));
          busyProject(true);try{const applied=await request('/assistant/apply',{proposal_id:data.proposal_id,fields:[...accepted]});await applied.json();WorkbenchUI.dirty();assistantProposals.delete(slug);await projectStore.load(snapshot.slug);S.data=projectStore.data;WorkbenchUI.dirty();renderSidebar();renderMain();reveal($('#insightsTitle'));toast(w('Propuestas seleccionadas guardadas.','Selected proposals saved.', "Propostas selecionadas salvas."));}finally{busyProject(false);}
        },'assistant-apply',true),button('Descartar esta propuesta','Discard this proposal', "Descartar esta proposta",async()=>{await discardProposal();proposal.replaceChildren(h('p',{role:'status'},w('Propuesta descartada; el informe sigue intacto.','Proposal discarded; the report remains unchanged.', "Proposta descartada; o relatório permanece inalterado.")));},'assistant-discard'));
    },'assistant-propose',true),proposal);
  }
  async function renderFinding(box, uid) {
    const slug=S.slug, lang=S.uiLang, etag=projectStore.etag;
    delete box.dataset.findingDecisionsReady;
    const status=h('p',{class:'insights-status',role:'status'},w('Leyendo las decisiones guardadas de este hallazgo…','Reading the saved decisions for this finding…', "Lendo as decisões salvas para este achado…"));
    box.append(status);
    const active=()=>box.isConnected && S.slug===slug && S.uiLang===lang && WorkbenchUI.renderedFindingUid()===uid;
    try {
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/insights?lang='+encodeURIComponent(lang))), responseTag=response.headers.get('ETag');
      const data=await response.json();
      if(!active())return;
      if(!etag||responseTag!==etag||projectStore.etag!==etag)throw Error(w('La revisión guardada cambió o no coincide con el editor. Conserva tu borrador y recarga el proyecto antes de consultar las decisiones.','The saved revision changed or differs from the editor. Keep your draft and reload the project before reading decisions.', "A revisão salva mudou ou difere do editor. Mantenha seu rascunho e recarregue o projeto antes de ler as decisões."));
      status.remove(); state=data; currentSlug=slug;
      box.dataset.findingDecisionsReady='true';
      box.append(notice('Este panel lee las decisiones guardadas. Abrirlo o cambiar de pestaña no guarda el informe ni registra decisiones. Los formularios editados se protegen localmente cuando su indicador lo confirma, hasta usar su botón de guardar.','This panel reads saved decisions. Opening it or switching tabs does not save the report or record decisions. Edited forms are protected locally when their indicator confirms it, until you use their save button.', "Este painel lê as decisões salvas. Abri-lo ou mudar de aba não salva o relatório nem registra decisões. Os formulários editados são protegidos localmente quando seu indicador confirma, até você usar o botão de salvar."));
      if(projectStore.dirty)box.append(notice('El editor tiene cambios sin guardar. Las decisiones mostradas corresponden a la revisión guardada; guardar una decisión guarda primero el borrador del informe.','The editor has unsaved changes. The displayed decisions belong to the saved revision; saving a decision first saves the report draft.', "O editor tem alterações não salvas. As decisões exibidas pertencem à revisão salva; salvar uma decisão salva primeiro o rascunho do relatório."));
      box.append(h('details',{},h('summary',{},w('Identidad de la revisión leída','Identity of the reviewed revision', "Identidade da revisão analisada")),h('p',{class:'insights-hash'},'SHA-256: '+data.digest)));
      if(!(data.map?.findings||[]).some(item=>item.uid===uid)){
        box.append(notice('Este hallazgo no consta en la revisión guardada. Guarda el informe y vuelve a consultar para documentar decisiones.','This finding is absent from the saved revision. Save the report and read again to document decisions.', "Este achado não consta na revisão salva. Salve o relatório e consulte novamente para documentar decisões."),button('Volver a consultar','Read again', "Consultar novamente",()=>{box.replaceChildren();return renderFinding(box,uid);},'finding-decisions-refresh'));
        return;
      }
      const context={uid}, selectedClaims=(data.claims||[]).filter(item=>item.finding_uid===uid), selectedRisks=(data.risks||[]).filter(item=>item.finding_uid===uid);
      const claimEditor=card(h('h3',{},w('Añadir afirmación de este hallazgo','Add a claim for this finding', "Adicionar uma afirmação para este achado")),claimForm({finding_uid:uid,statement:'',kind:'observed',demonstrates:'',does_not_demonstrate:'',evidence_uids:[]},context));
      const claimsList=card(h('h3',{},w('Afirmaciones registradas','Recorded claims', "Afirmações registradas")));
      if(!selectedClaims.length)claimsList.append(notice('Sin afirmaciones registradas para este hallazgo. No se generan automáticamente.','No claims are recorded for this finding. None are generated automatically.', "Nenhuma afirmação registrada para este achado. Elas não são geradas automaticamente."));
      paged(claimsList,selectedClaims,item=>claimRow(item,claimEditor,context));
      const riskEditor=card(h('h3',{},w('Documentar prioridad de este hallazgo','Document priority for this finding', "Documentar a prioridade deste achado")),riskForm({finding_uid:uid,service:'',objective:'',consequence:'',tolerance:'',source:'',assumptions:'',priority:'unassigned',rationale:'',owner:''},context));
      const risksList=card(h('h3',{},w('Decisiones de negocio registradas','Recorded business decisions', "Decisões de negócio registradas")));
      if(!selectedRisks.length)risksList.append(notice('Sin decisiones de negocio registradas para este hallazgo. La prioridad, la tolerancia y la verificación técnica no se deducen de abrir este panel.','No business decisions are recorded for this finding. Priority, tolerance and technical verification are not inferred by opening this panel.', "Nenhuma decisão de negócio registrada para este achado. A prioridade, a tolerância e a verificação técnica não são inferidas ao abrir este painel."));
      paged(risksList,selectedRisks,item=>riskRow(item,riskEditor,context));
      box.append(notice('Una afirmación distingue observación, inferencia e hipótesis. La prioridad de negocio es una decisión documentada, separada de la severidad técnica y CVSS.','A claim distinguishes observation, inference and hypothesis. Business priority is a documented decision, separate from technical severity and CVSS.', "Uma afirmação distingue observação, inferência e hipótese. A prioridade de negócio é uma decisão documentada, separada da severidade técnica e do CVSS."),claimsList,claimEditor,risksList,riskEditor);
      if(typeof PendingUI!=='undefined')for(const handle of PendingUI.active.values())if(handle.slug===slug&&handle.revision&&handle.key.startsWith('insights:')&&handle.read().data.finding_uid===uid)showPending(handle);
    } catch(error) {
      if(!active())return;
      status.remove();box.append(h('p',{role:'alert'},error.message),button('Reintentar','Retry', "Tentar novamente",()=>{box.replaceChildren();return renderFinding(box,uid);},'finding-decisions-retry'));
    }
  }
  function render(el) {
    const tab=names[S.sel.idx]?S.sel.idx:'claims',token=++generation,slug=S.slug;
    const shell=h('section',{class:'insights-shell','data-insights-page':tab,'aria-labelledby':'insightsTitle'});
    shell.append(h('header',{},h('p',{class:'insights-eyebrow'},w('EVIDENCIA · DECISIÓN · ENTREGA','EVIDENCE · DECISION · DELIVERY', "EVIDÊNCIA · DECISÃO · ENTREGA")),h('h1',{id:'insightsTitle',tabindex:'-1'},w('Evidencia y decisiones','Evidence and decisions', "Evidências e decisões")),notice('Conecta evidencia, conclusiones y prioridades. Revisa el contenido y prepara una entrega para cada lector.', 'Connect evidence, conclusions and priorities. Review content and prepare a delivery for each reader.', "Relacione evidências, conclusões e prioridades. Revise o conteúdo e prepare uma entrega para cada leitor.")),h('details',{},h('summary',{},w('Cómo se guardan estas decisiones','How these decisions are saved', "Como estas decisões são salvas")),notice('Abrir estas pantallas no cambia el proyecto. Los formularios editados se protegen en este navegador durante 30 días, sin cifrar, cuando su indicador confirma el guardado local. No se incorporan al informe hasta usar su botón de guardar.','Opening these screens does not change the project. Edited forms are protected in this browser for 30 days, unencrypted, when their indicator confirms local storage. They enter the report only when you press their save button.', "Abrir estas telas não altera o projeto. Os formulários editados são protegidos neste navegador por 30 dias, sem criptografia, quando seu indicador confirma o armazenamento local. Só entram no relatório quando você pressiona seu botão de salvar.")));
    const nav=h('nav',{class:'insights-nav','aria-label':w('Herramientas de revisión','Review tools', "Ferramentas de revisão")});
    for(const [key,labels]of Object.entries(names)){const b=h('button',{type:'button','data-insights-tab':key,'aria-current':tab===key?'page':null},w(...labels));b.addEventListener('click',()=>open(key));nav.append(b);}
    const box=h('div',{'data-insights-content':tab}),status=h('p',{class:'insights-status',role:'status'},w('Leyendo la revisión guardada…','Reading the saved revision…', "Lendo a revisão salva…"));box.append(status);shell.append(nav,box);el.append(shell);
    if(!slug){status.textContent=w('Abre un proyecto para usar estas herramientas.','Open a project to use these tools.', "Abra um projeto para usar estas ferramentas.");return;}
    api.get('/api/projects/'+encodeURIComponent(slug)+'/insights?lang='+encodeURIComponent(S.uiLang)).then(async data=>{
      if(token!==generation||S.slug!==slug||!box.isConnected)return;state=data;currentSlug=slug;status.remove();
      if(projectStore.dirty)box.append(notice('Hay cambios en el borrador. Este mapa muestra lo guardado; una acción explícita guarda antes de continuar.', 'There are draft changes. This map shows saved data; an explicit action saves before continuing.', "Há alterações no rascunho. Este mapa mostra os dados salvos; uma ação explícita salva antes de continuar."));
      box.append(h('details',{},h('summary',{},w('Identidad de la revisión leída','Identity of the reviewed revision', "Identidade da revisão analisada")),h('p',{class:'insights-hash'},'SHA-256: '+data.digest)));
      if(tab==='claims')claims(box);else if(tab==='risk')risk(box);else if(tab==='review')review(box);else if(tab==='audiences')audiences(box);else if(tab==='visual')await visual(box,slug);else await editorial(box,slug);
      if(typeof PendingUI!=='undefined')for(const handle of PendingUI.active.values())if(handle.slug===slug&&handle.revision&&(tab==='claims'?handle.key.startsWith('insights:claim-'):tab==='risk'?handle.key.startsWith('insights:risk-'):tab==='review'?/insights:(comment-|resolve-|review-)/.test(handle.key):tab==='audiences'&&handle.key==='insights:audience-new'))showPending(handle);
    }).catch(error=>{if(box.isConnected&&token===generation){status.remove();box.append(h('p',{role:'alert'},error.message),button('Reintentar','Retry', "Tentar novamente",()=>renderMain(),'retry'));}});
  }
  function entry() {
    if(!S.slug)return h('span',{hidden:''});
    return h('section',{class:'insights-entry'},h('div',{},h('h2',{},w('Conecta tu evidencia con la decisión','Connect evidence to the decision', "Relacione a evidência à decisão")),h('p',{},w('Documenta límites, prioriza con contexto, recibe observaciones y revisa tus entregas.','Document limitations, prioritize with context, receive review comments and inspect your deliverables.', "Documente limitações, priorize com contexto, receba comentários de revisão e inspecione suas entregas."))),button('Evidencia y decisiones','Evidence and decisions', "Evidências e decisões",()=>open(),'open-insights'));
  }
  function bind() {
    if($('#insightsBtn'))return;const b=button('Evidencia y decisiones','Evidence and decisions', "Evidências e decisões",()=>open(),'open-insights');b.id='insightsBtn';
    const utilities=$('.workspace-utilities')||$('.sidebar'),more=$('#studioMore .studio-more-body'),media=matchMedia('(max-width:760px)');
    function place(){const focused=document.activeElement===b,destination=media.matches&&more?more:utilities;if(b.parentElement!==destination)destination.append(b);if(focused){if(media.matches&&more)$('#studioMore').open=true;else if(document.body.classList.contains('focus-mode')){$('#studioMore summary')?.focus({preventScroll:true});return;}b.focus({preventScroll:true});}}
    place();media.addEventListener?.('change',place);update();
  }
  function update() {
    const active=S.sel.type==='insights',b=$('#insightsBtn');$('.layout')?.classList.toggle('workspace-insights',active);
    if(b){b.textContent=w('Evidencia y decisiones','Evidence and decisions', "Evidências e decisões");b.disabled=!S.slug||projectBusyCount>0;b.setAttribute('aria-current',active?'page':'false');b.classList.toggle('active',active);}
    if(active&&$('#workspaceContext'))$('#workspaceContext').textContent=w(...(names[S.sel.idx]||names.claims));
    if(currentSlug!==S.slug)state=null;
  }
  function resetProject(slug){if(restoring?.slug===slug)restoring=null;if(typeof PendingUI!=='undefined')PendingUI.reset(slug);for(const key of pendingSignatures.keys())if(key.startsWith(slug+'|'))pendingSignatures.delete(key);for(const key of drafts.keys())if(key.startsWith(slug+'|'))drafts.delete(key);assistantProposals.delete(slug);if(currentSlug===slug){state=null;currentSlug=null;generation++;}publicationKey=null;publicationRequest=null;}
  return{bind,update,render,renderFinding,entry,open,restorePending,mountAudience:audiences,projectDeleted:resetProject,projectCreated:resetProject};
})();

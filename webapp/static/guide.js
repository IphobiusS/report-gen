/* Optional editorial guide. Reading it never changes a report or its evidence. */
const GuideUI = (() => {
  'use strict';
  const w = (es, en) => S.uiLang === 'en' ? en : es;
  let current = 0;
  const names = [
    ['Empieza', 'Start'], ['Define el alcance', 'Define scope'],
    ['Redacta un hallazgo', 'Write a finding'], ['Conecta la evidencia', 'Connect evidence'],
    ['Revisa lo que compartes', 'Review what you share'], ['Entrega y conserva', 'Deliver and retain']
  ];

  // These are writing suggestions based on recorded fields, never a completion score.
  // Keep the decision function pure so navigation, language and reading the guide cannot edit a report.
  function nextAction(data = S.data, review = null) {
    const text = value => typeof value === 'string' && value.trim().length > 0;
    if (!data) return {key:'start', step:0, type:'start', title:['Empieza con un informe de ejemplo','Start with an example report'],
      description:['Nimbus crea una copia editable con datos ficticios. También puedes crear tu propio proyecto.','Nimbus creates an editable copy with fictional data. You can also create your own project.'], action:['Probar demo Nimbus','Try Nimbus demo']};
    const meta = data.meta || {}, findings = data.findings || [], evidence = data.evidence || [];
    if (!text(meta.report_title) || !text(meta.client)) return {key:'metadata', step:1, type:'report', title:['Identifica el informe','Identify your report'],
      description:['Falta el título o el cliente. Completa estos datos para reconocer el proyecto y su destinatario.','The title or client is missing. Fill them in to identify the project and its recipient.'], action:['Completar datos del informe','Complete report details']};
    const scope = data.report?.sections?.find(section => section.key === 'scope');
    if (scope && !text(scope.objectives)) return {key:'scope', step:1, type:'section', value:'scope', title:['Describe el alcance','Describe the scope'],
      description:['La sección Alcance está activa y sus objetivos están vacíos. Registra qué evalúas y sus límites.','The Scope section is enabled and its objectives are empty. Record what you assess and its boundaries.'], action:['Abrir alcance','Open scope']};
    if (!findings.length) return {key:'finding', step:2, type:'findings', title:['Documenta tu primer resultado','Document your first result'],
      description:['Este proyecto aún no tiene hallazgos. Añade uno si tu evaluación lo justifica; también puedes revisar un informe sin hallazgos.','This project has no findings yet. Add one if your assessment warrants it; you can also review a report with no findings.'], action:['Abrir hallazgos','Open findings']};
    const unfinished = findings.findIndex(f => !text(f.title) || !text(f.mode === 'machine' ? f.summary_md : f.description_md));
    if (unfinished >= 0) return {key:'finding-content', step:2, type:'finding', value:unfinished, title:['Completa el contexto del hallazgo','Complete the finding context'],
      description:['Hay una entrada sin título o descripción. Explica la observación antes de preparar la entrega.','An entry is missing its title or description. Explain the observation before preparing delivery.'], action:['Continuar el hallazgo','Continue the finding']};
    const known = new Set(evidence.map(item => item.uid)), references = findings.flatMap(f => [...(f.evidence_uids || []), ...(f.retests || []).flatMap(item => item.evidence_uids || [])]);
    const missing = references.some(uid => !known.has(uid)), unlinked = evidence.some(item => !references.includes(item.uid));
    if (missing || unlinked) return {key:'evidence-links', step:3, type:'workflow', value:'evidence', title:['Revisa las asociaciones de evidencia','Review evidence links'],
      description:missing ? ['Hay referencias a evidencias que no están en el registro. Revisa sus asociaciones.','Some evidence references are absent from the registry. Review their links.'] : ['Hay evidencias registradas sin asociación a un hallazgo o retest. Vincúlalas si corresponden.','Some registered evidence is not linked to a finding or retest. Link it where appropriate.'], action:['Abrir evidencias','Open evidence']};
    if (review?.current && review.issues === 0) return {key:'delivery', step:5, type:'studio', value:'deliver', title:['Inspecciona y prepara los archivos','Inspect and prepare the files'],
      description:['La última comprobación de esta revisión no detectó avisos. Revisa el texto, las imágenes y los archivos finales antes de entregarlos.','The latest check of this revision found no warnings. Inspect the text, images and final files before delivering them.'], action:['Preparar entrega','Prepare delivery']};
    return {key:'review', step:4, type:'workflow', value:'review', title:[review?.current ? 'Resuelve los avisos de revisión' : 'Revisa lo que vas a compartir', review?.current ? 'Resolve review warnings' : 'Review what you will share'],
      description:review?.current ? [review.issues+' avisos en la última comprobación de esta revisión. Ábrelos para decidir cómo resolverlos.', review.issues+' warnings in the latest check of this revision. Open them to decide how to address them.'] : ['Comprueba campos, referencias y omisiones de la revisión guardada. La validación técnica sigue a tu cargo.','Check fields, references and omissions in the saved revision. Technical validation remains your responsibility.'], action:['Abrir revisión de entrega','Open delivery review']};
  }
  function recommendation() {
    return nextAction(S.data, typeof WorkflowUI !== 'undefined' ? WorkflowUI.reviewSnapshot?.() : null);
  }
  function act(next) {
    if (next.type === 'start') activate('demoBtn');
    else go(next.type, next.value ?? -1);
  }
  function projectState(compact = false) {
    const next = recommendation();
    const panel = h('section', {class:'guide-project-state'+(compact?' compact':''), 'data-first-use-state':next.key, 'aria-label':w('Siguiente acción sugerida','Suggested next action')},
      h('div', {}, h('p', {class:'guide-eyebrow'}, w('SIGUIENTE ACCIÓN SUGERIDA','SUGGESTED NEXT ACTION')), h('h2', {}, w(...next.title)), h('p', {}, w(...next.description))));
    const actions = h('div', {class:'guide-actions'}, button(w(...next.action), () => act(recommendation()), 'suggested-action', true));
    if (!compact) actions.append(button(w('Ver este paso en la guía','View this step in the guide'), () => open(recommendation().step), 'suggested-guide'));
    if (S.data && ['finding','finding-content','evidence-links'].includes(next.key)) actions.append(button(w('Ir a revisión','Go to review'), () => go('workflow','review'), 'review-anyway'));
    panel.append(actions, h('p', {class:'guide-state-note'}, w('Sugerencia de redacción, no aprobación del informe. Puedes ir a cualquier sección.','Writing suggestion, not report approval. You can open any section.')));
    return panel;
  }

  function button(label, action, key, primary = false, project = false) {
    const b = h('button', {type: 'button', class: 'btn' + (primary ? ' primary' : ''), 'data-guide-action': key}, label);
    if (project) b.dataset.guideProject = 'required';
    b.disabled = (project && !S.slug) || projectBusyCount > 0;
    b.addEventListener('click', async () => {
      if (b.disabled) return;
      b.dataset.guideRunning = ''; b.disabled = true;
      try { await action(); } catch (error) { toast(error.message, 'err'); }
      finally { delete b.dataset.guideRunning; update(); }
    });
    return b;
  }
  function closeNavigation() {
    const more = $('#studioMore');
    if (more) more.open = false;
    $('.layout')?.classList.remove('navigation-open');
    $('#sidebarToggle')?.setAttribute('aria-expanded', 'false');
  }
  function go(type, value = -1) {
    closeNavigation();
    select(type, value);
    $('#editor')?.focus({preventScroll: true});
  }
  function activate(id) {
    const target = $('#' + id);
    if (!target || target.disabled) return;
    closeNavigation();
    target.click();
  }
  function reveal(target) {
    if (!target) return;
    const rect = target.getBoundingClientRect(), editor = $('#editor')?.getBoundingClientRect();
    const top = Math.max(0, editor?.top || 0), bottom = Math.min(innerHeight, editor?.bottom || innerHeight);
    if (rect.top < top + 12 || rect.bottom > bottom - 12) {
      target.scrollIntoView({block: 'start', inline: 'nearest', behavior: 'instant'});
    }
  }
  function open(index = current, focusStep = false) {
    current = Number.isInteger(index) && index >= 0 && index < names.length ? index : 0;
    go('guide', current);
    if (focusStep) {
      const heading = $('#guideStepTitle');
      heading?.focus({preventScroll: true});
      reveal(heading);
    } else {
      // On mobile the document, rather than the editor, retains the old scroll.
      // Preserve the editor focus while bringing the new guide into view.
      const intro = $('.guide-intro')?.getBoundingClientRect();
      if (intro && (intro.top < 0 || intro.bottom > innerHeight)) {
        $('#editor')?.scrollIntoView({block: 'start', inline: 'nearest', behavior: 'instant'});
      }
    }
  }
  function note(es, en) { return h('p', {class: 'guide-note'}, w(es, en)); }
  function checklist(items) {
    return h('section', {class: 'guide-checklist'},
      h('h3', {}, w('Antes de seguir', 'Before continuing')),
      h('ul', {}, items.map(pair => h('li', {}, w(...pair)))));
  }
  function example(title, children, caption) {
    return h('figure', {class: 'guide-example'},
      h('div', {class: 'guide-example-label'}, w('EJEMPLO FICTICIO', 'FICTIONAL EXAMPLE')),
      h('div', {class: 'guide-example-body'}, h('h3', {}, title), ...children),
      h('figcaption', {}, caption));
  }
  function exampleRows(rows) {
    return h('dl', {class: 'guide-example-rows'}, rows.map(([label, value]) =>
      h('div', {}, h('dt', {}, label), h('dd', {}, value))));
  }
  function projectActions(...children) {
    const box = h('div', {class: 'guide-actions'}, ...children);
    if (!S.slug) box.append(h('p', {class: 'guide-prerequisite'},
      w('Para usar estas acciones, crea un proyecto, prueba Nimbus o abre un respaldo desde el paso 1. Puedes leer toda la guía sin proyecto.',
        'To use these actions, create a project, try Nimbus or open a backup in step 1. You can read the entire guide without a project.')));
    else if (projectBusyCount > 0) box.append(note('Espera a que termine la operación actual para abrir otra pantalla.', 'Wait for the current operation before opening another screen.'));
    return box;
  }
  function scopeAvailable() {
    return !!S.data?.report?.sections?.some(section => section.key === 'scope');
  }
  function content(index) {
    const box = h('div', {class: 'guide-step-content'});
    if (index === 0) {
      box.append(note('Prueba el recorrido con Nimbus si aún no tienes material. Se crea una copia editable con datos ficticios; tu proyecto actual se guarda primero y no se sustituye.',
        'Try the workflow with Nimbus if you do not have material yet. It creates an editable copy with fictional data; your current project is saved first and is not replaced.'),
      example(w('Elige cómo empezar', 'Choose a starting point'), [h('div', {class: 'guide-choice-grid'},
        h('div', {}, h('strong', {}, 'Nimbus'), h('span', {}, w('Ejemplo editable', 'Editable example'))),
        h('div', {}, h('strong', {}, w('Proyecto nuevo', 'New project')), h('span', {}, w('Tu trabajo y tus datos', 'Your work and data'))),
        h('div', {}, h('strong', {}, w('Respaldo ZIP', 'ZIP backup')), h('span', {}, w('Una copia para continuar', 'A copy to continue'))))],
        w('Leer la guía no crea proyectos. Los botones de abajo realizan la acción que elijas.', 'Reading this guide creates no project. The buttons below perform the action you choose.')),
      checklist([
        ['Distingue un laboratorio de un encargo real y rotula las simulaciones.', 'Distinguish a lab from a real engagement and label simulations.'],
        ['Para un encargo, confirma autorización y reglas de trabajo fuera de la herramienta.', 'For an engagement, confirm authorization and rules of engagement outside the tool.'],
        ['Comprueba la instalación antes de depender de la exportación PDF.', 'Check the installation before relying on PDF export.']
      ]), h('div', {class: 'guide-actions'},
        button(w('Probar Nimbus: crear una copia', 'Try Nimbus: create a copy'), () => activate('demoBtn'), 'demo', true),
        button(w('Crear proyecto', 'Create project'), () => activate('newProjectBtn'), 'new'),
        button(w('Abrir respaldo', 'Open backup'), () => activate('importProjectBtn'), 'import'),
        button(w('Comprobar instalación', 'Check installation'), () => activate('diagnosticsBtn'), 'diagnostics')));
    } else if (index === 1) {
      box.append(note('Identifica al cliente, al evaluador y el periodo de trabajo. Escribe objetivos, activos incluidos, exclusiones y limitaciones antes de resumir resultados.',
        'Identify the client, assessor and assessment period. Write objectives, included assets, exclusions and limitations before summarizing results.'),
      example(w('Un alcance que se puede leer', 'A readable scope'), [exampleRows([
        [w('Objetivo', 'Target'), 'https://portal.example'],
        [w('Incluido', 'Included'), w('Portal web y API de pruebas autorizada', 'Web portal and authorized test API')],
        [w('Excluido', 'Excluded'), w('Producción y pruebas de denegación de servicio', 'Production and denial-of-service tests')],
        [w('Limitación', 'Limitation'), w('Sin acceso al código fuente', 'No access to source code')]
      ])], w('El ejemplo orienta la redacción; no modifica tu alcance ni concede autorización.', 'This example guides your writing; it does not modify scope or grant authorization.')),
      checklist([
        ['Usa Activos para registrar y vincular objetivos a los hallazgos.', 'Use Assets to register targets and link them to findings.'],
        ['En Cobertura, separa las pruebas realizadas de las pendientes o bloqueadas.', 'In Coverage, distinguish performed tests from pending or blocked tests.'],
        ['Si incluyes apetito de riesgo o impacto de negocio, documenta su fuente y supuestos.', 'If you include risk appetite or business impact, document sources and assumptions.']
      ]), projectActions(
        button(w('Abrir metadatos', 'Open metadata'), () => go('report'), 'metadata', true, true),
        ...(scopeAvailable() ? [button(w('Abrir alcance', 'Open scope'), () => go('section', 'scope'), 'scope', false, true)] : []),
        button(w('Abrir activos', 'Open assets'), () => go('workflow', 'assets'), 'assets', false, true),
        button(w('Abrir cobertura', 'Open coverage'), () => go('workflow', 'coverage'), 'coverage', false, true)));
      if (S.slug && !scopeAvailable()) box.append(note('La sección Alcance no está activada en este informe. Puedes añadirla desde «Gestionar secciones»; la guía no la activa por ti.',
        'The Scope section is not enabled in this report. You can add it under “Manage sections”; the guide does not enable it for you.'));
    } else if (index === 2) {
      box.append(note('Cuenta qué control falló, cómo lo comprobaste y qué resultado observaste. La severidad técnica y el riesgo para el negocio necesitan argumentos distintos.',
        'Explain the failed control, how you tested it and what you observed. Technical severity and business risk require different reasoning.'),
      example(w('De observación a hallazgo', 'From observation to finding'), [
        h('div', {class: 'guide-finding-preview'}, h('span', {class: 'guide-example-id'}, 'F1'), h('strong', {}, w('Lectura de un registro de otra cuenta', 'Reading another account’s record'))),
        exampleRows([
          [w('Observación', 'Observation'), w('Una cuenta de pruebas recibe un registro ajeno al cambiar el identificador.', 'A test account receives another account’s record after changing its identifier.')],
          [w('Causa', 'Cause'), w('Falta el control de autorización por objeto.', 'Object-level authorization is missing.')],
          [w('Severidad técnica', 'Technical severity'), w('Justifica las métricas del vector CVSS elegido.', 'Justify the metrics in your chosen CVSS vector.')],
          [w('Riesgo de negocio', 'Business risk'), w('Redacta impacto, exposición y supuestos con contexto del cliente.', 'Describe impact, exposure and assumptions using client context.')]
        ])], w('Es una muestra de redacción, no un resultado de pruebas ni una puntuación calculada.', 'This is a writing sample, not a test result or a calculated score.')),
      checklist([
        ['Incluye procedimiento, resultado observado, impacto demostrado y remediación comprobable.', 'Include procedure, observed result, demonstrated impact and verifiable remediation.'],
        ['CVSS 3.1 o 4.0 expresa severidad técnica; no calcula por sí solo pérdidas o apetito de riesgo.', 'CVSS 3.1 or 4.0 expresses technical severity; it does not calculate losses or risk appetite by itself.'],
        ['Una plantilla o importación ahorra redacción, pero debes verificarla y adaptarla a tu evidencia.', 'A template or import saves writing time, but you must verify it and adapt it to your evidence.']
      ]), projectActions(
        button(w('Abrir hallazgos', 'Open findings'), () => go('findings'), 'findings', true, true),
        button(w('Añadir hallazgo en blanco', 'Add blank finding'), () => { closeNavigation(); $('[data-add="blank"]')?.click(); $('#editor')?.focus({preventScroll: true}); }, 'add-finding', false, true)));
    } else if (index === 3) {
      box.append(note('Una imagen suelta no demuestra todo el hallazgo. Añade un pie claro, vincúlala al hallazgo y conserva el procedimiento como texto reproducible.',
        'An image alone does not demonstrate an entire finding. Add a clear caption, link it to the finding and retain the procedure as reproducible text.'),
      example(w('La evidencia tiene contexto', 'Evidence has context'), [
        h('div', {class: 'guide-evidence-preview'}, h('div', {class: 'guide-evidence-document'},
          h('span', {class: 'guide-example-id'}, 'EV-01'), h('strong', {}, w('Respuesta de prueba', 'Test response')),
          h('code', {}, 'GET /records/42 → 200'), h('span', {}, w('Datos sensibles censurados', 'Sensitive data redacted'))),
        h('div', {class: 'guide-evidence-link'}, h('span', {}, w('Vinculada a', 'Linked to')), h('strong', {}, 'F1'))),
        h('p', {class: 'guide-example-caption'}, w('Pie: la cuenta A recibe el registro de B en el entorno autorizado de pruebas.', 'Caption: account A receives account B’s record in the authorized test environment.'))
      ], w('La muestra es texto sintético; no es una captura real ni una petición ejecutada.', 'This is synthetic text, not a real screenshot or an executed request.')),
      checklist([
        ['En Evidencias: sube la imagen, escribe el pie y marca «Usada en hallazgos».', 'In Evidence: upload the image, write the caption and select “Used in findings”.'],
        ['Censura píxeles con «Anotar / censurar» y revisa la copia procesada antes de publicar.', 'Redact pixels under “Annotate / redact” and review the processed copy before publication.'],
        ['La Captura rápida queda en la bandeja privada hasta que la incorpores a un hallazgo.', 'Quick capture stays in the private inbox until you add it to a finding.']
      ]), projectActions(
        button(w('Abrir evidencias', 'Open evidence'), () => go('workflow', 'evidence'), 'evidence', true, true),
        button(w('Abrir bandeja de captura', 'Open capture inbox'), () => go('capture'), 'capture', false, true)));
    } else if (index === 4) {
      box.append(note('Primero revisa las omisiones del informe. Después inspecciona el texto y las imágenes que saldrán del proyecto. Lee cada aviso: la herramienta no valida por ti el pentest.',
        'First review report omissions. Then inspect the text and images leaving the project. Read each warning: the tool does not validate the pentest for you.'),
      example(w('Dos revisiones diferentes', 'Two different reviews'), [h('div', {class: 'guide-review-grid'},
        h('div', {}, h('strong', {}, w('Revisión de entrega', 'Delivery review')), h('p', {}, w('Campos, referencias y omisiones', 'Fields, references and omissions'))),
        h('div', {}, h('strong', {}, w('Inspector de publicación', 'Publication inspector')), h('p', {}, w('Texto de salida, imágenes y posibles secretos', 'Outgoing text, images and possible secrets'))))],
        w('Sin avisos no significa «sin vulnerabilidades» ni «listo sin revisión humana».', 'No warnings does not mean “no vulnerabilities” or “ready without human review”.')),
      checklist([
        ['Contrasta afirmaciones y referencias con tu evidencia y tu alcance.', 'Check claims and references against evidence and scope.'],
        ['Revisa también lo que aparece dentro de las imágenes: no hay OCR automático.', 'Also review text inside images: there is no automatic OCR.'],
        ['Las excepciones de publicación deben ser decisiones conscientes, no una forma de ocultar un aviso.', 'Publication exceptions must be deliberate decisions, not a way to conceal a warning.']
      ]), projectActions(
        button(w('Abrir revisión de entrega', 'Open delivery review'), () => go('workflow', 'review'), 'review', true, true),
        button(w('Abrir inspector de publicación', 'Open publication inspector'), () => { closeNavigation(); return StudioUI.inspector(); }, 'inspector', false, true)));
    } else {
      box.append(note('Prepara los formatos desde una revisión guardada, descarga el resultado y ábrelo antes de entregarlo. Conserva el proyecto editable por separado para seguir trabajando y registrar el retest.',
        'Prepare formats from a saved revision, download the result and open it before delivery. Keep the editable project separately to continue work and record retests.'),
      example(w('Cada archivo tiene un destinatario', 'Each file has a recipient'), [h('div', {class: 'guide-delivery-grid'},
        h('div', {}, h('strong', {}, w('Entrega', 'Deliverable')), h('span', {}, 'PDF · DOCX · HTML · Markdown'), h('p', {}, w('Informe y comprobaciones de exportación', 'Report and export checks'))),
        h('div', {}, h('strong', {}, w('Respaldo privado', 'Private backup')), h('span', {}, w('ZIP de proyecto', 'Project ZIP')), h('p', {}, w('Editable, originales e historial', 'Editable data, originals and history'))))],
        w('El HTML autónomo contiene todo el informe aunque uses filtros. Un filtro no elimina información.', 'Standalone HTML contains the whole report even when filtered. A filter does not remove information.')),
      checklist([
        ['Abre los archivos: revisa saltos de página, imágenes, índice y enlaces. Las comprobaciones automáticas no sustituyen esta lectura.', 'Open the files: review page breaks, images, contents and links. Automatic checks do not replace this review.'],
        ['Guarda el respaldo como información confidencial; no lo incluyas por defecto en la entrega al cliente.', 'Store the backup as confidential information; do not include it in the client delivery by default.'],
        ['Registra un retest con fecha, procedimiento y evidencia. «Corrección comunicada» no equivale a «corregido y verificado».', 'Record a retest with date, procedure and evidence. “Reported fixed” is distinct from “verified fixed”.']
      ]), projectActions(
        button(w('Abrir pantalla de entrega', 'Open delivery screen'), () => go('studio', 'deliver'), 'delivery-screen', true, true),
        button(w('Preparar entrega: elegir formatos', 'Prepare delivery: choose formats'), () => activate('deliveryBtn'), 'delivery', false, true),
        button(w('Abrir respaldo del proyecto', 'Open project backup'), () => go('workflow', 'backup'), 'backup', false, true),
        button(w('Abrir correcciones y retest', 'Open remediation and retest'), () => go('workflow', 'retest'), 'retest', false, true)));
    }
    return box;
  }
  function seniorHelp() {
    const details = h('details', {class: 'guide-senior'}, h('summary', {}, w('Si ya haces informes: límites y atajos', 'Already writing reports? Boundaries and shortcuts')));
    const rows = [
      ['Guardado y borrador', 'Save and draft', 'Comprueba el estado de guardado. Un borrador recuperable del navegador no equivale a una revisión guardada en disco; las entregas usan esta última.', 'Check the save state. A recoverable browser draft is distinct from a saved disk revision; deliveries use the latter.'],
      ['Revisión y criterio técnico', 'Review and technical judgment', 'Los avisos detectan omisiones y coherencia. La validación del hallazgo, el riesgo de negocio y la aceptación del riesgo corresponden al evaluador y al cliente.', 'Warnings detect omissions and consistency issues. Finding validation, business risk and risk acceptance remain with the assessor and client.'],
      ['PDF y Word', 'PDF and Word', 'Comprueba instalación y abre el archivo final. La vista HTML del editor no reproduce todos los saltos de página del PDF o Word.', 'Check installation and open the final file. The editor’s HTML preview does not reproduce every PDF or Word page break.'],
      ['Originales y respaldos', 'Originals and backups', 'La copia censurada no sustituye el original privado. Los respaldos incluyen originales e historial; el borrador JSON de emergencia no es un respaldo integral de evidencias.', 'A redacted copy does not replace the private original. Backups include originals and history; an emergency JSON draft is not a complete evidence backup.'],
      ['Texto dentro de imágenes', 'Text inside images', 'El inspector ofrece OCR local opcional con Tesseract (eng), por imagen y bajo tu acción. Puede omitir datos sensibles; no censura automáticamente. Revisa capturas, adjuntos y formatos finales.', 'The inspector offers optional local Tesseract OCR (eng), per image and only on your action. It may miss sensitive data and never redacts automatically. Review screenshots, attachments and final formats.']
    ];
    details.append(h('dl', {}, rows.map(([es, en, bodyEs, bodyEn]) => h('div', {}, h('dt', {}, w(es, en)), h('dd', {}, w(bodyEs, bodyEn))))));
    return details;
  }
  function render(el) {
    if (S.sel.type === 'guide' && Number.isInteger(S.sel.idx) && S.sel.idx >= 0 && S.sel.idx < names.length) current = S.sel.idx;
    const shell = h('section', {class: 'guide-shell', 'data-guide-page': '', 'aria-labelledby': 'guideTitle'});
    shell.append(h('header', {class: 'guide-intro'}, h('p', {class: 'guide-eyebrow'}, w('GUÍA DE TRABAJO', 'WORKFLOW GUIDE')),
      h('h1', {id: 'guideTitle'}, w('Tu primer informe, paso a paso.', 'Your first report, step by step.')),
      h('p', {}, w('Un recorrido opcional para convertir tu trabajo en una entrega clara. Puedes volver a cualquier paso sin cambiar el informe.',
        'An optional path from assessment work to a clear deliverable. You can revisit any step without changing the report.')),
      h('ol', {class: 'guide-flow', 'aria-label': w('De la evidencia a la entrega', 'From evidence to delivery')},
        ['Evidencia|Evidence', 'Hallazgo|Finding', 'Revisión|Review', 'Entrega|Delivery'].map(pair => h('li', {}, w(...pair.split('|')))))));
    if (S.data) shell.append(projectState(true));
    const navigation = h('nav', {class: 'guide-navigation', 'aria-label': w('Pasos de la guía', 'Guide steps')},
      h('ol', {'data-guide-nav': ''}, names.map((pair, index) => {
        const b = h('button', {type: 'button', 'data-guide-step': index, 'aria-current': current === index ? 'step' : null},
          h('span', {class: 'guide-step-number', 'aria-hidden': 'true'}, String(index + 1).padStart(2, '0')), h('span', {}, w(...pair)));
        b.addEventListener('click', () => open(index, true));
        return h('li', {}, b);
      })));
    const stage = h('section', {class: 'guide-stage', 'data-guide-current': current, 'aria-labelledby': 'guideStepTitle'},
      h('p', {class: 'guide-position'}, w('Paso ', 'Step ') + (current + 1) + w(' de 6 · recorrido de la guía, no avance del proyecto', ' of 6 · guide position, not project progress')),
      h('h2', {id: 'guideStepTitle', tabindex: '-1'}, w(...names[current])), content(current));
    const previous = button(w('Paso anterior', 'Previous step'), () => open(current - 1, true), 'previous');
    previous.id = 'guidePrev'; previous.disabled = current === 0;
    const next = button(w('Siguiente paso', 'Next step'), () => open(current + 1, true), 'next', true);
    next.id = 'guideNext'; next.disabled = current === names.length - 1;
    stage.append(h('footer', {class: 'guide-footer'}, previous, next,
      button(S.slug ? w('Volver al inicio del proyecto', 'Back to project overview') : w('Volver al inicio', 'Back to overview'), () => go('home'), 'home')));
    shell.append(h('div', {class: 'guide-layout'}, navigation, stage), seniorHelp());
    el.append(shell);
  }
  function entry() {
    if (S.data) return projectState();
    return h('section', {class: 'guide-entry', 'aria-labelledby': 'guideEntryTitle'},
      h('div', {}, h('p', {class: 'guide-eyebrow'}, w('6 PASOS · A TU RITMO', '6 STEPS · AT YOUR PACE')),
        h('h2', {id: 'guideEntryTitle'}, w('¿Es tu primer informe aquí?', 'Your first report here?')),
        h('p', {}, w('Alcance, hallazgos, evidencias, revisión y entrega. Una guía visual que puedes abrir cuando la necesites.',
          'Scope, findings, evidence, review and delivery. A visual guide you can open whenever you need it.'))),
      button(w('Abrir guía visual', 'Open visual guide'), () => open(), 'open-guide'));
  }
  function bind() {
    if ($('#guideBtn')) return;
    const b = button(w('Guía: primer informe', 'Guide: first report'), () => open(), 'open-guide');
    b.id = 'guideBtn';
    const utilities = $('.workspace-utilities') || $('.sidebar');
    const more = $('#studioMore .studio-more-body');
    const mobile = window.matchMedia('(max-width:760px)');
    const place = () => {
      const focused = document.activeElement === b;
      const destination = mobile.matches && more ? more : utilities;
      if (b.parentElement !== destination) destination.append(b);
      if (focused) {
        if (mobile.matches && more) $('#studioMore').open = true;
        else if (document.body.classList.contains('focus-mode')) {
          // Keep a focused help control reachable when the sidebar is hidden.
          $('#studioMore')?.querySelector('summary')?.focus({preventScroll: true});
          return;
        }
        b.focus({preventScroll: true});
      }
    };
    place();
    mobile.addEventListener?.('change', place);
    secondaryNavigation();
    update();
  }
  function secondaryNavigation() {
    const groups = [
      ['workspaceResearch', ['Registro y cobertura','Capture and coverage'], ['#navCaptures','[data-workflow="assets"]','[data-workflow="coverage"]']],
      ['workspaceFollowup', ['Historial y seguimiento','History and follow-up'], ['[data-workflow="history"]','[data-workflow="retest"]','[data-workflow="retest_diff"]','[data-workflow="retest_matrix"]']]
    ];
    for (const [id, title, selectors] of groups) {
      const controls = selectors.map(selector => $(selector)).filter(Boolean);
      if (!controls.length || $('#'+id)) continue;
      const details = h('details', {id, class:'workspace-secondary'}, h('summary', {}, w(...title)));
      controls[0].before(details);
      details.append(...controls);
    }
  }
  function update() {
    document.querySelectorAll('[data-guide-action]').forEach(control => {
      const key = control.dataset.guideAction;
      control.disabled = projectBusyCount > 0 || control.hasAttribute('data-guide-running') ||
        (control.dataset.guideProject === 'required' && !S.slug) ||
        (key === 'previous' && current === 0) || (key === 'next' && current === names.length - 1);
    });
    const active = S.sel.type === 'guide';
    const b = $('#guideBtn');
    if (b) {
      b.textContent = w('Guía: primer informe', 'Guide: first report');
      b.classList.toggle('active', active);
      b.setAttribute('aria-current', active ? 'page' : 'false');
      b.disabled = projectBusyCount > 0;
    }
    $('.layout')?.classList.toggle('workspace-guide', active);
    if (active && $('#workspaceContext')) $('#workspaceContext').textContent = w('Guía: primer informe', 'Guide: first report');
    for (const [id, pair] of [['workspaceResearch',['Registro y cobertura','Capture and coverage']],['workspaceFollowup',['Historial y seguimiento','History and follow-up']]]) {
      const details = $('#'+id);
      if (details) details.querySelector('summary').textContent = w(...pair);
    }
    const selected = S.sel.type === 'workflow' ? $('[data-workflow="'+S.sel.idx+'"]') : S.sel.type === 'capture' ? $('#navCaptures') : null;
    const group = selected?.closest('.workspace-secondary');
    if (group) group.open = true;
  }
  return {render, bind, update, entry, nextAction};
})();

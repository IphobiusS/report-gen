/* Optional editorial guide. Reading it never changes a report or its evidence. */
const GuideUI = (() => {
  'use strict';
  const w = (es, en, pt) => uiText(es, en, pt);
  let current = 0;
  const names = [
    ['Empieza', 'Start', "Comece"], ['Define el alcance', 'Define scope', "Defina o escopo"],
    ['Redacta un hallazgo', 'Write a finding', "Redija um achado"], ['Conecta la evidencia', 'Connect evidence', "Conecte as evidências"],
    ['Revisa lo que compartes', 'Review what you share', "Revise o que compartilha"], ['Entrega y conserva', 'Deliver and retain', "Entregue e preserve"]
  ];
  const tutorialKey = 'rg.visualTutorial.v1';
  let tutorialState = null, tutorialStorage = true;
  function progress() {
    if (tutorialState) return tutorialState;
    tutorialState = {version:1, dismissed:false, completed:false, step:0, visited:[]};
    try {
      const saved = JSON.parse(localStorage.getItem(tutorialKey) || 'null');
      if (saved?.version === 1 && Number.isInteger(saved.step) && saved.step >= 0 && saved.step < names.length) {
        tutorialState = {version:1, dismissed:saved.dismissed === true, completed:saved.completed === true, step:saved.step,
          visited:Array.isArray(saved.visited) ? [...new Set(saved.visited.filter(index => Number.isInteger(index) && index >= 0 && index < names.length))] : []};
      }
    } catch (_) { tutorialStorage = false; }
    return tutorialState;
  }
  function remember(changes) {
    tutorialState = {...progress(), ...changes};
    try { localStorage.setItem(tutorialKey, JSON.stringify(tutorialState)); tutorialStorage = true; }
    catch (_) { tutorialStorage = false; }
  }
  const screens = [
    {key:'gallery', title:['Elige una plantilla','Choose a template', "Escolha um modelo"], route:['Más → Nuevo proyecto → galería','More → New project → gallery', "Mais → Novo projeto → galeria"],
      caption:['Filtra por tipo de informe, compara una página equivalente y elige «Continuar con esta plantilla». Revisa los datos antes de crear.','Filter by report type, compare the same page and choose “Continue with this design”. Review the details before creating.', "Filtre por tipo de relatório, compare a mesma página e escolha “Continuar com este modelo”. Revise os dados antes de criar."]},
    {key:'metadata', title:['Identifica el proyecto','Identify the project', "Identifique o projeto"], route:['Proyecto → Informe','Project → Report', "Projeto → Relatório"],
      caption:['Completa título, cliente, evaluador y periodo. El idioma del informe se elige aquí; ES/EN/PT en Preferencias solo cambia la interfaz.','Complete title, client, assessor and dates. Choose the report language here; ES/EN/PT in Preferences changes only the interface.', "Preencha título, cliente, avaliador e datas. Escolha aqui o idioma do relatório; o seletor ES/EN/PT em Preferências altera somente a interface."]},
    {key:'finding', title:['Documenta el resultado','Document the result', "Documente o resultado"], route:['Contenido → Lista de hallazgos → selecciona un hallazgo','Content → Finding list → select a finding', "Conteúdo → Lista de achados → selecione um achado"],
      caption:['Usa las pestañas para separar contexto, procedimiento, evidencia y corrección. Mantén pendiente lo que todavía no has verificado.','Use the tabs to separate context, procedure, evidence and remediation. Keep unverified results pending.', "Use as abas para separar contexto, procedimento, evidências e correção. Mantenha como pendentes os resultados ainda não verificados."]},
    {key:'evidence', title:['Vincula las evidencias','Link the evidence', "Vincule as evidências"], route:['Evidencia y alcance → Evidencias','Evidence and scope → Evidence', "Evidências e escopo → Evidências"],
      caption:['Sube la imagen, escribe el pie y vincúlala a sus hallazgos. «Anotar / censurar» prepara la copia publicada; el original sigue siendo privado.','Upload the image, write its caption and link it to findings. “Annotate / redact” prepares the published copy; the original remains private.', "Envie a imagem, escreva a legenda e vincule-a aos achados. “Anotar / ocultar dados” prepara a cópia publicada; o original permanece privado."]},
    {key:'privacy', title:['Inspecciona antes de compartir','Inspect before sharing', "Inspecione antes de compartilhar"], route:['Entregar → Abrir inspector','Deliver → Open inspector', "Entregar → Abrir inspetor"],
      caption:['Lee los avisos y comprueba texto e imágenes. La censura y las excepciones solo se aplican cuando tú las eliges.','Read warnings and inspect text and images. Redactions and exceptions are applied only when you choose them.', "Leia os avisos e confira o texto e as imagens. As censuras e exceções só são aplicadas quando você as escolhe."]},
    {key:'delivery', title:['Revisa y exporta','Review and export', "Revise e exporte"], route:['Entregar → Elegir formatos','Deliver → Choose formats', "Entregar → Escolher formatos"],
      caption:['Guarda la revisión, elige PDF, DOCX, HTML o Markdown y descarga los archivos preparados. Abre cada resultado para comprobar su formato.','Save the revision, choose PDF, DOCX, HTML or Markdown and download the prepared files. Open each result to inspect its layout.', "Salve a revisão, escolha PDF, DOCX, HTML ou Markdown e baixe os arquivos preparados. Abra cada resultado para inspecionar sua diagramação."]},
    {key:'backup', title:['Conserva el proyecto editable','Keep the editable project', "Preserve o projeto editável"], route:['Entrega → Respaldo del proyecto','Delivery → Project backup', "Entrega → Backup do projeto"],
      caption:['El ZIP incluye el proyecto, imágenes, originales e historial. Guárdalo como información privada, separado de los informes destinados al cliente.','The ZIP contains the project, images, originals and history. Store it privately, separately from reports intended for the client.', "O ZIP contém o projeto, as imagens, os originais e o histórico. Guarde-o de forma privada, separado dos relatórios destinados ao cliente."]}
  ];
  function screenshot(spec) {
    const language = normalizeUiLanguage(S.uiLang);
    const source = '/static/tutorial/' + spec.key + '-' + language + '.webp';
    const dimensions = {gallery:[1320,1016], metadata:[1200,948], finding:[1200,948], evidence:[1200,948], privacy:[1000,972], delivery:[780,972], backup:[1136,203]};
    const [width,height] = dimensions[spec.key];
    const image = h('img', {src:source, width, height, loading:'lazy', decoding:'async', alt:w(...spec.title) + '. ' + w(...spec.caption)});
    const view = h('button', {type:'button', class:'tutorial-screenshot-button', 'data-tutorial-image':spec.key,
      'aria-label':w('Ampliar captura: ','Enlarge screenshot: ', "Ampliar captura: ") + w(...spec.title)}, image,
      h('span', {class:'tutorial-enlarge'}, w('Ampliar captura','Enlarge screenshot', "Ampliar captura")));
    view.addEventListener('click', () => imageDialog(source, spec, view));
    image.addEventListener('error', () => {
      const unavailable = w('Captura no disponible. Las instrucciones siguen debajo.','Screenshot unavailable. The instructions remain below.', "Captura indisponível. As instruções continuam abaixo.");
      view.replaceChildren(h('p', {}, unavailable));
      view.setAttribute('aria-label', unavailable);
      view.disabled = true;
    }, {once:true});
    return h('figure', {class:'tutorial-screenshot'},
      h('div', {class:'tutorial-screen-heading'}, h('span', {}, w('CAPTURA REAL · DATOS FICTICIOS','REAL SCREENSHOT · FICTIONAL DATA', "CAPTURA REAL · DADOS FICTÍCIOS")), h('strong', {}, w(...spec.route))),
      view, h('figcaption', {}, w(...spec.caption)));
  }
  function imageDialog(source, spec, opener) {
    const title = w(...spec.title), dialog = h('dialog', {class:'tutorial-image-dialog', 'aria-labelledby':'tutorialImageTitle'});
    const region = h('div', {class:'tutorial-image-region', 'data-tutorial-image-region':'', role:'region', tabindex:'0',
      'aria-label':w('Captura ampliada. Usa las flechas para desplazarte en tamaño real.','Enlarged screenshot. Use arrow keys to scroll at actual size.', "Captura ampliada. Use as setas para rolar em tamanho real.")},
      h('img', {src:source, alt:title + '. ' + w(...spec.caption)}));
    let actual = false;
    const scale = h('button', {type:'button', class:'btn', 'data-tutorial-scale':'', 'aria-pressed':'false'}, w('Tamaño real','Actual size', "Tamanho real"));
    scale.addEventListener('click', () => {actual = !actual; region.classList.toggle('actual-size', actual); scale.setAttribute('aria-pressed', String(actual)); scale.textContent = actual ? w('Ajustar a la ventana','Fit to window', "Ajustar à janela") : w('Tamaño real','Actual size', "Tamanho real");});
    const close = h('button', {type:'button', class:'btn', 'data-tutorial-close':'', autofocus:''}, w('Cerrar','Close', "Fechar"));
    close.addEventListener('click', () => dialog.close());
    dialog.append(h('header', {class:'tutorial-image-heading'}, h('h2', {id:'tutorialImageTitle'}, title), h('div', {}, scale, close)),
      region, h('p', {class:'tutorial-image-caption'}, w(...spec.caption)));
    dialog.addEventListener('close', () => {dialog.remove(); const target = opener.isConnected ? opener : $('#editor'); target?.focus({preventScroll:true});});
    document.body.append(dialog); dialog.showModal();
  }

  // These are writing suggestions based on recorded fields, never a completion score.
  // Keep the decision function pure so navigation, language and reading the guide cannot edit a report.
  function nextAction(data = S.data, review = null) {
    const text = value => typeof value === 'string' && value.trim().length > 0;
    if (!data) return {key:'start', step:0, type:'start', title:['Empieza con un informe de ejemplo','Start with an example report', "Comece com um relatório de exemplo"],
      description:['Nimbus crea una copia editable con datos ficticios. También puedes crear tu propio proyecto.','Nimbus creates an editable copy with fictional data. You can also create your own project.', "O Nimbus cria uma cópia editável com dados fictícios. Você também pode criar seu próprio projeto."], action:['Probar demo Nimbus','Try Nimbus demo', "Experimentar demonstração Nimbus"]};
    const meta = data.meta || {}, findings = data.findings || [], evidence = data.evidence || [];
    if (!text(meta.report_title) || !text(meta.client)) return {key:'metadata', step:1, type:'report', title:['Identifica el informe','Identify your report', "Identifique seu relatório"],
      description:['Falta el título o el cliente. Completa estos datos para reconocer el proyecto y su destinatario.','The title or client is missing. Fill them in to identify the project and its recipient.', "Falta o título ou o cliente. Preencha esses dados para identificar o projeto e seu destinatário."], action:['Completar datos del informe','Complete report details', "Completar dados do relatório"]};
    const scope = data.report?.sections?.find(section => section.key === 'scope');
    if (scope && !text(scope.objectives)) return {key:'scope', step:1, type:'section', value:'scope', title:['Describe el alcance','Describe the scope', "Descreva o escopo"],
      description:['La sección Alcance está activa y sus objetivos están vacíos. Registra qué evalúas y sus límites.','The Scope section is enabled and its objectives are empty. Record what you assess and its boundaries.', "A seção Escopo está ativa e seus objetivos estão vazios. Registre o que você avalia e seus limites."], action:['Abrir alcance','Open scope', "Abrir escopo"]};
    if (!findings.length) return {key:'finding', step:2, type:'findings', title:['Documenta tu primer resultado','Document your first result', "Documente seu primeiro resultado"],
      description:['Este proyecto aún no tiene hallazgos. Añade uno si tu evaluación lo justifica; también puedes revisar un informe sin hallazgos.','This project has no findings yet. Add one if your assessment warrants it; you can also review a report with no findings.', "Este projeto ainda não tem achados. Adicione um se a avaliação justificar; você também pode revisar um relatório sem achados."], action:['Abrir hallazgos','Open findings', "Abrir achados"]};
    const unfinished = findings.findIndex(f => !text(f.title) || !text(f.mode === 'machine' ? f.summary_md : f.description_md));
    if (unfinished >= 0) return {key:'finding-content', step:2, type:'finding', value:unfinished, title:['Completa el contexto del hallazgo','Complete the finding context', "Complete o contexto do achado"],
      description:['Hay una entrada sin título o descripción. Explica la observación antes de preparar la entrega.','An entry is missing its title or description. Explain the observation before preparing delivery.', "Há um registro sem título ou descrição. Explique a observação antes de preparar a entrega."], action:['Continuar el hallazgo','Continue the finding', "Continuar o achado"]};
    const known = new Set(evidence.map(item => item.uid)), references = findings.flatMap(f => [...(f.evidence_uids || []), ...(f.retests || []).flatMap(item => item.evidence_uids || [])]);
    const missing = references.some(uid => !known.has(uid)), unlinked = evidence.some(item => !references.includes(item.uid));
    if (missing || unlinked) return {key:'evidence-links', step:3, type:'workflow', value:'evidence', title:['Revisa las asociaciones de evidencia','Review evidence links', "Revise os vínculos das evidências"],
      description:missing ? ['Hay referencias a evidencias que no están en el registro. Revisa sus asociaciones.','Some evidence references are absent from the registry. Review their links.', "Há referências a evidências ausentes do registro. Revise seus vínculos."] : ['Hay evidencias registradas sin asociación a un hallazgo o retest. Vincúlalas si corresponden.','Some registered evidence is not linked to a finding or retest. Link it where appropriate.', "Há evidências registradas sem vínculo com um achado ou reteste. Vincule-as quando apropriado."], action:['Abrir evidencias','Open evidence', "Abrir evidências"]};
    if (review?.current && review.issues === 0) return {key:'delivery', step:5, type:'studio', value:'deliver', title:['Inspecciona y prepara los archivos','Inspect and prepare the files', "Inspecione e prepare os arquivos"],
      description:['La última comprobación de esta revisión no detectó avisos. Revisa el texto, las imágenes y los archivos finales antes de entregarlos.','The latest check of this revision found no warnings. Inspect the text, images and final files before delivering them.', "A última verificação desta revisão não encontrou avisos. Inspecione o texto, as imagens e os arquivos finais antes da entrega."], action:['Preparar entrega','Prepare delivery', "Preparar entrega"]};
    return {key:'review', step:4, type:'workflow', value:'review', title:[review?.current ? 'Resuelve los avisos de revisión' : 'Revisa lo que vas a compartir', review?.current ? 'Resolve review warnings' : 'Review what you will share', review?.current ? 'Resolva os avisos da revisão' : 'Revise o que vai compartilhar'],
      description:review?.current ? [review.issues+' avisos en la última comprobación de esta revisión. Ábrelos para decidir cómo resolverlos.', review.issues+' warnings in the latest check of this revision. Open them to decide how to address them.', review.issues+' avisos na última verificação desta revisão. Abra-os para decidir como resolvê-los.'] : ['Comprueba campos, referencias y omisiones de la revisión guardada. La validación técnica sigue a tu cargo.','Check fields, references and omissions in the saved revision. Technical validation remains your responsibility.', "Verifique campos, referências e omissões na revisão salva. A validação técnica continua sob sua responsabilidade."], action:['Abrir revisión de entrega','Open delivery review', "Abrir revisão de entrega"]};
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
    const panel = h('section', {class:'guide-project-state'+(compact?' compact':''), 'data-first-use-state':next.key, 'aria-label':w('Siguiente acción sugerida','Suggested next action', "Próxima ação sugerida")},
      h('div', {}, h('p', {class:'guide-eyebrow'}, w('SIGUIENTE ACCIÓN SUGERIDA','SUGGESTED NEXT ACTION', "PRÓXIMA AÇÃO SUGERIDA")), h('h2', {}, w(...next.title)), h('p', {}, w(...next.description))));
    const actions = h('div', {class:'guide-actions'}, button(w(...next.action), () => act(recommendation()), 'suggested-action', true));
    if (!compact) actions.append(button(w('Ver este paso en la guía','View this step in the guide', "Ver esta etapa no guia"), () => open(recommendation().step), 'suggested-guide'));
    if (S.data && ['finding','finding-content','evidence-links'].includes(next.key)) actions.append(button(w('Ir a revisión','Go to review', "Ir para a revisão"), () => go('workflow','review'), 'review-anyway'));
    panel.append(actions, h('p', {class:'guide-state-note'}, w('Sugerencia de redacción, no aprobación del informe. Puedes ir a cualquier sección.','Writing suggestion, not report approval. You can open any section.', "Sugestão de redação, não aprovação do relatório. Você pode abrir qualquer seção.")));
    return panel;
  }

  function button(label, action, key, primary = false, project = false) {
    const b = h('button', {type: 'button', class: 'btn' + (primary ? ' primary' : ''), 'data-guide-action': key}, label);
    if (project) b.dataset.guideProject = 'required';
    b.disabled = (project && !S.slug) || projectBusyCount > 0;
    b.addEventListener('click', async () => {
      if (b.disabled) return;
      b.dataset.guideRunning = ''; b.disabled = true;
      try { await action(b); } catch (error) { toast(error.message, 'err'); }
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
  function activate(id, opener = null) {
    const target = $('#' + id);
    if (!target || target.disabled) return;
    closeNavigation();
    // The gallery must return focus to the visible tutorial action, rather
    // than the hidden menu button used by the legacy click proxy.
    if (id === 'newProjectBtn' && opener) return DesignLibraryUI.newProject(opener);
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
  function open(index = progress().step, focusStep = false) {
    current = Number.isInteger(index) && index >= 0 && index < names.length ? index : 0;
    remember({dismissed:true, step:current, visited:[...new Set([...progress().visited, current])]});
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
  function note(es, en, pt) { return h('p', {class: 'guide-note'}, w(es, en, pt)); }
  function checklist(items) {
    return h('section', {class: 'guide-checklist'},
      h('h3', {}, w('Antes de seguir', 'Before continuing', "Antes de continuar")),
      h('ul', {}, items.map(pair => h('li', {}, w(...pair)))));
  }
  function example(title, children, caption) {
    return h('figure', {class: 'guide-example'},
      h('div', {class: 'guide-example-label'}, w('EJEMPLO FICTICIO', 'FICTIONAL EXAMPLE', "EXEMPLO FICTÍCIO")),
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
        'To use these actions, create a project, try Nimbus or open a backup in step 1. You can read the entire guide without a project.', "Para usar estas ações, crie um projeto, experimente o Nimbus ou abra um backup na etapa 1. Você pode ler todo o guia sem um projeto.")));
    else if (projectBusyCount > 0) box.append(note('Espera a que termine la operación actual para abrir otra pantalla.', 'Wait for the current operation before opening another screen.', "Aguarde a operação atual terminar antes de abrir outra tela."));
    return box;
  }
  function scopeAvailable() {
    return !!S.data?.report?.sections?.some(section => section.key === 'scope');
  }
  function content(index) {
    const box = h('div', {class: 'guide-step-content'});
    box.append(screenshot(screens[index]));
    if (index === 0) {
      box.append(note('Prueba el recorrido con Nimbus si aún no tienes material. Se crea una copia editable con datos ficticios; tu proyecto actual se guarda primero y no se sustituye.',
        'Try the workflow with Nimbus if you do not have material yet. It creates an editable copy with fictional data; your current project is saved first and is not replaced.', "Experimente o fluxo com o Nimbus se ainda não tiver material. Ele cria uma cópia editável com dados fictícios; o projeto atual é salvo antes e não é substituído."),
      example(w('Elige cómo empezar', 'Choose a starting point', "Escolha como começar"), [h('div', {class: 'guide-choice-grid'},
        h('div', {}, h('strong', {}, 'Nimbus'), h('span', {}, w('Ejemplo editable', 'Editable example', "Exemplo editável"))),
        h('div', {}, h('strong', {}, w('Proyecto nuevo', 'New project', "Novo projeto")), h('span', {}, w('Tu trabajo y tus datos', 'Your work and data', "Seu trabalho e seus dados"))),
        h('div', {}, h('strong', {}, w('Respaldo ZIP', 'ZIP backup', "Backup ZIP")), h('span', {}, w('Una copia para continuar', 'A copy to continue', "Uma cópia para continuar"))))],
        w('Leer la guía no crea proyectos. Los botones de abajo realizan la acción que elijas.', 'Reading this guide creates no project. The buttons below perform the action you choose.', "Ler este guia não cria projetos. Os botões abaixo executam a ação escolhida.")),
      checklist([
        ['Distingue un laboratorio de un encargo real y rotula las simulaciones.', 'Distinguish a lab from a real engagement and label simulations.', "Diferencie um laboratório de um trabalho real e identifique as simulações."],
        ['Para un encargo, confirma autorización y reglas de trabajo fuera de la herramienta.', 'For an engagement, confirm authorization and rules of engagement outside the tool.', "Em um trabalho real, confirme a autorização e as regras de engajamento fora da ferramenta."],
        ['Comprueba la instalación antes de depender de la exportación PDF.', 'Check the installation before relying on PDF export.', "Verifique a instalação antes de depender da exportação em PDF."]
      ]), h('div', {class: 'guide-actions'},
        button(w('Probar Nimbus: crear una copia', 'Try Nimbus: create a copy', "Experimentar Nimbus: criar uma cópia"), () => activate('demoBtn'), 'demo', true),
        button(w('Crear proyecto', 'Create project', "Criar projeto"), opener => activate('newProjectBtn', opener), 'new'),
        button(w('Abrir respaldo', 'Open backup', "Abrir backup"), () => activate('importProjectBtn'), 'import'),
        button(w('Comprobar instalación', 'Check installation', "Verificar instalação"), () => activate('diagnosticsBtn'), 'diagnostics')));
    } else if (index === 1) {
      box.append(note('Identifica al cliente, al evaluador y el periodo de trabajo. Escribe objetivos, activos incluidos, exclusiones y limitaciones antes de resumir resultados.',
        'Identify the client, assessor and assessment period. Write objectives, included assets, exclusions and limitations before summarizing results.', "Identifique o cliente, o avaliador e o período da avaliação. Escreva os objetivos, os ativos incluídos, as exclusões e as limitações antes de resumir os resultados."),
      example(w('Un alcance que se puede leer', 'A readable scope', "Um escopo legível"), [exampleRows([
        [w('Objetivo', 'Target', "Alvo"), 'https://portal.example'],
        [w('Incluido', 'Included', "Incluído"), w('Portal web y API de pruebas autorizada', 'Web portal and authorized test API', "Portal web e API de testes autorizada")],
        [w('Excluido', 'Excluded', "Excluído"), w('Producción y pruebas de denegación de servicio', 'Production and denial-of-service tests', "Produção e testes de negação de serviço")],
        [w('Limitación', 'Limitation', "Limitação"), w('Sin acceso al código fuente', 'No access to source code', "Sem acesso ao código-fonte")]
      ])], w('El ejemplo orienta la redacción; no modifica tu alcance ni concede autorización.', 'This example guides your writing; it does not modify scope or grant authorization.', "Este exemplo orienta a redação; não altera o escopo nem concede autorização.")),
      checklist([
        ['Abre Contenido → Secciones del informe para recorrer el índice junto al editor. Buscar o cerrar ese panel no modifica el informe.', 'Open Content → Report sections to browse the index beside the editor. Searching or closing that panel does not modify the report.', "Abra Conteúdo → Seções do relatório para percorrer o índice ao lado do editor. Pesquisar ou fechar esse painel não modifica o relatório."],
        ['Usa Activos para registrar y vincular objetivos a los hallazgos.', 'Use Assets to register targets and link them to findings.', "Use Ativos para registrar alvos e vinculá-los aos achados."],
        ['En Cobertura, separa las pruebas realizadas de las pendientes o bloqueadas.', 'In Coverage, distinguish performed tests from pending or blocked tests.', "Em Cobertura, diferencie testes realizados de testes pendentes ou bloqueados."],
        ['Si incluyes apetito de riesgo o impacto de negocio, documenta su fuente y supuestos.', 'If you include risk appetite or business impact, document sources and assumptions.', "Se incluir apetite ao risco ou impacto no negócio, documente as fontes e as premissas."]
      ]), projectActions(
        button(w('Abrir metadatos', 'Open metadata', "Abrir metadados"), () => go('report'), 'metadata', true, true),
        ...(scopeAvailable() ? [button(w('Abrir alcance', 'Open scope', "Abrir escopo"), () => go('section', 'scope'), 'scope', false, true)] : []),
        button(w('Abrir activos', 'Open assets', "Abrir ativos"), () => go('workflow', 'assets'), 'assets', false, true),
        button(w('Abrir cobertura', 'Open coverage', "Abrir cobertura"), () => go('workflow', 'coverage'), 'coverage', false, true)));
      if (S.slug && !scopeAvailable()) box.append(note('La sección Alcance no está activada en este informe. Puedes añadirla desde «Gestionar secciones»; la guía no la activa por ti.',
        'The Scope section is not enabled in this report. You can add it under “Manage sections”; the guide does not enable it for you.', "A seção Escopo não está ativa neste relatório. Você pode adicioná-la em “Gerenciar seções”; o guia não a ativa automaticamente."));
    } else if (index === 2) {
      box.append(note('Cuenta qué control falló, cómo lo comprobaste y qué resultado observaste. La severidad técnica y el riesgo para el negocio necesitan argumentos distintos.',
        'Explain the failed control, how you tested it and what you observed. Technical severity and business risk require different reasoning.', "Explique qual controle falhou, como você o testou e o que observou. A severidade técnica e o risco para o negócio exigem justificativas diferentes."),
      example(w('De observación a hallazgo', 'From observation to finding', "Da observação ao achado"), [
        h('div', {class: 'guide-finding-preview'}, h('span', {class: 'guide-example-id'}, 'F1'), h('strong', {}, w('Lectura de un registro de otra cuenta', 'Reading another account’s record', "Leitura de um registro de outra conta"))),
        exampleRows([
          [w('Observación', 'Observation', "Observação"), w('Una cuenta de pruebas recibe un registro ajeno al cambiar el identificador.', 'A test account receives another account’s record after changing its identifier.', "Uma conta de teste recebe o registro de outra conta após alterar seu identificador.")],
          [w('Causa', 'Cause', "Causa"), w('Falta el control de autorización por objeto.', 'Object-level authorization is missing.', "Falta autorização no nível do objeto.")],
          [w('Severidad técnica', 'Technical severity', "Severidade técnica"), w('Justifica las métricas del vector CVSS elegido.', 'Justify the metrics in your chosen CVSS vector.', "Justifique as métricas do vetor CVSS escolhido.")],
          [w('Riesgo de negocio', 'Business risk', "Risco de negócio"), w('Redacta impacto, exposición y supuestos con contexto del cliente.', 'Describe impact, exposure and assumptions using client context.', "Descreva impacto, exposição e premissas com o contexto do cliente.")]
        ])], w('Es una muestra de redacción, no un resultado de pruebas ni una puntuación calculada.', 'This is a writing sample, not a test result or a calculated score.', "Esta é uma amostra de redação, não um resultado de teste nem uma pontuação calculada.")),
      checklist([
        ['En Contenido → Lista de hallazgos, busca por ID o título y filtra por severidad o tipo. Los filtros no cambian la ficha abierta; usa Mostrar selección si queda fuera de la lista.', 'In Content → Finding list, search by ID or title and filter by severity or type. Filters do not change the open item; use Show selection if it falls outside the list.', "Em Conteúdo → Lista de achados, pesquise por ID ou título e filtre por severidade ou tipo. Os filtros não trocam o item aberto; use Mostrar seleção se ele ficar fora da lista."],
        ['Incluye procedimiento, resultado observado, impacto demostrado y remediación comprobable.', 'Include procedure, observed result, demonstrated impact and verifiable remediation.', "Inclua o procedimento, o resultado observado, o impacto demonstrado e uma correção verificável."],
        ['CVSS 3.1 o 4.0 expresa severidad técnica; no calcula por sí solo pérdidas o apetito de riesgo.', 'CVSS 3.1 or 4.0 expresses technical severity; it does not calculate losses or risk appetite by itself.', "O CVSS 3.1 ou 4.0 expressa severidade técnica; sozinho, não calcula perdas nem apetite ao risco."],
        ['Una plantilla o importación ahorra redacción, pero debes verificarla y adaptarla a tu evidencia.', 'A template or import saves writing time, but you must verify it and adapt it to your evidence.', "Um modelo ou uma importação economiza tempo de redação, mas você deve verificá-los e adaptá-los às suas evidências."]
      ]), projectActions(
        button(w('Abrir hallazgos', 'Open findings', "Abrir achados"), () => go('findings'), 'findings', true, true),
        button(w('Añadir hallazgo en blanco', 'Add blank finding', "Adicionar achado em branco"), () => { closeNavigation(); $('[data-add="blank"]')?.click(); $('#editor')?.focus({preventScroll: true}); }, 'add-finding', false, true)));
    } else if (index === 3) {
      box.append(note('Una imagen suelta no demuestra todo el hallazgo. Añade un pie claro, vincúlala al hallazgo y conserva el procedimiento como texto reproducible.',
        'An image alone does not demonstrate an entire finding. Add a clear caption, link it to the finding and retain the procedure as reproducible text.', "Uma imagem isolada não demonstra todo o achado. Adicione uma legenda clara, vincule-a ao achado e preserve o procedimento como texto reproduzível."),
      example(w('La evidencia tiene contexto', 'Evidence has context', "A evidência tem contexto"), [
        h('div', {class: 'guide-evidence-preview'}, h('div', {class: 'guide-evidence-document'},
          h('span', {class: 'guide-example-id'}, 'EV-01'), h('strong', {}, w('Respuesta de prueba', 'Test response', "Resposta de teste")),
          h('code', {}, 'GET /records/42 → 200'), h('span', {}, w('Datos sensibles censurados', 'Sensitive data redacted', "Dados sensíveis censurados"))),
        h('div', {class: 'guide-evidence-link'}, h('span', {}, w('Vinculada a', 'Linked to', "Vinculada a")), h('strong', {}, 'F1'))),
        h('p', {class: 'guide-example-caption'}, w('Pie: la cuenta A recibe el registro de B en el entorno autorizado de pruebas.', 'Caption: account A receives account B’s record in the authorized test environment.', "Legenda: a conta A recebe o registro da conta B no ambiente de testes autorizado."))
      ], w('La muestra es texto sintético; no es una captura real ni una petición ejecutada.', 'This is synthetic text, not a real screenshot or an executed request.', "Este é um texto sintético, não uma captura real nem uma requisição executada.")),
      checklist([
        ['En Evidencias: sube la imagen, escribe el pie y marca «Usada en hallazgos».', 'In Evidence: upload the image, write the caption and select “Used in findings”.', "Em Evidências: envie a imagem, escreva a legenda e selecione “Usada em achados”."],
        ['Censura píxeles con «Anotar / censurar» y revisa la copia procesada antes de publicar.', 'Redact pixels under “Annotate / redact” and review the processed copy before publication.', "Censure os pixels em “Anotar / ocultar dados” e revise a cópia processada antes da publicação."],
        ['La Captura rápida queda en la bandeja privada hasta que la incorpores a un hallazgo.', 'Quick capture stays in the private inbox until you add it to a finding.', "A Captura rápida permanece na caixa de entrada privada até ser adicionada a um achado."]
      ]), projectActions(
        button(w('Abrir evidencias', 'Open evidence', "Abrir evidências"), () => go('workflow', 'evidence'), 'evidence', true, true),
        button(w('Abrir bandeja de captura', 'Open capture inbox', "Abrir caixa de capturas"), () => go('capture'), 'capture', false, true)));
    } else if (index === 4) {
      box.append(note('Primero revisa las omisiones del informe. Después inspecciona el texto y las imágenes que saldrán del proyecto. Lee cada aviso: la herramienta no valida por ti el pentest.',
        'First review report omissions. Then inspect the text and images leaving the project. Read each warning: the tool does not validate the pentest for you.', "Primeiro, revise as omissões do relatório. Depois, inspecione o texto e as imagens que sairão do projeto. Leia cada aviso: a ferramenta não valida o pentest por você."),
      example(w('Dos revisiones diferentes', 'Two different reviews', "Duas revisões diferentes"), [h('div', {class: 'guide-review-grid'},
        h('div', {}, h('strong', {}, w('Revisión de entrega', 'Delivery review', "Revisão de entrega")), h('p', {}, w('Campos, referencias y omisiones', 'Fields, references and omissions', "Campos, referências e omissões"))),
        h('div', {}, h('strong', {}, w('Inspector de publicación', 'Publication inspector', "Inspetor de publicação")), h('p', {}, w('Texto de salida, imágenes y posibles secretos', 'Outgoing text, images and possible secrets', "Texto de saída, imagens e possíveis segredos"))))],
        w('Sin avisos no significa «sin vulnerabilidades» ni «listo sin revisión humana».', 'No warnings does not mean “no vulnerabilities” or “ready without human review”.', "A ausência de avisos não significa “sem vulnerabilidades” nem “pronto sem revisão humana”.")),
      checklist([
        ['Contrasta afirmaciones y referencias con tu evidencia y tu alcance.', 'Check claims and references against evidence and scope.', "Confira as afirmações e referências com as evidências e o escopo."],
        ['Revisa también el texto dentro de imágenes. El OCR local opcional puede omitir secretos y no censura automáticamente.', 'Also review text inside images. Optional local OCR can miss secrets and never redacts automatically.', "Revise também o texto dentro das imagens. O OCR local opcional pode deixar de identificar segredos e nunca censura automaticamente."],
        ['Las excepciones de publicación deben ser decisiones conscientes, no una forma de ocultar un aviso.', 'Publication exceptions must be deliberate decisions, not a way to conceal a warning.', "As exceções de publicação devem ser decisões conscientes, não uma forma de ocultar um aviso."]
      ]), projectActions(
        button(w('Abrir revisión de entrega', 'Open delivery review', "Abrir revisão de entrega"), () => go('workflow', 'review'), 'review', true, true),
        button(w('Abrir inspector de publicación', 'Open publication inspector', "Abrir inspetor de publicação"), () => { closeNavigation(); return StudioUI.inspector(); }, 'inspector', false, true)));
    } else {
      box.append(note('Prepara los formatos desde una revisión guardada, descarga el resultado y ábrelo antes de entregarlo. Conserva el proyecto editable por separado para seguir trabajando y registrar el retest.',
        'Prepare formats from a saved revision, download the result and open it before delivery. Keep the editable project separately to continue work and record retests.', "Prepare os formatos a partir de uma revisão salva, baixe o resultado e abra-o antes da entrega. Guarde o projeto editável separadamente para continuar o trabalho e registrar os retestes."),
      example(w('Cada archivo tiene un destinatario', 'Each file has a recipient', "Cada arquivo tem um destinatário"), [h('div', {class: 'guide-delivery-grid'},
        h('div', {}, h('strong', {}, w('Entrega', 'Deliverable', "Entrega")), h('span', {}, 'PDF · DOCX · HTML · Markdown'), h('p', {}, w('Informe y comprobaciones de exportación', 'Report and export checks', "Relatório e verificações de exportação"))),
        h('div', {}, h('strong', {}, w('Respaldo privado', 'Private backup', "Backup privado")), h('span', {}, w('ZIP de proyecto', 'Project ZIP', "ZIP do projeto")), h('p', {}, w('Editable, originales e historial', 'Editable data, originals and history', "Dados editáveis, originais e histórico"))))],
        w('El HTML autónomo contiene todo el informe aunque uses filtros. Un filtro no elimina información.', 'Standalone HTML contains the whole report even when filtered. A filter does not remove information.', "O HTML autônomo contém todo o relatório, mesmo com filtros. Um filtro não remove informações.")), screenshot(screens[6]),
      checklist([
        ['Abre los archivos: revisa saltos de página, imágenes, índice y enlaces. Las comprobaciones automáticas no sustituyen esta lectura.', 'Open the files: review page breaks, images, contents and links. Automatic checks do not replace this review.', "Abra os arquivos: revise quebras de página, imagens, sumário e links. As verificações automáticas não substituem essa leitura."],
        ['Guarda el respaldo como información confidencial; no lo incluyas por defecto en la entrega al cliente.', 'Store the backup as confidential information; do not include it in the client delivery by default.', "Guarde o backup como informação confidencial; não o inclua por padrão na entrega ao cliente."],
        ['Registra un retest con fecha, procedimiento y evidencia. «Corrección comunicada» no equivale a «corregido y verificado».', 'Record a retest with date, procedure and evidence. “Reported fixed” is distinct from “verified fixed”.', "Registre um reteste com data, procedimento e evidências. “Correção informada” é diferente de “correção verificada”."]
      ]), projectActions(
        button(w('Abrir pantalla de entrega', 'Open delivery screen', "Abrir tela de entrega"), () => go('studio', 'deliver'), 'delivery-screen', true, true),
        button(w('Preparar entrega: elegir formatos', 'Prepare delivery: choose formats', "Preparar entrega: escolher formatos"), () => activate('deliveryBtn'), 'delivery', false, true),
        button(w('Abrir respaldo del proyecto', 'Open project backup', "Abrir backup do projeto"), () => go('workflow', 'backup'), 'backup', false, true),
        button(w('Abrir correcciones y retest', 'Open remediation and retest', "Abrir correções e reteste"), () => go('workflow', 'retest'), 'retest', false, true)));
    }
    return box;
  }
  function seniorHelp() {
    const details = h('details', {class: 'guide-senior'}, h('summary', {}, w('Si ya haces informes: límites y atajos', 'Already writing reports? Boundaries and shortcuts', "Já escreve relatórios? Limites e atalhos")));
    const rows = [
      ['Guardado y borrador', 'Save and draft', "Salvar e rascunho", 'Comprueba el estado de guardado. Un borrador recuperable del navegador no equivale a una revisión guardada en disco; las entregas usan esta última.', 'Check the save state. A recoverable browser draft is distinct from a saved disk revision; deliveries use the latter.', "Confira o estado de salvamento. Um rascunho recuperável do navegador é diferente de uma revisão salva em disco; as entregas usam esta última."],
      ['Revisión y criterio técnico', 'Review and technical judgment', "Revisão e critério técnico", 'Los avisos detectan omisiones y coherencia. La validación del hallazgo, el riesgo de negocio y la aceptación del riesgo corresponden al evaluador y al cliente.', 'Warnings detect omissions and consistency issues. Finding validation, business risk and risk acceptance remain with the assessor and client.', "Os avisos detectam omissões e problemas de coerência. A validação do achado, o risco de negócio e a aceitação do risco continuam sob responsabilidade do avaliador e do cliente."],
      ['PDF y Word', 'PDF and Word', "PDF e Word", 'Comprueba instalación y abre el archivo final. La vista HTML del editor no reproduce todos los saltos de página del PDF o Word.', 'Check installation and open the final file. The editor’s HTML preview does not reproduce every PDF or Word page break.', "Verifique a instalação e abra o arquivo final. A prévia HTML do editor não reproduz todas as quebras de página do PDF ou do Word."],
      ['Originales y respaldos', 'Originals and backups', "Originais e backups", 'La copia censurada no sustituye el original privado. Los respaldos incluyen originales e historial; el borrador JSON de emergencia no es un respaldo integral de evidencias.', 'A redacted copy does not replace the private original. Backups include originals and history; an emergency JSON draft is not a complete evidence backup.', "Uma cópia censurada não substitui o original privado. Os backups incluem originais e histórico; um rascunho JSON de emergência não é um backup completo das evidências."],
      ['Texto dentro de imágenes', 'Text inside images', "Texto nas imagens", 'El inspector ofrece OCR local opcional con Tesseract (eng), por imagen y bajo tu acción. Puede omitir datos sensibles; no censura automáticamente. Revisa capturas, adjuntos y formatos finales.', 'The inspector offers optional local Tesseract OCR (eng), per image and only on your action. It may miss sensitive data and never redacts automatically. Review screenshots, attachments and final formats.', "O inspetor oferece OCR local opcional com Tesseract (eng), por imagem e somente por sua ação. Ele pode deixar de identificar dados sensíveis e nunca censura automaticamente. Revise capturas, anexos e formatos finais."]
    ];
    details.append(h('dl', {}, rows.map(([es, en, pt, bodyEs, bodyEn, bodyPt]) => h('div', {}, h('dt', {}, w(es, en, pt)), h('dd', {}, w(bodyEs, bodyEn, bodyPt))))));
    return details;
  }
  function render(el) {
    if (S.sel.type === 'guide' && Number.isInteger(S.sel.idx) && S.sel.idx >= 0 && S.sel.idx < names.length) current = S.sel.idx;
    const shell = h('section', {class: 'guide-shell', 'data-guide-page': '', 'aria-labelledby': 'guideTitle'});
    shell.append(h('header', {class: 'guide-intro'}, h('p', {class: 'guide-eyebrow'}, w('TUTORIAL VISUAL · 6 PASOS', 'VISUAL TUTORIAL · 6 STEPS', "TUTORIAL VISUAL · 6 ETAPAS")),
      h('h1', {id: 'guideTitle'}, w('Tu primer informe, paso a paso.', 'Your first report, step by step.', "Seu primeiro relatório, passo a passo.")),
      h('p', {}, w('Un recorrido opcional para convertir tu trabajo en una entrega clara. Puedes volver a cualquier paso sin cambiar el informe.',
        'An optional path from assessment work to a clear deliverable. You can revisit any step without changing the report.', "Um percurso opcional para transformar a avaliação em uma entrega clara. Você pode revisitar qualquer etapa sem alterar o relatório.")),
      h('ol', {class: 'guide-flow', 'aria-label': w('De la evidencia a la entrega', 'From evidence to delivery', "Da evidência à entrega")},
        ['Plantilla|Template|Modelo', 'Hallazgo|Finding|Achado', 'Revisión|Review|Revisão', 'Entrega|Delivery|Entrega'].map(pair => h('li', {}, w(...pair.split('|')))))));
    const reset = h('button', {type:'button', class:'btn', 'data-tutorial-reset':''}, w('Reiniciar recorrido','Restart tutorial', "Reiniciar tutorial"));
    reset.addEventListener('click', () => {remember({completed:false, step:0, visited:[]}); open(0, true);});
    shell.append(h('div', {class:'tutorial-progress'}, h('p', {'data-tutorial-progress':'', role:'status'}, progress().completed ?
      w('Recorrido completado. Puedes repasar cualquier paso.','Tutorial completed. You can revisit any step.', "Tutorial concluído. Você pode revisitar qualquer etapa.") :
      progress().visited.length + w(' de 6 pasos consultados. Este registro pertenece al tutorial.',' of 6 steps viewed. This record belongs to the tutorial.', " de 6 etapas consultadas. Este registro pertence ao tutorial.")), reset));
    shell.append(h('p', {class:'tutorial-storage-note'}, tutorialStorage ?
      w('El progreso se guarda solo en este navegador. Reiniciarlo no cambia tus proyectos.','Progress is saved only in this browser. Restarting it does not change your projects.', "O progresso é salvo somente neste navegador. Reiniciá-lo não altera seus projetos.") :
      w('Este navegador no permite guardar el progreso. Puedes seguir el recorrido durante esta sesión y abrirlo siempre desde Tutorial visual.','This browser cannot save progress. You can continue during this session and reopen it anytime from Visual tutorial.', "Este navegador não permite salvar o progresso. Você pode continuar nesta sessão e reabrir o percurso a qualquer momento em Tutorial visual.")));
    if (S.data) shell.append(projectState(true));
    const navigation = h('nav', {class: 'guide-navigation', 'aria-label': w('Pasos de la guía', 'Guide steps', "Etapas do guia")},
      h('ol', {'data-guide-nav': ''}, names.map((pair, index) => {
        const b = h('button', {type: 'button', 'data-guide-step': index, 'aria-current': current === index ? 'step' : null},
          h('span', {class: 'guide-step-number', 'aria-hidden': 'true'}, String(index + 1).padStart(2, '0')), h('span', {}, w(...pair)));
        b.addEventListener('click', () => open(index, true));
        return h('li', {}, b);
      })));
    const stage = h('section', {class: 'guide-stage', 'data-guide-current': current, 'aria-labelledby': 'guideStepTitle'},
      h('p', {class: 'guide-position'}, w('Paso ', 'Step ', "Etapa ") + (current + 1) + w(' de 6 · recorrido de la guía, no avance del proyecto', ' of 6 · guide position, not project progress', " de 6 · posição no guia, não progresso do projeto")),
      h('h2', {id: 'guideStepTitle', tabindex: '-1'}, w(...names[current])), content(current));
    const previous = button(w('Paso anterior', 'Previous step', "Etapa anterior"), () => open(current - 1, true), 'previous');
    previous.id = 'guidePrev'; previous.disabled = current === 0;
    const next = button(w('Siguiente paso', 'Next step', "Próxima etapa"), () => open(current + 1, true), 'next', true);
    next.id = 'guideNext'; next.disabled = current === names.length - 1;
    stage.append(h('footer', {class: 'guide-footer'}, previous, next,
      button(S.slug ? w('Volver al inicio del proyecto', 'Back to project overview', "Voltar à visão geral do projeto") : w('Volver al inicio', 'Back to overview', "Voltar ao início"), () => go('home'), 'home')));
    if (current === names.length - 1) {
      const complete = h('button', {type:'button', class:'btn primary', 'data-tutorial-complete':''}, w('Completar recorrido','Complete tutorial', "Concluir tutorial"));
      complete.addEventListener('click', () => {remember({completed:true, dismissed:true}); renderMain(); $('#guideStepTitle')?.focus({preventScroll:true});});
      complete.disabled = progress().completed;
      stage.querySelector('.guide-footer').append(complete);
    }
    shell.append(h('div', {class: 'guide-layout'}, navigation, stage), seniorHelp());
    el.append(shell);
  }
  function entry() {
    const wrapper = h('div', {class:'tutorial-entry-wrapper'});
    if (S.data) wrapper.append(projectState());
    if (progress().dismissed) return wrapper;
    const start = button(w('Empezar recorrido','Start tutorial', "Iniciar tutorial"), () => open(), 'open-guide', true);
    start.dataset.tutorialStart = '';
    const dismiss = h('button', {type:'button', class:'btn', 'data-tutorial-dismiss':''}, w('Ahora no','Not now', "Agora não"));
    dismiss.addEventListener('click', () => {remember({dismissed:true}); wrapper.querySelector('[data-tutorial-invite]')?.remove(); $('#editor')?.focus({preventScroll:true});});
    wrapper.prepend(h('section', {class: 'guide-entry', 'data-tutorial-invite':'', 'aria-labelledby': 'guideEntryTitle'},
      h('div', {}, h('p', {class: 'guide-eyebrow'}, w('6 PASOS · A TU RITMO', '6 STEPS · AT YOUR PACE', "6 ETAPAS · NO SEU RITMO")),
        h('h2', {id: 'guideEntryTitle'}, w('Conoce report-gen en imágenes','Get to know report-gen in pictures', "Conheça o report-gen em imagens")),
        h('p', {}, w('Capturas reales para elegir plantilla, redactar, revisar y exportar. Puedes volver desde «Tutorial visual» en el menú.',
          'Real screenshots to choose a template, write, review and export. Reopen it from “Visual tutorial” in the menu.', "Capturas reais para escolher um modelo, redigir, revisar e exportar. Reabra em “Tutorial visual” no menu."))),
      h('div', {class:'tutorial-entry-actions'}, start, dismiss)));
    return wrapper;
  }
  function bind() {
    if ($('#guideBtn')) return;
    const b = button(w('Tutorial visual', 'Visual tutorial', "Tutorial visual"), () => open(), 'open-guide');
    b.id = 'guideBtn';
    const utilities = $('.workspace-utilities') || $('.sidebar');
    const more = $('#studioMore .studio-more-body');
    // One stable menu entry remains reachable on mobile and in desktop focus mode.
    (more || utilities).append(b);
    update();
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
      b.textContent = w('Tutorial visual', 'Visual tutorial', "Tutorial visual");
      b.classList.toggle('active', active);
      b.setAttribute('aria-current', active ? 'page' : 'false');
      b.disabled = projectBusyCount > 0;
    }
    $('.layout')?.classList.toggle('workspace-guide', active);
    if (active && $('#workspaceContext')) $('#workspaceContext').textContent = w('Tutorial visual', 'Visual tutorial', "Tutorial visual");
  }
  return {render, bind, update, entry, nextAction};
})();

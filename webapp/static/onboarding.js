/* Learning preferences are browser UI state. They never modify an engagement. */
const OnboardingUI = (() => {
  'use strict';
  const w = (es, en, pt) => uiText(es, en, pt);
  const sessions = new Map();
  const advanced = ['workspaceResearch', 'workspaceFollowup', 'workspaceTools'];
  let bound = false, applied = '', helpOpen = false, helpScope = '', target = null;
  const names = [
    ['Proyecto', 'Project', 'Projeto'], ['Alcance', 'Scope', 'Escopo'],
    ['Hallazgos', 'Findings', 'Achados'], ['Evidencias', 'Evidence', 'Evidências'],
    ['Revisión', 'Review', 'Revisão'], ['Entrega', 'Delivery', 'Entrega']
  ];
  const steps = [
    {
      goal: ['Identifica el informe, el cliente y el periodo de trabajo. El idioma del informe se configura aquí; el idioma de la interfaz es independiente.', 'Identify the report, client and assessment dates. Set the report language here; the interface language is independent.', 'Identifique o relatório, o cliente e o período do trabalho. Defina aqui o idioma do relatório; o idioma da interface é independente.'],
      example: ['Banco Aurora · Evaluación web · Entorno de pruebas · Octubre de 2026.', 'Aurora Bank · Web assessment · Test environment · October 2026.', 'Banco Aurora · Avaliação web · Ambiente de testes · Outubro de 2026.']
    },
    {
      goal: ['Describe los objetivos, activos incluidos, exclusiones y limitaciones. La guía no añade secciones ni cambia el alcance.', 'Describe objectives, included assets, exclusions and limitations. The guide does not add sections or change scope.', 'Descreva os objetivos, ativos incluídos, exclusões e limitações. O guia não adiciona seções nem altera o escopo.'],
      example: ['Incluido: portal.example y su API de pruebas. Excluido: producción y denegación de servicio. Limitación: sin código fuente.', 'Included: portal.example and its test API. Excluded: production and denial of service. Limitation: no source code.', 'Incluído: portal.example e sua API de testes. Excluído: produção e negação de serviço. Limitação: sem código-fonte.']
    },
    {
      goal: ['Explica qué control falló, cómo lo comprobaste, el impacto demostrado y una corrección verificable. Distingue la severidad técnica del riesgo de negocio.', 'Explain the failed control, how you tested it, demonstrated impact and verifiable remediation. Distinguish technical severity from business risk.', 'Explique qual controle falhou, como foi testado, o impacto demonstrado e uma correção verificável. Diferencie a severidade técnica do risco de negócio.'],
      example: ['Una cuenta de pruebas accedió a un registro ajeno al cambiar el identificador. Documenta petición, respuesta y límites de la comprobación.', 'A test account accessed another account’s record after changing its identifier. Document the request, response and limits of the verification.', 'Uma conta de teste acessou o registro de outra conta após alterar o identificador. Documente a requisição, a resposta e os limites da verificação.']
    },
    {
      goal: ['Relaciona cada evidencia con su hallazgo o retest. Revisa la copia publicada y conserva los originales privados; avanzar en la guía no aprueba evidencias.', 'Link evidence to its finding or retest. Review the published copy and retain private originals; advancing through the guide does not approve evidence.', 'Vincule cada evidência ao achado ou reteste. Revise a cópia publicada e preserve os originais privados; avançar no guia não aprova evidências.'],
      example: ['F-01 → captura de respuesta → pie con resultado observado → copia publicada con los datos sensibles ocultos.', 'F-01 → response screenshot → caption with the observed result → published copy with sensitive data concealed.', 'F-01 → captura da resposta → legenda com o resultado observado → cópia publicada com dados sensíveis ocultos.']
    },
    {
      goal: ['Revisa campos, vínculos, omisiones y contenido que compartirás. La revisión editorial y el recorrido no sustituyen una verificación técnica.', 'Review fields, links, omissions and the content you will share. Editorial review and this walkthrough do not replace technical verification.', 'Revise campos, vínculos, omissões e o conteúdo a compartilhar. A revisão editorial e este percurso não substituem a verificação técnica.'],
      example: ['Una corrección comunicada sigue pendiente de retest hasta comprobarla y registrar el resultado con su evidencia.', 'A reported fix remains pending retest until you verify it and record the result with supporting evidence.', 'Uma correção informada permanece pendente de reteste até ser verificada e ter o resultado registrado com evidências.']
    },
    {
      goal: ['Revisa el destinatario y la vista previa, elige los formatos y comprueba los archivos generados. Conserva el proyecto editable por separado.', 'Review the audience and preview, choose formats and inspect the generated files. Keep the editable project separately.', 'Revise o público e a prévia, escolha os formatos e confira os arquivos gerados. Preserve o projeto editável separadamente.'],
      example: ['PDF y DOCX para el cliente; HTML o Markdown según el destino. El respaldo privado conserva el proyecto y sus originales.', 'PDF and DOCX for the client; HTML or Markdown as needed. The private backup retains the project and its originals.', 'PDF e DOCX para o cliente; HTML ou Markdown conforme o destino. O backup privado preserva o projeto e seus originais.']
    }
  ];
  function workspace() {
    try { return typeof BrowserWorkspace !== 'undefined' ? BrowserWorkspace.current() : S.workspace_id || ''; }
    catch (_) { return S.workspace_id || ''; }
  }
  function storageKey() { const id = workspace(); return id ? 'rg.onboarding.v1:' + encodeURIComponent(id) : null; }
  function emptyRoute() { return {active:false, step:0, completed:false, visited:[]}; }
  function cleanRoute(value) {
    const route = emptyRoute();
    if (!value || typeof value !== 'object' || Array.isArray(value)) return route;
    route.active = value.active === true;
    route.step = Number.isInteger(value.step) && value.step >= 0 && value.step < 6 ? value.step : 0;
    route.completed = value.completed === true;
    route.visited = Array.isArray(value.visited) ? [...new Set(value.visited.filter(n => Number.isInteger(n) && n >= 0 && n < 6))] : [];
    return route;
  }
  function preference() {
    const key = storageKey() || 'session-without-workspace';
    if (sessions.has(key)) return sessions.get(key);
    const value = {version:1, mode:null, routes:Object.create(null), storageAvailable:!!storageKey()};
    try {
      const raw = storageKey() ? JSON.parse(localStorage.getItem(key) || 'null') : null;
      if (raw?.version === 1) {
        if (['guided','complete'].includes(raw.mode)) value.mode = raw.mode;
        if (raw.routes && typeof raw.routes === 'object' && !Array.isArray(raw.routes)) {
          for (const [slug, route] of Object.entries(raw.routes).slice(-128)) value.routes[slug] = cleanRoute(route);
        }
      }
    } catch (_) { value.storageAvailable = false; }
    sessions.set(key, value);
    return value;
  }
  function routeKey() { return S.slug ? 'project:' + S.slug : 'welcome'; }
  function route() { return preference().routes[routeKey()] || emptyRoute(); }
  function remember(changes = null) {
    const value = preference();
    if (changes) value.routes[routeKey()] = cleanRoute({...route(), ...changes});
    const entries = Object.entries(value.routes).slice(-128);
    value.routes = Object.assign(Object.create(null), Object.fromEntries(entries));
    try {
      const key = storageKey();
      if (!key) throw Error('No workspace identity');
      localStorage.setItem(key, JSON.stringify({version:1, mode:value.mode, routes:value.routes}));
      value.storageAvailable = true;
    } catch (_) { value.storageAvailable = false; }
  }
  function state() { return {version:1, mode:preference().mode, ...JSON.parse(JSON.stringify(route())), storageAvailable:preference().storageAvailable}; }
  function busy() { return (typeof projectBusyCount !== 'undefined' && projectBusyCount > 0) || (typeof projectStore !== 'undefined' && projectStore.loading); }
  function button(text, action, run, primary = false) {
    const control = h('button', {type:'button', class:'btn sm' + (primary ? ' primary' : ''), 'data-onboarding-action':action}, text);
    control.addEventListener('click', async () => {
      if (busy()) return;
      control.disabled = true;
      try { await run(control); }
      catch (error) { if (typeof toast === 'function') toast(error.message, 'err'); }
      finally { if (control.isConnected) control.disabled = !!busy(); }
    });
    control.disabled = !!busy();
    return control;
  }
  function focusPanel() { const title = document.querySelector('#onboardingStepTitle'); title?.focus(); title?.scrollIntoView?.({block:'nearest'}); }
  function focusControl(id) {
    const mobileHidden = window.matchMedia?.('(max-width:760px)').matches && !document.querySelector('.layout')?.classList.contains('navigation-open');
    const control = document.getElementById(id);
    (mobileHidden && control?.closest('#workspaceSidebar') ? document.querySelector('#editor') : control)?.focus({preventScroll:true});
  }
  function changeRoute(changes, focus = false) {
    remember(changes); refresh(); if (focus) focusPanel();
  }
  function choose(mode) {
    if (!['guided','complete'].includes(mode)) return;
    const chooserFocused = !!document.activeElement?.closest('[data-onboarding-chooser]');
    preference().mode = mode;
    if (mode === 'guided') remember({...route(), active:!route().completed, visited:[...route().visited, route().step]});
    else remember({active:false});
    applied = ''; refresh();
    if (chooserFocused) focusControl('onboardingMode');
  }
  function start(restart = false) {
    const current = route(), step = restart ? 0 : current.step;
    closeMobileNavigation();
    changeRoute({active:true, completed:false, step, visited:restart ? [0] : [...current.visited,step]}, true);
  }
  function move(step) { changeRoute({active:true, completed:false, step, visited:[...route().visited,step]}, true); }
  function isScope() { return S.data?.report?.sections?.some(section => section.key === 'scope'); }
  function destinations(index) {
    if (!S.data) return {type:'home', value:-1};
    return [{type:'report',value:-1}, isScope() ? {type:'section',value:'scope'} : {type:'report',value:-1}, {type:'findings',value:-1}, {type:'workflow',value:'evidence'}, {type:'workflow',value:'review'}, {type:'studio',value:'deliver'}][index];
  }
  function closeMobileNavigation() {
    if (window.matchMedia?.('(max-width:760px)').matches) {
      document.querySelector('.layout')?.classList.remove('navigation-open');
      document.querySelector('#sidebarToggle')?.setAttribute('aria-expanded','false');
    }
  }
  function openStep() {
    const destination = destinations(route().step);
    closeMobileNavigation();
    select(destination.type, destination.value);
    // Navigation renders the editor synchronously. Focus a real control when it
    // is present; asynchronous workflow content retains the editor as fallback.
    afterRender();
    const node = highlight();
    const hiddenSidebar = window.matchMedia?.('(max-width:760px)').matches && node?.closest('#workspaceSidebar');
    const focusable = !hiddenSidebar && node?.matches('button,input,select,textarea,summary,a[href]') ? node : document.querySelector('#editor');
    focusable?.focus({preventScroll:true}); focusable?.scrollIntoView?.({block:'nearest'});
  }
  function stepTarget(index) {
    const editor = document.querySelector('#editor'), find = selector => editor?.querySelector(selector);
    if (!S.data) return document.querySelector('.workspace-hero-actions .primary') || document.querySelector('#newProjectBtn');
    if (index === 0) return S.sel.type === 'report' ? find('[data-field="report_title"]') || document.querySelector('#navReport') : document.querySelector('#navReport');
    if (index === 1) return !isScope() ? document.querySelector('#contextIndexToggle') || editor : S.sel.type === 'section' && S.sel.key === 'scope' ? find('[data-field="objectives"]') || find('textarea,input') : document.querySelector('#workspaceSections');
    if (index === 2) return S.sel.type === 'findings' ? find('[data-finding-create="blank"]') || document.querySelector('#navFindings') : document.querySelector('#navFindings');
    if (index === 3) return S.sel.type === 'workflow' && S.sel.idx === 'evidence' ? find('[data-workflow-view="evidence"] button') || find('[data-workflow-view="evidence"]') : document.querySelector('[data-workflow="evidence"]');
    if (index === 4) return S.sel.type === 'workflow' && S.sel.idx === 'review' ? find('[data-workflow-view="review"] button:not(:disabled)') || find('[data-workflow-view="review"]') : document.querySelector('[data-workflow="review"]');
    return S.sel.type === 'studio' && S.sel.idx === 'deliver' ? find('[data-delivery-action="step-0"]') || find('[data-delivery-flow]') : document.querySelector('[data-studio-nav="deliver"]') || document.querySelector('#deliveryBtn');
  }
  function clearHighlight() {
    if (!target) return;
    target.classList.remove('onboarding-target');
    const described = (target.getAttribute('aria-describedby') || '').split(/\s+/).filter(value => value && value !== 'onboardingStepPurpose');
    if (described.length) target.setAttribute('aria-describedby', described.join(' ')); else target.removeAttribute('aria-describedby');
    target = null;
  }
  function highlight() {
    clearHighlight();
    if (!route().active || !document.querySelector('#onboardingStepPurpose')) return null;
    target = stepTarget(route().step);
    if (target) {
      target.classList.add('onboarding-target');
      const described = new Set((target.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
      described.add('onboardingStepPurpose'); target.setAttribute('aria-describedby', [...described].join(' '));
    }
    return target;
  }
  function storageNote() {
    return h('p', {class:'onboarding-note', role:'status'}, w('El navegador no permite guardar esta preferencia. Se conserva durante esta sesión.', 'The browser cannot save this preference. It is retained for this session.', 'O navegador não permite salvar esta preferência. Ela será mantida durante esta sessão.'));
  }
  async function practice() {
    if (typeof ExperienceUI === 'undefined' || typeof ExperienceUI.createPractice !== 'function') return;
    if (await ExperienceUI.createPractice()) {
      if (!preference().mode) preference().mode = 'guided';
      remember({active:true, step:0, completed:false, visited:[0]});
      applied = ''; refresh(); focusPanel();
    }
  }
  function entry() {
    const box = h('section', {'data-onboarding-entry':'', class:'onboarding-entry'});
    const current = state();
    if (!current.mode) {
      const chooser = h('div', {'data-onboarding-chooser':''},
        h('p', {class:'onboarding-eyebrow'}, w('TU FORMA DE TRABAJAR', 'YOUR WAY OF WORKING', 'SUA FORMA DE TRABALHAR')),
        h('h2', {}, w('¿Cómo quieres empezar?', 'How would you like to start?', 'Como você quer começar?')),
        h('p', {}, w('Elige cuánto acompañamiento quieres. Puedes cambiar de vista en cualquier momento y conservar todas las herramientas.', 'Choose how much guidance you want. Switch views at any time while keeping every tool available.', 'Escolha quanto acompanhamento deseja. Mude de visualização a qualquer momento e mantenha todas as ferramentas disponíveis.')));
      const choices = h('div', {class:'onboarding-choices'});
      for (const [mode, title, description] of [
        ['guided', ['Guiado','Guided','Guiado'], ['Un recorrido, ejemplos y el siguiente paso a mano. Las herramientas avanzadas empiezan contraídas.', 'A walkthrough, examples and the next step at hand. Advanced tools start collapsed.', 'Um percurso, exemplos e o próximo passo à mão. As ferramentas avançadas começam recolhidas.']],
        ['complete', ['Completo','Complete','Completo'], ['Acceso directo a los grupos de herramientas desplegados. La guía sigue disponible cuando la necesites.', 'Direct access to expanded tool groups. Guidance remains available whenever you need it.', 'Acesso direto aos grupos de ferramentas expandidos. O guia continua disponível quando precisar.']]
      ]) {
        const choice = button('', 'choose-' + mode, () => choose(mode));
        choice.dataset.onboardingChoice = mode; choice.className = 'onboarding-choice';
        choice.append(h('strong', {}, w(...title)), h('span', {}, w(...description))); choices.append(choice);
      }
      chooser.append(choices); box.append(chooser);
    } else {
      const row = h('div', {class:'onboarding-entry-row'}, h('div', {}, h('h2', {}, w('Aprende en tu espacio de trabajo', 'Learn in your workspace', 'Aprenda no seu espaço de trabalho')),
        h('p', {}, current.completed ? w('Recorrido leído. La verificación de tu informe sigue siendo independiente.', 'Walkthrough read. Verification of your report remains separate.', 'Percurso lido. A verificação do relatório permanece independente.') : w('Seis pasos opcionales con ejemplos y controles reales.', 'Six optional steps with examples and real controls.', 'Seis etapas opcionais com exemplos e controles reais.'))));
      const actions = h('div', {class:'onboarding-actions'});
      actions.append(button(current.active ? w('Ver recorrido','Show walkthrough','Ver percurso') : current.visited.length ? w('Reanudar recorrido','Resume walkthrough','Retomar percurso') : w('Iniciar recorrido','Start walkthrough','Iniciar percurso'), current.visited.length ? 'resume' : 'start', () => start()));
      if (current.visited.length) actions.append(button(w('Reiniciar','Restart','Reiniciar'), 'restart', () => start(true)));
      row.append(actions); box.append(row);
    }
    box.append(h('div', {class:'onboarding-practice'}, h('span', {}, w('Practica en una copia independiente con datos ficticios.', 'Practice in a separate copy with fictional data.', 'Pratique em uma cópia independente com dados fictícios.')),
      button(w('Crear práctica ficticia','Create fictional practice','Criar prática fictícia'), 'practice', practice)));
    if (!current.storageAvailable) box.append(storageNote());
    return box;
  }
  function contextHelp() {
    const selection = S.sel || {type:'home'}, type = selection.type;
    const step = type === 'report' ? 0 : type === 'section' ? 1 : ['findings','finding'].includes(type) ? 2 : type === 'studio' && selection.idx === 'deliver' ? 5 : 0;
    let title = type === 'section' ? S.data?.report?.sections?.find(item => item.key === selection.key)?.title || selection.key : w(...names[step]);
    let details = steps[step];
    if (type === 'home' || !S.data) { title = w('Inicio','Overview','Visão geral'); details = {goal:['Abre un proyecto existente, crea uno con tu estructura o practica con una copia ficticia independiente.', 'Open an existing project, create one with your structure or practice in a separate fictional copy.', 'Abra um projeto existente, crie um com sua estrutura ou pratique em uma cópia fictícia independente.'], example:['Para empezar sin tocar tu trabajo: Crear práctica ficticia. Para continuar: abre tu proyecto en el catálogo.', 'To start without changing your work: Create fictional practice. To continue: open your project in the catalog.', 'Para começar sem alterar seu trabalho: Criar prática fictícia. Para continuar: abra seu projeto no catálogo.']}; }
    else if (type === 'section' && selection.key !== 'scope') details = {goal:['Esta sección forma parte del contenido del informe. Redacta para su destinatario y revisa el resultado en la vista previa.', 'This section forms part of the report content. Write for its audience and check the result in preview.', 'Esta seção faz parte do conteúdo do relatório. Escreva para o público e confira o resultado na prévia.'], example:['En un resumen ejecutivo, explica impacto y decisiones. En metodología, describe las pruebas y sus limitaciones con trazabilidad.', 'In an executive summary, explain impact and decisions. In methodology, describe tests and limitations with traceability.', 'Em um resumo executivo, explique o impacto e as decisões. Na metodologia, descreva os testes e suas limitações com rastreabilidade.']};
    else if (type === 'capture') {title = w('Bandeja de captura','Capture inbox','Caixa de capturas'); details = {goal:['Conserva observaciones privadas y decide cuáles incorporar al informe. Capturar no crea automáticamente un hallazgo verificado.', 'Keep private observations and choose which to include in the report. Capturing does not automatically create a verified finding.', 'Guarde observações privadas e escolha quais incluir no relatório. Capturar não cria automaticamente um achado verificado.'], example:['Guarda una petición, una nota y una imagen; comprueba el resultado antes de incorporarlo a un hallazgo.', 'Keep a request, a note and an image; verify the result before incorporating it into a finding.', 'Guarde uma requisição, uma nota e uma imagem; verifique o resultado antes de incorporá-lo a um achado.']};}
    else if (type === 'studio' && selection.idx === 'library') {title = w('Biblioteca','Library','Biblioteca'); details = {goal:['Compara diseños de informe y reutiliza plantillas de hallazgos. El diseño y la estructura del contenido son decisiones distintas.', 'Compare report designs and reuse finding templates. Design and content structure are separate choices.', 'Compare modelos de relatório e reutilize modelos de achados. O design e a estrutura do conteúdo são escolhas distintas.'], example:['Elige una apariencia corporativa para el informe y adapta una plantilla de hallazgo a las observaciones verificadas de este proyecto.', 'Choose a corporate report appearance and adapt a finding template to this project’s verified observations.', 'Escolha uma aparência corporativa para o relatório e adapte um modelo de achado às observações verificadas deste projeto.']};}
    else if (type === 'workflow') {
      const workflow = selection.idx;
      title = document.querySelector('[data-workflow="' + String(workflow).replace(/[^a-z_]/g,'') + '"]')?.textContent || w('Herramientas del proyecto','Project tools','Ferramentas do projeto');
      const definitions = {
        evidence:steps[3], review:steps[4], backup:steps[5],
        assets:{goal:['Registra los objetivos y vincúlalos con hallazgos y cobertura.', 'Register targets and link them with findings and coverage.', 'Registre os alvos e vincule-os aos achados e à cobertura.'],example:['API de pruebas → activo API-01 → hallazgos relacionados y comprobaciones realizadas.', 'Test API → asset API-01 → related findings and performed checks.', 'API de testes → ativo API-01 → achados relacionados e verificações realizadas.']},
        coverage:{goal:['Distingue las pruebas planificadas, realizadas, bloqueadas y no aplicables. El estado debe reflejar tu trabajo real.', 'Distinguish planned, performed, blocked and not applicable tests. Status must reflect your actual work.', 'Diferencie os testes planejados, realizados, bloqueados e não aplicáveis. O estado deve refletir seu trabalho real.'],example:['Control de autorización: realizado con cuentas A/B; prueba bloqueada: sin acceso a la consola administrativa.', 'Authorization control: performed with accounts A/B; blocked test: no access to the administration console.', 'Controle de autorização: realizado com contas A/B; teste bloqueado: sem acesso ao console administrativo.']},
        http_evidence:{goal:['Conserva peticiones y respuestas originales privadas; prepara y revisa la copia que saldrá en el informe.', 'Retain private original requests and responses; prepare and review the copy included in the report.', 'Preserve requisições e respostas originais privadas; prepare e revise a cópia incluída no relatório.'],example:['Oculta Authorization y cookies en la copia publicada y comprueba que conserve el resultado técnico relevante.', 'Conceal Authorization and cookies in the published copy and check that the relevant technical result remains clear.', 'Oculte Authorization e cookies na cópia publicada e confira se o resultado técnico relevante continua claro.']},
        assessment_cases:{goal:['Organiza casos de prueba y registra resultados junto con sus evidencias. Leer la guía no ejecuta ni aprueba pruebas.', 'Organize test cases and record results with their evidence. Reading the guide neither executes nor approves tests.', 'Organize casos de teste e registre resultados com evidências. Ler o guia não executa nem aprova testes.'],example:['Caso: autorización horizontal. Precondición: dos cuentas. Resultado esperado: acceso rechazado entre cuentas.', 'Case: horizontal authorization. Precondition: two accounts. Expected result: access between accounts denied.', 'Caso: autorização horizontal. Pré-condição: duas contas. Resultado esperado: acesso entre contas negado.']},
        assessment_paths:{goal:['Relaciona condiciones y hallazgos para explicar una ruta de ataque, diferenciando pasos observados de hipótesis.', 'Connect conditions and findings to explain an attack path, distinguishing observed steps from hypotheses.', 'Relacione condições e achados para explicar um caminho de ataque, diferenciando etapas observadas de hipóteses.'],example:['Acceso inicial demostrado → permiso excesivo observado → impacto potencial pendiente de validar.', 'Demonstrated initial access → observed excessive permission → potential impact pending validation.', 'Acesso inicial demonstrado → permissão excessiva observada → impacto potencial pendente de validação.']},
        root_causes:{goal:['Agrupa hallazgos con una causa común para proponer una corrección coherente.', 'Group findings with a shared cause to propose consistent remediation.', 'Agrupe achados com uma causa comum para propor uma correção coerente.'],example:['Varias API sin autorización por objeto → control centralizado y pruebas de regresión por recurso.', 'Several APIs without object authorization → centralized control and per-resource regression tests.', 'Várias APIs sem autorização por objeto → controle centralizado e testes de regressão por recurso.']},
        remediation_tasks:{goal:['Asigna acciones, responsables y fechas sin confundir una tarea cerrada con una corrección verificada.', 'Assign actions, owners and dates without confusing a closed task with a verified fix.', 'Atribua ações, responsáveis e datas sem confundir uma tarefa encerrada com uma correção verificada.'],example:['Equipo API: implementar control de propietario; pentester: comprobarlo en retest y adjuntar evidencia.', 'API team: implement ownership control; pentester: verify it during retest and attach evidence.', 'Equipe de API: implementar controle de proprietário; pentester: verificar no reteste e anexar evidências.']},
        retest:{goal:['Comprueba la corrección por instancia y conserva el resultado y la evidencia de cada retest.', 'Verify remediation per instance and retain each retest result and its evidence.', 'Verifique a correção por instância e preserve o resultado e as evidências de cada reteste.'],example:['La versión corregida rechaza la petición original; registra fecha, entorno, resultado y evidencia.', 'The fixed version rejects the original request; record date, environment, result and evidence.', 'A versão corrigida rejeita a requisição original; registre data, ambiente, resultado e evidência.']},
        retest_diff:{goal:['Compara revisiones para identificar cambios y separar una edición de una corrección comprobada.', 'Compare revisions to identify changes and distinguish an edit from a verified fix.', 'Compare revisões para identificar alterações e diferenciar uma edição de uma correção verificada.'],example:['Un texto cambiado no demuestra remediación; revisa las instancias y los resultados de retest asociados.', 'Changed text does not demonstrate remediation; inspect associated instances and retest results.', 'Um texto alterado não demonstra correção; revise as instâncias e os resultados de reteste associados.']},
        retest_matrix:{goal:['Revisa el estado de las instancias y las verificaciones pendientes en conjunto.', 'Review instance status and pending verifications together.', 'Revise em conjunto o estado das instâncias e as verificações pendentes.'],example:['Un hallazgo afecta tres activos: dos instancias corregidas y una pendiente requieren una conclusión distinta.', 'A finding affects three assets: two fixed instances and one pending instance require a distinct conclusion.', 'Um achado afeta três ativos: duas instâncias corrigidas e uma pendente exigem uma conclusão distinta.']},
        history:{goal:['Consulta revisiones guardadas y conserva la trazabilidad antes de entregar o recuperar una copia.', 'Inspect saved revisions and retain traceability before delivery or recovery.', 'Consulte revisões salvas e preserve a rastreabilidade antes de entregar ou recuperar uma cópia.'],example:['Compara la revisión entregada con la revisión posterior al retest y documenta los cambios relevantes.', 'Compare the delivered revision with the post-retest revision and document relevant changes.', 'Compare a revisão entregue com a revisão posterior ao reteste e documente as alterações relevantes.']},
        review_exchange:{goal:['Prepara el intercambio de revisión y evalúa los comentarios recibidos antes de incorporarlos.', 'Prepare the review exchange and evaluate returned comments before incorporating them.', 'Prepare a troca de revisão e avalie os comentários recebidos antes de incorporá-los.'],example:['Un cliente comunica una corrección; conserva su comentario y verifica el resultado antes de cambiar el estado técnico.', 'A client reports a fix; retain the comment and verify the result before changing technical status.', 'Um cliente informa uma correção; preserve o comentário e verifique o resultado antes de alterar o estado técnico.']},
        tickets:{goal:['Vincula el seguimiento externo con el hallazgo y revisa qué información compartirás.', 'Link external tracking with the finding and review the information you will share.', 'Vincule o acompanhamento externo ao achado e revise as informações a compartilhar.'],example:['Un ticket cerrado por el equipo requiere un retest independiente antes de declarar corregida la vulnerabilidad.', 'A ticket closed by the team requires an independent retest before declaring the vulnerability fixed.', 'Um chamado encerrado pela equipe exige um reteste independente antes de declarar a vulnerabilidade corrigida.']},
        library:{goal:['Reutiliza modelos de redacción y adáptalos al resultado real de tu evaluación.', 'Reuse writing templates and adapt them to your actual assessment result.', 'Reutilize modelos de redação e adapte-os ao resultado real da avaliação.'],example:['Una plantilla de autorización sirve como estructura; sustituye los ejemplos por tus observaciones verificadas.', 'An authorization template provides structure; replace its examples with your verified observations.', 'Um modelo de autorização fornece a estrutura; substitua os exemplos por suas observações verificadas.']}
      };
      details = definitions[workflow] || steps[4];
    } else if (type === 'insights') {
      title = document.querySelector('[data-insights-tab][aria-current="page"]')?.textContent || w('Análisis y revisión','Analysis and review','Análise e revisão');
      const definitions = {
        claims: {goal:['Relaciona afirmaciones con evidencias y distingue observaciones, inferencias e hipótesis.', 'Connect claims to evidence and distinguish observations, inferences and hypotheses.', 'Relacione afirmações às evidências e diferencie observações, inferências e hipóteses.'],example:['Observación: respuesta 200 con el registro ajeno. Inferencia: falta autorización por objeto. Hipótesis: otros recursos podrían verse afectados.', 'Observation: a 200 response with another account’s record. Inference: missing object authorization. Hypothesis: other resources may be affected.', 'Observação: resposta 200 com registro de outra conta. Inferência: falta autorização por objeto. Hipótese: outros recursos podem ser afetados.']},
        risk: {goal:['Explica decisiones de negocio con impacto, supuestos y responsables. Una puntuación técnica no determina el riesgo de negocio por sí sola.', 'Explain business decisions through impact, assumptions and owners. A technical score alone does not determine business risk.', 'Explique decisões de negócio com impacto, premissas e responsáveis. Uma pontuação técnica não determina sozinha o risco de negócio.'],example:['Priorizar la API de pagos por exposición y criticidad; registrar los supuestos y quién acepta el riesgo residual.', 'Prioritize the payments API based on exposure and criticality; record assumptions and who accepts residual risk.', 'Priorize a API de pagamentos pela exposição e criticidade; registre premissas e quem aceita o risco residual.']},
        review: {goal:['Registra observaciones y decisiones editoriales sobre una revisión concreta. La aceptación editorial no verifica vulnerabilidades.', 'Record comments and editorial decisions against a specific revision. Editorial acceptance does not verify vulnerabilities.', 'Registre observações e decisões editoriais sobre uma revisão específica. A aceitação editorial não verifica vulnerabilidades.'],example:['Pedir una explicación más clara del impacto y registrar su resolución antes de aceptar la redacción.', 'Request a clearer impact explanation and record its resolution before accepting the wording.', 'Solicite uma explicação mais clara do impacto e registre sua resolução antes de aceitar a redação.']},
        audiences: {goal:['Prepara una entrega para un destinatario concreto y revisa el contenido incluido antes de exportar.', 'Prepare a delivery for a specific audience and review included content before export.', 'Prepare uma entrega para um público específico e revise o conteúdo incluído antes de exportar.'],example:['Dirección recibe un resumen ejecutivo; el equipo técnico recibe detalles y evidencias revisadas según su necesidad.', 'Management receives an executive summary; the technical team receives details and reviewed evidence as needed.', 'A direção recebe um resumo executivo; a equipe técnica recebe detalhes e evidências revisadas conforme necessário.']},
        visual: {goal:['Inspecciona páginas y registra observaciones sobre el archivo y la revisión concretos. Generar sin errores no demuestra que el formato sea correcto.', 'Inspect pages and record observations about the exact file and revision. Error-free generation does not prove correct formatting.', 'Inspecione páginas e registre observações sobre o arquivo e a revisão específicos. Gerar sem erros não comprova uma diagramação correta.'],example:['Revisar saltos de página, tablas extensas, pies de evidencia e índice en el PDF generado.', 'Review page breaks, long tables, evidence captions and the table of contents in the generated PDF.', 'Revise quebras de página, tabelas extensas, legendas de evidências e sumário no PDF gerado.']},
        editorial: {goal:['Usa la ayuda editorial para proponer redacción y revisa los cambios antes de aplicarlos. Las propuestas no son resultados técnicos.', 'Use editorial assistance to propose wording and review changes before applying them. Proposals are not technical results.', 'Use a assistência editorial para propor redação e revise as alterações antes de aplicá-las. As propostas não são resultados técnicos.'],example:['Pedir claridad y concisión manteniendo evidencia, limitaciones y nivel de certeza; aceptar únicamente lo que hayas comprobado.', 'Request clarity and concision while preserving evidence, limitations and certainty; accept only what you have verified.', 'Peça clareza e concisão preservando evidências, limitações e grau de certeza; aceite apenas o que verificou.']}
      };
      details = definitions[selection.idx] || steps[4];
    } else if (type === 'guide') {title = w('Ayuda y orientación','Help and guidance','Ajuda e orientação'); details = {goal:['Consulta ejemplos y explicaciones. La lectura y el progreso de aprendizaje no cambian los estados técnicos del proyecto.', 'Read examples and explanations. Reading and learning progress do not change project technical states.', 'Consulte exemplos e explicações. A leitura e o progresso de aprendizagem não alteram os estados técnicos do projeto.'],example:['Puedes pausar, reanudar o reiniciar el recorrido sin modificar hallazgos, evidencias ni retests.', 'Pause, resume or restart the walkthrough without changing findings, evidence or retests.', 'Pause, retome ou reinicie o percurso sem alterar achados, evidências ou retestes.']};}
    return {title, ...details};
  }
  function helpContent() {
    const details = contextHelp(), box = h('section', {'data-onboarding-help':'', class:'onboarding-help', 'aria-labelledby':'onboardingHelpTitle'});
    box.append(h('div', {class:'onboarding-heading'}, h('h2', {id:'onboardingHelpTitle', tabindex:-1}, w('Explícame esta sección','Explain this section','Explique esta seção') + ': ' + details.title),
      button(w('Cerrar ayuda','Close help','Fechar ajuda'), 'close-help', () => {helpOpen = false; refresh(); focusControl('onboardingHelpBtn');})),
      h('p', {}, w(...details.goal)), h('p', {class:'onboarding-example'}, h('strong', {}, w('Ejemplo ficticio: ','Fictional example: ','Exemplo fictício: ')), w(...details.example)));
    return box;
  }
  function routeContent() {
    const current = route(), box = h('section', {class:'onboarding-route','aria-labelledby':'onboardingStepTitle'});
    const header = h('div', {class:'onboarding-heading'}, h('p', {class:'onboarding-eyebrow'}, w('RECORRIDO OPCIONAL','OPTIONAL WALKTHROUGH','PERCURSO OPCIONAL') + ' · ' + (current.step + 1) + '/6'),
      button(w('Pausar recorrido','Pause walkthrough','Pausar percurso'), 'pause', () => {changeRoute({active:false}); focusControl('onboardingRouteBtn');}));
    const navigation = h('nav', {class:'onboarding-steps', 'aria-label':w('Pasos del recorrido','Walkthrough steps','Etapas do percurso')});
    names.forEach((name, index) => {
      const control = button((index + 1) + ' ' + w(...name), 'step-' + index, () => move(index));
      control.dataset.onboardingStep = String(index); control.setAttribute('aria-current', current.step === index ? 'step' : 'false'); navigation.append(control);
    });
    box.append(header, navigation, h('h2', {id:'onboardingStepTitle', tabindex:-1}, w(...names[current.step])),
      h('p', {id:'onboardingStepPurpose'}, w(...steps[current.step].goal)),
      h('p', {class:'onboarding-example'}, h('strong', {}, w('Ejemplo ficticio: ','Fictional example: ','Exemplo fictício: ')), w(...steps[current.step].example)));
    if (current.step === 1 && S.data && !isScope()) box.append(h('p', {class:'onboarding-note'}, w('Este informe no tiene la sección Alcance. Puedes incorporarla desde Secciones del informe → Gestionar secciones; el recorrido la deja intacta.', 'This report has no Scope section. You can add it through Report sections → Manage sections; the walkthrough leaves it unchanged.', 'Este relatório não possui a seção Escopo. Você pode adicioná-la em Seções do relatório → Gerenciar seções; o percurso não a altera.')));
    if (!S.data) box.append(h('p', {class:'onboarding-note'}, w('Puedes leer los seis pasos sin crear nada. Abre un proyecto o crea una práctica para probar los controles.', 'Read all six steps without creating anything. Open a project or create a practice copy to try the controls.', 'Leia as seis etapas sem criar nada. Abra um projeto ou crie uma cópia de prática para experimentar os controles.')));
    const actions = h('div', {class:'onboarding-actions'});
    const back = button(w('Anterior','Back','Anterior'), 'back', () => move(current.step - 1)); back.disabled = current.step === 0 || !!busy();
    actions.append(back, button(S.data ? w('Abrir este paso','Open this step','Abrir esta etapa') : w('Ir al inicio','Go to overview','Ir para o início'), 'open', openStep, true),
      button(current.step === 5 ? w('Finalizar lectura','Finish reading','Concluir leitura') : w('Siguiente','Next','Próximo'), 'next', () => {if (current.step === 5) {changeRoute({active:false,completed:true});focusControl('onboardingRouteBtn');} else move(current.step + 1);}),
      button(w('Reiniciar','Restart','Reiniciar'), 'restart', () => start(true)));
    box.append(actions, h('p', {class:'onboarding-note'}, w('Avanzar, saltar pasos o finalizar solo registra tu recorrido. No verifica ni aprueba el informe.', 'Moving forward, skipping steps or finishing only records your walkthrough. It does not verify or approve the report.', 'Avançar, pular etapas ou concluir registra apenas seu percurso. Não verifica nem aprova o relatório.')));
    if (current.step === 0 && S.data && S.sel.type !== 'home') box.append(h('div', {class:'onboarding-practice'}, h('span', {}, w('Aprende en una copia separada con datos ficticios.', 'Learn in a separate copy with fictional data.', 'Aprenda em uma cópia separada com dados fictícios.')), button(w('Crear práctica ficticia','Create fictional practice','Criar prática fictícia'), 'practice', practice)));
    if (preference().mode === 'guided' && typeof GuideUI !== 'undefined') {
      const next = GuideUI.nextAction(S.data, typeof WorkflowUI !== 'undefined' ? WorkflowUI.reviewSnapshot?.() : null);
      const hint = h('p', {class:'onboarding-next'}, h('strong', {}, w('Siguiente tarea sugerida: ','Suggested next task: ','Próxima tarefa sugerida: ')), w(...next.title));
      box.append(hint);
    }
    return box;
  }
  function afterRender() {
    if (!bound) return;
    const editor = document.querySelector('#editor'); if (!editor) return;
    const prior = document.querySelector('#onboardingPanel'), focused = prior?.contains(document.activeElement) ? document.activeElement : null;
    const action = focused?.dataset.onboardingAction, heading = focused?.id;
    clearHighlight(); prior?.remove();
    const scope = storageKey() + '|' + (S.slug || '');
    if (helpScope && helpScope !== scope) {helpOpen = false;document.querySelector('#onboardingHelpBtn')?.setAttribute('aria-expanded','false');}
    helpScope = scope;
    if (!route().active && !helpOpen) return;
    const panel = h('aside', {id:'onboardingPanel', class:'onboarding-panel', 'data-onboarding-current':String(route().step), 'aria-label':w('Ayuda contextual','Contextual guidance','Orientação contextual')});
    if (route().active) panel.append(routeContent());
    if (helpOpen) panel.append(helpContent());
    if (!preference().storageAvailable) panel.append(storageNote());
    editor.prepend(panel); highlight();
    if (focused) {
      const replacement = action ? [...panel.querySelectorAll('[data-onboarding-action]')].find(node => node.dataset.onboardingAction === action) : heading ? document.getElementById(heading) : null;
      replacement?.focus({preventScroll:true});
    }
  }
  function update() {
    if (!bound) return;
    const current = state(), control = document.querySelector('#onboardingMode');
    document.documentElement.dataset.experience = current.mode || 'complete';
    control.value = current.mode || '';
    control.options[0].disabled = !!current.mode;
    control.setAttribute('aria-label', w('Vista de trabajo','Workspace view','Visualização de trabalho'));
    control.options[0].textContent = w('Elegir vista','Choose view','Escolher visualização');
    control.options[1].textContent = w('Guiado','Guided','Guiado'); control.options[2].textContent = w('Completo','Complete','Completo');
    document.querySelector('#onboardingModeLabel').textContent = w('Vista','View','Visualização');
    const launch = document.querySelector('#onboardingRouteBtn');
    launch.textContent = current.active ? w('Pausar guía','Pause guide','Pausar guia') : current.visited.length ? w('Reanudar guía','Resume guide','Retomar guia') : w('Recorrido','Walkthrough','Percurso');
    launch.setAttribute('aria-expanded', String(current.active)); launch.setAttribute('aria-controls','onboardingPanel');
    const help = document.querySelector('#onboardingHelpBtn');
    help.textContent = w('Explícame esta sección','Explain this section','Explique esta seção'); help.setAttribute('aria-expanded',String(helpOpen)); help.setAttribute('aria-controls','onboardingPanel');
    for (const node of document.querySelectorAll('[data-onboarding-action], #onboardingMode')) node.disabled = !!busy() || node.dataset.onboardingAction === 'back' && route().step === 0;
    const signature = (storageKey() || '') + ':' + current.mode;
    if (applied !== signature) {
      // Only set defaults on first application / mode change. Native details
      // remain operable, and the current group is always left open.
      if (current.mode) for (const id of advanced) {
        const group = document.getElementById(id);
        if (group) group.open = current.mode === 'complete' || group.classList.contains('has-current') || !!group.querySelector('[aria-current="page"]') || group.contains(document.activeElement);
      }
      applied = signature;
    }
  }
  function refresh() {
    update();
    document.querySelectorAll('[data-onboarding-entry]').forEach(node => node.replaceWith(entry()));
    afterRender();
  }
  function bind() {
    if (bound || !document.querySelector('#workspaceSidebar')) return;
    bound = true;
    const selectMode = h('select', {id:'onboardingMode'}, h('option',{value:''},''), h('option',{value:'guided'},''), h('option',{value:'complete'},''));
    selectMode.addEventListener('change', () => {if (selectMode.value) choose(selectMode.value);});
    const row = h('div', {class:'onboarding-mode-row'}, h('label', {for:'onboardingMode',id:'onboardingModeLabel'}), selectMode);
    const launcher = button('', 'toggle-route', () => route().active ? changeRoute({active:false}) : start()); launcher.id = 'onboardingRouteBtn';
    const help = button('', 'toggle-help', () => {helpOpen = !helpOpen; closeMobileNavigation(); refresh(); if (helpOpen) {document.querySelector('#onboardingHelpTitle')?.focus(); document.querySelector('#onboardingHelpTitle')?.scrollIntoView?.({block:'nearest'});}}); help.id = 'onboardingHelpBtn';
    const host = document.querySelector('#workspaceSidebar [data-sidebar-group="project"]') || document.querySelector('#workspaceSidebar');
    host.prepend(h('div', {class:'onboarding-controls'}, row, h('div',{class:'onboarding-control-actions'},launcher,help)));
    if (typeof MutationObserver !== 'undefined') new MutationObserver(() => {if (typeof document !== 'undefined' && document?.documentElement?.isConnected) highlight();}).observe(document.querySelector('#editor'), {childList:true,subtree:true});
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && helpOpen && !document.querySelector('dialog[open],.modal.open') && document.querySelector('#onboardingPanel')?.contains(document.activeElement)) {
        event.preventDefault(); helpOpen = false; refresh(); focusControl('onboardingHelpBtn');
      }
    });
    update();
  }
  return {bind, update, afterRender, entry, state};
})();

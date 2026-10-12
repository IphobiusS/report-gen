/* Report appearances are independent of report content. All mutations use revisions. */
const DesignLibraryUI=(()=>{
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const local=(v,lang=S.uiLang)=>v&&typeof v==='object'?(v[lang]||v.es||v.en||''):v;
  const layouts={rail:['Banda lateral','Side rail'],split:['Dos zonas','Split cover'],frame:['Marco','Frame'],band:['Franja central','Center band'],timeline:['Cronología','Timeline'],editorial:['Informe editorial','Editorial report']};
  const generalNames={serio:['Serio','Serious'],corporativo:['Corporativo','Corporate'],offsec:['OffSec (general)','OffSec (general)'],htb:['HTB (general)','HTB (general)'],ejecutivo:['Ejecutivo','Executive'],laboratorio:['Laboratorio','Laboratory']};
  const generalNotes={serio:['Lectura sobria y estructura general. Recomendado para empezar.','Restrained presentation and a general structure. Recommended starting point.'],corporativo:['Presentación para clientes con identidad corporativa.','Client reports with corporate branding.'],offsec:['Estética técnica inspirada en laboratorios.','Technical appearance inspired by labs.'],htb:['Estética de laboratorio con acento verde.','Lab appearance with a green accent.'],ejecutivo:['Presentación orientada a la lectura de resultados.','Presentation focused on reading results.'],laboratorio:['Presentación técnica para documentar ejercicios.','Technical presentation for documenting exercises.']};
  const generalItem=id=>({id,name:generalNames[id]?w(...generalNames[id]):id,provider:'General'});
  let catalog=null,etag=null,trigger=null,creationDraft=null,openingProject=false;
  const categories={all:['Todas','All'],general:['Generales','General'],corporate:['Empresariales','Corporate'],'red-team':['Red Team','Red Team'],'blue-team':['Blue Team','Blue Team'],certification:['Certificaciones','Certifications'],personal:['Mis plantillas','My designs']};
  function btn(label,fn,primary=false){const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},label);b.addEventListener('click',async()=>{trigger=b;b.disabled=true;try{await fn(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;}
  function modal(title,wide=false,opener=null){const focus=opener||(document.activeElement===document.body?trigger:document.activeElement);
    const d=h('dialog',{class:'experience-dialog'+(wide?' design-dialog':''),'aria-label':title});const body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),btn(w('Cerrar','Close'),()=>d.close())),body);
    d.addEventListener('close',()=>{d.remove();requestAnimationFrame(()=>{const open=[...document.querySelectorAll('dialog[open]')].at(-1),target=focus?.closest('details:not([open])')?.querySelector('summary')||focus;if(open?.contains(document.activeElement))return;if(target?.isConnected&&!target.disabled&&(!open||open.contains(target)))target.focus();else if(open)open.querySelector('button')?.focus();else $('#designLibraryBtn')?.focus();});});document.body.append(d);d.showModal();return {d,body};}
  function livePage(html,page='cover') {
    const box=h('div',{class:'design-live-page'});
    const target={cover:'.cover',summary:'#sample-summary',technical:'#sample-technical'}[page]||'.cover';
    const style='<style>@media screen{body{margin:0;background:white}body > *{display:none!important}body > '+target+'{display:block!important}body > .frontsec{margin:20mm;width:170mm;box-sizing:border-box}}</style>';
    const frame=h('iframe',{title:w('Vista previa real','Actual report preview'),sandbox:'allow-same-origin',srcdoc:html.replace('</head>',style+'</head>')});box.append(frame);
    const observer=new ResizeObserver(()=>{const scale=Math.min(1,box.clientWidth/794);frame.style.transform='scale('+scale+')';box.style.height=(1123*scale)+'px';});
    observer.observe(box);
    const cleanup=new MutationObserver(()=>{if(!box.isConnected){observer.disconnect();cleanup.disconnect();}});
    requestAnimationFrame(()=>{if(box.isConnected)cleanup.observe(document.body,{childList:true,subtree:true});else observer.disconnect();});
    return box;
  }
  async function refresh(){const r=await requireOk(await appFetch('/api/design-library'));etag=r.headers.get('ETag');catalog=await r.json();}
  async function write(url,body,method='POST'){const r=await requireOk(await appFetch(url,{method,headers:{'Content-Type':'application/json','If-Match':etag},...(body?{body:JSON.stringify(body)}:{})}));etag=r.headers.get('ETag');return r.json();}
  function guideBox(g){return h('div',{class:'design-guidance'},h('p',{},g.note),h('a',{href:g.source,target:'_blank',rel:'noopener noreferrer'},w('Consultar guía','Open guide')),h('p',{class:'wf-hint'},w('Referencia consultada: ','Reference checked: ')+g.checked));}
  async function gallery(opener=null,options={}){opener=opener||(document.activeElement!==document.body?document.activeElement:trigger);await refresh();const {d,body}=modal(options.create?w('Nuevo proyecto · Elige una plantilla','New project · Choose a design'):w('Biblioteca de informes','Report design library'),true,opener);
    const currentDesign=S.data?.meta?.design,currentId=currentDesign?.id||S.data?.meta?.theme;
    const current=(catalog.personal||[]).find(p=>p.id===currentId)||(catalog.profiles||[]).find(p=>p.id===currentId)||(catalog.general.includes(currentId)?generalItem(currentId):null);
    const saved=options.create?creationDraft:null;
    let family=saved?.family||(options.create?'All':current?.provider||'General'),category=saved?.category||(options.create||!current||current.provider==='General'?'general':'all'),query=saved?.query||'',selected=saved?saved.selected:(options.create?generalItem('serio'):current||generalItem('serio')),variant=saved?.variant||(options.create?'brand':currentDesign?.variant||'brand'),sample=saved?.sample||'cover',sampleLang=saved?.sampleLang||S.uiLang,serial=0;
    if(selected?.provider==='General')selected=generalItem(selected.id);
    const remember=()=>{if(options.create)creationDraft={family,category,query,selected,variant,sample,sampleLang,opener};};
    d.dataset.designMode=options.create?'create':'manage';d.addEventListener('close',remember);
    const purposes=h('div',{class:'design-filters design-purposes',role:'group','aria-label':w('Tipo de informe','Report type')});
    for(const [id,names] of Object.entries(categories)){const b=btn(w(...names),()=>{category=id;family='All';selected=null;renderList();renderDetail();});b.dataset.designCategory=id;purposes.append(b);}
    const purposeSelect=h('select',{'data-design-category-select':''},Object.entries(categories).map(([value,names])=>h('option',{value},w(...names))));
    purposeSelect.addEventListener('change',()=>{category=purposeSelect.value;family='All';selected=null;renderList();renderDetail();});
    const sampleLanguage=h('select',{'data-design-sample-language':'','aria-label':w('Idioma de las muestras','Sample language')},h('option',{value:'es'},'Español'),h('option',{value:'en'},'English'));sampleLanguage.value=sampleLang;
    sampleLanguage.addEventListener('change',()=>{sampleLang=sampleLanguage.value;renderList();renderDetail();});
    const samplePath=(id,v,page)=>'/static/design-previews/'+id+'/'+(sampleLang==='en'?'en/':'')+v+'-'+page+'.webp';
    const filters=h('div',{class:'design-filters',role:'group','aria-label':w('Familias','Families')});
    const search=h('input',{type:'search',placeholder:w('Busca un diseño, especialidad o certificación','Search a design, specialty or certification'),'aria-label':w('Buscar plantillas','Search designs')});
    const listing=h('div',{class:'design-cards'}),detail=h('div',{class:'design-detail'}),count=h('p',{role:'status',class:'wf-hint'});
    search.value=query;
    const allFamilies=['All','General',...new Set(catalog.profiles.map(p=>p.provider)),'Personal','Históricas'];
    const familyName=x=>({All:w('Todos los proveedores','All providers'),General:w('Generales','General'),Enterprise:w('Empresariales','Enterprise'),Personal:w('Mis plantillas','My designs'),'Históricas':w('Históricas','Historical')})[x]||x;
    for(const f of allFamilies){const b=btn(familyName(f),()=>{family=f;category='all';selected=null;renderList();renderDetail();});b.dataset.family=f;filters.append(b);}
    search.addEventListener('input',()=>{query=search.value.trim().toLowerCase();family='All';category='all';selected=null;renderList();renderDetail();});
    const comparison=h('select',{'data-design-compare-page':'','aria-label':w('Comparar la misma página','Compare the same page')},[['cover','Portada','Cover'],['summary','Resumen','Summary'],['technical','Técnica','Technical']].map(([value,es,en])=>h('option',{value},w(es,en))));
    comparison.addEventListener('change',()=>{sample=comparison.value;renderList();renderDetail();});
    const advanced=h('details',{class:'design-catalog-options','data-design-catalog':'',open:!['General','All'].includes(family)?'':null},h('summary',{},w('Filtrar por proveedor y consultar referencias','Filter by provider and browse references')),filters,h('p',{class:'wf-hint'},w('Los perfiles son puntos de partida editables; no acreditan cumplimiento de requisitos de certificación. Revisa las instrucciones vigentes.','Profiles are editable starting points; they do not certify compliance with certification requirements. Check the current instructions.')));
    body.append(options.create?h('ol',{class:'design-steps','aria-label':w('Pasos para crear el proyecto','Project creation steps')},h('li',{'aria-current':'step'},w('1 · Plantilla','1 · Design')),h('li',{},w('2 · Datos del proyecto','2 · Project details'))):h('p',{},w('Compara una muestra real antes de elegir. El diseño y la estructura se pueden editar después.','Compare an actual sample before choosing. Appearance and structure remain editable.')),
      h('p',{class:'wf-hint design-intro'},w('Elige un punto de partida. Compara portada, resumen y contenido técnico antes de continuar.','Choose a starting point. Compare the cover, summary and technical content before continuing.')),
      purposes,h('label',{class:'design-purpose-select'},w('Tipo de informe','Report type'),purposeSelect),h('label',{class:'design-search'},w('Buscar en todo el catálogo','Search the entire catalog'),search),
      ...(!options.create&&currentId?[h('p',{class:'design-current','data-design-current':''},w('Apariencia del proyecto: ','Project appearance: ')+(currentDesign?.name||generalItem(currentId).name))]:[]),
      advanced,h('div',{class:'grid2'},h('label',{},w('Idioma de las muestras','Sample language'),sampleLanguage),h('label',{},w('Comparar la misma página','Compare the same page'),comparison)),count,h('div',{class:'design-layout'},listing,detail));
    async function showSavedPersonal(saved){await refresh();family='Personal';category='personal';query='';search.value='';selected=catalog.personal.find(x=>x.id===saved.id)||null;variant=selected?.design.variant||'brand';renderList();await renderDetail();if(d.isConnected)listing.querySelector('[data-design="'+saved.id+'"]')?.focus({preventScroll:true});}
    function items(){const priority=id=>id==='serio'?0:id===currentId?1:2;
      if(family==='Históricas')return catalog.historical;
      const all=[...[...catalog.general].sort((a,b)=>priority(a)-priority(b)).map(generalItem),...catalog.profiles,...catalog.personal];
      return all.filter(p=>(family==='All'||p.provider===family)&&(category==='all'||(p.provider==='General'?['general']:p.provider==='Personal'?['personal']:p.categories||[]).includes(category)));}
    function renderList(){remember();purposeSelect.value=category;purposes.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.designCategory===category)));filters.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.family===family)));listing.replaceChildren();const rows=items().filter(p=>[p.name,p.course||'',p.provider,local(p.description),...(p.categories||[]).flatMap(c=>categories[c]||[])].join(' ').toLowerCase().includes(query));count.textContent=rows.length+' '+w('plantillas o referencias','designs or references');
      if(!rows.length)listing.append(h('div',{class:'design-empty'},h('h3',{},w('No hay coincidencias','No matching designs')),h('p',{},category==='personal'||family==='Personal'?w('Duplica un perfil desde la biblioteca para guardar tu primera plantilla personal.','Duplicate a profile in the library to save your first personal design.'):w('Prueba otro término o amplía los filtros.','Try another search or broaden the filters.')),btn(w('Ver todas las plantillas','View all designs'),()=>{family='All';category='all';query='';search.value='';renderList();search.focus();})));
      rows.forEach(p=>{if(family==='Históricas'){listing.append(h('article',{class:'design-history'},h('h3',{},p.name),h('p',{},local(p.note)),h('a',{href:p.source,target:'_blank',rel:'noopener noreferrer'},w('Fuente','Source'))));return;}
        const card=btn('',()=>{if(selected?.id!==p.id)variant=p.provider==='Personal'?p.design.variant:'brand';selected=p;renderList();renderDetail();listing.querySelector('[data-design="'+p.id+'"]')?.focus({preventScroll:true});});card.classList.add('design-card');card.dataset.design=p.id;card.setAttribute('aria-pressed',String(selected?.id===p.id));
        if(p.provider!=='Personal')card.append(h('img',{src:samplePath(p.id,'brand',sample),alt:'',loading:'lazy',width:210,height:297}));
        else card.append(h('div',{class:'design-personal-swatch',style:'border-color:'+p.design.accent},p.design.certificate));
        card.append(h('strong',{},p.name),h('span',{},p.id==='serio'?w('Inicio recomendado','Recommended starting point'):p.course||familyName(p.provider)));if(!options.create&&p.id===currentId)card.append(h('span',{class:'design-current-badge'},w('Actual','Current')));listing.append(card);});}
    async function renderDetail(){remember();const turn=++serial;detail.replaceChildren();if(!selected){detail.append(h('h3',{},w('Elige una plantilla','Choose a design')),h('p',{},w('Crear un proyecto incorpora la estructura. Aplicar apariencia conserva tus secciones, hallazgos y evidencias.','Creating a project adds the structure. Applying an appearance preserves your sections, findings and evidence.')));return;}
      const p=selected;detail.append(h('h3',{},p.name));
      detail.append(h('p',{class:'wf-hint'},p.provider==='General'&&generalNotes[p.id]?w(...generalNotes[p.id]):local(p.description)||w('Perfil especializado. Revisa su estructura y las instrucciones de referencia.','Specialized profile. Review its structure and reference instructions.')));
      if(p.provider!=='General'){
        const v=h('select',{'data-design-variant':'','aria-label':w('Variante de diseño','Design variant')},h('option',{value:'brand'},w('Marca','Brand')),h('option',{value:'quiet'},w('Sobria','Quiet')));v.value=variant;v.addEventListener('change',()=>{variant=v.value;renderDetail();detail.querySelector('[data-design-variant]')?.focus();});detail.append(h('label',{},w('Apariencia','Appearance'),v));
      }
      const samples=h('div',{class:'design-filters'}),preview=h('div',{class:'design-preview'});
      for(const [id,es,en] of [['cover','Portada','Cover'],['summary','Resumen','Summary'],['technical','Técnica','Technical']]){const b=btn(w(es,en),()=>{sample=id;comparison.value=id;renderList();renderDetail();detail.querySelector('[data-design-sample="'+id+'"]')?.focus({preventScroll:true});});b.dataset.designSample=id;b.setAttribute('aria-pressed',String(sample===id));samples.append(b);}
      detail.append(samples,preview,h('p',{class:'wf-hint'},w('Muestra ficticia. Calibri en Word; Carlito en PDF. Código monoespaciado.','Fictional sample. Calibri in Word; Carlito in PDF. Monospaced code.')));
      if(p.provider==='Personal'){
        preview.append(h('p',{role:'status'},w('Generando vista previa real…','Rendering actual preview…')));
        try{const response=await requireOk(await api.post('/api/design-library/preview',{id:p.id,variant,lang:sampleLang}));const html=await response.text();if(serial!==turn||!d.isConnected)return;
          preview.replaceChildren(livePage(html,sample));
        }catch(e){if(serial===turn)preview.replaceChildren(h('p',{role:'alert'},e.message));}
      }else preview.append(h('a',{href:samplePath(p.id,p.provider==='General'?'brand':variant,sample),target:'_blank',rel:'noopener noreferrer'},h('img',{src:samplePath(p.id,p.provider==='General'?'brand':variant,sample),alt:p.name+' / '+sample,width:595,height:842})));
      const actions=h('div',{class:'experience-actions'});
      actions.append(btn(options.create?w('Continuar con esta plantilla','Continue with this design'):w('Crear proyecto','Create project'),()=>{creationDraft={family,category,query,selected:p,variant,sample,sampleLang,opener};configureProject(p,variant,d,sampleLang,opener);},true));
      if(S.slug&&!options.create)actions.append(btn(w('Aplicar apariencia','Apply appearance'),async()=>{if(!await doSave())return;const slug=S.slug;busyProject(true);try{
        await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/design',{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(p.provider==='General'?{general:p.id}:{id:p.id,variant})}));d.close();await loadProject(slug);select('report');toast(w('Apariencia aplicada. El contenido se conserva.','Appearance applied. Content preserved.'),'ok');
      }finally{busyProject(false);}}));
      if(p.provider!=='General'&&!options.create)actions.append(btn(w('Duplicar y personalizar','Duplicate and customize'),()=>editPersonal({...p,design:{...p.design,variant}},false,showSavedPersonal)));
      if(p.provider==='Personal'&&!options.create)actions.append(btn(w('Editar plantilla','Edit design'),()=>editPersonal({...p,design:{...p.design,variant}},true,showSavedPersonal)),btn(w('Eliminar plantilla','Delete design'),async()=>{
        const {d:confirm,body:cb}=modal(w('Eliminar plantilla personal','Delete personal design'));cb.append(h('p',{},w('Los proyectos que ya la usan conservarán su apariencia.','Projects already using this design will keep their appearance.')),btn(w('Confirmar eliminación','Confirm deletion'),async()=>{await write('/api/design-library/personal/'+p.id,null,'DELETE');confirm.close();await refresh();selected=null;renderList();renderDetail();}));
      }));
      detail.insertBefore(actions,samples);
      detail.insertBefore(h('p',{class:'wf-hint'},options.create?w('A continuación podrás indicar título, cliente, idioma y carpeta. No se crea nada hasta confirmar.','Next, enter the title, client, language and folder. Nothing is created until you confirm.'):w('Crear incorpora la estructura en un proyecto nuevo. Aplicar apariencia conserva las secciones, hallazgos y evidencias del proyecto abierto.','Create adds the structure to a new project. Apply appearance preserves the sections, findings and evidence of the open project.')),actions);
      if(p.sections){const list=h('ol');p.sections.forEach(s=>list.append(h('li',{},local(s.title,sampleLang)||w('Hallazgos','Findings'))));detail.append(h('details',{},h('summary',{},w('Estructura inicial','Starter structure')),list));}
      if(p.guidance)detail.append(guideBox({...p.guidance,note:local(p.guidance.note)}));
    }
    comparison.value=sample;renderList();renderDetail();
  }
  function configureProject(p,variant,parent,sampleLang,opener){
    const fresh=!$('#newModal').dataset.designId;
    const previousPreset=$('#mPreset').value,previousCert=$('#mCert').value;
    populatePresetSelector();
    if(fresh)$('#mPresetOptions').open=false;
    else{if([...$('#mPreset').options].some(o=>o.value===previousPreset))$('#mPreset').value=previousPreset;if(previousPreset.startsWith('family:')){fillCertOptions(previousPreset.slice(7));$('#mCert').value=previousCert;}refreshPresetDesc();}
    $('#newModal').dataset.designId=p.id;
    $('#mLang').value='corporativo-'+sampleLang;
    $('#mPresetOptions').hidden=p.provider!=='General';$('#mPresetSelected').hidden=p.provider!=='General';
    $('#mDesignSelected').replaceChildren(h('strong',{},p.name),h('span',{},(p.provider==='General'?w('Diseño general','General design'):variant==='quiet'?w('Variante sobria','Quiet variant'):w('Variante de marca','Brand variant'))+' · '+(p.sections?p.sections.length+' '+w('secciones iniciales','starter sections'):w('Estructura editable','Editable structure'))));
    parent?.close();openModal($('#newModal'));$('#newModal')._opener=opener||$('#newProjectBtn');$('#mTitle').focus();
  }
  async function newProject(opener=$('#newProjectBtn')){
    if(openingProject)return;openingProject=true;
    try{await gallery(opener,{create:true});}catch(e){toast(e.message,'err');}finally{openingProject=false;}
  }
  function projectRequest(){
    const p=creationDraft?.selected,lang=$('#mLang').value.split('-').at(-1);
    const fields={title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value};
    if(p&&p.provider!=='General')return {url:'/api/design-library/projects',body:{...fields,id:p.id,variant:creationDraft.variant,lang}};
    return {url:'/api/projects',body:{...fields,model:(p?.id||'corporativo')+'-'+lang,preset:selectedPresetId(),...(p?{appearance:p.id}:{})}};
  }
  function resetCreation(){creationDraft=null;delete $('#newModal').dataset.designId;}
  async function editPersonal(p,editing,done){const {d,body}=modal(w('Personalizar plantilla','Customize design'));let sections=structuredClone(p.sections);
    const design=structuredClone(p.design),name=h('input',{value:editing?p.name:p.name+' '+w('personal','personal'),maxlength:160,'data-design-field':'name'});
    const accent=h('input',{type:'color',value:design.accent,'data-design-field':'accent'}),bg=h('input',{type:'color',value:design.background,'data-design-field':'background'});
    const layout=h('select',{'data-design-field':'layout'},catalog.layouts.map(id=>h('option',{value:id},layouts[id][S.uiLang==='en'?1:0])));layout.value=design.layout;
    const preview=h('div',{class:'design-custom-preview'}),rows=h('div',{class:'design-section-editor'});
    function renderRows(){rows.replaceChildren();sections.forEach((s,i)=>{
      const row=h('div',{class:'design-section-row'}),fields=h('div',{class:'grid2'});
      if(!s.title)s.title={es:'Hallazgos',en:'Findings'};
      if(typeof s.title==='string')s.title={es:s.title,en:''};
      if(typeof s.body==='string')s.body={es:s.body,en:''};
      for(const lang of ['es','en']){
        const input=h('input',{value:s.title[lang]||'',maxlength:200,'data-section-lang':lang,'aria-label':lang==='es'?'Título de sección (ES)':'Section title (EN)'});
        input.addEventListener('input',()=>{s.title[lang]=input.value;});
        const column=h('div',{},h('label',{},lang==='es'?'Título (ES)':'Title (EN)',input));
        if(s.body){const bodyInput=h('textarea',{rows:3,'aria-label':lang==='es'?'Contenido inicial (ES)':'Starter text (EN)'},s.body[lang]||'');bodyInput.addEventListener('input',()=>{s.body[lang]=bodyInput.value;});column.append(h('label',{},lang==='es'?'Contenido inicial (ES)':'Starter text (EN)',bodyInput));}
        fields.append(column);
      }
      row.append(fields,btn(w('Quitar','Remove'),()=>{sections.splice(i,1);renderRows();}));rows.append(row);
    });}
    function read(){return {...design,name:name.value,accent:accent.value,background:bg.value,layout:layout.value};}
    body.append(h('p',{},w('Guarda el diseño y la estructura en español e inglés. Revisa ambas columnas: el contenido personal no se traduce automáticamente.','Saves the appearance and structure in Spanish and English. Review both columns: personal content is not translated automatically.')),h('label',{},w('Nombre','Name'),name),h('div',{class:'grid2'},h('label',{},w('Acento','Accent'),accent),h('label',{},w('Fondo de portada','Cover background'),bg)),h('label',{},w('Composición','Composition'),layout),
      btn(w('Actualizar vista previa','Update preview'),async()=>{const r=await requireOk(await api.post('/api/design-library/preview',{design:read(),lang:S.uiLang}));preview.replaceChildren(livePage(await r.text()));}),preview,h('h3',{},w('Secciones iniciales','Starter sections')),rows,
      btn(w('Añadir sección','Add section'),()=>{sections.push({key:'custom-'+crypto.randomUUID().replaceAll('-',''),title:{es:'Nueva sección',en:'New section'},body:{es:'TODO: Completa esta sección.',en:'TODO: Complete this section.'}});renderRows();}));
    if(S.data)body.append(btn(w('Usar títulos del proyecto abierto','Use open project headings'),()=>{sections=(S.data.report?.sections||[]).map((s,i)=>({key:s.key,title:s.title?{[S.data.meta.lang||'es']:s.title}:{es:S.catBy[s.key]?.title_es||s.key,en:S.catBy[s.key]?.title_en||''},body:{es:'TODO: Completa esta sección.',en:'TODO: Complete this section.'}}));renderRows();}));
    body.append(btn(w('Guardar plantilla','Save design'),async()=>{if(sections.some(s=>!s.title?.es?.trim()||!s.title?.en?.trim()||(s.body&&(!s.body.es?.trim()||!s.body.en?.trim()))))throw Error(w('Completa los títulos y textos iniciales en español e inglés.','Complete headings and starter text in Spanish and English.'));const saved=await write('/api/design-library/personal'+(editing?'/'+p.id:''),{name:name.value,design:read(),sections},editing?'PUT':'POST');d.close();await done(saved);},true));renderRows();}
  function panel(){const design=S.data.meta.design;
    return h('div',{class:'card'},h('h4',{},w('Diseño del informe','Report design')),h('p',{},design?design.name+' / '+(design.variant==='quiet'?w('Sobria','Quiet'):w('Marca','Brand')):generalItem(S.data.meta.theme).name),btn(w('Abrir biblioteca de informes','Open report design library'),gallery));}
  function bind(){const b=btn(w('Biblioteca de informes','Report design library'),gallery);b.id='designLibraryBtn';$('.sidebar').prepend(b);
    $('#mLang').addEventListener('change',()=>{if(creationDraft)creationDraft.sampleLang=$('#mLang').value.split('-').at(-1);});
    const newBox=$('#newProjectLibrary');if(newBox){const library=btn(w('Volver a la galería','Back to gallery'),()=>{const opener=$('#newModal')._opener;if(creationDraft)creationDraft.sampleLang=$('#mLang').value.split('-').at(-1);closeModal($('#newModal'));return newProject(opener);});library.dataset.i18n='new_project_library';newBox.append(library);}}

  return {bind,gallery,panel,guideBox,newProject,projectRequest,resetCreation};
})();

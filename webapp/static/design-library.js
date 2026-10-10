/* Report appearances are independent of report content. All mutations use revisions. */
const DesignLibraryUI=(()=>{
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const local=v=>typeof v==='object'?(v[S.uiLang]||v.es||''):v;
  const layouts={rail:['Banda lateral','Side rail'],split:['Dos zonas','Split cover'],frame:['Marco','Frame'],band:['Franja central','Center band'],timeline:['Cronología','Timeline']};
  let catalog=null,etag=null,trigger=null;
  function btn(label,fn,primary=false){const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},label);b.addEventListener('click',async()=>{trigger=b;b.disabled=true;try{await fn(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;}
  function modal(title,wide=false,opener=null){const focus=opener||(document.activeElement===document.body?trigger:document.activeElement);
    const d=h('dialog',{class:'experience-dialog'+(wide?' design-dialog':''),'aria-label':title});const body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),btn(w('Cerrar','Close'),()=>d.close())),body);
    d.addEventListener('close',()=>{d.remove();requestAnimationFrame(()=>{const open=[...document.querySelectorAll('dialog[open]')].at(-1);if(focus?.isConnected&&(!open||open.contains(focus)))focus.focus();else if(open)open.querySelector('button')?.focus();else $('#designLibraryBtn')?.focus();});});document.body.append(d);d.showModal();return {d,body};}
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
  async function gallery(opener=null){opener=opener||(document.activeElement!==document.body?document.activeElement:trigger);await refresh();const {d,body}=modal(w('Biblioteca de informes','Report design library'),true,opener);
    let family='OffSec',query='',selected=null,variant='brand',sample='cover',sampleLang=S.uiLang,serial=0;
    const sampleLanguage=h('select',{'data-design-sample-language':'','aria-label':w('Idioma de las muestras','Sample language')},h('option',{value:'es'},'Español'),h('option',{value:'en'},'English'));sampleLanguage.value=sampleLang;
    sampleLanguage.addEventListener('change',()=>{sampleLang=sampleLanguage.value;renderList();renderDetail();});
    const samplePath=(id,v,page)=>'/static/design-previews/'+id+'/'+(sampleLang==='en'?'en/':'')+v+'-'+page+'.webp';
    const filters=h('div',{class:'design-filters','aria-label':w('Familias','Families')});
    const search=h('input',{type:'search',placeholder:w('Buscar certificación o curso','Search certificate or course'),'aria-label':w('Buscar plantillas','Search designs')});
    const listing=h('div',{class:'design-cards'}),detail=h('div',{class:'design-detail'}),count=h('p',{role:'status',class:'wf-hint'});
    const allFamilies=['General','OffSec','HTB','Personal','Históricas'];
    const familyName=x=>({General:w('Generales','General'),Personal:w('Mis plantillas','My designs'),'Históricas':w('Históricas','Historical')})[x]||x;
    for(const f of allFamilies){const b=btn(familyName(f),()=>{family=f;selected=null;renderList();renderDetail();});b.dataset.family=f;filters.append(b);}
    search.addEventListener('input',()=>{query=search.value.trim().toLowerCase();renderList();});
    body.append(h('p',{},w('22 perfiles de certificación y seis diseños generales. Portada, resumen y página técnica generados con report-gen.','22 certification profiles and six general designs. Cover, summary and technical page generated by report-gen.')),
      filters,h('div',{class:'grid2'},h('label',{},w('Idioma de las muestras','Sample language'),sampleLanguage),h('label',{},w('Buscar plantillas','Search designs'),search)),count,h('div',{class:'design-layout'},listing,detail));
    function items(){return family==='General'?catalog.general.map(id=>({id,name:id,provider:'General'})):family==='Personal'?catalog.personal:family==='Históricas'?catalog.historical:catalog.profiles.filter(p=>p.provider===family);}
    function renderList(){filters.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.family===family)));listing.replaceChildren();const rows=items().filter(p=>[p.name,p.course||'',p.provider].join(' ').toLowerCase().includes(query));count.textContent=rows.length+' '+w('plantillas o referencias','designs or references');
      if(!rows.length)listing.append(h('p',{},family==='Personal'?w('Duplica un perfil para guardar tu primera plantilla.','Duplicate a profile to save your first design.'):w('No hay coincidencias.','No matches.')));
      rows.forEach(p=>{if(family==='Históricas'){listing.append(h('article',{class:'design-history'},h('h3',{},p.name),h('p',{},local(p.note)),h('a',{href:p.source,target:'_blank',rel:'noopener noreferrer'},w('Fuente','Source'))));return;}
        const card=btn('',()=>{selected=p;if(p.provider==='Personal')variant=p.design.variant;sample='cover';renderList();renderDetail();});card.classList.add('design-card');card.dataset.design=p.id;card.setAttribute('aria-pressed',String(selected?.id===p.id));
        if(p.provider!=='Personal')card.append(h('img',{src:samplePath(p.id,'brand','cover'),alt:'',loading:'lazy',width:210,height:297}));
        else card.append(h('div',{class:'design-personal-swatch',style:'border-color:'+p.design.accent},p.design.certificate));
        card.append(h('strong',{},p.name),h('span',{},p.course||familyName(p.provider)));listing.append(card);});}
    async function renderDetail(){const turn=++serial;detail.replaceChildren();if(!selected){detail.append(h('h3',{},w('Elige una plantilla','Choose a design')),h('p',{},w('Crear un proyecto incorpora la estructura. Aplicar apariencia conserva tus secciones, hallazgos y evidencias.','Creating a project adds the structure. Applying an appearance preserves your sections, findings and evidence.')));return;}
      const p=selected;detail.append(h('h3',{},p.name));
      if(p.provider!=='General'){
        const v=h('select',{'aria-label':w('Variante de diseño','Design variant')},h('option',{value:'brand'},w('Marca','Brand')),h('option',{value:'quiet'},w('Sobria','Quiet')));v.value=variant;v.addEventListener('change',()=>{variant=v.value;renderDetail();});detail.append(h('label',{},w('Apariencia','Appearance'),v));
      }
      const samples=h('div',{class:'design-filters'}),preview=h('div',{class:'design-preview'});
      for(const [id,es,en] of [['cover','Portada','Cover'],['summary','Resumen','Summary'],['technical','Técnica','Technical']]){const b=btn(w(es,en),()=>{sample=id;renderDetail();});b.setAttribute('aria-pressed',String(sample===id));samples.append(b);}
      detail.append(samples,preview,h('p',{class:'wf-hint'},w('Muestra ficticia. Calibri en Word; Carlito en PDF. Código monoespaciado.','Fictional sample. Calibri in Word; Carlito in PDF. Monospaced code.')));
      if(p.provider==='Personal'){
        preview.append(h('p',{role:'status'},w('Generando vista previa real…','Rendering actual preview…')));
        try{const response=await requireOk(await api.post('/api/design-library/preview',{id:p.id,variant,lang:sampleLang}));const html=await response.text();if(serial!==turn||!d.isConnected)return;
          preview.replaceChildren(livePage(html,sample));
        }catch(e){if(serial===turn)preview.replaceChildren(h('p',{role:'alert'},e.message));}
      }else preview.append(h('a',{href:samplePath(p.id,p.provider==='General'?'brand':variant,sample),target:'_blank',rel:'noopener noreferrer'},h('img',{src:samplePath(p.id,p.provider==='General'?'brand':variant,sample),alt:p.name+' / '+sample,width:595,height:842})));
      const actions=h('div',{class:'experience-actions'});
      actions.append(btn(w('Crear proyecto','Create project'),()=>createProject(p,variant,d,sampleLang),true));
      if(S.slug)actions.append(btn(w('Aplicar apariencia','Apply appearance'),async()=>{if(!await doSave())return;const slug=S.slug;busyProject(true);try{
        await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/design',{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(p.provider==='General'?{general:p.id}:{id:p.id,variant})}));d.close();await loadProject(slug);select('report');toast(w('Apariencia aplicada. El contenido se conserva.','Appearance applied. Content preserved.'),'ok');
      }finally{busyProject(false);}}));
      if(p.provider!=='General')actions.append(btn(w('Duplicar y personalizar','Duplicate and customize'),()=>editPersonal({...p,design:{...p.design,variant}},false,async()=>{await refresh();family='Personal';selected=null;renderList();renderDetail();})));
      if(p.provider==='Personal')actions.append(btn(w('Editar plantilla','Edit design'),()=>editPersonal({...p,design:{...p.design,variant}},true,async()=>{await refresh();selected=catalog.personal.find(x=>x.id===p.id);renderList();renderDetail();})),btn(w('Eliminar plantilla','Delete design'),async()=>{
        const {d:confirm,body:cb}=modal(w('Eliminar plantilla personal','Delete personal design'));cb.append(h('p',{},w('Los proyectos que ya la usan conservarán su apariencia.','Projects already using this design will keep their appearance.')),btn(w('Confirmar eliminación','Confirm deletion'),async()=>{await write('/api/design-library/personal/'+p.id,null,'DELETE');confirm.close();await refresh();selected=null;renderList();renderDetail();}));
      }));
      detail.insertBefore(actions,samples);
      if(p.sections){const list=h('ol');p.sections.forEach(s=>list.append(h('li',{},(typeof s.title==='object'?s.title[sampleLang]:s.title)||w('Hallazgos','Findings'))));detail.append(h('details',{},h('summary',{},w('Estructura inicial','Starter structure')),list));}
      if(p.guidance)detail.append(guideBox({...p.guidance,note:local(p.guidance.note)}));
    }
    renderList();renderDetail();
  }
  async function createProject(p,variant,parent,sampleLang=S.uiLang){const {d,body}=modal(w('Nuevo proyecto desde plantilla','New project from design'));
    const title=h('input',{maxlength:300,value:p.name+' '+(sampleLang==='en'?'lab':'laboratorio'),'data-design-field':'project-title'});
    const lang=h('select',{'data-design-field':'lang'},h('option',{value:'es'},'Español'),h('option',{value:'en'},'English'));lang.value=sampleLang;
    body.append(h('label',{},w('Título del informe','Report title'),title),h('label',{},w('Idioma del contenido inicial','Starter content language'),lang),btn(w('Crear proyecto','Create project'),async()=>{
      if(S.slug&&!await doSave())return;busyProject(true);try{const payload=p.provider==='General'?{title:title.value,model:p.id+'-'+lang.value}:{title:title.value,id:p.id,variant,lang:lang.value};
      const response=await requireOk(await api.post(p.provider==='General'?'/api/projects':'/api/design-library/projects',payload));const {slug}=await response.json();d.close();parent.close();await refreshProjects();await loadProject(slug);
      }finally{busyProject(false);}
    },true));title.focus();title.select();}
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
    body.append(btn(w('Guardar plantilla','Save design'),async()=>{if(sections.some(s=>!s.title?.es?.trim()||!s.title?.en?.trim()||(s.body&&(!s.body.es?.trim()||!s.body.en?.trim()))))throw Error(w('Completa los títulos y textos iniciales en español e inglés.','Complete headings and starter text in Spanish and English.'));await write('/api/design-library/personal'+(editing?'/'+p.id:''),{name:name.value,design:read(),sections},editing?'PUT':'POST');d.close();await done();},true));renderRows();}
  function panel(){const design=S.data.meta.design;
    return h('div',{class:'card'},h('h4',{},w('Diseño del informe','Report design')),h('p',{},design?design.name+' / '+(design.variant==='quiet'?w('Sobria','Quiet'):w('Marca','Brand')):w('Diseño general','General design')),btn(w('Abrir biblioteca de informes','Open report design library'),gallery));}
  function bind(){const b=btn(w('Biblioteca de informes','Report design library'),gallery);b.id='designLibraryBtn';$('.sidebar').prepend(b);
    const newBox=$('#newModal .modal-box');if(newBox)newBox.prepend(btn(w('Elegir en la biblioteca de informes','Choose in report design library'),()=>{closeModal($('#newModal'));return gallery();}));}
  return {bind,gallery,panel,guideBox};
})();

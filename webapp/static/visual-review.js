/* Optional project-owned progress. PDF persistence requires an explicit checkbox. */
const VisualReviewUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  function mount({box,slug,display,saved}) {
    const root=h('section',{class:'insights-card visual-review-library','data-visual-library':''},h('h2',{},w('Revisiones guardadas','Saved reviews','Revisões salvas')));
    const rows=h('div',{'data-visual-saved-list':''}),status=h('p',{role:'status'});let current=null,sequence=0;
    const button=(labels,action,key)=>{
      const node=h('button',{type:'button',class:'btn','data-visual-action':key},w(...labels));
      node.addEventListener('click',async()=>{if(projectBusyCount>0)return;node.disabled=true;try{await action();}catch(error){toast(error.message,'err');}finally{if(node.isConnected)node.disabled=projectBusyCount>0;}});return node;
    };
    root.append(h('p',{class:'insights-note'},w('Guarda únicamente cuando quieras conservar el progreso. Las notas y copias privadas quedan en el proyecto, su historial y sus respaldos; se excluyen de la entrega por defecto. No certifican autoría ni revisión técnica.','Save only when you want to retain progress. Notes and private copies remain in the project, its history and backups; they are excluded from delivery by default. They do not certify authorship or technical review.','Salve somente quando quiser manter o progresso. Notas e cópias privadas ficam no projeto, no histórico e nos backups; são excluídas da entrega por padrão. Não certificam autoria nem revisão técnica.')),
      button(['Actualizar lista','Refresh list','Atualizar lista'],refresh,'refresh'),status,rows);box.append(root);
    const dirty=()=>current&&(JSON.stringify(current.read())!==current.signature||current.keep.checked!==Boolean(current.data.saved?.pdf_attachment_uid));
    function allowSwitch(){return !dirty()||confirm(w('Hay cambios de revisión sin guardar. ¿Abrir otro PDF y descartarlos?','There are unsaved review changes. Open another PDF and discard them?','Há alterações da revisão não salvas. Abrir outro PDF e descartá-las?'));}
    async function send(path,body,method='POST',mutate=true){
      busyProject(true);
      try{
        const snapshot=await saved();if(snapshot.slug!==slug)throw Error(w('Abre el proyecto original.','Open the original project.','Abra o projeto original.'));
        const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+path,{method,headers:{'Content-Type':'application/json','If-Match':snapshot.etag},body:JSON.stringify(body)}));
        const data=await response.json();if(S.slug!==slug)throw Error(w('El proyecto cambió.','The project changed.','O projeto mudou.'));
        if(mutate){await adoptSavedProject(data.data,response.headers.get('ETag'));renderSidebar();}
        return data;
      }finally{busyProject(false);}
    }
    async function resume(record,useCurrent){
      if(!allowSwitch())return;
      if(useCurrent&&!current)throw Error(w('Primero abre el PDF original en esta pantalla.','First open the original PDF on this screen.','Primeiro abra o PDF original nesta tela.'));
      const data=await send('/visual-reviews/'+record.uid+'/open',{visual_id:useCurrent?current.data.id:null},'POST',false);
      if(!root.isConnected||S.slug!==slug)return;
      display(data,'/api/visual/'+encodeURIComponent(data.id),true);
    }
    async function refresh(){
      const token=++sequence,response=await api.get('/api/projects/'+encodeURIComponent(slug)+'/visual-reviews');
      if(token!==sequence||!root.isConnected||S.slug!==slug)return;
      rows.replaceChildren();status.textContent=response.records.length+' / '+response.max_records+' '+w('revisiones guardadas','saved reviews','revisões salvas');
      for(const record of response.records){
        const progress=record.progress,pending=progress.pages.filter(item=>!item.resolved).length;
        const article=h('article',{class:'visual-review-entry','data-visual-saved-id':record.uid},h('h3',{},'PDF '+record.pdf_sha256.slice(0,12)),
          h('p',{},w('Página ','Page ','Página ')+progress.page+' / '+record.page_count+' · '+pending+' '+w('pendientes','pending issues','pendências')),
          h('p',{class:'insights-hash'},'SHA-256: '+record.pdf_sha256),h('p',{class:'insights-hash'},w('Revisión vinculada: ','Linked revision: ','Revisão vinculada: ')+record.revision),
          h('p',{class:'insights-note'},record.updated+' · '+(record.pdf_attachment_uid?w('Copia privada guardada','Private copy saved','Cópia privada salva'):w('Requiere el PDF original','Original PDF required','Requer o PDF original'))));
        const actions=h('div',{class:'insights-actions'});
        if(record.pdf_attachment_uid)actions.append(button(['Reanudar copia privada','Resume private copy','Retomar cópia privada'],()=>resume(record,false),'resume-copy'));
        actions.append(button(['Reanudar con el PDF abierto','Resume with the open PDF','Retomar com o PDF aberto'],()=>resume(record,true),'resume-file'),
          button(['Eliminar revisión guardada','Delete saved review','Excluir revisão salva'],async()=>{
            if(!confirm(w('¿Eliminar esta revisión y su copia privada del estado actual? Las versiones anteriores y los respaldos conservan sus copias. El PDF temporal abierto se conserva.','Delete this review and its private copy from the current state? Previous versions and backups retain their copies. The open temporary PDF is retained.','Excluir esta revisão e sua cópia privada do estado atual? Versões anteriores e backups mantêm suas cópias. O PDF temporário aberto é mantido.')))return;
            await send('/visual-reviews/'+record.uid,{},'DELETE');
            if(current?.data.saved?.uid===record.uid){current.data.saved=null;current.keep.checked=false;current.status.textContent=w('Revisión guardada eliminada; el progreso abierto es temporal.','Saved review deleted; open progress is temporary.','Revisão salva excluída; o progresso aberto é temporário.');}
            await refresh();
          },'delete-saved'));
        article.append(actions);rows.append(article);
      }
    }
    function setCurrent(data,read,target){
      const keep=h('input',{type:'checkbox','data-visual-keep-pdf':''}),message=h('p',{role:'status','data-visual-save-status':''});
      keep.checked=Boolean(data.saved?.pdf_attachment_uid);
      const panel=h('section',{class:'insights-card visual-review-save','data-visual-save-panel':''},h('h3',{},w('Conservar y retomar','Save and resume','Salvar e retomar')),
        h('p',{class:'insights-note'},w('Guarda la página actual, notas y pendientes de este PDF exacto. Sin copia privada tendrás que volver a abrir el mismo archivo. Desmarcar la copia la elimina del estado actual al guardar; el historial y los respaldos anteriores la conservan.','Save the current page, notes and pending issues for this exact PDF. Without a private copy you must reopen the same file. Unchecking the copy removes it from the current state when saved; history and earlier backups retain it.','Salve a página atual, notas e pendências deste PDF exato. Sem cópia privada será necessário abrir o mesmo arquivo novamente. Desmarcar a cópia a remove do estado atual ao salvar; o histórico e backups anteriores a mantêm.')),
        h('label',{class:'insights-check'},keep,w('Guardar también una copia privada del PDF (máximo 16 MiB)','Also save a private PDF copy (maximum 16 MiB)','Salvar também uma cópia privada do PDF (máximo de 16 MiB)')));
      const entry={data,read,signature:JSON.stringify(read()),keep,status:message};current=entry;
      const save=button(['Guardar progreso en el proyecto','Save progress in project','Salvar progresso no projeto'],async()=>{
        const progress=JSON.parse(JSON.stringify(read())),keep_pdf=keep.checked;
        const response=await send('/visual-reviews',{visual_id:data.id,uid:data.saved?.uid||null,progress,keep_pdf});
        data.saved=response.record;entry.signature=JSON.stringify(progress);
        if(current===entry&&target.isConnected){message.textContent=w('Progreso guardado. Puedes cerrar y retomarlo desde esta lista.','Progress saved. You can close and resume from this list.','Progresso salvo. Você pode fechar e retomar nesta lista.');await refresh();}
      },'save-progress');
      message.textContent=data.saved?w('Progreso recuperado del proyecto. Los cambios requieren Guardar progreso.','Progress restored from the project. Changes require Save progress.','Progresso recuperado do projeto. As alterações exigem Salvar progresso.'):w('Temporal: no se guarda automáticamente en el proyecto.','Temporary: not automatically saved in the project.','Temporário: não é salvo automaticamente no projeto.');
      panel.append(save,message);target.append(panel);return entry;
    }
    refresh().catch(error=>{status.textContent=error.message;});
    return {setCurrent,refresh,allowSwitch,clearCurrent:()=>{current=null;}};
  }
  return {mount};
})();

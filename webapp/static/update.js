/* Explicit public check -> verified local stage -> handoff after stopping editor. */
const UpdateUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  function button(label,run,attributes={}) {
    const node=h('button',{type:'button',class:'btn',...attributes},label);
    node.addEventListener('click',run);return node;
  }
  function open(opener) {
    const previous=opener||document.activeElement;
    const dialog=h('dialog',{class:'experience-dialog update-dialog','aria-label':w('Actualizar report-gen','Update report-gen')});
    const body=h('div',{class:'experience-body'}),status=h('p',{role:'status','aria-live':'polite','data-update-status':''});
    const result=h('div',{'data-update-result':''});
    const network=h('input',{type:'checkbox','data-update-network':''});
    const check=button(w('Comprobar versión oficial','Check official version'),async()=>{
      if(!network.checked||busy)return;
      setBusy(true);result.replaceChildren();status.textContent=w('Comprobando publicación, etiqueta y sumas de verificación…','Checking release, tag and checksums…');
      try {
        const response=await requireOk(await api.post('/api/update/check',{allow_network:true}));
        const plan=await response.json();if(!dialog.isConnected)return;
        if(!plan.available){status.textContent=w('No hay una versión estable más reciente. Instalada: ','No newer stable version is available. Installed: ')+plan.current_version;return;}
        status.textContent=w('Publicación verificada. Revisa antes de preparar.','Release verified. Review before preparing.');
        const terms=h('input',{type:'checkbox','data-update-private':''});
        const details=h('dl',{},h('dt',{},w('Nueva versión','New version')),h('dd',{},plan.version),
          h('dt',{},w('Descarga','Download')),h('dd',{},(plan.size/1024/1024).toFixed(1)+' MiB'),
          h('dt',{},'SHA-256'),h('dd',{class:'update-digest'},plan.sha256));
        const prepare=button(w('Descargar, verificar y respaldar','Download, verify and back up'),async()=>{
          if(!terms.checked||!network.checked||busy)return;
          if(S.slug && !await doSave())return;
          setBusy(true);terms.disabled=true;prepare.disabled=true;
          status.textContent=w('Preparando una carpeta nueva y un respaldo verificado…','Preparing a new directory and verified backup…');
          try {
            const response=await requireOk(await api.post('/api/update/prepare',{allow_network:true,ack_private_backup:true,preview_token:plan.preview_token}));
            const receipt=await response.json();if(!dialog.isConnected)return;
            result.replaceChildren(h('h3',{},w('Preparación completa','Preparation complete')),
              h('p',{},w('Guarda estas instrucciones antes de cerrar el editor. No cambies los proyectos entre el respaldo y la actualización.','Save these instructions before closing the editor. Do not edit projects between backup and update.')),
              h('p',{},w('Respaldo privado (no cifrado): ','Private backup (not encrypted): ')+receipt.backup),
              h('p',{},w('Capturado: ','Captured: ')+receipt.prepared_at),
              h('p',{class:'update-digest'},'SHA-256: '+receipt.backup_sha256),
              h('p',{},w('1. Cierra las otras pestañas y detén este editor con Ctrl+C.','1. Close other tabs and stop this editor with Ctrl+C.')),
              h('p',{},w('2. Ejecuta estas líneas, una a una, en ','2. Run these lines one at a time in ')+receipt.shell+w('. Si una falla, detente. La instalación de dependencias accede a Internet.','. Stop if any line fails. Dependency installation accesses the Internet.')));
            receipt.commands.forEach(command=>result.append(h('pre',{'data-update-command':'',tabindex:'0'},command)));
            result.append(h('p',{},w('3. Comprueba tus proyectos y las exportaciones antes de borrar la instalación anterior. Conserva el respaldo.','3. Check your projects and exports before deleting the previous installation. Keep the backup.')),
              h('h3',{},w('Volver a la instalación anterior','Return to the previous installation')),
              h('p',{},w('Si la preparación o instalación falla, detén cualquier editor nuevo y ejecuta lo siguiente. El lanzador existente solo se cambia después de comprobar las dependencias. Si ya editaste datos con la nueva versión, conserva ambas carpetas y restaura el respaldo en un espacio vacío; no sobrescribas tu trabajo.','If preparation or installation fails, stop any new editor and run the following. The existing launcher only changes after dependencies are checked. If you already edited data with the new version, keep both directories and restore the backup into an empty workspace; do not overwrite your work.')),
              h('pre',{tabindex:'0'},receipt.rollback_command));
            if(receipt.migration)result.append(h('p',{},w('La migración copia los datos heredados a un espacio externo. Los borradores del navegador no forman parte del respaldo: guárdalos o descárgalos antes de cerrar.','Migration copies legacy data into an external workspace. Browser drafts are excluded from the backup: save or download them before closing.')));
            const save=button(w('Descargar instrucciones privadas','Download private instructions'),()=>{
              const text=result.innerText,link=h('a',{href:URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'})),download:'report-gen-update-private.txt'});
              link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
            });result.append(save);status.textContent=w('Paquete y respaldo preparados. La versión en ejecución no ha cambiado.','Package and backup prepared. The running version has not changed.');
          } catch(error) {if(dialog.isConnected)status.textContent=error.message;}
          finally {setBusy(false);terms.disabled=false;prepare.disabled=!terms.checked||!network.checked;}
        },{'data-update-prepare':'',disabled:''});
        const toggle=()=>{prepare.disabled=busy||!terms.checked||!network.checked;};terms.addEventListener('change',toggle);network.addEventListener('change',toggle);
        result.append(details,h('a',{href:plan.release_url,target:'_blank',rel:'noopener noreferrer'},w('Leer publicación en GitHub','Read release on GitHub')),
          h('p',{},w('Se creará una copia privada sin cifrar de los proyectos, evidencias, bibliotecas e historial guardados en disco. Los borradores del navegador quedan fuera. La descarga no se ejecuta automáticamente.','An unencrypted private copy of projects, evidence, libraries and history saved on disk will be created. Browser drafts are excluded. Downloaded code does not run automatically.')),
          h('label',{class:'support-review-label'},terms,w('He revisado la versión y autorizo preparar el paquete y el respaldo privado.','I reviewed the version and allow preparing the package and private backup.')),prepare);
      } catch(error) {if(dialog.isConnected)status.textContent=error.message;}
      finally {setBusy(false);}
    },{'data-update-check':'',disabled:''});
    let busy=false;
    function setBusy(value){busy=value;check.disabled=busy||!network.checked;network.disabled=busy;close.disabled=busy;dialog.setAttribute('aria-busy',String(value));}
    const close=button(w('Cerrar','Close'),()=>dialog.close());
    network.addEventListener('change',()=>{check.disabled=busy||!network.checked;});
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    dialog.addEventListener('close',()=>{
      dialog.remove();
      const visible=node=>node?.isConnected&&!node.disabled&&node.getClientRects().length&&!node.closest('[inert]');
      const target=visible(previous)?previous:document.querySelector('#sidebarToggle');
      if(visible(target))target.focus();
    });
    body.append(h('p',{},w('Consulta manual al repositorio oficial IphobiusS/report-gen. Solo se envían solicitudes públicas; no se envían informes, rutas ni credenciales.','Manual check of the official IphobiusS/report-gen repository. Only public requests are sent; reports, paths and credentials are not sent.')),
      h('label',{class:'support-review-label'},network,w('Permitir consulta y descarga desde GitHub.','Allow checking and downloading from GitHub.')),check,status,result);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},w('Actualizar report-gen','Update report-gen')),close),body);
    document.body.append(dialog);dialog.showModal();
  }
  return {open};
})();

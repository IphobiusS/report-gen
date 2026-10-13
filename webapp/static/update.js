/* Explicit public check -> verified local stage -> handoff after stopping editor. */
const UpdateUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  function button(label,run,attributes={}) {
    const node=h('button',{type:'button',class:'btn',...attributes},label);
    node.addEventListener('click',run);return node;
  }
  function open(opener) {
    const previous=opener||document.activeElement;
    const dialog=h('dialog',{class:'experience-dialog update-dialog','aria-label':w('Actualizar report-gen','Update report-gen', "Atualizar report-gen")});
    const body=h('div',{class:'experience-body'}),status=h('p',{role:'status','aria-live':'polite','data-update-status':''});
    const result=h('div',{'data-update-result':''});
    const network=h('input',{type:'checkbox','data-update-network':''});
    const check=button(w('Comprobar versión oficial','Check official version', "Verificar versão oficial"),async()=>{
      if(!network.checked||busy)return;
      setBusy(true);result.replaceChildren();status.textContent=w('Comprobando publicación, etiqueta y sumas de verificación…','Checking release, tag and checksums…', "Verificando versão publicada, tag e somas de verificação…");
      try {
        const response=await requireOk(await api.post('/api/update/check',{allow_network:true}));
        const plan=await response.json();if(!dialog.isConnected)return;
        if(!plan.available){status.textContent=w('No hay una versión estable más reciente. Instalada: ','No newer stable version is available. Installed: ', "Nenhuma versão estável mais recente está disponível. Instalada: ")+plan.current_version;return;}
        status.textContent=w('Publicación verificada. Revisa antes de preparar.','Release verified. Review before preparing.', "Versão verificada. Revise antes de preparar.");
        const terms=h('input',{type:'checkbox','data-update-private':''});
        const details=h('dl',{},h('dt',{},w('Nueva versión','New version', "Nova versão")),h('dd',{},plan.version),
          h('dt',{},w('Descarga','Download', "Baixar")),h('dd',{},(plan.size/1024/1024).toFixed(1)+' MiB'),
          h('dt',{},'SHA-256'),h('dd',{class:'update-digest'},plan.sha256));
        const prepare=button(w('Descargar, verificar y respaldar','Download, verify and back up', "Baixar, verificar e criar backup"),async()=>{
          if(!terms.checked||!network.checked||busy)return;
          if(S.slug && !await doSave())return;
          setBusy(true);terms.disabled=true;prepare.disabled=true;
          status.textContent=w('Preparando una carpeta nueva y un respaldo verificado…','Preparing a new directory and verified backup…', "Preparando um novo diretório e um backup verificado…");
          try {
            const response=await requireOk(await api.post('/api/update/prepare',{allow_network:true,ack_private_backup:true,preview_token:plan.preview_token}));
            const receipt=await response.json();if(!dialog.isConnected)return;
            result.replaceChildren(h('h3',{},w('Preparación completa','Preparation complete', "Preparação concluída")),
              h('p',{},w('Guarda estas instrucciones antes de cerrar el editor. No cambies los proyectos entre el respaldo y la actualización.','Save these instructions before closing the editor. Do not edit projects between backup and update.', "Salve estas instruções antes de fechar o editor. Não edite projetos entre o backup e a atualização.")),
              h('p',{},w('Respaldo privado (no cifrado): ','Private backup (not encrypted): ', "Backup privado (sem criptografia): ")+receipt.backup),
              h('p',{},w('Capturado: ','Captured: ', "Capturado em: ")+receipt.prepared_at),
              h('p',{class:'update-digest'},'SHA-256: '+receipt.backup_sha256),
              h('p',{},w('1. Cierra las otras pestañas y detén este editor con Ctrl+C.','1. Close other tabs and stop this editor with Ctrl+C.', "1. Feche as outras abas e pare este editor com Ctrl+C.")),
              h('p',{},w('2. Ejecuta estas líneas, una a una, en ','2. Run these lines one at a time in ', "2. Execute estas linhas, uma por vez, em ")+receipt.shell+w('. Si una falla, detente. La instalación de dependencias accede a Internet.','. Stop if any line fails. Dependency installation accesses the Internet.', ". Pare se alguma linha falhar. A instalação das dependências acessa a Internet.")));
            receipt.commands.forEach(command=>result.append(h('pre',{'data-update-command':'',tabindex:'0'},command)));
            result.append(h('p',{},w('3. Comprueba tus proyectos y las exportaciones antes de borrar la instalación anterior. Conserva el respaldo.','3. Check your projects and exports before deleting the previous installation. Keep the backup.', "3. Verifique seus projetos e exportações antes de excluir a instalação anterior. Mantenha o backup.")),
              h('h3',{},w('Volver a la instalación anterior','Return to the previous installation', "Voltar à instalação anterior")),
              h('p',{},w('Si la preparación o instalación falla, detén cualquier editor nuevo y ejecuta lo siguiente. El lanzador existente solo se cambia después de comprobar las dependencias. Si ya editaste datos con la nueva versión, conserva ambas carpetas y restaura el respaldo en un espacio vacío; no sobrescribas tu trabajo.','If preparation or installation fails, stop any new editor and run the following. The existing launcher only changes after dependencies are checked. If you already edited data with the new version, keep both directories and restore the backup into an empty workspace; do not overwrite your work.', "Se a preparação ou a instalação falhar, pare qualquer novo editor e execute o seguinte. O inicializador existente só muda após a verificação das dependências. Se você já editou dados na nova versão, mantenha os dois diretórios e restaure o backup em um espaço de trabalho vazio; não sobrescreva seu trabalho.")),
              h('pre',{tabindex:'0'},receipt.rollback_command));
            if(receipt.migration)result.append(h('p',{},w('La migración copia los datos heredados a un espacio externo. Los borradores del navegador no forman parte del respaldo: guárdalos o descárgalos antes de cerrar.','Migration copies legacy data into an external workspace. Browser drafts are excluded from the backup: save or download them before closing.', "A migração copia dados legados para um espaço de trabalho externo. Rascunhos do navegador ficam fora do backup: salve-os ou baixe-os antes de fechar.")));
            const save=button(w('Descargar instrucciones privadas','Download private instructions', "Baixar instruções privadas"),()=>{
              const text=result.innerText,link=h('a',{href:URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'})),download:'report-gen-update-private.txt'});
              link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
            });result.append(save);status.textContent=w('Paquete y respaldo preparados. La versión en ejecución no ha cambiado.','Package and backup prepared. The running version has not changed.', "Pacote e backup preparados. A versão em execução não mudou.");
          } catch(error) {if(dialog.isConnected)status.textContent=error.message;}
          finally {setBusy(false);terms.disabled=false;prepare.disabled=!terms.checked||!network.checked;}
        },{'data-update-prepare':'',disabled:''});
        const toggle=()=>{prepare.disabled=busy||!terms.checked||!network.checked;};terms.addEventListener('change',toggle);network.addEventListener('change',toggle);
        result.append(details,h('a',{href:plan.release_url,target:'_blank',rel:'noopener noreferrer'},w('Leer publicación en GitHub','Read release on GitHub', "Ler publicação no GitHub")),
          h('p',{},w('Se creará una copia privada sin cifrar de los proyectos, evidencias, bibliotecas e historial guardados en disco. Los borradores del navegador quedan fuera. La descarga no se ejecuta automáticamente.','An unencrypted private copy of projects, evidence, libraries and history saved on disk will be created. Browser drafts are excluded. Downloaded code does not run automatically.', "Será criada uma cópia privada sem criptografia dos projetos, evidências, bibliotecas e histórico salvos no disco. Rascunhos do navegador ficam de fora. O código baixado não é executado automaticamente.")),
          h('label',{class:'support-review-label'},terms,w('He revisado la versión y autorizo preparar el paquete y el respaldo privado.','I reviewed the version and allow preparing the package and private backup.', "Revisei a versão e autorizo a preparação do pacote e do backup privado.")),prepare);
      } catch(error) {if(dialog.isConnected)status.textContent=error.message;}
      finally {setBusy(false);}
    },{'data-update-check':'',disabled:''});
    let busy=false;
    function setBusy(value){busy=value;check.disabled=busy||!network.checked;network.disabled=busy;close.disabled=busy;dialog.setAttribute('aria-busy',String(value));}
    const close=button(w('Cerrar','Close', "Fechar"),()=>dialog.close());
    network.addEventListener('change',()=>{check.disabled=busy||!network.checked;});
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    dialog.addEventListener('close',()=>{
      dialog.remove();
      const visible=node=>node?.isConnected&&!node.disabled&&node.getClientRects().length&&!node.closest('[inert]');
      const target=visible(previous)?previous:document.querySelector('#sidebarToggle');
      if(visible(target))target.focus();
    });
    body.append(h('p',{},w('Consulta manual al repositorio oficial IphobiusS/report-gen. Solo se envían solicitudes públicas; no se envían informes, rutas ni credenciales.','Manual check of the official IphobiusS/report-gen repository. Only public requests are sent; reports, paths and credentials are not sent.', "Verificação manual do repositório oficial IphobiusS/report-gen. Somente solicitações públicas são enviadas; relatórios, caminhos e credenciais não são enviados.")),
      h('label',{class:'support-review-label'},network,w('Permitir consulta y descarga desde GitHub.','Allow checking and downloading from GitHub.', "Permitir verificação e download do GitHub.")),check,status,result);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},w('Actualizar report-gen','Update report-gen', "Atualizar report-gen")),close),body);
    document.body.append(dialog);dialog.showModal();
  }
  return {open};
})();

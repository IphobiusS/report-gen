/* Local opt-in scheduling; private destinations never enter a report. */
const BackupRoutineUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  function mount(parent) {
    const section=h('details',{'data-backup-routine':''}),body=h('div',{class:'experience-body'});
    const summary=h('summary',{},w('Respaldos periódicos opcionales','Optional periodic backups', "Backups periódicos opcionais"));
    const status=h('p',{role:'status','aria-live':'polite','data-routine-status':''});
    const details=h('div',{'data-routine-details':''});
    const enabled=h('input',{type:'checkbox','data-routine-enabled':''});
    const destination=h('input',{type:'text',maxlength:'4096',autocomplete:'off',spellcheck:'false','data-routine-destination':''});
    const interval=h('select',{'data-routine-interval':''},
      h('option',{value:'3600'},w('Cada hora','Every hour', "A cada hora")),
      h('option',{value:'86400'},w('Cada día','Every day', "Todos os dias")),
      h('option',{value:'604800'},w('Cada semana','Every week', "Todas as semanas")));
    const retention=h('input',{type:'number',min:'1',max:'90',step:'1',value:'7','data-routine-retention':''});
    const acknowledge=h('input',{type:'checkbox','data-routine-ack':''});
    let busy=false,configured=false,last=null;
    const controls=[];
    const button=(label,run,key)=>{
      const node=h('button',{type:'button',class:'btn',['data-routine-'+key]:''},label);
      node.addEventListener('click',run);controls.push(node);return node;
    };
    function availability(){
      for(const node of [enabled,destination,interval,retention,acknowledge,...controls])node.disabled=busy;
      save.disabled=busy||!acknowledge.checked||!destination.value.trim()||!retention.validity.valid;
      run.disabled=busy||!configured||!last?.destination;
      verify.disabled=busy||!configured||!last?.latest_name;
      disable.disabled=busy||!last?.enabled;
      section.setAttribute('aria-busy',String(busy));
    }
    const date=value=>value?new Date(value*1000).toLocaleString(languageTag(S.uiLang)):w('Todavía no','Not yet', "Ainda não");
    function render(data,fields=false){
      last=data;
      if(fields){enabled.checked=data.enabled;destination.value=data.destination;interval.value=String(data.interval_seconds);retention.value=String(data.retention);configured=true;}
      details.replaceChildren(h('p',{},data.enabled?w('Programación activada.','Schedule enabled.', "Agendamento ativado."):w('Programación desactivada.','Schedule disabled.', "Agendamento desativado.")),
        h('p',{},w('Última copia correcta: ','Last successful copy: ', "Última cópia bem-sucedida: ")+date(data.last_success)),
        h('p',{},w('Última restauración temporal correcta: ','Last successful temporary restoration: ', "Última restauração temporária bem-sucedida: ")+date(data.last_verified)));
      if(data.directory)details.append(h('p',{style:'overflow-wrap:anywhere'},w('Carpeta privada: ','Private directory: ', "Diretório privado: ")+data.directory));
      if(data.latest_name)details.append(h('p',{style:'overflow-wrap:anywhere'},w('Última copia: ','Latest copy: ', "Última cópia: ")+data.latest_name),
        h('p',{class:'update-digest'},'SHA-256: '+data.latest_sha256));
      if(data.enabled)details.append(h('p',{},data.scheduler_running
        ?(data.next_due?w('Próximo vencimiento: ','Next due: ', "Próximo prazo: ")+date(data.next_due):w('Primera copia pendiente; se revisa en un minuto como máximo.','First copy pending; checked within one minute.', "Primeira cópia pendente; verificação em até um minuto."))
        :w('El programador no está activo en este proceso. Inicia el editor con su lanzador local.','The scheduler is not active in this process. Start the editor through its local launcher.', "O agendador não está ativo neste processo. Inicie o editor pelo inicializador local.")));
      if(data.last_error==='backup_failed')details.append(h('p',{role:'alert'},w('El último intento falló. Revisa espacio libre, permisos y destino; luego vuelve a crear o comprobar la copia.','The last attempt failed. Check free space, permissions and destination; then create or check the copy again.', "A última tentativa falhou. Verifique o espaço livre, as permissões e o destino; depois crie ou verifique a cópia novamente.")));
      if(data.last_error==='retention_pending')details.append(h('p',{role:'alert'},w('La copia nueva está verificada, pero algunos archivos antiguos no se pudieron retirar. Se conservaron los archivos alterados o inaccesibles; revisa también las subcarpetas .retention-* si existen.','The new copy is verified, but some older files could not be removed. Changed or inaccessible files were retained; also review .retention-* subdirectories if present.', "A nova cópia foi verificada, mas alguns arquivos antigos não puderam ser removidos. Arquivos alterados ou inacessíveis foram mantidos; revise também os subdiretórios .retention-*, se existirem.")));
      availability();
    }
    async function request(path,method='GET',body){
      const options={method};
      if(body!==undefined){options.headers={'Content-Type':'application/json'};options.body=JSON.stringify(body);}
      return (await requireOk(await appFetch('/api/workspace/backup-routine'+path,options))).json();
    }
    async function action(path,method,body,working,complete){
      if(busy)return;
      busy=true;availability();status.textContent=working;
      try{const data=await request(path,method,body);if(!section.isConnected)return;render(data,method!=='GET'||configured||!last);status.textContent=complete;}
      catch(error){if(section.isConnected)status.textContent=error.message;}
      finally{busy=false;if(section.isConnected)availability();}
    }
    const save=button(w('Guardar programación','Save schedule', "Salvar agendamento"),()=>action('','PUT',{
      enabled:enabled.checked,destination:destination.value.trim(),interval_seconds:Number(interval.value),retention:Number(retention.value),ack_unencrypted:acknowledge.checked
    },w('Guardando programación…','Saving schedule…', "Salvando agendamento…"),w('Programación guardada. Los destinos anteriores se conservan.','Schedule saved. Previous destinations are retained.', "Agendamento salvo. Os destinos anteriores foram mantidos.")),'save');
    const disable=button(w('Desactivar programación','Disable schedule', "Desativar agendamento"),()=>action('/disable','POST',{},w('Desactivando…','Disabling…', "Desativando…"),w('Programación desactivada. Las copias se conservan.','Schedule disabled. Backups are retained.', "Agendamento desativado. Os backups foram mantidos.")),'disable');
    const run=button(w('Crear y comprobar copia ahora','Create and check copy now', "Criar e verificar cópia agora"),async()=>{
      if(busy||!configured)return;
      if(S.slug&&!await doSave())return;
      return action('/run','POST',{},w('Capturando datos guardados y comprobando una restauración temporal…','Capturing saved data and checking a temporary restoration…', "Capturando dados salvos e verificando uma restauração temporária…"),w('Copia creada y restauración temporal comprobada.','Copy created and temporary restoration checked.', "Cópia criada e restauração temporária verificada."));
    },'run');
    const verify=button(w('Comprobar última copia','Check latest copy', "Verificar última cópia"),()=>action('/verify','POST',{},w('Restaurando la copia en una carpeta temporal…','Restoring the copy into a temporary directory…', "Restaurando a cópia em um diretório temporário…"),w('Última copia restaurada y comprobada en una carpeta temporal. Tus proyectos actuales se conservan.','Latest copy restored and checked in a temporary directory. Your current projects are retained.', "Última cópia restaurada e verificada em um diretório temporário. Seus projetos atuais foram mantidos.")),'verify');
    const refresh=button(w('Actualizar estado','Refresh status', "Atualizar status"),()=>action('','GET',undefined,w('Consultando estado…','Checking status…', "Verificando status…"),w('Estado actualizado.','Status refreshed.', "Status atualizado.")),'refresh');
    for(const node of [enabled,destination,interval,retention])node.addEventListener('input',()=>{configured=false;availability();});
    acknowledge.addEventListener('change',availability);
    body.append(h('p',{},w('Desactivados por defecto. Se ejecutan solo mientras el servidor local de report-gen sigue abierto; al volver a iniciarlo, se realiza una copia pendiente. No es una tarea del sistema operativo.','Disabled by default. Backups run only while the local report-gen server stays open; an overdue copy is made after restarting it. This is not an operating-system scheduled task.', "Desativado por padrão. Os backups só são executados enquanto o servidor local do report-gen permanece aberto; uma cópia atrasada é criada após reiniciá-lo. Esta não é uma tarefa agendada do sistema operacional.")),
      h('p',{},w('Copia privada sin cifrado: incluye todos los proyectos guardados, originales, versiones y bibliotecas. No guarda contraseñas ni incluye borradores pendientes del navegador. Elige una carpeta protegida en otro disco si necesitas protección frente a fallos del disco de trabajo.','Unencrypted private copy: includes all saved projects, originals, versions and libraries. No passwords are stored and pending browser drafts are excluded. Choose a protected directory on another disk for protection against failure of the working disk.', "Cópia privada sem criptografia: inclui todos os projetos salvos, originais, versões e bibliotecas. Nenhuma senha é armazenada e os rascunhos pendentes do navegador ficam de fora. Escolha um diretório protegido em outro disco para se proteger contra falhas do disco de trabalho.")),
      h('label',{class:'support-review-label'},enabled,w('Activar respaldos periódicos','Enable periodic backups', "Ativar backups periódicos")),
      h('label',{},w('Carpeta existente (ruta absoluta, fuera de la aplicación y del espacio de trabajo)','Existing directory (absolute path, outside the application and workspace)', "Diretório existente (caminho absoluto, fora da aplicação e do espaço de trabalho)"),destination),
      h('label',{},w('Frecuencia','Frequency', "Frequência"),interval),h('label',{},w('Copias a conservar (1–90)','Copies to retain (1–90)', "Cópias a manter (1–90)"),retention),
      h('p',{},w('Se crea una subcarpeta propia. La retención solo retira copias registradas e intactas de esa subcarpeta después de verificar una nueva; los archivos ajenos y destinos anteriores se conservan. Cambiar de destino inicia una serie nueva.','A dedicated subdirectory is created. Retention removes only registered, intact copies in that subdirectory after checking a new one; unrelated files and previous destinations are retained. Changing destination starts a new series.', "Um subdiretório dedicado é criado. A retenção remove somente cópias registradas e íntegras desse subdiretório após verificar uma nova; arquivos não relacionados e destinos anteriores são mantidos. Mudar o destino inicia uma nova série.")),
      h('label',{class:'support-review-label'},acknowledge,w('Entiendo que son copias privadas sin cifrar y he revisado el destino.','I understand these are unencrypted private copies and have reviewed the destination.', "Entendo que estas são cópias privadas sem criptografia e revisei o destino.")),
      h('div',{class:'modal-actions'},save,disable,run,verify,refresh),status,details);
    section.append(summary,body);parent.append(section);
    action('','GET',undefined,w('Consultando programación…','Checking schedule…', "Verificando agendamento…"),'');
  }
  return {mount};
})();

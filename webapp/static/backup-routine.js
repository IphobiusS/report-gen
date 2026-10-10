/* Local opt-in scheduling; private destinations never enter a report. */
const BackupRoutineUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  function mount(parent) {
    const section=h('details',{'data-backup-routine':''}),body=h('div',{class:'experience-body'});
    const summary=h('summary',{},w('Respaldos periódicos opcionales','Optional periodic backups'));
    const status=h('p',{role:'status','aria-live':'polite','data-routine-status':''});
    const details=h('div',{'data-routine-details':''});
    const enabled=h('input',{type:'checkbox','data-routine-enabled':''});
    const destination=h('input',{type:'text',maxlength:'4096',autocomplete:'off',spellcheck:'false','data-routine-destination':''});
    const interval=h('select',{'data-routine-interval':''},
      h('option',{value:'3600'},w('Cada hora','Every hour')),
      h('option',{value:'86400'},w('Cada día','Every day')),
      h('option',{value:'604800'},w('Cada semana','Every week')));
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
    const date=value=>value?new Date(value*1000).toLocaleString(S.uiLang==='en'?'en-US':'es-CL'):w('Todavía no','Not yet');
    function render(data,fields=false){
      last=data;
      if(fields){enabled.checked=data.enabled;destination.value=data.destination;interval.value=String(data.interval_seconds);retention.value=String(data.retention);configured=true;}
      details.replaceChildren(h('p',{},data.enabled?w('Programación activada.','Schedule enabled.'):w('Programación desactivada.','Schedule disabled.')),
        h('p',{},w('Última copia correcta: ','Last successful copy: ')+date(data.last_success)),
        h('p',{},w('Última restauración temporal correcta: ','Last successful temporary restoration: ')+date(data.last_verified)));
      if(data.directory)details.append(h('p',{style:'overflow-wrap:anywhere'},w('Carpeta privada: ','Private directory: ')+data.directory));
      if(data.latest_name)details.append(h('p',{style:'overflow-wrap:anywhere'},w('Última copia: ','Latest copy: ')+data.latest_name),
        h('p',{class:'update-digest'},'SHA-256: '+data.latest_sha256));
      if(data.enabled)details.append(h('p',{},data.scheduler_running
        ?(data.next_due?w('Próximo vencimiento: ','Next due: ')+date(data.next_due):w('Primera copia pendiente; se revisa en un minuto como máximo.','First copy pending; checked within one minute.'))
        :w('El programador no está activo en este proceso. Inicia el editor con su lanzador local.','The scheduler is not active in this process. Start the editor through its local launcher.')));
      if(data.last_error==='backup_failed')details.append(h('p',{role:'alert'},w('El último intento falló. Revisa espacio libre, permisos y destino; luego vuelve a crear o comprobar la copia.','The last attempt failed. Check free space, permissions and destination; then create or check the copy again.')));
      if(data.last_error==='retention_pending')details.append(h('p',{role:'alert'},w('La copia nueva está verificada, pero algunos archivos antiguos no se pudieron retirar. Se conservaron los archivos alterados o inaccesibles; revisa también las subcarpetas .retention-* si existen.','The new copy is verified, but some older files could not be removed. Changed or inaccessible files were retained; also review .retention-* subdirectories if present.')));
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
    const save=button(w('Guardar programación','Save schedule'),()=>action('','PUT',{
      enabled:enabled.checked,destination:destination.value.trim(),interval_seconds:Number(interval.value),retention:Number(retention.value),ack_unencrypted:acknowledge.checked
    },w('Guardando programación…','Saving schedule…'),w('Programación guardada. Los destinos anteriores se conservan.','Schedule saved. Previous destinations are retained.')),'save');
    const disable=button(w('Desactivar programación','Disable schedule'),()=>action('/disable','POST',{},w('Desactivando…','Disabling…'),w('Programación desactivada. Las copias se conservan.','Schedule disabled. Backups are retained.')),'disable');
    const run=button(w('Crear y comprobar copia ahora','Create and check copy now'),async()=>{
      if(busy||!configured)return;
      if(S.slug&&!await doSave())return;
      return action('/run','POST',{},w('Capturando datos guardados y comprobando una restauración temporal…','Capturing saved data and checking a temporary restoration…'),w('Copia creada y restauración temporal comprobada.','Copy created and temporary restoration checked.'));
    },'run');
    const verify=button(w('Comprobar última copia','Check latest copy'),()=>action('/verify','POST',{},w('Restaurando la copia en una carpeta temporal…','Restoring the copy into a temporary directory…'),w('Última copia restaurada y comprobada en una carpeta temporal. Tus proyectos actuales se conservan.','Latest copy restored and checked in a temporary directory. Your current projects are retained.')),'verify');
    const refresh=button(w('Actualizar estado','Refresh status'),()=>action('','GET',undefined,w('Consultando estado…','Checking status…'),w('Estado actualizado.','Status refreshed.')),'refresh');
    for(const node of [enabled,destination,interval,retention])node.addEventListener('input',()=>{configured=false;availability();});
    acknowledge.addEventListener('change',availability);
    body.append(h('p',{},w('Desactivados por defecto. Se ejecutan solo mientras el servidor local de report-gen sigue abierto; al volver a iniciarlo, se realiza una copia pendiente. No es una tarea del sistema operativo.','Disabled by default. Backups run only while the local report-gen server stays open; an overdue copy is made after restarting it. This is not an operating-system scheduled task.')),
      h('p',{},w('Copia privada sin cifrado: incluye todos los proyectos guardados, originales, versiones y bibliotecas. No guarda contraseñas ni incluye borradores pendientes del navegador. Elige una carpeta protegida en otro disco si necesitas protección frente a fallos del disco de trabajo.','Unencrypted private copy: includes all saved projects, originals, versions and libraries. No passwords are stored and pending browser drafts are excluded. Choose a protected directory on another disk for protection against failure of the working disk.')),
      h('label',{class:'support-review-label'},enabled,w('Activar respaldos periódicos','Enable periodic backups')),
      h('label',{},w('Carpeta existente (ruta absoluta, fuera de la aplicación y del espacio de trabajo)','Existing directory (absolute path, outside the application and workspace)'),destination),
      h('label',{},w('Frecuencia','Frequency'),interval),h('label',{},w('Copias a conservar (1–90)','Copies to retain (1–90)'),retention),
      h('p',{},w('Se crea una subcarpeta propia. La retención solo retira copias registradas e intactas de esa subcarpeta después de verificar una nueva; los archivos ajenos y destinos anteriores se conservan. Cambiar de destino inicia una serie nueva.','A dedicated subdirectory is created. Retention removes only registered, intact copies in that subdirectory after checking a new one; unrelated files and previous destinations are retained. Changing destination starts a new series.')),
      h('label',{class:'support-review-label'},acknowledge,w('Entiendo que son copias privadas sin cifrar y he revisado el destino.','I understand these are unencrypted private copies and have reviewed the destination.')),
      h('div',{class:'modal-actions'},save,disable,run,verify,refresh),status,details);
    section.append(summary,body);parent.append(section);
    action('','GET',undefined,w('Consultando programación…','Checking schedule…'),'');
  }
  return {mount};
})();

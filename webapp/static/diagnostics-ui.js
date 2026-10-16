/* Structural locations supplied by validators; never infer them from prose. */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DiagnosticUI = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const labels = {
    format:['Formato','Format','Formato'], record:['Registro','Record','Registro'],
    line:['Línea','Line','Linha'], line_end:['Hasta línea','Through line','Até a linha'],
    column:['Columna','Column','Coluna'], field:['Campo','Field','Campo'],
    finding_id:['Hallazgo','Finding','Achado'], finding_uid:['UID del hallazgo','Finding UID','UID do achado'],
    section:['Sección','Section','Seção'], table:['Tabla','Table','Tabela'], row:['Fila','Row','Linha da tabela'],
    cell:['Celda','Cell','Célula'], run_index:['Ejecución','Run','Execução'],
    result_index:['Resultado','Result','Resultado'], evidence_index:['Evidencia','Evidence','Evidência']
  };
  const numeric = new Set(['record','line','line_end','column','table','row','cell']);
  const indexed = new Set(['run_index','result_index','evidence_index']);
  function locationText(location, language='es') {
    if (!location || typeof location !== 'object' || Array.isArray(location)) return '';
    const lang = language==='en'?1:(language==='pt'||language==='pt-br'?2:0), parts=[];
    for (const [key, names] of Object.entries(labels)) {
      const value=location[key];
      if (numeric.has(key) || indexed.has(key)) {
        const min=indexed.has(key)?0:1;
        if (Number.isInteger(value) && value>=min && value<10000000) parts.push(names[lang]+': '+(indexed.has(key)?value+1:value));
      } else if (typeof value==='string' && /^[A-Za-z0-9_][A-Za-z0-9_.\[\] ()/+\-]{0,159}$/.test(value)) {
        parts.push(names[lang]+': '+value);
      }
    }
    return parts.join(' · ');
  }
  function render(details, language='es', source=null) {
    const locations = new Set();
    const origin=locationText(source,language);
    if (origin) locations.add(origin);
    if (Array.isArray(details)) for (const detail of details.slice(0,64)) {
      const text=locationText(detail?.location,language);
      if(text) locations.add(text);
    }
    if(!locations.size) return null;
    const box=document.createElement('div');box.className='diagnostic-locations';box.dataset.diagnosticLocations='';
    for(const text of locations){const line=document.createElement('p');line.textContent=text;box.append(line);}
    return box;
  }
  return Object.freeze({locationText,render});
});

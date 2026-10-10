/* Private, per-tab journals. IndexedDB completion, not an input event, means recoverable. */
(function(root){
'use strict';
const clone=v=>v===undefined?undefined:JSON.parse(JSON.stringify(v));
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
class DraftJournal{
  constructor(){this.tail=Promise.resolve();this.id=(root.crypto?.randomUUID?.()||String(Date.now())+Math.random());this.db=null;}
  async open(){
    if(this.db)return this.db;
    if(!root.indexedDB)throw Error('El navegador no permite borradores locales / Browser draft storage unavailable');
    this.db=await new Promise((resolve,reject)=>{const r=root.indexedDB.open('report-gen-drafts',1);r.onupgradeneeded=()=>r.result.createObjectStore('drafts',{keyPath:'id'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('Borradores bloqueados / Draft storage blocked'));});
    return this.db;
  }
  run(mode,fn){const job=this.tail.catch(()=>{}).then(async()=>{const db=await this.open();return new Promise((resolve,reject)=>{const tx=db.transaction('drafts',mode),store=tx.objectStore('drafts');let value;fn(store,x=>value=x);tx.oncomplete=()=>resolve(value);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('Draft transaction aborted'));});});this.tail=job;return job;}
  put(record){return this.run('readwrite',store=>store.put({...record,id:this.id+':'+record.slug,format:'report-gen-draft',version:1,updated:Date.now()}));}
  remove(id){return this.run('readwrite',store=>store.delete(id));}
  removeUnchanged(record){return this.run('readwrite',(store,done)=>{const r=store.get(record.id);r.onsuccess=()=>{const unchanged=equal(r.result,record);if(unchanged)store.delete(record.id);done(unchanged);};});}
  clearOwn(slug){return this.remove(this.id+':'+slug);}
  list(slug){return this.run('readwrite',(store,done)=>{const r=store.getAll();r.onsuccess=()=>{const cut=Date.now()-30*86400000;for(const row of r.result)if(row.updated<cut)store.delete(row.id);done(r.result.filter(x=>x.slug===slug&&x.updated>=cut).sort((a,b)=>b.updated-a.updated));};});}
}
// Pending forms have their own store: saving a project must never clear them.
class PendingJournal {
  constructor(){this.tail=Promise.resolve();this.id=root.crypto?.randomUUID?.()||String(Date.now())+Math.random();this.db=null;}
  async open(){
    if(this.db)return this.db;
    if(!root.indexedDB)throw Error('Almacenamiento local no disponible / Local storage unavailable');
    this.db=await new Promise((resolve,reject)=>{const r=root.indexedDB.open('report-gen-pending',1);r.onupgradeneeded=()=>r.result.createObjectStore('pending',{keyPath:'id'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('Almacenamiento local bloqueado / Local storage blocked'));});return this.db;
  }
  run(fn){const job=this.tail.catch(()=>{}).then(async()=>{const db=await this.open();return new Promise((resolve,reject)=>{const tx=db.transaction('pending','readwrite'),store=tx.objectStore('pending');let value;try{fn(store,x=>value=x,tx);}catch(e){tx.abort();reject(e);}tx.oncomplete=()=>resolve(value);tx.onerror=()=>reject(tx.error||Error('No se pudo guardar / Could not save'));tx.onabort=()=>reject(tx.error||Error('Límite local de 64 MiB / Local 64 MiB limit'));});});this.tail=job;return job;}
  put(input){
    const data=clone(input.data),file=input.file||null,bytes=new Blob([JSON.stringify(data)]).size+(file?.size||0);
    if(new Blob([JSON.stringify(data)]).size>1024*1024||file?.size>16*1024*1024)return Promise.reject(Error('Máximo 1 MiB de texto y 16 MiB por imagen / Maximum 1 MiB text and 16 MiB per image'));
    const row={...input,data,file,id:this.id+':'+input.slug+':'+input.key,format:'report-gen-pending',version:1,bytes,updated:Date.now(),token:root.crypto?.randomUUID?.()||String(Date.now())+Math.random()};
    return this.run((store,done,tx)=>{const r=store.getAll();r.onsuccess=()=>{let size=bytes;for(const old of r.result){if(old.updated<Date.now()-30*86400000)store.delete(old.id);else if(old.id!==row.id)size+=old.bytes||0;}if(size>64*1024*1024){tx.abort();return;}store.put(row);done(row);};});
  }
  list(slug){return this.run((store,done)=>{const r=store.getAll();r.onsuccess=()=>{const cut=Date.now()-30*86400000;for(const row of r.result)if(row.updated<cut)store.delete(row.id);done(r.result.filter(row=>row.slug===slug&&row.updated>=cut).sort((a,b)=>b.updated-a.updated));};});}
  removeUnchanged(row){return this.run((store,done)=>{const r=store.get(row.id);r.onsuccess=()=>{const same=!!r.result&&r.result.token===row.token;if(same)store.delete(row.id);done(same);};});}
}
function mergeDraft(base,local,remote,choices={}){
  const conflicts=[];
  function walk(a,b,c,path){
    if(equal(b,c))return clone(b);
    if(equal(a,b))return clone(c);
    if(equal(a,c))return clone(b);
    const obj=v=>v&&typeof v==='object'&&!Array.isArray(v);
    if(obj(a)&&obj(b)&&obj(c)){
      const out=Object.create(null);for(const k of new Set([...Object.keys(a),...Object.keys(b),...Object.keys(c)])){const v=walk(a[k],b[k],c[k],path+'/'+k);if(v!==undefined)out[k]=v;}return out;
    }
    const keyed=v=>Array.isArray(v)&&v.every(x=>obj(x)&&typeof x.uid==='string')&&new Set(v.map(x=>x.uid)).size===v.length;
    if(keyed(a)&&keyed(b)&&keyed(c)){
      const maps=[a,b,c].map(rows=>new Map(rows.map(x=>[x.uid,x]))),ids=new Set([...a,...b,...c].map(x=>x.uid)),out=new Map();
      for(const id of ids){const v=walk(...maps.map(m=>m.get(id)),path+'/'+id);if(v!==undefined)out.set(id,v);}
      let order=b.map(x=>x.uid);const original=a.map(x=>x.uid),server=c.map(x=>x.uid);
      if(equal(order,original))order=server;
      else if(!equal(server,original)&&!equal(order,server)){const p=path+'/order';conflicts.push({path:p,base:original,local:order,remote:server});if(choices[p]==='remote')order=server;}
      return [...new Set([...order,...out.keys()])].filter(id=>out.has(id)).map(id=>out.get(id));
    }
    conflicts.push({path,base:clone(a),local:clone(b),remote:clone(c)});
    return clone(choices[path]==='remote'?c:b);
  }
  return {data:clone(walk(base,local,remote,'')),conflicts};
}
root.DraftJournal=DraftJournal;root.PendingJournal=PendingJournal;root.mergeDraft=mergeDraft;
if(typeof module!=='undefined')module.exports={DraftJournal,PendingJournal,mergeDraft};
})(typeof window!=='undefined'?window:globalThis);

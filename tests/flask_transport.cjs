/* Real Flask endpoints and session over pipes; no HTTP listener or simulated API. */
const {spawn}=require('node:child_process');
const path=require('node:path');
module.exports=function transport(seed=false){
  const child=spawn(process.env.RG_PYTHON||'python',[path.join(__dirname,'flask_stdio.py'),...(seed?['--seed']:[])],{stdio:['pipe','pipe','inherit']});
  let next=0,buffer='';const pending=new Map();
  child.stdout.on('data',chunk=>{buffer+=chunk;let i;while((i=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,i);buffer=buffer.slice(i+1);if(!line)continue;const r=JSON.parse(line);const job=pending.get(r.id);pending.delete(r.id);if(r.error)job.reject(Error(r.error));else job.resolve(new Response(Buffer.from(r.body,'base64'),{status:r.status,headers:r.headers}));}});
  child.on('exit',code=>{for(const job of pending.values())job.reject(Error('Flask bridge exited: '+code));pending.clear();});
  return {
    async fetch(url,options={}){
      const request=new Request(new URL(url,'http://127.0.0.1'),options);
      const bytes=Buffer.from(await request.arrayBuffer());const parsed=new URL(request.url);
      return new Promise((resolve,reject)=>{const id=++next;pending.set(id,{resolve,reject});child.stdin.write(JSON.stringify({id,path:parsed.pathname+parsed.search,method:request.method,headers:Object.fromEntries(request.headers),body:bytes.toString('base64')})+'\n');});
    }, close(){child.stdin.end();}
  };
};

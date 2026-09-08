const test = require('node:test');
const assert = require('node:assert/strict');
const {ProjectStore} = require('../webapp/static/save-manager.js');
const timers = {setTimeout: () => 1, clearTimeout: () => {}};
const response = (data, etag = '"r1"', status = 200) => ({ok: status < 400, status, json: async () => data, headers: {get: () => etag}});
const deferred = () => {let resolve; const promise = new Promise(r => resolve = r); return {promise, resolve};};

test('failed save keeps changes pending and does not announce success', async () => {
  const events = [];
  const store = new ProjectStore(async (url, options) => options ? response({error:'Disk full'}, null, 500) : response({title:'A'}), state => events.push(state), timers);
  await store.load('a'); store.data.title='unsaved'; store.changed();
  await assert.rejects(store.save(), /Disk full/);
  assert.equal(store.dirty,true); assert.equal(events.at(-1),'error'); assert.ok(!events.includes('saved'));
});

test('project switch flushes A before requesting B', async () => {
  const events=[]; const gate=deferred();
  const store=new ProjectStore(async (url, options) => {
    events.push({url, options});
    if(options) return gate.promise;
    return response({title:url.endsWith('/a')?'A':'B'});
  },()=>{},timers);
  await store.load('a'); store.data.title='A edited'; store.changed();
  const switching=store.load('b'); await new Promise(r=>setImmediate(r));
  assert.equal(store.slug,'a'); assert.equal(events.at(-1).url,'/api/projects/a');
  assert.equal(JSON.parse(events.at(-1).options.body).title,'A edited');
  gate.resolve(response({},'"r2"')); await switching;
  assert.equal(store.slug,'b'); assert.equal(store.data.title,'B'); assert.equal(store.dirty,false);
});

test('an old acknowledgement cannot clear newer edits; saves are serialized', async () => {
  const gate=deferred(); const writes=[];
  const store=new ProjectStore(async (url, options) => {
    if(!options)return response({title:'A'});
    writes.push(options);
    return writes.length===1?gate.promise:response({},'"r3"');
  },()=>{},timers);
  await store.load('a');store.data.title='first';store.changed();const first=store.save();
  await new Promise(r=>setImmediate(r));
  store.data.title='second';store.changed();const second=store.save();
  assert.equal(writes.length,1);
  gate.resolve(response({},'"r2"'));await first;
  assert.equal(store.dirty,true);
  await second;assert.equal(store.dirty,false);
  assert.equal(writes[1].headers['If-Match'],'"r2"');
  assert.equal(JSON.parse(writes[0].body).title,'first');assert.equal(JSON.parse(writes[1].body).title,'second');
});

test('failed flush prevents changing project', async () => {
  const reads=[];
  const store=new ProjectStore(async(url,options)=>{
    if(options)return response({error:'Conflict'},null,409);
    reads.push(url);return response({title:'A'});
  },()=>{},timers);
  await store.load('a');store.changed();await assert.rejects(store.load('b'),/Conflict/);
  assert.equal(store.slug,'a');assert.equal(store.dirty,true);assert.equal(reads.length,1);assert.equal(store.loading,false);
});

test('second navigation cannot replace state while a load is pending', async () => {
  const gate=deferred();const store=new ProjectStore(()=>gate.promise,()=>{},timers);
  const first=store.load('a');assert.equal(await store.load('b'),false);
  gate.resolve(response({title:'A'}));await first;assert.equal(store.slug,'a');
});

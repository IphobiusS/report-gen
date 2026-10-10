(function (root) {
  "use strict";
  class ProjectStore {
    constructor(request, notify = () => {}, timers = globalThis) {
      this.request = request; this.notify = notify; this.timers = timers;
      this.slug = null; this.data = null; this.etag = null;
      this.revision = 0; this.savedRevision = 0; this.pending = Promise.resolve();
      this.timer = null; this.loading = false; this.lastSavedAt = null; this.lastError = null;
      this.base=null; this.journal=root.DraftJournal?new root.DraftJournal():null; this.recoverableRevision=0; this.draftError=null; this.recovery=[];
    }
    get dirty() { return this.revision !== this.savedRevision; }
    changed() {
      this.revision++; this.persistDraft(); this.notify(this.lastError ? "error" : "pending", this.lastError);
      this.timers.clearTimeout(this.timer);
      this.timer = this.timers.setTimeout(() => this.save().catch(() => {}), 700);
    }
    persistDraft() {
      if(!this.journal||!this.slug)return Promise.resolve();
      const record={slug:this.slug,base:this.base,etag:this.etag,data:JSON.parse(JSON.stringify(this.data)),revision:this.revision};
      return this.journal.put(record).then(()=>{this.recoverableRevision=record.revision;this.draftError=null;this.notify(this.lastError?'error':'pending',this.lastError);}).catch(error=>{this.draftError=error;this.recoverableRevision=0;this.notify(this.lastError?'error':'pending',this.lastError);});
    }
    draftFile(){return {format:'report-gen-draft',version:1,slug:this.slug,base:this.base,etag:this.etag,data:this.data,updated:Date.now()};}
    async remote(){
      const response=await this.request(`/api/projects/${encodeURIComponent(this.slug)}`);
      if(!response.ok)throw Error(`HTTP ${response.status}`);
      return {data:await response.json(),etag:response.headers.get('ETag')};
    }
    adopt(data,remote){
      this.data=data;this.base=JSON.parse(JSON.stringify(remote.data));this.etag=remote.etag;
      this.lastError=null;this.revision++;this.persistDraft();this.notify('pending');
    }
    save() {
      this.timers.clearTimeout(this.timer); this.timer = null;
      if (!this.slug || !this.dirty) return this.pending;
      const snapshot = { slug: this.slug, data: JSON.parse(JSON.stringify(this.data)), revision: this.revision };
      const task = this.pending.catch(() => {}).then(async () => {
        if (snapshot.revision <= this.savedRevision) return;
        this.notify("saving");
        const response = await this.request(`/api/projects/${encodeURIComponent(snapshot.slug)}`, {
          method: "PUT", headers: { "Content-Type": "application/json", "If-Match": this.etag }, body: JSON.stringify(snapshot.data)
        });
        if (!response.ok) {const error=new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);error.status=response.status;throw error;}
        this.etag = response.headers.get("ETag");
        this.savedRevision = snapshot.revision;
        this.base=JSON.parse(JSON.stringify(snapshot.data));
        if(!this.dirty && this.journal){await this.journal.clearOwn(snapshot.slug).catch(error=>{this.draftError=error;});this.recoverableRevision=0;}
        this.lastSavedAt = new Date(); this.lastError = null;
        this.notify(this.dirty ? "saving" : "saved");
      }).catch(error => { this.lastError = error; this.notify("error", error); throw error; });
      this.pending = task;
      return task;
    }
    async load(slug) {
      if (this.loading) return false;
      this.loading = true; this.notify("loading");
      try {
        await this.save();
        const response = await this.request(`/api/projects/${encodeURIComponent(slug)}`);
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);
        const data = await response.json();
        this.slug = slug; this.data = data; this.etag = response.headers.get("ETag");
        this.revision = 0; this.savedRevision = 0; this.pending = Promise.resolve();
        this.lastSavedAt = null; this.lastError = null;
        this.base=JSON.parse(JSON.stringify(data));this.recovery=[];this.recoverableRevision=0;
        if(this.journal){try{this.recovery=await this.journal.list(slug);}catch(error){this.draftError=error;}}
        this.notify("ready"); return true;
      } catch (error) { this.lastError = error; this.notify("error", error); throw error; }
      finally { this.loading = false; this.notify("loaded"); }
    }
    reset() {
      this.timers.clearTimeout(this.timer); this.timer = null;
      this.slug = null; this.data = null; this.etag = null; this.lastSavedAt = null; this.lastError = null;
      this.revision = this.savedRevision = 0; this.pending = Promise.resolve();
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { ProjectStore };
  root.ProjectStore = ProjectStore;
})(typeof window !== "undefined" ? window : globalThis);

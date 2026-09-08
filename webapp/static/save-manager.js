(function (root) {
  "use strict";
  class ProjectStore {
    constructor(request, notify = () => {}, timers = globalThis) {
      this.request = request; this.notify = notify; this.timers = timers;
      this.slug = null; this.data = null; this.etag = null;
      this.revision = 0; this.savedRevision = 0; this.pending = Promise.resolve();
      this.timer = null; this.loading = false;
    }
    get dirty() { return this.revision !== this.savedRevision; }
    changed() {
      this.revision++; this.notify("saving");
      this.timers.clearTimeout(this.timer);
      this.timer = this.timers.setTimeout(() => this.save().catch(() => {}), 700);
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
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);
        this.etag = response.headers.get("ETag");
        this.savedRevision = snapshot.revision;
        this.notify(this.dirty ? "saving" : "saved");
      }).catch(error => { this.notify("error", error); throw error; });
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
        this.notify("ready"); return true;
      } catch (error) { this.notify("error", error); throw error; }
      finally { this.loading = false; this.notify("loaded"); }
    }
    reset() {
      this.timers.clearTimeout(this.timer); this.timer = null;
      this.slug = null; this.data = null; this.etag = null;
      this.revision = this.savedRevision = 0; this.pending = Promise.resolve();
    }
  }
  if (typeof module !== "undefined" && module.exports) module.exports = { ProjectStore };
  root.ProjectStore = ProjectStore;
})(typeof window !== "undefined" ? window : globalThis);

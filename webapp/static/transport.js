/* HTTP boundary for the local editor: UI language, CSRF and workspace identity.
 * No project copy or DOM state belongs here. Dependencies are injected so the
 * same production boundary is exercised by browser and contract tests. */
(function(root, factory) {
  const transport = factory();
  if (typeof module === 'object' && module.exports) module.exports = transport;
  else root.ReportTransport = transport;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
'use strict';

async function requireOk(response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(typeof body?.error === 'string' ? body.error : `HTTP ${response.status}`);
    error.status = response.status;
    error.diagnostics = Array.isArray(body?.diagnostics) ? body.diagnostics.slice(0,64) : [];
    throw error;
  }
  return response;
}

function create({fetch, workspace, getLanguage, getETag, baseURL, onWorkspaceChanged}) {
  let csrfPromise;
  const language = () => { const value=String(getLanguage()||'es').toLowerCase();return value==='pt'||value==='pt-br'?'pt':value==='en'?'en':'es'; };
  const messageFor=(lang,es,en,pt)=>lang==='pt'?pt:lang==='en'?en:es;
  // BrowserWorkspace is the sole identity used by HTTP and browser journals.
  const identity = () => { try { return workspace.current(); } catch (_) { return null; } };
  const workspaceHeaders = () => { const id = identity(); return id ? {'X-Report-Gen-Workspace':id} : {}; };

  function changedWorkspaceError() {
    workspace.block();
    const message = messageFor(language(),
      'El servidor cambió de espacio. Esta pestaña no enviará cambios. Descarga tu borrador antes de recargar.',
      'The server changed workspace. This tab will not send changes. Download your draft before reloading.',
      'O servidor mudou de espaço de trabalho. Esta aba não enviará alterações. Baixe seu rascunho antes de recarregar.');
    onWorkspaceChanged?.(message);
    const error = new Error(message); error.status = 409; return error;
  }

  function checkResponseWorkspace(response, uiLanguage) {
    const expected = identity();
    if (!expected) return;
    const received = response.headers.get('X-Report-Gen-Workspace');
    if (received === expected) return;
    if (received !== null || response.ok) throw changedWorkspaceError();
    // An intermediary can fail without the app's headers. Reject its unverified
    // body, retain the original scope and allow a deliberate retry.
    const error = new Error(messageFor(uiLanguage,
      'El servidor devolvió un error sin verificar. Tus cambios siguen pendientes; vuelve a intentarlo.',
      'The server returned an unverified error. Your changes are still pending; try again.',
      'O servidor retornou um erro não verificado. Suas alterações continuam pendentes; tente novamente.'));
    error.status = response.status; throw error;
  }

  async function request(url, options = {}) {
    if (workspace.blocked()) throw changedWorkspaceError();
    const uiLanguage = language();
    options = {...options, headers:{...options.headers, 'X-UI-Language':uiLanguage, ...workspaceHeaders()}};
    const method = (options.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
      csrfPromise ||= fetch('/api/session', {headers:{'X-UI-Language':uiLanguage, ...workspaceHeaders()}}).then(async response => {
        checkResponseWorkspace(response, uiLanguage);
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error ||
          messageFor(uiLanguage,'No se pudo iniciar la sesión local','Could not start the local session','Não foi possível iniciar a sessão local'));
        return (await response.json()).csrf;
      }).catch(error => { csrfPromise = null; throw error; });
      options = {...options, headers:{...options.headers, 'X-CSRF-Token':await csrfPromise}};
      // Another pending response can block the tab while CSRF is being fetched.
      // A valid older handshake must never resume a mutation after that block.
      if (workspace.blocked()) throw changedWorkspaceError();
    }
    const response = await fetch(url, options);
    checkResponseWorkspace(response, uiLanguage);
    if (workspace.blocked()) throw changedWorkspaceError();
    return response;
  }

  function bindSession(session) {
    if (workspace.blocked()) throw changedWorkspaceError();
    const id = workspace.bind(session.workspace_id);
    csrfPromise = session.csrf ? Promise.resolve(session.csrf) : null;
    return id;
  }

  function scopedResourceURL(value) {
    if (typeof value !== 'string' || !value.startsWith('/api/')) return value;
    const id = identity();
    if (!id) throw Error(messageFor(language(),'Espacio de trabajo todavía no preparado','Workspace is not ready','O espaço de trabalho ainda não está pronto'));
    const url = new URL(value, baseURL());
    url.searchParams.set('workspace_id', id);
    return url.pathname + url.search + url.hash;
  }

  const api = Object.freeze({
    get: url => request(url).then(requireOk).then(response => response.json()),
    post: (url, body) => request(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})}),
    put: (url, body) => request(url, {method:'PUT', headers:{'Content-Type':'application/json', 'If-Match':getETag()}, body:JSON.stringify(body)}).then(requireOk),
    del: url => request(url, {method:'DELETE', headers:{'If-Match':getETag()}}).then(requireOk),
  });
  return Object.freeze({request, requireOk, api, bindSession, scopedResourceURL});
}
return Object.freeze({create});
});

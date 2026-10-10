# Evidence and decisions (0.23.0)

Open the sidebar entry or Overview card. This is optional; reading screens does not add fields. Claims, comments and review are private working records, excluded from technical and standard exports. Structured business decisions appear only in the executive profile, not automatically in the technical PDF.

- **Claims:** record observed facts, inferences or hypotheses and link existing supporting evidence. State what it demonstrates and what it does not. A link is not technical verification.
- **Business risk:** author service, objective, consequence, agreed tolerance, source, assumptions, owner and the reason for a priority. Unknown context stays unassigned. CVSS does not calculate loss or risk appetite.
- **Comments and review:** inspect a field before commenting. Identities are self-declared locally. Comments remain outside every delivery, including comments marked public (local visibility only). Content, image bytes or comments changed after a decision make it stale. Approval is not a technical validation or publication permission.
- **Audiences:** select findings by stable identity and inspect the rendered prose and exact inclusion plan. Section selection belongs only to the technical profile; an internal reference whose destination was excluded blocks delivery. Technical retains selected content, metadata-clean published images and reviewed, included annexes. Executive keeps titles, description, impact, remediation, technical severity/CVSS and documented business decisions; it excludes images, attachments, reproduction, code blocks, link destinations and recognized technical paths. The client name remains unless you provide a client alias or literal substitution. Public rebuilds a document from an authored title, replacement client identity and explicitly approved prose; it retains project language and theme but excludes source identities, contacts, technical scores, evidence and source sections. It requires at least one literal substitution, review confirmation, consent and self-declared simulation/authorization. Substitutions are case-sensitive and run before text escaping; inspect the result, including names containing dots or underscores. Potential-secret patterns may block a derivative but do not replace human review. These declarations do not establish actual permission. Executive and public derivatives declare their omissions and are not complete technical reports. Comments, editorial reviews and private history are not copied into deliveries. Every package and its formats use one saved revision; preview and generation require that revision and never edit the project.
- **Visual review:** inspect real pages from a generated PDF or the main informe.pdf in a delivery ZIP (PDF attachments remain separate) or upload a local PDF. Annotate issues and download a manual record tied to the exact PDF SHA-256 and context revision. An uploaded PDF is not proved to originate from that revision. This does not verify Word, a vulnerability or permission to publish. Access expires after 30 minutes; memory is purged on the next preview request or restart. Limits: 16 MB, 500 pages, four previews per session, eight globally. Clear previews when finished.
- **Editorial:** deterministic rules are advisory. Optional Ollama receives only selected description, impact or remediation fields (24 KB maximum), with explicit consent. No document, images, history or comments are sent. Only fixed loopback 127.0.0.1:11434 is used, without environment proxies or redirects. Known remote models are rejected. Disable cloud and search on the Ollama server using OLLAMA_NO_CLOUD=1 and restart it. report-gen cannot certify another process's network isolation. Compare proposals before accepting; source and revision must remain unchanged. A model can fabricate or change meaning, so verify every suggestion.

## Optional requirements

With the same Python environment as report-gen:

```bash
.venv/bin/python -m pip install -e '.[previews]'
```

Preview extras install PyMuPDF and Playwright. Thumbnails use PyMuPDF. Without the dependency the other features work and the UI explains what is missing. Rendering is in a bounded process with size, page and time limits; POSIX also applies memory/CPU limits. Those POSIX limits are absent on Windows.

Ollama is a separately installed optional service. report-gen does not install, start, download or configure it. A local GGUF model must already be installed. See https://docs.ollama.com/faq and https://docs.ollama.com/api/chat. Disable cloud on the service itself, not only the report-gen shell. No model or quality guarantee is included.

## Scale and backups

Finding sidebar and board paginate 50 records; evidence gallery paginates 20. Open associations for paged finding selection. Search and exports still cover all records. Cross-page move controls preserve ordering.

Claims, risks, comments and review belong to private editable backups. Do not publish a project backup as a client delivery. AI proposals and PDF reviews are temporary; accept or download what you need to retain. Clearing a preview removes memory, not your source PDF. Back up before upgrading.

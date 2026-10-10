> **Historical document.** This README accompanied the 0.25.0 delivery, including upgrade references that still said 0.24.0. Use the [current 0.25.0 guide](../guide.en.md) and [current welcome](../../README.en.md) for current instructions. Content is retained; only its links have been relocated.

# report-gen 0.25.0

Turn your pentest work into a clear report: organize findings, link evidence and prepare PDF, Word, Markdown and portable HTML from one saved revision. Work locally without accounts, telemetry or external editing services. Prometeo and Evaristo accompany the workspace.

Document scope and methodology, calculate CVSS 3.1 or 4.0, track remediation and retests, retain versions and review what you share before delivery. The tool organizes your documentation; technical verification and conclusions remain the assessor's responsibility.

[Español](README-0.25.0-original.md) · [Changes and validation](../../VALIDACION-0.25.0.md) · [Security](../../SECURITY.md) · [Contributing](../../CONTRIBUTING.md)

## New in 0.25.0

The retest matrix keeps each bar with its label and count, including enlarged text and printing. Delivery preparation shows a status for each check, a counter and links to the relevant workspace. Human review remains explicit.

Preview initially fits the available width and supports manual zoom. PDF routes group steps by phase, retain their complete text alternative and continue when steps or long text need more space. Paragraphs introducing tables, commands or figures stay with the start of their block where space permits.

YAML reads use libyaml when its input behavior preserves the existing contract, with a bounded Python fallback for compatibility syntax. Both paths retain byte, node, depth and expansion limits, dates as text and duplicate-key rejection. Measurements and their limitations are recorded in this release's validation.

`python -m delivery_signature fingerprint --public-key KEY.pem` displays an Ed25519 public-key fingerprint for comparison through a trusted channel. On POSIX, the launcher replaces itself with the server, so signals terminate that same process. Continuous integration includes the new UI checks.

## New in 0.24.0

Incremental saves reuse unchanged finding fragments and avoid duplicating them in large-project history. A verified unchanged save does not write files or change the ETag. Changes still activate atomically and remain recoverable; `engagement.yaml` stays a complete, interoperable YAML document.

The improvement focuses on localized edits and unchanged saves. Initial compound history creation and cold-cache saves can add overhead; faster saves are not guaranteed in every case. This release's validation records the measurements, metadata cost and observed memory.

Optional detached signatures verify report deliveries with an externally pinned public key. They bind the exact ZIP and manifest bytes without modifying the delivery. Use the local `python -m delivery_signature` command; the editor never receives the private key. See [Delivery signing](../delivery-signing.md) for the optional dependency and commands. Private-key generation and signing require POSIX; normal editing and exports retain their previous platforms.

To move a 0.24.0 project to an older version, export a backup using 0.24.0. Portable v1 backups materialize the history objects. Do not copy a large project's local history directory directly into 0.23.4: it cannot interpret the new compound objects. Keep the source until restoration has been checked.

## New in 0.23.4

The server's own errors follow the interface language, including validation messages and export jobs. Report language remains an independent choice; error codes, revisions and security controls keep their existing role.

Machine-mode PDFs include a Documented route with recorded steps and figure references. Arrows indicate documentation order; they do not prove causality or successful exploitation. Bounded panels have a complete text version, so long routes may add report pages. HTML, Word and Markdown keep their previous content.

## New in 0.23.3

Each finding has Evidence and Decisions tabs that reuse existing links, claims and business context. Switching tabs preserves drafts; reading a view does not save or technically verify a finding.

Changes since delivery compares the saved revision with an explicitly identified locally marked delivery snapshot. Choose another baseline when needed and distinguish private from shareable comparisons. The local mark does not prove export success or client receipt; removing a finding does not prove remediation.

The Retest matrix summarizes the latest valid recorded observation with filters and a numeric chart. Remediation status, technical verification and retest result remain separate. When a draft changes, explicitly save and reload these views.

## New in 0.23.2

Use `j` and `k` outside editable fields to move through findings, and `?` to open shortcut help. Inside the finding editor, `Ctrl+Enter` or `⌘+Enter` saves and advances only after a successful save with an unchanged selection. Finding cards and the board show recorded assets, owner, status and linked evidence.

Review groups its items and lets you save and check the next pending item. Progress compares initial items no longer detected in this session; it does not certify technical validation. Deliver adds a saved-revision checklist for annexes, possible secret patterns and evidence associations, with required human review and stale-draft notices.

Import and restore recovery also fixes an inherited defect: a transient cleanup failure could recreate a private preparation directory and block workspace backup. Project publication and snapshots retain their recovery protections.

## New in 0.23.1

Move between findings with Previous/Next in the project order, without returning to the table. The visible HTML preview follows the current finding after loading, using the identities in that rendered snapshot; its highlight stays inside the preview and does not enter exported documents. Hidden panes stop requesting previews, including narrow layouts. The welcome/About mark uses a smaller lossless WebP.

The top navigation, asset relationships, CVSS calculator and gallery actions reflow on narrow screens with text enlarged to 200%.

New DOCX files use the prepared report's title, assessor and language. Template comments and inherited dates are removed; unknown creation dates are omitted.

## New in 0.23.0

**Evidence and decisions** adds six optional workspaces: claims and limitations, business context, comments and revision-bound review, audience deliveries, actual PDF review and editorial help. Reading them does not fill in a project or verify findings.

Technical, executive and public deliveries contain different, independent content. Public publication requires explicit approved prose, aliases and consent. Private comments, original client metadata, raw commands and evidence are excluded. Review the inclusion plan before exporting.

PDF thumbnails require optional preview extras. Local AI remains idle until explicitly requested and only sends selected fields to loopback Ollama; proposals need explicit acceptance. See [requirements and limitations](../evidence-decisions-0230.en.md). Normal editing needs neither Ollama nor an external connection.

## New in 0.22.1

The [changelog](../../CHANGELOG.md) includes the missing 0.22.0 entry. The header uses the SVG symbol from startup; the brand PNG is retained and recompressed without changing its pixels. The guide and fixes from 0.22.0 remain available, with their [original validation record](../../VALIDACION-0.22.0.md).

## New in 0.22.0

The optional **Guide: first report** explains the workflow in six steps, with instructional examples and links to the actual screens. Reopen it from Overview, the sidebar or **More**. Reading it or changing steps does not fill in fields or validate the pentest. Use it with a demo or your own project.

Overview also makes it easier to continue findings and add one when starting a project. Experienced users can work directly without following the tutorial.

New findings start **Pending assessment**. Classification, CVSS and technical verification are recorded separately. The application does not invent scores to complete a report.

## Install and launch

Primary installation path: Linux/Kali with Python 3.10+. Consult the validation record for the environments and checks of this release. Native Windows and Microsoft Word require separate validation.

```bash
python3 start.py --setup
python3 start.py --diagnose --lang en
python3 start.py
```

Setup creates `.venv` and installs dependencies constrained by `requirements-audited.txt`; it needs network access. Open **http://127.0.0.1:8080**. Use `--port 8081` for another local port. An existing prepared environment is also supported.

On Debian/Kali, missing native dependencies can be installed with:

```bash
sudo apt install python3-venv python3-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

Chromium is an optional alternative PDF engine:

```bash
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
```

## First report

On Overview, select **Open visual guide** in the **Your first report here?** card. You can also use **Guide: first report** in the sidebar or under **More** on mobile. Jump to any step and revisit the help while working.

1. **Start.** Use **Create project** or **New project** to choose the design and report language. To learn with prepared content, **Try Nimbus demo** creates an editable fictional case with 12 findings. You can also open a backup of your work.
2. **Define scope.** Complete the client, assessor, dates and report details. Document objectives, included assets, exclusions and limitations. Record **Assets** and **Coverage** when useful for your assessment.
3. **Write a finding.** Add a blank finding or open an existing one. Describe the failed control, observed behavior, reproduction steps, demonstrated impact and proposed remediation. Record severity, CVSS vector and technical verification when you can substantiate them.
4. **Connect evidence.** Under **Evidence**, upload the screenshot, write its title and caption and select its associations under **Used in findings**. Review and redact the copy that will be published. Quick capture notes stay outside the report until you incorporate them.
5. **Review what you share.** Under **Review**, open errors, warnings and their explanations; then inspect text and images in the **Publication inspector**. Confirm the save to disk: a recoverable browser draft is a separate safeguard, not a saved delivery. These checks detect omissions; they do not confirm vulnerabilities.
6. **Deliver and retain.** Under **Deliver**, review annexes: upload redacted copies and select reviewed files. Choose formats, generate the package and open **Exports and downloads**. Check files and presentation; **View checks** displays the record. Further edits do not modify the queued revision. Also download the **Project backup**: it retains originals and versions, is private and is separate from the client package. Use **Versions** to label deliveries and **Remediation and retest** to record actual follow-up checks; a reported fix still requires verification.

CVSS expresses technical severity, not business risk by itself. **Risk Posture and Business Impact** and **Strategic Recommendations** let you document the context, priorities and risk appetite agreed with the organization. Enable these sections under **Manage sections**. You author the conclusions; selecting a design does not calculate or approve them.

**Library** includes 22 certification profiles, six general layouts, Brand/Sober variants and personal templates. Every profile supports English and Spanish. Applying an appearance preserves findings. Word uses Calibri; PDF and HTML use compatible Carlito. Commands retain their monospaced font.

## Delivery checks and limits

**View checks** shows the saved revision, SHA-256, file sizes and checks for each download. All formats still require visual review.

Annexes are excluded until individually reviewed and selected. Only the combined delivery includes them. They are copied unchanged, without redaction or metadata removal; upload reviewed copies. Backups containing attachments require 0.21.0 or newer. Annex records with `required` need 0.21.1 or newer, including when false. Required annexes block delivery until reviewed, included and intact; acknowledging warnings does not bypass this.

The annex scanner searches the first MiB of UTF-8 text or counts image metadata. It does not perform OCR or inspect PDF contents. Results include scope and limitations, never matched secret values.

Structured export checks compare paragraphs, literal code, metadata, native tables, links and evidence placement within their finding. Only code line endings are normalized. Missing internal destinations block publication. Static HTML visibility checks do not certify geometry, occlusion, conditional CSS or dynamic states. PDF checks text presence, image counts and index destinations; literal whitespace, block association and layout require manual review. Markdown intentionally omits the severity chart and its scope caption; that difference is recorded.

Project integers must be within −9,007,199,254,740,991 to 9,007,199,254,740,991 to preserve their value in the browser editor. Store larger documentary values or identifiers as quoted text in YAML/JSON. Out-of-range inputs are rejected with the field path rather than silently rounded or replaced with `null`. Report numbered lists use counters from 0 to 2,147,483,647, compatible with browser and Word consumers. An initial or final ordinal above that limit is rejected, preserving any previous output file.

Native Microsoft Word validation requires a licensed Windows desktop installation. The opt-in workflow is implemented; local OOXML and LibreOffice checks do not substitute for that native validation.

## Recovery and privacy

Projects live in `webapp/projects/`, personal libraries in `webapp/library/`. **Workspace backup** includes all projects, originals and libraries. Treat it as private data.

Pending drafts are stored in this browser profile's IndexedDB for 30 days on the same origin (host and port). The interface only says recoverable after the write completes. Drafts are not encrypted by the application. They recover project data, not image files or auxiliary forms that have not been added to the project. Private browsing, clearing browser storage or switching profile/port can make drafts inaccessible. **More → Download private draft** creates an emergency copy. Recovery requires the matching project and explicit conflict resolution.

**Stored private data** inventories current files, originals, history and removed annexes. Cleanup requires category selection and the exact project ID. Current data is retained; cleaning history creates one new recovery snapshot. Browser drafts have separate download/delete controls. External backups and downloads cannot be deleted here.

Text redaction applies to the publication copy; image redaction creates a pixel derivative and retains the private original. Image metadata is removed from exports. Pattern detection cannot identify every secret: review manually.

Portable HTML contains the entire report. Executive view and filters are presentation options, not access control. Shareable comparisons omit historical images. Internal comparisons may contain private captures and are not client deliverables.

## Upgrade from an earlier version

Extract 0.24.0 into a new directory. Create a workspace backup in the previous version and restore it into the empty new installation. Keep the old directory until you have checked your projects. Do not copy another installation's `.venv` or overwrite data with demo files. Existing projects remain readable. Backups containing annexes require 0.21.0 or later.

If an old project has its only preceding revision in `engagement.yaml.bak`, without snapshot history, the 0.21.2 exporter omits that copy. Keep a complete copy of `webapp/projects/` and `webapp/library/` as well. Copy those directories into a new 0.24.0 installation and create the backup there: this release includes the legacy recovery state without modifying its source when exporting. An older ZIP that already omitted the copy cannot reconstruct it.

Existing IDs are retained. Since 0.21.2, the `finding_sequence` counter prevents deleted IDs from being reused; older versions do not preserve this guarantee. References already misdirected by older edits cannot be repaired automatically without knowing their original intent.

## CLI and development

API clients select error language with `X-UI-Language: es` or `en`. An absent or unsupported header keeps the historical Spanish default. URLs opened directly use that default; external library and tool diagnostics remain verbatim. This does not change report language or authored content.

```bash
.venv/bin/python export.py webapp/projects/my-project/engagement.yaml -f html -o report.html
.venv/bin/python -m pip install -e '.[dev]'
npm ci
.venv/bin/python -m pytest
node --test tests/test_save_manager.cjs tests/test_drafts_0200.cjs
export RG_PYTHON="$PWD/.venv/bin/python"
npm run test:workspace
npx playwright install chromium
export REPORT_GEN_CHROMIUM="$(node -p "require('playwright').chromium.executablePath()")"
.venv/bin/python -m pytest tests/test_portable_report_browser.py
node tests/test_editor_browser_0213.cjs --output out/editor-chromium
```

Other export formats: `pdf`, `docx`, `md` (ZIP with images). The editor runs in one process on `127.0.0.1`; it is not a multiuser service. Certification profiles are starting points; check current provider requirements before an exam submission. Logos remain their owners' property and imply no affiliation.

The application package retains source, tests, demo, designs and current documentation. Historical screenshots and generated samples are distributed separately.

## Retained history

<details>
<summary>Improvements from 0.21.3 to 0.21.9</summary>

Release 0.21.9 protects inputs during export: it rejects destinations that match the source YAML or local resources, including file aliases. Replacing an existing report that is not an input remains supported. The validation record documents the contracts and scope of this review.

Release 0.21.8 strengthens list-order checks and Word numbering, PDF index references and report extracts. It aligns library input validation, checks follow-up dates and uses native dialogs for templates. Portable search matches canonically equivalent Unicode text. See the validation record for executed checks and format limitations.

Release 0.21.7 fixes null inputs, encoded anchors, language consistency, summary-only reports, project imports and startup recovery. It verifies table order in HTML, Word and Markdown, improves portable layout and long Word tables, and updates the optional PyMuPDF dependency. See the validation record for executed contracts and their limits.

Release 0.21.6 checks anchor collisions before export and improves the semantics and printing of portable HTML. It retains the responsive tables introduced in 0.21.5. The validation record covers export contracts and a new report generated during this review.

Release 0.21.5 improves portable HTML tables: field/value rows use bounded labels on desktop and a stacked layout on mobile; comparative tables use accessible local horizontal scrolling. Report content, filtering, no-JavaScript reading and revision-based exports are preserved.

Release 0.21.4 validates severity against a supported CVSS vector even when the scalar score is absent. It rejects a null theme in validated input while preserving the editor’s default normalization. Missing scores are neither assigned nor published. Two unused regex definitions were removed and CVSS 4.0 documentation corrected.

Release 0.21.3 fixes narrow-screen portable HTML and reference navigation while filters are active. It also preserves images, literal references and CVSS vectors across exports, protects legacy backups, improves reusable finding templates, and fixes keyboard flows in the editor. The content and integrity checks introduced in 0.21.2 remain in place. See [the validation record](../../VALIDACION-0.21.9.md) for reproduced defects, measured results and compatibility limits.

The export fixes introduced in 0.20.2 remain included. Chromium acceptance now covers real clicks, downloads, failed-save recovery, import, keyboard navigation and mobile layout.

The improvements from 0.20.1 remain: unclassified findings labelled **Pending assessment** without assigning severity or CVSS, PDF index leaders, content-aware table widths and Markdown code styling. Word includes a linked native table of contents with its own page-reference fields.

The synthetic example `examples/pending-severity/engagement.yaml` exercises these fixes. The Word index titles work immediately; page numbers are computed when fields are updated in the editor. Use **Ctrl+A**, then **F9**, if numbers are missing or content changes. Word pagination is never copied from the PDF. Desktop Microsoft Word remains a separate validation target from LibreOffice.

Executed contracts and limitations from these reviews are documented in [VALIDACION-0.21.9.md](../../VALIDACION-0.21.9.md).

</details>

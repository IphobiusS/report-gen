<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen with Prometeo and Evaristo" width="300">
</p>

# report-gen 0.45.0

**A local editor for turning security assessments into clear reports.** Organize findings, connect evidence, track remediation and retests, and prepare **PDF, Word, Markdown with images and portable HTML** from a saved revision.

[Español](README.md) · [Português (Brasil)](README.pt.md) · [Full guide](docs/guide.en.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

## Audit and stability in 0.45.0

Fixes cover Unicode imports, CVSS validation, HAR selection, HTTP comparison, historical retests, shared-comparison privacy, export cancellation and cleanup, cover metadata and the terminal wizard. Reproduced defects have regression checks; only demonstrated redundant or unreachable code is removed.

[Audit scope and acceptance protocol](docs/QA-AUDIT-0450.md). Publication requires seven passing gates for the same commit. Their receipts document observed results, without claiming universal freedom from bugs.

## Install and launch

Primary path: **Linux/Kali and Python 3.11+**. Download and extract the [latest published release](https://github.com/IphobiusS/report-gen/releases/latest), or clone the repository:

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 scripts/install.py --desktop --lang en
~/.local/bin/report-gen
```

The installer prepares `.venv`, downloads dependencies constrained by `requirements-audited.txt` and adds an application-menu shortcut. It does not use `sudo` or install system packages. **Keep the application directory and its `.venv`: the shortcut depends on them; this is not a standalone executable.** Opening the shortcut later does not reinstall dependencies.

Data stays outside the application at `$XDG_DATA_HOME/report-gen`, or `~/.local/share/report-gen` by default. Choose another directory with `--workspace /path/to/data`; when omitted, `REPORT_GEN_WORKSPACE` is respected. The installer does not migrate old projects automatically.

Open **http://127.0.0.1:8080**; `Ctrl+C` stops the server. The shortcut accepts `--port 8081`. The existing `python3 start.py --ready --lang en` path remains available and retains `webapp/` when no external workspace is selected. **Node.js is not required to use the editor.** See [PDF requirements, migration and other options](docs/guide.en.md#install-and-launch).

## First report

1. On **Overview**, choose **Try Nimbus demo** to create an editable copy of a fictional case with 12 findings. Use **Create my project** for your own assessment.
2. In the project, **Suggested next action** follows what you have written so far. **View this step in the guide** opens the relevant help. Guidance does not fill in or validate assessment data for you.
3. Save, review the **Publication inspector**, and generate the formats you need from **Deliver**. Open the files before sharing them and keep a private project backup.

**Visual tutorial** is available from the menu, with enlargable ES/EN/PT screenshots and local progress. The first-entry invitation can be skipped.

[Complete walkthrough and recommendations](docs/guide.en.md#first-report).

## What you can do

- **Document an assessment:** scope, methodology, assets, coverage, findings and reproducible steps; CVSS 3.1 and 4.0 where appropriate.
- **Work with evidence:** a gallery, captions, finding links, redacted copies and an inspector for published content.
- **Retain follow-up:** stable identities, recoverable revisions, comparisons with a marked delivery, remediation and a retest matrix.
- **Choose presentation:** start a project from a gallery with six general designs and 30 specialized profiles, grouped by purpose. Report language is independent of interface language.
- **Separate audiences:** technical, executive and public deliveries with explicit inclusion plans; public output requires approved prose and recorded consent.
- **Connect evidence and decisions:** claims, limitations, business context, comments and actual PDF review. [Workflow and optional requirements](docs/evidence-decisions-0230.en.md).

| Format | What you receive |
| --- | --- |
| PDF | A paginated `.pdf` report. |
| Word | An editable `.docx` with its own table-of-contents fields. |
| Markdown | A ZIP containing `report.md` and its images. |
| Portable HTML | A self-contained `.html` with reading filters. |

## Library and engagement preparation in 0.44.0

**Finding library → Curated catalog** provides 90 original entries in Spanish, English and Portuguese: 18 web, 12 API, 8 identity/AD, 8 infrastructure, 8 cloud, 6 mobile and 30 AI/LLM/agent patterns. Search text or filter by category and language. Each entry explains prerequisites, required evidence, false positives, remediation and retest, with sources and a review date. **My library** retains your templates and versions.

AI entries cover direct/indirect/multimodal injection, RAG, memory, tools, agent identities, supply chains, privacy and resource bounds. Sources reviewed on 2026-10-17: OWASP LLM Top 10 2026, Agentic Applications 2026, MITRE ATLAS and NIST AI 100-2e2025. The OWASP 2025 category selector remains labeled with its edition; historical IDs are not reinterpreted.

**Work packages** creates independent projects with structure and pending tests for seven specialties. You can explicitly include suggested entries; they start unverified and without assigned severity/CVSS. **Annotated report** explains nine writing decisions in the fictional Nimbus case. Field guidance contrasts adequate and insufficient examples without automatically filling in results.

[Library and package guide](docs/knowledge.en.md) · [Acceptance protocol](docs/QA-KNOWLEDGE-0440.md). The review date identifies a content edition, not a live update or a guarantee of exhaustive coverage.

## Guided start in 0.43.0

On first entry, choose **Guided** or **Complete**, and change later with the view selector. Both retain the same routes, tools and data. Guided reduces initial density by collapsing advanced tools and offering a next action; expand those tools whenever needed.

The optional **Project → Scope → Findings → Evidence → Review → Delivery** route explains and highlights editor controls. Skip, go back, pause, resume or restart at any time. **Explain this section** provides contextual help. This browser remembers the view per workspace and learning progress per project; if storage is unavailable, they work for the session.

Practice opens a separate fictional Nimbus copy, clearly labelled, and lets you return to your project. Completing guidance never verifies findings, approves evidence, executes tests or certifies delivery. The screenshot-based **Visual tutorial** remains available. [Using guided start](docs/guide.en.md#guided-start-and-contextual-help).

## Assessment workflow 0.42.0

Review connects the filtered queue, evidence pinned beside the editor, table selections and search across assets, evidence and comments. **Save and next** retains the active review session.

Findings support **affected instances** with independent ownership, deadlines, evidence and retests. Overall status derives from the set: a partial fix never closes outstanding targets. **Test plans** record methodology and version, roles, tenants and outcomes; **attack paths** distinguish demonstrated, inferred and blocked transitions.

**HTTP evidence** separates private originals from reviewed technical delivery copies. It includes HAR import, comparison and an optional Burp extension that sends only selected messages. Scanner reimports compare and attach new observations while preserving analyst decisions.

Versioned client profiles and editorial review packages retain requirements and field-level changes. Jira Cloud and DefectDojo support explicit exchanges with existing records on public HTTPS servers; external status does not replace retesting. Ollama editorial review uses selected sources and retains the author's judgment.

[Practical 0.42 workflow and limits](docs/senior-workflow.en.md) · [Fictional Aster ES/EN/PT case](qa/aster/README.md) · [Burp extension](integrations/burp-report-gen/README.md). Native Word and Burp acceptance, live Jira/DefectDojo accounts and Ollama inference need their own records; this capability list does not establish those executions.

## 0.41.0 integration

**Deliver** combines review, audience, preview and export. Blockers link to their source; content or option changes invalidate the preview. Export retains the reviewed revision and requires renewed acknowledgement when appropriate.

Long tables inside findings can continue by rows across pages with repeated headers. Short tables stay together. A cell or heading that exceeds the printable height still produces a diagnostic; content is never clipped to force an output.

Recoverable drafts now cover bulk editing and auxiliary library, import, annotation and creation forms. Recovery opens a form for review; it never applies changes or restores approvals. Workspace forms are distinguished from report forms. Browser quotas and 30-day retention still apply.

Visual review offers **Save progress in project**: current page, notes and pending issues bound to the PDF SHA-256 and original revision. Saving a private PDF copy is optional. Without it, reopen the exact original file. These records are excluded from published reports but included in backups and history. Deleting the current record does not erase earlier versions.

Start the wizard with `python scripts/install.py --gui --lang en`. It requires Python 3.11 or newer, Tkinter and a graphical session. The wizard guides diagnosis, folders, installation and recovery. Updates use a new directory; application and workspace locks prevent updating a running editor. Python and system requirements still apply: the wizard is not a standalone bundle containing every dependency.

Native Microsoft Word acceptance remains separate. The corpus covers Spanish, English and Portuguese; `--additional-projects PATH` includes three complex projects under `es/`, `en/` and `pt/`. It requires Windows with installed, licensed desktop Word. Preparing the kit, validating DOCX or rendering with LibreOffice does not execute Word.

## New in 0.40.0

The left sidebar keeps five tool groups. Section and finding lists open in an **Index** beside the editor, with search, finding filters and pages of 50 entries. Close the panel or adjust its width without changing the report. If a filter hides the open item, **Show selection** helps locate it again.

**Order sections** explicitly enables controls for moving them. The normal list retains the project order. On mobile, selecting an entry closes the index; **Escape** returns focus to its button. Index preferences are retained in this browser separately for each workspace and project. [Using the index and navigation](docs/guide.en.md#sidebar-navigation-in-0400).

## New in 0.39.0

*0.39.0 history: the five-group organization remains; its expandable lists inside the sidebar were replaced by the contextual index in 0.40.0.*

The left sidebar organizes work into five groups: **Project**, **Content**, **Evidence and scope**, **Analysis and follow-up** and **Delivery**. Rows use consistent sizing and spacing. Expandable section and finding indices show their counts and retain pagination for large projects.

Navigating to an item opens its group and reveals the selection. This sidebar visibility adjustment preserves focus and does not scroll the editor. You can collapse the current group; background refreshes respect that choice. **Delivery → Tools** collects libraries, workspace backup, privacy, diagnostics and application updates. On mobile, **Navigation** opens the sidebar and **Escape** closes it, restoring focus to its trigger.

The new fictional **Atlas Servicios Financieros** case prepares extensive testing with authored Spanish, English and Brazilian Portuguese content. Its [acceptance protocol](docs/QA-ATLAS-0390.md) separates complete reports, style excerpts, API journeys and visual checks. Results are established per run; unfinished outputs are not treated as accepted. [Sidebar walkthrough](docs/guide.en.md#sidebar-navigation-in-0390).

## New in 0.38.0

**Error locations:** imports show the available record, field and line; failed exports identify a finding, table, row, cell or evidence item when the contract can locate it reliably. Otherwise, the original general error remains. These private details are excluded from delivery manifests.

**DOCX preview with LibreOffice:** from a completed export containing Word, explicitly generate a PDF view using LibreOffice installed on your computer. The view is linked to the exact DOCX by SHA-256 and revision without modifying it. It is private and temporary; it shows LibreOffice layout and does not establish Microsoft Word equivalence.

**PDF annex inspection:** examine extractable text, metadata and PDF structures within explicit limits. Results show categories and locations without revealing sensitive values or changing the file. Scope is always partial: no OCR, arbitrary binary inspection or reconstruction of earlier PDF revisions. Manual annex authorization remains necessary.

Cleanup removes private helpers, unused bindings, obsolete constants and 20 CSS rules with no current emitters. Public adapters, library callbacks and resources with documented roles remain. This does not claim universal absence of dead code. [New feature workflow and limits](docs/guide.en.md#review-errors-and-documents-in-0380).

## Fixes in 0.37.1

Linked images inside Markdown tables preserve their destinations and captions in Word, including URL fragments and surrounding text. Link verification remains enabled. The fictional Banco Horizonte Austral case extends content and workflow acceptance; see its coverage matrix in `qa/horizonte/`.

## New in 0.37.0

**Pair PDF pages:** manually match earlier and later pages after insertions or reordering. The editor shows each mapping and unmatched pages; every page must be covered exactly once.

**Record the review:** optionally save the self-declared author, decision, note, page mapping and hashes as a private JSON record in the project. It is saved only on request and excluded from delivery by default. It remains in project history and backups without automatic deletion. PDFs, HTML and images are not copied into the record; download the HTML separately to retain the comparison images.

**SARIF extensions:** self-contained `tool.extensions` rules are supported with consistent index or GUID references. Component provenance is preserved and observations remain informational and unverified.

## Features introduced in 0.36.0

**SARIF 2.1.0:** use **Import results**, inspect provenance and choose which results to include. They remain unverified informational observations; analyzer levels are not converted to CVSS.

**Compare PDFs:** select two files from revision history to view their pages and highlighted differences. Download the comparison as self-contained HTML. Pages are paired by position by default; visual changes alone do not establish semantic changes.

## New in 0.35.0

Brazilian Portuguese joins Spanish and English across the editor, server messages, tutorial, design gallery and all four report formats. An explicit selector controls interface language; report language remains separate, and switching either preserves authored content.

Section labels now refresh immediately when report language changes. Section-based Markdown reports also retain the appendix introduction. Checks cover translation catalogs and placeholders, Portuguese exports and tutorial journeys in all three languages.

### Retained corrections from 0.34.5

Word contents reserve room for the page number when a title fills almost the entire line. Long captions can continue across pages without making their figure disappear; HTML, PDF and Markdown preserve their line breaks. Markdown also supports empty captions without displaying asterisks. Retest tables nested in quotations or lists use the available page space, and undated retests no longer display an empty separator.

Review identifies the field containing a Markdown character entity incompatible with Word before export. Literal code remains unchanged. Automatic text continues to describe recorded information without claiming unrecorded verification.

Export tracking pauses its requests when the page is left and resumes them when it is restored, without cancelling server jobs. Inspector, preview and validation labels follow the interface language after reload; changing that language does not modify the report. Native select controls follow the editor's dark or light theme, correcting insufficient contrast observed in WebKit on Linux.

An [optional LibreOffice extension](docs/guide.en.md#optional-libreoffice-extension) wraps marked ASCII technical literals without inserting characters or changing links. **Installation and wrapping were checked with the official LibreOffice 26.2.6.3 distribution for Linux x86-64 and its Python UNO runtime.** DOCX exports add the technical-language marker by default; the extension is built from source and explicitly installed. The document remains editable without it, although early line breaks may return. This does not establish Microsoft Word or LibreOffice compatibility on Windows or macOS.

## Export and visual tutorial

Left, center and right alignment in Markdown tables is preserved on export. PDF verification checks each finding's content within its region, so a copy in the contents or summary cannot conceal missing text. Long URLs in ordinary text no longer overflow the PDF; verification avoids unnecessary ambiguous searches. On Linux and macOS, a supervisor keeps the job's process group reserved until cleanup, even if the worker exits early. Publication also requires macOS, stable LibreOffice and WebKit checks, plus a project and trilingual tutorial journey in native desktop Safari. This automated journey has a defined scope; it does not substitute for native Microsoft Word or human screen-reader review.

**Visual tutorial** offers an optional invitation on first entry and remains available in the menu. Its six steps include real Spanish, English and Portuguese screenshots: template, report details, findings, evidence, review, and delivery with a backup. Enlarge screenshots, resume your place or restart without changing your projects. It works locally, including when the browser cannot save progress.

PDF export reduces layout work for long literal URLs. It preserves selectable text and complete destinations with a default 300-second budget, configurable from 30 to 600, and without removing report checks. Regressions cover tables with 72 URLs longer than 300 characters, both languages and the six general designs. A paragraph is no longer falsely rejected when a complete URL continues across pages.

The optional Microsoft Word acceptance kit admits numbering fields generated by report-gen and distinguishes external URL fragments from document bookmarks. A dedicated case covers long URLs and exceptional numbering for native review.

**Limits:** without the extension, some Word URLs may wrap before filling the line in LibreOffice; their text is not altered to conceal this. The checked integration is limited to the environment and literals described in the guide. Native Microsoft Word review remains pending. PDF verification does not establish ordinals or layout; both require visual review. [Full changelog](CHANGELOG.md) · [Delivery guide](docs/guide.en.md#delivery-checks-and-limits).

## What delivery checks establish

**View checks** shows the revision, SHA-256, size and controls for each file. Export checks compare content and references with different scope for each format. **They do not certify the assessment's correctness or visual presentation:** review PDF, Word, Markdown and HTML before delivery.

[Export checks, annexes and limitations](docs/guide.en.md#delivery-checks-and-limits). Optional [Ed25519 signing](docs/delivery-signing.md#optional-signing-of-a-delivery) establishes integrity relative to a pinned public key; it does not encrypt the delivery or certify its conclusions.

## Recovery and privacy

The editor runs on **`127.0.0.1` in one process**, without accounts or external services for normal editing. After dependency installation, everyday work stays local. Ollama assistance is **optional and explicitly requested**; read which fields it sends and its limitations before enabling it.

The external workspace contains `projects/` and `library/`. Traditional startup without `--workspace` or `REPORT_GEN_WORKSPACE` retains `webapp/projects/` and `webapp/library/`. **Workspace backup** retains projects, originals and history; it is private material. Projects on disk and browser drafts are not encrypted by the application. Install the optional `privacy` extra to download a password-encrypted private backup; it encrypts that file only. [Recovery, backups and privacy](docs/guide.en.md#recovery-and-privacy).

Browser drafts are separated by workspace, profile, host and port. Updating the application while retaining the same external workspace preserves that scope; moving it or restoring into another workspace creates a different scope. Download pending drafts before transferring it: workspace backups do not carry them. Earlier copies without an identity remain under **More → Unassigned legacy copies** for explicit review and download.

Portable HTML contains the complete report: filters are not access permissions. Possible-secret detectors do not replace human review. Windows compatibility tests do not replace review in desktop Microsoft Word; Word and LibreOffice can paginate differently. Certification profiles imply no affiliation or guarantee of compliance with exam rules.

## Upgrade from an earlier version

**Update report-gen** checks for a new version and lets you review its package and prepare an unencrypted private backup. Preparation does not replace the running installation: download the private instructions, stop the editor and follow the supplied commands. [Guided workflow and limits](docs/guide.en.md#guided-updates).

If you already use an external workspace, stop the editor, download **0.44.0 into a new directory** and run `python3 scripts/install.py --desktop --workspace /path/to/existing-data --lang en` there. This retains the data and updates the shortcut; run only one installation at a time. Do not copy the old `.venv`.

To transfer projects from an installation still using `webapp/`, run from the new directory:

```bash
python3 start.py --ready --workspace /path/to/new-data --upgrade-from /path/to/previous-report-gen --lang en
```

The destination must be empty. Migration preserves the source and creates a private backup. To separate data from the current application directory itself, use `--upgrade-from .` with an empty external destination. Check projects, images and history before retiring any installation. **Workspace backup** is another transfer option. [Details and compatibility](docs/guide.en.md#upgrade-from-an-earlier-version).

## Export from the terminal

Try an included fictional example from the project root:

```bash
.venv/bin/python export.py examples/pending-severity/engagement.yaml -f html -o out/example.html
```

The values of `-f` are `pdf`, `docx`, `md` and `html`; `md` produces a ZIP. This fixture contains Spanish report text. [CLI and development details](docs/guide.en.md#cli-and-development).

<a id="cli-and-development"></a>

## Development and limitations

Development and interface tests require **Node.js 22+**. From an installed environment:

```bash
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci
.venv/bin/python -m pytest
npm test
```

[Browser checks and optional scenarios](docs/guide.en.md#cli-and-development) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [MIT license](LICENSE).

## Documentation

- [Usage guide: installation, publication, backups, CLI and development](docs/guide.en.md).
- [Evidence and decisions; optional previews and Ollama](docs/evidence-decisions-0230.en.md).
- [CVSS 4.0](docs/CVSS40.md) and [delivery signing](docs/delivery-signing.md#optional-signing-of-a-delivery).
- [Design and template library (Spanish)](docs/design-library.md).
- [Changelog](CHANGELOG.md).

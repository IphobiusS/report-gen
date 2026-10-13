# report-gen 0.34.5 user guide

[Welcome](../README.en.md) · [Español](guide.es.md) · [Changelog](../CHANGELOG.md)

Unless stated otherwise, run commands from the project root containing `start.py`. Initial setup and optional downloads need a connection; ordinary editing and exports run locally.

## Install and launch

Primary installation path: Linux/Kali with Python 3.11+. Windows compatibility tests do not replace document review in desktop Microsoft Word.

Download and extract the ZIP from the [latest Release](https://github.com/IphobiusS/report-gen/releases/latest). From that directory:

```bash
python3 scripts/install.py --desktop --lang en
~/.local/bin/report-gen
```

The first command installs dependencies into `.venv` using the audited constraints and creates `~/.local/bin/report-gen`. `--desktop` also adds an application-menu shortcut that opens a terminal. Installation needs connectivity, Python 3.11+ and venv support; it does not use `sudo` or install system packages. This is not a standalone executable: retain the extracted application directory and `.venv`. The shortcut points to that location and the chosen workspace; subsequent launches do not reinstall or download dependencies. If you move the application, rerun the installer from its new location.

Workspace selection is `--workspace`, then `REPORT_GEN_WORKSPACE`, then `$XDG_DATA_HOME/report-gen` or `~/.local/share/report-gen`. For example, `python3 scripts/install.py --desktop --workspace /path/to/data --lang en` selects a specific external directory. Existing data is not migrated automatically: read the migration instructions before interpreting an empty list as lost projects.

`--lang en` sets the launcher messages and initial interface language to English. An existing browser language preference takes precedence; change it in the editor when needed. Report language remains independent.

The existing `python3 start.py --ready --lang en` route remains available. Without `--workspace` or the environment variable, this launch retains the traditional `webapp/` location. `--ready` allows dependency installation when the local environment is missing or incomplete, runs diagnostics and starts the editor if its requirements are available. Setup creates `.venv`, updates pip and installs dependencies constrained by `requirements-audited.txt`. Open **http://127.0.0.1:8080**; `Ctrl+C` stops the server. Use `python3 start.py --ready --port 8081 --lang en` for another local port.

Diagnostics distinguish the editor from each export engine. Editing can work while an optional engine is unavailable; opening the editor does not establish that every output format is available. If preparation stops, follow the reported correction before trying again.

| Need | Command |
| --- | --- |
| Install with application-menu shortcut, without starting | `python3 scripts/install.py --desktop --lang en` |
| Open the prepared installation | `~/.local/bin/report-gen` |
| Prepare, check and start | `python3 start.py --ready --lang en` |
| Reinstall dependencies and stop | `python3 start.py --setup --lang en` |
| Diagnose without installing or starting | `python3 start.py --diagnose --lang en` |
| Start an already prepared environment without installing | `python3 start.py --lang en` |

**Node.js is not required for ordinary use.**

On Debian/Kali, missing native dependencies can be installed with:

```bash
sudo apt install python3-venv python3-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

Chromium is an optional alternative PDF engine:

```bash
.venv/bin/python -m pip install playwright -c requirements-audited.txt
.venv/bin/python -m playwright install chromium
```

Read each engine status in the diagnostic output; its exit code alone does not establish that every engine is available.

## First report

On Overview, choose **Try Nimbus demo** or **Create my project**. With a project open, **Suggested next action** proposes a step based on its title and client, scope objectives, findings, evidence associations and actual results of the last saved review. **View this step in the guide** opens the corresponding explanation. You can also open **Visual tutorial** under **More**, on desktop and mobile and revisit any of its six steps.

First entry offers an optional invitation: **Start tutorial** or **Not now**. The tutorial uses real screenshots with fictional data in Spanish and English, with controls to enlarge them or view actual size. **Escape** closes the screenshot and restores focus to its trigger. It remembers your step in this browser; **Restart tutorial** resets only tutorial progress, without changing projects. If storage is blocked, the tutorial still works during the session. It does not send screenshots to an external service.

Suggestions support writing without requiring a fabricated finding or screenshot: go directly to review when a recommendation does not apply to your assessment. A review with no issues suggests preparing delivery, but does not approve its content. If you edit the draft after review, repeat the saved review before delivery.

1. **Start.** Use **Create my project** or **New project** to open the gallery. Choose a template, compare its samples and continue to enter the title, client, folder and report language. You can return to the gallery without losing those details. To learn with prepared content, **Try Nimbus demo** creates an editable fictional case with 12 findings. You can also open a backup of your work.
2. **Define scope.** Complete the client, assessor, dates and report details. Document objectives, included assets, exclusions and limitations. Record **Assets** and **Coverage** when useful for your assessment.
3. **Write a finding.** Add a blank finding or open an existing one. Describe the failed control, observed behavior, reproduction steps, demonstrated impact and proposed remediation. Record severity, CVSS vector and technical verification when you can substantiate them.
4. **Connect evidence.** Under **Evidence**, upload the screenshot, write its title and caption and select its associations under **Used in findings**. Review and redact the copy that will be published. Quick capture notes stay outside the report until you incorporate them.
5. **Review what you share.** Under **Review**, open errors, warnings and their explanations; then inspect text and images in the **Publication inspector**. Confirm the save to disk: a recoverable browser draft is a separate safeguard, not a saved delivery. These checks detect omissions; they do not confirm vulnerabilities.
6. **Deliver and retain.** Under **Deliver**, review annexes: upload redacted copies and select reviewed files. Choose formats, generate the package and open **Exports and downloads**. Check files and presentation; **View checks** displays the record. Further edits do not modify the queued revision. Also download the **Project backup**: it retains originals and versions, is private and is separate from the client package. Use **Versions** to label deliveries and **Remediation and retest** to record actual follow-up checks; a reported fix still requires verification.

CVSS expresses technical severity, not business risk by itself. **Risk Posture and Business Impact** and **Strategic Recommendations** let you document the context, priorities and risk appetite agreed with the organization. Enable these sections under **Manage sections**. You author the conclusions; selecting a design does not calculate or approve them.

**Library** recommends Serious as a general starting point. Compare the same sample page: cover, summary or technical page. The gallery contains six general designs, 26 certification and practice profiles, four business report structures and personal templates. Filter by purpose or provider, search by name and compare Brand/Quiet variants. **Enterprise Control Review** adds an editorial composition and eight sections covering control design and operation, sampling, exceptions and retesting. If your project already uses a specialized design, the library opens in that context; browsing does not change its appearance. Appearance and initial structure are separate choices; changing a preset does not replace the selected design.

Every profile supports English and Spanish. Applying an appearance preserves findings. Word uses Calibri; PDF and HTML use compatible Carlito. Commands retain their monospaced font.

The default WeasyPrint PDF export detects characters lacking a glyph in available fonts and stops before replacing the previous output. The error identifies codes such as `U+1F3E6`: install a font containing those characters or revise the text and export again. Extractable text alone does not prove that the symbol renders correctly. This check does not certify fonts or visual composition in the optional Chromium engine.

On pages with custom font maps or right-to-left text, the reader recovers a line-ending ASCII hyphen only when the PDF’s explicit codes and maps and a second reader agree character by character. A soft hyphen, unsupported map or divergent reading can still be ambiguous. If this specific error appears, delivery stops without replacing the previous file: adjust that line break or use another format and review the result. The verifier does not invent a missing character.

The sidebar groups capture/coverage and history/follow-up tools in expandable sections. Direct navigation to one of their pages expands the group to show your location. **More project tools** on Overview contains less frequent controls; existing functions and data remain available.

## Organize multiple projects

Under **Overview → Your projects**, search titles, clients or identifiers; accented text can be searched without accents. Filter active, archived, all or pending-retest projects. Sort by last modification, client, nearest due date or pending retest count. Eight projects appear per page.

**Planned delivery → Save date** records a date independently from the report date. **Next due date** is the earliest delivery or finding deadline, excluding findings already verified fixed or with accepted risk; overdue dates remain included. **Pending retests** counts findings with **Reported fixed** status, not every update received through CSV.

**Archive** retains content, allows opening and editing, and can be reversed with **Reactivate**. It neither deletes files nor makes the project read-only. Automatic startup selects an active project; archived projects remain reachable through their filter and the project selector. Dates and archive state travel with backups and history, and are excluded from report publication.

## Bulk edit findings

Open **Findings → Bulk edit** and explicitly select findings. Search and pages of 50 entries retain selections from other pages; the counter includes every selected finding. An operation can contain up to 500 findings.

1. Enable the fields to change: **Owner**, **Remediation date** or **Root cause group**. An empty value clears that assignment; fields not enabled remain unchanged.
2. Choose **Compare changes**. Pending report changes are saved first, then each previous and proposed value is displayed, including selected findings hidden by the search.
3. Review the comparison, acknowledge it and choose **Save reviewed changes**. The assignment is saved in one operation with a recoverable revision under **Versions**. If the project changes during review, compare again.

Status, technical verification, evidence and retests are unchanged. A save error retains the selection and proposal in the dialog for retry; this form is not guaranteed to survive reloading or closing the browser. Closing an unsaved proposal requires confirming its discard.

**Move** supports keyboard reordering even in small projects; dragging is not required. Filters, saved views, reading position and recent activity are separated by workspace and project. Older preferences without a workspace identity are not adopted because project names match. A filter whose value was removed remains labelled **Unavailable**, alongside the active-filter count; **Clear filters** shows all findings again.

## Share diagnostics

Open **Check installation**. The checks generate temporary synthetic PDF and DOCX files and probe workspace write access; they do not export real projects. An unavailable engine is reported separately as failed.

Under **Shareable diagnostics**, review the JSON, check **I have reviewed the diagnostic fields**, then select **Download reviewed diagnostics**. It contains only report-gen version, generic operating system, Python version and synthetic-export/write statuses. It excludes project, client and user names, paths, hostname, environment variables and exception details. Nothing is sent automatically. Changing preview content invalidates its download; run diagnostics again to refresh results.

The DOCX check creates and rereads a document. It does not establish pagination or opening in native Microsoft Word.

## Delivery checks and limits

**View checks** shows the saved revision, SHA-256, file sizes and checks for each download. All formats still require visual review.

Annexes are excluded until individually reviewed and selected. Only the combined delivery includes them. They are copied unchanged, without redaction or metadata removal; upload reviewed copies. Backups containing attachments require 0.21.0 or newer. Annex records with `required` need 0.21.1 or newer, including when false. Required annexes block delivery until reviewed, included and intact; acknowledging warnings does not bypass this.

The annex scanner searches the first MiB of UTF-8 text or counts image metadata. That annex scan does not perform OCR or inspect PDF contents. The Publication inspector offers a separate optional local OCR action for published images. Results include scope and limitations, never matched secret values.

Structured export checks compare paragraphs, literal code, metadata, native tables, links and evidence placement within their finding. Only code line endings are normalized. Missing internal destinations block publication. Static HTML visibility checks do not certify geometry, occlusion, conditional CSS or dynamic states. PDF checks text presence, including table cells and list items, image counts and index destinations. Text presence is global and does not prove the location or association of a cell or item. Wrapped parts of a logical code line stay on one page; a line taller than the printable page is rejected while preserving the previous output. In PDF, literal whitespace, block association and layout require manual review. Markdown includes the severity chart as a PNG, alternative text with its counts and its scope caption. Checks compare the generated image bytes, text and position relative to the summary, separately from evidence images.

Tables inside a finding, including its detailed procedure, must fit on one page with their heading. Otherwise split or shorten the table, or place the extensive register in a narrative section or report appendix, where it can continue across pages. PDF export allows 300 seconds by default. Set `REPORT_GEN_PDF_TIMEOUT` before starting report-gen to an integer between 30 and 600 seconds; an invalid value is rejected before the renderer starts. Reaching the deadline preserves the previous output and removes intermediate files. The queue retains cancellation and its outer 1,800-second deadline. The budget is not automatically increased after a failure: split the content, explicitly adjust the configuration, or retry with less load.

Version 0.34.0 corrected the excessive layout cost of long literal URLs. The test with 72 rows and a URL of about 300 characters per row in a narrative section passed within the limit after that correction. This does not establish a universal row maximum or a guaranteed duration: content and available resources affect it. Preserve literal URLs that are part of the evidence; descriptive labels are an optional writing choice, not a requirement for exporting that case.

Project integers must be within −9,007,199,254,740,991 to 9,007,199,254,740,991 to preserve their value in the browser editor. Store larger documentary values or identifiers as quoted text in YAML/JSON. Out-of-range inputs are rejected with the field path rather than silently rounded or replaced with `null`. Report numbered lists use counters from 0 to 2,147,483,647, compatible with browser and Word consumers. An initial or final ordinal above that limit is rejected, preserving any previous output file.

Within a Markdown list, indent continuation text and code fences by four spaces per level, regardless of the number of digits in the list marker. Eight spaces at the first level represent indented code, not an equivalent continuation. Fenced blocks preserve tabs, spaces and blank lines; indented code follows Markdown normalization.

A Word list starting above 65,535 uses `SEQ` fields to avoid the truncation observed in LibreOfficeDev 26.8. Other lists retain automatic numbering, including when crossing that value. To extend a field-based list, edit it in report-gen and export again. Within Word, copy an item after the first while retaining its field, then update with **Ctrl+A → F9**; the first field sets the starting value. If there is only one item, use report-gen to edit it. Pressing Enter alone does not add a field. HTML, Markdown and Word checks compare ordinals, decimal format and order against the source; Word also checks each field's instruction and cached result. These checks do not replace reviewing the display in your editor. PDF numbering remains subject to visual review.

PDF verification reserves independent physical occurrences for each code line and, within each category, for distinct headings, cells, list items and paragraphs. A longer cell cannot also supply a missing cell whose text it contains. Categories are checked separately because a paragraph inside a list legitimately belongs to both. If ambiguous wrapping exceeds its verification budget, it reports that verification could not be completed and preserves the previous delivery; it does not claim content loss without establishing it.

For reports with canonical sections, PDF verification also requires each
finding's text inside its region, between the delimiting PDF destinations.
It checks the title, headings, paragraphs, code, cells, lists and metadata.
Copies in the contents or summary cannot replace text missing from that region.
This does not verify visual order or the association of individual images;
noncanonical documents retain the global scope.

PDF and portable HTML wrap literal URLs to the available width without changing their text. LibreOffice may wrap some DOCX URLs early; no artificial characters or line breaks are inserted to conceal that limitation. Native Microsoft Word validation requires a licensed Windows desktop installation. The opt-in workflow is implemented; local OOXML and LibreOffice checks do not substitute for that native validation.

In PDF, ASCII identifiers of at least 32 characters, or at least 24 containing digits, underscore, slash or colon, can continue from the remaining line space. This applies to those strings and URLs; it preserves their characters and normal Unicode prose rules. It does not promise identical wrapping for arbitrary words or widths.

PDF and Word body chapters continue without forcing a fresh page for every chapter. The cover and contents stay separate. A figure that cannot fit intact moves to the next page with its size and order preserved; evidence is not cropped to remove that space.

In portable HTML, tables with one header row and uniform cells become records at narrow widths, with each header beside its value. Tables with merged cells or complex headers keep local horizontal scrolling to preserve their relationships. Long ordinals move above their text when width is limited.

**URL compatibility in Word**, under review, identifies locations containing visible URLs of 96 or more characters in the outgoing content. This signals that the DOCX needs inspection; it does not measure line breaks, fail preparation or change the readiness score. Markdown fields offer **Link** for entering a descriptive name and an HTTP/HTTPS URL whose destination remains literal. This is an optional writing alternative: preserve literal URLs that are evidence or commands. The notice does not modify the report automatically or display the detected value.

Shared delivery manifests and downloadable verification records retain warning categories and counts, without copying private diagnostic messages, paths or source values. The complete details remain in the editor for review. This separation does not redact fields you choose to include in a report or annex.

## Optional LibreOffice extension

**Candidate status:** acceptance with the extension installed in stable LibreOffice is pending. DOCX exporter marking remains disabled. These instructions prepare an optional trial; they do not yet replace reviewing the document's line breaks.

The extension acts only on long ASCII technical literals carrying the nonlinguistic `zxx-ZZ-x-rgwrap` marker: URLs of at least 32 characters and identifiers of at least 24 containing a digit, underscore, slash or colon. It does not change prose, insert invisible characters, hyphens or manual line breaks, or modify link destinations. Installing it does not change wrapping in an unmarked DOCX. The document remains editable; without the extension, LibreOffice may retain early line breaks.

It needs LibreOffice with its Python UNO component provider. Python in report-gen's virtual environment does not substitute for that component. For LibreOffice installed from Ubuntu packages, install the dependencies with:

```bash
sudo apt install python3-uno libreoffice-script-provider-python
```

This command changes system packages and requires administrator permissions; it does not install the extension. For other distributions or installation formats, use the provider matching your own LibreOffice installation.

To build the candidate package from the report-gen source tree:

```bash
python integrations/libreoffice/build_oxt.py --output report-gen-libreoffice-0.34.5.oxt
```

1. In LibreOffice, open **Tools → Extensions → Add**. Some versions call the menu **Extension Manager**.
2. Select `report-gen-libreoffice-0.34.5.oxt` and install it for your user.
3. Close every LibreOffice window, reopen it, then open a copy of the marked DOCX.
4. Inspect its URLs, lists and tables after opening, editing and saving it. To remove the extension, disable or remove it in the same manager and restart LibreOffice.

The pending acceptance targets stable LibreOffice on Linux with the extension installed in a temporary profile. Acceptance of the extension in LibreOffice on Windows or macOS and native Microsoft Word review have not been established. The extension does not guarantee identical pagination across editors and does not affect report-gen's PDF, HTML or Markdown exports.

Installation references: [LibreOffice Extension Manager](https://help.libreoffice.org/latest/en-US/text/shared/01/packagemanager.html) and [Ubuntu Python provider](https://packages.ubuntu.com/noble/all/libreoffice-script-provider-python).

## Recovery and privacy

The export queue terminates each job's processes before cleaning up its files. Windows uses a private process job. On Linux and macOS, a supervisor retains the job's process group until cleanup without relying on `waitid`/`WNOWAIT`; it communicates the worker result separately and stops the group if the parent disappears. Cleanup covers descendants that remain in that group; it is not isolation against programs that deliberately start another session. The macOS gate runs Python 3.11 and 3.12.

The external workspace contains `projects/` and `library/`; originals, history and annexes stay inside each project. The launcher resolves `--workspace` before `REPORT_GEN_WORKSPACE`. Without either selection it retains `webapp/projects/` and `webapp/library/`; it does not search for or move data automatically. **Workspace backup** includes all projects, originals and libraries. Treat it as private data.

Pending drafts are stored in IndexedDB for 30 days, separated by workspace identity, browser profile and origin (host and port). The interface only says recoverable after the write completes. Drafts are not encrypted by the application. They recover project data. A separate journal protects pending captures and Evidence and decisions forms, with explicit form recovery: it does not attach evidence or approve publication automatically. Limits are 16 MiB per image, 1 MiB per form, 64 MiB in total and 30 days. Storage failures are shown as tab-only work. Publication consent must be given again after recovery. This protects Quick capture and Evidence and decisions forms, not every auxiliary dialog. Pending copies are excluded from workspace backups and emergency project JSON: incorporate and save them before moving installation or browser origin. Private browsing, clearing browser storage or switching profile/port can make drafts inaccessible. **More → Download private draft** creates an emergency copy. Recovery requires the matching project and explicit conflict resolution.

The identity stays stable across restarts and application upgrades while the external data location remains unchanged. Moving that directory or restoring a backup into a new workspace creates a different scope: matching project identifiers do not authorize draft adoption. Workspace backups retain saved projects but exclude the local identity and browser journals. Download pending work before moving. If a tab detects that the server changed workspace, it blocks requests and lets you download the draft before reloading.

Earlier versions did not identify the workspace of browser copies. **More → Unassigned legacy copies** retains them without automatic adoption or deletion. Choose **I understand the uncertain origin; review copies**, inspect the private content and use **Download private copy**; a pending capture offers its original image separately. For a downloaded draft, open the correct project and choose **Recover draft file**: a missing or different identity requires confirmation before comparing and resolving changes. Legacy copies are deleted only when explicitly selected.

**Stored private data** inventories current files, originals, history and removed annexes. Cleanup requires category selection and the exact project ID. Current data is retained; cleaning history creates one new recovery snapshot. Browser drafts have separate download/delete controls. External backups and downloads cannot be deleted here.

Text redaction applies to the publication copy; image redaction creates a pixel derivative and retains the private original. Image metadata is removed from exports. Pattern detection cannot identify every secret: review manually.

Portable HTML contains the entire report. Executive view and filters are presentation options, not access control. Shareable comparisons omit historical images. Internal comparisons may contain private captures and are not client deliverables.

## Guided updates

Open **Update report-gen**. There are no background network checks or automatic updates.

1. Check **Allow checking and downloading from GitHub**, then choose **Check official version**. Only the official `IphobiusS/report-gen` repository is queried; reports, local paths and credentials are not sent. If no newer stable version exists, the dialog says so without preparing files.
2. Review the version, size, SHA-256 and release. Separately acknowledge preparing the package and an **unencrypted private backup**, then choose **Download, verify and back up**. Pending changes to the open project are saved before preparation.
3. **Download private instructions**. They include the new application and backup locations, capture time and SHA-256, continuation commands and a command to return to the previous installation.
4. Save or download pending drafts in other tabs, close those tabs and stop the editor with `Ctrl+C`. Do not edit projects between the backup and update. Run the supplied lines one at a time; stop if one fails. Installing dependencies in the new directory requires Internet access.
5. Check projects, images, history and exports before retiring the previous installation; keep the backup.

Preparation verifies the tag and commit, the three application release assets (ZIP, JSON and SHA-256), the ZIP's SHA-256 and every file in its manifest. The optional LibreOffice extension is built separately from the downloaded source: the updater does not download or verify a standalone OXT, or install it. Unsupported archive paths and entry types are rejected. This checks integrity against the official HTTPS source; it is not a cryptographic signature independent of that repository. Source packages are limited to 128 MiB compressed, 256 MiB extracted and 4,000 files.

Files are staged under `~/report-gen-updates/update-*/`: `application/`, `workspace-backup.zip` and `receipt.json`. Every preparation captures current saved data and validates a temporary restoration of the backup. An identical capture can reuse verified preparation; changed data creates another while preserving the preceding backup. These files are private, and the backup ZIP is not encrypted. Browser drafts are excluded.

Downloaded code is not executed and the running application is not replaced during preparation. The instructions reuse an external workspace or explicitly migrate legacy data into a new one. Linux uses the local installer; Windows and macOS use the Python launcher. Keep the previous installation and run only one process against a workspace. To return, stop the new editor and use the displayed command. If you already edited with the new version, retain both directories and restore the backup into an empty workspace instead of overwriting work.

## Upgrade from an earlier version

For a manual update when your data already lives outside the application, stop the editor, extract or clone the current release into a new directory and run `python3 scripts/install.py --desktop --workspace /path/to/existing-data --lang en`. This prepares the new `.venv` and updates the shortcut to reuse your data; no import or `--upgrade-from` is needed. Do not run two processes against the same workspace. Once the new installation is checked, you can retire the previous application directory while retaining the external data.

To separate data still held inside an old installation, stop both editors and run from the new directory:

```bash
python3 start.py --ready --workspace /path/to/new-data --upgrade-from /path/to/previous-report-gen --lang en
```

The external destination must be empty and outside both installations. If you updated the code inside the directory holding legacy data, `python3 start.py --ready --workspace /path/to/new-data --upgrade-from . --lang en` transfers it from there. Omitting `--workspace` retains the previous migration between two distinct installations; do not manually merge or delete data directories.

The launcher prepares its own environment, creates a workspace backup of the source, validates a temporary restoration and transfers data to the selected empty destination. It prints the result, ZIP path and SHA-256, then checks the engines and starts the editor. If dependencies are already installed and you want to inspect the result before starting, omit `--ready`: migration stops after diagnostics.

The private backup is kept at `~/report-gen-backups/upgrade-*/workspace.zip`, outside the installations and external destination, alongside `result.json` with its SHA-256 and counts. It includes originals and history. If destination activation fails, the backup already created is retained and the previous installation is not modified. Overlapping paths, symbolic links, pending recovery states and destinations containing projects or personal libraries are rejected to avoid merging or overwriting data. Address the reported cause and use an empty destination; do not delete your data to force migration.

Migration retains projects, evidence, history and libraries covered by workspace backup. It does not copy `.venv`, delivery outputs or browser drafts. Download a pending draft before changing installation or browser origin. Open your projects, verify images and history and retain any delivery files you need before retiring the previous directory.

Alternatively, create **Workspace backup** in the previous version and restore it into the empty new installation. If an old project has its only preceding revision in `engagement.yaml.bak`, without snapshot history, the 0.21.2 exporter omits that copy. Keep the original directory and use the 0.30.0 migration to include this legacy recovery state. An older ZIP that already omitted the copy cannot reconstruct it. Existing projects remain readable. Backups containing annexes require 0.21.0 or later.

Existing IDs are retained. Since 0.21.2, the `finding_sequence` counter prevents deleted IDs from being reused; older versions do not preserve this guarantee. References already misdirected by older edits cannot be repaired automatically without knowing their original intent.

## CLI and development

Development and interface tests require Node.js 22+ and an installed Python environment. Run these commands from the project root.

API clients select error language with `X-UI-Language: es` or `en`. An absent or unsupported header keeps the historical Spanish default. URLs opened directly use that default; external library and tool diagnostics remain verbatim. This does not change report language or authored content.

```bash
.venv/bin/python export.py /path/to/data/projects/my-project/engagement.yaml -f html -o report.html
.venv/bin/python -m pip install -e '.[dev]' -c requirements-audited.txt
npm ci
.venv/bin/python -m pytest
npm test
export RG_PYTHON="$PWD/.venv/bin/python"
npm run test:workspace
npx playwright install chromium
export REPORT_GEN_CHROMIUM="$(node -p "require('playwright').chromium.executablePath()")"
.venv/bin/python -m pytest tests/test_portable_report_browser.py
node tests/test_editor_browser_0213.cjs --output out/editor-chromium
```

Replace `/path/to/data` with the selected workspace; legacy installations use `webapp/projects/`. Other export formats: `pdf`, `docx`, `md` (ZIP with images).

The automatic summary describes recorded findings and severity ratings without claiming that all are confirmed. Machine entries are records, and **Asset inventory** does not establish that assessment was performed. Consult **Coverage and limitations** and each finding's verification state. If no approach has been authored, default text stays within documented information and does not claim manual reproduction. Explicitly authored text is preserved and must be reviewed before delivery.

The included `examples/pending-severity/engagement.yaml` fixture contains two fictional findings with confirmed technical verification and no assigned severity. Its report text is in Spanish. In Word, contents entries are available immediately, with internal links and independent native `PAGEREF` fields. LibreOffice calculates their page numbers during layout; after editing content, use **Ctrl+A**, then **F9**. Numbers follow the editor’s actual pagination, not the PDF. To add, remove, rename or reorder contents entries, edit the report in report-gen and export again: the entry list is not a TOC field that Word automatically rebuilds. Microsoft Word and LibreOffice may paginate differently; native Microsoft Word remains a separate validation target.

The editor runs in one process on `127.0.0.1`; it is not a multiuser service. Certification profiles are starting points; check current provider requirements before an exam submission. Logos remain their owners' property and imply no affiliation.

The repository includes source, tests, demo, designs and usage documentation.

## Scanner imports

The existing import flow accepts CSV, Burp, Nuclei JSONL and Nmap XML. Review and select items before applying them. Nuclei results remain technically unverified; importing is not confirmation. Nmap adds assets, services and pending coverage, never findings merely because ports are open. Imports preserve provenance, prevent duplicates and check the current project revision. No imported commands are executed or targets contacted. Limits are 4 MiB, 500 rows or hosts and 10,000 ports. Nmap omits NSE scripts, OS and traceroute; a scan lacking a recorded successful finish is identified as partial.

## Optional screenshot OCR

Request OCR for a specific published image from the Publication inspector. It requires local Tesseract with `eng` data; no engine downloads or external image service. Static images are limited to 12 MiB and 12 megapixels. Results contain possible sensitive-data categories and regions, never recognized secret values. No alerts is not proof of safety: review the image and explicitly create a redacted publication copy when needed. Originals are unchanged. Missing engine, errors and limits are reported honestly.

## Optional periodic backups

Under **Workspace backup → Optional periodic backups**, enter the absolute path of an existing directory outside the application and workspace. Choose **every hour**, **every day** or **every week**, and retain **1–90 copies**. Review the destination, acknowledge that these are **unencrypted private copies**, then choose **Save schedule**. Scheduling is disabled by default. Use **Disable schedule** to stop it; existing copies remain.

Scheduling runs only while the local server started by the report-gen launcher remains open. Closing a tab does not stop that server; stopping its process does. Restarting the editor checks for an overdue copy, without creating one copy for every missed interval. Checks run at startup and every minute. A failed attempt waits at least five minutes before retrying. No operating-system task is installed and no data is sent over the network.

Each copy includes saved projects, originals, annexes, versions and libraries. Capture shares the editing lock, so it cannot include an operation halfway through. Pending browser drafts and forms are excluded; save or download that work separately. **Create and check copy now** saves the open project first; scheduled runs capture only data already saved on disk. Passwords are never retained. Use a protected directory, on a different disk if you need protection against disk failure.

The application creates a `report-gen-backups-<identifier>` subdirectory. Before recording a new copy and removing older ones, it restores the ZIP into a temporary directory, validates its contents and checks the bytes written. Retention affects only registered, intact files from that series; unrelated files, modified copies and previous destinations are preserved. Changing destination starts another series, even if you later return to the earlier directory. A warning identifies pending retention caused by permissions or a modified copy. If a file changes during removal and cannot be returned to its original name without replacing another, it remains in a private `.retention-*` subdirectory; review it before any manual cleanup. This does not isolate files from a malicious process that already has access to the same operating-system account.

The panel shows the last successful copy, last successful temporary restoration, private path and SHA-256. **Refresh status** fetches the current state; **Check latest copy** restores it again into a temporary directory without changing your current projects. An earlier date does not establish that the latest attempt succeeded: read the warnings. If space is exhausted, a disk was disconnected or permissions changed, address the cause and create or check another copy.

Configuration is private to the workspace and excluded from report exports and workspace backups. Configure scheduling again after moving or restoring projects into another workspace. To recover a copy, select its ZIP using workspace restoration in an empty installation. A temporary restoration proves that the archive is recoverable with this version; it does not replace keeping a copy on another device.

## Password-encrypted private backups

Install the optional dependency inside the project environment:

```bash
.venv/bin/python -m pip install -e '.[privacy]' -c requirements-audited.txt
```

In **Workspace backup**, enter and confirm a 12–256-character password, then choose **Download encrypted backup**. The `.rgbackup` contains the complete private workspace, not a client deliverable. AES-256-GCM authenticates the file; scrypt derives its key with fixed parameters. Keep the password separately: report-gen cannot recover it. This encrypts the downloaded backup, not disk projects or browser drafts. The clearly labelled unencrypted ZIP remains available.

Restore the file with its password into an empty installation. Authentication precedes validation and activation by the existing restorer. Wrong passwords, modified files or occupied destinations do not authorize partial restoration or merging.

## Root causes and remediation tasks

Under **History and follow-up > Root causes**, create a group with a name, cause and shared action. Assign related findings; each retains its permanent identity, severity, evidence, owner and retests. Removing a group unlinks its members after confirmation without deleting findings. Each finding can also have a verifiable **Closure criteria** field.

A finding-specific action takes precedence over the shared action. The report's root-cause section is off by default: enable it explicitly and inspect the result. Partial deliveries retain only groups with included findings; public and executive audiences do not automatically include this private content.

In **Remediation tasks**, select the fields to share. Permanent references preserve correspondence with original findings. Authored fields require review acknowledgement because they may contain client data. Save the project, generate a preview and download CSV or HTML cards in a ZIP. Changing the fields or project invalidates the preview and requires another review. No task is sent to an external service.

CSV cells that might be interpreted as formulas are neutralized. Cards display content as text without executing HTML. Missing fields remain empty; exporting a task or writing closure criteria does not establish that a fix has been completed.

## Receive remediation updates

In **Remediation tasks → Receive owner updates**, open **1. Issue a template**. Select findings with an assigned owner, review the outgoing data and acknowledge retention before choosing **Issue return CSV template**. Issuance saves an assignment in the project and its history; it is not a download without changes. Up to 20 batches or 4 MiB are retained; issuing new batches expires the oldest ones. Backups and restarts preserve current batches.

Provide `remediation-return.csv` and request edits only to `owner`, `due_date` and `reported_remediation`. Preserve references, headers and leading apostrophes on text fields, including `project_slug`; these belong to the reversible format that neutralizes formulas. Owner cannot be empty. Dates use `YYYY-MM-DD`; an empty date proposes clearing the deadline. Save comma-separated UTF-8 CSV, limited to 2 MiB and 500 rows. A subset of rows can be returned, but batches cannot be mixed. The informational task CSV is not a return template.

Upload the file and choose **Compare return**. Current and proposed values are shown, with the issued value when it has changed since issuance. No field is accepted by default. Select each change, acknowledge its review and choose **Save selected changes**. Concurrent changes require a fresh comparison. A temporary save failure retains the loaded file and selected changes in the tab for retry. After a successful save, the report preview no longer marks the preceding revision as current; a visible live preview is requested again.

The communication is stored separately as **Remediation reported through return (unverified)**. Importing never changes status, technical verification, retests, description or evidence: record actual checks in **Remediation and retest**. The template identifies a project and batch but does not authenticate the sender; verify provenance before accepting updates.

## Owner deliveries and local batch log

In **Remediation tasks → Receive owner updates → 1. Issue a template**, select findings with an assigned owner and choose card fields in the controls above. Acknowledge private data and retention. Choose **Preview owner delivery** to inspect both the cards and the fields always included in the CSV: `owner`, `due_date` and `reported_remediation`, including the existing last communication.

**Issue cards and CSV by owner (ZIP)** creates `remediation-delivery.zip` and saves the batch in the project. Each `owner-001/`, `owner-002/`, etc., directory contains an HTML index, task cards and its return CSV. The manifest records fields, owners, source revision and hashes; `INSTRUCTIONS.txt` explains how to separate the delivery. Cards contain only the selected fields; images and annexes are not added. Card text does not execute HTML or Markdown. The complete ZIP includes every selected owner: review and separate the directories appropriate to each recipient before sharing. Nothing is sent automatically, and the ZIP has no access controls.

**Local batch log** distinguishes local issuance, recorded receipt, accepted changes and revocation, with timestamps, source revision and hashes. Comparing a CSV is read-only. After review, choose **Record receipt without applying changes**, or select and save changes; neither action authenticates the sender. **Revoke this batch** prevents further returns for that batch without deleting findings or records.

Retention is limited to 20 batches or 4 MiB overall and 16 events per batch; the log states how many earlier events were omitted. Batches travel with backups and revision history and are excluded from published reports. Restoring an earlier revision also restores its batch and revocation state. This editable local log does not prove that a recipient received the file, authenticate the sender or establish verified remediation.

## Downloadable releases

The [latest Release](https://github.com/IphobiusS/report-gen/releases/latest) provides the source ZIP, its SHA-256 file and a JSON manifest. Automatic publication requires all four workflows on the same commit: **tests**, **Browser acceptance**, **Windows compatibility** and **Reproducible source package**. The publisher rebuilds from Git, verifies all three uploaded assets and only then publishes the Release. Passing automation does not replace document review or human sessions.

## External acceptance materials

`python scripts/prepare-external-acceptance.py --output out/external-acceptance` prepares four synthetic DOCX files and a blank five-participant, three-task CSV. Its manifest records native Word and human sessions as `not_run`. The manual Word workflow requires Windows with desktop Word installed. See CONTRIBUTING.md for the observation protocol and native review command. Material preparation and automated checks are not human observations or native Word acceptance.

The kit includes `word-review.csv` for visual inspection and `INSTRUCTIONS.txt`. After conducting the checks, run `python scripts/prepare-external-acceptance.py --summarize out/external-acceptance` to validate hashes and records without changing them. Native Word automation, visual review and human sessions retain separate states; prepared materials or completed rows do not establish general usability.

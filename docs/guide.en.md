# report-gen 0.26.0 user guide

[Welcome](../README.en.md) · [Español](guide.es.md) · [Changelog](../CHANGELOG.md)

Unless stated otherwise, run commands from the project root containing `start.py`. Initial setup and optional downloads need a connection; ordinary editing and exports run locally.

## Install and launch

Primary installation path: Linux/Kali with Python 3.10+. Windows compatibility tests do not replace document review in desktop Microsoft Word.

```bash
python3 start.py --ready --lang en
```

`--ready` allows dependency installation when the local environment is missing or incomplete, runs diagnostics and starts the editor if its requirements are available. Setup creates `.venv`, updates pip and installs dependencies constrained by `requirements-audited.txt`. Open **http://127.0.0.1:8080**; `Ctrl+C` stops the server. Use `python3 start.py --ready --port 8081 --lang en` for another local port.

Diagnostics distinguish the editor from each export engine. Editing can work while an optional engine is unavailable; opening the editor does not establish that every output format is available. If preparation stops, follow the reported correction before trying again.

| Need | Command |
| --- | --- |
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

On Overview, choose **Try Nimbus demo** or **Create my project**. With a project open, **Suggested next action** proposes a step based on its title and client, scope objectives, findings, evidence associations and actual results of the last saved review. **View this step in the guide** opens the corresponding explanation. You can also open **Guide: first report** in the sidebar or under **More** on mobile and revisit any of its six steps.

Suggestions support writing without requiring a fabricated finding or screenshot: go directly to review when a recommendation does not apply to your assessment. A review with no issues suggests preparing delivery, but does not approve its content. If you edit the draft after review, repeat the saved review before delivery.

1. **Start.** Use **Create project** or **New project** to choose the design and report language. To learn with prepared content, **Try Nimbus demo** creates an editable fictional case with 12 findings. You can also open a backup of your work.
2. **Define scope.** Complete the client, assessor, dates and report details. Document objectives, included assets, exclusions and limitations. Record **Assets** and **Coverage** when useful for your assessment.
3. **Write a finding.** Add a blank finding or open an existing one. Describe the failed control, observed behavior, reproduction steps, demonstrated impact and proposed remediation. Record severity, CVSS vector and technical verification when you can substantiate them.
4. **Connect evidence.** Under **Evidence**, upload the screenshot, write its title and caption and select its associations under **Used in findings**. Review and redact the copy that will be published. Quick capture notes stay outside the report until you incorporate them.
5. **Review what you share.** Under **Review**, open errors, warnings and their explanations; then inspect text and images in the **Publication inspector**. Confirm the save to disk: a recoverable browser draft is a separate safeguard, not a saved delivery. These checks detect omissions; they do not confirm vulnerabilities.
6. **Deliver and retain.** Under **Deliver**, review annexes: upload redacted copies and select reviewed files. Choose formats, generate the package and open **Exports and downloads**. Check files and presentation; **View checks** displays the record. Further edits do not modify the queued revision. Also download the **Project backup**: it retains originals and versions, is private and is separate from the client package. Use **Versions** to label deliveries and **Remediation and retest** to record actual follow-up checks; a reported fix still requires verification.

CVSS expresses technical severity, not business risk by itself. **Risk Posture and Business Impact** and **Strategic Recommendations** let you document the context, priorities and risk appetite agreed with the organization. Enable these sections under **Manage sections**. You author the conclusions; selecting a design does not calculate or approve them.

**Library** recommends Serious as a general starting point. Compare the six general designs using the same sample page: cover, summary or technical page. An expandable specialized catalog retains the 22 certification profiles, Brand/Quiet variants and personal templates. If your project already uses a specialized design, the library opens in that context; browsing does not change its appearance.

Every profile supports English and Spanish. Applying an appearance preserves findings. Word uses Calibri; PDF and HTML use compatible Carlito. Commands retain their monospaced font.

The sidebar groups capture/coverage and history/follow-up tools in expandable sections. Direct navigation to one of their pages expands the group to show your location. **More project tools** on Overview contains less frequent controls; existing functions and data remain available.

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

Extract or clone 0.26.0 into a new directory. Close both editors before transferring data, then run from the new directory:

```bash
python3 start.py --ready --upgrade-from /path/to/previous-report-gen --lang en
```

The launcher prepares its own environment, creates a workspace backup of the source, validates a temporary restoration and transfers data to the empty new installation. It prints the result, ZIP path and SHA-256, then checks the engines and starts the editor. If dependencies are already installed and you want to inspect the result before starting, omit `--ready`: migration stops after diagnostics.

The private backup is kept at `~/report-gen-backups/upgrade-*/workspace.zip`, outside both installations, alongside `result.json` with its SHA-256 and counts. It includes originals and history. If destination activation fails, the backup already created is retained and the previous installation is not modified. Overlapping paths, symbolic links, pending recovery states and destinations containing projects or personal libraries are rejected to avoid merging or overwriting data. Address the reported cause and use an empty destination; do not delete your data to force migration.

Migration retains projects, evidence, history and libraries covered by workspace backup. It does not copy `.venv`, delivery outputs or browser drafts. Download a pending draft before changing installation or browser origin. Open your projects, verify images and history and retain any delivery files you need before retiring the previous directory.

Alternatively, create **Workspace backup** in the previous version and restore it into the empty new installation. If an old project has its only preceding revision in `engagement.yaml.bak`, without snapshot history, the 0.21.2 exporter omits that copy. Keep the original directory and use the 0.26.0 migration to include this legacy recovery state. An older ZIP that already omitted the copy cannot reconstruct it. Existing projects remain readable. Backups containing annexes require 0.21.0 or later.

Existing IDs are retained. Since 0.21.2, the `finding_sequence` counter prevents deleted IDs from being reused; older versions do not preserve this guarantee. References already misdirected by older edits cannot be repaired automatically without knowing their original intent.

## CLI and development

Development and interface tests require Node.js 22+ and an installed Python environment. Run these commands from the project root.

API clients select error language with `X-UI-Language: es` or `en`. An absent or unsupported header keeps the historical Spanish default. URLs opened directly use that default; external library and tool diagnostics remain verbatim. This does not change report language or authored content.

```bash
.venv/bin/python export.py webapp/projects/my-project/engagement.yaml -f html -o report.html
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

Other export formats: `pdf`, `docx`, `md` (ZIP with images).

The included `examples/pending-severity/engagement.yaml` fixture contains two fictional findings with confirmed technical verification and no assigned severity. Its report text is in Spanish. In Word, table-of-contents titles are available immediately; page numbers are calculated when fields are updated in the editor. If they are missing or the content changes, use **Ctrl+A**, then **F9**. Word pagination is not copied from the PDF. Microsoft Word and LibreOffice may distribute content differently; desktop Microsoft Word remains a separate validation target.

The editor runs in one process on `127.0.0.1`; it is not a multiuser service. Certification profiles are starting points; check current provider requirements before an exam submission. Logos remain their owners' property and imply no affiliation.

The repository includes source, tests, demo, designs and usage documentation.

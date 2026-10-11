<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen with Prometeo and Evaristo" width="300">
</p>

# report-gen 0.31.4

**A local editor for turning security assessments into clear reports.** Organize findings, connect evidence, track remediation and retests, and prepare **PDF, Word, Markdown with images and portable HTML** from a saved revision.

[Español](README.md) · [Full guide](docs/guide.en.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

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

[Complete walkthrough and recommendations](docs/guide.en.md#first-report).

## What you can do

- **Document an assessment:** scope, methodology, assets, coverage, findings and reproducible steps; CVSS 3.1 and 4.0 where appropriate.
- **Work with evidence:** a gallery, captions, finding links, redacted copies and an inspector for published content.
- **Retain follow-up:** stable identities, recoverable revisions, comparisons with a marked delivery, remediation and a retest matrix.
- **Choose presentation:** start with Serious, compare the six general designs and open the specialized catalog when needed. Report language is independent of interface language.
- **Separate audiences:** technical, executive and public deliveries with explicit inclusion plans; public output requires approved prose and recorded consent.
- **Connect evidence and decisions:** claims, limitations, business context, comments and actual PDF review. [Workflow and optional requirements](docs/evidence-decisions-0230.en.md).

| Format | What you receive |
| --- | --- |
| PDF | A paginated `.pdf` report. |
| Word | An editable `.docx` with its own table-of-contents fields. |
| Markdown | A ZIP containing `report.md` and its images. |
| Portable HTML | A self-contained `.html` with reading filters. |

## Fixes in 0.31.4

The second banking exercise corrects searches for equivalent accents and phrases split across lines, together with Unicode highlighting. Word keeps long captions with their figures, arranges images inserted inside paragraphs and prevents isolated final table rows when the tail fits together. Its retest table gives owners more space. PDF gives portrait and nearly square evidence more space for readability. PDF verification reads Unicode font maps correctly, and the default engine reports missing glyphs before replacing a file. The extensive-report fixes from 0.31.3 remain available and visual review is still required. [Detailed changes](CHANGELOG.md).

## New in 0.31.0

- **Optional backup routine:** choose an external destination, frequency and retained generations. While the local server is open, it creates private unencrypted backups and tests restoration before rotating its own copies. Review the latest result or verify a copy manually. Browser drafts are not included.
- **Strict CVSS 3.1 vectors:** incomplete, duplicate or invalid pasted metrics show an error and preserve the previous finding. Valid vectors retain the same calculation.
- **A more maintainable editor:** transport, CVSS and preview have dedicated modules while saved project state remains shared. A tab blocked by a workspace change cannot resume a write after session preparation finishes.
- **Reproducible scale measurements:** synthetic projects with hundreds of findings and distinct images, interface timings and real exports in all four formats. Results identify the environment and corpus; they are not universal performance guarantees.
- **Lighter delivery preparation:** outgoing-text checks validate images without recompressing them. The complete inspector and exports retain their sanitization and verification.
- **Checked external-review materials:** all four Word inputs pass automated structural delivery checks. Native Microsoft Word review and the five participant sessions remain pending.

Bulk editing, per-owner deliveries, the installer and guided updates remain available. [Full changelog](CHANGELOG.md).

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

If you already use an external workspace, stop the editor, download **0.31.4 into a new directory** and run `python3 scripts/install.py --desktop --workspace /path/to/existing-data --lang en` there. This retains the data and updates the shortcut; run only one installation at a time. Do not copy the old `.venv`.

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

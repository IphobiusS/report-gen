<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen with Prometeo and Evaristo" width="300">
</p>

# report-gen 0.26.0

**A local editor for turning security assessments into clear reports.** Organize findings, connect evidence, track remediation and retests, and prepare **PDF, Word, Markdown with images and portable HTML** from a saved revision.

[Español](README.md) · [Full guide](docs/guide.en.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

## Install and launch

Primary path: **Linux/Kali and Python 3.10+**. The guide describes requirements and installation options.

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 start.py --ready --lang en
```

Open **http://127.0.0.1:8080** in your browser. `Ctrl+C` stops the server; `--port 8081` selects another local port.

`--ready` prepares `.venv` when needed, checks the engines and starts the editor. Initial setup downloads dependencies constrained by `requirements-audited.txt`. Missing optional engines are reported separately. See [detailed installation](docs/guide.en.md#install-and-launch) for native PDF libraries. **Node.js is not required to use the editor.**

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

## New in 0.26.0

One-command preparation and launch, verified migration from an earlier installation, a more visible first-report journey, and design selection with a recommendation and comparable samples. Specialized options remain available. [Full changes](CHANGELOG.md).

<a id="delivery-checks-and-limits"></a>

## What delivery checks establish

**View checks** shows the revision, SHA-256, size and controls for each file. Export checks compare content and references with different scope for each format. **They do not certify the assessment's correctness or visual presentation:** review PDF, Word, Markdown and HTML before delivery.

[Export checks, annexes and limitations](docs/guide.en.md#delivery-checks-and-limits). Optional [Ed25519 signing](docs/delivery-signing.md#optional-signing-of-a-delivery) establishes integrity relative to a pinned public key; it does not encrypt the delivery or certify its conclusions.

## Recovery and privacy

The editor runs on **`127.0.0.1` in one process**, without accounts or external services for normal editing. After dependency installation, everyday work stays local. Ollama assistance is **optional and explicitly requested**; read which fields it sends and its limitations before enabling it.

Projects live in `webapp/projects/`, personal libraries in `webapp/library/`. **Workspace backup** retains projects, originals and history; it is private material. The application does not encrypt stored data or drafts. [Recovery, backups and privacy](docs/guide.en.md#recovery-and-privacy).

Portable HTML contains the complete report: filters are not access permissions. Possible-secret detectors do not replace human review. Windows compatibility tests do not replace review in desktop Microsoft Word; Word and LibreOffice can paginate differently. Certification profiles imply no affiliation or guarantee of compliance with exam rules.

## Upgrade from an earlier version

Download **0.26.0 into a new directory**, stop the previous installation and run from the new directory:

```bash
python3 start.py --ready --upgrade-from /path/to/previous-report-gen --lang en
```

Migration requires a destination without projects or personal libraries. It preserves the source and creates a private backup. Check your projects before retiring the previous installation. You can also use **Workspace backup** to transfer them. Do not copy the old `.venv`.

[Backup compatibility and recovery of older projects](docs/guide.en.md#upgrade-from-an-earlier-version).

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

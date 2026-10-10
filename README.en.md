<p align="center">
  <img src="docs/img/report-gen-logo.png" alt="report-gen with Prometeo and Evaristo" width="300">
</p>

# report-gen 0.25.0

**A local editor for turning security assessments into clear reports.** Organize findings, connect evidence, track remediation and retests, and prepare **PDF, Word, Markdown with images and portable HTML** from a saved revision.

[Español](README.md) · [Full guide](docs/guide.en.md) · [0.25.0 validation](VALIDACION-0.25.0.md) · [Security](SECURITY.md)

## Install and launch

Primary path: **Linux/Kali and Python 3.10+**. This release's validation records Linux with Python 3.12; consult it for the tested scope.

```bash
git clone https://github.com/IphobiusS/report-gen.git
cd report-gen
python3 start.py --setup
python3 start.py --diagnose --lang en
python3 start.py
```

Open **http://127.0.0.1:8080** in your browser. `Ctrl+C` stops the server; `--port 8081` selects another local port.

`--setup` creates `.venv` and installs dependencies constrained by `requirements-audited.txt`; it needs an Internet connection. Read each engine's diagnostic result. See [detailed installation](docs/guide.en.md#install-and-launch) for native PDF libraries or the optional Chromium engine. **Node.js is not required to use the editor.**

## First report

1. On **Overview**, choose **Try Nimbus demo** to create an editable copy of a fictional case with 12 findings. Use **Create project** for your own assessment.
2. Open **Guide: first report**. Its six steps cover scope, findings, evidence, review and delivery without filling in or validating data for you.
3. Save, review the **Publication inspector**, and generate the formats you need from **Deliver**. Open the files before sharing them and keep a private project backup.

[Complete walkthrough and recommendations](docs/guide.en.md#first-report).

## What you can do

- **Document an assessment:** scope, methodology, assets, coverage, findings and reproducible steps; CVSS 3.1 and 4.0 where appropriate.
- **Work with evidence:** a gallery, captions, finding links, redacted copies and an inspector for published content.
- **Retain follow-up:** stable identities, recoverable revisions, comparisons with a marked delivery, remediation and a retest matrix.
- **Choose presentation:** designs and certification profiles, personal templates, and Spanish or English reports. Report language is independent of interface language.
- **Separate audiences:** technical, executive and public deliveries with explicit inclusion plans; public output requires approved prose and recorded consent.
- **Connect evidence and decisions:** claims, limitations, business context, comments and actual PDF review. [Workflow and optional requirements](docs/evidence-decisions-0230.en.md).

| Format | What you receive |
| --- | --- |
| PDF | A paginated `.pdf` report. |
| Word | An editable `.docx` with its own table-of-contents fields. |
| Markdown | A ZIP containing `report.md` and its images. |
| Portable HTML | A self-contained `.html` with reading filters. |

## New in 0.25.0

The retest matrix keeps labels and counts together; delivery preparation shows statuses and links for resolving pending items. Preview fits the available width and supports manual zoom. Documented PDF routes group steps by phase and retain their complete text alternative.

This release also improves YAML reading with libyaml and a bounded compatibility path, and adds public-key fingerprint lookup for optional signing. [Full changes](CHANGELOG.md) · [Tests, measurements and limitations](VALIDACION-0.25.0.md).

<a id="delivery-checks-and-limits"></a>

## What delivery checks establish

**View checks** shows the revision, SHA-256, size and controls for each file. Export checks compare content and references with different scope for each format. **They do not certify the assessment's correctness or visual presentation:** review PDF, Word, Markdown and HTML before delivery.

[Export checks, annexes and limitations](docs/guide.en.md#delivery-checks-and-limits). Optional [Ed25519 signing](docs/delivery-signing.md#optional-signing-of-a-delivery) establishes integrity relative to a pinned public key; it does not encrypt the delivery or certify its conclusions.

## Recovery and privacy

The editor runs on **`127.0.0.1` in one process**, without accounts or external services for normal editing. After dependency installation, everyday work stays local. Ollama assistance is **optional and explicitly requested**; read which fields it sends and its limitations before enabling it.

Projects live in `webapp/projects/`, personal libraries in `webapp/library/`. **Workspace backup** retains projects, originals and history; it is private material. The application does not encrypt stored data or drafts. [Recovery, backups and privacy](docs/guide.en.md#recovery-and-privacy).

Portable HTML contains the complete report: filters are not access permissions. Possible-secret detectors do not replace human review. Native Windows and desktop Microsoft Word require specific validation; Word and LibreOffice can paginate differently. Certification profiles imply no affiliation or guarantee of compliance with exam rules.

## Upgrade from an earlier version

Install **0.25.0 in a new directory**. Create a workspace backup with the previous version, restore it into the empty new installation, and check your projects before retiring the old one. Do not copy its `.venv` or overwrite data with demo files.

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
- [Changelog](CHANGELOG.md) and [0.25.0 validation](VALIDACION-0.25.0.md).

## Retained history

<details>
<summary>Earlier release notes</summary>

The guide above contains current instructions. These documents preserve earlier release context.

<a id="new-in-0240"></a><a id="new-in-0234"></a><a id="new-in-0233"></a><a id="new-in-0232"></a><a id="new-in-0231"></a><a id="new-in-0230"></a><a id="new-in-0221"></a><a id="new-in-0220"></a>

- [Detailed notes originally shipped with 0.25.0](docs/history/README-0.25.0-original.en.md).
- [Historical GitHub welcome for 0.13.0 (Spanish)](docs/history/README-github-0.13.0.md).
- [Earlier 0.18 README (Spanish)](docs/history/README-0.18.md).

</details>

# Acceptance contract · 0.44.0

This protocol defines checks, not a claim that they have run. GitHub Actions receipts and local logs identify each execution, source commit, errors and output hashes. Publication retains all seven existing required workflows; the `tests` workflow also requires the VEGA matrix.

## Catalog and APIs

- Exactly 90 stable IDs across seven categories, including 30 AI patterns, with ten authored nonempty fields in each of ES/EN/PT.
- Explicit bundled resources and strict schema; references record HTTPS URL, version and access date. Date/version mismatches are editorial defects, not automatically corrected by the application.
- Read-only search and detail do not mutate customer data. Personal copies retain technical guidance and never overwrite existing templates.
- Insertion checks project/library ETags. Missing/stale revisions cannot mutate state. Project language defaults independently of interface language.
- Imported patterns remain unverified and unrated; suggested evidence and retest instructions are not completed records.
- Seven independent work packages generate pending plans; selected findings retain unresolved targets for analyst completion. Atomic failure leaves no partial project.

## Browser and field guidance

`npm run test:knowledge` covers DOM/transport behavior and writing guidance. `npm run test:knowledge-browser` exercises actual Chromium and Flask, ES/EN/PT, search, filtering, pagination, detail, personal copies, insertion, draft protection, stale revisions, packages and annotated lessons. Screenshots and accessibility/geometry observations are written with the receipt.

Check keyboard access, Escape/focus return, 40px desktop and 44px mobile action targets, narrow widths and increased text. Field guidance must be optional and must not mutate the report. The sidebar retains its existing groups. Practice reuses Nimbus creation provenance and previous-project navigation.

## VEGA complex report

```sh
python scripts/build-knowledge-case.py --output /tmp/vega-case
python scripts/audit-knowledge-0440.py --projects /tmp/vega-case/projects --output /tmp/vega-exports --languages es en pt
```

For actual native DOCX rendering, provide `--native-executable /usr/bin/libreoffice --require-stable`. Use fresh output directories. Input preparation does not render a report: all final outputs go through report-gen's registered exporters and delivery snapshot pipeline.

Each language has 90 unverified findings, 90 pending test cases, seven assets, 14 explicitly synthetic figures, pending coverage and a 180-row matrix. PDF, DOCX, HTML and Markdown must preserve catalog content and unique entry/row markers. Check continued table headers, structural DOCX rows, immutable input hashes and expected pending-state warnings. These warnings must not be concealed through false verification or severity assignment.

Receipts report pages, bytes, hashes, exporter errors and native rendering results. Structural/content checks are not a visual review of every page. Microsoft Word acceptance remains separate from LibreOffice. No security tests execute against external systems.

## Human acceptance still required

Use the existing onboarding participant protocol with junior and senior testers. Ask them to select an applicable pattern, reject a false positive, adapt a finding to evidence, prepare a package and deliver an inspected report. Record confusion, completion time, recovery behavior and suggested changes without inventing participants or results. Automated success cannot close this gate.

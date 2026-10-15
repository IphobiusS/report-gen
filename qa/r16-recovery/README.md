# R16 — recovered Estuario acceptance corpus

The three projects in `projects/` are the original fictional Estuario backups
recovered from the October 14 checkpoint (`31f09ee5`). Their wording, URLs,
unverified-control warnings and evidence image bytes are preserved.

Run the twelve exports and strict content contracts with:

```sh
python scripts/audit-estuario-r16.py --output out/estuario-r16
```

Use a new output directory. Install fonts covering Devanagari, Japanese and
Korean in addition to Latin and Arabic (for example Noto Core and Noto CJK).
The audit records per-format results, SHA-256 hashes and source immutability.
It does not claim visual review or Microsoft Word desktop compatibility.

October 15 recovery: all twelve PDF, DOCX, HTML and Markdown exports pass
their content contracts locally. Native stable LibreOffice and browser checks
run separately in CI; rendered pages require visual review. Version 0.35.0
remains a candidate until the seven exact-commit release gates complete.

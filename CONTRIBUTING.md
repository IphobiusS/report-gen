# Contributing / Contribuir

0.20 freezes feature scope while prioritizing security, data preservation and usability fixes. Start an issue with the user problem and a small reproducible case before proposing a large feature. Use synthetic projects and evidence.

For a fix, include a regression that fails on the affected version and passes with the change. Preserve existing tests unless the public contract intentionally changes; explain that change. Run Python tests, JS save/merge tests and the applicable real-browser flow. Report exactly which OS, browser and document renderer were used. A LibreOffice render is not a Microsoft Word test.

UI and template changes must support Spanish and English. Keep Calibri/Carlito and monospaced commands in reports. Do not silently translate or rewrite assessment content. Keep licenses and source attribution with third-party assets. New templates must not imply provider affiliation or compliance with current exam rules without verification.

For privacy changes, test private captures, originals, disabled content, old revisions, image metadata and all public formats. For persistence, test conflicts, failed writes, abrupt tab closure and backup restoration. Never add a telemetry or network dependency to ordinary editing without explicit design review.

En español: prioriza errores reproducibles, datos ficticios y pruebas que protejan el contenido. Mantén ES/EN, registra los motores probados y documenta cambios de contrato. Las contribuciones de plantillas necesitan licencia y atribución. No incluyas informes reales de clientes.

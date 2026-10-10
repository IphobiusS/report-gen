# Security / Seguridad

report-gen is a local, single-process editor. Keep it bound to 127.0.0.1. Project YAML, backups, originals, history and browser drafts can contain sensitive assessment data. Protect the machine and its backups. The app does not encrypt those stores.

Client exports use a publication copy, exclude the capture inbox and original evidence files, and strip image metadata. Pattern checks are assistance, not a guarantee. Review the publication inspector, including screenshots and filenames. Portable HTML filtering is not an access-control mechanism. Internal comparisons and editable backups must not be shared as client deliverables.

For suspected data loss, stop editing, preserve the project directory and download any recoverable browser draft. Include the version, operating system, browser, expected behavior and minimal reproduction in a report. Use synthetic data; never attach a client's project, credentials or original evidence to a public issue.

For security bugs, use the repository's private vulnerability-reporting channel if enabled. If unavailable, contact the maintainer privately through the contact linked in the application to arrange a secure report. No response-time guarantee is claimed. Security and data-loss fixes remain in scope after the 0.20 feature freeze.

En español: trata respaldos, originales, historial y borradores como datos privados. Ante pérdida de datos, detén la edición, conserva el proyecto y descarga el borrador si está disponible. Comunica fallos con datos ficticios. Usa un canal privado para vulnerabilidades y no adjuntes material de clientes a incidencias públicas.

# Seguridad · Security

[Español](#español) · [English](#english) · [README](README.md)

## Español

### Comunicar una vulnerabilidad

**No publiques vulnerabilidades ni datos de clientes en una incidencia pública.**

1. Comprueba si está disponible **Report a vulnerability** en la [pestaña Security del repositorio](https://github.com/IphobiusS/report-gen/security). Si el reporte privado está habilitado, utiliza ese canal.
2. Si no está disponible, contacta en privado a [Sebastián Latorre Muñoz](https://www.linkedin.com/in/sebastian-latorre-munoz/), el contacto enlazado en la aplicación, para acordar un canal seguro. En ese primer mensaje, indica únicamente que deseas comunicar una vulnerabilidad; no envíes credenciales ni evidencia sensible.
3. Prepara una reproducción mínima con datos ficticios. Incluye la versión y, si lo conoces, el commit; sistema operativo, navegador y motor de documentos; pasos; resultado esperado y observado; e impacto estimado. Distingue lo comprobado de lo que todavía sea una hipótesis.

Los problemas de seguridad y pérdida de datos tienen prioridad. No se garantiza un plazo de respuesta o corrección. Usa la [última versión estable publicada](https://github.com/IphobiusS/report-gen/releases/latest) y consulta el [registro de cambios](CHANGELOG.md); esta política no establece mantenimiento de ramas antiguas.

### Modelo de uso y datos privados

report-gen es un editor local de un solo proceso. Mantén el servidor ligado a **`127.0.0.1`**; no lo expongas como servicio público ni como aplicación compartida en una red.

Los proyectos YAML, originales, historial, respaldos editables y borradores del navegador pueden contener información sensible de una evaluación. Protege el equipo, la cuenta del sistema, el perfil del navegador y las copias de seguridad. **Los proyectos en disco y los borradores del navegador no están cifrados por la aplicación.**

El [respaldo privado con contraseña](docs/guide.es.md#respaldos-privados-con-contraseña) es opcional y cifra el archivo descargado `.rgbackup`; no cifra los datos de trabajo. El ZIP sin cifrar sigue disponible. Conserva la contraseña por separado: report-gen no puede recuperarla. Un respaldo editable, cifrado o no, no es una entrega para el cliente.

### Revisar antes de entregar

Las exportaciones para el cliente se preparan a partir de una copia de publicación. Excluyen la bandeja de captura y los archivos originales de evidencia, y eliminan metadatos de las imágenes procesadas. Los campos, imágenes y anexos que decides publicar siguen necesitando revisión.

- Revisa el inspector de publicación, los archivos finales, las capturas y los nombres de archivo.
- Trata las detecciones por patrones como una ayuda; no garantizan que no queden secretos o datos personales.
- No utilices el filtrado de un HTML portátil como mecanismo de control de acceso.
- Conserva las comparaciones internas y los respaldos editables separados de las entregas para el cliente.

### Ante una posible pérdida de datos

Detén la edición, conserva el directorio del proyecto y descarga cualquier borrador recuperable del navegador. No sobrescribas la única copia mientras investigas. Documenta los pasos y el entorno con datos ficticios; nunca adjuntes proyectos de clientes, credenciales, originales ni respaldos a una incidencia pública.

Para errores reproducibles sin información sensible, consulta [cómo contribuir](CONTRIBUTING.md#español). Si sospechas una vulnerabilidad, utiliza el procedimiento privado anterior.

## English

### Report a vulnerability

**Do not disclose vulnerabilities or client data in a public issue.**

1. Check whether **Report a vulnerability** is available on the [repository's Security tab](https://github.com/IphobiusS/report-gen/security). Use that channel if private reporting is enabled.
2. If it is unavailable, contact [Sebastián Latorre Muñoz](https://www.linkedin.com/in/sebastian-latorre-munoz/) privately, using the contact linked in the application, to arrange a secure channel. In the initial message, state only that you wish to report a vulnerability; do not send credentials or sensitive evidence.
3. Prepare a minimal reproduction with synthetic data. Include the version and commit if known; operating system, browser and document renderer; steps; expected and observed behavior; and estimated impact. Separate verified observations from hypotheses.

Security and data-loss fixes are priorities. No response or remediation deadline is guaranteed. Use the [latest stable release](https://github.com/IphobiusS/report-gen/releases/latest) and consult the [changelog](CHANGELOG.md); this policy does not establish maintenance for older branches.

### Usage model and private data

report-gen is a local, single-process editor. Keep the server bound to **`127.0.0.1`**; do not expose it as a public service or a shared network application.

YAML projects, originals, history, editable backups and browser drafts can contain sensitive assessment data. Protect the machine, operating-system account, browser profile and backups. **The application does not encrypt projects on disk or browser drafts.**

The optional [password-protected private backup](docs/guide.en.md#password-encrypted-private-backups) encrypts the downloaded `.rgbackup` file, not working data. An unencrypted ZIP remains available. Keep the password separately: report-gen cannot recover it. An editable backup, encrypted or otherwise, is not a client deliverable.

### Review before delivery

Client exports are prepared from a publication copy. They exclude the capture inbox and original evidence files, and strip metadata from processed images. Fields, images and annexes you choose to publish still require review.

- Review the publication inspector, final files, screenshots and filenames.
- Treat pattern checks as assistance; they do not guarantee that all secrets or personal data have been removed.
- Do not use portable HTML filtering as an access-control mechanism.
- Keep internal comparisons and editable backups separate from client deliverables.

### Suspected data loss

Stop editing, preserve the project directory and download any recoverable browser draft. Do not overwrite the only copy while investigating. Document the steps and environment using synthetic data; never attach client projects, credentials, originals or backups to a public issue.

For reproducible bugs without sensitive information, see [how to contribute](CONTRIBUTING.md#english). If you suspect a vulnerability, use the private reporting procedure above.

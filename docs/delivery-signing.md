# Firma opcional de una entrega

R10 permite firmar **el ZIP de entrega de un informe** que ya descargaste del editor. No modifica la entrega, no firma automáticamente y no usa la clave privada en el servidor. Los ZIP de instalación de report-gen y los respaldos de proyectos tienen otros formatos y no son entradas de este comando.

Instala la dependencia opcional desde la raíz del proyecto:

```bash
python -m pip install ".[signing]"
```

Crea un directorio privado fuera de report-gen y de cualquier proyecto de informe. Estos comandos usan rutas de ejemplo que debes sustituir por las tuyas; el directorio debe existir antes de generar la clave.

```bash
mkdir -m 700 /ruta/privada/claves-report-gen
python -m delivery_signature keygen \
  --private-key /ruta/privada/claves-report-gen/autor.pem \
  --public-key /ruta/privada/claves-report-gen/autor-publica.pem

python -m delivery_signature sign /ruta/entregas/entrega.zip \
  --private-key /ruta/privada/claves-report-gen/autor.pem \
  --signature /ruta/entregas/entrega.sig.json

python -m delivery_signature verify /ruta/entregas/entrega.zip \
  --signature /ruta/entregas/entrega.sig.json \
  --public-key /ruta/confiable/autor-publica.pem

python -m delivery_signature fingerprint \
  --public-key /ruta/confiable/autor-publica.pem
```

La privada se genera como PEM PKCS8 sin cifrado, con permisos **0600**. Su generación y uso requieren POSIX y un único enlace de archivo. Los archivos de clave deben contener un único bloque PEM completo, sin otra clave o contenido ajeno; se admiten LF/CRLF y espacios de borde. Conservarla y respaldarla es responsabilidad de su propietario; no la subas al editor, al proyecto, a entregas ni a un repositorio. Las salidas deben ser nuevas: ningún comando sobrescribe entradas o archivos existentes. Las rutas no admiten enlaces simbólicos. Para volver a firmar, elige otro nombre de firma.

Comparte y fija la pública o su huella `key_sha256` mediante un canal confiable independiente. La huella usa SHA-256 de los 32 bytes públicos Ed25519, **no** del texto PEM. Descargar pública, ZIP y firma desde el mismo origen no demuestra por sí solo quién posee esa clave. `verify` usa exclusivamente la pública externa que eliges: no acepta una pública incorporada al ZIP o a la firma como ancla automática.

`fingerprint` calcula esa misma huella a partir de una pública recibida, sin leer una entrega ni crear archivos. Devuelve JSON con `algorithm: "Ed25519"`, `key_sha256`, `scope: "raw_32_byte_public_key"`, `message` y `language`. El `key_sha256` coincide con el de `keygen`, `sign` y `verify` para la misma clave, aunque el PEM use LF o CRLF. Aplica el mismo lector estricto: pública Ed25519 única y completa, máximo 16 KiB, archivo regular, sin enlaces simbólicos ni contenido adicional; una privada no sirve como entrada. Necesita el extra `signing` y su cálculo no autentica el origen de la clave.

La firma separada `report-gen-delivery-signature`, versión 1, usa Ed25519 de `cryptography`. El mensaje firmado comienza con los bytes ASCII `report-gen-delivery-signature-v1` y un byte nulo, seguido del JSON del `payload` con claves ordenadas, separadores `,` y `:`, caracteres ASCII escapados y sin números no finitos. Este contexto pertenece al formato de la aplicación: no implementa Ed25519ctx ni Ed25519ph.

El `payload` vincula tamaño y SHA-256 del **ZIP completo**, tamaño y SHA-256 de los bytes exactos de `verificacion.json`, y la huella pública. Cambiar un archivo, el LEEME/README, los espacios del manifiesto, recomprimir el ZIP o añadir miembros invalida la firma. La representación exterior del JSON de firma puede cambiar espacios y orden sin cambiar su mensaje canónico; claves duplicadas, campos desconocidos, algoritmos/versiones no soportados y Base64 no canónico se rechazan.

Los nombres Unicode de anexos permitidos se conservan exactamente, incluso si usan caracteres descompuestos (NFD). Para detectar nombres duplicados y colisiones archivo/directorio se comparan normalizados a NFC y sin distinguir mayúsculas; esto no cambia ningún nombre, miembro ZIP ni byte firmado.

Antes de firmar o aceptar una firma se valida el manifiesto v1, la existencia de todos sus archivos, sus tamaños y hashes, y un único LEEME/README. Se admiten las entregas normales y los derivados oficiales técnicos, ejecutivos y públicos; sus metadatos `audience`/`design_guidance` se conservan como decisiones documentadas, sin certificar autorizaciones de publicación. Se usa una copia temporal privada del archivo ZIP completo para verificar siempre una misma captura; **no se extraen miembros** ni se ejecutan archivos. Límites: ZIP 256 MiB, miembros externos expandidos 512 MiB, 20.000 entradas, directorio central 16 MiB, manifiesto 12 MiB y claves/firma 16 KiB. Se rechazan ZIP divididos/ZIP64, prefijos, datos finales ajenos al ZIP, cifrado de miembros, compresiones distintas de STORE/DEFLATE, rutas no portables, enlaces, duplicados sin distinguir mayúsculas y colisiones archivo/directorio. Los ZIP internos de Word/Markdown se verifican como bytes del manifiesto, sin descomprimirlos aquí.

Una firma válida acredita integridad con respecto a **esa clave pública fijada**. No certifica identidad real, validez técnica de hallazgos, revisión humana, fecha confiable, ausencia general de secretos ni cifrado de la entrega. La firma mantiene visibles sus archivos. Nunca se crea una firma usando una clave privada de ejemplo como identidad del autor de una entrega real.

Para mensajes y ayuda en inglés, añade `--lang en` a los mismos comandos. Se devuelve JSON y código 0 en éxito, JSON de error y código 1 si falla una operación; los errores de argumentos de `argparse` usan código 2. Una instalación sin el extra `signing` conserva las exportaciones normales y comunica qué dependencia falta cuando se solicita firmar, verificar o calcular una huella.

# Optional signing of a delivery

Use `python -m delivery_signature --lang en keygen`, `sign`, `verify`, or `fingerprint` with the arguments above. This is an opt-in local command for report delivery ZIPs, not installation packages or project backups. Keep the unencrypted PKCS8 private key outside report-gen and report projects, in a POSIX file with mode 0600 and one link. Outputs are exclusive and never overwrite existing files.

`fingerprint --public-key /trusted/author-public.pem` returns JSON with `algorithm`, `key_sha256`, `scope`, `message`, and `language`. It hashes the 32 raw Ed25519 public bytes, not PEM text, and uses the same strict public-key reader as verification. It requires the optional `signing` dependency, rejects private keys, symlinks, extra PEM blocks and oversized or nonregular files, and does not write files or establish the key owner's identity. Confirm the fingerprint through a separate trusted channel.

Pin the external Ed25519 public key through a separate trusted channel. The detached v1 signature binds the exact whole ZIP and manifest bytes; verification also checks every declared file and rejects unsafe or oversized archives without extracting them. A verified signature establishes integrity for that pinned key. It does not automatically establish a real person's identity, trustworthy signing time, finding correctness, secrecy or encryption.

Ed25519 implementation and serialization follow the library's documented API: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/ . Algorithm specification and test vectors: https://www.rfc-editor.org/rfc/rfc8032 . The application adds a fixed message prefix and signs a canonical JSON payload with ordinary Ed25519; it does not implement cryptographic arithmetic.

# report-gen: selected HTTP evidence from Burp

This optional Java extension sends only HTTP request/response pairs explicitly selected in Burp's context menu (or the message whose editor context menu was opened). It does not enumerate Proxy history, run a scanner, issue requests to assessment targets, or publish a report.

## Build

Use Java 17 or newer and the official compile-only Montoya API artifact `net.portswigger.burp.extensions:montoya-api:2025.2`:

```sh
curl --fail --location --output montoya-api-2025.2.jar https://repo.maven.apache.org/maven2/net/portswigger/burp/extensions/montoya-api/2025.2/montoya-api-2025.2.jar
python integrations/burp-report-gen/build.py montoya-api-2025.2.jar --test
```

The output is `integrations/burp-report-gen/build/report-gen-burp.jar`. The Montoya API and the test harness are not bundled. With a Java 17 runtime but no `javac`, pass a separately obtained Eclipse compiler JAR using `--ecj /path/to/ecj.jar`. The build script never downloads dependencies.

## Use

1. In Burp, load the JAR as a Java extension under Extensions. Use a Burp version compatible with Montoya API 2025.2 or newer.
2. In report-gen, save the project and open **HTTP evidence → Pair Burp**. Optionally choose existing findings and assets as the destination, then generate a pairing code.
3. In Burp, select the request/response pairs to capture, right-click, and choose **Send selected HTTP pair(s) to report-gen**. Paste the code and optionally record the observed identity or role.
4. Review the displayed destination and selected message count. Confirm the send.
5. Reload the report-gen project. The messages arrive as private evidence. Open each record to annotate, link, compare, and prepare a separate reviewed technical publication copy.

Pairing codes expire after 15 minutes, one successful send, revocation, server restart, a project revision change, or another pairing for the same project. Generate a new code after the project changes. If a connection fails after sending, reload before retrying: the server may already have saved the evidence.

## Boundaries

- Destination must be the local HTTP report-gen server (`127.0.0.1`, `localhost`, or `::1`). Redirects are disabled. No remote connector endpoint is supported.
- The extension obtains its own local session and preserves cookies. Normal trusted-host, origin, CSRF, workspace, revision and pairing checks all remain active.
- Limit: 100 selected pairs, 4 MiB JSON payload, 200 headers per message and 256 KiB per body. Oversized selections are rejected before sending; the server also validates all records atomically.
- Binary bodies are preserved as canonical base64. Duplicate header names and order are preserved. The structured record does not claim to be a byte-for-byte packet capture: protocol framing and header wire whitespace are not retained.
- Original capture time is left blank when unavailable from this selection API. The server records import time separately; it is not presented as capture time.
- A hash detects accidental original/copy changes. It does not authenticate who supplied evidence. Local project storage and browser drafts retain the application's existing unencrypted-storage behavior.
- Private originals may contain credentials or personal data. Technical publication requires a separate editable copy and explicit confirmation of its exact contents. Executive/public deliveries do not receive HTTP bodies automatically.
- Pairing codes and payloads are not logged by the extension. Codes are kept only in the interaction that uses them.

## Verification

`build.py --test` compiles against real Montoya interfaces and executes a headless Java harness for selection-only access, binary/JSON fidelity, Unicode project names, external-destination rejection, and cookie/CSRF/token transport to a local HTTP server. Python tests separately verify the report-gen API's authorization, CAS, expiry, replay, malformed data, HAR selection and publication isolation. DOM tests cover ES/EN/PT consent and stale-form behavior; the Chromium scenario is `tests/test_http_evidence_0420_browser.cjs`.

Compilation and the Java harness do **not** establish successful loading or menu behavior inside a running Burp installation. Native Burp acceptance must be recorded separately; it was not available in the development environment for this change.

Official API references:

- https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/ui/contextmenu/ContextMenuEvent.html
- https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/http/message/HttpRequestResponse.html

package reportgen;

import burp.api.montoya.BurpExtension;
import burp.api.montoya.MontoyaApi;
import burp.api.montoya.http.message.HttpHeader;
import burp.api.montoya.http.message.HttpRequestResponse;
import burp.api.montoya.ui.contextmenu.ContextMenuEvent;
import burp.api.montoya.ui.contextmenu.ContextMenuItemsProvider;
import java.awt.Component;
import java.awt.GridLayout;
import java.net.CookieManager;
import java.net.CookiePolicy;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.swing.JLabel;
import javax.swing.JMenuItem;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingWorker;

/** Explicit, selected-only intake. Never issues requests to assessed targets. */
public final class ReportGenExtension implements BurpExtension, ContextMenuItemsProvider {
    private static final int MAX_PAIRS = 100;
    private static final int MAX_BODY = 256 * 1024;
    private static final int MAX_PAYLOAD = 4 * 1024 * 1024;

    @Override public void initialize(MontoyaApi api) {
        api.extension().setName("report-gen — selected HTTP evidence");
        api.userInterface().registerContextMenuItemsProvider(this);
        api.logging().logToOutput("report-gen: select request/response pairs, right-click, and paste a one-use pairing code from report-gen.");
    }

    @Override public List<Component> provideMenuItems(ContextMenuEvent event) {
        // Never query Proxy history, Site Map, Scanner results or Organizer.
        List<HttpRequestResponse> selected = new ArrayList<>(event.selectedRequestResponses());
        if (selected.isEmpty()) {
            event.messageEditorRequestResponse().ifPresent(message -> selected.add(message.requestResponse()));
        }
        if (selected.isEmpty()) return List.of();
        JMenuItem item = new JMenuItem("Send " + selected.size() + " selected HTTP pair(s) to report-gen…");
        item.setEnabled(selected.size() <= MAX_PAIRS);
        item.addActionListener(action -> confirmAndSend(List.copyOf(selected)));
        return List.of(item);
    }

    private void confirmAndSend(List<HttpRequestResponse> selected) {
        JTextArea code = new JTextArea(4, 54);
        code.setLineWrap(true);
        JTextField identity = new JTextField();
        JPanel panel = new JPanel(new GridLayout(0, 1, 4, 4));
        panel.add(new JLabel("One-use pairing code from report-gen → HTTP evidence → Pair Burp:"));
        panel.add(new JScrollPane(code));
        panel.add(new JLabel("Observed identity / role (optional):"));
        panel.add(identity);
        panel.add(new JLabel(selected.size() + " selected pairs only. Originals stay private; publication requires separate review."));
        if (JOptionPane.showConfirmDialog(null, panel, "Send selected HTTP evidence", JOptionPane.OK_CANCEL_OPTION,
                JOptionPane.PLAIN_MESSAGE) != JOptionPane.OK_OPTION) return;
        final Pairing pairing;
        final String payload;
        try {
            pairing = Pairing.parse(code.getText().trim());
            if (identity.getText().getBytes(StandardCharsets.UTF_8).length > 500) throw new IllegalArgumentException("Identity exceeds 500 bytes.");
            payload = serialize(selected, identity.getText());
        } catch (Exception error) {
            JOptionPane.showMessageDialog(null, error.getMessage(), "report-gen", JOptionPane.ERROR_MESSAGE);
            return;
        }
        if (JOptionPane.showConfirmDialog(null, "Destination: " + pairing.api + "\nProject: " + pairing.project
                + "\nSend " + selected.size() + " explicitly selected pair(s)?", "Confirm destination",
                JOptionPane.OK_CANCEL_OPTION) != JOptionPane.OK_OPTION) return;
        new SwingWorker<String, Void>() {
            @Override protected String doInBackground() throws Exception { return send(pairing, payload, selected.size()); }
            @Override protected void done() {
                try { JOptionPane.showMessageDialog(null, get(), "report-gen", JOptionPane.INFORMATION_MESSAGE); }
                catch (Exception error) {
                    // No payload, pairing code or credentials are written to logs.
                    Throwable cause = error.getCause() == null ? error : error.getCause();
                    JOptionPane.showMessageDialog(null, cause.getMessage(), "report-gen", JOptionPane.ERROR_MESSAGE);
                }
            }
        }.execute();
    }

    static String send(Pairing pairing, String payload, int count) throws Exception {
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
                .followRedirects(HttpClient.Redirect.NEVER)
                .cookieHandler(new CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER)).build();
        HttpResponse<String> session = client.send(HttpRequest.newBuilder(URI.create(pairing.api + "/api/session"))
                .timeout(Duration.ofSeconds(10)).header("Origin", pairing.api).GET().build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (session.statusCode() != 200) throw new IllegalStateException("Local session failed (HTTP " + session.statusCode() + ").");
        String csrf = scalar(session.body(), "csrf");
        String workspace = scalar(session.body(), "workspace_id");
        if (!workspace.equals(pairing.workspace)) throw new IllegalStateException("Workspace changed. Generate another pairing code.");
        URI destination = URI.create(pairing.api + "/api/projects/" + URLEncoder.encode(pairing.project, StandardCharsets.UTF_8)
                + "/http-evidence/bridge");
        HttpResponse<String> response = client.send(HttpRequest.newBuilder(destination).timeout(Duration.ofSeconds(30))
                .header("Origin", pairing.api).header("Content-Type", "application/json")
                .header("X-CSRF-Token", csrf).header("X-Report-Gen-Workspace", pairing.workspace)
                .header("X-Report-Gen-Pairing", pairing.token).header("If-Match", '"' + pairing.revision + '"')
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8)).build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() != 200) {
            String advice = response.statusCode() == 409 ? "Project changed; reload and pair again."
                    : response.statusCode() == 403 ? "Pairing expired, used, revoked, or invalid; pair again."
                    : response.statusCode() == 422 || response.statusCode() == 413 ? "A selected message exceeds intake limits or contains unsupported data. Nothing was imported."
                    : "Check report-gen. If the connection was lost, reload the project before retrying.";
            throw new IllegalStateException("Import failed (HTTP " + response.statusCode() + "). " + advice);
        }
        return count + " pair(s) imported privately. Reload the report-gen project to review and link them. Pairing code consumed.";
    }

    static String serialize(List<HttpRequestResponse> pairs, String identity) {
        if (pairs.isEmpty() || pairs.size() > MAX_PAIRS) throw new IllegalArgumentException("Select 1–100 HTTP pairs.");
        StringBuilder json = new StringBuilder("{\"records\":[");
        for (int i = 0; i < pairs.size(); i++) {
            if (i > 0) json.append(',');
            HttpRequestResponse pair = pairs.get(i);
            var req = pair.request();
            String title = req.method() + " " + req.url();
            // Server retains the full URL; this short title is only an editor label.
            if (title.length() > 200) title = title.substring(0, 200);
            json.append("{\"title\":").append(quote(title)).append(",\"original\":{\"identity\":").append(quote(identity))
                    .append(",\"captured_at\":\"\",\"source\":\"Burp Montoya selected messages\",\"request\":{")
                    .append("\"method\":").append(quote(req.method())).append(",\"url\":").append(quote(req.url()))
                    .append(",\"http_version\":").append(quote(req.httpVersion())).append(",\"headers\":")
                    .append(headers(req.headers())).append(",\"body_encoding\":\"base64\",\"body\":")
                    .append(body(req.body().getBytes())).append("},\"response\":");
            if (pair.response() == null) json.append("null");
            else {
                var res = pair.response();
                json.append("{\"status\":").append(res.statusCode()).append(",\"http_version\":").append(quote(res.httpVersion()))
                        .append(",\"headers\":").append(headers(res.headers())).append(",\"body_encoding\":\"base64\",\"body\":")
                        .append(body(res.body().getBytes())).append('}');
            }
            json.append("}}");
            if (json.length() > MAX_PAYLOAD) throw new IllegalArgumentException("Selection exceeds 4 MiB. Select fewer messages.");
        }
        json.append("]}");
        if (json.toString().getBytes(StandardCharsets.UTF_8).length > MAX_PAYLOAD)
            throw new IllegalArgumentException("Selection exceeds 4 MiB. Select fewer messages.");
        return json.toString();
    }

    private static String body(byte[] bytes) {
        if (bytes.length > MAX_BODY) throw new IllegalArgumentException("A selected body exceeds 256 KiB. No message was sent.");
        return quote(Base64.getEncoder().encodeToString(bytes));
    }

    private static String headers(List<HttpHeader> values) {
        if (values.size() > 200) throw new IllegalArgumentException("A message exceeds 200 headers.");
        List<String> parts = new ArrayList<>();
        for (HttpHeader value : values) parts.add("{\"name\":" + quote(value.name()) + ",\"value\":" + quote(value.value()) + '}');
        return '[' + String.join(",", parts) + ']';
    }

    static String quote(String value) {
        StringBuilder result = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c == '"' || c == '\\') result.append('\\').append(c);
            else if (c < 0x20 || Character.isSurrogate(c)) result.append(String.format("\\u%04x", (int)c));
            else result.append(c);
        }
        return result.append('"').toString();
    }

    // Pairing/session fields are server-issued strings. Do not parse any
    // captured HTTP data with this helper or accept arbitrary JSON structures.
    static String scalar(String json, String name) {
        Matcher matcher = Pattern.compile("\"" + Pattern.quote(name) + "\"\\s*:\\s*\"((?:[^\"\\\\\\x00-\\x1f]|\\\\[\"\\\\/bfnrt]|\\\\u[0-9A-Fa-f]{4})*)\"").matcher(json);
        if (!matcher.find()) throw new IllegalArgumentException("Missing or invalid " + name + ".");
        String value = matcher.group(1);
        if (matcher.find()) throw new IllegalArgumentException("Duplicate " + name + ".");
        StringBuilder decoded = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (c != '\\') { decoded.append(c); continue; }
            char escaped = value.charAt(++i);
            switch (escaped) {
                case 'u' -> { decoded.append((char)Integer.parseInt(value.substring(i+1,i+5),16)); i+=4; }
                case 'n' -> decoded.append('\n');
                case 'r' -> decoded.append('\r');
                case 't' -> decoded.append('\t');
                case 'b' -> decoded.append('\b');
                case 'f' -> decoded.append('\f');
                default -> decoded.append(escaped);
            }
        }
        return decoded.toString();
    }

    static final class Pairing {
        final String api, project, workspace, revision, token;
        private Pairing(String api, String project, String workspace, String revision, String token) {
            this.api=api;this.project=project;this.workspace=workspace;this.revision=revision;this.token=token;
        }
        static Pairing parse(String code) {
            if (!code.startsWith("rg1.") || code.length() > 4096) throw new IllegalArgumentException("Invalid pairing code.");
            String json = new String(Base64.getUrlDecoder().decode(code.substring(4)), StandardCharsets.UTF_8);
            String api = scalar(json,"api"), project=scalar(json,"project"), workspace=scalar(json,"workspace"),
                    revision=scalar(json,"revision"), token=scalar(json,"token");
            URI uri = URI.create(api);
            if (!"http".equals(uri.getScheme()) || !List.of("127.0.0.1", "localhost", "[::1]", "::1").contains(uri.getHost())
                    || uri.getUserInfo()!=null || uri.getQuery()!=null || uri.getFragment()!=null || !uri.getPath().isEmpty()
                    || uri.getPort() < -1 || uri.getPort() > 65535)
                throw new IllegalArgumentException("Pairing destination must be the local report-gen HTTP server.");
            if (!project.matches("[\\p{L}\\p{N}_-]{1,80}") || !revision.matches("[a-f0-9]{64}")
                    || !workspace.matches("[A-Za-z0-9_-]{8,200}") || !token.matches("[A-Za-z0-9_-]{32,100}"))
                throw new IllegalArgumentException("Invalid project, revision, workspace or pairing token.");
            return new Pairing(api,project,workspace,revision,token);
        }
    }
}

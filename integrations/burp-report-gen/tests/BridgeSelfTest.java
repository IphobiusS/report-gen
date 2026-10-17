package reportgen;

import burp.api.montoya.core.ByteArray;
import burp.api.montoya.http.message.HttpHeader;
import burp.api.montoya.http.message.HttpRequestResponse;
import burp.api.montoya.http.message.requests.HttpRequest;
import burp.api.montoya.http.message.responses.HttpResponse;
import burp.api.montoya.ui.contextmenu.ContextMenuEvent;
import com.sun.net.httpserver.HttpServer;
import java.lang.reflect.Proxy;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

/** Contract/transport test using the real Montoya interfaces, without Burp UI. */
public final class BridgeSelfTest {
    interface Answer { Object get(String method); }
    @SuppressWarnings("unchecked") static <T> T proxy(Class<T> type, Answer answer) {
        return (T)Proxy.newProxyInstance(type.getClassLoader(),new Class<?>[]{type},(p,m,a)->answer.get(m.getName()));
    }
    static void check(boolean condition,String message) { if(!condition)throw new AssertionError(message); }
    static void rejected(Runnable code) { try{code.run();}catch(IllegalArgumentException expected){return;}throw new AssertionError("Expected rejection"); }
    static String config(String origin,String project) {
        return "rg1."+Base64.getUrlEncoder().withoutPadding().encodeToString(("{\"api\":"+ReportGenExtension.quote(origin)
            +",\"project\":"+ReportGenExtension.quote(project)+",\"workspace\":\"workspace0123456789\",\"revision\":\""
            +"a".repeat(64)+"\",\"token\":\""+"b".repeat(43)+"\"}").getBytes(StandardCharsets.UTF_8));
    }
    static HttpRequestResponse pair() {
        ByteArray binary=proxy(ByteArray.class,m->{if(m.equals("getBytes"))return new byte[]{0,(byte)255,65};throw new AssertionError(m);});
        HttpHeader header=proxy(HttpHeader.class,m->switch(m){case "name"->"Authorization";case "value"->"Bearer test-secret";default->throw new AssertionError(m);});
        HttpRequest request=proxy(HttpRequest.class,m->switch(m){case "method"->"POST";case "url"->"https://target.invalid/account/1";case "httpVersion"->"HTTP/2";case "headers"->List.of(header);case "body"->binary;default->throw new AssertionError(m);});
        HttpResponse response=proxy(HttpResponse.class,m->switch(m){case "statusCode"->(short)200;case "httpVersion"->"HTTP/2";case "headers"->List.of();case "body"->binary;default->throw new AssertionError(m);});
        return proxy(HttpRequestResponse.class,m->switch(m){case "request"->request;case "response"->response;default->throw new AssertionError(m);});
    }
    public static void main(String[] args) throws Exception {
        for(String bad:List.of("https://example.test","http://127.0.0.1.attacker.test","http://user@127.0.0.1","http://127.0.0.1/path","http://127.0.0.1#fragment","file:///tmp"))
            rejected(()->ReportGenExtension.Pairing.parse(config(bad,"case")));
        rejected(()->ReportGenExtension.Pairing.parse(config("http://127.0.0.1:8080","../case")));
        check(ReportGenExtension.Pairing.parse(config("http://127.0.0.1:8080","auditoría")).project.equals("auditoría"),"Unicode project");
        check(ReportGenExtension.scalar("{\"project\":\"auditor\\u00eda\"}","project").equals("auditoría"),"Escaped Unicode");
        rejected(()->ReportGenExtension.scalar("{\"csrf\":\"a\",\"csrf\":\"b\"}","csrf"));
        String payload=ReportGenExtension.serialize(List.of(pair()),"reader\"\\\nrole");
        check(payload.contains("AP9B")&&payload.contains("Bearer test-secret")&&payload.contains("reader\\\"\\\\\\u000arole"),"Binary and JSON preservation");
        ContextMenuEvent event=proxy(ContextMenuEvent.class,m->{if(m.equals("selectedRequestResponses"))return List.of(pair());throw new AssertionError("Unexpected context access: "+m);});
        check(new ReportGenExtension().provideMenuItems(event).size()==1,"Selected-only menu");
        ContextMenuEvent empty=proxy(ContextMenuEvent.class,m->switch(m){case "selectedRequestResponses"->List.of();case "messageEditorRequestResponse"->Optional.empty();default->throw new AssertionError(m);});
        check(new ReportGenExtension().provideMenuItems(empty).isEmpty(),"No selection sends nothing");
        AtomicInteger requests=new AtomicInteger(),received=new AtomicInteger();
        HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/api/session",exchange->{
            requests.incrementAndGet();exchange.getResponseHeaders().add("Set-Cookie","session=test-local; Path=/; HttpOnly; SameSite=Strict");
            byte[] body="{\"csrf\":\"csrf-test-value\",\"workspace_id\":\"workspace0123456789\"}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        server.createContext("/api/projects/case/http-evidence/bridge",exchange->{
            requests.incrementAndGet();String value=new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);
            boolean valid=value.equals(payload)&&"csrf-test-value".equals(exchange.getRequestHeaders().getFirst("X-CSRF-Token"))
                &&"b".repeat(43).equals(exchange.getRequestHeaders().getFirst("X-Report-Gen-Pairing"))
                &&exchange.getRequestHeaders().getFirst("Cookie").contains("session=test-local");
            if(valid)received.incrementAndGet();byte[] body="{}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(valid?200:403,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        server.start();
        try{
            String origin="http://127.0.0.1:"+server.getAddress().getPort();
            String result=ReportGenExtension.send(ReportGenExtension.Pairing.parse(config(origin,"case")),payload,1);
            check(result.startsWith("1 pair")&&received.get()==1&&requests.get()==2,"Cookie/CSRF/paired local transport");
        }finally{server.stop(0);}
        System.out.println("PASS Montoya interface contract, selected-only serialization, loopback destination, Unicode pairing, cookie/CSRF transport; Burp runtime not exercised.");
    }
}

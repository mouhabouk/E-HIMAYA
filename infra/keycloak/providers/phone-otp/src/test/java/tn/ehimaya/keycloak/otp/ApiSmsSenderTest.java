package tn.ehimaya.keycloak.otp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class ApiSmsSenderTest {

    private static final String SECRET = "test-otp-sms-secret-0000000001";

    @Test
    void signatureMatchesTheApiScheme() {
        // Same value as app/modules/identity/internal.py signature(secret, "1700000000", body).
        String body = ApiSmsSender.body("+21622333444", "123456", "ar");
        assertEquals("{\"phone\":\"+21622333444\",\"code\":\"123456\",\"locale\":\"ar\"}", body);
        String sig = ApiSmsSender.signature(SECRET.getBytes(StandardCharsets.UTF_8), "1700000000", body);
        // Value printed by the Python side for the same secret, timestamp and body.
        assertEquals("sha256=ccfe515cab22fb4936108775784fcac9eb5d2be07f2cd5c6622e9038ee1b0854", sig);
    }

    @Test
    void postsSignedBodyAndReadsTheSimulationFlag() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        AtomicReference<String> signature = new AtomicReference<>();
        AtomicReference<String> received = new AtomicReference<>();
        server.createContext("/internal/auth/otp-sms", exchange -> {
            String timestamp = exchange.getRequestHeaders().getFirst("X-Timestamp");
            String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            received.set(body);
            signature.set(exchange.getRequestHeaders().getFirst("X-Signature")
                    .equals(ApiSmsSender.signature(SECRET.getBytes(StandardCharsets.UTF_8), timestamp, body))
                    ? "ok" : "bad");
            byte[] answer = "{\"sent\":true,\"simulated\":true}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, answer.length);
            exchange.getResponseBody().write(answer);
            exchange.close();
        });
        server.start();
        try {
            ApiSmsSender sender = new ApiSmsSender("http://127.0.0.1:" + server.getAddress().getPort() + "/", SECRET);
            SmsSender.Result result = sender.send("+21622333444", "654321", "fr");
            assertTrue(result.ok());
            assertTrue(result.simulated());
            assertEquals("ok", signature.get());
            assertTrue(received.get().contains("\"code\":\"654321\""));
        } finally {
            server.stop(0);
        }
    }

    @Test
    void refusedOrUnreachableIsNotOk() throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/internal/auth/otp-sms", exchange -> {
            exchange.sendResponseHeaders(502, -1);
            exchange.close();
        });
        server.start();
        int port = server.getAddress().getPort();
        try {
            assertFalse(new ApiSmsSender("http://127.0.0.1:" + port, SECRET).send("+21622333444", "1", "ar").ok());
        } finally {
            server.stop(0);
        }
        assertFalse(new ApiSmsSender("http://127.0.0.1:" + port, SECRET).send("+21622333444", "1", "ar").ok());
    }
}

package tn.ehimaya.keycloak.otp;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HexFormat;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.jboss.logging.Logger;

/**
 * Asks the e-Himaya API to send the code: {@code POST <api>/internal/auth/otp-sms}, signed with HMAC-SHA256
 * (X-Timestamp, X-Signature: sha256=hex of "timestamp.body"), the same scheme as the SMS gateway webhook. The API
 * renders the text in the user's language and uses the national SMS provider.
 */
public final class ApiSmsSender implements SmsSender {

    private static final Logger LOG = Logger.getLogger(ApiSmsSender.class);

    private final URI endpoint;
    private final byte[] secret;
    private final HttpClient client;

    public ApiSmsSender(String apiUrl, String secret) {
        this.endpoint = URI.create(apiUrl.replaceAll("/+$", "") + "/internal/auth/otp-sms");
        this.secret = secret.getBytes(StandardCharsets.UTF_8);
        this.client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    }

    static String signature(byte[] secret, String timestamp, String body) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            mac.update((timestamp + ".").getBytes(StandardCharsets.UTF_8));
            return "sha256=" + HexFormat.of().formatHex(mac.doFinal(body.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    static String body(String phone, String code, String locale) {
        // Every value is validated before (digits, +, two-letter locale): no JSON escaping is needed.
        return "{\"phone\":\"" + phone + "\",\"code\":\"" + code + "\",\"locale\":\"" + locale + "\"}";
    }

    @Override
    public Result send(String phone, String code, String locale) {
        String body = body(phone, code, locale);
        String timestamp = Long.toString(System.currentTimeMillis() / 1000);
        HttpRequest request = HttpRequest.newBuilder(endpoint)
                .timeout(Duration.ofSeconds(10))
                .header("Content-Type", "application/json")
                .header("X-Timestamp", timestamp)
                .header("X-Signature", signature(secret, timestamp, body))
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build();
        try {
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                LOG.warnf("ehimaya-phone-otp: the API refused the SMS (HTTP %d)", response.statusCode());
                return new Result(false, false);
            }
            return new Result(true, response.body().contains("\"simulated\":true"));
        } catch (Exception e) {
            LOG.warnf("ehimaya-phone-otp: the API is unreachable (%s)", e.getClass().getSimpleName());
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
            return new Result(false, false);
        }
    }
}

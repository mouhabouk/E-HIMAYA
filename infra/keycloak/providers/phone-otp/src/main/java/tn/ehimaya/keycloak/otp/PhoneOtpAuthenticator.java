package tn.ehimaya.keycloak.otp;

import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.Authenticator;
import org.keycloak.events.Errors;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.RealmModel;
import org.keycloak.models.UserModel;

/**
 * Direct-grant step of the public realm (client ehimaya-mobile): sign-in with a phone number and an SMS code.
 *
 * <ol>
 *   <li>{@code grant_type=password&phone=+216XXXXXXXX} (no {@code otp}): a code is sent by SMS and Keycloak answers
 *       400 {@code {"error":"otp_sent", "expires_in", "resend_after", "sms_simulated"}}.</li>
 *   <li>The same request with {@code otp=123456}: the right code signs the person in (the account is created on the
 *       first sign-in, user name = the number's digits, attributes {@code phone_number} and
 *       {@code phone_number_verified}); a wrong one answers 401 {@code invalid_grant} with {@code tries_left}.</li>
 * </ol>
 */
public final class PhoneOtpAuthenticator implements Authenticator {

    static final String ATTR_PHONE = "phone_number";
    static final String ATTR_PHONE_VERIFIED = "phone_number_verified";
    private static final Set<String> LOCALES = Set.of("ar", "fr", "en");

    private final SmsSender sms;

    PhoneOtpAuthenticator(SmsSender sms) {
        this.sms = sms;
    }

    private static Response json(int status, Map<String, Object> body) {
        StringBuilder out = new StringBuilder("{");
        for (Map.Entry<String, Object> entry : body.entrySet()) {
            if (out.length() > 1) {
                out.append(',');
            }
            out.append('"').append(entry.getKey()).append("\":");
            Object value = entry.getValue();
            if (value instanceof String text) {
                out.append('"').append(text.replace("\\", "\\\\").replace("\"", "\\\"")).append('"');
            } else {
                out.append(value);
            }
        }
        out.append('}');
        return Response.status(status).type(MediaType.APPLICATION_JSON_TYPE).entity(out.toString()).build();
    }

    private static Response error(int status, String error, String description) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("error", error);
        body.put("error_description", description);
        return json(status, body);
    }

    private static String locale(MultivaluedMap<String, String> form) {
        String raw = form.getFirst("ui_locales");
        if (raw == null) {
            raw = form.getFirst("locale");
        }
        String code = raw == null ? "ar" : raw.trim().toLowerCase();
        code = code.length() >= 2 ? code.substring(0, 2) : code;
        return LOCALES.contains(code) ? code : "ar";
    }

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        MultivaluedMap<String, String> form = context.getHttpRequest().getDecodedFormParameters();
        String phone = PhoneNumbers.normalize(form.getFirst("phone"));
        if (phone == null) {
            context.getEvent().error(Errors.INVALID_USER);
            context.failure(
                    AuthenticationFlowError.INVALID_USER,
                    error(400, "invalid_phone", "A Tunisian mobile number is expected (+216 and 8 digits)"));
            return;
        }
        OtpService otp = new OtpService(new KeycloakOtpStore(context.getSession()));
        long now = System.currentTimeMillis() / 1000;
        String code = form.getFirst("otp");
        if (code == null || code.isBlank()) {
            sendCode(context, otp, phone, locale(form), now);
        } else {
            checkCode(context, otp, phone, code.trim(), now);
        }
    }

    private void sendCode(AuthenticationFlowContext context, OtpService otp, String phone, String locale, long now) {
        OtpService.Issued issued = otp.issue(phone, now);
        switch (issued.status()) {
            case TOO_SOON -> {
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("error", "otp_too_soon");
                body.put("error_description", "Wait before asking for a new code");
                body.put("retry_after", OtpService.RESEND_GAP_S);
                context.challenge(json(429, body));
            }
            case HOURLY_LIMIT -> context.challenge(error(429, "otp_limit", "Too many codes for this number, try later"));
            case ISSUED -> {
                SmsSender.Result sent = sms.send(phone, issued.code(), locale);
                if (!sent.ok()) {
                    otp.discard(phone);
                    context.challenge(error(503, "sms_unavailable", "The SMS could not be sent, try again"));
                    return;
                }
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("error", "otp_sent");
                body.put("error_description", "A code was sent by SMS");
                body.put("expires_in", OtpService.CODE_TTL_S);
                body.put("resend_after", OtpService.RESEND_GAP_S);
                // SIMULATION: true while SMS go to notify-sim (development); the app then shows a [SIM] strip.
                body.put("sms_simulated", sent.simulated());
                context.challenge(json(400, body));
            }
        }
    }

    private void checkCode(AuthenticationFlowContext context, OtpService otp, String phone, String code, long now) {
        OtpService.Checked checked = otp.check(phone, code, now);
        switch (checked.status()) {
            case EXPIRED -> {
                context.getEvent().error(Errors.EXPIRED_CODE);
                context.failure(
                        AuthenticationFlowError.EXPIRED_CODE,
                        error(400, "otp_expired", "The code expired or was used up, ask for a new one"));
            }
            case WRONG -> {
                context.getEvent().error(Errors.INVALID_USER_CREDENTIALS);
                Map<String, Object> body = new LinkedHashMap<>();
                body.put("error", "invalid_grant");
                body.put("error_description", "Wrong code");
                body.put("tries_left", checked.triesLeft());
                context.failure(AuthenticationFlowError.INVALID_CREDENTIALS, json(401, body));
            }
            case OK -> signIn(context, phone);
        }
    }

    private void signIn(AuthenticationFlowContext context, String phone) {
        KeycloakSession session = context.getSession();
        RealmModel realm = context.getRealm();
        UserModel user = session.users()
                .searchForUserByUserAttributeStream(realm, ATTR_PHONE, phone)
                .findFirst()
                .orElseGet(() -> session.users().getUserByUsername(realm, PhoneNumbers.username(phone)));
        if (user == null) {
            // First sign-in: the account exists only once the number is proven. Default roles give "citizen".
            user = session.users().addUser(realm, null, PhoneNumbers.username(phone), true, false);
            user.setEnabled(true);
        }
        if (!user.isEnabled()) {
            context.getEvent().user(user).error(Errors.USER_DISABLED);
            context.failure(AuthenticationFlowError.USER_DISABLED, error(400, "invalid_grant", "Account disabled"));
            return;
        }
        user.setSingleAttribute(ATTR_PHONE, phone);
        user.setSingleAttribute(ATTR_PHONE_VERIFIED, "true");
        context.setUser(user);
        context.success();
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        authenticate(context);
    }

    @Override
    public boolean requiresUser() {
        return false;
    }

    @Override
    public boolean configuredFor(KeycloakSession session, RealmModel realm, UserModel user) {
        return true;
    }

    @Override
    public void setRequiredActions(KeycloakSession session, RealmModel realm, UserModel user) {}

    @Override
    public void close() {}
}

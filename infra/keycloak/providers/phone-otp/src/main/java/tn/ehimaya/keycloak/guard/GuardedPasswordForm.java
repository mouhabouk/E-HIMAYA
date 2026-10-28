package tn.ehimaya.keycloak.guard;

import jakarta.ws.rs.core.MultivaluedMap;
import jakarta.ws.rs.core.Response;
import java.util.Map;
import org.keycloak.authentication.AuthenticationFlowContext;
import org.keycloak.authentication.AuthenticationFlowError;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordForm;
import org.keycloak.forms.login.LoginFormsProvider;
import org.keycloak.models.AuthenticatorConfigModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.UserModel;
import org.keycloak.services.managers.AuthenticationManager;

/**
 * Keycloak's username and password form with a proof of work from the third failed attempt of a user name (phase
 * L2, item 8, docs/phase-l/design-l2.md §3). Below the threshold it is the built-in form, unchanged. From it, the
 * page carries a challenge that the browser solves by itself (themes/ehimaya/login/resources/js/pow.js), and an
 * attempt without a valid solution is refused before the password is checked. The realm's temporary lockout (10
 * failures) still applies on top.
 */
public class GuardedPasswordForm extends UsernamePasswordForm {

    static final String SALT_NOTE = "ehimaya.pow.salt";
    static final String SOLUTION_FIELD = "pow_solution";
    static final String PROOF_REQUIRED = "ehimayaProofRequired";
    static final String CONFIG_AFTER = "ehimaya.guard.after";
    static final String CONFIG_BITS = "ehimaya.guard.bits";
    static final int DEFAULT_AFTER = 3;
    static final int DEFAULT_BITS = 18;

    /** The context of the request being handled (one instance per request: see the factory). */
    private AuthenticationFlowContext current;
    /** Set while the built-in form checks the password: if it fails, the form it renders already counts it. */
    private boolean pendingFailure;

    public GuardedPasswordForm(KeycloakSession session) {
        super(session);
    }

    @Override
    public void authenticate(AuthenticationFlowContext context) {
        current = context;
        super.authenticate(context);
    }

    @Override
    public void action(AuthenticationFlowContext context) {
        current = context;
        super.action(context);
    }

    @Override
    protected boolean validateForm(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        current = context;
        LoginGuard guard = guard(context);
        String username = usernameOf(context, formData);
        if (guard.proofRequired(username, false)) {
            String salt = context.getAuthenticationSession().getAuthNote(SALT_NOTE);
            context.getAuthenticationSession().removeAuthNote(SALT_NOTE);
            if (!ProofOfWork.verify(salt, bits(context), formData.getFirst(SOLUTION_FIELD))) {
                context.getEvent().detail("ehimaya_guard", "proof_missing");
                Response challenge = challenge(context, PROOF_REQUIRED, null);
                context.failureChallenge(AuthenticationFlowError.INVALID_CREDENTIALS, challenge);
                return false;
            }
        }
        pendingFailure = true;
        boolean ok;
        try {
            ok = super.validateForm(context, formData);
        } finally {
            pendingFailure = false;
        }
        if (ok) {
            guard.succeeded(username);
        } else {
            guard.failed(username);
        }
        return ok;
    }

    @Override
    protected Response createLoginForm(LoginFormsProvider form) {
        AuthenticationFlowContext context = current;
        if (context != null) {
            String username = usernameOf(context, typed(context));
            if (guard(context).proofRequired(username, pendingFailure)) {
                String salt = ProofOfWork.newSalt();
                context.getAuthenticationSession().setAuthNote(SALT_NOTE, salt);
                form.setAttribute("ehimayaPow", Map.of("salt", salt, "bits", bits(context)));
            }
        }
        return super.createLoginForm(form);
    }

    private static String usernameOf(AuthenticationFlowContext context, MultivaluedMap<String, String> formData) {
        UserModel user = context.getUser();
        if (user != null) return user.getUsername();
        String typed = formData == null ? null : formData.getFirst(AuthenticationManager.FORM_USERNAME);
        if (typed != null && !typed.isBlank()) return typed;
        return context.getAuthenticationSession().getAuthNote(ATTEMPTED_USERNAME);
    }

    /** The fields of the form being answered, or null on the first display of the page. */
    private static MultivaluedMap<String, String> typed(AuthenticationFlowContext context) {
        if (!"POST".equals(context.getHttpRequest().getHttpMethod())) return null;
        return context.getHttpRequest().getDecodedFormParameters();
    }

    private static LoginGuard guard(AuthenticationFlowContext context) {
        return new LoginGuard(new KeycloakGuardStore(context.getSession()), context.getRealm().getId(), after(context));
    }

    static int after(AuthenticationFlowContext context) {
        return setting(context.getAuthenticatorConfig(), CONFIG_AFTER, DEFAULT_AFTER, 1, 100);
    }

    static int bits(AuthenticationFlowContext context) {
        return setting(context.getAuthenticatorConfig(), CONFIG_BITS, DEFAULT_BITS, 8, ProofOfWork.MAX_BITS);
    }

    static int setting(AuthenticatorConfigModel config, String key, int fallback, int min, int max) {
        if (config == null || config.getConfig() == null) return fallback;
        try {
            int value = Integer.parseInt(config.getConfig().getOrDefault(key, Integer.toString(fallback)).trim());
            return Math.max(min, Math.min(max, value));
        } catch (NumberFormatException e) {
            return fallback;
        }
    }
}

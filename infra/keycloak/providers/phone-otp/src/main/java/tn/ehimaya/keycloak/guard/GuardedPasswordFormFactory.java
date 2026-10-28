package tn.ehimaya.keycloak.guard;

import java.util.ArrayList;
import java.util.List;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.authenticators.browser.UsernamePasswordFormFactory;
import org.keycloak.models.KeycloakSession;
import org.keycloak.provider.ProviderConfigProperty;

/**
 * Registers {@link GuardedPasswordForm} as {@code ehimaya-guarded-password-form}: the browser flows of both realms use
 * it in place of {@code auth-username-password-form}. It keeps the built-in form's settings (the {@code amr}
 * reference of the staff realm) and adds the threshold and the difficulty.
 */
public class GuardedPasswordFormFactory extends UsernamePasswordFormFactory {

    public static final String PROVIDER_ID = "ehimaya-guarded-password-form";

    @Override
    public Authenticator create(KeycloakSession session) {
        // One instance per request: the form keeps the request's context between validation and rendering.
        return new GuardedPasswordForm(session);
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayType() {
        return "e-Himaya username password form (proof of work after failures)";
    }

    @Override
    public String getHelpText() {
        return "Username and password; from the given number of failed attempts of a user name, the page solves a"
                + " proof of work before the password is checked.";
    }

    @Override
    public boolean isConfigurable() {
        return true;
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        List<ProviderConfigProperty> properties = new ArrayList<>(super.getConfigProperties());
        properties.add(new ProviderConfigProperty(
                GuardedPasswordForm.CONFIG_AFTER,
                "Proof of work after",
                "Failed attempts of a user name (15 minutes) after which the proof of work is required.",
                ProviderConfigProperty.STRING_TYPE,
                Integer.toString(GuardedPasswordForm.DEFAULT_AFTER)));
        properties.add(new ProviderConfigProperty(
                GuardedPasswordForm.CONFIG_BITS,
                "Difficulty (bits)",
                "Leading zero bits of the SHA-256 the browser must find (8 to 24; 18 is about a second on a phone).",
                ProviderConfigProperty.STRING_TYPE,
                Integer.toString(GuardedPasswordForm.DEFAULT_BITS)));
        return properties;
    }
}

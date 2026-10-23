package tn.ehimaya.keycloak.otp;

import java.util.List;
import org.jboss.logging.Logger;
import org.keycloak.Config;
import org.keycloak.authentication.Authenticator;
import org.keycloak.authentication.AuthenticatorFactory;
import org.keycloak.models.AuthenticationExecutionModel;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;
import org.keycloak.provider.ProviderConfigProperty;

/**
 * Registers {@code ehimaya-phone-otp}. Settings come from the container environment:
 * {@code EHIMAYA_API_INTERNAL_URL} (default http://api:8000) and {@code OTP_SMS_SECRET} (shared with the API).
 * Without the secret the provider answers {@code sms_unavailable}: no code is ever issued that cannot be sent.
 */
public final class PhoneOtpAuthenticatorFactory implements AuthenticatorFactory {

    public static final String ID = "ehimaya-phone-otp";
    private static final Logger LOG = Logger.getLogger(PhoneOtpAuthenticatorFactory.class);

    private SmsSender sender;

    @Override
    public void init(Config.Scope config) {
        String url = System.getenv().getOrDefault("EHIMAYA_API_INTERNAL_URL", "http://api:8000");
        String secret = System.getenv("OTP_SMS_SECRET");
        if (secret == null || secret.length() < 24) {
            LOG.warn("ehimaya-phone-otp: OTP_SMS_SECRET is not set (24 characters or more), phone sign-in is off");
            sender = (phone, code, locale) -> new SmsSender.Result(false, false);
        } else {
            sender = new ApiSmsSender(url, secret);
        }
    }

    @Override
    public Authenticator create(KeycloakSession session) {
        return new PhoneOtpAuthenticator(sender);
    }

    @Override
    public String getId() {
        return ID;
    }

    @Override
    public String getDisplayType() {
        return "e-Himaya phone number and SMS code";
    }

    @Override
    public String getReferenceCategory() {
        return "otp";
    }

    @Override
    public boolean isConfigurable() {
        return false;
    }

    @Override
    public AuthenticationExecutionModel.Requirement[] getRequirementChoices() {
        return new AuthenticationExecutionModel.Requirement[] {AuthenticationExecutionModel.Requirement.REQUIRED};
    }

    @Override
    public boolean isUserSetupAllowed() {
        return false;
    }

    @Override
    public String getHelpText() {
        return "Direct grant: sends a 6-digit code by SMS to a Tunisian mobile number, then signs the person in.";
    }

    @Override
    public List<ProviderConfigProperty> getConfigProperties() {
        return List.of();
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {}

    @Override
    public void close() {}
}

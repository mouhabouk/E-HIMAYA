package tn.ehimaya.keycloak.otp;

import java.util.Map;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.SingleUseObjectProvider;

/** {@link OtpStore} on Keycloak's single-use object store (shared by the cluster, entries expire by themselves). */
final class KeycloakOtpStore implements OtpStore {

    private final SingleUseObjectProvider objects;

    KeycloakOtpStore(KeycloakSession session) {
        this.objects = session.singleUseObjects();
    }

    @Override
    public void put(String key, long lifespanSeconds, Map<String, String> notes) {
        objects.put(key, Math.max(1, lifespanSeconds), notes);
    }

    @Override
    public Map<String, String> get(String key) {
        return objects.get(key);
    }

    @Override
    public void remove(String key) {
        objects.remove(key);
    }

    @Override
    public boolean putIfAbsent(String key, long lifespanSeconds) {
        return objects.putIfAbsent(key, lifespanSeconds);
    }
}

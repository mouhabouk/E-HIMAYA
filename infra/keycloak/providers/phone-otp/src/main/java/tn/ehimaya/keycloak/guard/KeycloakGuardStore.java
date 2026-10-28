package tn.ehimaya.keycloak.guard;

import java.util.Map;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.SingleUseObjectProvider;

/** {@link GuardStore} on Keycloak's single-use object store (shared by the cluster, entries expire by themselves). */
final class KeycloakGuardStore implements GuardStore {

    private final SingleUseObjectProvider objects;

    KeycloakGuardStore(KeycloakSession session) {
        this.objects = session.singleUseObjects();
    }

    @Override
    public Map<String, String> get(String key) {
        return objects.get(key);
    }

    @Override
    public void put(String key, long lifespanSeconds, Map<String, String> notes) {
        objects.put(key, Math.max(1, lifespanSeconds), notes);
    }

    @Override
    public void remove(String key) {
        objects.remove(key);
    }
}

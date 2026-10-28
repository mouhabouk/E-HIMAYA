package tn.ehimaya.keycloak.guard;

import java.util.HashMap;
import java.util.Map;

/** {@link GuardStore} in memory, with the lifespans recorded so the tests can check them. */
final class MemoryGuardStore implements GuardStore {

    final Map<String, Map<String, String>> entries = new HashMap<>();
    final Map<String, Long> lifespans = new HashMap<>();

    @Override
    public Map<String, String> get(String key) {
        return entries.get(key);
    }

    @Override
    public void put(String key, long lifespanSeconds, Map<String, String> notes) {
        entries.put(key, Map.copyOf(notes));
        lifespans.put(key, lifespanSeconds);
    }

    @Override
    public void remove(String key) {
        entries.remove(key);
        lifespans.remove(key);
    }
}

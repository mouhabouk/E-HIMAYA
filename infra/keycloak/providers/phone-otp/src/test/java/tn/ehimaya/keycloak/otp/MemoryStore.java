package tn.ehimaya.keycloak.otp;

import java.util.HashMap;
import java.util.Map;

/** In-memory {@link OtpStore} with a settable clock, for the tests. */
final class MemoryStore implements OtpStore {

    private record Entry(long expires, Map<String, String> notes) {}

    private final Map<String, Entry> entries = new HashMap<>();
    long now = 1_000_000;

    private Entry live(String key) {
        Entry entry = entries.get(key);
        if (entry != null && entry.expires() <= now) {
            entries.remove(key);
            return null;
        }
        return entry;
    }

    @Override
    public void put(String key, long lifespanSeconds, Map<String, String> notes) {
        entries.put(key, new Entry(now + lifespanSeconds, Map.copyOf(notes)));
    }

    @Override
    public Map<String, String> get(String key) {
        Entry entry = live(key);
        return entry == null ? null : entry.notes();
    }

    @Override
    public void remove(String key) {
        entries.remove(key);
    }

    @Override
    public boolean putIfAbsent(String key, long lifespanSeconds) {
        if (live(key) != null) {
            return false;
        }
        put(key, lifespanSeconds, Map.of());
        return true;
    }
}

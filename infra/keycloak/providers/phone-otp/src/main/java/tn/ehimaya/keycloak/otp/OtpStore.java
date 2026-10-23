package tn.ehimaya.keycloak.otp;

import java.util.Map;

/**
 * The few operations of Keycloak's single-use object store the service needs (cluster-wide, entries expire on
 * their own). Kept as an interface so the rules can be tested without a Keycloak server.
 */
public interface OtpStore {

    void put(String key, long lifespanSeconds, Map<String, String> notes);

    Map<String, String> get(String key);

    void remove(String key);

    /** True when the key was absent and is now stored for {@code lifespanSeconds}. */
    boolean putIfAbsent(String key, long lifespanSeconds);
}

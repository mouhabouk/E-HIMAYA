package tn.ehimaya.keycloak.guard;

import java.util.Map;

/** The few operations of Keycloak's single-use object store that the login guard needs (a memory one in tests). */
interface GuardStore {

    Map<String, String> get(String key);

    void put(String key, long lifespanSeconds, Map<String, String> notes);

    void remove(String key);
}

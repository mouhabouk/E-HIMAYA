package tn.ehimaya.keycloak.guard;

import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;

/**
 * Failed sign-ins per user name (phase L2, item 8): from the {@code after}-th failure in the window, the next attempt
 * must carry a solved proof of work before the password is even checked. The count is kept for every name typed,
 * known or not, so the challenge never tells whether an account exists. Only a hash of the name is stored.
 */
final class LoginGuard {

    /** The window of the count: the same 15 minutes as the realm's longest temporary lockout. */
    static final long WINDOW_SECONDS = 900;
    private static final String PREFIX = "ehimaya-guard:";

    private final GuardStore store;
    private final String realmId;
    private final int after;

    LoginGuard(GuardStore store, String realmId, int after) {
        this.store = store;
        this.realmId = realmId;
        this.after = after;
    }

    /** True when the next attempt of this name needs a proof ({@code pending} counts a failure being recorded). */
    boolean proofRequired(String username, boolean pending) {
        if (username == null || username.isBlank()) return false;
        return failures(username) + (pending ? 1 : 0) >= after;
    }

    int failures(String username) {
        Map<String, String> notes = store.get(key(username));
        if (notes == null) return 0;
        try {
            return Integer.parseInt(notes.getOrDefault("n", "0"));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    void failed(String username) {
        if (username == null || username.isBlank()) return;
        store.put(key(username), WINDOW_SECONDS, Map.of("n", Integer.toString(failures(username) + 1)));
    }

    void succeeded(String username) {
        if (username == null || username.isBlank()) return;
        store.remove(key(username));
    }

    private String key(String username) {
        String name = username.trim().toLowerCase(Locale.ROOT);
        return PREFIX + realmId + ":" + HexFormat.of().formatHex(ProofOfWork.sha256(name));
    }
}

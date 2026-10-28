package tn.ehimaya.keycloak.guard;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class LoginGuardTest {

    private MemoryGuardStore store;
    private LoginGuard guard;

    @BeforeEach
    void setUp() {
        store = new MemoryGuardStore();
        guard = new LoginGuard(store, "realm-1", 3);
    }

    @Test
    void asksForTheProofFromTheThirdFailure() {
        assertFalse(guard.proofRequired("salma", false));
        guard.failed("salma");
        guard.failed("salma");
        assertFalse(guard.proofRequired("salma", false));
        // The form shown after the third failure already carries the challenge.
        assertTrue(guard.proofRequired("salma", true));
        guard.failed("salma");
        assertTrue(guard.proofRequired("salma", false));
        assertEquals(3, guard.failures("salma"));
    }

    @Test
    void countsPerNameWhateverTheCaseAndForgetsOnSuccess() {
        guard.failed("Salma ");
        guard.failed("SALMA");
        guard.failed("salma");
        assertTrue(guard.proofRequired("salma", false));
        assertFalse(guard.proofRequired("amine", false));
        guard.succeeded("salma");
        assertFalse(guard.proofRequired("salma", false));
    }

    @Test
    void keepsOnlyAHashOfTheNameForFifteenMinutesPerRealm() {
        guard.failed("salma@example.tn");
        String key = store.entries.keySet().iterator().next();
        assertTrue(key.startsWith("ehimaya-guard:realm-1:"));
        assertFalse(key.contains("salma"));
        assertEquals(LoginGuard.WINDOW_SECONDS, store.lifespans.get(key));
        assertFalse(new LoginGuard(store, "realm-2", 1).proofRequired("salma@example.tn", false));
    }

    @Test
    void ignoresAnEmptyName() {
        guard.failed("");
        guard.failed(null);
        assertTrue(store.entries.isEmpty());
        assertFalse(guard.proofRequired(" ", true));
    }
}

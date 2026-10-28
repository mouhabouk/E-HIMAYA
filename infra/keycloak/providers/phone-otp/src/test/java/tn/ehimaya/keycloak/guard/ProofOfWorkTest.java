package tn.ehimaya.keycloak.guard;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ProofOfWorkTest {

    @Test
    void aSolutionIsAcceptedAndCheckedAgainstItsSalt() {
        String salt = ProofOfWork.newSalt();
        String nonce = ProofOfWork.solve(salt, 12);
        assertTrue(ProofOfWork.verify(salt, 12, nonce));
        assertFalse(ProofOfWork.verify(salt, 40, nonce)); // 2^-28 chance of a false alarm
        assertNotEquals(salt, ProofOfWork.newSalt());
        assertEquals(32, salt.length());
    }

    @Test
    void refusesWhatIsNotADecimalNonce() {
        String salt = "00ff";
        assertFalse(ProofOfWork.verify(salt, 0, null));
        assertFalse(ProofOfWork.verify(salt, 0, ""));
        assertFalse(ProofOfWork.verify(salt, 0, "12a"));
        assertFalse(ProofOfWork.verify(salt, 0, "١٢")); // Arabic-Indic digits are not accepted
        assertFalse(ProofOfWork.verify(salt, 0, "1234567890123"));
        assertFalse(ProofOfWork.verify(null, 0, "1"));
        assertTrue(ProofOfWork.verify(salt, 0, "1"));
    }

    @Test
    void countsLeadingZeroBits() {
        assertEquals(0, ProofOfWork.leadingZeroBits(new byte[] {(byte) 0x80, 0}));
        assertEquals(7, ProofOfWork.leadingZeroBits(new byte[] {1, 0}));
        assertEquals(12, ProofOfWork.leadingZeroBits(new byte[] {0, 0x08}));
        assertEquals(16, ProofOfWork.leadingZeroBits(new byte[] {0, 0}));
    }

    @Test
    void matchesTheBrowserSolver() {
        // The same vector is checked by the JavaScript solver's test (themes/ehimaya/login/resources/js/pow.js).
        assertEquals(
                "6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
                java.util.HexFormat.of().formatHex(ProofOfWork.sha256("1")));
    }
}

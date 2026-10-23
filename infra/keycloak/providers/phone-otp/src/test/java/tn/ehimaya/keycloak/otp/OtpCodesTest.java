package tn.ehimaya.keycloak.otp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.Test;

class OtpCodesTest {

    @Test
    void codesAreSixDigitsAndVary() {
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < 200; i++) {
            String code = OtpCodes.newCode();
            assertTrue(code.matches("\\d{6}"), code);
            seen.add(code);
        }
        assertTrue(seen.size() > 190);
    }

    @Test
    void saltChangesTheHash() {
        String a = OtpCodes.newSalt();
        String b = OtpCodes.newSalt();
        assertNotEquals(a, b);
        assertNotEquals(OtpCodes.hash("123456", a), OtpCodes.hash("123456", b));
        assertEquals(OtpCodes.hash("123456", a), OtpCodes.hash("123456", a));
    }

    @Test
    void matchesOnlyTheRightCode() {
        String salt = OtpCodes.newSalt();
        String hash = OtpCodes.hash("482913", salt);
        assertTrue(OtpCodes.matches("482913", salt, hash));
        assertFalse(OtpCodes.matches("482914", salt, hash));
        assertFalse(OtpCodes.matches(null, salt, hash));
        assertFalse(OtpCodes.matches("48291", salt, hash));
        assertFalse(OtpCodes.matches("48291a", salt, hash));
    }
}

package tn.ehimaya.keycloak.otp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class PhoneNumbersTest {

    @ParameterizedTest
    @ValueSource(strings = {"+21622333444", "22333444", "22 333 444", "0021622333444", "21622333444", "+216 22-333-444"})
    void acceptsTunisianMobiles(String raw) {
        assertEquals("+21622333444", PhoneNumbers.normalize(raw));
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "+21612333444", "+21672333444", "2233344", "223334445", "+33612345678", "abcdefgh"})
    void refusesTheRest(String raw) {
        assertNull(PhoneNumbers.normalize(raw));
    }

    @ParameterizedTest
    @ValueSource(strings = {"20000000", "30000000", "40000000", "50000000", "90000000"})
    void everyMobilePrefix(String raw) {
        assertEquals("+216" + raw, PhoneNumbers.normalize(raw));
    }

    @org.junit.jupiter.api.Test
    void nullAndUsername() {
        assertNull(PhoneNumbers.normalize(null));
        assertEquals("21622333444", PhoneNumbers.username("+21622333444"));
    }
}

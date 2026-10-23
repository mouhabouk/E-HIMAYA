package tn.ehimaya.keycloak.otp;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class OtpServiceTest {

    private static final String PHONE = "+21622333444";
    private MemoryStore store;
    private OtpService otp;

    @BeforeEach
    void setUp() {
        store = new MemoryStore();
        otp = new OtpService(store);
    }

    private String wrong(String code) {
        return code.equals("000000") ? "111111" : "000000";
    }

    @Test
    void issuesSixDigitsAndAcceptsThemOnce() {
        OtpService.Issued issued = otp.issue(PHONE, store.now);
        assertEquals(OtpService.IssueStatus.ISSUED, issued.status());
        assertTrue(issued.code().matches("\\d{6}"));
        assertEquals(OtpService.CheckStatus.OK, otp.check(PHONE, issued.code(), store.now).status());
        // Used: the same code never works twice.
        assertEquals(OtpService.CheckStatus.EXPIRED, otp.check(PHONE, issued.code(), store.now).status());
    }

    @Test
    void keepsOnlyASaltedHash() {
        OtpService.Issued issued = otp.issue(PHONE, store.now);
        var notes = store.get("ehimaya-otp:code:" + PHONE);
        assertTrue(notes.values().stream().noneMatch(v -> v.contains(issued.code())));
        assertNotEquals(OtpCodes.hash(issued.code(), OtpCodes.newSalt()), notes.get("hash"));
    }

    @Test
    void threeTriesThenTheCodeIsGone() {
        String code = otp.issue(PHONE, store.now).code();
        assertEquals(2, otp.check(PHONE, wrong(code), store.now).triesLeft());
        assertEquals(1, otp.check(PHONE, wrong(code), store.now).triesLeft());
        OtpService.Checked last = otp.check(PHONE, wrong(code), store.now);
        assertEquals(OtpService.CheckStatus.WRONG, last.status());
        assertEquals(0, last.triesLeft());
        assertEquals(OtpService.CheckStatus.EXPIRED, otp.check(PHONE, code, store.now).status());
    }

    @Test
    void rightCodeAfterOneWrongTry() {
        String code = otp.issue(PHONE, store.now).code();
        otp.check(PHONE, wrong(code), store.now);
        assertEquals(OtpService.CheckStatus.OK, otp.check(PHONE, code, store.now).status());
    }

    @Test
    void expiresAfterFiveMinutes() {
        String code = otp.issue(PHONE, store.now).code();
        store.now += OtpService.CODE_TTL_S;
        assertEquals(OtpService.CheckStatus.EXPIRED, otp.check(PHONE, code, store.now).status());
    }

    @Test
    void wrongTryKeepsTheOriginalExpiry() {
        String code = otp.issue(PHONE, store.now).code();
        store.now += 200;
        otp.check(PHONE, wrong(code), store.now);
        store.now += 100;
        assertEquals(OtpService.CheckStatus.EXPIRED, otp.check(PHONE, code, store.now).status());
    }

    @Test
    void oneCodePerMinute() {
        otp.issue(PHONE, store.now);
        assertEquals(OtpService.IssueStatus.TOO_SOON, otp.issue(PHONE, store.now + 30).status());
        store.now += OtpService.RESEND_GAP_S;
        assertEquals(OtpService.IssueStatus.ISSUED, otp.issue(PHONE, store.now).status());
        // Another number is not slowed down.
        assertEquals(OtpService.IssueStatus.ISSUED, otp.issue("+21655000111", store.now).status());
    }

    @Test
    void newCodeReplacesTheOldOne() {
        String first = otp.issue(PHONE, store.now).code();
        store.now += OtpService.RESEND_GAP_S;
        String second = otp.issue(PHONE, store.now).code();
        if (!first.equals(second)) {
            assertEquals(OtpService.CheckStatus.WRONG, otp.check(PHONE, first, store.now).status());
        }
        assertEquals(OtpService.CheckStatus.OK, otp.check(PHONE, second, store.now).status());
    }

    @Test
    void fiveCodesPerHour() {
        for (int i = 0; i < OtpService.CODES_PER_HOUR; i++) {
            assertEquals(OtpService.IssueStatus.ISSUED, otp.issue(PHONE, store.now).status());
            store.now += OtpService.RESEND_GAP_S;
        }
        assertEquals(OtpService.IssueStatus.HOURLY_LIMIT, otp.issue(PHONE, store.now).status());
        store.now += 3600;
        assertEquals(OtpService.IssueStatus.ISSUED, otp.issue(PHONE, store.now).status());
    }

    @Test
    void discardAllowsAnImmediateRetry() {
        otp.issue(PHONE, store.now);
        otp.discard(PHONE);
        assertNull(store.get("ehimaya-otp:code:" + PHONE));
        assertEquals(OtpService.IssueStatus.ISSUED, otp.issue(PHONE, store.now).status());
    }

    @Test
    void noCodeMeansExpired() {
        assertEquals(OtpService.CheckStatus.EXPIRED, otp.check(PHONE, "123456", store.now).status());
    }
}

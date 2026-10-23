package tn.ehimaya.keycloak.otp;

import java.util.HashMap;
import java.util.Map;

/**
 * Rules of the SMS sign-in code (docs/phase-a/design.md §2.2), independent of Keycloak:
 * <ul>
 *   <li>a 6-digit code, valid {@link #CODE_TTL_S} seconds, {@link #MAX_TRIES} tries;</li>
 *   <li>one code per number every {@link #RESEND_GAP_S} seconds, at most {@link #CODES_PER_HOUR} per hour;</li>
 *   <li>only a salted hash is kept, and no account is created before the right code is given.</li>
 * </ul>
 */
public final class OtpService {

    public static final long CODE_TTL_S = 300;
    public static final int MAX_TRIES = 3;
    public static final long RESEND_GAP_S = 60;
    public static final int CODES_PER_HOUR = 5;

    private static final String PREFIX = "ehimaya-otp:";

    public enum IssueStatus { ISSUED, TOO_SOON, HOURLY_LIMIT }

    public record Issued(IssueStatus status, String code) {}

    public enum CheckStatus { OK, WRONG, EXPIRED }

    public record Checked(CheckStatus status, int triesLeft) {}

    private final OtpStore store;

    public OtpService(OtpStore store) {
        this.store = store;
    }

    private static String codeKey(String phone) {
        return PREFIX + "code:" + phone;
    }

    /** A new code for {@code phone}, unless the number asked too soon or too often. */
    public Issued issue(String phone, long nowSeconds) {
        if (!store.putIfAbsent(PREFIX + "gap:" + phone, RESEND_GAP_S)) {
            return new Issued(IssueStatus.TOO_SOON, null);
        }
        boolean slot = false;
        for (int i = 0; i < CODES_PER_HOUR && !slot; i++) {
            slot = store.putIfAbsent(PREFIX + "hour:" + phone + ":" + i, 3600);
        }
        if (!slot) {
            return new Issued(IssueStatus.HOURLY_LIMIT, null);
        }
        String code = OtpCodes.newCode();
        String salt = OtpCodes.newSalt();
        Map<String, String> notes = new HashMap<>();
        notes.put("hash", OtpCodes.hash(code, salt));
        notes.put("salt", salt);
        notes.put("tries", Integer.toString(MAX_TRIES));
        notes.put("expires", Long.toString(nowSeconds + CODE_TTL_S));
        store.put(codeKey(phone), CODE_TTL_S, notes);
        return new Issued(IssueStatus.ISSUED, code);
    }

    /** Forget the code and the resend delay (the SMS could not be sent: the person may try again at once). */
    public void discard(String phone) {
        store.remove(codeKey(phone));
        store.remove(PREFIX + "gap:" + phone);
    }

    public Checked check(String phone, String code, long nowSeconds) {
        Map<String, String> notes = store.get(codeKey(phone));
        if (notes == null) {
            return new Checked(CheckStatus.EXPIRED, 0);
        }
        long expires = Long.parseLong(notes.get("expires"));
        int tries = Integer.parseInt(notes.get("tries"));
        if (nowSeconds >= expires || tries <= 0) {
            store.remove(codeKey(phone));
            return new Checked(CheckStatus.EXPIRED, 0);
        }
        if (OtpCodes.matches(code, notes.get("salt"), notes.get("hash"))) {
            store.remove(codeKey(phone));
            return new Checked(CheckStatus.OK, tries);
        }
        int left = tries - 1;
        if (left <= 0) {
            store.remove(codeKey(phone));
            return new Checked(CheckStatus.WRONG, 0);
        }
        Map<String, String> updated = new HashMap<>(notes);
        updated.put("tries", Integer.toString(left));
        store.put(codeKey(phone), expires - nowSeconds, updated);
        return new Checked(CheckStatus.WRONG, left);
    }
}

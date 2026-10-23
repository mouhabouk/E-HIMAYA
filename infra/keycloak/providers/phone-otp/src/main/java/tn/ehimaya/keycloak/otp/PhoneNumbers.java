package tn.ehimaya.keycloak.otp;

import java.util.regex.Pattern;

/** Tunisian mobile numbers: +216 then 8 digits whose first digit is 2, 3, 4, 5 or 9. */
public final class PhoneNumbers {

    private static final Pattern MOBILE = Pattern.compile("[23459]\\d{7}");

    private PhoneNumbers() {}

    /** The number as +216XXXXXXXX, or null when it is not a Tunisian mobile number. */
    public static String normalize(String raw) {
        if (raw == null) {
            return null;
        }
        String digits = raw.replaceAll("[\\s.\\-()]", "");
        if (digits.startsWith("+216")) {
            digits = digits.substring(4);
        } else if (digits.startsWith("00216")) {
            digits = digits.substring(5);
        } else if (digits.startsWith("216") && digits.length() == 11) {
            digits = digits.substring(3);
        }
        return MOBILE.matcher(digits).matches() ? "+216" + digits : null;
    }

    /** Keycloak user name of a phone account: the digits without "+", e.g. 21622333444. */
    public static String username(String normalized) {
        return normalized.substring(1);
    }
}

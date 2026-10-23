package tn.ehimaya.keycloak.otp;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.Base64;

/** Random 6-digit codes, kept only as a salted SHA-256 and compared in constant time. */
public final class OtpCodes {

    private static final SecureRandom RANDOM = new SecureRandom();

    private OtpCodes() {}

    public static String newCode() {
        return String.format("%06d", RANDOM.nextInt(1_000_000));
    }

    public static String newSalt() {
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        return Base64.getEncoder().encodeToString(salt);
    }

    public static String hash(String code, String salt) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(Base64.getDecoder().decode(salt));
            return Base64.getEncoder().encodeToString(digest.digest(code.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    public static boolean matches(String code, String salt, String expectedHash) {
        if (code == null || !code.matches("\\d{6}")) {
            return false;
        }
        return MessageDigest.isEqual(
                hash(code, salt).getBytes(StandardCharsets.UTF_8), expectedHash.getBytes(StandardCharsets.UTF_8));
    }
}

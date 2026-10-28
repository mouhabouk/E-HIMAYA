package tn.ehimaya.keycloak.guard;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.HexFormat;

/**
 * Self-hosted proof of work (phase L2, item 8, docs/phase-l/design-l2.md §3), in the manner of ALTCHA: the server
 * gives a random salt and a difficulty; the browser looks for a number {@code n} such that SHA-256("salt:n") starts
 * with {@code bits} zero bits, about 2^bits tries (a second or so on a phone at 18 bits). Nothing goes to a third
 * party and nothing is asked of the person: the page solves it by itself, with a status line for screen readers.
 */
public final class ProofOfWork {

    /** Upper bound of the difficulty: 2^24 hashes is already several seconds on a modest phone. */
    public static final int MAX_BITS = 24;
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final int MAX_NONCE_LENGTH = 12;

    private ProofOfWork() {}

    /** A fresh salt: 16 random bytes in hexadecimal. */
    public static String newSalt() {
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        return HexFormat.of().formatHex(salt);
    }

    /** True when {@code nonce} (decimal digits) solves the challenge {@code salt} at {@code bits}. */
    public static boolean verify(String salt, int bits, String nonce) {
        if (salt == null || salt.isEmpty() || nonce == null || nonce.isEmpty() || nonce.length() > MAX_NONCE_LENGTH) {
            return false;
        }
        for (int i = 0; i < nonce.length(); i++) {
            char c = nonce.charAt(i);
            if (c < '0' || c > '9') return false;
        }
        return leadingZeroBits(sha256(salt + ":" + nonce)) >= bits;
    }

    /** Finds a solution (the browser does this in JavaScript; here for the tests and the CI check). */
    public static String solve(String salt, int bits) {
        for (long n = 0; ; n++) {
            String nonce = Long.toString(n);
            if (leadingZeroBits(sha256(salt + ":" + nonce)) >= bits) return nonce;
        }
    }

    static int leadingZeroBits(byte[] hash) {
        int bits = 0;
        for (byte b : hash) {
            if (b == 0) {
                bits += 8;
                continue;
            }
            return bits + Integer.numberOfLeadingZeros(b & 0xff) - 24;
        }
        return bits;
    }

    static byte[] sha256(String text) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is part of every Java runtime", e);
        }
    }
}

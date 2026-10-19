import { describe, expect, it } from "vitest";
import { Sha256, sameHash, sha256Hex, toHex } from "./sha256";

const enc = (s: string) => new TextEncoder().encode(s);

describe("incremental SHA-256", () => {
  it("matches the FIPS 180-4 test vectors", () => {
    expect(toHex(new Sha256().digest())).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(toHex(new Sha256().update(enc("abc")).digest())).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    expect(toHex(new Sha256().update(enc("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")).digest())).toBe(
      "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
    );
  });

  it("gives the same digest whatever the chunking", () => {
    const data = Uint8Array.from({ length: 1000 }, (_, i) => (i * 31) % 256);
    const whole = toHex(new Sha256().update(data).digest());
    const h = new Sha256();
    for (let i = 0; i < data.length; i += 7) h.update(data.subarray(i, i + 7));
    expect(toHex(h.digest())).toBe(whole);
  });
});

describe("sha256Hex(blob)", () => {
  const data = Uint8Array.from({ length: 300_000 }, (_, i) => (i * 7 + 3) % 256);
  const blob = new Blob([data]);

  it("WebCrypto and incremental paths agree, reading in chunks with progress", async () => {
    const expected = toHex(new Uint8Array(await crypto.subtle.digest("SHA-256", data)));
    const progress: number[] = [];
    const viaWebCrypto = await sha256Hex(blob, { chunkBytes: 64 * 1024, onProgress: (d) => progress.push(d) });
    const viaIncremental = await sha256Hex(blob, { chunkBytes: 50_000, webCryptoMaxBytes: 0 });
    expect(viaWebCrypto).toBe(expected);
    expect(viaIncremental).toBe(expected);
    expect(progress[0]).toBe(0);
    expect(progress.at(-1)).toBe(300_000);
    expect(progress.length).toBe(1 + Math.ceil(300_000 / (64 * 1024)));
  });

  it("hashes an empty file and can be aborted", async () => {
    expect(await sha256Hex(new Blob([]))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    const c = new AbortController();
    c.abort();
    await expect(sha256Hex(blob, { signal: c.signal })).rejects.toMatchObject({ name: "AbortError" });
  });

  it("compares hashes case-insensitively", () => {
    expect(sameHash("ABC", "abc")).toBe(true);
    expect(sameHash("abc", null)).toBe(false);
  });
});

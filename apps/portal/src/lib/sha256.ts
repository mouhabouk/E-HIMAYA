/**
 * SHA-256 of a file, read in chunks (Blob.slice), as lowercase hex.
 *
 * WebCrypto (`crypto.subtle.digest`) is used whenever the file fits the in-memory limit: the chunks are
 * copied into one buffer and hashed natively. WebCrypto has no incremental (streaming) API, so larger files
 * (CAD plans reach 100 MB) go through the small incremental implementation below, which keeps memory
 * bounded to one chunk. Both paths give the same digest (tested against each other and known vectors).
 */

export const HASH_CHUNK_BYTES = 4 * 1024 * 1024;
/** Above this size the incremental implementation is used instead of one WebCrypto call. */
export const WEBCRYPTO_MAX_BYTES = 64 * 1024 * 1024;

export interface HashOptions {
  chunkBytes?: number;
  webCryptoMaxBytes?: number;
  onProgress?: (hashedBytes: number, totalBytes: number) => void;
  signal?: AbortSignal;
}

export function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const b of bytes) out += b.toString(16).padStart(2, "0");
  return out;
}

async function readChunk(blob: Blob, start: number, end: number): Promise<Uint8Array> {
  const part = blob.slice(start, end);
  // Blob.arrayBuffer is missing in some test environments; FileReader is the portable fallback.
  if (typeof part.arrayBuffer === "function") return new Uint8Array(await part.arrayBuffer());
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(reader.error ?? new Error("read failed"));
    reader.readAsArrayBuffer(part);
  });
}

function abortIfNeeded(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException("Hashing aborted", "AbortError");
}

export async function sha256Hex(blob: Blob, options: HashOptions = {}): Promise<string> {
  const chunk = options.chunkBytes ?? HASH_CHUNK_BYTES;
  const total = blob.size;
  const useWebCrypto = typeof crypto !== "undefined" && "subtle" in crypto && total <= (options.webCryptoMaxBytes ?? WEBCRYPTO_MAX_BYTES);
  const incremental = useWebCrypto ? null : new Sha256();
  const whole = useWebCrypto ? new Uint8Array(total) : null;
  options.onProgress?.(0, total);
  for (let offset = 0; offset < total; offset += chunk) {
    abortIfNeeded(options.signal);
    const bytes = await readChunk(blob, offset, Math.min(total, offset + chunk));
    if (whole) whole.set(bytes, offset);
    else incremental?.update(bytes);
    options.onProgress?.(Math.min(total, offset + chunk), total);
  }
  abortIfNeeded(options.signal);
  if (whole) return toHex(new Uint8Array(await crypto.subtle.digest("SHA-256", whole)));
  return toHex((incremental ?? new Sha256()).digest());
}

/** Constant-time-ish comparison is not needed here (public data); just normalise case and spaces. */
export function sameHash(a: string | null | undefined, b: string | null | undefined): boolean {
  return !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();
}

// ---------------------------------------------------------------- incremental SHA-256 (FIPS 180-4)

const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
  0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
  0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
  0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
]);

export class Sha256 {
  private readonly h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  private readonly block = new Uint8Array(64);
  private readonly w = new Uint32Array(64);
  private blockLength = 0;
  private bytesHashed = 0;
  private finished = false;

  update(data: Uint8Array): this {
    if (this.finished) throw new Error("digest already computed");
    let pos = 0;
    this.bytesHashed += data.length;
    while (pos < data.length) {
      const take = Math.min(64 - this.blockLength, data.length - pos);
      this.block.set(data.subarray(pos, pos + take), this.blockLength);
      this.blockLength += take;
      pos += take;
      if (this.blockLength === 64) {
        this.compress();
        this.blockLength = 0;
      }
    }
    return this;
  }

  digest(): Uint8Array {
    if (!this.finished) {
      const bitsHi = Math.floor(this.bytesHashed / 0x20000000);
      const bitsLo = (this.bytesHashed << 3) >>> 0;
      this.block[this.blockLength++] = 0x80;
      if (this.blockLength > 56) {
        this.block.fill(0, this.blockLength);
        this.compress();
        this.blockLength = 0;
      }
      this.block.fill(0, this.blockLength, 56);
      const view = new DataView(this.block.buffer);
      view.setUint32(56, bitsHi);
      view.setUint32(60, bitsLo);
      this.compress();
      this.finished = true;
    }
    const out = new Uint8Array(32);
    const view = new DataView(out.buffer);
    this.h.forEach((v, i) => view.setUint32(i * 4, v));
    return out;
  }

  private compress(): void {
    const w = this.w;
    const b = this.block;
    for (let i = 0; i < 16; i++) {
      w[i] = ((b[i * 4] ?? 0) << 24) | ((b[i * 4 + 1] ?? 0) << 16) | ((b[i * 4 + 2] ?? 0) << 8) | (b[i * 4 + 3] ?? 0);
    }
    for (let i = 16; i < 64; i++) {
      const w15 = w[i - 15] ?? 0;
      const w2 = w[i - 2] ?? 0;
      const s0 = ((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3);
      const s1 = ((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10);
      w[i] = ((w[i - 16] ?? 0) + s0 + (w[i - 7] ?? 0) + s1) | 0;
    }
    const h = this.h;
    let a = h[0] ?? 0;
    let bb = h[1] ?? 0;
    let c = h[2] ?? 0;
    let d = h[3] ?? 0;
    let e = h[4] ?? 0;
    let f = h[5] ?? 0;
    let g = h[6] ?? 0;
    let hh = h[7] ?? 0;
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & f) ^ (~e & g);
      const t1 = (hh + S1 + ch + (K[i] ?? 0) + (w[i] ?? 0)) | 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const maj = (a & bb) ^ (a & c) ^ (bb & c);
      const t2 = (S0 + maj) | 0;
      hh = g;
      g = f;
      f = e;
      e = (d + t1) | 0;
      d = c;
      c = bb;
      bb = a;
      a = (t1 + t2) | 0;
    }
    h[0] = (h[0] ?? 0) + a;
    h[1] = (h[1] ?? 0) + bb;
    h[2] = (h[2] ?? 0) + c;
    h[3] = (h[3] ?? 0) + d;
    h[4] = (h[4] ?? 0) + e;
    h[5] = (h[5] ?? 0) + f;
    h[6] = (h[6] ?? 0) + g;
    h[7] = (h[7] ?? 0) + hh;
  }
}

// e-Himaya proof of work (phase L2, item 8, docs/phase-l/design-l2.md §3): after three failed attempts of a user name
// the sign-in page carries a salt and a difficulty; this script finds n such that SHA-256("salt:n") starts with
// `bits` zero bits, puts it in the form and enables the button. Nothing leaves the page and nothing is asked of the
// person. Plain SHA-256 (no crypto.subtle) so it also works over http:// on a local network.
(function () {
  "use strict";
  var K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
    0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
    0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
    0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
  ];
  var W = new Array(64);

  function rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  /** SHA-256 of an ASCII string (the salt is hexadecimal and the nonce decimal), as eight 32-bit words. */
  function sha256(text) {
    var n = text.length;
    var blocks = ((n + 8) >> 6) + 1;
    var words = new Array(blocks * 16);
    for (var z = 0; z < words.length; z++) words[z] = 0;
    for (var i = 0; i < n; i++) words[i >> 2] |= text.charCodeAt(i) << (24 - (i % 4) * 8);
    words[n >> 2] |= 0x80 << (24 - (n % 4) * 8);
    words[words.length - 1] = n * 8;
    var h = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    for (var b = 0; b < words.length; b += 16) {
      var a = h[0], bb = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
      for (var t = 0; t < 64; t++) {
        if (t < 16) {
          W[t] = words[b + t] | 0;
        } else {
          var x = W[t - 15], y = W[t - 2];
          var s0 = rotr(x, 7) ^ rotr(x, 18) ^ (x >>> 3);
          var s1 = rotr(y, 17) ^ rotr(y, 19) ^ (y >>> 10);
          W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
        }
        var t1 = (k + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[t] + W[t]) | 0;
        var t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & bb) ^ (a & c) ^ (bb & c))) | 0;
        k = g;
        g = f;
        f = e;
        e = (d + t1) | 0;
        d = c;
        c = bb;
        bb = a;
        a = (t1 + t2) | 0;
      }
      h[0] = (h[0] + a) | 0;
      h[1] = (h[1] + bb) | 0;
      h[2] = (h[2] + c) | 0;
      h[3] = (h[3] + d) | 0;
      h[4] = (h[4] + e) | 0;
      h[5] = (h[5] + f) | 0;
      h[6] = (h[6] + g) | 0;
      h[7] = (h[7] + k) | 0;
    }
    return h;
  }

  function leadingZeroBits(h) {
    var bits = 0;
    for (var i = 0; i < 8; i++) {
      if (h[i] === 0) {
        bits += 32;
        continue;
      }
      return bits + Math.clz32(h[i]);
    }
    return bits;
  }

  function hex(h) {
    return h
      .map(function (w) {
        return ("00000000" + (w >>> 0).toString(16)).slice(-8);
      })
      .join("");
  }

  // Exposed for the checks and the browser console: ehimayaPow.hex(ehimayaPow.sha256("1")).
  window.ehimayaPow = { sha256: sha256, hex: hex, leadingZeroBits: leadingZeroBits };

  var box = document.getElementById("ehimaya-pow");
  if (!box) return;
  var salt = box.getAttribute("data-salt");
  var bits = parseInt(box.getAttribute("data-bits"), 10);
  var field = document.getElementById("pow-solution");
  var status = document.getElementById("ehimaya-pow-status");
  var button = document.getElementById("kc-login");
  if (button) button.disabled = true;
  var n = 0;
  var limit = Math.pow(2, Math.min(bits + 6, 30));

  // Work in slices so the page stays responsive and the status line is read out.
  function slice() {
    var stop = n + 20000;
    for (; n < stop && n < limit; n++) {
      if (leadingZeroBits(sha256(salt + ":" + n)) >= bits) {
        field.value = String(n);
        status.textContent = box.getAttribute("data-done");
        if (button) button.disabled = false;
        return;
      }
    }
    if (n >= limit) {
      status.textContent = box.getAttribute("data-failed");
      return;
    }
    setTimeout(slice, 0);
  }
  setTimeout(slice, 0);
})();

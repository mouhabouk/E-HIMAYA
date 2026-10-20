/**
 * Line diff for the national memory version history (phase 8 §4): longest common subsequence over lines, which is
 * exact for the sizes of an entry section (a few hundred lines). Above `MAX_CELLS` comparisons the common prefix and
 * suffix are kept and the middle is shown as removed then added, so the page never stalls.
 */

export type DiffOp = { kind: "same" | "add" | "del"; text: string };

const MAX_CELLS = 1_000_000;

function splitLines(s: string): string[] {
  return s === "" ? [] : s.replace(/\r\n?/g, "\n").split("\n");
}

export function diffLines(before: string, after: string): DiffOp[] {
  const a = splitLines(before);
  const b = splitLines(after);
  let start = 0;
  while (start < a.length && start < b.length && a[start] === b[start]) start += 1;
  let endA = a.length;
  let endB = b.length;
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
    endA -= 1;
    endB -= 1;
  }
  const head: DiffOp[] = a.slice(0, start).map((text) => ({ kind: "same", text }));
  const tail: DiffOp[] = a.slice(endA).map((text) => ({ kind: "same", text }));
  const midA = a.slice(start, endA);
  const midB = b.slice(start, endB);
  return [...head, ...diffMiddle(midA, midB), ...tail];
}

function diffMiddle(a: string[], b: string[]): DiffOp[] {
  if (a.length === 0) return b.map((text) => ({ kind: "add", text }));
  if (b.length === 0) return a.map((text) => ({ kind: "del", text }));
  if (a.length * b.length > MAX_CELLS) {
    return [...a.map((text): DiffOp => ({ kind: "del", text })), ...b.map((text): DiffOp => ({ kind: "add", text }))];
  }
  // lcs[i][j] = LCS length of a[i..] and b[j..], stored flat.
  const w = b.length + 1;
  const lcs = new Uint32Array((a.length + 1) * w);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      lcs[i * w + j] =
        a[i] === b[j] ? (lcs[(i + 1) * w + j + 1] ?? 0) + 1 : Math.max(lcs[(i + 1) * w + j] ?? 0, lcs[i * w + j + 1] ?? 0);
    }
  }
  const out: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: "same", text: a[i] ?? "" });
      i += 1;
      j += 1;
    } else if ((lcs[(i + 1) * w + j] ?? 0) >= (lcs[i * w + j + 1] ?? 0)) {
      out.push({ kind: "del", text: a[i] ?? "" });
      i += 1;
    } else {
      out.push({ kind: "add", text: b[j] ?? "" });
      j += 1;
    }
  }
  while (i < a.length) out.push({ kind: "del", text: a[i++] ?? "" });
  while (j < b.length) out.push({ kind: "add", text: b[j++] ?? "" });
  return out;
}

/** True when the two texts differ (cheaper than a diff). */
export function changed(before: string | null | undefined, after: string | null | undefined): boolean {
  return (before ?? "") !== (after ?? "");
}

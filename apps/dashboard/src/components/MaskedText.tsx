import { Fragment } from "react";
import { useTranslation } from "react-i18next";

/**
 * `[start, end, kind]` in UTF-16 code units, as the API's `*_masks` fields. `hide`: obscene or insulting word;
 * `flag`: threat, incitement to violence or hatred, terrorism (kept readable).
 */
export type Masks = [number, number, "hide" | "flag"][];

type Part = { text: string; kind: "shown" | "hide" | "flag" };

/** Splits `text` into the shown parts, the hidden ones and the flagged ones (rule 4, moderation.masks). */
export function maskedParts(text: string, masks: Masks | undefined): Part[] {
  const parts: Part[] = [];
  let at = 0;
  for (const [start, end, kind] of [...(masks ?? [])].sort((a, b) => a[0] - b[0])) {
    if (start < at || end <= start || end > text.length) continue;
    if (start > at) parts.push({ text: text.slice(at, start), kind: "shown" });
    parts.push({ text: text.slice(start, end), kind: kind === "flag" ? "flag" : "hide" });
    at = end;
  }
  if (at < text.length) parts.push({ text: text.slice(at), kind: "shown" });
  return parts;
}

/**
 * A citizen's text with its obscene and insulting words hidden: a shaded block in another colour stands in their
 * place, never the word itself. Threats, incitement and terrorism stay readable, shaded red, because the operator
 * must read them. Both say what they are (tooltip and screen reader), not by colour alone. The shown parts stay
 * plain text of the parent element (its `lang` and `dir` apply to them).
 */
export function MaskedText({ text, masks }: { text: string; masks?: Masks }) {
  const { t } = useTranslation();
  return (
    <>
      {maskedParts(text, masks).map((p, i) => {
        if (p.kind === "hide")
          return (
            <span key={i} className="masked-word" role="img" aria-label={t("moderation.masked")} title={t("moderation.masked")}>
              {"•".repeat(Math.min(Math.max(p.text.length, 3), 8))}
            </span>
          );
        if (p.kind === "flag")
          return (
            <mark key={i} className="flagged-word" title={t("moderation.flagged")}>
              <span className="visually-hidden">{t("moderation.flagged")}: </span>
              {p.text}
            </mark>
          );
        return <Fragment key={i}>{p.text}</Fragment>;
      })}
    </>
  );
}

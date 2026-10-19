import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

/** Copies a text to the clipboard and says so (aria-live), with a selectable fallback when the API is refused. */
export function CopyButton({ text, label }: { text: string; label?: string }) {
  const { t } = useTranslation();
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  useEffect(() => {
    if (state === "idle") return;
    const id = setTimeout(() => setState("idle"), 2500);
    return () => clearTimeout(id);
  }, [state]);
  return (
    <span className="copy">
      <button
        type="button"
        className="btn"
        onClick={() => {
          const clipboard = typeof navigator !== "undefined" ? navigator.clipboard : undefined;
          if (!clipboard) {
            setState("failed");
            return;
          }
          clipboard.writeText(text).then(
            () => setState("copied"),
            () => setState("failed"),
          );
        }}
      >
        {label ?? t("common.copy")}
      </button>
      <span role="status" aria-live="polite" className="copy__status">
        {state === "copied" ? t("common.copied") : state === "failed" ? t("common.copyFailed") : ""}
      </span>
    </span>
  );
}

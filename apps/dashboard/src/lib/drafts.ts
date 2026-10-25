import { useCallback, useEffect, useState } from "react";

/**
 * Backlog G4: text an operator is typing survives live updates and accidental reloads.
 *
 * Live events can re-render or unmount a form (a report changes status, a panel closes, the page reloads). A draft is
 * kept in sessionStorage under its own key (record + field), restored when the form comes back, and dropped when it
 * is sent or emptied. sessionStorage stays in this tab and is gone when the tab closes; nothing leaves the browser.
 * While any draft holds text, closing or reloading the tab asks for confirmation.
 */
const PREFIX = "ehimaya.draft.";
const dirty = new Set<string>();

function onBeforeUnload(event: BeforeUnloadEvent) {
  event.preventDefault();
}

function markDirty(key: string, isDirty: boolean) {
  const before = dirty.size;
  if (isDirty) dirty.add(key);
  else dirty.delete(key);
  if (before === 0 && dirty.size > 0) window.addEventListener("beforeunload", onBeforeUnload);
  if (before > 0 && dirty.size === 0) window.removeEventListener("beforeunload", onBeforeUnload);
}

function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(PREFIX + key);
  } catch {
    return null;
  }
}

function write(key: string, value: string) {
  try {
    if (value) window.sessionStorage.setItem(PREFIX + key, value);
    else window.sessionStorage.removeItem(PREFIX + key);
  } catch {
    // Storage blocked or full: the draft still lives in the form.
  }
}

/** Number of drafts holding text, for tests and the leave warning. */
export function pendingDrafts(): number {
  return dirty.size;
}

/**
 * Like `useState("")` for a text field, but the text is kept per `key` until `clear()` (after a successful send).
 * The key names the record and the field, e.g. `report:<id>:note`.
 */
export function useDraft(key: string, initial = ""): [string, (value: string) => void, () => void] {
  const [value, setValue] = useState(() => read(key) ?? initial);

  useEffect(() => {
    markDirty(key, value.trim() !== "" && value !== initial);
    return () => markDirty(key, false);
  }, [key, value, initial]);

  const set = useCallback(
    (next: string) => {
      setValue(next);
      write(key, next === initial ? "" : next);
    },
    [key, initial],
  );

  const clear = useCallback(() => {
    setValue(initial);
    write(key, "");
  }, [key, initial]);

  return [value, set, clear];
}

import { useEffect, useState } from "react";

/** True when the page is in the night look (the header toggle, else the system setting). */
export function isDark(): boolean {
  if (typeof document === "undefined") return false;
  const explicit = document.documentElement.dataset.theme;
  if (explicit === "dark") return true;
  if (explicit === "light") return false;
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Follows the header toggle and the system setting. */
export function useDarkMode(): boolean {
  const [dark, setDark] = useState(isDark);
  useEffect(() => {
    const update = () => setDark(isDark());
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = typeof matchMedia === "function" ? matchMedia("(prefers-color-scheme: dark)") : null;
    mq?.addEventListener("change", update);
    return () => {
      observer.disconnect();
      mq?.removeEventListener("change", update);
    };
  }, []);
  return dark;
}

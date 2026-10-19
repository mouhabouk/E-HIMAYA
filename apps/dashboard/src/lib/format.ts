import type { Language } from "../i18n";

/** BCP 47 locales with Western (Latin) digits, as required for both languages. */
export const INTL_LOCALE: Record<Language, string> = { ar: "ar-TN-u-nu-latn", fr: "fr-TN-u-nu-latn" };

export interface Formatters {
  dateTime(iso: string): string;
  time(iso: string): string;
  number(n: number): string;
  bytes(n: number): string;
  duration(seconds: number): string;
  meters(m: number): string;
}

export function createFormatters(lang: Language): Formatters {
  const locale = INTL_LOCALE[lang];
  const dateTimeFmt = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const timeFmt = new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" });
  const numberFmt = new Intl.NumberFormat(locale);
  const unit = (u: string, max = 0) =>
    new Intl.NumberFormat(locale, { style: "unit", unit: u, unitDisplay: "short", maximumFractionDigits: max });

  return {
    dateTime: (iso) => {
      const d = new Date(iso);
      return Number.isNaN(d.getTime()) ? "—" : dateTimeFmt.format(d);
    },
    time: (iso) => {
      const d = new Date(iso);
      return Number.isNaN(d.getTime()) ? "—" : timeFmt.format(d);
    },
    number: (n) => numberFmt.format(n),
    bytes: (n) => {
      if (n >= 1024 * 1024) return unit("megabyte", 1).format(n / (1024 * 1024));
      if (n >= 1024) return unit("kilobyte", 0).format(n / 1024);
      return unit("byte").format(n);
    },
    meters: (m) => unit("meter").format(Math.round(m)),
    duration: (seconds) => {
      const s = Math.max(0, Math.round(seconds));
      if (s < 60) return unit("second").format(s);
      if (s < 3600) {
        const m = Math.floor(s / 60);
        const rest = s % 60;
        return rest ? `${unit("minute").format(m)} ${unit("second").format(rest)}` : unit("minute").format(m);
      }
      const h = Math.floor(s / 3600);
      const m = Math.floor((s % 3600) / 60);
      return m ? `${unit("hour").format(h)} ${unit("minute").format(m)}` : unit("hour").format(h);
    },
  };
}

import type { Language } from "../i18n";

/** BCP 47 locales with Western (Latin) digits, as in the dashboard. */
export const INTL_LOCALE: Record<Language, string> = { ar: "ar-TN-u-nu-latn", fr: "fr-TN-u-nu-latn", en: "en-GB-u-nu-latn" };

export interface Formatters {
  dateTime(iso: string | null | undefined): string;
  /** Calendar date ("2027-03-10" or a timestamp) without time. */
  date(iso: string | null | undefined): string;
  number(n: number | null | undefined): string;
  bytes(n: number | null | undefined): string;
  percent(fraction: number): string;
}

/** "2027-03-10" is a calendar date: format it in UTC so no time zone moves it to another day. */
function parseDate(iso: string): Date {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00Z`) : new Date(iso);
}

export function createFormatters(lang: Language): Formatters {
  const locale = INTL_LOCALE[lang];
  const dateTimeFmt = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const dateFmt = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" });
  const numberFmt = new Intl.NumberFormat(locale);
  const percentFmt = new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 });
  const unit = (u: string, max = 0) =>
    new Intl.NumberFormat(locale, { style: "unit", unit: u, unitDisplay: "short", maximumFractionDigits: max });
  return {
    dateTime: (iso) => {
      if (!iso) return "—";
      const d = new Date(iso);
      return Number.isNaN(d.getTime()) ? "—" : dateTimeFmt.format(d);
    },
    date: (iso) => {
      if (!iso) return "—";
      const d = parseDate(iso);
      return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
    },
    number: (n) => (n === null || n === undefined ? "—" : numberFmt.format(n)),
    bytes: (n) => {
      if (n === null || n === undefined) return "—";
      if (n >= 1024 * 1024) return unit("megabyte", 1).format(n / (1024 * 1024));
      if (n >= 1024) return unit("kilobyte", 0).format(n / 1024);
      return unit("byte").format(n);
    },
    percent: (fraction) => percentFmt.format(fraction),
  };
}

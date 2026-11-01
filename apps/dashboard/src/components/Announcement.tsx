// covers: phase 5 (Yamen 2026-11-01): the system administrator's message, written once and shown at once in the
// citizen app, the field app, the portal and the dashboard, for the surfaces chosen and until the end chosen.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useAnnouncement } from "../lib/features";
import { useLanguage } from "../lib/hooks";
import { reasonValid } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import type { PlatformSetting } from "../lib/phase9Types";
import { ReasonField } from "./Phase9Bits";

export const ANNOUNCEMENT_KEY = "app.announcement";
export const SURFACES = ["citizen_app", "field_app", "portal", "dashboard"] as const;
type Surface = (typeof SURFACES)[number];

interface AnnouncementValue {
  active: boolean;
  tone: "info" | "warn";
  text: { ar: string; fr: string; en: string };
  surfaces: Surface[];
  ends_at: string | null;
}

export function announcementOf(value: unknown): AnnouncementValue {
  const v = (value && typeof value === "object" ? value : {}) as Partial<AnnouncementValue>;
  return {
    active: v.active === true,
    tone: v.tone === "warn" ? "warn" : "info",
    text: { ar: v.text?.ar ?? "", fr: v.text?.fr ?? "", en: v.text?.en ?? "" },
    surfaces: (v.surfaces ?? []).filter((s): s is Surface => (SURFACES as readonly string[]).includes(s)),
    ends_at: v.ends_at ?? null,
  };
}

/** The message on top of every page of the dashboard, when the administrator shows it here. */
export function AnnouncementBanner() {
  const lang = useLanguage();
  const message = useAnnouncement();
  if (!message) return null;
  const text = message[lang] || message.ar;
  return (
    <div className={`alert alert--${message.tone} announcement`} role="status" dir="auto">
      {text}
    </div>
  );
}

/** The system administrator writes the message, chooses where it shows and until when. */
export function AnnouncementCard({ setting }: { setting: PlatformSetting }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [value, setValue] = useState(() => announcementOf(setting.value));
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const missing = value.active && (!value.text.ar.trim() || value.surfaces.length === 0);
  const save = useMutation({
    mutationFn: () =>
      api.savePlatformSetting(ANNOUNCEMENT_KEY, { value, version: setting.version, reason: reason.trim() }),
    onSuccess: () => {
      setReason("");
      setTried(false);
      void qc.invalidateQueries({ queryKey: p9Keys.settings });
      void qc.invalidateQueries({ queryKey: ["features", "mine"] });
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (missing || !reasonValid(reason)) return;
    save.mutate();
  };
  const set = (patch: Partial<AnnouncementValue>) => setValue((v) => ({ ...v, ...patch }));
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("announcement.title")}</h2>
      <p className="muted">{t("announcement.help")}</p>
      <form noValidate onSubmit={submit}>
        <fieldset disabled={!setting.editable || save.isPending}>
          <label className="checkbox">
            <input type="checkbox" checked={value.active} onChange={(e) => set({ active: e.target.checked })} />{" "}
            {t("announcement.active")}
          </label>
          {(["ar", "fr", "en"] as const).map((l) => (
            <div key={l} className="field">
              <label htmlFor={`${id}-${l}`}>{t(`announcement.text.${l}`)}</label>
              <textarea
                id={`${id}-${l}`}
                rows={2}
                maxLength={2000}
                dir={l === "ar" ? "rtl" : "ltr"}
                value={value.text[l]}
                aria-invalid={tried && l === "ar" && value.active && !value.text.ar.trim()}
                onChange={(e) => set({ text: { ...value.text, [l]: e.target.value } })}
              />
            </div>
          ))}
          <fieldset className="perm-form__row">
            <legend>{t("announcement.surfaces")}</legend>
            {SURFACES.map((s) => (
              <label key={s} className="checkbox">
                <input
                  type="checkbox"
                  checked={value.surfaces.includes(s)}
                  onChange={(e) =>
                    set({ surfaces: e.target.checked ? [...value.surfaces, s] : value.surfaces.filter((x) => x !== s) })
                  }
                />{" "}
                {t(`announcement.surface.${s}`)}
              </label>
            ))}
          </fieldset>
          <fieldset className="perm-form__row">
            <legend>{t("announcement.tone")}</legend>
            {(["info", "warn"] as const).map((tone) => (
              <label key={tone} className="radio">
                <input type="radio" name={`${id}-tone`} checked={value.tone === tone} onChange={() => set({ tone })} />{" "}
                {t(`announcement.tones.${tone}`)}
              </label>
            ))}
          </fieldset>
          <div className="field">
            <label htmlFor={`${id}-end`}>{t("announcement.until")}</label>
            <input
              id={`${id}-end`}
              type="datetime-local"
              value={value.ends_at ? value.ends_at.slice(0, 16) : ""}
              onChange={(e) => set({ ends_at: e.target.value ? new Date(e.target.value).toISOString() : null })}
            />
          </div>
          <ReasonField label={t("permissions.reason")} value={reason} onChange={setReason} showError={tried} />
          <button type="submit" className="btn btn--primary">
            {t("announcement.save")}
          </button>
        </fieldset>
        {tried && missing && (
          <p className="field__error" role="alert">
            {t("announcement.missing")}
          </p>
        )}
        {save.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(save.error))}
          </p>
        )}
        {save.isSuccess && (
          <p className="alert alert--ok" role="status">
            {t("announcement.saved")}
          </p>
        )}
      </form>
    </section>
  );
}

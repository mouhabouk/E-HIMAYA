import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import type { PlatformSetting } from "../lib/phase9Types";
import { SettingForm } from "./PhaseASettings";

/**
 * `safety.location_history` (phase B2, addition 7b): the 72-hour location history, off until the platform turns it
 * on. While off, the app hides it and the dashboard hides the missing-person search.
 */
export function LocationHistoryCard({ setting }: { setting: PlatformSetting }) {
  const { t } = useTranslation();
  const id = useId();
  const [on, setOn] = useState(setting.value === true);

  return (
    <SettingForm
      setting={setting}
      title={t("settings.locationHistory.title")}
      help={t("settings.locationHistory.help")}
      error={null}
      toValue={() => on}
    >
      {() => (
        <div className="field">
          <label className="checkbox" htmlFor={`${id}-on`}>
            <input id={`${id}-on`} type="checkbox" checked={on} onChange={(e) => setOn(e.target.checked)} />{" "}
            {t("settings.locationHistory.label")}
          </label>
          <p className="muted">{t("settings.locationHistory.note")}</p>
        </div>
      )}
    </SettingForm>
  );
}

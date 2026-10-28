// covers: docs/phase-r/design-basemap.md §2: the background of a map, street map, satellite or hybrid (satellite with
// the place names), kept in the browser. The imagery comes from the open source unless the administration enabled a
// paid provider; the source is named under the switch.
import { useQuery } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { BASEMAP_MODES, basemapKeys, storedMode, storeMode, type BasemapMode, type BasemapView } from "../lib/basemap";

export function useBasemap() {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [mode, setModeState] = useState<BasemapMode>(storedMode);
  const query = useQuery({
    queryKey: basemapKeys.view,
    // The signed address of a paid provider lasts twelve hours.
    staleTime: 60 * 60 * 1000,
    refetchInterval: 6 * 60 * 60 * 1000,
    queryFn: ({ signal }) => api.basemap(signal),
  });
  const setMode = (m: BasemapMode) => {
    setModeState(m);
    storeMode(m);
  };
  const data = query.data;
  const view = useMemo<BasemapView | null>(
    () => (data ? { mode, satellite: data.satellite, labels: data.labels } : null),
    [data, mode],
  );
  const control = (
    <div className="basemap-switch">
      {/* Named by aria-label: a visually hidden legend of a segmented control widens the page in RTL. */}
      <fieldset className="segmented" aria-label={t("basemap.label")}>
        {BASEMAP_MODES.map((m) => (
          <label key={m} className="segmented__item">
            <input
              type="radio"
              name={`${id}-basemap`}
              checked={mode === m}
              disabled={m !== "map" && !data}
              onChange={() => setMode(m)}
            />
            <span>{t(`basemap.mode.${m}`)}</span>
          </label>
        ))}
      </fieldset>
      {mode !== "map" && data && (
        <span className="muted basemap-switch__source">
          {t(data.source === "paid" ? "basemap.source.paid" : "basemap.source.open")}
        </span>
      )}
    </div>
  );
  return { view, control };
}

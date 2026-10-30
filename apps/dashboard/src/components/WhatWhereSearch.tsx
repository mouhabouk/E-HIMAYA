// covers: phase N (docs/phase-n/design-n.md §7): "what, then where" on the map. The agent first picks what (a layer:
// hospitals, schools, dams…), then types where (words of the place's name); a result moves the map to the place.
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { useDebounced, useGouvernorats, useLanguage } from "../lib/hooks";
import type { LayerFeature } from "../lib/layers";
import { layerKeys } from "../lib/layersApi";
import { localized } from "../lib/localized";

/** Results shown at most; the API answers the first places by name. */
const SHOWN = 12;

export function WhatWhereSearch({ onPick }: { onPick: (place: LayerFeature) => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const { nameOf } = useGouvernorats();
  const id = useId();
  const [layer, setLayer] = useState("");
  const [text, setText] = useState("");
  const q = useDebounced(text.trim(), 300);
  const layers = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) });
  const choices = (layers.data?.items ?? []).filter((l) => l.enabled && l.feature_count > 0);
  const found = useQuery({
    queryKey: [...layerKeys.all, "places", layer, q] as const,
    queryFn: ({ signal }) => api.layerPlaces(layer, q, signal),
    enabled: Boolean(layer) && q.length >= 2,
    staleTime: 60_000,
  });
  const items = found.data?.items.slice(0, SHOWN) ?? [];
  return (
    <section className="what-where" aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`} className="what-where__title">
        {t("whatWhere.title")}
      </h2>
      <div className="what-where__row">
        <label htmlFor={`${id}-what`} className="visually-hidden">
          {t("whatWhere.what")}
        </label>
        <select id={`${id}-what`} value={layer} onChange={(e) => setLayer(e.target.value)}>
          <option value="">{t("whatWhere.what")}</option>
          {choices.map((l) => (
            <option key={l.key} value={l.key}>
              {localized(l.name, lang)}
            </option>
          ))}
        </select>
        <label htmlFor={`${id}-where`} className="visually-hidden">
          {t("whatWhere.where")}
        </label>
        <input
          id={`${id}-where`}
          type="search"
          value={text}
          disabled={!layer}
          placeholder={t("whatWhere.where")}
          onChange={(e) => setText(e.target.value)}
        />
      </div>
      {layer && q.length >= 2 && found.isSuccess && (
        <ul className="what-where__results" aria-live="polite">
          {items.length === 0 && <li className="muted">{t("whatWhere.none")}</li>}
          {items.map((f) => (
            <li key={f.id}>
              <button type="button" className="link-button" onClick={() => onPick(f)}>
                <span dir="auto">{f.name}</span>
              </button>{" "}
              <span className="muted">{nameOf(f.gouvernorat_code) ?? ""}</span>
            </li>
          ))}
          {found.data.items.length > SHOWN && <li className="muted">{t("whatWhere.more")}</li>}
        </ul>
      )}
    </section>
  );
}

import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import type { DamageEntry } from "../lib/missionRecord";
import { referenceKeys, type RefItem } from "../lib/references";

const UNITS = ["ha", "bale", "bag"] as const;

/**
 * What a fire destroyed (Yamen, 2026-11-01): the place burnt and its surface in hectares, or the crop or fodder lost
 * in hectares, bales or bags. The places and the crops are the items of the reference lists; choosing a crop gives its
 * usual unit (straw and hay in bales), which can still be changed.
 */
export function DamagesEditor({
  value,
  onChange,
  disabled,
}: {
  value: DamageEntry[];
  onChange: (lines: DamageEntry[]) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const refs = useQuery({ queryKey: referenceKeys.all, queryFn: ({ signal }) => api.references(signal) });
  const items = (key: string): RefItem[] =>
    refs.data?.lists.find((l) => l.key === key)?.items.filter((i) => i.active) ?? [];
  const forest = items("forest_place");
  const agri = items("agri_place");
  const crops = items("crop_loss");
  const set = (i: number, patch: Partial<DamageEntry>) =>
    onChange(value.map((d, j) => (j === i ? { ...d, ...patch } : d)));
  return (
    <fieldset className="record-damages">
      <legend>{t("record.damages.title")}</legend>
      <p className="muted">{t("record.damages.hint")}</p>
      {value.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">{t("record.damages.kind")}</th>
                <th scope="col">{t("record.damages.place")}</th>
                <th scope="col">{t("record.damages.crop")}</th>
                <th scope="col">{t("record.damages.value")}</th>
                <th scope="col">{t("record.damages.unit")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("record.damages.remove")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {value.map((d, i) => {
                const places = d.kind === "forest" ? forest : agri;
                return (
                  <tr key={i}>
                    <td>
                      <select
                        aria-label={t("record.damages.kind")}
                        value={d.kind}
                        disabled={disabled}
                        onChange={(e) => {
                          const kind = e.target.value as DamageEntry["kind"];
                          set(i, { kind, place: "", crop: null, unit: "ha" });
                        }}
                      >
                        <option value="forest">{t("record.damages.forest")}</option>
                        <option value="agri">{t("record.damages.agri")}</option>
                      </select>
                    </td>
                    <td>
                      <select
                        aria-label={t("record.damages.place")}
                        value={d.place}
                        disabled={disabled}
                        onChange={(e) => set(i, { place: e.target.value })}
                      >
                        <option value="">—</option>
                        {places.map((p) => (
                          <option key={p.id} value={p.label_ar}>
                            {p.label_ar}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      {d.kind === "agri" ? (
                        <select
                          aria-label={t("record.damages.crop")}
                          value={d.crop ?? ""}
                          disabled={disabled}
                          onChange={(e) => {
                            const crop = crops.find((c) => c.label_ar === e.target.value);
                            set(i, { crop: e.target.value || null, unit: crop?.unit ?? d.unit });
                          }}
                        >
                          <option value="">—</option>
                          {crops.map((c) => (
                            <option key={c.id} value={c.label_ar}>
                              {c.label_ar}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <input
                        type="number"
                        inputMode="decimal"
                        min={0}
                        step="any"
                        aria-label={t("record.damages.value")}
                        value={d.value || ""}
                        disabled={disabled}
                        onChange={(e) => set(i, { value: Number(e.target.value) || 0 })}
                      />
                    </td>
                    <td>
                      <select
                        aria-label={t("record.damages.unit")}
                        value={d.kind === "forest" ? "ha" : d.unit}
                        disabled={disabled || d.kind === "forest"}
                        onChange={(e) => set(i, { unit: e.target.value as DamageEntry["unit"] })}
                      >
                        {UNITS.map((u) => (
                          <option key={u} value={u}>
                            {t(`record.damages.units.${u}`)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={disabled}
                        aria-label={t("record.damages.removeLine", { n: i + 1 })}
                        onClick={() => onChange(value.filter((_, j) => j !== i))}
                      >
                        {t("record.damages.remove")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <button
        type="button"
        id={`${id}-add`}
        className="btn btn--small"
        disabled={disabled || value.length >= 20}
        onClick={() => onChange([...value, { kind: "forest", place: "", crop: null, unit: "ha", value: 0 }])}
      >
        {t("record.damages.add")}
      </button>
    </fieldset>
  );
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../../context/services";
import { errorMessageKey } from "../../lib/api";
import { crisisKeys, EXPOSURE_GROUPS, type Axis, type Exposure } from "../../lib/crisis";
import { useFormat } from "../../lib/hooks";
import { ErrorBox, Loading } from "../Feedback";
import { Kpi } from "./CrisisBits";

/**
 * OS14 (docs/phase-os14/design-os14.md): the people and places exposed on the axis area, in the axis's own tab.
 * The footprint is the axis area (no hazard drawn twice) plus a band chosen here; the room computes, every reader
 * of the axis reads, and each estimate stays in the axis timeline. The decision window and the interactive map show
 * the same figures.
 */
export function ExposurePanel({ axis }: { axis: Axis }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: crisisKeys.exposure(axis.id), queryFn: ({ signal }) => api.crisisExposure(axis.id, signal) });
  const [ring, setRing] = useState<number | null>(null);
  const compute = useMutation({
    mutationFn: (ringM: number | null) => api.computeExposure(axis.id, ringM),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: crisisKeys.exposure(axis.id) });
      void qc.invalidateQueries({ queryKey: crisisKeys.axis(axis.id) });
      void qc.invalidateQueries({ queryKey: crisisKeys.exposureMap });
    },
  });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorBox error={q.error} onRetry={() => void q.refetch()} />;
  const s = q.data;
  const e = s.estimate;
  const chosen = ring ?? e?.ring_m ?? s.default_ring_m;
  const km = (m: number) => fmt.number(m / 1000);
  return (
    <div className="exposure">
      <div className="exposure__bar">
        <div className="segmented" role="radiogroup" aria-label={t("crisis.exposure.ring")}>
          {s.rings.map((r) => (
            <label key={r} className="segmented__item">
              <input
                type="radio"
                name={`exposure-ring-${axis.id}`}
                checked={chosen === r}
                onChange={() => setRing(r)}
                disabled={!s.can_compute}
              />
              <span>{r === 0 ? t("crisis.exposure.noRing") : t("crisis.exposure.ringKm", { km: km(r) })}</span>
            </label>
          ))}
        </div>
        {s.can_compute && (
          <button
            type="button"
            className="btn btn--small btn--primary"
            onClick={() => compute.mutate(chosen)}
            disabled={compute.isPending || !s.has_area}
          >
            {e ? t("crisis.exposure.recompute") : t("crisis.exposure.compute")}
          </button>
        )}
        {e && (
          <span className="muted">
            {t("crisis.exposure.at", { at: fmt.dateTime(e.computed_at) })}
            {e.computed_by ? ` · ${e.computed_by}` : ""}
          </span>
        )}
      </div>
      {compute.isError && <p className="alert alert--error">{t(errorMessageKey(compute.error))}</p>}
      {!s.has_area && <p className="ops-empty">{t("crisis.exposure.noArea")}</p>}
      {s.has_area && !e && <p className="ops-empty">{t(s.can_compute ? "crisis.exposure.none" : "crisis.exposure.noneReader")}</p>}
      {e?.stale && <p className="alert alert--warning">{t("crisis.exposure.stale")}</p>}
      {e && <ExposureBody e={e} />}
    </div>
  );
}

function ExposureBody({ e }: { e: Exposure }) {
  const { t, i18n } = useTranslation();
  const fmt = useFormat();
  const n = (v: number) => fmt.number(v);
  const sensitive = e.groups.health.count + e.groups.elderly.count + e.groups.education.count;
  const sensitiveCore = e.groups.health.core + e.groups.elderly.core + e.groups.education.core;
  const ar = i18n.language.startsWith("ar");
  return (
    <>
      <div className="kpi-row">
        <Kpi
          label={t("crisis.exposure.people")}
          value={`≈ ${n(e.population.estimate)}`}
          tone="red"
          hint={t("crisis.exposure.peopleHint", { low: n(e.population.low), high: n(e.population.high), core: n(e.population.core) })}
        />
        <Kpi label={t("crisis.exposure.sensitive")} value={n(sensitive)} tone="purple" hint={t("crisis.exposure.inCore", { n: sensitiveCore })} />
        <Kpi
          label={t("crisis.exposure.linesCut")}
          value={n(e.brief.lines_cut)}
          tone="amber"
          hint={t("crisis.exposure.linesHint", { n: e.lines.length })}
        />
        <Kpi
          label={t("crisis.exposure.area")}
          value={`${n(e.area_km2)} km²`}
          tone="teal"
          hint={t("crisis.exposure.areaHint", { core: n(e.core_km2), ring: n(e.ring_m / 1000) })}
        />
      </div>
      <div className="exposure__grid">
        <section aria-labelledby="exp-del">
          <h3 id="exp-del">{t("crisis.exposure.byDelegation")}</h3>
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">{t("crisis.exposure.delegation")}</th>
                <th scope="col">{t("crisis.exposure.census")}</th>
                <th scope="col">{t("crisis.exposure.share")}</th>
                <th scope="col">{t("crisis.exposure.estimate")}</th>
                <th scope="col">{t("crisis.exposure.core")}</th>
              </tr>
            </thead>
            <tbody>
              {e.delegations.map((d) => (
                <tr key={d.id}>
                  <th scope="row">{ar ? d.name_ar : d.name_fr}</th>
                  <td><bdi dir="ltr">{n(d.population)}</bdi></td>
                  <td><bdi dir="ltr">{n(d.area_share)} %</bdi></td>
                  <td>
                    <strong><bdi dir="ltr">≈ {n(d.estimate)}</bdi></strong>
                    <div className="muted exposure__small"><bdi dir="ltr">{n(d.low)} – {n(d.high)}</bdi></div>
                  </td>
                  <td><bdi dir="ltr">≈ {n(d.core)}</bdi></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted exposure__small">{t("crisis.exposure.method")}</p>
        </section>
        <section aria-labelledby="exp-places">
          <h3 id="exp-places">{t("crisis.exposure.places")}</h3>
          {EXPOSURE_GROUPS.map((g) => {
            const group = e.groups[g];
            return (
              <div key={g} className="exposure__group">
                <p className="exposure__group-head">
                  <strong>{t(`crisis.exposure.group.${g}`)}</strong> <span className="pill tone-slate">{n(group.count)}</span>
                </p>
                {group.count === 0 ? (
                  <p className="muted exposure__small">{t("crisis.exposure.noneInside")}</p>
                ) : (
                  <ul className="exposure__places">
                    {group.items.map((p, k) => (
                      <li key={`${p.name}-${k}`}>
                        <span dir="auto">{p.name}</span>
                        <span className={`pill tone-${p.zone === "core" ? "red" : "amber"}`}>{t(`crisis.exposure.zone.${p.zone}`)}</span>
                      </li>
                    ))}
                    {group.count > group.items.length && (
                      <li className="muted exposure__small">{t("crisis.exposure.more", { n: group.count - group.items.length })}</li>
                    )}
                  </ul>
                )}
              </div>
            );
          })}
        </section>
        <section aria-labelledby="exp-lines">
          <h3 id="exp-lines">{t("crisis.exposure.lines")}</h3>
          {e.lines.length === 0 ? (
            <p className="muted exposure__small">{t("crisis.exposure.noLines")}</p>
          ) : (
            <ul className="exposure__places">
              {e.lines.map((l, k) => (
                <li key={`${l.layer}-${l.name}-${k}`}>
                  <span dir="auto">
                    {t(`crisis.exposure.line.${l.layer}`, { defaultValue: l.layer })}
                    {l.name ? ` · ${l.name}` : ""} · <bdi dir="ltr">{n(l.km)} km</bdi>
                  </span>
                  <span className={`pill tone-${l.cut ? "red" : "amber"}`}>{t(l.cut ? "crisis.exposure.cut" : "crisis.exposure.threatened")}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="muted exposure__small">{t("crisis.exposure.roadsNote")}</p>
          <h3>{t("crisis.exposure.sources")}</h3>
          <ul className="muted exposure__small">
            <li>{t("crisis.exposure.sourceCensus", { census: e.sources.census })}</li>
            <li>
              {t("crisis.exposure.sourceLayers", { n: e.sources.layers.length })}
              {e.sources.layers.some((l) => l.to_verify) ? ` · ${t("crisis.exposure.toVerify")}` : ""}
            </li>
          </ul>
          <p className="muted exposure__small">{t("crisis.exposure.caveat")}</p>
        </section>
      </div>
    </>
  );
}

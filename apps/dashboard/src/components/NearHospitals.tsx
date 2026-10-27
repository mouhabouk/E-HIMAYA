import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { formatPhone } from "../lib/layers";
import { opsKeys } from "../lib/opsApi";
import { canManageIncidents } from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { IncidentDetail } from "../lib/types";
import { ErrorBox, Loading } from "./Feedback";
import { SimTag } from "./StreamBits";

/**
 * The nearest hospitals and clinics of an incident on the road (phase L1b, design-layers.md §4): from the hospital
 * layers the reader may see, timed by the routing engine (or estimated, and said so). The room adds one to the
 * incident: it goes on the timeline, for the crews and the report.
 */
export function NearHospitals({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const canWrite = canManageIncidents(user?.identity.roles ?? []) && incident.status === "open";
  const [added, setAdded] = useState<string | null>(null);
  const hospitals = useQuery({
    queryKey: opsKeys.hospitals(incident.id),
    queryFn: ({ signal }) => api.incidentHospitals(incident.id, signal),
  });
  const choose = useMutation({
    mutationFn: (featureId: string) => api.chooseHospital(incident.id, featureId),
    onSuccess: (h) => {
      setAdded(h.id);
      void qc.invalidateQueries({ queryKey: queryKeys.incident(incident.id) });
    },
  });
  return (
    <section className="card" aria-labelledby="sec-hospitals">
      <h2 id="sec-hospitals">{t("hospitals.title")}</h2>
      {hospitals.isLoading && <Loading />}
      {hospitals.isError && <ErrorBox error={hospitals.error} onRetry={() => void hospitals.refetch()} />}
      {hospitals.data && hospitals.data.length === 0 && <p className="muted">{t("hospitals.none")}</p>}
      <ol className="near-hospitals">
        {(hospitals.data ?? []).map((h) => (
          <li key={h.id}>
            <strong dir="auto">{h.name}</strong>
            {h.simulated && <SimTag label={t("layers.simulated")} />}
            <span className="muted">
              {t("hospitals.road", {
                km: fmt.decimal(h.road_m / 1000),
                minutes: fmt.number(Math.max(1, Math.round(h.road_s / 60))),
              })}
              {h.engine === "fallback" && ` · ${t("hospitals.estimate")}`}
            </span>
            {h.phone && (
              <a href={`tel:${h.phone}`} dir="ltr">
                {formatPhone(h.phone)}
              </a>
            )}
            {canWrite &&
              (added === h.id ? (
                <span className="pill tone-green">{t("hospitals.added")}</span>
              ) : (
                <button type="button" className="btn btn--small" disabled={choose.isPending} onClick={() => choose.mutate(h.id)}>
                  {t("hospitals.add")}
                </button>
              ))}
          </li>
        ))}
      </ol>
      {choose.isError && (
        <p role="alert" className="alert alert--error">
          {t(errorMessageKey(choose.error))}
        </p>
      )}
    </section>
  );
}

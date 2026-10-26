import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { crewKeys } from "../lib/crewApi";
import type { CrewDevice } from "../lib/crewTypes";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { canManageCrewDevices, hasReadAccess } from "../lib/roles";

function OnDuty() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const query = useQuery({ queryKey: crewKeys.shifts, queryFn: ({ signal }) => api.shifts(signal), refetchInterval: 30_000 });
  return (
    <section className="card" aria-labelledby="sec-on-duty">
      <h2 id="sec-on-duty">{t("crew.onDuty")}</h2>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && <p className="muted">{t("crew.noShift")}</p>}
      {query.isSuccess && query.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("crew.onDuty")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("crew.vehicle")}</th>
                <th scope="col">{t("crew.leaderCol")}</th>
                <th scope="col">{t("crew.crewCol")}</th>
                <th scope="col">{t("crew.since")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong dir="auto">{s.resource.label}</strong>
                    <div className="cell-sub">
                      {t(`resources.kind.${s.resource.kind}`)} · <span dir="auto">{s.resource.unit_name}</span> ·{" "}
                      {gouvernorats.nameOf(s.gouvernorat_code) ?? s.gouvernorat_code}
                    </div>
                  </td>
                  <td dir="auto">{s.leader_name ?? "—"}</td>
                  <td>
                    {t("crew.size", { count: s.crew_size })}
                    {s.crew_names && (
                      <div className="cell-sub" dir="auto">
                        {s.crew_names}
                      </div>
                    )}
                  </td>
                  <td>
                    <time dateTime={s.started_at}>{fmt.dateTime(s.started_at)}</time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function DeviceRow({ device }: { device: CrewDevice }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const revoke = useMutation({
    mutationFn: () => api.revokeCrewDevice(device.id),
    onSuccess: () => {
      setConfirming(false);
      void qc.invalidateQueries({ queryKey: crewKeys.devicesAll });
      void qc.invalidateQueries({ queryKey: crewKeys.shifts });
    },
  });
  const name = device.holder_name ?? "—";
  return (
    <tr>
      <td>
        <strong dir="auto">{name}</strong>
        <div className="cell-sub">
          {device.label && <span dir="auto">{device.label} · </span>}
          {device.platform}
          {device.app_build !== null && ` · ${t("crew.build", { build: device.app_build })}`}
        </div>
      </td>
      <td>
        {device.revoked_at ? (
          <span className="chip chip--crew-revoked">{t("crew.revoked")}</span>
        ) : device.on_shift ? (
          <span className="chip chip--crew-ack">{t("crew.onShift")}</span>
        ) : (
          <span className="muted">{t("crew.idle")}</span>
        )}
      </td>
      <td>
        <time dateTime={device.last_seen_at}>{fmt.dateTime(device.last_seen_at)}</time>
      </td>
      <td>
        {!device.revoked_at &&
          (confirming ? (
            <div className="ops-row-actions" role="group" aria-label={t("crew.revokeConfirm", { name })}>
              <span>{t("crew.revokeConfirm", { name })}</span>
              <button
                type="button"
                className="btn btn--danger btn--small"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate()}
              >
                {t("crew.revokeYes")}
              </button>
              <button type="button" className="btn btn--small" onClick={() => setConfirming(false)}>
                {t("common.cancel")}
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn btn--small"
              aria-label={t("crew.revokeLabel", { name })}
              onClick={() => setConfirming(true)}
            >
              {t("crew.revoke")}
            </button>
          ))}
        {revoke.isError && <ErrorBox error={revoke.error} />}
      </td>
    </tr>
  );
}

function Devices() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [revoked, setRevoked] = useState(false);
  const query = useQuery({
    queryKey: crewKeys.devices(revoked),
    queryFn: ({ signal }) => api.crewDevices(revoked, signal),
  });
  return (
    <section className="card" aria-labelledby="sec-devices">
      <h2 id="sec-devices">{t("crew.devices")}</h2>
      <p className="muted">{t("crew.devicesIntro")}</p>
      <label className="checkbox">
        <input type="checkbox" checked={revoked} onChange={(e) => setRevoked(e.target.checked)} />
        <span>{t("crew.showRevoked")}</span>
      </label>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && <p className="muted">{t("crew.noDevice")}</p>}
      {query.isSuccess && query.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("crew.devices")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("crew.holder")}</th>
                <th scope="col">{t("crew.state")}</th>
                <th scope="col">{t("crew.lastSeen")}</th>
                <th scope="col">{t("ops.assignment.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((d) => (
                <DeviceRow key={d.id} device={d} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** Phase P4a: teams on duty on the staff app and, for the account administrators, the leaders' phones. */
export function CrewPage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="groups" tone="green">
          {t("crew.pageTitle")}
        </PageTitle>
      </div>
      <p className="muted">{t("crew.intro")}</p>
      {hasReadAccess(roles) && <OnDuty />}
      {canManageCrewDevices(roles) && <Devices />}
    </div>
  );
}

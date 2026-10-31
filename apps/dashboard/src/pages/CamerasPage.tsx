import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Pill, type Tone } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { SimTag } from "../components/StreamBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { canRegisterCameras } from "../lib/roles";
import { streamKeys, type Prealert, type RegisteredSource } from "../lib/streamsApi";
import { StreamsNav } from "./StreamsPage";

const STATE_TONE: Record<Prealert["state"], Tone> = {
  pending: "red",
  cancelled: "slate",
  confirmed: "amber",
  escalated: "red",
};

/** The publish URL and the token, shown once, with the relay line for a camera that only offers RTSP (Tapo). */
function Registered({ source, onClose }: { source: RegisteredSource; onClose: () => void }) {
  const { t } = useTranslation();
  const relay =
    `CAMERA_RTSP_URL='rtsp://<user>:<password>@<camera-ip>:554/stream1' ` +
    `CAMERA_PUBLISH_URL='${source.publish_url_rtsp}?token=${source.publish_token}' ` +
    `docker compose --profile camera up -d camera-relay`;
  return (
    <div className="alert alert--success" role="status" aria-live="polite">
      <p>{t("cameras.registered")}</p>
      <p className="muted">{t("cameras.tokenOnce")}</p>
      <pre className="code" dir="ltr">
        {relay}
      </pre>
      <button type="button" className="btn btn--small" onClick={onClose}>
        {t("cameras.copied")}
      </button>
    </div>
  );
}

function RegisterForm({ gouvernorat }: { gouvernorat: number }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [label, setLabel] = useState("");
  const [org, setOrg] = useState("");
  const [shown, setShown] = useState<RegisteredSource | null>(null);
  const orgs = useQuery({
    queryKey: ["orgs", "cameras", gouvernorat],
    queryFn: ({ signal }) =>
      api.orgs(
        { status: "active", kind: null, gouvernorat, certificate: null, hasHazmat: null, q: "" },
        { limit: 200, signal },
      ),
  });
  const chosen = orgs.data?.items.find((o) => o.id === org) ?? null;
  const create = useMutation({
    mutationFn: () =>
      api.registerCamera({
        label: label.trim(),
        gouvernorat_code: gouvernorat,
        org_id: org || null,
        lat: chosen?.location?.lat ?? null,
        lon: chosen?.location?.lon ?? null,
      }),
    onSuccess: (source) => {
      setLabel("");
      setShown(source);
      void qc.invalidateQueries({ queryKey: streamKeys.listsAll });
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (label.trim()) create.mutate();
  };
  return (
    <section className="card" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{t("cameras.add")}</h2>
      <p className="muted">{t("cameras.addHelp")}</p>
      {shown && <Registered source={shown} onClose={() => setShown(null)} />}
      <form className="form-row" onSubmit={submit}>
        <div className="field">
          <label htmlFor={`${id}-org`}>{t("cameras.org")}</label>
          <select id={`${id}-org`} value={org} onChange={(e) => setOrg(e.target.value)}>
            <option value="">{t("cameras.noOrg")}</option>
            {orgs.data?.items.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-label`}>
            {t("cameras.label")} <span className="required">*</span>
          </label>
          <input
            id={`${id}-label`}
            value={label}
            maxLength={100}
            required
            placeholder="Tapo C200 · entrepôt"
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn--primary" disabled={create.isPending || !label.trim()}>
          {t("cameras.register")}
        </button>
      </form>
      {create.isError && <ErrorBox error={create.error} />}
    </section>
  );
}

/** Review point 25 (phase D): the institutions' cameras and their pre-alerts. A camera of an institution tells the
 * owner first; the room sees here every pre-alert, the false alarms with their reason included. */
export function CamerasPage() {
  const { t } = useTranslation();
  const fmt = useFormat();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const national = user?.identity.national ?? false;
  const [chosen, setChosen] = useState("");
  const pickId = useId();
  const gouvernorat = national ? (chosen ? Number(chosen) : null) : (user?.identity.gouvernoratCode ?? null);
  const query = useQuery({
    queryKey: streamKeys.prealerts(gouvernorat),
    queryFn: ({ signal }) => api.prealerts(gouvernorat, signal),
    refetchInterval: 15_000,
  });
  const canRegister = canRegisterCameras(user?.identity.roles ?? []);
  return (
    <div className="page cameras-page">
      <div className="page__head">
        <PageTitle icon="videocam" tone="red">
          {t("cameras.pageTitle")}
        </PageTitle>
      </div>
      <StreamsNav />
      <p className="muted">{t("cameras.intro")}</p>
      {national && (
        <div className="field">
          <label htmlFor={pickId}>{t("filters.gouvernorat")}</label>
          <select id={pickId} value={chosen} onChange={(e) => setChosen(e.target.value)}>
            <option value="">{t("streams.filters.allGouvernorats")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
      )}
      <section className="card" aria-labelledby="sec-prealerts">
        <h2 id="sec-prealerts">{t("cameras.prealerts")}</h2>
        {query.isPending && <Loading />}
        {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
        {query.isSuccess && query.data.length === 0 && <p className="muted">{t("cameras.none")}</p>}
        {query.isSuccess && query.data.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("cameras.prealerts")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("cameras.when")}</th>
                  <th scope="col">{t("cameras.org")}</th>
                  <th scope="col">{t("cameras.seen")}</th>
                  <th scope="col">{t("cameras.state")}</th>
                  <th scope="col">{t("cameras.report")}</th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((p) => (
                  <tr key={p.id} data-testid={`prealert-${p.id}`}>
                    <td>{fmt.dateTime(p.raised_at)}</td>
                    <td>
                      {p.org_name ?? "—"} {p.simulated && <SimTag />}
                    </td>
                    <td>
                      {t(`cameras.labels.${p.label}`)} · {Math.round(p.confidence * 100)}%
                    </td>
                    <td>
                      <Pill tone={STATE_TONE[p.state]}>
                        {p.state === "pending"
                          ? t("cameras.states.pending", { seconds: p.seconds_left })
                          : t(`cameras.states.${p.state}`)}
                      </Pill>
                      {p.reason && <div className="muted">{p.reason}</div>}
                    </td>
                    <td>
                      {p.report_id ? <NavLink to={`/reports/${p.report_id}`}>{t("cameras.openReport")}</NavLink> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {canRegister && gouvernorat !== null && <RegisterForm gouvernorat={gouvernorat} />}
    </div>
  );
}

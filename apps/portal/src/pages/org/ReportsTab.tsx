import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { StatusChip } from "../../components/Badges";
import { Dialog } from "../../components/Dialog";
import { BackIcon, ErrorBox, Loading } from "../../components/Feedback";
import { LocationField } from "../../components/LocationField";
import { useServices } from "../../context/services";
import { isApiError } from "../../lib/api";
import { newUuid, useFormat, useLanguage } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import { CATEGORIES, TEXT_LANGS, type Category, type GeoPoint, type Report, type TextLang } from "../../lib/types";
import { isInTunisia } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field, RequiredNote } from "./RegisterParts";

export const TEXT_MAX_LENGTH = 4000;

/** Reports made on behalf of the institution (FR-B-011), newest first, with phase 2 status labels. */
export function ReportsTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const query = useInfiniteQuery({
    queryKey: queryKeys.reports(org.id),
    queryFn: ({ pageParam, signal }) => api.orgReports(org.id, pageParam, signal),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });

  return (
    <section className="card" aria-labelledby="reports-title">
      <div className="section-head">
        <h2 id="reports-title">{t("reports.title")}</h2>
        {can("report") && (
          <Link className="btn btn--primary" to="new">
            {t("reports.new")}
          </Link>
        )}
      </div>
      <p className="muted">{t("reports.help")}</p>
      <BlockedNote action="report" />
      {query.isPending ? (
        <Loading />
      ) : query.isError ? (
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        (() => {
          const items = query.data.pages.flatMap((p) => p.items);
          if (items.length === 0) return <p className="empty">{t("reports.empty")}</p>;
          return (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t("reports.trackingCode")}</th>
                      <th scope="col">{t("reports.category")}</th>
                      <th scope="col">{t("reports.status")}</th>
                      <th scope="col">{t("reports.text")}</th>
                      <th scope="col">{t("reports.received")}</th>
                      <th scope="col">{t("reports.updated")}</th>
                      <th scope="col">{t("reports.by")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((r) => (
                      <tr key={r.id}>
                        <th scope="row" className="code" dir="ltr">
                          {r.tracking_code}
                        </th>
                        <td>{t(`category.${r.category}`)}</td>
                        <td>
                          <StatusChip status={r.status} />
                        </td>
                        <td className="text-cell">
                          <p className="clamp" dir="auto">
                            {r.text ?? "—"}
                          </p>
                        </td>
                        <td>{fmt.dateTime(r.received_at)}</td>
                        <td>{fmt.dateTime(r.updated_at)}</td>
                        <td>{r.reporter_display_name ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {query.hasNextPage && (
                <div className="load-more">
                  <button type="button" className="btn" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
                    {t("common.loadMore")}
                  </button>
                </div>
              )}
            </>
          );
        })()
      )}
    </section>
  );
}

/**
 * Charter acceptance asked when the API answers `428 consent_required` (phase 2 §2): the text comes from
 * the translation files, keyed by the version the server requires.
 */
function CharterDialog({ onAccepted, onClose }: { onAccepted: () => void; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const [checked, setChecked] = useState(false);
  const charter = useQuery({ queryKey: ["charter"], queryFn: ({ signal }) => api.charter(signal), staleTime: 0 });
  const accept = useMutation({
    mutationFn: (version: string) => api.acceptCharter(version, lang),
    onSuccess: onAccepted,
  });
  const version = charter.data?.version;
  const key = version ? `charter.versions.${version}` : null;
  const known = !!key && i18n.exists(`${key}.checkbox`);
  // From 2026-11 (phase A) the charter is the ten sections of the terms of use, as in the mobile app.
  const sections = known
    ? (t(`${key}.sections`, { returnObjects: true, defaultValue: [] }) as { title: string; body: string }[])
    : [];

  return (
    <Dialog title={t("charter.title")} onClose={onClose} wide>
      {charter.isPending ? (
        <Loading />
      ) : charter.isError ? (
        <ErrorBox error={charter.error} onRetry={() => void charter.refetch()} />
      ) : !known ? (
        <div className="alert alert--error" role="alert">
          <p>{t("charter.unknownVersion", { version })}</p>
        </div>
      ) : (
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            // The dialog is portalled but React still bubbles submit through the component tree.
            e.stopPropagation();
            if (checked && version) accept.mutate(version);
          }}
        >
          <p className="muted">{t("charter.why")}</p>
          <p className="muted">{t("charter.version", { version })}</p>
          <div className="charter-text" tabIndex={0} aria-label={t("charter.textLabel")}>
            {i18n.exists(`${key}.placeholderNotice`) && <p className="alert alert--warn">{t(`${key}.placeholderNotice`)}</p>}
            <p>{t(`${key}.intro`)}</p>
            {Array.isArray(sections) && sections.length > 0 ? (
              sections.map((s) => (
                <section key={s.title}>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                </section>
              ))
            ) : (
              <>
                <p>{t(`${key}.body`)}</p>
                <p>{t(`${key}.liability`)}</p>
              </>
            )}
          </div>
          <label className="radio">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            {t(`${key}.checkbox`)}
          </label>
          {accept.isError && <ErrorBox error={accept.error} />}
          <div className="actions actions--end">
            <button type="button" className="btn" onClick={onClose}>
              {t("common.cancel")}
            </button>
            <button type="submit" className="btn btn--primary" disabled={!checked || accept.isPending}>
              {t("charter.accept")}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

function Sent({ report, onAnother }: { report: Report; onAnother: () => void }) {
  const { t } = useTranslation();
  return (
    <section className="card notice" aria-labelledby="sent-title">
      <h2 id="sent-title">{t("reports.sentTitle")}</h2>
      <p>{t("reports.sentBody")}</p>
      <p className="tracking">
        <span className="muted">{t("reports.trackingCode")}</span> <strong className="code" dir="ltr">{report.tracking_code}</strong>
      </p>
      <div className="actions">
        <Link className="btn btn--primary" to=".." relative="path">
          {t("reports.backToList")}
        </Link>
        <button type="button" className="btn" onClick={onAnother}>
          {t("reports.another")}
        </button>
      </div>
    </section>
  );
}

/** New report on behalf of the institution (FR-A-080, FR-B-011): POST /api/v1/reports with organization_id. */
export function NewReportPage() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const lang = useLanguage();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<Category>("fire");
  const [text, setText] = useState("");
  const [textLang, setTextLang] = useState<TextLang>(lang);
  const [location, setLocation] = useState<GeoPoint | null>(org.location);
  // Idempotency key of this report: kept across retries (network, consent), renewed after success.
  const [clientUuid, setClientUuid] = useState(newUuid);
  const [askCharter, setAskCharter] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const allowed = can("report");

  const send = useMutation({
    mutationFn: () =>
      api.createReport({
        client_uuid: clientUuid,
        category,
        text: text.trim() || null,
        lang: textLang,
        location: location ?? org.location,
        created_at: new Date().toISOString(),
        organization_id: org.id,
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.reports(org.id) }),
    onError: (e) => {
      if (isApiError(e) && e.code === "consent_required") setAskCharter(true);
    },
  });

  if (send.isSuccess) {
    return (
      <Sent
        report={send.data}
        onAnother={() => {
          setText("");
          setClientUuid(newUuid());
          send.reset();
        }}
      />
    );
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!location || !isInTunisia(location)) {
      setLocationError(t("validation.outsideTunisia"));
      return;
    }
    setLocationError(null);
    send.mutate();
  }

  const consentPending = send.isError && isApiError(send.error) && send.error.code === "consent_required";

  return (
    <>
    <form className="stack" onSubmit={submit} noValidate>
      <section className="card" aria-labelledby="new-report-title">
        <p>
          <Link to=".." relative="path" className="back-link">
            <BackIcon />
            {t("reports.title")}
          </Link>
        </p>
        <h2 id="new-report-title">{t("reports.newTitle", { name: org.name })}</h2>
        <p className="alert alert--warn">{t("reports.emergencyNote")}</p>
        <RequiredNote />
        <BlockedNote action="report" />
        <div className="form-grid">
          <Field id="rp-category" label={t("reports.category")} required>
            <select id="rp-category" value={category} disabled={!allowed} onChange={(e) => setCategory(e.target.value as Category)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {t(`category.${c}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="rp-lang" label={t("reports.lang")}>
            <select id="rp-lang" value={textLang} disabled={!allowed} onChange={(e) => setTextLang(e.target.value as TextLang)}>
              {TEXT_LANGS.map((l) => (
                <option key={l} value={l}>
                  {t(`header.languages.${l}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <Field id="rp-text" label={t("reports.text")} hint={t("reports.textHint", { n: TEXT_MAX_LENGTH })}>
          <textarea
            id="rp-text"
            rows={5}
            maxLength={TEXT_MAX_LENGTH}
            value={text}
            dir="auto"
            disabled={!allowed}
            aria-describedby="rp-text-hint"
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
      </section>
      <section className="card">
        <LocationField legend={t("reports.location")} value={location} onChange={setLocation} error={locationError} />
        <button type="button" className="btn btn--small" onClick={() => setLocation(org.location)}>
          {t("reports.useOrgLocation")}
        </button>
      </section>
      <div className="card sticky-actions">
        {send.isError && !consentPending && <ErrorBox error={send.error} />}
        {consentPending && !askCharter && (
          <div className="alert alert--warn">
            <p>{t("errors.consent_required")}</p>
            <button type="button" className="btn" onClick={() => setAskCharter(true)}>
              {t("charter.read")}
            </button>
          </div>
        )}
        <div className="actions actions--end">
          <button type="submit" className="btn btn--primary" disabled={!allowed || send.isPending}>
            {t("reports.send")}
          </button>
        </div>
      </div>
    </form>
      {askCharter && (
        <CharterDialog
          onClose={() => setAskCharter(false)}
          onAccepted={() => {
            setAskCharter(false);
            send.mutate();
          }}
        />
      )}
    </>
  );
}

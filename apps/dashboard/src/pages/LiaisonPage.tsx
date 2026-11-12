import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, IconTile, Pill } from "../components/Icon";
import { ContactForm } from "../components/LiaisonContactForm";
import { PageTitle } from "../components/PageTitle";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import {
  CALL_RESULTS,
  LIAISON_CATEGORIES,
  RESULT_TONE,
  categoryLook,
  liaisonKeys,
  type CallResult,
  type ContactBody,
  type LiaisonCategory,
} from "../lib/liaison";
import { canManageIncidents } from "../lib/roles";

type Tab = "contacts" | "history" | "calls" | "followUps";
const TABS: readonly Tab[] = ["contacts", "history", "calls", "followUps"];

/**
 * The contact system (OS20, docs/phase-os20/design-os20.md): central and regional, every body, ministry or structure
 * with its officials, phones, email, place, duty hours and last update. A regional room sees its gouvernorat and the
 * national bodies and keeps its own; the central room sees every body and keeps the national ones. With the history
 * of the reports and the bodies informed, the log of the calls and the reminders to call back.
 */
export function LiaisonPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("contacts");
  return (
    <div className="page">
      <PageTitle print icon="call" tone="teal">
        {t("liaison.title")}
      </PageTitle>
      <p className="muted">{t("liaison.intro")}</p>
      <div className="aw-tabs" role="group" aria-label={t("liaison.title")}>
        {TABS.map((k) => (
          <button
            key={k}
            type="button"
            aria-pressed={tab === k}
            onClick={() => setTab(k)}
          >
            {t(`liaison.tab.${k}`)}
          </button>
        ))}
      </div>
      {tab === "contacts" && <Contacts />}
      {tab === "history" && <History />}
      {tab === "calls" && <Calls />}
      {tab === "followUps" && <FollowUps />}
    </div>
  );
}

function Contacts() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const base = useId();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const central = Boolean(user?.identity.national);
  const own = user?.identity.gouvernoratCode ?? null;
  const [gov, setGov] = useState<number | null>(null);
  const [category, setCategory] = useState<LiaisonCategory | "">("");
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const q = useDebounced(query, 250);
  const filter = { gouvernorat: central ? gov : null, category, q };
  const list = useQuery({
    queryKey: liaisonKeys.bodies(filter),
    queryFn: ({ signal }) => api.liaisonBodies(filter, signal),
  });
  return (
    <>
      <div className="liaison-filters">
        {central ? (
          <select
            aria-label={t("liaison.picker.gouvernorat")}
            value={gov ?? ""}
            onChange={(e) =>
              setGov(e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">{t("liaison.allGouvernorats")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        ) : (
          <Pill tone="navy">
            <Icon name="lockOpen" size={14} />{" "}
            {t("liaison.scope.regional", {
              gov: gouvernorats.nameOf(own) ?? "",
            })}
          </Pill>
        )}
        <select
          aria-label={t("liaison.form.category")}
          value={category}
          onChange={(e) => setCategory(e.target.value as LiaisonCategory | "")}
        >
          <option value="">{t("liaison.allCategories")}</option>
          {LIAISON_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {t(`liaison.category.${c}`)}
            </option>
          ))}
        </select>
        <input
          id={`${base}-q`}
          type="search"
          aria-label={t("liaison.picker.search")}
          placeholder={t("liaison.picker.search")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {canWrite && !adding && (
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => setAdding(true)}
          >
            <Icon name="addLocationAlt" size={18} /> {t("liaison.addBody")}
          </button>
        )}
      </div>
      <p className="muted">
        {t(
          central ? "liaison.scope.centralRule" : "liaison.scope.regionalRule",
        )}
      </p>
      {adding && (
        <section className="card">
          <ContactForm
            onCancel={() => setAdding(false)}
            onSaved={() => setAdding(false)}
          />
        </section>
      )}
      {list.isLoading && <Loading />}
      {list.isError && (
        <ErrorBox error={list.error} onRetry={() => void list.refetch()} />
      )}
      {list.data && list.data.length === 0 && (
        <p className="muted">{t("liaison.picker.none")}</p>
      )}
      <div className="liaison-bodies">
        {list.data?.map((b) => (
          <BodyCard key={b.id} body={b} canWrite={canWrite} />
        ))}
      </div>
    </>
  );
}

function BodyCard({
  body,
  canWrite,
}: {
  body: ContactBody;
  canWrite: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const refresh = () =>
    void qc.invalidateQueries({ queryKey: liaisonKeys.all });
  const archive = useMutation({
    mutationFn: () => api.liaisonArchiveBody(body.id),
    onSuccess: refresh,
  });
  const drop = useMutation({
    mutationFn: (id: string) => api.liaisonArchiveOfficial(id),
    onSuccess: refresh,
  });
  const look = categoryLook(body.category);
  const keep = canWrite && body.editable;
  return (
    <article className="card liaison-body">
      <header className="liaison-body__head">
        <IconTile name={look.icon} tone={look.tone} />
        <div className="liaison-body__title">
          <strong dir="auto">{body.name}</strong>
          <span className="muted" dir="auto">
            {[body.domain, body.address].filter(Boolean).join(" · ")}
          </span>
        </div>
        <Pill tone={look.tone}>{t(`liaison.category.${body.category}`)}</Pill>
        <Pill tone={body.gouvernorat_code ? "navy" : "red"}>
          {body.gouvernorat_code
            ? gouvernorats.nameOf(body.gouvernorat_code)
            : t("liaison.national")}
        </Pill>
        {body.kind === "internal" && (
          <Pill tone="red">{t("liaison.internal")}</Pill>
        )}
      </header>
      {body.public_phone && (
        <p className="liaison-body__public">
          {t("liaison.publicPhone")}:{" "}
          <span className="mono" dir="ltr">
            {body.public_phone}
          </span>
        </p>
      )}
      {body.officials.length === 0 ? (
        <p className="muted">{t("liaison.noOfficials")}</p>
      ) : (
        <table className="table liaison-officials">
          <thead>
            <tr>
              <th>{t("liaison.form.person")}</th>
              <th>{t("liaison.form.role")}</th>
              <th>{t("liaison.form.phone")}</th>
              <th>{t("liaison.form.email")}</th>
              <th>{t("liaison.form.duty")}</th>
              {keep && <th aria-label={t("liaison.actions")} />}
            </tr>
          </thead>
          <tbody>
            {body.officials.map((o) => (
              <tr key={o.id}>
                <td dir="auto">{o.name}</td>
                <td dir="auto">{o.role ?? "—"}</td>
                <td className="mono" dir="ltr">
                  {o.phones.join(" · ")}
                </td>
                <td dir="ltr">{o.email ?? "—"}</td>
                <td dir="auto">{o.duty ?? "—"}</td>
                {keep && (
                  <td>
                    <button
                      type="button"
                      className="btn btn--small btn--ghost"
                      disabled={drop.isPending}
                      onClick={() => drop.mutate(o.id)}
                    >
                      {t("liaison.archiveOfficial")}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <footer className="liaison-body__foot">
        <span className="muted">
          {t("liaison.updated", {
            date: fmt.dateTime(body.updated_at),
            name: body.updated_by_name ?? "—",
          })}
        </span>
        {keep ? (
          <span className="actions">
            <button
              type="button"
              className="btn btn--small"
              onClick={() => setAdding((v) => !v)}
            >
              {t("liaison.addOfficial")}
            </button>
            {body.kind !== "internal" && (
              <button
                type="button"
                className="btn btn--small btn--ghost"
                disabled={archive.isPending}
                onClick={() => archive.mutate()}
              >
                {t("liaison.archiveBody")}
              </button>
            )}
          </span>
        ) : (
          <Pill tone="slate">{t("liaison.readOnly")}</Pill>
        )}
      </footer>
      {(archive.isError || drop.isError) && (
        <ErrorBox error={archive.error ?? drop.error} />
      )}
      {adding && (
        <ContactForm
          existing={[body]}
          onCancel={() => setAdding(false)}
          onSaved={() => setAdding(false)}
        />
      )}
    </article>
  );
}

function History() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const [level, setLevel] = useState<1 | 2 | "">("");
  const q = useQuery({
    queryKey: liaisonKeys.history(level),
    queryFn: ({ signal }) => api.liaisonHistory(level, signal),
  });
  return (
    <>
      <div className="liaison-filters">
        <select
          aria-label={t("liaison.level.legend")}
          value={level}
          onChange={(e) =>
            setLevel(e.target.value ? (Number(e.target.value) as 1 | 2) : "")
          }
        >
          <option value="">{t("liaison.allLevels")}</option>
          <option value="1">{t("liaison.level.short1")}</option>
          <option value="2">{t("liaison.level.short2")}</option>
        </select>
      </div>
      {q.isLoading && <Loading />}
      {q.isError && (
        <ErrorBox error={q.error} onRetry={() => void q.refetch()} />
      )}
      {q.data && q.data.length === 0 && (
        <p className="muted">{t("liaison.history.none")}</p>
      )}
      {q.data && q.data.length > 0 && (
        <table className="table liaison-history">
          <thead>
            <tr>
              <th>{t("liaison.history.report")}</th>
              <th>{t("liaison.level.legend")}</th>
              <th>{t("liaison.history.parties")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((h) => (
              <tr key={h.incident_id}>
                <td>
                  <Link to={`/incidents/${h.incident_id}`}>
                    {h.title || t(`category.${h.category}`)}
                  </Link>
                  <div className="muted">
                    {t(`category.${h.category}`)} ·{" "}
                    {gouvernorats.nameOf(h.gouvernorat_code) ?? "—"} ·{" "}
                    {fmt.dateTime(h.opened_at)}
                  </div>
                </td>
                <td>
                  {h.level ? (
                    <Pill tone={h.level === 1 ? "slate" : "teal"}>
                      {t(`liaison.level.short${h.level}`)}
                    </Pill>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  {h.parties.length === 0 ? (
                    <span className="muted">
                      {t("liaison.history.roomOnly")}
                    </span>
                  ) : (
                    <ul className="liaison-history__parties">
                      {h.parties.map((p) => (
                        <li key={`${p.body_id}:${p.official_id ?? ""}`}>
                          <strong dir="auto">{p.body_name}</strong>
                          {p.official_name && (
                            <span dir="auto">
                              {" "}
                              · {p.official_name}
                              {p.official_role ? ` (${p.official_role})` : ""}
                            </span>
                          )}{" "}
                          {p.last_result ? (
                            <Pill tone={RESULT_TONE[p.last_result]}>
                              {t(`liaison.result.${p.last_result}`)}
                              {p.calls > 1
                                ? ` · ${t("liaison.history.calls", { n: p.calls })}`
                                : ""}
                            </Pill>
                          ) : (
                            <Pill tone="slate">
                              {t("liaison.party.notCalled")}
                            </Pill>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function Calls() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const [result, setResult] = useState<CallResult | "">("");
  const q = useQuery({
    queryKey: liaisonKeys.calls(result),
    queryFn: ({ signal }) => api.liaisonCalls(result, signal),
  });
  return (
    <>
      <div className="liaison-filters">
        <select
          aria-label={t("liaison.call.result")}
          value={result}
          onChange={(e) => setResult(e.target.value as CallResult | "")}
        >
          <option value="">{t("liaison.allResults")}</option>
          {CALL_RESULTS.map((r) => (
            <option key={r} value={r}>
              {t(`liaison.result.${r}`)}
            </option>
          ))}
        </select>
      </div>
      {q.isLoading && <Loading />}
      {q.isError && (
        <ErrorBox error={q.error} onRetry={() => void q.refetch()} />
      )}
      {q.data && q.data.length === 0 && (
        <p className="muted">{t("liaison.calls.none")}</p>
      )}
      {q.data && q.data.length > 0 && (
        <table className="table liaison-log">
          <thead>
            <tr>
              <th>{t("liaison.calls.at")}</th>
              <th>{t("liaison.history.report")}</th>
              <th>{t("liaison.calls.who")}</th>
              <th>{t("liaison.call.result")}</th>
              <th>{t("liaison.calls.detail")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((c) => (
              <tr key={c.id}>
                <td className="mono">{fmt.dateTime(c.at)}</td>
                <td>
                  <Link to={`/incidents/${c.incident_id}`}>
                    {c.incident_title ||
                      (c.incident_category
                        ? t(`category.${c.incident_category}`)
                        : "—")}
                  </Link>
                </td>
                <td dir="auto">
                  <strong>{c.body_name}</strong>
                  {c.official_name ? ` · ${c.official_name}` : ""}
                  <div className="mono muted" dir="ltr">
                    {c.number}
                  </div>
                </td>
                <td>
                  <Pill tone={RESULT_TONE[c.result]}>
                    {t(`liaison.result.${c.result}`)}
                  </Pill>
                  <div className="muted">
                    {t(`liaison.via.${c.via}`)} · {c.by_name ?? "—"}
                  </div>
                </td>
                <td dir="auto">
                  {c.promised && (
                    <div>
                      {t("liaison.call.promised")}: {c.promised}
                      {c.eta_min !== null &&
                        ` · ${t("liaison.call.etaShort", { n: c.eta_min })}`}
                    </div>
                  )}
                  {c.asked && (
                    <div className="muted">
                      {t("liaison.call.asked")}: {c.asked}
                    </div>
                  )}
                  {c.note && <div className="muted">{c.note}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

function FollowUps() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const q = useQuery({
    queryKey: liaisonKeys.followUps(),
    queryFn: ({ signal }) => api.liaisonFollowUps(undefined, signal),
    refetchInterval: 30_000,
  });
  const done = useMutation({
    mutationFn: (id: string) => api.liaisonFollowUpDone(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: liaisonKeys.all }),
  });
  return (
    <>
      {q.isLoading && <Loading />}
      {q.isError && (
        <ErrorBox error={q.error} onRetry={() => void q.refetch()} />
      )}
      {done.isError && <ErrorBox error={done.error} />}
      {q.data && q.data.length === 0 && (
        <p className="muted">{t("liaison.followUps.none")}</p>
      )}
      <ul className="liaison-due">
        {q.data?.map((c) => (
          <li
            key={c.id}
            className={
              c.follow_up_due
                ? "liaison-due__item liaison-due__item--now"
                : "liaison-due__item"
            }
          >
            <Icon name="schedule" size={18} />
            <span>
              <strong dir="auto">{c.body_name}</strong>
              {c.official_name ? ` · ${c.official_name}` : ""} ·{" "}
              <Link to={`/incidents/${c.incident_id}`}>
                {c.incident_title ||
                  (c.incident_category
                    ? t(`category.${c.incident_category}`)
                    : "—")}
              </Link>
              <span className="muted">
                {" "}
                · {c.follow_up_at ? fmt.time(c.follow_up_at) : ""}
              </span>
            </span>
            {c.follow_up_due && (
              <Pill tone="red">{t("liaison.followUps.dueNow")}</Pill>
            )}
            {canWrite && (
              <button
                type="button"
                className="btn btn--small"
                disabled={done.isPending}
                onClick={() => done.mutate(c.id)}
              >
                {t("liaison.followUps.done")}
              </button>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

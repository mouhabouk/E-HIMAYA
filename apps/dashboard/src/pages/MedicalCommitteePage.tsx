import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import {
  COMMITTEE_TERMS,
  committeeKeys,
  doctorKeys,
  type CommitteeMember,
  type MedicalCommittee,
  type StaffDoctor,
} from "../lib/doctorsApi";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import { SpecialtyList } from "./DoctorsPage";
import { PageTitle } from "../components/PageTitle";

function useCommitteeUpdate() {
  const qc = useQueryClient();
  return (committee: MedicalCommittee) => {
    qc.setQueryData(committeeKeys.all, committee);
    void qc.invalidateQueries({ queryKey: committeeKeys.all, predicate: (q) => q.queryKey.length > 1 });
    void qc.invalidateQueries({ queryKey: doctorKeys.all });
  };
}

function TermSelect({ value, onChange }: { value: number; onChange: (months: number) => void }) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{t("medicalCommittee.term")}</label>
      <select id={id} value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {COMMITTEE_TERMS.map((m) => (
          <option key={m} value={m}>
            {t(`medicalCommittee.months.${m}`)}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Renew or revoke one member; a revocation needs a reason (e-mailed to the doctor). */
function MemberActions({ member }: { member: CommitteeMember }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const update = useCommitteeUpdate();
  const reasonId = useId();
  const [months, setMonths] = useState(12);
  const [revoking, setRevoking] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState(false);
  const renew = useMutation({ mutationFn: () => api.appointMember(member.id, months), onSuccess: update });
  const revoke = useMutation({ mutationFn: () => api.revokeMember(member.id, reason), onSuccess: update });
  const submitRevoke = (e: SyntheticEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setReasonError(true);
      return;
    }
    revoke.mutate();
  };
  const error = renew.error ?? revoke.error;
  return (
    <div>
      {!revoking ? (
        <div className="actions">
          <TermSelect value={months} onChange={setMonths} />
          <button type="button" className="btn" disabled={renew.isPending} onClick={() => renew.mutate()}>
            {t("medicalCommittee.renew")}
          </button>
          <button type="button" className="btn btn--danger" onClick={() => setRevoking(true)}>
            {t("medicalCommittee.revoke")}
          </button>
        </div>
      ) : (
        <form onSubmit={submitRevoke} noValidate>
          <div className={`field${reasonError ? " field--invalid" : ""}`}>
            <label htmlFor={reasonId}>{t("medicalCommittee.revokeReason")}</label>
            <textarea
              id={reasonId}
              rows={2}
              maxLength={1000}
              dir="auto"
              value={reason}
              aria-invalid={reasonError || undefined}
              aria-describedby={reasonError ? `${reasonId}-error` : undefined}
              onChange={(e) => setReason(e.target.value)}
            />
            {reasonError && (
              <span id={`${reasonId}-error`} className="field__error">
                {t("volunteers.review.reasonRequired")}
              </span>
            )}
          </div>
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={revoke.isPending}>
              {t("medicalCommittee.confirmRevoke")}
            </button>
            <button type="button" className="btn" onClick={() => setRevoking(false)}>
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
    </div>
  );
}

function Candidates({ full }: { full: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const update = useCommitteeUpdate();
  const searchId = useId();
  const [text, setText] = useState("");
  const [months, setMonths] = useState(12);
  const q = useDebounced(text, 350);
  const query = useQuery({
    queryKey: committeeKeys.candidates(q),
    queryFn: ({ signal }) => api.committeeCandidates(q, signal),
  });
  const appoint = useMutation({
    mutationFn: (doctor: StaffDoctor) => api.appointMember(doctor.id, months),
    onSuccess: update,
  });
  return (
    <section className="card" aria-labelledby="sec-candidates">
      <h2 id="sec-candidates">{t("medicalCommittee.candidates")}</h2>
      <p className="muted">{t("medicalCommittee.candidatesHelp")}</p>
      <div className="filters__row">
        <div className="field field--search">
          <label htmlFor={searchId}>{t("doctors.search")}</label>
          <input
            id={searchId}
            type="search"
            value={text}
            maxLength={100}
            autoComplete="off"
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <TermSelect value={months} onChange={setMonths} />
      </div>
      {full && <p className="alert alert--warn">{t("medicalCommittee.full")}</p>}
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && query.data.length === 0 && <p className="empty">{t("medicalCommittee.noCandidate")}</p>}
      {query.isSuccess && query.data.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("medicalCommittee.candidates")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("volunteers.columns.name")}</th>
                <th scope="col">{t("doctors.columns.specialties")}</th>
                <th scope="col">{t("doctors.columns.workplace")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("medicalCommittee.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((d) => (
                <tr key={d.id}>
                  <td dir="auto">{d.full_name ?? t("doctors.unnamed")}</td>
                  <td>
                    <SpecialtyList specialties={d.specialties} />
                  </td>
                  <td dir="auto">
                    {d.workplace}
                    {d.cp_unit && <div className="cell-sub">{d.cp_unit}</div>}
                  </td>
                  <td>{gouvernorats.nameOf(d.gouvernorat_code)}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn--primary"
                      disabled={full || appoint.isPending}
                      onClick={() => appoint.mutate(d)}
                      aria-label={t("medicalCommittee.appointName", { name: d.full_name ?? t("doctors.unnamed") })}
                    >
                      {t("medicalCommittee.appoint")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {appoint.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(appoint.error))}
        </p>
      )}
    </section>
  );
}

/**
 * The national medical committee (docs/phase-c/design-medical-axis.md §11): the system administrator appoints approved
 * Civil Protection doctors for a fixed term. From phase C1-b the phone locks every medical file for its members too.
 */
export function MedicalCommitteePage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const query = useQuery({ queryKey: committeeKeys.all, queryFn: ({ signal }) => api.medicalCommittee(signal) });

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="groups" tone="purple">{t("medicalCommittee.title")}</PageTitle>
      </div>
      <p className="muted">{t("medicalCommittee.intro")}</p>
      <ul className="muted">
        <li>{t("medicalCommittee.rules.who")}</li>
        <li>{t("medicalCommittee.rules.keys")}</li>
        <li>{t("medicalCommittee.rules.audit")}</li>
      </ul>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && (
        <>
          <section className="card" aria-labelledby="sec-members">
            <h2 id="sec-members">
              {t("medicalCommittee.members")}{" "}
              <span className="muted">
                {t("medicalCommittee.seats", { count: query.data.members.length, max: query.data.max_members })}
              </span>
            </h2>
            {query.data.members.length === 0 ? (
              <p className="empty">{t("medicalCommittee.noMember")}</p>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <caption className="visually-hidden">{t("medicalCommittee.members")}</caption>
                  <thead>
                    <tr>
                      <th scope="col">{t("volunteers.columns.name")}</th>
                      <th scope="col">{t("doctors.columns.workplace")}</th>
                      <th scope="col">{t("filters.gouvernorat")}</th>
                      <th scope="col">{t("medicalCommittee.since")}</th>
                      <th scope="col">{t("medicalCommittee.until")}</th>
                      <th scope="col">{t("medicalCommittee.actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.members.map((m) => (
                      <tr key={m.id}>
                        <td dir="auto">{m.full_name ?? t("doctors.unnamed")}</td>
                        <td dir="auto">
                          {m.workplace}
                          {m.cp_unit && <div className="cell-sub">{m.cp_unit}</div>}
                        </td>
                        <td>{gouvernorats.nameOf(m.gouvernorat_code)}</td>
                        <td>
                          <time dateTime={m.committee_since}>{fmt.date(m.committee_since)}</time>
                        </td>
                        <td>
                          {m.committee_until && <time dateTime={m.committee_until}>{fmt.date(m.committee_until)}</time>}
                        </td>
                        <td>
                          <MemberActions member={m} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <Candidates full={query.data.members.length >= query.data.max_members} />
        </>
      )}
    </div>
  );
}

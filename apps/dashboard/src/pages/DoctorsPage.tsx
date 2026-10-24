import { useInfiniteQuery } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import {
  DOCTOR_KINDS,
  doctorKeys,
  SPECIALTIES,
  type DoctorFilters,
  type Specialty,
  type StaffDoctor,
} from "../lib/doctorsApi";
import { useDebounced, useFormat, useGouvernorats } from "../lib/hooks";
import { VOLUNTEER_STATUSES } from "../lib/opsTypes";
import { VolunteerStatusChip } from "./VolunteersPage";

export function SpecialtyList({ specialties }: { specialties: readonly Specialty[] }) {
  const { t } = useTranslation();
  return (
    <ul className="tags" aria-label={t("doctors.columns.specialties")}>
      {specialties.map((s) => (
        <li key={s} className="tag">
          {t(`doctors.specialty.${s}`)}
        </li>
      ))}
    </ul>
  );
}

export function AvailableTag({ doctor }: { doctor: Pick<StaffDoctor, "available"> }) {
  const { t } = useTranslation();
  return doctor.available ? (
    <span className="tag tag--ready">{t("doctors.available")}</span>
  ) : (
    <span className="muted">{t("doctors.notAvailable")}</span>
  );
}

const EMPTY: DoctorFilters = {
  status: "",
  kind: "",
  specialty: "",
  gouvernorat_code: null,
  q: "",
};

/**
 * Phase C1-a (docs/phase-c/design-medical-axis.md §2): doctors who registered from the app, pending registrations
 * first. The medical coordinator checks the registration number before the doctor receives any medical file.
 */
export function DoctorsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const national = user?.identity.national ?? false;
  const ids = {
    status: useId(),
    kind: useId(),
    specialty: useId(),
    gouv: useId(),
    q: useId(),
  };
  const [filters, setFilters] = useState<DoctorFilters>(EMPTY);
  const [text, setText] = useState("");
  const q = useDebounced(text, 350);
  const effective = useMemo(() => ({ ...filters, q }), [filters, q]);
  const patch = (p: Partial<DoctorFilters>) => setFilters((f) => ({ ...f, ...p }));

  const query = useInfiniteQuery({
    queryKey: doctorKeys.list(effective),
    queryFn: ({ pageParam, signal }) => api.doctors(effective, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("doctors.title")}</h1>
      </div>
      <p className="muted">{t("doctors.intro")}</p>

      <section className="filters card" aria-label={t("doctors.filters")}>
        <div className="field field--search">
          <label htmlFor={ids.q}>{t("doctors.search")}</label>
          <input
            id={ids.q}
            type="search"
            value={text}
            maxLength={100}
            autoComplete="off"
            onChange={(e) => setText(e.target.value)}
          />
        </div>
        <div className="filters__row">
          <div className="field">
            <label htmlFor={ids.status}>{t("volunteers.columns.status")}</label>
            <select
              id={ids.status}
              value={filters.status ?? ""}
              onChange={(e) => patch({ status: e.target.value as DoctorFilters["status"] })}
            >
              <option value="">{t("volunteers.filters.any")}</option>
              {VOLUNTEER_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`volunteers.status.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.kind}>{t("doctors.columns.kind")}</label>
            <select
              id={ids.kind}
              value={filters.kind ?? ""}
              onChange={(e) => patch({ kind: e.target.value as DoctorFilters["kind"] })}
            >
              <option value="">{t("volunteers.filters.any")}</option>
              {DOCTOR_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`doctors.kind.${k}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.specialty}>{t("doctors.columns.specialties")}</label>
            <select
              id={ids.specialty}
              value={filters.specialty ?? ""}
              onChange={(e) =>
                patch({
                  specialty: e.target.value as DoctorFilters["specialty"],
                })
              }
            >
              <option value="">{t("volunteers.filters.any")}</option>
              {SPECIALTIES.map((s) => (
                <option key={s} value={s}>
                  {t(`doctors.specialty.${s}`)}
                </option>
              ))}
            </select>
          </div>
          {national && (
            <div className="field">
              <label htmlFor={ids.gouv}>{t("filters.gouvernorat")}</label>
              <select
                id={ids.gouv}
                value={filters.gouvernorat_code ?? ""}
                onChange={(e) =>
                  patch({
                    gouvernorat_code: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">{t("filters.allGouvernorats")}</option>
                {gouvernorats.list.map((g) => (
                  <option key={g.code} value={g.code}>
                    {gouvernorats.nameOf(g.code)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </section>

      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("doctors.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("doctors.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("volunteers.columns.name")}</th>
                <th scope="col">{t("volunteers.columns.status")}</th>
                <th scope="col">{t("doctors.columns.kind")}</th>
                <th scope="col">{t("doctors.columns.specialties")}</th>
                <th scope="col">{t("doctors.columns.workplace")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("doctors.columns.available")}</th>
                <th scope="col">{t("volunteers.columns.submittedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link to={`/doctors/${encodeURIComponent(d.id)}`} dir="auto">
                      {d.full_name ?? t("doctors.unnamed")}
                    </Link>
                  </td>
                  <td>
                    <VolunteerStatusChip status={d.status} />
                  </td>
                  <td>{t(`doctors.kind.${d.kind}`)}</td>
                  <td>
                    <SpecialtyList specialties={d.specialties} />
                  </td>
                  <td dir="auto">
                    {d.workplace}
                    {d.cp_unit && <div className="cell-sub">{d.cp_unit}</div>}
                  </td>
                  <td>{gouvernorats.nameOf(d.gouvernorat_code)}</td>
                  <td>
                    <AvailableTag doctor={d} />
                  </td>
                  <td>
                    <time dateTime={d.submitted_at}>{fmt.date(d.submitted_at)}</time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {query.hasNextPage && (
        <div className="load-more">
          <button
            type="button"
            className="btn"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage ? t("common.loading") : t("reports.loadMore")}
          </button>
        </div>
      )}
    </div>
  );
}

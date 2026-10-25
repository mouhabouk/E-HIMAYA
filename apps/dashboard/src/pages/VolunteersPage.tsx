import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Suspense, useCallback, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import type { HeatPoint, MapPoi } from "../components/MapView";
import { MapLegend } from "../components/OrgBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import type { BBox } from "../lib/filters";
import { useDebounced, useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import { opsKeys } from "../lib/opsApi";
import {
  SKILLS,
  VOLUNTEER_STATUSES,
  type Skill,
  type StaffVolunteer,
  type VolunteerFilters,
  type VolunteerStatus,
} from "../lib/opsTypes";
import { PageTitle } from "../components/PageTitle";

export function VolunteerStatusChip({ status }: { status: VolunteerStatus }) {
  const { t } = useTranslation();
  return <span className={`chip chip--volunteer-${status}`}>{t(`volunteers.status.${status}`)}</span>;
}

export function SkillList({ skills }: { skills: readonly Skill[] }) {
  const { t } = useTranslation();
  return (
    <ul className="tags" aria-label={t("volunteers.columns.skills")}>
      {skills.map((s) => (
        <li key={s} className="tag">
          {t(`volunteers.skill.${s}`)}
        </li>
      ))}
    </ul>
  );
}

export function ReadyTag({ volunteer }: { volunteer: Pick<StaffVolunteer, "ready" | "ready_until"> }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  if (!volunteer.ready) return <span className="muted">{t("volunteers.notReady")}</span>;
  return (
    <span className="tag tag--ready">
      {volunteer.ready_until
        ? t("volunteers.readyUntil", { time: fmt.time(volunteer.ready_until) })
        : t("volunteers.ready")}
    </span>
  );
}

/** Layer «متطوعون حسب الاختصاص»: ready volunteers as points over a readiness heat map. */
function ReadinessMap() {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const fmt = useFormat();
  const navigate = useNavigate();
  const skillId = useId();
  const [skill, setSkill] = useState<Skill | "">("");
  const [rawBBox, setRawBBox] = useState<BBox | null>(null);
  const bbox = useDebounced(rawBBox, 400);
  const [initialBounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const query = useQuery({
    queryKey: bbox ? opsKeys.volunteersMap(bbox, skill) : ["volunteers-map", "pending"],
    enabled: bbox !== null,
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) => {
      if (!bbox) throw new Error("no bbox");
      return api.volunteersMap(bbox, skill, signal);
    },
  });
  const features = useMemo(() => query.data?.features ?? [], [query.data]);
  const pois = useMemo<MapPoi[]>(
    () =>
      features.map((f) => ({
        id: f.properties.id,
        lon: f.geometry.coordinates[0],
        lat: f.geometry.coordinates[1],
        kind: "volunteer" as const,
        title: f.properties.full_name ?? t("ops.volunteer"),
        subtitle: [
          f.properties.skills.map((s) => t(`volunteers.skill.${s}`)).join(t("common.listSeparator")),
          f.properties.ready_until ? t("volunteers.readyUntil", { time: fmt.time(f.properties.ready_until) }) : null,
        ]
          .filter(Boolean)
          .join(" · "),
        href: `/volunteers/${encodeURIComponent(f.properties.id)}`,
      })),
    [features, t, fmt],
  );
  const heat = useMemo<HeatPoint[]>(
    () => features.map((f) => ({ lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1] })),
    [features],
  );
  const onOpenPoi = useCallback((href: string) => void navigate(href), [navigate]);
  return (
    <section className="card" aria-labelledby="sec-readiness">
      <h2 id="sec-readiness">{t("volunteers.map.title")}</h2>
      <p className="muted">{t("volunteers.map.privacy")}</p>
      <div className="map-layers">
        <div className="field">
          <label htmlFor={skillId}>{t("volunteers.columns.skills")}</label>
          <select id={skillId} value={skill} onChange={(e) => setSkill(e.target.value as Skill | "")}>
            <option value="">{t("volunteers.filters.any")}</option>
            {SKILLS.map((s) => (
              <option key={s} value={s}>
                {t(`volunteers.skill.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <span className="muted" role="status" aria-live="polite">
          {query.isFetching ? t("common.loading") : t("volunteers.map.count", { count: fmt.number(pois.length) })}
        </span>
        <MapLegend items={[{ kind: "volunteer", label: t("volunteers.map.legend") }]} />
      </div>
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      <Suspense fallback={<Loading />}>
        <LazyMapView
          className="map"
          markers={[]}
          bounds={initialBounds}
          ariaLabel={t("volunteers.map.label")}
          onBoundsChange={setRawBBox}
          styleUrl={mapStyleUrl}
          dir={directionOf(lang)}
          pois={pois}
          poiOpenLabel={t("volunteers.open")}
          onOpenPoi={onOpenPoi}
          heat={heat}
        />
      </Suspense>
    </section>
  );
}

const EMPTY: VolunteerFilters = { status: "", skill: "", gouvernorat_code: null, ready: null, q: "" };

/** FR-C-04: the volunteer network in the user's scope (applications first), with the readiness map. */
export function VolunteersPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const national = user?.identity.national ?? false;
  const ids = { status: useId(), skill: useId(), ready: useId(), gouv: useId(), q: useId() };
  const [filters, setFilters] = useState<VolunteerFilters>(EMPTY);
  const [text, setText] = useState("");
  const q = useDebounced(text, 350);
  const effective = useMemo(() => ({ ...filters, q }), [filters, q]);
  const patch = (p: Partial<VolunteerFilters>) => setFilters((f) => ({ ...f, ...p }));

  const query = useInfiniteQuery({
    queryKey: opsKeys.volunteers(effective),
    queryFn: ({ pageParam, signal }) => api.volunteers(effective, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
  });
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="volunteerActivism" tone="green">{t("volunteers.title")}</PageTitle>
      </div>
      <p className="muted">{t("volunteers.intro")}</p>

      <section className="filters card" aria-label={t("volunteers.filters.title")}>
        <div className="field field--search">
          <label htmlFor={ids.q}>{t("volunteers.filters.search")}</label>
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
              onChange={(e) => patch({ status: e.target.value as VolunteerFilters["status"] })}
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
            <label htmlFor={ids.skill}>{t("volunteers.columns.skills")}</label>
            <select
              id={ids.skill}
              value={filters.skill ?? ""}
              onChange={(e) => patch({ skill: e.target.value as VolunteerFilters["skill"] })}
            >
              <option value="">{t("volunteers.filters.any")}</option>
              {SKILLS.map((s) => (
                <option key={s} value={s}>
                  {t(`volunteers.skill.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={ids.ready}>{t("volunteers.columns.ready")}</label>
            <select
              id={ids.ready}
              value={filters.ready === null || filters.ready === undefined ? "" : String(filters.ready)}
              onChange={(e) => patch({ ready: e.target.value === "" ? null : e.target.value === "true" })}
            >
              <option value="">{t("volunteers.filters.any")}</option>
              <option value="true">{t("volunteers.ready")}</option>
              <option value="false">{t("volunteers.notReady")}</option>
            </select>
          </div>
          {national && (
            <div className="field">
              <label htmlFor={ids.gouv}>{t("filters.gouvernorat")}</label>
              <select
                id={ids.gouv}
                value={filters.gouvernorat_code ?? ""}
                onChange={(e) => patch({ gouvernorat_code: e.target.value ? Number(e.target.value) : null })}
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
      {query.isSuccess && items.length === 0 && <p className="card empty">{t("volunteers.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap card">
          <table className="table">
            <caption className="visually-hidden">{t("volunteers.caption")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("volunteers.columns.name")}</th>
                <th scope="col">{t("volunteers.columns.status")}</th>
                <th scope="col">{t("volunteers.columns.skills")}</th>
                <th scope="col">{t("volunteers.columns.availability")}</th>
                <th scope="col">{t("filters.gouvernorat")}</th>
                <th scope="col">{t("volunteers.columns.ready")}</th>
                <th scope="col">{t("volunteers.columns.submittedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((v) => (
                <tr key={v.id}>
                  <td>
                    <Link to={`/volunteers/${encodeURIComponent(v.id)}`} dir="auto">
                      {v.full_name ?? t("ops.volunteer")}
                    </Link>
                    {v.phone && (
                      <div className="cell-sub" dir="ltr">
                        {v.phone}
                      </div>
                    )}
                  </td>
                  <td>
                    <VolunteerStatusChip status={v.status} />
                  </td>
                  <td>
                    <SkillList skills={v.skills} />
                  </td>
                  <td>{t(`volunteers.availability.${v.availability}`)}</td>
                  <td>{gouvernorats.nameOf(v.gouvernorat_code)}</td>
                  <td>
                    <ReadyTag volunteer={v} />
                  </td>
                  <td>
                    <time dateTime={v.submitted_at}>{fmt.date(v.submitted_at)}</time>
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

      <ReadinessMap />
    </div>
  );
}

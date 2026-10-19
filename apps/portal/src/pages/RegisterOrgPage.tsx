import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { OrgStatusBadge } from "../components/Badges";
import { BackIcon, ErrorBox, ForwardIcon } from "../components/Feedback";
import {
  CARD_SECTIONS,
  CardSectionFields,
  draftToCard,
  emptyDraft,
  fieldOfServerError,
  sectionOf,
  validateDraft,
  type CardDraft,
  type DraftErrors,
} from "../components/OrgCardFields";
import { useServices } from "../context/services";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { queryKeys } from "../lib/portalApi";
import type { Organization } from "../lib/types";

const STEPS = [...CARD_SECTIONS, "review"] as const;
type Step = (typeof STEPS)[number];

function Review({ draft }: { draft: CardDraft }) {
  const { t } = useTranslation();
  const card = draftToCard(draft);
  const fmt = useFormat();
  const rows: [string, string][] = [
    [t("org.name"), card.name],
    [t("org.kind"), t(`kinds.${card.kind}`)],
    [t(`identifierTypes.${card.identifier_type}`), card.identifier],
    [t("org.activitySector"), card.activity_sector ?? "—"],
    [t("org.activityType"), card.activity_type ?? "—"],
    [t("org.capacity"), fmt.number(card.capacity)],
    [t("org.floors"), fmt.number(card.floors)],
    [t("org.heightM"), fmt.number(card.height_m)],
    [t("org.receivesPublic"), card.receives_public ? t("common.yes") : t("common.no")],
    [t("org.address"), card.address],
    [t("org.location"), `${fmt.number(card.location.lat)}, ${fmt.number(card.location.lon)}`],
    [t("org.managerName"), card.manager.full_name],
    [t("org.managerPhone"), card.manager.phone],
    [t("org.managerEmail"), card.manager.email ?? "—"],
    [t("org.contactEmail"), card.contact_email ?? "—"],
    [t("org.contactPhone"), card.contact_phone ?? "—"],
  ];
  return (
    <dl className="fields">
      {rows.map(([k, v]) => (
        <div key={k} className="fields__row">
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function PendingReview({ org }: { org: Organization }) {
  const { t } = useTranslation();
  const { nameOf } = useGouvernorats();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <section className="card notice page--narrow" aria-labelledby="pending-title">
      <h1 id="pending-title" ref={heading} tabIndex={-1}>
        {t("register.doneTitle")}
      </h1>
      <p>
        <OrgStatusBadge status={org.status} />
      </p>
      <p>{t("register.doneBody", { name: org.name })}</p>
      <dl className="fields">
        <dt>{t("org.gouvernorat")}</dt>
        <dd>{nameOf(org.gouvernorat_code) ?? t("common.notAvailable")}</dd>
        <dt>{t("org.identifier")}</dt>
        <dd className="code">{org.identifier}</dd>
      </dl>
      <p className="muted">{t("register.doneNext")}</p>
      <div className="actions">
        <Link className="btn btn--primary" to={`/orgs/${encodeURIComponent(org.id)}`}>
          {t("register.openWorkspace")}
          <ForwardIcon />
        </Link>
        <Link className="btn" to="/orgs/mine">
          {t("nav.myOrgs")}
        </Link>
      </div>
    </section>
  );
}

/** "Register an institution" wizard (FR-B-001, FR-B-002): identity, building, location, contacts, review. */
export function RegisterOrgPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<CardDraft>(emptyDraft);
  const [errors, setErrors] = useState<DraftErrors>({});
  const [step, setStep] = useState<Step>("identity");
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    heading.current?.focus();
  }, [step]);

  const create = useMutation({
    mutationFn: () => api.createOrg(draftToCard(draft)),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs }),
    onError: (e) => {
      const placed = fieldOfServerError(e, draft);
      if (placed) {
        setErrors({ [placed.field]: placed.key });
        setStep(sectionOf(placed.field));
      }
    },
  });

  if (create.isSuccess) return <PendingReview org={create.data} />;

  const index = STEPS.indexOf(step);
  const placedError = create.isError && fieldOfServerError(create.error, draft);

  function next(e: SubmitEvent) {
    e.preventDefault();
    if (step === "review") {
      const all = validateDraft(draft);
      const firstBad = Object.keys(all)[0] as keyof CardDraft | undefined;
      if (firstBad) {
        setErrors(all);
        setStep(sectionOf(firstBad));
        return;
      }
      create.mutate();
      return;
    }
    const found = validateDraft(draft, [step]);
    setErrors(found);
    if (Object.keys(found).length === 0) setStep(STEPS[index + 1] ?? "review");
  }

  return (
    <div className="page page--narrow">
      <div className="page__head">
        <h1>{t("register.title")}</h1>
      </div>
      <ol className="steps" aria-label={t("register.progress")}>
        {STEPS.map((s, i) => (
          <li key={s} className={i < index ? "steps__done" : undefined} aria-current={s === step ? "step" : undefined}>
            <span className="steps__n" aria-hidden="true">
              {i + 1}
            </span>
            {t(`register.steps.${s}`)}
          </li>
        ))}
      </ol>
      <form className="card form" onSubmit={next} noValidate>
        <h2 ref={heading} tabIndex={-1}>
          {t("register.stepTitle", { n: index + 1, total: STEPS.length, title: t(`register.steps.${step}`) })}
        </h2>
        <p className="muted">{t(`register.help.${step}`)}</p>
        {step === "review" ? (
          <Review draft={draft} />
        ) : (
          <CardSectionFields
            section={step}
            draft={draft}
            errors={errors}
            onChange={(patch) => {
              setDraft((d) => ({ ...d, ...patch }));
              setErrors((old) =>
                Object.fromEntries(Object.entries(old).filter(([k]) => !(k in patch))),
              );
            }}
          />
        )}
        {create.isError && !placedError && step === "review" && <ErrorBox error={create.error} />}
        <div className="actions actions--between">
          {index > 0 ? (
            <button type="button" className="btn" onClick={() => setStep(STEPS[index - 1] ?? "identity")}>
              <BackIcon />
              {t("common.back")}
            </button>
          ) : (
            <Link className="btn" to="/orgs/mine">
              {t("common.cancel")}
            </Link>
          )}
          <button type="submit" className="btn btn--primary" disabled={create.isPending}>
            {step === "review" ? t("register.submit") : t("common.next")}
            {step !== "review" && <ForwardIcon />}
          </button>
        </div>
      </form>
    </div>
  );
}

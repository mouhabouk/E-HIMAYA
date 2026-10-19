import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox } from "../../components/Feedback";
import {
  CARD_SECTIONS,
  CardSectionFields,
  draftFromCard,
  draftToCard,
  fieldOfServerError,
  validateDraft,
  type CardDraft,
  type DraftErrors,
} from "../../components/OrgCardFields";
import { useServices } from "../../context/services";
import { isApiError } from "../../lib/api";
import { useGouvernorats } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import type { Organization } from "../../lib/types";
import { normalizeIdentifier } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";

/** Card editor (FR-B-002) with optimistic concurrency on `version` (`409 version_conflict`). */
export function CardTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const queryClient = useQueryClient();
  const { nameOf } = useGouvernorats();
  // The draft and the version it was based on (kept even if the cached org is refreshed meanwhile).
  const [base, setBase] = useState<Organization>(org);
  const [draft, setDraft] = useState<CardDraft>(() => draftFromCard(org));
  const [errors, setErrors] = useState<DraftErrors>({});
  const [saved, setSaved] = useState(false);
  const editable = can("editCard");

  const save = useMutation({
    mutationFn: () => api.updateOrg(org.id, draftToCard(draft), base.version),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.org(org.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs });
      setBase(updated);
      setDraft(draftFromCard(updated));
      setSaved(true);
    },
    onError: (e) => {
      const placed = fieldOfServerError(e, draft);
      if (placed) setErrors({ [placed.field]: placed.key });
    },
  });

  const reload = useMutation({
    mutationFn: () => api.org(org.id),
    onSuccess: (fresh) => {
      queryClient.setQueryData(queryKeys.org(org.id), fresh);
      setBase(fresh);
      setDraft(draftFromCard(fresh));
      setErrors({});
      save.reset();
    },
  });

  const conflict = save.isError && isApiError(save.error) && save.error.code === "version_conflict";
  const placed = save.isError && fieldOfServerError(save.error, draft);
  const sendsBackToReview =
    base.status === "active" &&
    (draft.name.trim() !== base.name || normalizeIdentifier(draft.identifier) !== base.identifier || draft.identifier_type !== base.identifier_type);

  function submit(e: SubmitEvent) {
    e.preventDefault();
    setSaved(false);
    const found = validateDraft(draft);
    setErrors(found);
    if (Object.keys(found).length === 0) save.mutate();
  }

  return (
    <form className="stack" onSubmit={submit} noValidate>
      <BlockedNote action="editCard" />
      {CARD_SECTIONS.map((section) => (
        <section key={section} className="card" aria-labelledby={`card-${section}-title`}>
          <h2 id={`card-${section}-title`}>{t(`register.steps.${section}`)}</h2>
          <CardSectionFields
            section={section}
            draft={draft}
            errors={errors}
            disabled={!editable}
            onChange={(patch) => {
              setSaved(false);
              setDraft((d) => ({ ...d, ...patch }));
            }}
          />
          {section === "location" && (
            <p className="muted">
              {t("card.gouvernoratFromServer", { name: nameOf(base.gouvernorat_code) ?? t("common.notAvailable") })}
            </p>
          )}
        </section>
      ))}
      {editable && (
        <div className="card sticky-actions">
          {sendsBackToReview && (
            <div className="alert alert--warn" role="status">
              <p>{t("card.backToReview")}</p>
            </div>
          )}
          {conflict ? (
            <div className="alert alert--error" role="alert">
              <p>{t("errors.version_conflict")}</p>
              <p>{t("card.conflictHelp")}</p>
              <button type="button" className="btn" disabled={reload.isPending} onClick={() => reload.mutate()}>
                {t("card.reload")}
              </button>
            </div>
          ) : (
            save.isError && !placed && <ErrorBox error={save.error} />
          )}
          {placed && (
            <div className="alert alert--error" role="alert">
              <p>{t(placed.key)}</p>
            </div>
          )}
          {reload.isError && <ErrorBox error={reload.error} />}
          {saved && (
            <p className="alert alert--ok" role="status">
              {t("card.saved")}
            </p>
          )}
          <div className="actions actions--end">
            <button
              type="button"
              className="btn"
              onClick={() => {
                setDraft(draftFromCard(base));
                setErrors({});
              }}
            >
              {t("card.discard")}
            </button>
            <button type="submit" className="btn btn--primary" disabled={save.isPending || conflict}>
              {t("common.save")}
            </button>
          </div>
        </div>
      )}
    </form>
  );
}

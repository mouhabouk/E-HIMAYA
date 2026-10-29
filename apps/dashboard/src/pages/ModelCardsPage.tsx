// covers: L5 (docs/phase-l/design-l5.md §4.1 and §4.2, item 9): the model cards, their figures by condition and
// language with small samples flagged, the PDF, the committee's approval of the thresholds (AI-01), and the drowning
// risk model kept in shadow, trained on [SIM] days.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { PageTitle } from "../components/PageTitle";
import { RequiredNote } from "../components/PhaseASettings";
import { SimTag } from "../components/StreamBits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import { saveDownload } from "../lib/layersApi";
import {
  MAX_DECISION_NOTE,
  MAX_REFERENCE,
  modelCardKeys,
  type MeasureTable,
  type ModelCard,
  type ModelCards,
  type ModelStatus,
} from "../lib/modelCards";

const STATUS_TONE: Record<ModelStatus, string> = {
  approved: "tone-green",
  pending: "tone-amber",
  changed: "tone-amber",
  withdrawn: "tone-red",
  shadow: "tone-slate",
};

function Failure({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p role="alert" className="field__error">
      {t(errorMessageKey(error))}
    </p>
  );
}

function Measure({ table }: { table: MeasureTable }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const small = new Set(table.small_rows);
  return (
    <div className="model-card__measure">
      <h4>
        {table.title}
        {table.simulated && (
          <>
            {" "}
            <SimTag label={t("modelCards.simulated")} />
          </>
        )}
      </h4>
      {table.measured_on && (
        <p className="muted">{t("modelCards.measuredOn", { date: fmt.date(`${table.measured_on}T12:00:00Z`) })}</p>
      )}
      {table.rows.length > 0 && (
        <div className="table-wrap">
          <table className="table table--compact">
            <caption className="visually-hidden">{table.title}</caption>
            <thead>
              <tr>
                {table.columns.map((c, i) => (
                  <th key={i} scope="col">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i} className={small.has(i) ? "model-card__small" : undefined}>
                  {row.map((cell, j) =>
                    j === 0 ? (
                      <th key={j} scope="row">
                        {cell}
                        {small.has(i) && <span className="tag tag--small">{t("modelCards.smallSample")}</span>}
                      </th>
                    ) : (
                      <td key={j} dir="auto">
                        {cell}
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {table.note && <p className="muted">{table.note}</p>}
    </div>
  );
}

function thresholdValue(t: (k: string) => string, value: number | boolean | null): string {
  if (value === null) return "—";
  if (typeof value === "boolean") return value ? t("common.yes") : t("common.no");
  return String(value);
}

/** The committee approves the card as shown, or withdraws its approval (AI-01). */
function DecisionForm({ card }: { card: ModelCard }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [decision, setDecision] = useState<"approved" | "withdrawn">(
    card.status === "approved" ? "withdrawn" : "approved",
  );
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [invalid, setInvalid] = useState(false);
  const decide = useMutation({
    mutationFn: () => api.decideModel(card.id, { decision, version: card.version, reference: reference.trim(), note }),
    onSuccess: () => {
      setReference("");
      setNote("");
      void qc.invalidateQueries({ queryKey: ["model-cards"] });
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    if (reference.trim().length < 3) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    decide.mutate();
  };
  return (
    <form className="model-card__decide" onSubmit={submit} aria-labelledby={`${id}-t`} noValidate>
      <h4 id={`${id}-t`}>{t("modelCards.decide.title")}</h4>
      <fieldset className="segmented segmented--small">
        <legend className="visually-hidden">{t("modelCards.decide.title")}</legend>
        {(["approved", "withdrawn"] as const).map((d) => (
          <label key={d} className="segmented__item">
            <input type="radio" name={`${id}-d`} checked={decision === d} onChange={() => setDecision(d)} />
            <span>{t(`modelCards.decide.${d}`)}</span>
          </label>
        ))}
      </fieldset>
      <div className={`field${invalid ? " field--invalid" : ""}`}>
        <label htmlFor={`${id}-ref`}>{t("modelCards.decide.reference")}</label>
        <input
          id={`${id}-ref`}
          required
          maxLength={MAX_REFERENCE}
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? `${id}-ref-e` : `${id}-ref-h`}
        />
        <p id={`${id}-ref-h`} className="hint">
          {t("modelCards.decide.referenceHelp")}
        </p>
        {invalid && (
          <p id={`${id}-ref-e`} className="field__error">
            {t("modelCards.decide.referenceRequired")}
          </p>
        )}
      </div>
      <div className="field">
        <label htmlFor={`${id}-note`}>{t("modelCards.decide.note")}</label>
        <textarea
          id={`${id}-note`}
          rows={2}
          maxLength={MAX_DECISION_NOTE}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <RequiredNote />
      <button type="submit" className="btn btn--primary btn--small" disabled={decide.isPending}>
        {t("modelCards.decide.submit")}
      </button>
      <Failure error={decide.error} />
    </form>
  );
}

function Train() {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const train = useMutation({
    mutationFn: () => api.trainDrowningModel(),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["model-cards"] }),
  });
  return (
    <div className="model-card__train">
      <p className="muted">{t("modelCards.train.help")}</p>
      <button type="button" className="btn btn--small" disabled={train.isPending} onClick={() => train.mutate()}>
        {train.isPending ? t("modelCards.train.running") : t("modelCards.train.start")}
      </button>
      <Failure error={train.error} />
    </div>
  );
}

function Card({ card }: { card: ModelCard }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const fmt = useFormat();
  const id = useId();
  const pdf = useMutation({ mutationFn: () => api.modelCardPdf(card.id, lang), onSuccess: saveDownload });
  return (
    <section className="card model-card" aria-labelledby={`${id}-name`}>
      <div className="model-card__head">
        <h2 id={`${id}-name`}>{card.name}</h2>
        <span className={`pill ${STATUS_TONE[card.status]}`}>{card.status_label}</span>
        {card.simulated && <SimTag label={t("modelCards.simulated")} />}
        <button type="button" className="btn btn--small" disabled={pdf.isPending} onClick={() => pdf.mutate()}>
          {t("modelCards.pdf")}
        </button>
      </div>
      <p className="muted" dir="auto">
        {t("modelCards.version")}: <span dir="ltr">{card.version}</span>
      </p>
      <Failure error={pdf.error} />
      <dl className="model-card__text">
        <div>
          <dt>{t("modelCards.use")}</dt>
          <dd>{card.use}</dd>
        </div>
        <div>
          <dt>{t("modelCards.limits")}</dt>
          <dd>{card.limits}</dd>
        </div>
        <div>
          <dt>{t("modelCards.data")}</dt>
          <dd>
            {card.data}
            <span className="muted model-card__licences" dir="ltr">
              {card.licences.join(" · ")}
            </span>
          </dd>
        </div>
      </dl>
      <h3>{t("modelCards.measures")}</h3>
      {card.measures.map((m) => (
        <Measure key={m.key} table={m} />
      ))}
      <h3>{t("modelCards.thresholds")}</h3>
      <dl className="model-card__thresholds">
        {card.thresholds.map((th) => (
          <div key={th.key}>
            <dt>{th.label}</dt>
            <dd dir="ltr">{thresholdValue(t, th.value)}</dd>
          </div>
        ))}
      </dl>
      <h3>{t("modelCards.decisions")}</h3>
      {card.decisions.length === 0 ? (
        <p className="muted">{t("modelCards.noDecision")}</p>
      ) : (
        <ul className="model-card__decisions">
          {card.decisions.map((d) => (
            <li key={d.decided_at}>
              <strong>{t(`modelCards.decide.${d.decision}`)}</strong> · {d.decided_by_name} · {fmt.dateTime(d.decided_at)}{" "}
              · {t("modelCards.decide.reference")}: <span dir="auto">{d.reference}</span>
              {d.note && (
                <>
                  {" "}
                  · <span dir="auto">{d.note}</span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {card.can_train && <Train />}
      {card.can_decide && <DecisionForm card={card} />}
    </section>
  );
}

export function ModelCardsPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const query = useQuery<ModelCards>({
    queryKey: modelCardKeys.all(lang),
    queryFn: ({ signal }) => api.modelCards(lang, signal),
  });
  return (
    <div className="page">
      <div className="page__head">
        <PageTitle icon="science" tone="slate">
          {t("modelCards.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("modelCards.intro")}</p>
      {query.isPending && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.data?.items.map((card) => (
        <Card key={card.id} card={card} />
      ))}
    </div>
  );
}

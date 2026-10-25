import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Badge } from "../../components/Badges";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useServices } from "../../context/services";
import { useFormat, useLanguage } from "../../lib/hooks";
import { queryKeys } from "../../lib/portalApi";
import type { OrgMessage } from "../../lib/types";
import { BlockedNote, useOrg } from "./OrgWorkspace";

/** The text in the page language, or Arabic when that language is empty. */
export function pick(texts: OrgMessage["title"], lang: string): string {
  const own = texts[lang as keyof typeof texts];
  return own?.trim() ? own : (texts.ar ?? "");
}

/**
 * Phase P2b: Office messages addressed to the institution. Some ask the institution to confirm it read them;
 * an editor or an administrator does it once for everyone.
 */
export function OfficeMessages() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const queryClient = useQueryClient();
  const messages = useQuery({ queryKey: queryKeys.messages(org.id), queryFn: ({ signal }) => api.messages(org.id, signal) });
  const ack = useMutation({
    mutationFn: (messageId: string) => api.ackMessage(org.id, messageId),
    onSuccess: (updated) =>
      queryClient.setQueryData<OrgMessage[]>(queryKeys.messages(org.id), (old) =>
        old?.map((m) => (m.id === updated.id ? updated : m)),
      ),
  });
  const waiting = messages.data?.filter((m) => m.ack_required && !m.acked_at).length ?? 0;

  return (
    <section className="card" aria-labelledby="messages-title">
      <div className="section-head">
        <h2 id="messages-title">{t("messages.title")}</h2>
        {waiting > 0 && <Badge tone="warn">{t("messages.waitingCount", { count: waiting })}</Badge>}
      </div>
      {messages.isPending && <Loading />}
      {messages.isError && <ErrorBox error={messages.error} onRetry={() => void messages.refetch()} />}
      {messages.data?.length === 0 && <p className="muted">{t("messages.none")}</p>}
      {messages.data && messages.data.length > 0 && (
        <>
          {waiting > 0 && <BlockedNote action="acknowledge" />}
          <ul className="office-messages">
            {messages.data.map((m) => (
              <li key={m.id} className={`office-message${m.ack_required && !m.acked_at ? " office-message--waiting" : ""}`}>
                <h3 dir="auto">{pick(m.title, lang)}</h3>
                <p className="muted">{fmt.dateTime(m.published_at)}</p>
                <p dir="auto">{pick(m.body, lang)}</p>
                {m.ack_required && (
                  <div className="actions">
                    {m.acked_at ? (
                      <Badge tone="ok">{t("messages.acked", { at: fmt.dateTime(m.acked_at), by: m.acked_by ?? "—" })}</Badge>
                    ) : (
                      <>
                        <Badge tone="warn">{t("messages.waiting")}</Badge>
                        {can("acknowledge") && (
                          <button
                            type="button"
                            className="btn btn--primary btn--small"
                            disabled={ack.isPending}
                            onClick={() => ack.mutate(m.id)}
                          >
                            {t("messages.ack")}
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {ack.isError && <ErrorBox error={ack.error} />}
    </section>
  );
}

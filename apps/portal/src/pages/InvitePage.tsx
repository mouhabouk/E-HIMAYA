import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { isApiError } from "../lib/api";
import { useFormat } from "../lib/hooks";
import { queryKeys } from "../lib/portalApi";
import { PageTitle } from "../components/PageTitle";

/** Codes that end the invitation flow: shown as a page, not as a retryable error. */
const TERMINAL = new Set(["invitation_not_found", "invitation_expired", "invitation_email_mismatch", "not_found"]);

function InvitationProblem({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const code = isApiError(error) ? error.code : "unknown";
  return (
    <section className="card notice" role="alert">
      <h1>{t("invite.problemTitle")}</h1>
      <p>{t(`errors.${code === "not_found" ? "invitation_not_found" : code}`)}</p>
      {code === "invitation_email_mismatch" && user?.identity.email && (
        <p className="muted">{t("invite.signedInAs", { email: user.identity.email })}</p>
      )}
      <Link className="btn" to="/orgs/mine">
        {t("nav.myOrgs")}
      </Link>
    </section>
  );
}

/** `/invite/:token`: shows the invitation and accepts it (contract §2). */
export function InvitePage() {
  const { t } = useTranslation();
  const { token = "" } = useParams();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.invitation(token),
    queryFn: ({ signal }) => api.invitation(token, signal),
    retry: false,
  });
  const accept = useMutation({
    mutationFn: () => api.acceptInvitation(token),
    onSuccess: async (res) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs });
      void navigate(`/orgs/${encodeURIComponent(res.org_id)}`);
    },
  });

  if (query.isPending) return <Loading />;
  if (query.isError) {
    return isApiError(query.error) && TERMINAL.has(query.error.code) ? (
      <InvitationProblem error={query.error} />
    ) : (
      <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
    );
  }
  if (accept.isError && isApiError(accept.error) && TERMINAL.has(accept.error.code)) {
    return <InvitationProblem error={accept.error} />;
  }

  const inv = query.data;
  const myEmail = user?.identity.email ?? null;
  const mismatch = !!myEmail && myEmail.toLowerCase() !== inv.email.toLowerCase();
  return (
    <section className="card notice page--narrow">
      <PageTitle icon="groups" tone="navy">{t("invite.title")}</PageTitle>
      <p>{t("invite.body", { org: inv.org_name, role: t(`roles.${inv.role}`) })}</p>
      <dl className="fields">
        <dt>{t("invite.email")}</dt>
        <dd>{inv.email}</dd>
        <dt>{t("invite.role")}</dt>
        <dd>
          {t(`roles.${inv.role}`)} — <span className="muted">{t(`roleHelp.${inv.role}`)}</span>
        </dd>
        <dt>{t("invite.expires")}</dt>
        <dd>{fmt.dateTime(inv.expires_at)}</dd>
      </dl>
      {mismatch && (
        <div className="alert alert--warn">
          <p>{t("invite.mismatchWarning", { email: myEmail, invited: inv.email })}</p>
        </div>
      )}
      {accept.isError && <ErrorBox error={accept.error} />}
      <div className="actions">
        <button type="button" className="btn btn--primary" disabled={accept.isPending} onClick={() => accept.mutate()}>
          {t("invite.accept")}
        </button>
        <Link className="btn" to="/orgs/mine">
          {t("common.cancel")}
        </Link>
      </div>
    </section>
  );
}

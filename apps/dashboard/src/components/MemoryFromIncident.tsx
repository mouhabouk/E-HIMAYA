import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { p8Keys } from "../lib/phase8Api";
import { canAuthorMemory } from "../lib/roles";

/**
 * "Start from incident" (phase 8 §2/§4): the API pre-fills a national memory draft from the incident (timeline,
 * figures, resources, response times) for the after-action review; nothing is published automatically.
 */
export function MemoryFromIncidentButton({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const start = useMutation({
    mutationFn: () => api.memoryFromIncident(incidentId),
    onSuccess: (entry) => {
      qc.setQueryData(p8Keys.memoryEntry(entry.id), entry);
      void qc.invalidateQueries({ queryKey: p8Keys.memoryAll });
      void navigate(`/memory/${encodeURIComponent(entry.id)}`);
    },
  });
  if (!canAuthorMemory(user?.identity.roles ?? [])) return null;
  return (
    <span className="memory-from-incident">
      <button
        type="button"
        className="btn"
        disabled={start.isPending}
        aria-busy={start.isPending}
        title={t("memory.fromIncident.hint")}
        onClick={() => start.mutate()}
      >
        {start.isPending ? t("ops.working") : t("memory.fromIncident.button")}
      </button>
      {start.isError && (
        <span className="field__error" role="alert">
          {t(errorMessageKey(start.error))}
        </span>
      )}
    </span>
  );
}

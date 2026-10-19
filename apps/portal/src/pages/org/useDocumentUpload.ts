import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useServices } from "../../context/services";
import { queryKeys } from "../../lib/portalApi";
import { sha256Hex } from "../../lib/sha256";
import { TusError, TusUpload, forgetUpload, recallUpload, rememberUpload } from "../../lib/tus";
import type { DocumentKind } from "../../lib/types";
import { checkDocumentFile, detectContentType } from "../../lib/validators";

export type UploadState =
  | { phase: "idle" }
  | { phase: "hashing"; done: number; total: number }
  | { phase: "uploading"; sent: number; total: number }
  | { phase: "paused"; sent: number; total: number }
  | { phase: "error"; error: unknown; sent: number; total: number; canResume: boolean }
  | { phase: "sent"; sha256: string };

interface Doc {
  id: string;
  kind: DocumentKind;
}

function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

/**
 * Upload of a new document version (contract §6): local checks, SHA-256 in the browser, then tus with
 * pause / resume / retry. The server then verifies the hash (`verifying` → `stored` | `rejected`), which
 * the versions list follows by polling.
 */
export function useDocumentUpload(orgId: string, doc: Doc) {
  const { auth, tusEndpoint, fetchImpl } = useServices();
  const queryClient = useQueryClient();
  const [state, setState] = useState<UploadState>({ phase: "idle" });
  const upload = useRef<TusUpload | null>(null);
  const storeKey = useRef<string | null>(null);
  const hashAbort = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      // Leaving the page pauses the transfer; the remembered URL lets a later attempt resume.
      hashAbort.current?.abort();
      upload.current?.pause();
    },
    [],
  );

  const run = useCallback(async () => {
    const u = upload.current;
    if (!u) return;
    setState({ phase: "uploading", sent: u.offset, total: u.total });
    try {
      await u.start();
      if (storeKey.current) forgetUpload(storeKey.current);
      const sha = storeKey.current?.split(":")[1] ?? "";
      upload.current = null;
      setState({ phase: "sent", sha256: sha });
      await queryClient.invalidateQueries({ queryKey: queryKeys.versions(orgId, doc.id) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.documents(orgId) });
    } catch (e) {
      if (isAbort(e)) {
        setState({ phase: "paused", sent: u.offset, total: u.total });
        return;
      }
      // Network or 5xx failures can be resumed; refusals (4xx) need another file or a fix.
      const status = (e as { status?: number }).status ?? 0;
      setState({ phase: "error", error: e, sent: u.offset, total: u.total, canResume: status === 0 || status >= 500 });
    }
  }, [orgId, doc.id, queryClient]);

  const start = useCallback(
    async (file: File, note: string) => {
      const problem = checkDocumentFile(doc.kind, file);
      if (problem) {
        setState({ phase: "error", error: new TusError(415, problem), sent: 0, total: file.size, canResume: false });
        return;
      }
      const controller = new AbortController();
      hashAbort.current = controller;
      setState({ phase: "hashing", done: 0, total: file.size });
      let sha256: string;
      try {
        sha256 = await sha256Hex(file, {
          signal: controller.signal,
          onProgress: (done, total) => setState({ phase: "hashing", done, total }),
        });
      } catch (e) {
        setState(isAbort(e) ? { phase: "idle" } : { phase: "error", error: e, sent: 0, total: file.size, canResume: false });
        return;
      }
      const key = `${doc.id}:${sha256}:${file.size}`;
      storeKey.current = key;
      upload.current = new TusUpload({
        endpoint: tusEndpoint,
        file,
        metadata: {
          target: "org_document",
          document_id: doc.id,
          sha256,
          filetype: detectContentType(file),
          filename: file.name,
          note: note.trim() || null,
        },
        headers: (): Record<string, string> => {
          const token = auth.getAccessToken();
          return token ? { Authorization: `Bearer ${token}` } : {};
        },
        renewAuth: async () => !!(await auth.renew().catch(() => null)),
        uploadUrl: recallUpload(key),
        onUrl: (url) => rememberUpload(key, url),
        onProgress: (sent, total) => setState({ phase: "uploading", sent, total }),
        fetchImpl,
      });
      await run();
    },
    [doc.id, doc.kind, tusEndpoint, auth, fetchImpl, run],
  );

  const pause = useCallback(() => {
    if (state.phase === "hashing") hashAbort.current?.abort();
    upload.current?.pause();
  }, [state.phase]);

  const resume = useCallback(() => void run(), [run]);

  const cancel = useCallback(() => {
    hashAbort.current?.abort();
    upload.current?.pause();
    upload.current = null;
    setState({ phase: "idle" });
  }, []);

  return { state, start, pause, resume, cancel };
}

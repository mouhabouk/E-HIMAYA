import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { LiveClient, type LiveEvent, type LiveState } from "../lib/live";
import { applyLiveEvent } from "../lib/liveCache";
import { useAuth } from "./auth";
import { useServices } from "./services";

type Listener = (event: LiveEvent) => void;

interface LiveContextValue {
  state: LiveState;
  subscribe: (listener: Listener) => () => void;
}

const LiveContext = createContext<LiveContextValue | null>(null);

const KPI_DEBOUNCE_MS = 2000;

/**
 * Owns the live WebSocket for the signed-in user: re-authenticates after each token renewal,
 * patches react-query caches on every event and fans events out to subscribed screens.
 */
export function LiveProvider({ children }: { children: ReactNode }) {
  const { auth, liveUrl, createSocket } = useServices();
  const { status } = useAuth();
  const queryClient = useQueryClient();
  const [state, setState] = useState<LiveState>("idle");
  const listeners = useRef(new Set<Listener>());

  useEffect(() => {
    if (status !== "signedIn") return;
    let kpiTimer: ReturnType<typeof setTimeout> | null = null;
    const client = new LiveClient({
      url: liveUrl,
      getToken: () => auth.getAccessToken(),
      renewToken: () => auth.renew(),
      createSocket,
      onStateChange: setState,
      onEvent: (event) => {
        applyLiveEvent(queryClient, event);
        // KPIs count reports (incl. high_priority / analysis_pending): incident events do not change them.
        if (event.type !== "media.stored" && event.type !== "incident.updated") {
          if (kpiTimer) clearTimeout(kpiTimer);
          kpiTimer = setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["kpis"] }), KPI_DEBOUNCE_MS);
        }
        for (const l of listeners.current) l(event);
      },
    });
    const unsubscribe = auth.subscribe((user) => {
      if (user) client.updateToken(user.accessToken);
    });
    const onVisible = () => {
      if (document.visibilityState === "visible") client.reconnectNow();
    };
    const onOnline = () => client.reconnectNow();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("online", onOnline);
    client.start();
    return () => {
      unsubscribe();
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("online", onOnline);
      if (kpiTimer) clearTimeout(kpiTimer);
      client.stop();
      setState("idle");
    };
  }, [status, auth, liveUrl, createSocket, queryClient]);

  const subscribe = useCallback((listener: Listener) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const value = useMemo(() => ({ state, subscribe }), [state, subscribe]);
  return <LiveContext value={value}>{children}</LiveContext>;
}

function useLiveContext(): LiveContextValue {
  const v = useContext(LiveContext);
  if (!v) throw new Error("LiveProvider missing");
  return v;
}

export function useLiveState(): LiveState {
  return useLiveContext().state;
}

/** Subscribe a screen to live events; the handler may change between renders. */
export function useLiveEvents(handler: Listener): void {
  const { subscribe } = useLiveContext();
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => subscribe((e) => ref.current(e)), [subscribe]);
}

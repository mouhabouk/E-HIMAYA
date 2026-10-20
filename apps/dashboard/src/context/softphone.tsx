import { createContext, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";
import { useAuth } from "./auth";
import { useLiveEvents } from "./live";
import { useServices } from "./services";
import { hasSoftphone } from "../lib/roles";
import { setRinging } from "../lib/ringtone";
import { Softphone, type SipEngineFactory, type SoftphoneState } from "../lib/softphone";

/** The softphone stays on across reloads of this tab once the operator switched it on. */
export const SOFTPHONE_ON_KEY = "ehimaya.softphoneOn";

const loadJsSip: SipEngineFactory = () => import("../lib/jssipEngine").then((m) => m.createJsSipEngine());

const SoftphoneContext = createContext<Softphone | null>(null);

export function rememberSoftphone(on: boolean): void {
  try {
    if (on) sessionStorage.setItem(SOFTPHONE_ON_KEY, "1");
    else sessionStorage.removeItem(SOFTPHONE_ON_KEY);
  } catch {
    /* storage unavailable */
  }
}

function remembered(): boolean {
  try {
    return sessionStorage.getItem(SOFTPHONE_ON_KEY) === "1";
  } catch {
    return false;
  }
}

/** One softphone per signed-in staff member who may call or join a conference (nothing is loaded before use). */
export function SoftphoneProvider({ children }: { children: ReactNode }) {
  const { api, createSipEngine } = useServices();
  const { user } = useAuth();
  const allowed = hasSoftphone(user?.identity.roles ?? []);
  const phone = useMemo(
    () =>
      allowed ? new Softphone({ api, createEngine: createSipEngine ?? loadJsSip, onRingingChange: setRinging }) : null,
    [allowed, api, createSipEngine],
  );

  // Nothing is loaded or registered before the operator switches the phone on (remembered for this tab).
  useEffect(() => {
    if (!phone) return;
    if (remembered()) void phone.connect();
    return () => {
      phone.disconnect();
      setRinging(false);
    };
  }, [phone]);

  useLiveEvents((event) => {
    if (phone && event.type.startsWith("call.") && "call_id" in event) phone.noteCallEvent(event);
  });

  return <SoftphoneContext value={phone}>{children}</SoftphoneContext>;
}

/** The softphone controller, or null for roles without telephony. */
export function useSoftphone(): Softphone | null {
  return useContext(SoftphoneContext);
}

const OFF: SoftphoneState = {
  status: "off",
  error: null,
  transfer198: false,
  simulated: false,
  credentialsExpireAt: null,
  calls: [],
};
const noop = () => () => undefined;

export function useSoftphoneState(): SoftphoneState {
  const phone = useSoftphone();
  return useSyncExternalStore(phone ? phone.subscribe : noop, phone ? phone.getState : () => OFF, () => OFF);
}

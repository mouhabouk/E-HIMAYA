/**
 * Audible cue for a confirmed fire or smoke on a live stream (phase 6 §3 `stream.alert`). Synthesised with the Web
 * Audio API (no audio file, nothing for the CSP to allow); each operator can turn it off, and the choice is kept in
 * this browser only. Browsers start audio only after a first interaction with the page: before that the cue is
 * silently skipped and the on-screen alert is the only signal.
 */
import { useSyncExternalStore } from "react";

const STORAGE_KEY = "ehimaya.streamAlertSound";
const listeners = new Set<() => void>();
let current: boolean | null = null;

function read(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setAlertSoundEnabled(enabled: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, enabled ? "on" : "off");
  } catch {
    /* storage unavailable: the choice lasts until the page is reloaded */
  }
  current = enabled;
  for (const l of listeners) l();
}

export function alertSoundEnabled(): boolean {
  current ??= read();
  return current;
}

export function useAlertSound(): [boolean, (enabled: boolean) => void] {
  const enabled = useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    alertSoundEnabled,
    () => true,
  );
  return [enabled, setAlertSoundEnabled];
}

/** Forget the cached choice (tests clear localStorage between cases). */
export function resetAlertSoundForTests(): void {
  current = null;
}

type AudioContextCtor = typeof AudioContext;
let context: AudioContext | null = null;

/** Two short descending tones, quiet enough not to startle (gain 0.12). */
export function playAlertTone(): void {
  if (!alertSoundEnabled()) return;
  const Ctor = (window as unknown as { AudioContext?: AudioContextCtor; webkitAudioContext?: AudioContextCtor }).AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
  if (!Ctor) return;
  try {
    context ??= new Ctor();
    const ctx = context;
    if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
    const start = ctx.currentTime + 0.02;
    [880, 660].forEach((frequency, i) => {
      const at = start + i * 0.22;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = frequency;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.12, at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(at);
      osc.stop(at + 0.2);
    });
  } catch {
    /* audio unavailable: the visual alert remains */
  }
}

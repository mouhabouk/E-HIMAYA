/**
 * Ringing of an incoming queue call (phase 7 §4). Same rules as the stream alert cue (lib/alertSound.ts): Web Audio
 * synthesis (no file, nothing for the CSP), and silent when the operator turned the alert sound off in this browser;
 * the visual incoming-call panel is always shown.
 */
import { alertSoundEnabled } from "./alertSound";

type AudioContextCtor = typeof AudioContext;
let context: AudioContext | null = null;
let timer: ReturnType<typeof setInterval> | null = null;

/** A soft double ring (two short 440/480 Hz bursts), repeated every 3 s while ringing. */
function ringOnce(): void {
  if (!alertSoundEnabled()) return;
  const Ctor =
    (window as unknown as { AudioContext?: AudioContextCtor }).AudioContext ??
    (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
  if (!Ctor) return;
  try {
    context ??= new Ctor();
    const ctx = context;
    if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
    const start = ctx.currentTime + 0.02;
    [0, 0.5].forEach((offset) => {
      const at = start + offset;
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.1, at + 0.03);
      gain.gain.setValueAtTime(0.1, at + 0.35);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.4);
      gain.connect(ctx.destination);
      for (const frequency of [440, 480]) {
        const osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = frequency;
        osc.connect(gain);
        osc.start(at);
        osc.stop(at + 0.42);
      }
    });
  } catch {
    /* audio unavailable: the incoming-call panel remains */
  }
}

export function setRinging(on: boolean): void {
  if (on && timer === null) {
    ringOnce();
    timer = setInterval(ringOnce, 3_000);
  } else if (!on && timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}

import { useMutation } from "@tanstack/react-query";
import {
  useEffect,
  useRef,
  useState,
  type TextareaHTMLAttributes,
} from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { useLanguage } from "../lib/hooks";
import { Icon } from "./Icon";
import { MutationError } from "./IncidentDecision";

/** The longest dictation, in seconds (the API refuses longer ones). */
export const DICTATION_MAX_S = 60;

function canRecord(): boolean {
  return (
    typeof MediaRecorder !== "undefined" &&
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices
  );
}

/**
 * Phase D, review point 19: a free-text field with a microphone. One press starts, a second press stops (or the minute
 * does); the recording is transcribed by the local service, its audio deleted, and the text added to the field for the
 * user to correct. When the field's form is sent, the text the user kept goes back once, so the error rate of each
 * field is measured (the corrections log). Only on free text: never on a number, a date, a choice or a name.
 */
export function DictatedTextarea({
  field,
  value,
  onText,
  ...textarea
}: {
  /** The field's name in the corrections log, e.g. `report.note` (lower case, digits, `.` and `_`). */
  field: string;
  value: string;
  onText: (value: string) => void;
} & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange">) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const box = useRef<HTMLTextAreaElement | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);
  const pending = useRef<string[]>([]);
  const latest = useRef(value);
  const [seconds, setSeconds] = useState(0);
  const [recording, setRecording] = useState(false);
  const [refused, setRefused] = useState(false);
  useEffect(() => {
    latest.current = value;
  }, [value]);

  const transcribe = useMutation({
    mutationFn: (audio: Blob) => api.dictate(field, audio, lang),
    onSuccess: (result) => {
      pending.current.push(result.dictation_id);
      const before = latest.current.trimEnd();
      onText(before ? `${before} ${result.text}` : result.text);
    },
  });

  // The form is sent: the text kept is measured against each transcript of this field, once.
  useEffect(() => {
    const form = box.current?.form;
    if (!form) return;
    const sent = () => {
      const ids = pending.current.splice(0);
      for (const id of ids)
        void api.dictationKept(id, latest.current).catch(() => undefined);
    };
    form.addEventListener("submit", sent);
    return () => form.removeEventListener("submit", sent);
  }, [api]);

  const stopTimer = () => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
  };
  useEffect(
    () => () => {
      stopTimer();
      recorder.current?.stream.getTracks().forEach((track) => track.stop());
    },
    [],
  );
  useEffect(() => {
    if (!recording || seconds < DICTATION_MAX_S) return;
    stopTimer();
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, [recording, seconds]);

  const stop = () => {
    stopTimer();
    if (recorder.current?.state === "recording") recorder.current.stop();
  };
  const start = async () => {
    setRefused(false);
    transcribe.reset();
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setRefused(true);
      return;
    }
    const chunks: Blob[] = [];
    const rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      recorder.current = null;
      setRecording(false);
      setSeconds(0);
      const audio = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      if (audio.size > 0) transcribe.mutate(audio);
    };
    recorder.current = rec;
    rec.start();
    setRecording(true);
    setSeconds(0);
    timer.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
  };

  const label = recording
    ? t("dictation.stop", { seconds: DICTATION_MAX_S - seconds })
    : transcribe.isPending
      ? t("dictation.transcribing")
      : t("dictation.record");
  return (
    <>
      <div className="dictated">
        <textarea
          ref={box}
          dir="auto"
          {...textarea}
          value={value}
          onChange={(e) => onText(e.target.value)}
        />
        {canRecord() && (
          <button
            type="button"
            className={`btn btn--small dictated__mic ${recording ? "btn--danger" : ""}`}
            aria-pressed={recording}
            aria-label={label}
            title={label}
            disabled={textarea.disabled || transcribe.isPending}
            onClick={() => (recording ? stop() : void start())}
          >
            <Icon name={recording ? "stop" : "mic"} size={18} />
            {recording && (
              <span aria-hidden="true"> {DICTATION_MAX_S - seconds}</span>
            )}
          </button>
        )}
      </div>
      {refused && (
        <p className="alert alert--warn" role="alert">
          {t("dictation.refused")}
        </p>
      )}
      <MutationError error={transcribe.error} />
    </>
  );
}

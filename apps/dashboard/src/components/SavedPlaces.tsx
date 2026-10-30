// covers: FR-M-10 — docs/phase-m/design-m.md §7: a room saves a point of its map (a fuel depot, a school, a ford that
// floods) with a name, a kind and a note, and finds it again in a list; the kind is told by its word, never by the
// colour of the bookmark alone.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import type { BBox } from "../lib/filters";
import { useFormat } from "../lib/hooks";
import {
  PLACE_COLOURS,
  PLACE_ICON,
  PLACE_KINDS,
  placeKeys,
  type PlaceBody,
  type PlaceKind,
  type SavedPlace,
} from "../lib/places";
import type { MapPoi, MapPopupContent } from "./MapView";

/** About 300 m around a place: the view a click in the list flies to. */
const AROUND = 0.003;

function PlaceForm({
  initial,
  busy,
  error,
  onSave,
  onCancel,
  onDelete,
}: {
  initial: PlaceBody;
  busy: boolean;
  error: string | null;
  onSave: (body: PlaceBody) => void;
  onCancel: () => void;
  onDelete?: () => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [name, setName] = useState(initial.name);
  const [kind, setKind] = useState<PlaceKind>(initial.kind);
  const [note, setNote] = useState(initial.note ?? "");
  const [confirming, setConfirming] = useState(false);
  return (
    <form
      className="place-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) onSave({ name: name.trim(), kind, note: note.trim() || null });
      }}
    >
      <div className="field">
        <label htmlFor={`${id}-name`}>
          {t("places.name")}
        </label>
        <input id={`${id}-name`} value={name} maxLength={120} required dir="auto" onChange={(e) => setName(e.target.value)} />
      </div>
      <fieldset className="segmented" aria-label={t("places.kind")}>
        {PLACE_KINDS.map((k) => (
          <label key={k} className="segmented__item">
            <input type="radio" name={`${id}-kind`} checked={kind === k} onChange={() => setKind(k)} />
            <span>{t(`places.kinds.${k}`)}</span>
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-note`}>{t("places.note")}</label>
        <textarea id={`${id}-note`} rows={3} maxLength={2000} value={note} dir="auto" onChange={(e) => setNote(e.target.value)} />
      </div>
      {error && (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--small" disabled={busy || !name.trim()}>
          {t("places.save")}
        </button>
        <button type="button" className="btn btn--small btn--ghost" onClick={onCancel}>
          {t("common.cancel")}
        </button>
        {onDelete &&
          (confirming ? (
            <button type="button" className="btn btn--small btn--danger" disabled={busy} onClick={onDelete}>
              {t("places.deleteConfirm")}
            </button>
          ) : (
            <button type="button" className="btn btn--small btn--ghost" onClick={() => setConfirming(true)}>
              {t("places.delete")}
            </button>
          ))}
      </div>
    </form>
  );
}

export function useSavedPlaces() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<{ lon: number; lat: number } | null>(null);
  const [editing, setEditing] = useState<SavedPlace | null>(null);
  const [filter, setFilter] = useState<PlaceKind | "all">("all");
  const [flyTo, setFlyTo] = useState<BBox | null>(null);

  const query = useQuery({ queryKey: placeKeys.all, staleTime: 60_000, queryFn: ({ signal }) => api.places(signal) });
  const places = useMemo(() => query.data ?? [], [query.data]);
  const done = () => {
    void qc.invalidateQueries({ queryKey: placeKeys.all });
    setDraft(null);
    setEditing(null);
    setAdding(false);
  };
  const create = useMutation({ mutationFn: api.createPlace, onSuccess: done });
  const update = useMutation({ mutationFn: (v: { id: string; body: PlaceBody }) => api.updatePlace(v.id, v.body), onSuccess: done });
  const remove = useMutation({ mutationFn: (id: string) => api.deletePlace(id), onSuccess: done });
  const busy = create.isPending || update.isPending || remove.isPending;
  const failure = create.error ?? update.error ?? remove.error;
  const error = failure ? t(errorMessageKey(failure)) : null;
  const reset = () => {
    create.reset();
    update.reset();
    remove.reset();
  };

  const pois = useMemo<MapPoi[]>(
    () =>
      places.map((p) => ({
        id: `place:${p.id}`,
        lon: p.lon,
        lat: p.lat,
        kind: "place",
        iconPath: PLACE_ICON,
        colour: PLACE_COLOURS[p.kind],
        title: p.name,
        subtitle: t(`places.kinds.${p.kind}`),
        details: [
          ...(p.note ? [p.note] : []),
          t("places.by", { name: p.updated_by_name ?? p.created_by_name ?? "—", time: fmt.dateTime(p.updated_at) }),
        ],
      })),
    [places, t, fmt],
  );

  /** A map click while "save a place" is on opens the form there; returns whether the click was used. */
  const onMapClick = (lon: number, lat: number): boolean => {
    if (!adding) return false;
    reset();
    setEditing(null);
    setDraft({ lon, lat });
    return true;
  };
  const close = () => {
    setDraft(null);
    setEditing(null);
    reset();
  };

  const popup: MapPopupContent | null = draft
    ? {
        lon: draft.lon,
        lat: draft.lat,
        key: `place-new:${draft.lon},${draft.lat}`,
        node: (
          <div className="admin-card">
            <strong>{t("places.new")}</strong>
            <PlaceForm
              initial={{ name: "", kind: "important", note: null }}
              busy={busy}
              error={error}
              onSave={(body) => create.mutate({ ...body, lon: draft.lon, lat: draft.lat })}
              onCancel={close}
            />
          </div>
        ),
      }
    : editing
      ? {
          lon: editing.lon,
          lat: editing.lat,
          key: `place-edit:${editing.id}`,
          node: (
            <div className="admin-card">
              <strong dir="auto">{editing.name}</strong>
              <PlaceForm
                initial={{ name: editing.name, kind: editing.kind, note: editing.note }}
                busy={busy}
                error={error}
                onSave={(body) => update.mutate({ id: editing.id, body })}
                onCancel={close}
                onDelete={() => remove.mutate(editing.id)}
              />
            </div>
          ),
        }
      : null;

  const shown = filter === "all" ? places : places.filter((p) => p.kind === filter);
  const controls = (
    <section className="card saved-places" aria-label={t("places.title")}>
      <div className="saved-places__head">
        <h2>{t("places.title")}</h2>
        <button
          type="button"
          className={`btn btn--small${adding ? "" : " btn--ghost"}`}
          aria-pressed={adding}
          onClick={() => {
            setAdding(!adding);
            close();
          }}
        >
          {adding ? t("places.addingStop") : t("places.add")}
        </button>
      </div>
      <p className="muted" role="status" aria-live="polite">
        {adding ? t("places.addingHint") : t("places.count", { count: fmt.number(places.length) })}
      </p>
      {query.isError && <p className="field__error">{t(errorMessageKey(query.error))}</p>}
      {places.length > 0 && (
        <fieldset className="segmented" aria-label={t("places.kind")}>
          {(["all", ...PLACE_KINDS] as const).map((k) => (
            <label key={k} className="segmented__item">
              <input type="radio" name="places-filter" checked={filter === k} onChange={() => setFilter(k)} />
              <span>{k === "all" ? t("places.all") : t(`places.kinds.${k}`)}</span>
            </label>
          ))}
        </fieldset>
      )}
      {shown.length > 0 && (
        <ul className="saved-places__list">
          {shown.map((p) => (
            <li key={p.id} className={`saved-places__item saved-places__item--${p.kind}`}>
              <button
                type="button"
                className="link-button"
                onClick={() => setFlyTo([p.lon - AROUND, p.lat - AROUND, p.lon + AROUND, p.lat + AROUND])}
              >
                <strong dir="auto">{p.name}</strong>
              </button>
              <span className="pill">{t(`places.kinds.${p.kind}`)}</span>
              {p.note && (
                <span className="muted saved-places__note" dir="auto">
                  {p.note}
                </span>
              )}
              <button
                type="button"
                className="btn btn--small btn--ghost"
                onClick={() => {
                  reset();
                  setDraft(null);
                  setEditing(p);
                }}
              >
                {t("places.edit")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );

  return { pois, onMapClick, popup, closePopup: close, controls, focusBounds: flyTo, adding };
}

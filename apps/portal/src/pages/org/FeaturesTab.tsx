import { useMemo, useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Dialog } from "../../components/Dialog";
import { ErrorBox, Loading } from "../../components/Feedback";
import { MapPanel } from "../../components/LazyMap";
import type { MapMarker } from "../../components/MapView";
import { useFormat } from "../../lib/hooks";
import { FEATURE_KINDS, type FeatureKind, type GeoPoint, type MapFeature } from "../../lib/types";
import { FEATURE_MAX_DISTANCE_M, distanceMeters, isWithinFeatureRadius, parseNumber } from "../../lib/validators";
import { BlockedNote, useOrg } from "./OrgWorkspace";
import { Field, RowActions } from "./RegisterParts";
import { useRegister } from "./useRegister";

type Editing = { feature: MapFeature | null; location: GeoPoint };

function FeatureDialog({
  editing,
  orgLocation,
  onClose,
  save,
}: {
  editing: Editing;
  orgLocation: GeoPoint;
  onClose: () => void;
  save: ReturnType<typeof useRegister<"features">>["save"];
}) {
  const { t } = useTranslation();
  const { feature } = editing;
  const [kind, setKind] = useState<FeatureKind>(feature?.kind ?? "evacuation_point");
  const [label, setLabel] = useState(feature?.label ?? "");
  const [lat, setLat] = useState(String(editing.location.lat));
  const [lon, setLon] = useState(String(editing.location.lon));
  const [error, setError] = useState<string | null>(null);

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const a = parseNumber(lat);
    const b = parseNumber(lon);
    if (!label.trim()) return setError("validation.required");
    if (a === null || b === null || !Number.isFinite(a) || !Number.isFinite(b)) return setError("validation.coordinates");
    const location = { lat: a, lon: b };
    if (!isWithinFeatureRadius(orgLocation, location)) return setError("errors.feature_too_far");
    setError(null);
    save.mutate({ id: feature?.id ?? null, input: { kind, label: label.trim(), location } }, { onSuccess: onClose });
  }

  return (
    <Dialog title={feature ? t("features.editTitle") : t("features.addTitle")} onClose={onClose}>
      <form className="form" onSubmit={submit} noValidate>
        <div className="form-grid">
          <Field id="ft-kind" label={t("features.kind")}>
            <select id="ft-kind" value={kind} onChange={(e) => setKind(e.target.value as FeatureKind)}>
              {FEATURE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {t(`featureKinds.${k}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field id="ft-label" label={t("features.label")} required>
            <input id="ft-label" value={label} onChange={(e) => setLabel(e.target.value)} />
          </Field>
          <Field id="ft-lat" label={t("location.lat")}>
            <input id="ft-lat" inputMode="decimal" dir="ltr" value={lat} onChange={(e) => setLat(e.target.value)} />
          </Field>
          <Field id="ft-lon" label={t("location.lon")}>
            <input id="ft-lon" inputMode="decimal" dir="ltr" value={lon} onChange={(e) => setLon(e.target.value)} />
          </Field>
        </div>
        {error && (
          <p className="field__error" role="alert">
            {t(error)}
          </p>
        )}
        {save.isError && <ErrorBox error={save.error} />}
        <div className="actions actions--end">
          <button type="button" className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("common.save")}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

/** Map of the institution (FR-B-007): evacuation points, water points and alarms within 2 km. */
export function FeaturesTab() {
  const { t } = useTranslation();
  const { org, can } = useOrg();
  const fmt = useFormat();
  const { list, save, remove } = useRegister(org.id, "features");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resetTick, setResetTick] = useState(0);
  const editable = can("editRegisters");
  const features = list.data;

  const markers = useMemo<MapMarker[]>(() => {
    return [
      { id: "__org", lat: org.location.lat, lon: org.location.lon, kind: "org", label: org.name },
      ...(features ?? []).map((f) => ({
        id: f.id,
        lat: f.location.lat,
        lon: f.location.lon,
        kind: f.kind,
        label: `${t(`featureKinds.${f.kind}`)} — ${f.label}`,
        draggable: editable,
      })),
    ];
  }, [org, features, editable, t]);

  if (list.isPending) return <Loading />;
  if (list.isError || !features) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;

  function moved(id: string, p: GeoPoint) {
    const f = features?.find((x) => x.id === id);
    if (!f) return;
    if (!isWithinFeatureRadius(org.location, p)) {
      setNotice("errors.feature_too_far");
      setResetTick((n) => n + 1);
      return;
    }
    setNotice(null);
    save.mutate(
      { id, input: { kind: f.kind, label: f.label, location: p } },
      {
        onError: () => {
          setResetTick((n) => n + 1);
        },
      },
    );
  }

  return (
    <div className="stack">
      <section className="card" aria-labelledby="map-title">
        <div className="section-head">
          <h2 id="map-title">{t("features.title")}</h2>
          {editable && (
            <button type="button" className="btn btn--primary" onClick={() => setEditing({ feature: null, location: org.location })}>
              {t("features.add")}
            </button>
          )}
        </div>
        <p className="muted">{t(editable ? "features.helpEdit" : "features.help", { km: fmt.number(FEATURE_MAX_DISTANCE_M / 1000) })}</p>
        <BlockedNote action="editRegisters" />
        <div aria-live="polite">
          {notice && (
            <p className="alert alert--error" role="alert">
              {t(notice)}
            </p>
          )}
          {save.isError && !editing && <ErrorBox error={save.error} />}
        </div>
        <MapPanel
          center={org.location}
          zoom={15}
          className="map map--full"
          ariaLabel={t("features.mapLabel")}
          markers={markers}
          resetToken={resetTick}
          circle={{ center: org.location, meters: FEATURE_MAX_DISTANCE_M }}
          onMapClick={
            editable
              ? (p) => {
                  if (!isWithinFeatureRadius(org.location, p)) {
                    setNotice("errors.feature_too_far");
                    return;
                  }
                  setNotice(null);
                  setEditing({ feature: null, location: p });
                }
              : undefined
          }
          onMarkerClick={(id) => {
            const f = features.find((x) => x.id === id);
            if (f && editable) setEditing({ feature: f, location: f.location });
          }}
          onMarkerDragEnd={editable ? moved : undefined}
        />
        <ul className="legend">
          {(["org", ...FEATURE_KINDS] as const).map((k) => (
            <li key={k}>
              <span className={`legend__dot map-marker--${k}`} aria-hidden="true" />
              {k === "org" ? t("features.institution") : t(`featureKinds.${k}`)}
            </li>
          ))}
        </ul>
      </section>
      <section className="card" aria-labelledby="features-list-title">
        <h2 id="features-list-title">{t("features.listTitle")}</h2>
        {features.length === 0 ? (
          <p className="empty">{t("features.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("features.kind")}</th>
                  <th scope="col">{t("features.label")}</th>
                  <th scope="col" className="num">
                    {t("features.distance")}
                  </th>
                  {editable && <th scope="col">{t("common.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {features.map((f) => (
                  <tr key={f.id}>
                    <td>{t(`featureKinds.${f.kind}`)}</td>
                    <th scope="row">{f.label}</th>
                    <td className="num">{t("features.meters", { n: fmt.number(Math.round(distanceMeters(org.location, f.location))) })}</td>
                    {editable && (
                      <td>
                        <RowActions name={f.label} editable={editable} onEdit={() => setEditing({ feature: f, location: f.location })} remove={remove} id={f.id} />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {editing && (
        <FeatureDialog
          editing={editing}
          orgLocation={org.location}
          save={save}
          onClose={() => {
            save.reset();
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { TUNISIA_CENTER } from "../lib/mapStyle";
import type { GeoPoint } from "../lib/types";
import { isInTunisia, parseNumber } from "../lib/validators";
import { MapPanel } from "./LazyMap";

function fmt(n: number | undefined): string {
  return n === undefined ? "" : String(Math.round(n * 1e6) / 1e6);
}

/**
 * Point picker: click on the map or drag the pin, or type the coordinates (keyboard and screen-reader
 * alternative to the map).
 */
export function LocationField({
  value,
  onChange,
  error,
  legend,
}: {
  value: GeoPoint | null;
  onChange: (p: GeoPoint | null) => void;
  error?: string | null;
  legend: string;
}) {
  const { t } = useTranslation();
  const id = useId();
  const [lat, setLat] = useState(fmt(value?.lat));
  const [lon, setLon] = useState(fmt(value?.lon));
  const [shown, setShown] = useState(value);
  // Keep the text fields in sync when the point changes on the map.
  if (shown !== value) {
    setShown(value);
    if (value) {
      setLat(fmt(value.lat));
      setLon(fmt(value.lon));
    }
  }

  function typed(nextLat: string, nextLon: string) {
    setLat(nextLat);
    setLon(nextLon);
    const a = parseNumber(nextLat);
    const b = parseNumber(nextLon);
    const p = a !== null && b !== null && Number.isFinite(a) && Number.isFinite(b) ? { lat: a, lon: b } : null;
    setShown(p);
    onChange(p);
  }

  const outside = value !== null && !isInTunisia(value);
  return (
    <fieldset className="location-field">
      <legend>{legend}</legend>
      <p className="muted">{t("location.help")}</p>
      <MapPanel
        center={value ?? TUNISIA_CENTER}
        zoom={value ? 15 : 6}
        followCenter
        className="map map--picker"
        ariaLabel={t("location.mapLabel")}
        markers={value ? [{ id: "point", lat: value.lat, lon: value.lon, kind: "point", label: t("location.pin"), draggable: true }] : []}
        onMapClick={(p) => onChange(p)}
        onMarkerDragEnd={(_id, p) => onChange(p)}
      />
      <div className="form-row">
        <div className="field">
          <label htmlFor={`${id}-lat`}>{t("location.lat")}</label>
          <input
            id={`${id}-lat`}
            inputMode="decimal"
            value={lat}
            aria-invalid={!!error || outside}
            onChange={(e) => typed(e.target.value, lon)}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-lon`}>{t("location.lon")}</label>
          <input
            id={`${id}-lon`}
            inputMode="decimal"
            value={lon}
            aria-invalid={!!error || outside}
            onChange={(e) => typed(lat, e.target.value)}
          />
        </div>
      </div>
      {(error ?? outside) && (
        <p className="field__error" role="alert">
          {error ?? t("validation.outsideTunisia")}
        </p>
      )}
    </fieldset>
  );
}

// Integration first (Yamen 2026-11-13): a screen that draws data on its own map also opens the interactive map with
// that data as a layer, so the same information is reachable from more than one place without being copied.
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Icon } from "./Icon";
import type { MapLayerId } from "./SystemLayers";

export function MapLayerLink({ layer }: { layer: MapLayerId }) {
  const { t } = useTranslation();
  return (
    <Link className="btn btn--small btn--ghost map-layer-link" to={`/map?layers=${layer}`}>
      <Icon name="map" size={16} /> {t("mapLayers.openOnMap")}
    </Link>
  );
}

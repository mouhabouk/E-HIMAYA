/**
 * Map points of interest: the institutions layer (phase 4 §5, §9) and the operations layers (phase 5:
 * Civil Protection units, resources, ready volunteers) and live streams (phase 6): kinds and 24×24 icon paths.
 */

export const POI_KINDS = [
  "org",
  "org_hazmat",
  "evacuation_point",
  "water_point",
  "alarm",
  "unit",
  "resource",
  "resource_busy",
  "volunteer",
  "stream",
  "stream_alert",
  // Sensors of the local network (L5b): the level is in the shape and the label too, never colour alone.
  "sensor",
  "sensor_watch",
  "sensor_alarm",
  "sensor_silent",
  // Watch towers (L5b): a camera on a tower; a fire or smoke in the last hour adds a ring.
  "tower",
  "tower_alert",
  // Drones (L5b, read only): a quadcopter; an open alert of its zones or battery adds a ring.
  "drone",
  "drone_alert",
  // Map data layers loaded from files (phase B1): the icon and colour come from the layer (lib/layers.ts).
  "place",
  "place_cluster",
] as const;
export type PoiKind = (typeof POI_KINDS)[number];

export const POI_ICON_PATHS: Record<PoiKind, string> = {
  // Building.
  org: "M4 21V5l8-3 8 3v16h-6v-5h-4v5H4zm4-12h2V7H8v2zm6 0h2V7h-2v2zm-6 4h2v-2H8v2zm6 0h2v-2h-2v2z",
  // Warning triangle (hazardous materials).
  org_hazmat: "M12 2 1 21h22L12 2zm-1 7h2v6h-2V9zm0 8h2v2h-2v-2z",
  // Person at an assembly point.
  evacuation_point: "M12 2a2 2 0 1 1 0 4 2 2 0 0 1 0-4zM9 8h6l-1 6h-1v8h-2v-8h-1L9 8z",
  // Water drop.
  water_point: "M12 2s7 8 7 13a7 7 0 0 1-14 0c0-5 7-13 7-13z",
  // Bell.
  alarm: "M12 22a2 2 0 0 0 2-2h-4a2 2 0 0 0 2 2zm6-6v-5a6 6 0 0 0-5-5.9V4h-2v1.1A6 6 0 0 0 6 11v5l-2 2v1h16v-1l-2-2z",
  // Shield (Civil Protection unit).
  unit: "M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3zm-1 5h2v4h4v2h-4v4h-2v-4H7v-2h4V7z",
  // Truck (resource available).
  resource: "M2 6h12v9h1.5A3 3 0 0 1 21 15h1v-4l-3-4h-4V6h0V5H2v1zm0 1v8h1a3 3 0 0 1 5.8 0H13V7H2zm4.5 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
  // Truck with a flag (resource engaged).
  resource_busy: "M2 6h12v9h1.5A3 3 0 0 1 21 15h1v-4l-3-4h-4V5H2v1zm4.5 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm11 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM16 2h6v4h-5v2h-1V2z",
  // Person with a cross (volunteer).
  volunteer: "M10 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6zM4 20v-3c0-3 3-5 6-5s6 2 6 5v3H4zm14-11h2v2h2v2h-2v2h-2v-2h-2v-2h2V9z",
  // Video camera (live stream, phase 6).
  stream: "M3 6h12a2 2 0 0 1 2 2v1.5l4-2.5v10l-4-2.5V16a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
  // Flame (live stream with a fire or smoke detection).
  stream_alert: "M12 2c1 4 6 6 6 12a6 6 0 0 1-12 0c0-3 2-5 3-6 0 2 1 3 2 3 0-4-1-6 1-9z",
  // Gauge (a sensor), the same shape at every level; the marker's frame tells the level.
  sensor: "M12 4a10 10 0 0 0-10 10c0 2 .6 3.9 1.6 5.5l1.7-1A8 8 0 0 1 4 14a8 8 0 0 1 16 0c0 1.7-.5 3.2-1.3 4.5l1.7 1A10 10 0 0 0 22 14 10 10 0 0 0 12 4zm4.2 4.4-5.1 4.2a2 2 0 1 0 2.4 2.4l2.7-6.6z",
  sensor_watch: "M12 4a10 10 0 0 0-10 10c0 2 .6 3.9 1.6 5.5l1.7-1A8 8 0 0 1 4 14a8 8 0 0 1 16 0c0 1.7-.5 3.2-1.3 4.5l1.7 1A10 10 0 0 0 22 14 10 10 0 0 0 12 4zm4.2 4.4-5.1 4.2a2 2 0 1 0 2.4 2.4l2.7-6.6z",
  sensor_alarm: "M12 4a10 10 0 0 0-10 10c0 2 .6 3.9 1.6 5.5l1.7-1A8 8 0 0 1 4 14a8 8 0 0 1 16 0c0 1.7-.5 3.2-1.3 4.5l1.7 1A10 10 0 0 0 22 14 10 10 0 0 0 12 4zm4.2 4.4-5.1 4.2a2 2 0 1 0 2.4 2.4l2.7-6.6z",
  sensor_silent: "M12 4a10 10 0 0 0-10 10c0 2 .6 3.9 1.6 5.5l1.7-1A8 8 0 0 1 4 14a8 8 0 0 1 16 0c0 1.7-.5 3.2-1.3 4.5l1.7 1A10 10 0 0 0 22 14 10 10 0 0 0 12 4zm4.2 4.4-5.1 4.2a2 2 0 1 0 2.4 2.4l2.7-6.6z",
  // Watch tower (the same shape with or without a recent fire or smoke; the ring tells it).
  tower: "M11 2h2v3h3l-1 4h-2v4l3 9h-2l-1.6-5h-2.8L8 22H6l3-9V9H9L8 5h3V2zm-.5 13h3L12 10.5 10.5 15z",
  tower_alert: "M11 2h2v3h3l-1 4h-2v4l3 9h-2l-1.6-5h-2.8L8 22H6l3-9V9H9L8 5h3V2zm-.5 13h3L12 10.5 10.5 15z",
  // Drone seen from above (the same shape with or without an open alert; the ring tells it).
  drone: "M5 1.7999999999999998a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM19 1.7999999999999998a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM5 15.8a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM19 15.8a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM5.7 4.3L19.7 18.3L18.3 19.7L4.3 5.7zM18.3 4.3L19.7 5.7L5.7 19.7L4.3 18.3zM9 9L15 9L15 15L9 15z",
  drone_alert: "M5 1.7999999999999998a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM19 1.7999999999999998a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM5 15.8a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM19 15.8a3.2 3.2 0 1 1 0 6.4a3.2 3.2 0 1 1 0 -6.4zM5.7 4.3L19.7 18.3L18.3 19.7L4.3 5.7zM18.3 4.3L19.7 5.7L5.7 19.7L4.3 18.3zM9 9L15 9L15 15L9 15z",
  // Map pin (a place whose layer icon is unknown); clusters show their count instead.
  place: "M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 4.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z",
  place_cluster: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z",
};

export function isPoiKind(v: unknown): v is PoiKind {
  return typeof v === "string" && (POI_KINDS as readonly string[]).includes(v);
}

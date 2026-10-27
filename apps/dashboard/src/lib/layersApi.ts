import type { ApiClient } from "./api";
import type { BBox } from "./filters";
import type {
  FeatureBody,
  FeaturePatch,
  ImportMode,
  LayerBody,
  LayerFeature,
  LayerFeatures,
  LayerImport,
  LayerImportDetail,
  LayerPatch,
  LayerRevision,
  MapLayer,
  MapLayers,
  ReviewBody,
  ReviewQueue,
  ReviewResult,
  Confidence,
} from "./layers";

const enc = encodeURIComponent;
const L = "/api/v1/staff/layers";
const layerPath = (key: string) => `${L}/${enc(key)}`;

export const layerKeys = {
  all: ["layers"] as const,
  imports: (key: string) => ["layers", key, "imports"] as const,
  features: (key: string, bbox: BBox | null) => ["layers", key, "features", bbox] as const,
  deletedFeatures: (key: string) => ["layers", key, "features", "deleted"] as const,
  revisions: (key: string) => ["layers", key, "revisions"] as const,
  review: (key: string, view: string) => ["layers", key, "review", view] as const,
};

/** A file the browser saves (export, template). */
export interface Download {
  blob: Blob;
  filename: string;
}

function filenameOf(response: Response, fallback: string): string {
  const match = /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "");
  return match?.[1] ?? fallback;
}

/** Map data layers (phase B1, docs/phase-b/design.md §2.7). */
export function layersApi(api: ApiClient) {
  return {
    layers: (signal?: AbortSignal) => api.request<MapLayers>(L, { signal }),

    createLayer: (body: LayerBody) => api.request<MapLayer>(L, { method: "POST", body }),

    updateLayer: (key: string, body: LayerPatch) => api.request<MapLayer>(layerPath(key), { method: "PATCH", body }),

    // Phase L1a: delete (kept 30 days), restore, erase now, settings revisions.
    deleteLayer: (key: string, reason: string) =>
      api.request<MapLayer>(layerPath(key), { method: "DELETE", body: { reason } }),

    restoreLayer: (key: string, reason: string) =>
      api.request<MapLayer>(`${layerPath(key)}/restore`, { method: "POST", body: { reason } }),

    purgeLayer: (key: string, reason: string) =>
      api.requestRaw(`${layerPath(key)}/purge`, { method: "DELETE", body: { reason } }).then(() => undefined),

    layerRevisions: (key: string, signal?: AbortSignal) =>
      api.request<{ items: LayerRevision[] }>(`${layerPath(key)}/revisions`, { signal }).then((b) => b.items),

    restoreRevision: (key: string, n: number, reason: string) =>
      api.request<MapLayer>(`${layerPath(key)}/revisions/${n}/restore`, { method: "POST", body: { reason } }),

    reviewQueue: (
      key: string,
      view: { confidence?: Confidence; duplicates?: boolean; offset?: number },
      signal?: AbortSignal,
    ) =>
      api.request<ReviewQueue>(`${layerPath(key)}/review`, {
        query: {
          confidence: view.confidence,
          duplicates: view.duplicates ? "true" : undefined,
          offset: view.offset ? String(view.offset) : undefined,
        },
        signal,
      }),

    review: (key: string, body: ReviewBody) =>
      api.request<ReviewResult>(`${layerPath(key)}/review`, { method: "POST", body }),

    deletedFeatures: (key: string, signal?: AbortSignal) =>
      api.request<LayerFeatures>(`${layerPath(key)}/features`, { query: { deleted: "true" }, signal }),

    deleteFeature: (key: string, id: string, reason: string) =>
      api.request<LayerFeature>(`${layerPath(key)}/features/${enc(id)}`, { method: "DELETE", body: { reason } }),

    restoreFeature: (key: string, id: string, reason: string) =>
      api.request<LayerFeature>(`${layerPath(key)}/features/${enc(id)}/restore`, { method: "POST", body: { reason } }),

    previewImport: (key: string, file: File, mode: ImportMode) =>
      api.request<LayerImportDetail>(`${layerPath(key)}/imports`, {
        method: "POST",
        query: { file_name: file.name, mode },
        rawBody: file,
      }),

    layerImports: (key: string, signal?: AbortSignal) =>
      api.request<{ items: LayerImport[] }>(`${layerPath(key)}/imports`, { signal }).then((b) => b.items),

    applyImport: (key: string, id: string, reason: string) =>
      api.request<LayerImport>(`${layerPath(key)}/imports/${enc(id)}/apply`, { method: "POST", body: { reason } }),

    discardImport: (key: string, id: string) =>
      api.request<LayerImport>(`${layerPath(key)}/imports/${enc(id)}/discard`, { method: "POST", body: {} }),

    undoImport: (key: string, id: string, reason: string) =>
      api.request<LayerImport>(`${layerPath(key)}/imports/${enc(id)}/undo`, { method: "POST", body: { reason } }),

    layerFeatures: (key: string, bbox: BBox | null, signal?: AbortSignal) =>
      api.request<LayerFeatures>(`${layerPath(key)}/features`, {
        query: { bbox: bbox ? bbox.map((v) => v.toFixed(5)).join(",") : undefined },
        signal,
      }),

    createFeature: (key: string, body: FeatureBody) =>
      api.request<LayerFeature>(`${layerPath(key)}/features`, { method: "POST", body }),

    updateFeature: (key: string, id: string, body: FeaturePatch) =>
      api.request<LayerFeature>(`${layerPath(key)}/features/${enc(id)}`, { method: "PATCH", body }),

    exportLayer: async (key: string, format: "csv" | "xlsx" | "geojson", lang: string): Promise<Download> => {
      const response = await api.requestRaw(`${layerPath(key)}/export`, { query: { format, lang }, accept: "*/*" });
      return { blob: await response.blob(), filename: filenameOf(response, `${key}.${format}`) };
    },

    layerTemplate: async (format: "csv" | "xlsx", lang: string): Promise<Download> => {
      const response = await api.requestRaw(`${L}/template`, { query: { format, lang }, accept: "*/*" });
      return { blob: await response.blob(), filename: filenameOf(response, `layer-template.${format}`) };
    },
  };
}

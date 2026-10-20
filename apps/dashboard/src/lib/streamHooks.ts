import { useInfiniteQuery } from "@tanstack/react-query";
import { useServices } from "../context/services";
import { streamKeys, type StreamListFilters } from "./streamsApi";

/** Paged stream list (§4), kept current by the live events (lib/streamsCache.ts). */
export function useStreamList(filters: StreamListFilters) {
  const { api } = useServices();
  return useInfiniteQuery({
    queryKey: streamKeys.list(filters),
    queryFn: ({ pageParam, signal }) => api.streams(filters, { cursor: pageParam, signal }),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    // Events keep it current; the interval only covers a lost live connection.
    refetchInterval: filters.status === "live" ? 60_000 : false,
  });
}

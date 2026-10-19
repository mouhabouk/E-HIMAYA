import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useServices } from "../../context/services";
import { queryKeys, type RegisterName, type RegisterTypes } from "../../lib/portalApi";

/**
 * List + create/update/delete of one register (team, hazmat, equipment, features). Every write also
 * refreshes the institution, whose classification, completeness and alerts depend on the registers.
 */
export function useRegister<R extends RegisterName>(orgId: string, register: R) {
  const { api } = useServices();
  const queryClient = useQueryClient();
  const key = queryKeys.register(orgId, register);
  const list = useQuery({ queryKey: key, queryFn: ({ signal }) => api.list(orgId, register, signal) });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: key });
    await queryClient.invalidateQueries({ queryKey: queryKeys.org(orgId), exact: true });
    void queryClient.invalidateQueries({ queryKey: queryKeys.myOrgs });
  };
  const save = useMutation({
    mutationFn: ({ id, input }: { id: string | null; input: RegisterTypes[R]["input"] }) =>
      id ? api.update(orgId, register, id, input) : api.create(orgId, register, input),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.remove(orgId, register, id),
    onSuccess: refresh,
  });
  return { list, save, remove };
}

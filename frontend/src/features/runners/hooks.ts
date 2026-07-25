import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { runnersApi, triggersApi } from "@/api/endpoints";
import { EXECUTIONS_QUERY_KEY } from "@/features/executions/hooks";
import type { RunnerCreate, RunnerUpdate } from "@/types/runner";

export const RUNNERS_QUERY_KEY = ["runners"] as const;

export function runnersQueryKey(projectId: number) {
  return [...RUNNERS_QUERY_KEY, projectId] as const;
}

export function useRunners(projectId: number) {
  return useQuery({
    queryKey: runnersQueryKey(projectId),
    queryFn: () => runnersApi.list(projectId),
  });
}

export function useRunner(runnerId: number, enabled = true) {
  return useQuery({
    queryKey: [...RUNNERS_QUERY_KEY, "detail", runnerId] as const,
    queryFn: () => runnersApi.get(runnerId),
    enabled,
  });
}

/** Create a runner; onSuccess is left to the caller (navigation + 422 mapping). */
export function useCreateRunner(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: RunnerCreate) => runnersApi.create(body),
    onSuccess: (runner) => {
      queryClient.invalidateQueries({ queryKey: runnersQueryKey(projectId) });
      toast.success(`Runner ${runner.name} creado`);
    },
  });
}

/** Update a runner; onSuccess is left to the caller (navigation + 422 mapping). */
export function useUpdateRunner(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runnerId, body }: { runnerId: number; body: RunnerUpdate }) =>
      runnersApi.update(runnerId, body),
    onSuccess: (runner) => {
      queryClient.invalidateQueries({ queryKey: runnersQueryKey(projectId) });
      queryClient.invalidateQueries({ queryKey: [...RUNNERS_QUERY_KEY, "detail"] });
      toast.success(`Runner ${runner.name} actualizado`);
    },
  });
}

export function useDeleteRunner(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runnerId: number) => runnersApi.remove(runnerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: runnersQueryKey(projectId) });
      toast.success("Runner eliminado");
    },
    onError: () => {
      toast.error("No se pudo eliminar el runner");
    },
  });
}

/** Toggle a runner on/off; the list is invalidated once the backend confirms. */
export function useToggleRunner(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runnerId, enable }: { runnerId: number; enable: boolean }) =>
      enable ? runnersApi.enable(runnerId) : runnersApi.disable(runnerId),
    onSuccess: (runner) => {
      queryClient.invalidateQueries({ queryKey: runnersQueryKey(projectId) });
      toast.success(runner.is_enabled ? "Runner activado" : "Runner desactivado");
    },
    onError: () => {
      toast.error("No se pudo cambiar el estado del runner");
    },
  });
}

/**
 * Manual trigger (spec 6.3): enqueues an execution and invalidates every
 * executions view (prefix match) so the queued execution shows up. The toast
 * action navigates to the new execution's detail.
 */
export function useTriggerRunner() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (runnerId: number) => triggersApi.trigger(runnerId),
    onSuccess: (execution) => {
      queryClient.invalidateQueries({ queryKey: EXECUTIONS_QUERY_KEY });
      toast.success("Ejecución encolada", {
        action: {
          label: "Ver ejecución",
          onClick: () => navigate(`/executions/${execution.id}`),
        },
      });
    },
    onError: () => {
      toast.error("No se pudo encolar la ejecución");
    },
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { envVarsApi } from "@/api/endpoints";
import type { EnvVarCreate, EnvVarRotate } from "@/types/env-var";

export const ENV_VARS_QUERY_KEY = ["env-vars"] as const;

export function envVarsQueryKey(projectId: number) {
  return [...ENV_VARS_QUERY_KEY, projectId] as const;
}

export function useEnvVars(projectId: number) {
  return useQuery({
    queryKey: envVarsQueryKey(projectId),
    queryFn: () => envVarsApi.list(projectId),
  });
}

/** Create an env var; onError is left to the caller (form error mapping). */
export function useCreateEnvVar(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EnvVarCreate) => envVarsApi.create(body),
    onSuccess: (envVar) => {
      queryClient.invalidateQueries({ queryKey: envVarsQueryKey(projectId) });
      toast.success(`Variable ${envVar.key} creada`);
    },
  });
}

/** Rotate an env var value (write-only); onError is left to the caller. */
export function useRotateEnvVar(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ envVarId, body }: { envVarId: number; body: EnvVarRotate }) =>
      envVarsApi.rotate(envVarId, body),
    onSuccess: (envVar) => {
      queryClient.invalidateQueries({ queryKey: envVarsQueryKey(projectId) });
      toast.success(`Variable ${envVar.key} rotada`);
    },
  });
}

export function useDeleteEnvVar(projectId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (envVarId: number) => envVarsApi.remove(envVarId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: envVarsQueryKey(projectId) });
      toast.success("Variable eliminada");
    },
    onError: () => {
      toast.error("No se pudo eliminar la variable");
    },
  });
}

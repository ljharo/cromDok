import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { apiKeysApi } from "@/api/endpoints";
import type { ApiKeyCreate } from "@/types/api-key";

export const API_KEYS_QUERY_KEY = ["api-keys"] as const;

export function useApiKeys() {
  return useQuery({
    queryKey: API_KEYS_QUERY_KEY,
    queryFn: apiKeysApi.list,
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ApiKeyCreate) => apiKeysApi.create(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
    },
    onError: () => {
      toast.error("No se pudo crear la API key");
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (apiKeyId: number) => apiKeysApi.revoke(apiKeyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: API_KEYS_QUERY_KEY });
      toast.success("API key revocada");
    },
    onError: () => {
      toast.error("No se pudo revocar la API key");
    },
  });
}

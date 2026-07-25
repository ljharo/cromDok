import { useQuery } from "@tanstack/react-query";

import { authApi } from "@/api/endpoints";
import type { User } from "@/types/user";

export const ME_QUERY_KEY = ["me"] as const;

/**
 * Session source of truth: who is logged in and with which role.
 * 401 is an expected answer (anonymous), so retries are disabled.
 */
export function useCurrentUser() {
  return useQuery<User>({
    queryKey: ME_QUERY_KEY,
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

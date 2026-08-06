import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { authApi } from "@/api/endpoints";
import { ME_QUERY_KEY } from "@/hooks/useCurrentUser";
import type { LoginRequest, PasswordChangeRequest } from "@/types/auth";

/**
 * Login mutation. On success the returned user becomes the cached session
 * and the caller decides where to navigate (original destination or "/").
 */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: LoginRequest) => authApi.login(body),
    onSuccess: (user) => {
      queryClient.setQueryData(ME_QUERY_KEY, user);
    },
  });
}

/**
 * Logout mutation: revokes the session server-side, wipes all cached data
 * and navigates to /login.
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
}

/**
 * Self-service password change. The server revokes every session (including
 * the current one) and clears the cookie, so on success all cached data is
 * wiped and the user is sent to /login to authenticate with the new password.
 */
export function useChangePassword() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (body: PasswordChangeRequest) => authApi.changePassword(body),
    onSuccess: () => {
      queryClient.clear();
      navigate("/login", { replace: true });
    },
  });
}

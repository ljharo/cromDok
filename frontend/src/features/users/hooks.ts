import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { usersApi } from "@/api/endpoints";
import type { PasswordReset, UserCreate } from "@/types/user";

export const USERS_QUERY_KEY = ["users"] as const;

export function useUsers() {
  return useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: usersApi.list,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => usersApi.create(body),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
      toast.success(`Usuario ${user.username} creado`);
    },
    onError: () => {
      toast.error("No se pudo crear el usuario");
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => usersApi.remove(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
      toast.success("Usuario eliminado");
    },
    onError: () => {
      toast.error("No se pudo eliminar el usuario");
    },
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ userId, body }: { userId: number; body: PasswordReset }) =>
      usersApi.resetPassword(userId, body),
    onSuccess: () => {
      toast.success("Contraseña restablecida");
    },
    onError: () => {
      toast.error("No se pudo restablecer la contraseña");
    },
  });
}

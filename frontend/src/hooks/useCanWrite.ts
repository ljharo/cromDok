import { useCurrentUser } from "@/hooks/useCurrentUser";

/**
 * Write permission (spec 9.4.1): every mutation endpoint requires
 * operator or admin; viewers are read-only. Use this to hide write
 * actions in the UI.
 */
export function useCanWrite() {
  const { data: user } = useCurrentUser();
  return user?.role === "operator" || user?.role === "admin";
}

import { z } from "zod";

// Mirrors cron_dok.domain.entities.user.UserRole
export const userRoleSchema = z.enum(["admin", "operator", "viewer"]);
export type UserRole = z.infer<typeof userRoleSchema>;

// Mirrors UserResponse (never exposes the password hash)
export const userSchema = z.object({
  id: z.number().int(),
  username: z.string(),
  role: userRoleSchema,
  is_active: z.boolean(),
  must_change_password: z.boolean(),
  created_at: z.string(),
});
export type User = z.infer<typeof userSchema>;

// Mirrors UserCreate. Password minimum of 12 chars per spec 9.4.1
// (the backend enforces it too via WeakPasswordError → 422).
export const userCreateSchema = z.object({
  username: z
    .string()
    .min(1, "El nombre de usuario es obligatorio")
    .max(100, "Máximo 100 caracteres"),
  password: z
    .string()
    .min(12, "La contraseña debe tener al menos 12 caracteres")
    .max(500, "Máximo 500 caracteres"),
  role: userRoleSchema,
});
export type UserCreate = z.infer<typeof userCreateSchema>;

// Mirrors PasswordReset
export const passwordResetSchema = z.object({
  password: z
    .string()
    .min(12, "La contraseña debe tener al menos 12 caracteres")
    .max(500, "Máximo 500 caracteres"),
});
export type PasswordReset = z.infer<typeof passwordResetSchema>;

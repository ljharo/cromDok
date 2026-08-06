import { z } from "zod";

// Mirrors LoginRequest (POST /auth/login)
export const loginRequestSchema = z.object({
  username: z
    .string()
    .min(1, "El nombre de usuario es obligatorio")
    .max(100, "Máximo 100 caracteres"),
  password: z.string().min(1, "La contraseña es obligatoria").max(500, "Máximo 500 caracteres"),
});
export type LoginRequest = z.infer<typeof loginRequestSchema>;

// Mirrors PasswordChange (POST /auth/password); the confirmation is a
// client-side-only concern and never reaches the API.
export const passwordChangeSchema = z
  .object({
    current_password: z.string().min(1, "La contraseña actual es obligatoria"),
    new_password: z.string().min(12, "Mínimo 12 caracteres").max(500, "Máximo 500 caracteres"),
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Las contraseñas no coinciden",
    path: ["confirm_password"],
  });
export type PasswordChange = z.infer<typeof passwordChangeSchema>;

/** API body of POST /auth/password (without the client-side confirmation). */
export type PasswordChangeRequest = Pick<PasswordChange, "current_password" | "new_password">;

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

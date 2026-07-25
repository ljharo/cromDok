import { z } from "zod";

// Mirrors EnvVarResponse. The value is NEVER returned by the API (spec 9.1):
// the UI renders "••••••••" and rotation is write-only.
export const envVarSummarySchema = z.object({
  id: z.number().int(),
  project_id: z.number().int(),
  key: z.string(),
  runner_id: z.number().int().nullable(),
});
export type EnvVarSummary = z.infer<typeof envVarSummarySchema>;

// Keys that would overwrite container system variables (spec 9.1 blacklist)
export const ENV_VAR_BLACKLIST = ["PATH", "LD_PRELOAD", "HOME"] as const;

// Mirrors _KEY_PATTERN in cron_dok.domain.entities.env_var
const ENV_VAR_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

// Mirrors EnvVarCreate
export const envVarCreateSchema = z.object({
  project_id: z.number().int(),
  key: z
    .string()
    .min(1, "La clave es obligatoria")
    .max(200, "Máximo 200 caracteres")
    .regex(
      ENV_VAR_KEY_PATTERN,
      "Formato no válido: usa letras, dígitos y guiones bajos, sin empezar por dígito",
    )
    .refine((key) => !ENV_VAR_BLACKLIST.includes(key as (typeof ENV_VAR_BLACKLIST)[number]), {
      message: "Clave no permitida: sobrescribiría una variable del sistema",
    }),
  value: z.string().min(1, "El valor es obligatorio"),
  runner_id: z.number().int().nullable().default(null),
});
export type EnvVarCreate = z.infer<typeof envVarCreateSchema>;

// Mirrors EnvVarRotate (write-only)
export const envVarRotateSchema = z.object({
  value: z.string().min(1, "El valor es obligatorio"),
});
export type EnvVarRotate = z.infer<typeof envVarRotateSchema>;

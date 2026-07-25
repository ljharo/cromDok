import { z } from "zod";

// Mirrors cron_dok.domain.entities.api_key.ApiKeyScope
export const apiKeyScopeSchema = z.enum(["runners:read", "runners:execute", "admin"]);
export type ApiKeyScope = z.infer<typeof apiKeyScopeSchema>;

export const API_KEY_SCOPES: ApiKeyScope[] = ["runners:read", "runners:execute", "admin"];

// Mirrors ApiKeyResponse (never exposes the hash nor the token)
export const apiKeySchema = z.object({
  id: z.number().int(),
  name: z.string(),
  scopes: z.array(apiKeyScopeSchema),
  created_by: z.number().int(),
  created_at: z.string(),
  last_used_at: z.string().nullable(),
  revoked: z.boolean(),
});
export type ApiKey = z.infer<typeof apiKeySchema>;

// Mirrors ApiKeyCreate
export const apiKeyCreateSchema = z.object({
  name: z.string().min(1, "El nombre es obligatorio").max(100, "Máximo 100 caracteres"),
  scopes: z.array(apiKeyScopeSchema).min(1, "Selecciona al menos un scope"),
});
export type ApiKeyCreate = z.infer<typeof apiKeyCreateSchema>;

// Mirrors ApiKeyCreatedResponse: the plaintext token, shown exactly once.
export const apiKeyCreatedSchema = apiKeySchema.extend({
  token: z.string(),
});
export type ApiKeyCreated = z.infer<typeof apiKeyCreatedSchema>;

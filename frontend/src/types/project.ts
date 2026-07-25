import { z } from "zod";

// Mirrors ProjectResponse
export const projectSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  description: z.string(),
  created_at: z.string(),
});
export type Project = z.infer<typeof projectSchema>;

// Mirrors ProjectCreate
export const projectCreateSchema = z.object({
  name: z.string().min(1, "El nombre es obligatorio").max(100, "Máximo 100 caracteres"),
  description: z.string().default(""),
});
export type ProjectCreate = z.infer<typeof projectCreateSchema>;

// Mirrors ProjectUpdate (null/undefined fields are left unchanged)
export const projectUpdateSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  description: z.string().optional(),
});
export type ProjectUpdate = z.infer<typeof projectUpdateSchema>;

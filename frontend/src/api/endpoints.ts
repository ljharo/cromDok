import { client } from "./client";
import type { ApiKey, ApiKeyCreate, ApiKeyCreated } from "@/types/api-key";
import type { LoginRequest } from "@/types/auth";
import type { EnvVarCreate, EnvVarRotate, EnvVarSummary } from "@/types/env-var";
import type { Execution, LogChunk } from "@/types/execution";
import type { Project, ProjectCreate, ProjectUpdate } from "@/types/project";
import type { Runner, RunnerCreate, RunnerUpdate } from "@/types/runner";
import type { PasswordReset, User, UserCreate } from "@/types/user";

// Thin wrappers over the API contract (routers under /api/v1, spec 9.4).
// Pages never call `client` directly; they use TanStack Query hooks that
// wrap these functions.

export const projectsApi = {
  list: async (): Promise<Project[]> => {
    const { data } = await client.get<Project[]>("/projects");
    return data;
  },
  get: async (projectId: number): Promise<Project> => {
    const { data } = await client.get<Project>(`/projects/${projectId}`);
    return data;
  },
  create: async (body: ProjectCreate): Promise<Project> => {
    const { data } = await client.post<Project>("/projects", body);
    return data;
  },
  update: async (projectId: number, body: ProjectUpdate): Promise<Project> => {
    const { data } = await client.patch<Project>(`/projects/${projectId}`, body);
    return data;
  },
  remove: async (projectId: number): Promise<void> => {
    await client.delete(`/projects/${projectId}`);
  },
};

export const runnersApi = {
  list: async (projectId: number): Promise<Runner[]> => {
    const { data } = await client.get<Runner[]>("/runners", {
      params: { project_id: projectId },
    });
    return data;
  },
  get: async (runnerId: number): Promise<Runner> => {
    const { data } = await client.get<Runner>(`/runners/${runnerId}`);
    return data;
  },
  create: async (body: RunnerCreate): Promise<Runner> => {
    const { data } = await client.post<Runner>("/runners", body);
    return data;
  },
  update: async (runnerId: number, body: RunnerUpdate): Promise<Runner> => {
    const { data } = await client.patch<Runner>(`/runners/${runnerId}`, body);
    return data;
  },
  remove: async (runnerId: number): Promise<void> => {
    await client.delete(`/runners/${runnerId}`);
  },
  enable: async (runnerId: number): Promise<Runner> => {
    const { data } = await client.post<Runner>(`/runners/${runnerId}/enable`);
    return data;
  },
  disable: async (runnerId: number): Promise<Runner> => {
    const { data } = await client.post<Runner>(`/runners/${runnerId}/disable`);
    return data;
  },
};

export const triggersApi = {
  trigger: async (runnerId: number): Promise<Execution> => {
    const { data } = await client.post<Execution>(`/triggers/${runnerId}`);
    return data;
  },
};

export const authApi = {
  login: async (body: LoginRequest): Promise<User> => {
    const { data } = await client.post<User>("/auth/login", body);
    return data;
  },
  logout: async (): Promise<void> => {
    await client.post("/auth/logout");
  },
  me: async (): Promise<User> => {
    const { data } = await client.get<User>("/auth/me");
    return data;
  },
};

export const executionsApi = {
  list: async (
    runnerId: number,
    { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {},
  ): Promise<Execution[]> => {
    const { data } = await client.get<Execution[]>(`/runners/${runnerId}/executions`, {
      params: { limit, offset },
    });
    return data;
  },
  get: async (executionId: number): Promise<Execution> => {
    const { data } = await client.get<Execution>(`/executions/${executionId}`);
    return data;
  },
  logs: async (executionId: number, offset = 0): Promise<LogChunk> => {
    const { data } = await client.get<LogChunk>(`/executions/${executionId}/logs`, {
      params: { offset },
    });
    return data;
  },
};

export const envVarsApi = {
  list: async (projectId: number): Promise<EnvVarSummary[]> => {
    const { data } = await client.get<EnvVarSummary[]>("/env-vars", {
      params: { project_id: projectId },
    });
    return data;
  },
  create: async (body: EnvVarCreate): Promise<EnvVarSummary> => {
    const { data } = await client.post<EnvVarSummary>("/env-vars", body);
    return data;
  },
  rotate: async (envVarId: number, body: EnvVarRotate): Promise<EnvVarSummary> => {
    const { data } = await client.post<EnvVarSummary>(`/env-vars/${envVarId}/rotate`, body);
    return data;
  },
  remove: async (envVarId: number): Promise<void> => {
    await client.delete(`/env-vars/${envVarId}`);
  },
};

export const usersApi = {
  list: async (): Promise<User[]> => {
    const { data } = await client.get<User[]>("/users");
    return data;
  },
  create: async (body: UserCreate): Promise<User> => {
    const { data } = await client.post<User>("/users", body);
    return data;
  },
  remove: async (userId: number): Promise<void> => {
    await client.delete(`/users/${userId}`);
  },
  resetPassword: async (userId: number, body: PasswordReset): Promise<void> => {
    await client.post(`/users/${userId}/password`, body);
  },
};

export const apiKeysApi = {
  list: async (): Promise<ApiKey[]> => {
    const { data } = await client.get<ApiKey[]>("/api-keys");
    return data;
  },
  create: async (body: ApiKeyCreate): Promise<ApiKeyCreated> => {
    const { data } = await client.post<ApiKeyCreated>("/api-keys", body);
    return data;
  },
  revoke: async (apiKeyId: number): Promise<void> => {
    await client.delete(`/api-keys/${apiKeyId}`);
  },
};

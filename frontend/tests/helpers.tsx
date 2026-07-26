import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError } from "axios";
import type { InternalAxiosRequestConfig, AxiosResponse } from "axios";

import type { User, UserRole } from "@/types/user";
import type { ApiKey } from "@/types/api-key";
import type { EnvVarSummary } from "@/types/env-var";
import type { Execution } from "@/types/execution";
import type { Project } from "@/types/project";
import type { Runner } from "@/types/runner";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

/** Render with a fresh QueryClient so queries never leak between tests. */
export function renderWithQuery(ui: ReactElement) {
  return render(<QueryClientProvider client={createTestQueryClient()}>{ui}</QueryClientProvider>);
}

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    username: "admin",
    role: "admin" as UserRole,
    is_active: true,
    must_change_password: false,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 1,
    name: "ETL nocturno",
    description: "Procesos batch",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeRunner(overrides: Partial<Runner> = {}): Runner {
  return {
    id: 1,
    project_id: 1,
    name: "Backup diario",
    script_content: "echo ok",
    language: "python",
    cron_expression: "*/5 * * * *",
    resource_limits: {
      memory_mb: 256,
      cpu_quota: 1.0,
      pids_limit: 100,
      network_enabled: false,
    },
    is_enabled: true,
    timeout_seconds: 300,
    on_overlap: "skip",
    dependencies: null,
    ...overrides,
  };
}

export function makeExecution(overrides: Partial<Execution> = {}): Execution {
  return {
    id: 1,
    runner_id: 1,
    status: "succeeded",
    trigger_type: "scheduled",
    started_at: "2026-01-01T10:00:00Z",
    finished_at: "2026-01-01T10:01:00Z",
    exit_code: 0,
    duration_ms: 60_000,
    log_path: "/var/log/crondok/1.log",
    ...overrides,
  };
}

export function makeEnvVar(overrides: Partial<EnvVarSummary> = {}): EnvVarSummary {
  return {
    id: 5,
    project_id: 1,
    key: "API_TOKEN",
    runner_id: null,
    ...overrides,
  };
}

export function makeApiKey(overrides: Partial<ApiKey> = {}): ApiKey {
  return {
    id: 1,
    name: "ci-pipeline",
    scopes: ["runners:execute"],
    created_by: 1,
    created_at: "2026-01-01T00:00:00Z",
    last_used_at: null,
    revoked: false,
    ...overrides,
  };
}

/** Build a real AxiosError with the given HTTP status (e.g. 401 responses). */
export function axiosError(status: number): AxiosError {
  const config = { headers: {} } as unknown as InternalAxiosRequestConfig;
  const response = {
    status,
    statusText: "",
    headers: {},
    config,
    data: { detail: "error" },
  } as AxiosResponse;
  return new AxiosError(
    `Request failed with status ${status}`,
    "ERR_BAD_RESPONSE",
    config,
    undefined,
    response,
  );
}

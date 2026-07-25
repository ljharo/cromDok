import { describe, expect, it, vi } from "vitest";

import { client } from "@/api/client";
import {
  authApi,
  envVarsApi,
  executionsApi,
  projectsApi,
  runnersApi,
  triggersApi,
  usersApi,
} from "@/api/endpoints";
import { makeUser } from "../helpers";

vi.mock("@/api/client", () => ({
  client: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: { response: { use: vi.fn() } },
  },
}));

const mockedClient = vi.mocked(client, true);

describe("endpoints (contrato HTTP)", () => {
  it("auth: login, logout y me usan las rutas del contrato", async () => {
    const user = makeUser();
    mockedClient.post.mockResolvedValue({ data: user });
    mockedClient.get.mockResolvedValue({ data: user });

    await authApi.login({ username: "admin", password: "secreto" }); // pragma: allowlist secret
    expect(mockedClient.post).toHaveBeenCalledWith("/auth/login", {
      username: "admin",
      password: "secreto", // pragma: allowlist secret
    });

    await authApi.me();
    expect(mockedClient.get).toHaveBeenCalledWith("/auth/me");

    await authApi.logout();
    expect(mockedClient.post).toHaveBeenCalledWith("/auth/logout");
  });

  it("users: list, create, delete y reset password", async () => {
    const user = makeUser();
    mockedClient.get.mockResolvedValue({ data: [user] });
    mockedClient.post.mockResolvedValue({ data: user });
    mockedClient.delete.mockResolvedValue({});

    await usersApi.list();
    expect(mockedClient.get).toHaveBeenCalledWith("/users");

    await usersApi.create({ username: "nuevo", password: "larga-12-caracteres", role: "viewer" }); // pragma: allowlist secret
    expect(mockedClient.post).toHaveBeenCalledWith("/users", {
      username: "nuevo",
      password: "larga-12-caracteres", // pragma: allowlist secret
      role: "viewer",
    });

    await usersApi.remove(2);
    expect(mockedClient.delete).toHaveBeenCalledWith("/users/2");

    await usersApi.resetPassword(2, { password: "otra-larga-12" }); // pragma: allowlist secret
    expect(mockedClient.post).toHaveBeenCalledWith("/users/2/password", {
      password: "otra-larga-12", // pragma: allowlist secret
    });
  });

  it("projects: CRUD sobre las rutas del contrato", async () => {
    const project = { id: 1, name: "ETL", description: "", created_at: "2026-01-01" };
    mockedClient.get.mockResolvedValue({ data: [project] });
    mockedClient.post.mockResolvedValue({ data: project });
    mockedClient.patch.mockResolvedValue({ data: project });
    mockedClient.delete.mockResolvedValue({});

    await projectsApi.list();
    expect(mockedClient.get).toHaveBeenCalledWith("/projects");

    await projectsApi.get(1);
    expect(mockedClient.get).toHaveBeenCalledWith("/projects/1");

    await projectsApi.create({ name: "ETL", description: "" });
    expect(mockedClient.post).toHaveBeenCalledWith("/projects", { name: "ETL", description: "" });

    await projectsApi.update(1, { name: "ETL 2" });
    expect(mockedClient.patch).toHaveBeenCalledWith("/projects/1", { name: "ETL 2" });

    await projectsApi.remove(1);
    expect(mockedClient.delete).toHaveBeenCalledWith("/projects/1");
  });

  it("runners: CRUD y enable/disable sobre las rutas del contrato", async () => {
    mockedClient.get.mockResolvedValue({ data: [] });
    mockedClient.post.mockResolvedValue({ data: {} });
    mockedClient.delete.mockResolvedValue({});

    await runnersApi.list(3);
    expect(mockedClient.get).toHaveBeenCalledWith("/runners", {
      params: { project_id: 3 },
    });

    await runnersApi.enable(7);
    expect(mockedClient.post).toHaveBeenCalledWith("/runners/7/enable");

    await runnersApi.disable(7);
    expect(mockedClient.post).toHaveBeenCalledWith("/runners/7/disable");

    await runnersApi.remove(7);
    expect(mockedClient.delete).toHaveBeenCalledWith("/runners/7");
  });

  it("executions: list por runner, detalle y logs incrementales con offset", async () => {
    mockedClient.get.mockResolvedValue({ data: [] });

    await executionsApi.list(3, { limit: 10, offset: 20 });
    expect(mockedClient.get).toHaveBeenCalledWith("/runners/3/executions", {
      params: { limit: 10, offset: 20 },
    });

    await executionsApi.get(9);
    expect(mockedClient.get).toHaveBeenCalledWith("/executions/9");

    await executionsApi.logs(9, 128);
    expect(mockedClient.get).toHaveBeenCalledWith("/executions/9/logs", {
      params: { offset: 128 },
    });
  });

  it("triggers: POST sin body a /triggers/{runnerId}", async () => {
    mockedClient.post.mockResolvedValue({ data: { id: 42 } });

    await triggersApi.trigger(7);
    expect(mockedClient.post).toHaveBeenCalledWith("/triggers/7");
  });

  it("env-vars: list por proyecto, create, rotate y delete", async () => {
    const summary = { id: 5, project_id: 3, key: "API_TOKEN", runner_id: null };
    mockedClient.get.mockResolvedValue({ data: [summary] });
    mockedClient.post.mockResolvedValue({ data: summary });
    mockedClient.delete.mockResolvedValue({});

    await envVarsApi.list(3);
    expect(mockedClient.get).toHaveBeenCalledWith("/env-vars", {
      params: { project_id: 3 },
    });

    await envVarsApi.create({ project_id: 3, key: "API_TOKEN", value: "secreto", runner_id: null });
    expect(mockedClient.post).toHaveBeenCalledWith("/env-vars", {
      project_id: 3,
      key: "API_TOKEN",
      value: "secreto",
      runner_id: null,
    });

    await envVarsApi.rotate(5, { value: "nuevo" });
    expect(mockedClient.post).toHaveBeenCalledWith("/env-vars/5/rotate", { value: "nuevo" });

    await envVarsApi.remove(5);
    expect(mockedClient.delete).toHaveBeenCalledWith("/env-vars/5");
  });
});

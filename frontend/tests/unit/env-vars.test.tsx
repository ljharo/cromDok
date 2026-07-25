import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import EnvVarsTable, { MASKED_VALUE } from "@/features/env-vars/EnvVarsTable";
import { authApi, envVarsApi, runnersApi } from "@/api/endpoints";
import { makeEnvVar, makeRunner, makeUser, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  runnersApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
  },
  envVarsApi: {
    list: vi.fn(),
    create: vi.fn(),
    rotate: vi.fn(),
    remove: vi.fn(),
  },
}));

const mockedAuth = vi.mocked(authApi);
const mockedRunners = vi.mocked(runnersApi);
const mockedEnvVars = vi.mocked(envVarsApi);

// jsdom lacks the pointer APIs that Radix Select/DropdownMenu need.
beforeAll(() => {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
  Element.prototype.scrollIntoView = () => {};
  window.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

function renderTable(role: "admin" | "operator" | "viewer" = "operator") {
  mockedAuth.me.mockResolvedValue(makeUser({ role }));
  mockedRunners.list.mockResolvedValue([makeRunner({ id: 9, name: "Backup diario" })]);
  return renderWithQuery(<EnvVarsTable projectId={1} />);
}

describe("EnvVarsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("nunca muestra valores: siempre la máscara", async () => {
    mockedEnvVars.list.mockResolvedValue([
      makeEnvVar({ id: 5, key: "API_TOKEN" }),
      makeEnvVar({ id: 6, key: "DB_PASSWORD", runner_id: 9 }),
    ]);
    renderTable();

    expect(await screen.findByText("API_TOKEN")).toBeInTheDocument();
    expect(screen.getAllByText(MASKED_VALUE)).toHaveLength(2);
    // Ningún valor en claro puede aparecer en el DOM.
    expect(screen.queryByText(/secreto|password123/i)).not.toBeInTheDocument();
    // Ámbito: proyecto vs runner concreto.
    expect(screen.getByText("Proyecto")).toBeInTheDocument();
    expect(screen.getByText("Backup diario")).toBeInTheDocument();
  });

  it("la blacklist (PATH/LD_PRELOAD/HOME) se rechaza en cliente sin llamar a la API", async () => {
    mockedEnvVars.list.mockResolvedValue([]);
    renderTable();

    fireEvent.click(await screen.findByRole("button", { name: /Nueva variable/ }));
    fireEvent.change(await screen.findByLabelText("Clave"), { target: { value: "PATH" } });
    fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "/tmp" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear variable" }));

    expect(
      await screen.findByText("Clave no permitida: sobrescribiría una variable del sistema"),
    ).toBeInTheDocument();
    expect(mockedEnvVars.create).not.toHaveBeenCalled();
  });

  it("crea una variable con ámbito de proyecto (runner_id null)", async () => {
    mockedEnvVars.list.mockResolvedValue([]);
    mockedEnvVars.create.mockResolvedValue(makeEnvVar());
    renderTable();

    fireEvent.click(await screen.findByRole("button", { name: /Nueva variable/ }));
    fireEvent.change(await screen.findByLabelText("Clave"), {
      target: { value: "API_TOKEN" },
    });
    fireEvent.change(screen.getByLabelText("Valor"), { target: { value: "s3cr3t" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear variable" }));

    await waitFor(() => {
      expect(mockedEnvVars.create).toHaveBeenCalledWith({
        project_id: 1,
        key: "API_TOKEN",
        value: "s3cr3t",
        runner_id: null,
      });
    });
  });

  it("rotar llama al endpoint de rotate solo con el nuevo valor", async () => {
    mockedEnvVars.list.mockResolvedValue([makeEnvVar({ id: 5, key: "API_TOKEN" })]);
    mockedEnvVars.rotate.mockResolvedValue(makeEnvVar());
    renderTable();

    const actionsTrigger = await screen.findByRole("button", { name: "Acciones de API_TOKEN" });
    actionsTrigger.focus();
    fireEvent.keyDown(actionsTrigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitem", { name: /Rotar valor/ }));

    fireEvent.change(await screen.findByLabelText("Nuevo valor"), {
      target: { value: "valor-nuevo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Rotar valor" }));

    await waitFor(() => {
      expect(mockedEnvVars.rotate).toHaveBeenCalledWith(5, { value: "valor-nuevo" });
    });
  });

  it("eliminar pide confirmación antes de llamar al endpoint", async () => {
    mockedEnvVars.list.mockResolvedValue([makeEnvVar({ id: 5, key: "API_TOKEN" })]);
    mockedEnvVars.remove.mockResolvedValue(undefined);
    renderTable();

    const actionsTrigger = await screen.findByRole("button", { name: "Acciones de API_TOKEN" });
    actionsTrigger.focus();
    fireEvent.keyDown(actionsTrigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitem", { name: /Eliminar/ }));
    expect(mockedEnvVars.remove).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: "Eliminar" }));
    await waitFor(() => {
      expect(mockedEnvVars.remove).toHaveBeenCalledWith(5);
    });
  });

  it("el viewer ve la tabla pero ninguna acción de escritura", async () => {
    mockedEnvVars.list.mockResolvedValue([makeEnvVar({ key: "API_TOKEN" })]);
    renderTable("viewer");

    expect(await screen.findByText("API_TOKEN")).toBeInTheDocument();
    expect(screen.getByText(MASKED_VALUE)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nueva variable/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Acciones de API_TOKEN" })).not.toBeInTheDocument();
  });
});

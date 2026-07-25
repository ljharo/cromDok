import type { MouseEvent } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectDetailPage from "@/features/projects/ProjectDetailPage";
import { executionsViewQueryKey } from "@/features/executions/hooks";
import { authApi, projectsApi, runnersApi, triggersApi } from "@/api/endpoints";
import {
  createTestQueryClient,
  makeExecution,
  makeProject,
  makeRunner,
  makeUser,
} from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  projectsApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
  runnersApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
  },
  executionsApi: { list: vi.fn(), get: vi.fn(), logs: vi.fn() },
  triggersApi: { trigger: vi.fn() },
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);
const mockedProjects = vi.mocked(projectsApi);
const mockedRunners = vi.mocked(runnersApi);
const mockedTriggers = vi.mocked(triggersApi);
const mockedToast = vi.mocked(toast);

function renderPage(role: "admin" | "operator" | "viewer" = "operator") {
  mockedAuth.me.mockResolvedValue(makeUser({ role }));
  mockedProjects.get.mockResolvedValue(makeProject());
  const queryClient = createTestQueryClient();
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/projects/1"]}>
        <Routes>
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route path="/executions/:executionId" element={<div>Detalle de ejecución</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { queryClient, ...utils };
}

describe("ProjectDetailPage (tab Runners)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra los runners con la programación en texto legible", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner({ cron_expression: "*/5 * * * *" })]);
    renderPage();

    expect(await screen.findByText("Backup diario")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("*/5 * * * *")).toBeInTheDocument();
    // cronstrue con locale "es"
    expect(screen.getByText("Cada 5 minutos")).toBeInTheDocument();
  });

  it("el switch desactiva un runner activo y activa uno inactivo", async () => {
    mockedRunners.list.mockResolvedValue([
      makeRunner({ id: 1, name: "Activo", is_enabled: true }),
      makeRunner({ id: 2, name: "Inactivo", is_enabled: false }),
    ]);
    mockedRunners.disable.mockResolvedValue(makeRunner({ is_enabled: false }));
    mockedRunners.enable.mockResolvedValue(makeRunner({ id: 2, is_enabled: true }));
    renderPage();

    fireEvent.click(await screen.findByRole("switch", { name: "Activar o desactivar Activo" }));
    await waitFor(() => {
      expect(mockedRunners.disable).toHaveBeenCalledWith(1);
    });

    fireEvent.click(screen.getByRole("switch", { name: "Activar o desactivar Inactivo" }));
    await waitFor(() => {
      expect(mockedRunners.enable).toHaveBeenCalledWith(2);
    });
  });

  it("Ejecutar dispara el trigger, muestra toast con acción e invalida las ejecuciones", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner()]);
    mockedTriggers.trigger.mockResolvedValue(
      makeExecution({ id: 42, status: "queued", trigger_type: "manual" }),
    );
    const { queryClient } = renderPage();
    // Una vista de ejecuciones cacheada para comprobar la invalidación.
    queryClient.setQueryData(executionsViewQueryKey(1, 1), {
      executions: [],
      runnerNames: {},
    });

    fireEvent.click(await screen.findByRole("button", { name: "Ejecutar Backup diario" }));

    await waitFor(() => {
      expect(mockedTriggers.trigger).toHaveBeenCalledWith(1);
    });
    await waitFor(() => {
      expect(mockedToast.success).toHaveBeenCalledWith(
        "Ejecución encolada",
        expect.objectContaining({
          action: expect.objectContaining({ label: "Ver ejecución" }),
        }),
      );
    });
    await waitFor(() => {
      expect(queryClient.getQueryState(executionsViewQueryKey(1, 1))?.isInvalidated).toBe(true);
    });

    // La acción del toast navega al detalle de la ejecución encolada.
    const options = vi.mocked(toast.success).mock.calls[0][1] as {
      action: { onClick: (event: MouseEvent<HTMLButtonElement>) => void };
    };
    act(() => options.action.onClick({} as MouseEvent<HTMLButtonElement>));
    expect(await screen.findByText("Detalle de ejecución")).toBeInTheDocument();
  });

  it("muestra un toast de error si el trigger falla", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner()]);
    mockedTriggers.trigger.mockRejectedValue(new Error("boom"));
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Ejecutar Backup diario" }));

    await waitFor(() => {
      expect(mockedToast.error).toHaveBeenCalledWith("No se pudo encolar la ejecución");
    });
  });

  it("el botón de ejecutar se deshabilita mientras la mutación está en curso", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner()]);
    mockedTriggers.trigger.mockReturnValue(new Promise(() => {}));
    renderPage();

    const runButton = await screen.findByRole("button", {
      name: "Ejecutar Backup diario",
    });
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(runButton).toBeDisabled();
    });
    expect(mockedTriggers.trigger).toHaveBeenCalledTimes(1);
  });

  it("no se puede ejecutar un runner desactivado", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner({ is_enabled: false })]);
    renderPage();

    const runButton = await screen.findByRole("button", {
      name: "Ejecutar Backup diario",
    });
    expect(runButton).toBeDisabled();

    fireEvent.click(runButton);
    expect(mockedTriggers.trigger).not.toHaveBeenCalled();
  });

  it("muestra un estado vacío cuando el proyecto no tiene runners", async () => {
    mockedRunners.list.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/Este proyecto no tiene runners todavía/)).toBeInTheDocument();
  });

  it("el viewer no ve el switch ni las acciones de escritura", async () => {
    mockedRunners.list.mockResolvedValue([makeRunner()]);
    renderPage("viewer");

    expect(await screen.findByText("Backup diario")).toBeInTheDocument();
    expect(screen.queryByRole("switch")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nuevo runner/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Ejecutar Backup diario" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Acciones de Backup diario" }),
    ).not.toBeInTheDocument();
  });
});

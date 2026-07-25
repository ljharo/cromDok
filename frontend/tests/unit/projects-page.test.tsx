import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProjectsPage from "@/features/projects/ProjectsPage";
import { authApi, projectsApi, runnersApi } from "@/api/endpoints";
import { makeProject, makeRunner, makeUser, renderWithQuery } from "../helpers";

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
}));

const mockedAuth = vi.mocked(authApi);
const mockedProjects = vi.mocked(projectsApi);
const mockedRunners = vi.mocked(runnersApi);

function renderPage(role: "admin" | "operator" | "viewer" = "operator") {
  mockedAuth.me.mockResolvedValue(makeUser({ role }));
  return renderWithQuery(
    <MemoryRouter>
      <ProjectsPage />
    </MemoryRouter>,
  );
}

describe("ProjectsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lista los proyectos con su número de runners", async () => {
    mockedProjects.list.mockResolvedValue([makeProject()]);
    mockedRunners.list.mockResolvedValue([makeRunner(), makeRunner({ id: 2 })]);
    renderPage();

    expect(await screen.findByText("ETL nocturno")).toBeInTheDocument();
    expect(screen.getByText("Procesos batch")).toBeInTheDocument();
    expect(await screen.findByText("2 runners")).toBeInTheDocument();
    expect(mockedRunners.list).toHaveBeenCalledWith(1);
  });

  it("muestra un estado vacío cuando no hay proyectos", async () => {
    mockedProjects.list.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/No hay proyectos todavía/)).toBeInTheDocument();
  });

  it("crea un proyecto llamando al endpoint e invalida la lista", async () => {
    mockedProjects.list
      .mockResolvedValueOnce([])
      .mockResolvedValue([makeProject({ id: 5, name: "Nuevo" })]);
    mockedProjects.create.mockResolvedValue(makeProject({ id: 5, name: "Nuevo" }));
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Nuevo proyecto/ }));
    fireEvent.change(await screen.findByLabelText("Nombre"), {
      target: { value: "Nuevo" },
    });
    fireEvent.change(screen.getByLabelText("Descripción"), {
      target: { value: "Desc" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear proyecto" }));

    await waitFor(() => {
      expect(mockedProjects.create).toHaveBeenCalledWith({
        name: "Nuevo",
        description: "Desc",
      });
    });
    // Invalidation after the mutation refetches the active list query.
    await waitFor(() => {
      expect(mockedProjects.list).toHaveBeenCalledTimes(2);
    });
  });

  it("no envía el alta si el nombre está vacío", async () => {
    mockedProjects.list.mockResolvedValue([]);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Nuevo proyecto/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Crear proyecto" }));

    expect(await screen.findByText("El nombre es obligatorio")).toBeInTheDocument();
    expect(mockedProjects.create).not.toHaveBeenCalled();
  });

  it("el viewer no ve acciones de escritura", async () => {
    mockedProjects.list.mockResolvedValue([makeProject()]);
    mockedRunners.list.mockResolvedValue([]);
    renderPage("viewer");

    expect(await screen.findByText("ETL nocturno")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nuevo proyecto/ })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Acciones de ETL nocturno" }),
    ).not.toBeInTheDocument();
  });

  it("avisa de la cascada al eliminar un proyecto", async () => {
    mockedProjects.list.mockResolvedValue([makeProject()]);
    mockedRunners.list.mockResolvedValue([]);
    renderPage("admin");

    const trigger = await screen.findByRole("button", {
      name: "Acciones de ETL nocturno",
    });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByText("Eliminar"));

    expect(
      await screen.findByText(/Se eliminarán en cascada todos sus runners/),
    ).toBeInTheDocument();
  });
});

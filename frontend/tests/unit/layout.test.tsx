import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Layout from "@/components/Layout";
import { ThemeProvider } from "@/components/theme-provider";
import { authApi } from "@/api/endpoints";
import { makeUser, renderWithQuery } from "../helpers";
import type { User } from "@/types/user";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  usersApi: { list: vi.fn(), create: vi.fn(), remove: vi.fn(), resetPassword: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);

function renderLayout(user: User) {
  mockedAuth.me.mockResolvedValue(user);
  return renderWithQuery(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div>Contenido</div>} />
          </Route>
          <Route path="/login" element={<div>Página de login</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("Layout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("muestra la navegación y el usuario actual", async () => {
    renderLayout(makeUser());
    expect(await screen.findByRole("link", { name: "Proyectos" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ejecuciones" })).toBeInTheDocument();
    // Username y badge de rol coinciden en "admin" para este usuario.
    expect((await screen.findAllByText("admin")).length).toBeGreaterThan(0);
  });

  it("oculta las entradas Usuarios y API Keys a los no-admin", async () => {
    renderLayout(makeUser({ role: "viewer" }));
    await screen.findByRole("link", { name: "Proyectos" });
    expect(screen.queryByRole("link", { name: "Usuarios" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "API Keys" })).not.toBeInTheDocument();
  });

  it("muestra las entradas Usuarios y API Keys al admin", async () => {
    renderLayout(makeUser({ role: "admin" }));
    expect(await screen.findByRole("link", { name: "Usuarios" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  });

  it("muestra el aviso cuando el usuario debe cambiar su contraseña", async () => {
    renderLayout(makeUser({ must_change_password: true }));
    expect(
      await screen.findByText(/Tu contraseña es temporal y debes cambiarla/),
    ).toBeInTheDocument();
  });

  it("cierra sesión: llama a logout y redirige a /login", async () => {
    mockedAuth.logout.mockResolvedValue(undefined);
    renderLayout(makeUser());

    fireEvent.click(await screen.findByRole("button", { name: /Cerrar sesión/ }));

    await waitFor(() => {
      expect(mockedAuth.logout).toHaveBeenCalled();
    });
    expect(await screen.findByText("Página de login")).toBeInTheDocument();
  });
});

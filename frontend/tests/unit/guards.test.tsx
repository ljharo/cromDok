import { screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RequireAuth, RequireRole } from "@/features/auth/guards";
import { authApi } from "@/api/endpoints";
import { axiosError, makeUser, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  usersApi: { list: vi.fn(), create: vi.fn(), remove: vi.fn(), resetPassword: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);

describe("guardas de rutas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("RequireAuth redirige a /login sin sesión", async () => {
    mockedAuth.me.mockRejectedValue(axiosError(401));

    renderWithQuery(
      <MemoryRouter initialEntries={["/privada"]}>
        <Routes>
          <Route path="/login" element={<div>Página de login</div>} />
          <Route
            path="/privada"
            element={
              <RequireAuth>
                <div>Zona privada</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Página de login")).toBeInTheDocument();
    expect(screen.queryByText("Zona privada")).not.toBeInTheDocument();
  });

  it("RequireAuth renderiza el contenido con sesión", async () => {
    mockedAuth.me.mockResolvedValue(makeUser());

    renderWithQuery(
      <MemoryRouter initialEntries={["/privada"]}>
        <Routes>
          <Route path="/login" element={<div>Página de login</div>} />
          <Route
            path="/privada"
            element={
              <RequireAuth>
                <div>Zona privada</div>
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Zona privada")).toBeInTheDocument();
  });

  it("RequireRole echa a los no-admin de las rutas de administración", async () => {
    mockedAuth.me.mockResolvedValue(makeUser({ role: "viewer" }));

    renderWithQuery(
      <MemoryRouter initialEntries={["/users"]}>
        <Routes>
          <Route path="/" element={<div>Inicio</div>} />
          <Route
            path="/users"
            element={
              <RequireRole role="admin">
                <div>Gestión de usuarios</div>
              </RequireRole>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Inicio")).toBeInTheDocument();
    expect(screen.queryByText("Gestión de usuarios")).not.toBeInTheDocument();
  });

  it("RequireRole deja pasar al admin", async () => {
    mockedAuth.me.mockResolvedValue(makeUser({ role: "admin" }));

    renderWithQuery(
      <MemoryRouter initialEntries={["/users"]}>
        <Routes>
          <Route path="/" element={<div>Inicio</div>} />
          <Route
            path="/users"
            element={
              <RequireRole role="admin">
                <div>Gestión de usuarios</div>
              </RequireRole>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Gestión de usuarios")).toBeInTheDocument();
  });
});

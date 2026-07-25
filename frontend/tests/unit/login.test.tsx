import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/features/auth/LoginPage";
import { authApi } from "@/api/endpoints";
import { axiosError, makeUser, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  usersApi: { list: vi.fn(), create: vi.fn(), remove: vi.fn(), resetPassword: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);

function renderLogin(initialEntry: string | { pathname: string; state: unknown } = "/login") {
  return renderWithQuery(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>Panel principal</div>} />
        <Route path="/users" element={<div>Gestión de usuarios</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Anonymous by default: /auth/me answers 401.
    mockedAuth.me.mockRejectedValue(axiosError(401));
  });

  it("renderiza el formulario de acceso", () => {
    renderLogin();
    expect(screen.getByText("CronDok")).toBeInTheDocument();
    expect(screen.getByLabelText("Usuario")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
  });

  it("valida los campos y no envía si están vacíos", async () => {
    renderLogin();
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => {
      expect(screen.getByText("El nombre de usuario es obligatorio")).toBeInTheDocument();
      expect(screen.getByText("La contraseña es obligatoria")).toBeInTheDocument();
    });
    expect(mockedAuth.login).not.toHaveBeenCalled();
  });

  it("envía las credenciales y redirige al destino original", async () => {
    const user = makeUser();
    mockedAuth.login.mockResolvedValue(user);

    renderLogin({ pathname: "/login", state: { from: "/users" } });
    fireEvent.change(screen.getByLabelText("Usuario"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "secreto-largo" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    await waitFor(() => {
      expect(mockedAuth.login).toHaveBeenCalledWith({
        username: "admin",
        password: "secreto-largo", // pragma: allowlist secret
      });
    });
    expect(await screen.findByText("Gestión de usuarios")).toBeInTheDocument();
  });

  it("muestra un error visible ante un 401", async () => {
    mockedAuth.login.mockRejectedValue(axiosError(401));

    renderLogin();
    fireEvent.change(screen.getByLabelText("Usuario"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "mal" } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Usuario o contraseña incorrectos.");
  });

  it("redirige al panel si ya hay sesión activa", async () => {
    mockedAuth.me.mockResolvedValue(makeUser());

    renderLogin();
    expect(await screen.findByText("Panel principal")).toBeInTheDocument();
  });
});

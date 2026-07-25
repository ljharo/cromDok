import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "@/features/users/UsersPage";
import { authApi, usersApi } from "@/api/endpoints";
import { makeUser, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  usersApi: { list: vi.fn(), create: vi.fn(), remove: vi.fn(), resetPassword: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);
const mockedUsers = vi.mocked(usersApi);

const USERS = [
  makeUser({ id: 1, username: "admin", role: "admin" }),
  makeUser({ id: 2, username: "oper", role: "operator" }),
];

function renderPage() {
  mockedAuth.me.mockResolvedValue(USERS[0]);
  return renderWithQuery(
    <MemoryRouter>
      <UsersPage />
    </MemoryRouter>,
  );
}

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lista los usuarios en una tabla", async () => {
    mockedUsers.list.mockResolvedValue(USERS);
    renderPage();

    expect(await screen.findByText("oper")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("Administrador")).toBeInTheDocument();
    expect(screen.getByText("Operador")).toBeInTheDocument();
  });

  it("no envía el alta si la contraseña es demasiado corta", async () => {
    mockedUsers.list.mockResolvedValue(USERS);
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Nuevo usuario/ }));
    fireEvent.change(await screen.findByLabelText("Usuario"), { target: { value: "nuevo" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), { target: { value: "corta" } });
    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));

    expect(
      await screen.findByText("La contraseña debe tener al menos 12 caracteres"),
    ).toBeInTheDocument();
    expect(mockedUsers.create).not.toHaveBeenCalled();
  });

  it("crea un usuario con rol por defecto viewer", async () => {
    mockedUsers.list.mockResolvedValue(USERS);
    mockedUsers.create.mockResolvedValue(makeUser({ id: 3, username: "nuevo", role: "viewer" }));
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Nuevo usuario/ }));
    fireEvent.change(await screen.findByLabelText("Usuario"), { target: { value: "nuevo" } });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "contraseña-larga-12" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear usuario" }));

    await waitFor(() => {
      expect(mockedUsers.create).toHaveBeenCalledWith({
        username: "nuevo",
        password: "contraseña-larga-12", // pragma: allowlist secret
        role: "viewer",
      });
    });
  });
});

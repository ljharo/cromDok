import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApiKeysPage from "@/features/api-keys/ApiKeysPage";
import { apiKeysApi, authApi } from "@/api/endpoints";
import { makeApiKey, makeUser, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  authApi: { login: vi.fn(), logout: vi.fn(), me: vi.fn() },
  apiKeysApi: { list: vi.fn(), create: vi.fn(), revoke: vi.fn() },
}));

const mockedAuth = vi.mocked(authApi);
const mockedApiKeys = vi.mocked(apiKeysApi);

function renderPage() {
  mockedAuth.me.mockResolvedValue(makeUser({ role: "admin" }));
  return renderWithQuery(
    <MemoryRouter>
      <ApiKeysPage />
    </MemoryRouter>,
  );
}

describe("ApiKeysPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
  });

  it("lista las API keys en una tabla", async () => {
    mockedApiKeys.list.mockResolvedValue([
      makeApiKey({ id: 1, name: "ci-pipeline" }),
      makeApiKey({ id: 2, name: "monitoring", revoked: true }),
    ]);
    renderPage();

    expect(await screen.findByText("ci-pipeline")).toBeInTheDocument();
    expect(screen.getByText("monitoring")).toBeInTheDocument();
    expect(screen.getByText("Activa")).toBeInTheDocument();
    expect(screen.getByText("Revocada")).toBeInTheDocument();
  });

  it("crear muestra el token una única vez", async () => {
    mockedApiKeys.list.mockResolvedValue([]);
    mockedApiKeys.create.mockResolvedValue({
      ...makeApiKey({ name: "nueva" }),
      token: "crondok_secret-token-value",
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Nueva API key/ }));
    fireEvent.change(await screen.findByLabelText("Nombre"), { target: { value: "nueva" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /Ejecutar runners/ }));
    fireEvent.click(screen.getByRole("button", { name: "Crear API key" }));

    await waitFor(() => {
      expect(mockedApiKeys.create).toHaveBeenCalledWith({
        name: "nueva",
        scopes: ["runners:execute"],
      });
    });
    expect(await screen.findByText("crondok_secret-token-value")).toBeInTheDocument();

    // Cerrar y reabrir no debe volver a mostrar el token.
    fireEvent.click(screen.getByRole("button", { name: "Listo" }));
    fireEvent.click(await screen.findByRole("button", { name: /Nueva API key/ }));
    expect(screen.queryByText("crondok_secret-token-value")).not.toBeInTheDocument();
  });

  it("revocar pide confirmación antes de llamar al endpoint", async () => {
    mockedApiKeys.list.mockResolvedValue([makeApiKey({ id: 5, name: "ci-pipeline" })]);
    mockedApiKeys.revoke.mockResolvedValue(undefined);
    renderPage();

    const actionsTrigger = await screen.findByRole("button", { name: "Acciones de ci-pipeline" });
    actionsTrigger.focus();
    fireEvent.keyDown(actionsTrigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("menuitem", { name: /Revocar/ }));
    expect(mockedApiKeys.revoke).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: "Revocar" }));
    await waitFor(() => {
      expect(mockedApiKeys.revoke).toHaveBeenCalledWith(5);
    });
  });
});

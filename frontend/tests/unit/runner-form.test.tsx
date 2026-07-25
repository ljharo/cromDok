import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AxiosError } from "axios";
import type { InternalAxiosRequestConfig, AxiosResponse } from "axios";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import RunnerFormPage from "@/features/runners/RunnerFormPage";
import { languageExtension } from "@/features/runners/components/language-extension";
import { authApi, runnersApi } from "@/api/endpoints";
import { makeRunner, makeUser, renderWithQuery } from "../helpers";

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
}));

// CodeMirror does not run under jsdom; swap the editor for a textarea that
// still exposes the selected language, so tests can assert the highlighting
// follows the language select.
vi.mock("@/features/runners/components/ScriptEditor", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/features/runners/components/ScriptEditor")>();
  return {
    ...actual,
    default: ({
      value,
      onChange,
      language,
    }: {
      value: string;
      onChange: (value: string) => void;
      language: string;
    }) => (
      <textarea
        aria-label="Script del runner"
        data-language={language}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    ),
  };
});

const mockedAuth = vi.mocked(authApi);
const mockedRunners = vi.mocked(runnersApi);

// jsdom lacks the pointer APIs that Radix Select needs.
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

function axiosErrorWithDetail(status: number, detail: unknown): AxiosError {
  const config = { headers: {} } as unknown as InternalAxiosRequestConfig;
  const response = {
    status,
    statusText: "",
    headers: {},
    config,
    data: { detail },
  } as AxiosResponse;
  return new AxiosError("Request failed", "ERR_BAD_RESPONSE", config, undefined, response);
}

function renderCreatePage() {
  mockedAuth.me.mockResolvedValue(makeUser({ role: "operator" }));
  return renderWithQuery(
    <MemoryRouter initialEntries={["/projects/1/runners/new"]}>
      <Routes>
        <Route path="/projects/:projectId/runners/new" element={<RunnerFormPage />} />
        <Route path="/projects/:projectId/runners/:runnerId/edit" element={<RunnerFormPage />} />
        <Route path="/projects/:projectId" element={<p>Detalle del proyecto</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Backup diario" } });
  fireEvent.change(screen.getByLabelText("Expresión cron"), {
    target: { value: "*/5 * * * *" },
  });
  fireEvent.change(screen.getByLabelText("Script del runner"), {
    target: { value: "print('hola')" },
  });
}

describe("RunnerFormPage (crear)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("no envía el formulario con una expresión cron inválida", async () => {
    renderCreatePage();

    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Backup" } });
    fireEvent.change(screen.getByLabelText("Expresión cron"), {
      target: { value: "esto no es cron" },
    });
    fireEvent.change(screen.getByLabelText("Script del runner"), {
      target: { value: "print(1)" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Crear runner" }));

    expect(await screen.findByText("Expresión cron no válida")).toBeInTheDocument();
    expect(mockedRunners.create).not.toHaveBeenCalled();
  });

  it("muestra una descripción legible de la expresión cron", async () => {
    renderCreatePage();

    fireEvent.change(screen.getByLabelText("Expresión cron"), {
      target: { value: "*/5 * * * *" },
    });

    expect(await screen.findByText("Cada 5 minutos")).toBeInTheDocument();
  });

  it("envía el payload correcto y vuelve al detalle del proyecto", async () => {
    mockedRunners.create.mockResolvedValue(makeRunner());
    renderCreatePage();

    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Crear runner" }));

    await waitFor(() => {
      expect(mockedRunners.create).toHaveBeenCalledWith({
        project_id: 1,
        name: "Backup diario",
        language: "python",
        cron_expression: "*/5 * * * *",
        script_content: "print('hola')",
        timeout_seconds: 300,
        on_overlap: "skip",
        resource_limits: {
          memory_mb: 256,
          cpu_quota: 1.0,
          pids_limit: 100,
          network_enabled: false,
        },
      });
    });
    expect(await screen.findByText("Detalle del proyecto")).toBeInTheDocument();
  });

  it("el editor cambia de lenguaje al cambiar el select", async () => {
    renderCreatePage();

    expect(screen.getByLabelText("Script del runner")).toHaveAttribute("data-language", "python");

    const trigger = screen.getByRole("combobox", { name: "Lenguaje" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.click(await screen.findByRole("option", { name: "Node.js" }));

    expect(screen.getByLabelText("Script del runner")).toHaveAttribute("data-language", "node");
  });

  it("mapea el 422 del backend (detalle string) al campo cron", async () => {
    mockedRunners.create.mockRejectedValue(
      axiosErrorWithDetail(422, "Invalid cron expression: campo fuera de rango"),
    );
    renderCreatePage();

    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Crear runner" }));

    expect(
      await screen.findByText("Invalid cron expression: campo fuera de rango"),
    ).toBeInTheDocument();
  });

  it("mapea los errores 422 de validación (lista loc/msg) a sus campos", async () => {
    mockedRunners.create.mockRejectedValue(
      axiosErrorWithDetail(422, [
        { loc: ["body", "timeout_seconds"], msg: "Input should be greater than 0" },
      ]),
    );
    renderCreatePage();

    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Crear runner" }));

    expect(await screen.findByText("Input should be greater than 0")).toBeInTheDocument();
  });
});

describe("RunnerFormPage (editar)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("carga el runner y envía el PATCH con los cambios", async () => {
    mockedAuth.me.mockResolvedValue(makeUser({ role: "operator" }));
    mockedRunners.get.mockResolvedValue(
      makeRunner({ id: 7, name: "Backup diario", cron_expression: "0 3 * * *" }),
    );
    mockedRunners.update.mockResolvedValue(makeRunner({ id: 7 }));

    renderWithQuery(
      <MemoryRouter initialEntries={["/projects/1/runners/7/edit"]}>
        <Routes>
          <Route path="/projects/:projectId/runners/new" element={<RunnerFormPage />} />
          <Route path="/projects/:projectId/runners/:runnerId/edit" element={<RunnerFormPage />} />
          <Route path="/projects/:projectId" element={<p>Detalle del proyecto</p>} />
        </Routes>
      </MemoryRouter>,
    );

    const nameInput = await screen.findByLabelText("Nombre");
    await waitFor(() => expect(nameInput).toHaveValue("Backup diario"));
    expect(screen.getByLabelText("Expresión cron")).toHaveValue("0 3 * * *");

    fireEvent.change(nameInput, { target: { value: "Backup semanal" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => {
      expect(mockedRunners.update).toHaveBeenCalledWith(7, {
        name: "Backup semanal",
        language: "python",
        cron_expression: "0 3 * * *",
        script_content: "echo ok",
        timeout_seconds: 300,
        on_overlap: "skip",
        resource_limits: {
          memory_mb: 256,
          cpu_quota: 1.0,
          pids_limit: 100,
          network_enabled: false,
        },
      });
    });
    expect(await screen.findByText("Detalle del proyecto")).toBeInTheDocument();
  });
});

describe("languageExtension", () => {
  it("devuelve una extensión de highlighting por lenguaje", () => {
    expect(languageExtension("python")).toBeTruthy();
    expect(languageExtension("node")).toBeTruthy();
    expect(languageExtension("bash")).toBeTruthy();
  });
});

import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ExecutionDetailPage from "@/features/executions/ExecutionDetailPage";
import { LOG_POLL_INTERVAL_MS, useExecutionLogs } from "@/features/executions/hooks";
import { executionsApi } from "@/api/endpoints";
import { makeExecution, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  executionsApi: { list: vi.fn(), get: vi.fn(), logs: vi.fn() },
}));

const mockedExecutions = vi.mocked(executionsApi);

/** Flush the pending promise chain (works with fake timers). */
async function flush() {
  await act(async () => {});
}

describe("useExecutionLogs (polling incremental con offset)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("acumula chunks usando el offset de la respuesta anterior", async () => {
    vi.useFakeTimers();
    mockedExecutions.logs
      .mockResolvedValueOnce({ chunk: "línea 1\n", offset: 8 })
      .mockResolvedValueOnce({ chunk: "línea 2\n", offset: 16 })
      .mockResolvedValue({ chunk: "", offset: 16 });

    const { result } = renderHook(() => useExecutionLogs(7, true));
    await flush();

    expect(mockedExecutions.logs).toHaveBeenCalledWith(7, 0);
    expect(result.current.text).toBe("línea 1\n");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOG_POLL_INTERVAL_MS);
    });
    expect(mockedExecutions.logs).toHaveBeenCalledWith(7, 8);
    expect(result.current.text).toBe("línea 1\nlínea 2\n");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOG_POLL_INTERVAL_MS);
    });
    expect(mockedExecutions.logs).toHaveBeenCalledWith(7, 16);
    expect(result.current.text).toBe("línea 1\nlínea 2\n");
  });

  it("deja de hacer polling al llegar a estado terminal (live pasa a false)", async () => {
    vi.useFakeTimers();
    mockedExecutions.logs.mockResolvedValue({ chunk: "", offset: 0 });

    const { rerender } = renderHook(({ live }) => useExecutionLogs(7, live), {
      initialProps: { live: true },
    });
    await flush();
    expect(mockedExecutions.logs).toHaveBeenCalledTimes(1);

    // Al pasar a terminal el efecto se re-ejecuta una última vez (fetch final)
    // y no vuelve a programar el intervalo.
    rerender({ live: false });
    await flush();
    expect(mockedExecutions.logs).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(LOG_POLL_INTERVAL_MS * 5);
    });
    expect(mockedExecutions.logs).toHaveBeenCalledTimes(2);
  });
});

describe("ExecutionDetailPage (visor de logs)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedExecutions.logs.mockResolvedValue({ chunk: "hola\n", offset: 5 });
  });

  function renderPage() {
    return renderWithQuery(
      <MemoryRouter initialEntries={["/executions/5"]}>
        <Routes>
          <Route path="/executions/:executionId" element={<ExecutionDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("muestra la metadata, el badge EN VIVO mientras running y los logs", async () => {
    mockedExecutions.get.mockResolvedValue(
      makeExecution({ id: 5, status: "running", exit_code: null, duration_ms: null }),
    );
    renderPage();

    expect(await screen.findByText("Ejecución #5")).toBeInTheDocument();
    expect(screen.getByText("En ejecución")).toBeInTheDocument();
    expect(screen.getByText("EN VIVO")).toBeInTheDocument();
    // El hook hace un fetch inicial (live=false) y otro al detectar running.
    await waitFor(() => expect(screen.getByTestId("log-viewer").textContent).toContain("hola"));
  });

  it("no muestra EN VIVO en estado terminal", async () => {
    mockedExecutions.get.mockResolvedValue(makeExecution({ id: 5, status: "succeeded" }));
    renderPage();

    expect(await screen.findByText("Ejecución #5")).toBeInTheDocument();
    expect(screen.getByText("Éxito")).toBeInTheDocument();
    expect(screen.queryByText("EN VIVO")).not.toBeInTheDocument();
  });

  it("el toggle de auto-scroll activa y desactiva el desplazamiento al final", async () => {
    mockedExecutions.get.mockResolvedValue(makeExecution({ id: 5, status: "succeeded" }));
    renderPage();

    const viewer = await screen.findByTestId("log-viewer");
    // Esperar a que los logs iniciales se asienten antes de espiar el scroll.
    await waitFor(() => expect(viewer.textContent).toContain("hola"));
    const setScrollTop = vi.fn();
    Object.defineProperty(viewer, "scrollTop", { set: setScrollTop, configurable: true });

    const toggle = screen.getByRole("switch", { name: "Auto-scroll de logs" });
    expect(toggle).toHaveAttribute("aria-checked", "true");

    // Desactivar: el efecto se dispara pero no debe desplazar.
    fireEvent.click(toggle);
    await flush();
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(setScrollTop).not.toHaveBeenCalled();

    // Reactivar: vuelve a desplazar al final.
    fireEvent.click(toggle);
    await flush();
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(setScrollTop).toHaveBeenCalled();
  });
});

import { act, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ExecutionsTable from "@/features/executions/ExecutionsTable";
import { EXECUTIONS_POLL_INTERVAL_MS } from "@/features/executions/hooks";
import { executionsApi, projectsApi, runnersApi } from "@/api/endpoints";
import { makeExecution, makeProject, makeRunner, renderWithQuery } from "../helpers";

vi.mock("@/api/endpoints", () => ({
  projectsApi: { list: vi.fn() },
  runnersApi: { list: vi.fn(), get: vi.fn() },
  executionsApi: { list: vi.fn(), get: vi.fn(), logs: vi.fn() },
}));

const mockedProjects = vi.mocked(projectsApi);
const mockedRunners = vi.mocked(runnersApi);
const mockedExecutions = vi.mocked(executionsApi);

function renderTable(runnerId?: number) {
  return renderWithQuery(
    <MemoryRouter>
      <ExecutionsTable runnerId={runnerId} />
    </MemoryRouter>,
  );
}

/** Flush the pending promise chain of the query (works with fake timers). */
async function flush() {
  // The aggregation queryFn chains several awaits; each needs its own tick.
  for (let i = 0; i < 5; i++) {
    await act(async () => {});
  }
}

describe("ExecutionsTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedProjects.list.mockResolvedValue([makeProject()]);
    mockedRunners.list.mockResolvedValue([makeRunner()]);
    mockedRunners.get.mockResolvedValue(makeRunner());
    mockedExecutions.list.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("agrega proyectos → runners → ejecuciones en la vista global", async () => {
    mockedProjects.list.mockResolvedValue([makeProject({ id: 1 }), makeProject({ id: 2 })]);
    mockedRunners.list
      .mockResolvedValueOnce([makeRunner({ id: 10, name: "R1" })])
      .mockResolvedValueOnce([makeRunner({ id: 20, name: "R2" })]);
    mockedExecutions.list
      .mockResolvedValueOnce([makeExecution({ id: 1, runner_id: 10 })])
      .mockResolvedValueOnce([makeExecution({ id: 2, runner_id: 20 })]);

    renderTable();
    await flush();

    expect(mockedRunners.list).toHaveBeenCalledWith(1);
    expect(mockedRunners.list).toHaveBeenCalledWith(2);
    expect(mockedExecutions.list).toHaveBeenCalledWith(10, { limit: 50 });
    expect(mockedExecutions.list).toHaveBeenCalledWith(20, { limit: 50 });
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.getByText("R2")).toBeInTheDocument();
  });

  it("renderiza cada estado con su badge y los ordena de más reciente a más antigua", async () => {
    mockedExecutions.list.mockResolvedValue([
      makeExecution({ id: 1, status: "queued", started_at: null }),
      makeExecution({ id: 2, status: "running", exit_code: null, duration_ms: null }),
      makeExecution({ id: 3, status: "succeeded" }),
      makeExecution({ id: 4, status: "failed", exit_code: 1 }),
      makeExecution({ id: 5, status: "killed", exit_code: 137 }),
      makeExecution({ id: 6, status: "skipped", exit_code: null }),
    ]);

    renderTable();

    expect((await screen.findByText("En cola")).className).toContain("bg-slate-500");
    expect(screen.getByText("En ejecución").className).toContain("bg-blue-600");
    expect(screen.getByText("Éxito").className).toContain("bg-green-600");
    expect(screen.getByText("Fallida").className).toContain("bg-red-600");
    expect(screen.getByText("Detenida").className).toContain("bg-orange-500");
    expect(screen.getByText("Omitida").className).toContain("bg-yellow-500");

    const rows = screen
      .getAllByRole("row", { name: /Ejecución \d+ de / })
      .map((row) => row.getAttribute("aria-label"));
    expect(rows).toEqual([
      "Ejecución 6 de Backup diario",
      "Ejecución 5 de Backup diario",
      "Ejecución 4 de Backup diario",
      "Ejecución 3 de Backup diario",
      "Ejecución 2 de Backup diario",
      "Ejecución 1 de Backup diario",
    ]);
  });

  it("con runnerId solo consulta ese runner y no la agregación global", async () => {
    mockedRunners.get.mockResolvedValue(makeRunner({ id: 5, name: "Solo este" }));
    mockedExecutions.list.mockResolvedValue([makeExecution({ runner_id: 5 })]);

    renderTable(5);

    expect(await screen.findByText("Solo este")).toBeInTheDocument();
    expect(mockedRunners.get).toHaveBeenCalledWith(5);
    expect(mockedExecutions.list).toHaveBeenCalledWith(5, { limit: 50 });
    expect(mockedProjects.list).not.toHaveBeenCalled();
    expect(mockedRunners.list).not.toHaveBeenCalled();
  });

  it("no vuelve a pedir datos cuando todas las ejecuciones están en estado terminal", async () => {
    vi.useFakeTimers();
    mockedExecutions.list.mockResolvedValue([makeExecution({ status: "succeeded" })]);

    renderTable();
    await flush();
    expect(mockedExecutions.list).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EXECUTIONS_POLL_INTERVAL_MS * 4);
    });
    expect(mockedExecutions.list).toHaveBeenCalledTimes(1);
  });

  it("hace polling mientras haya ejecuciones en cola o en ejecución", async () => {
    vi.useFakeTimers();
    mockedExecutions.list.mockResolvedValue([makeExecution({ status: "running" })]);

    renderTable();
    await flush();
    expect(mockedExecutions.list).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EXECUTIONS_POLL_INTERVAL_MS);
    });
    expect(mockedExecutions.list).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(EXECUTIONS_POLL_INTERVAL_MS);
    });
    expect(mockedExecutions.list).toHaveBeenCalledTimes(3);
  });
});

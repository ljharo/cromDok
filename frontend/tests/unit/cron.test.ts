import { describe, expect, it } from "vitest";

import { cronToSchedule, scheduleToCron, type Schedule } from "@/lib/cron";

describe("scheduleToCron", () => {
  it("cada N minutos", () => {
    expect(scheduleToCron({ type: "minutes", interval: 5 })).toBe("*/5 * * * *");
  });

  it("cada N horas", () => {
    expect(scheduleToCron({ type: "hours", interval: 2 })).toBe("0 */2 * * *");
  });

  it("diario a una hora fija", () => {
    expect(scheduleToCron({ type: "daily", hour: 7, minute: 30 })).toBe("30 7 * * *");
  });

  it("semanal en días concretos, ordenados", () => {
    expect(scheduleToCron({ type: "weekly", days: [4, 2], hour: 7, minute: 0 })).toBe(
      "0 7 * * 2,4",
    );
  });

  it("mensual en un día concreto", () => {
    expect(scheduleToCron({ type: "monthly", day: 15, hour: 3, minute: 0 })).toBe("0 3 15 * *");
  });
});

describe("cronToSchedule", () => {
  const cases: [string, Schedule][] = [
    ["*/5 * * * *", { type: "minutes", interval: 5 }],
    ["0 */2 * * *", { type: "hours", interval: 2 }],
    ["30 7 * * *", { type: "daily", hour: 7, minute: 30 }],
    ["0 7 * * 2,4", { type: "weekly", days: [2, 4], hour: 7, minute: 0 }],
    ["0 3 15 * *", { type: "monthly", day: 15, hour: 3, minute: 0 }],
  ];

  it.each(cases)("reconoce %s como preset", (cron, expected) => {
    expect(cronToSchedule(cron)).toEqual(expected);
  });

  it("es el inverso exacto de scheduleToCron para cada preset", () => {
    for (const [, schedule] of cases) {
      expect(cronToSchedule(scheduleToCron(schedule))).toEqual(schedule);
    }
  });

  it("devuelve null para expresiones que no coinciden con ningún preset", () => {
    expect(cronToSchedule("*/5 */3 * * *")).toBeNull(); // step en dos campos a la vez
    expect(cronToSchedule("0 3 * 6 *")).toBeNull(); // mes fijo, no soportado
    expect(cronToSchedule("0 3 1 * 1")).toBeNull(); // día del mes Y día de semana a la vez
    expect(cronToSchedule("not a cron")).toBeNull();
    expect(cronToSchedule("* * * *")).toBeNull(); // 4 campos, no 5
  });

  it("acepta días de semana duplicados sin romperse", () => {
    expect(cronToSchedule("0 7 * * 2,2,4")).toEqual({
      type: "weekly",
      days: [2, 4],
      hour: 7,
      minute: 0,
    });
  });
});

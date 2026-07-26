import cronstrue from "cronstrue/i18n";

/**
 * Human-readable Spanish description of a cron expression.
 * Falls back to the raw expression when it cannot be parsed
 * (the backend is the ultimate validator anyway).
 */
export function describeCron(expression: string): string {
  try {
    return cronstrue.toString(expression, { locale: "es" });
  } catch {
    return expression;
  }
}

/**
 * Client-side sanity check for cron expressions: cronstrue throws on
 * anything it cannot parse. The backend stays the ultimate validator
 * (a 422 there is mapped back to the form field).
 */
export function isValidCron(expression: string): boolean {
  try {
    cronstrue.toString(expression);
    return true;
  } catch {
    return false;
  }
}

// --- Schedule builder: friendly presets <-> raw cron -----------------------
//
// The "Simple" tab of ScheduleBuilder never needs full cron generality — it
// only needs to generate (and recognize, when editing) these five shapes.
// Anything else (a hand-written or imported expression) falls back to the
// "Avanzado" raw-text tab untouched.

/** Cron day-of-week: 0 = domingo ... 6 = sábado (standard cron numbering). */
export type WeekDay = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export const WEEKDAY_LABELS: Record<WeekDay, string> = {
  1: "Lun",
  2: "Mar",
  3: "Mié",
  4: "Jue",
  5: "Vie",
  6: "Sáb",
  0: "Dom",
};

/** Monday-first display order (cron itself numbers Sunday as 0). */
export const WEEKDAY_ORDER: WeekDay[] = [1, 2, 3, 4, 5, 6, 0];

export type Schedule =
  | { type: "minutes"; interval: number }
  | { type: "hours"; interval: number }
  | { type: "daily"; hour: number; minute: number }
  | { type: "weekly"; days: WeekDay[]; hour: number; minute: number }
  | { type: "monthly"; day: number; hour: number; minute: number };

export function scheduleToCron(schedule: Schedule): string {
  switch (schedule.type) {
    case "minutes":
      return `*/${schedule.interval} * * * *`;
    case "hours":
      return `0 */${schedule.interval} * * *`;
    case "daily":
      return `${schedule.minute} ${schedule.hour} * * *`;
    case "weekly": {
      const days = [...schedule.days].sort((a, b) => a - b);
      return `${schedule.minute} ${schedule.hour} * * ${days.join(",")}`;
    }
    case "monthly":
      return `${schedule.minute} ${schedule.hour} ${schedule.day} * *`;
  }
}

/**
 * Best-effort reverse of scheduleToCron. Returns null when the expression
 * doesn't match one of the five preset shapes (e.g. a custom/complex cron
 * written by hand) — the caller falls back to the raw "Avanzado" tab.
 */
export function cronToSchedule(expression: string): Schedule | null {
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5) return null;
  const [min, hour, dom, month, dow] = parts;
  if (month !== "*") return null;

  const minuteStep = /^\*\/([1-9]\d*)$/.exec(min);
  if (minuteStep && hour === "*" && dom === "*" && dow === "*") {
    return { type: "minutes", interval: Number(minuteStep[1]) };
  }

  const hourStep = /^\*\/([1-9]\d*)$/.exec(hour);
  if (min === "0" && hourStep && dom === "*" && dow === "*") {
    return { type: "hours", interval: Number(hourStep[1]) };
  }

  if (!/^\d+$/.test(min) || !/^\d+$/.test(hour)) return null;
  const minute = Number(min);
  const hourNum = Number(hour);

  if (dom === "*" && dow === "*") {
    return { type: "daily", hour: hourNum, minute };
  }
  if (dom === "*" && /^[0-6](,[0-6])*$/.test(dow)) {
    const days = [...new Set(dow.split(",").map(Number))] as WeekDay[];
    return { type: "weekly", days, hour: hourNum, minute };
  }
  if (dow === "*" && /^([1-9]|[12]\d|3[01])$/.test(dom)) {
    return { type: "monthly", day: Number(dom), hour: hourNum, minute };
  }
  return null;
}

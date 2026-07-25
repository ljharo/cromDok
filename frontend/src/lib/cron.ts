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

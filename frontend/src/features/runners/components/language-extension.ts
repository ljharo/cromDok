import { StreamLanguage } from "@codemirror/language";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { shell } from "@codemirror/legacy-modes/mode/shell";

import type { RunnerLanguage } from "@/types/runner";

/** CodeMirror highlighting extension for each runner language. */
export function languageExtension(language: RunnerLanguage) {
  switch (language) {
    case "python":
      return python();
    case "node":
      return javascript();
    case "bash":
      return StreamLanguage.define(shell);
  }
}

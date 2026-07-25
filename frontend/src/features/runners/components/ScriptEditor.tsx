import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";

import { languageExtension } from "./language-extension";
import type { RunnerLanguage } from "@/types/runner";

interface ScriptEditorProps {
  value: string;
  language: RunnerLanguage;
  onChange: (value: string) => void;
  "aria-label"?: string;
}

/** Script editor (CodeMirror 6); highlighting follows the selected language. */
export default function ScriptEditor({
  value,
  language,
  onChange,
  "aria-label": ariaLabel = "Script del runner",
}: ScriptEditorProps) {
  const extensions = useMemo(() => [languageExtension(language)], [language]);

  return (
    <CodeMirror
      value={value}
      onChange={onChange}
      extensions={extensions}
      height="320px"
      basicSetup={{ lineNumbers: true, foldGutter: false }}
      aria-label={ariaLabel}
      className="overflow-hidden rounded-md border text-sm"
    />
  );
}

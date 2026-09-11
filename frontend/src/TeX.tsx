import katex from "katex";
import { useMemo } from "react";

/** Render LaTeX, falling back to the raw source when it will not parse.
 *  A malformed expression is information the user needs, not a blank space. */
export function TeX({ latex, display = false }: { latex: string; display?: boolean }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, { displayMode: display, throwOnError: true });
    } catch {
      return null;
    }
  }, [latex, display]);

  if (html === null) {
    return <code className="math-error" title="LaTeX could not be parsed">{latex}</code>;
  }
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Text with inline $...$ spans typeset. Prose routinely carries notation. */
export function RichText({ text }: { text: string }) {
  const parts = useMemo(() => text.split(/(\$[^$]+\$)/g), [text]);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("$") && part.endsWith("$") && part.length > 2 ? (
          <TeX key={index} latex={part.slice(1, -1)} />
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

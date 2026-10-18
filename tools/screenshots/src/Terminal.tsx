import React from "react";
import { loadFont } from "@remotion/google-fonts/JetBrainsMono";
import { CROP_KEY, term } from "./theme";

const { fontFamily } = loadFont("normal", { weights: ["400", "700"], subsets: ["latin"] });

export type TerminalProps = { width: number; lines: string[]; title?: string };

const SQL_WORDS = /\b(SELECT|INSERT INTO|UPDATE|DELETE|FROM|WHERE|JOIN|ORDER BY|GROUP BY|VALUES|RETURNING|LIMIT|BEGIN|COMMIT|AND|DESC|SET)\b/g;

/** Colours a log line roughly the way `docker compose logs` and a typical terminal do. */
const Line: React.FC<{ line: string }> = ({ line }) => {
  const service = line.match(/^(\S+-\d+\s+\|)(.*)$/);
  if (line.startsWith("sqlite>") || line.startsWith("$ ")) {
    return <div style={{ color: term.prompt, fontWeight: 700 }}>{line || " "}</div>;
  }
  if (!service) return <div style={{ color: term.text }}>{line || " "}</div>;

  const [, prefix, rest] = service;
  const log = rest.match(/^( \d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) (INFO|WARNING|ERROR) ([\w.]+): (.*)$/);
  const highlight = (text: string) =>
    text.split(SQL_WORDS).map((part, i) =>
      i % 2 === 1 ? (
        <span key={i} style={{ color: "#c586c0" }}>
          {part}
        </span>
      ) : (
        part.split(/(added|finished|rendered|handled|New user)/).map((p, j) =>
          j % 2 === 1 ? (
            <span key={`${i}-${j}`} style={{ color: term.green }}>
              {p}
            </span>
          ) : (
            p
          ),
        )
      ),
    );

  return (
    <div style={{ color: term.text }}>
      <span style={{ color: term.service }}>{prefix}</span>
      {log ? (
        <>
          <span style={{ color: term.dim }}>{log[1]}</span>{" "}
          <span style={{ color: log[2] === "INFO" ? term.info : term.warning }}>{log[2]}</span>{" "}
          <span style={{ color: term.dim }}>{log[3]}:</span> {highlight(log[4])}
        </>
      ) : (
        highlight(rest)
      )}
    </div>
  );
};

export const Terminal: React.FC<TerminalProps> = ({ width, lines }) => (
  <div style={{ width, height: "100%", background: CROP_KEY }}>
    <div
      style={{
        background: term.background,
        padding: "10px 12px",
        fontFamily,
        fontSize: 13,
        lineHeight: "19px",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}
    >
      {lines.map((line, i) => (
        <Line key={i} line={line} />
      ))}
    </div>
  </div>
);
